"""Train MobileNetV3 on dataset/processed; training is never run by the API."""
import argparse
import json
import random
from pathlib import Path

import numpy as np
import torch
from sklearn.utils.class_weight import compute_class_weight
from torch import nn
from torch.utils.data import DataLoader, WeightedRandomSampler
from torchvision import datasets, transforms

from ai_engine.classification.class_mapping import CLASS_LABELS, DATASET_CLASS_DIRS
from ai_engine.classification.config import CHECKPOINT_PATH, IMAGE_SIZE, MODEL_VERSION
from ai_engine.classification.model import build_model

def train(data_dir: Path, output: Path = CHECKPOINT_PATH, epochs: int = 20, batch_size: int = 32,
          learning_rate: float = 1e-4, seed: int = 42, patience: int = 4):
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    if torch.cuda.is_available(): torch.cuda.manual_seed_all(seed)
    distribution_path = data_dir / "class_distribution.json"
    if distribution_path.exists():
        distribution = json.loads(distribution_path.read_text(encoding="utf-8"))
        missing = [label for label in CLASS_LABELS if distribution.get("classes", {}).get(label, {}).get("train", 0) == 0
                   or distribution.get("classes", {}).get(label, {}).get("validation", 0) == 0]
        if missing:
            raise ValueError(f"No train/validation examples for target classes: {missing}. Add reviewed images; no class metrics will be inferred.")
    mean, std = (0.485, 0.456, 0.406), (0.229, 0.224, 0.225)
    aug = transforms.Compose([transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)), transforms.RandomHorizontalFlip(),
                              transforms.ToTensor(), transforms.Normalize(mean, std)])
    plain = transforms.Compose([transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)), transforms.ToTensor(), transforms.Normalize(mean, std)])
    train_ds = datasets.ImageFolder(data_dir / "train", transform=aug)
    val_ds = datasets.ImageFolder(data_dir / "validation", transform=plain)
    if train_ds.classes != DATASET_CLASS_DIRS or val_ds.classes != DATASET_CLASS_DIRS:
        raise ValueError(f"Expected all eight class directories, in order: {DATASET_CLASS_DIRS}; found {train_ds.classes}")
    if not len(train_ds) or not len(val_ds): raise ValueError("Training and validation splits must contain images.")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    counts = np.bincount(train_ds.targets, minlength=len(CLASS_LABELS))
    weights = compute_class_weight("balanced", classes=np.arange(len(CLASS_LABELS)), y=np.asarray(train_ds.targets))
    sampler = WeightedRandomSampler([weights[target] for target in train_ds.targets], len(train_ds), replacement=True)
    train_loader = DataLoader(train_ds, batch_size=batch_size, sampler=sampler, num_workers=0)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, num_workers=0)
    model = build_model(pretrained=True).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate)
    criterion = nn.CrossEntropyLoss()
    best_loss, stale = float("inf"), 0
    output.parent.mkdir(parents=True, exist_ok=True)
    for epoch in range(epochs):
        model.train(); train_loss = 0.0
        for images, labels in train_loader:
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad(set_to_none=True); loss = criterion(model(images), labels)
            loss.backward(); optimizer.step(); train_loss += loss.item() * labels.size(0)
        model.eval(); val_loss, correct = 0.0, 0; calibration_logits, calibration_targets = [], []
        with torch.inference_mode():
            for images, labels in val_loader:
                images, labels = images.to(device), labels.to(device); logits = model(images)
                val_loss += criterion(logits, labels).item() * labels.size(0)
                correct += (logits.argmax(1) == labels).sum().item()
                calibration_logits.append(logits.detach().cpu()); calibration_targets.append(labels.detach().cpu())
        val_loss /= len(val_ds)
        print(f"epoch={epoch+1} train_loss={train_loss/len(train_ds):.4f} val_loss={val_loss:.4f} val_accuracy={correct/len(val_ds):.4f}")
        if val_loss < best_loss:
            best_loss, stale = val_loss, 0
            logits_for_calibration = torch.cat(calibration_logits)
            targets_for_calibration = torch.cat(calibration_targets)
            log_temperature = torch.zeros(1, requires_grad=True)
            calibration_optimizer = torch.optim.LBFGS([log_temperature], lr=0.1, max_iter=50)
            def closure():
                calibration_optimizer.zero_grad()
                temperature_loss = nn.functional.cross_entropy(logits_for_calibration / log_temperature.exp(), targets_for_calibration)
                temperature_loss.backward()
                return temperature_loss
            calibration_optimizer.step(closure)
            temperature = float(log_temperature.detach().exp().clamp(0.05, 20).item())
            torch.save({"state_dict": model.cpu().state_dict(), "class_labels": CLASS_LABELS,
                        "model_version": MODEL_VERSION, "seed": seed, "class_counts": counts.tolist(),
                        "temperature": temperature}, output)
            model.to(device)
        else:
            stale += 1
            if stale >= patience: print("Early stopping."); break
    return output

if __name__ == "__main__":
    p = argparse.ArgumentParser(); p.add_argument("--data", type=Path, default=Path("dataset/processed"))
    p.add_argument("--output", type=Path, default=CHECKPOINT_PATH); p.add_argument("--epochs", type=int, default=20)
    p.add_argument("--batch-size", type=int, default=32); p.add_argument("--learning-rate", type=float, default=1e-4)
    p.add_argument("--seed", type=int, default=42); p.add_argument("--patience", type=int, default=4)
    a = p.parse_args(); train(a.data, a.output, a.epochs, a.batch_size, a.learning_rate, a.seed, a.patience)
