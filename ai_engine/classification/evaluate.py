"""Evaluate a trained checkpoint on a separate test split and save honest metrics."""
import argparse
import json
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from torch.utils.data import DataLoader
from torchvision import datasets, transforms

from ai_engine.classification.class_mapping import CLASS_LABELS, DATASET_CLASS_DIRS
from ai_engine.classification.config import CHECKPOINT_PATH, IMAGE_SIZE
from ai_engine.classification.model import build_model

def evaluate(data_dir: Path, checkpoint_path: Path = CHECKPOINT_PATH, report_path: Path = Path("models/waste_classifier/evaluation.json")):
    if not checkpoint_path.is_file(): raise FileNotFoundError(f"Checkpoint missing: {checkpoint_path}")
    ds = datasets.ImageFolder(data_dir / "test", transform=transforms.Compose([
        transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)), transforms.ToTensor(),
        transforms.Normalize((.485,.456,.406),(.229,.224,.225))]))
    if ds.classes != DATASET_CLASS_DIRS or not ds: raise ValueError("Test set must contain all eight configured classes and images.")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=True)
    model = build_model(pretrained=False).to(device); model.load_state_dict(checkpoint["state_dict"]); model.eval()
    y_true, y_pred = [], []
    with torch.inference_mode():
        for x, y in DataLoader(ds, batch_size=32, shuffle=False, num_workers=0):
            y_pred.extend(model(x.to(device)).argmax(1).cpu().tolist()); y_true.extend(y.tolist())
    report = {"accuracy": accuracy_score(y_true, y_pred),
              "per_class": classification_report(y_true, y_pred, labels=list(range(8)), target_names=CLASS_LABELS, output_dict=True, zero_division=0),
              "confusion_matrix": confusion_matrix(y_true, y_pred, labels=list(range(8))).tolist(),
              "class_distribution": {label: int((np.asarray(y_true) == idx).sum()) for idx, label in enumerate(CLASS_LABELS)},
              "checkpoint": str(checkpoint_path), "metrics_are_test_split": True}
    report_path.parent.mkdir(parents=True, exist_ok=True); report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report

if __name__ == "__main__":
    p=argparse.ArgumentParser(); p.add_argument("--data",type=Path,default=Path("dataset/processed")); p.add_argument("--checkpoint",type=Path,default=CHECKPOINT_PATH); p.add_argument("--report",type=Path,default=Path("models/waste_classifier/evaluation.json")); a=p.parse_args()
    print(json.dumps(evaluate(a.data,a.checkpoint,a.report),indent=2))
