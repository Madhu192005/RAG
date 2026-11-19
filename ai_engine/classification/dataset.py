"""Dataset validation, deduplication, class reporting, and deterministic splits.

Input is dataset/raw/<safe class directory>/*; output is ImageFolder-compatible
dataset/processed/{train,validation,test}/<class>/*. Dataset images are not committed.
"""
import argparse
import hashlib
import json
import random
import shutil
from pathlib import Path

from ai_engine.classification.class_mapping import (
    CLASS_LABELS, DATASET_CLASS_NAMES, canonical_label_for_source,
)
from ai_engine.classification.preprocessing import InvalidImageError, decode_image

def prepare_dataset(raw_dir: Path, output_dir: Path, seed: int = 42, ratios=(0.7, 0.15, 0.15)):
    if abs(sum(ratios) - 1) > 1e-9:
        raise ValueError("Split ratios must sum to 1.")
    random.seed(seed)
    seen, report = set(), {"seed": seed, "classes": {}, "source_label_mapping": {}, "duplicates": 0, "invalid": []}
    source_folders = {label: [] for label in CLASS_LABELS}
    if raw_dir.exists():
        for folder in raw_dir.iterdir():
            if folder.is_dir():
                mapped = canonical_label_for_source(folder.name)
                if mapped:
                    source_folders[mapped].append(folder)
                    report["source_label_mapping"][folder.name] = mapped
    for split in ("train", "validation", "test"):
        (output_dir / split).mkdir(parents=True, exist_ok=True)
    for label in CLASS_LABELS:
        class_dir = DATASET_CLASS_NAMES.get(label, label)
        paths = sorted(path for folder in source_folders[label] for path in folder.glob("**/*"))
        valid = []
        for path in paths:
            if not path.is_file():
                continue
            try:
                data = path.read_bytes()
                decode_image(data)
                digest = hashlib.sha256(data).hexdigest()
                if digest in seen:
                    report["duplicates"] += 1
                    continue
                seen.add(digest)
                valid.append((path, digest))
            except (OSError, InvalidImageError) as exc:
                report["invalid"].append({"path": str(path), "reason": str(exc)})
        random.Random(seed).shuffle(valid)
        n = len(valid)
        n_train, n_val = int(n * ratios[0]), int(n * ratios[1])
        assignments = {"train": valid[:n_train], "validation": valid[n_train:n_train+n_val], "test": valid[n_train+n_val:]}
        for split, entries in assignments.items():
            folder = output_dir / split / class_dir
            folder.mkdir(parents=True, exist_ok=True)
            for index, (path, digest) in enumerate(entries):
                shutil.copy2(path, folder / f"{digest[:12]}_{index}{path.suffix.lower()}")
        report["classes"][label] = {key: len(value) for key, value in assignments.items()}
        report["classes"][label]["total"] = n
    (output_dir / "class_distribution.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, default=Path("dataset/raw"))
    parser.add_argument("--output", type=Path, default=Path("dataset/processed"))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    print(json.dumps(prepare_dataset(args.raw, args.output, args.seed), indent=2))
