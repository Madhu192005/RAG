"""Resolve PDF inputs from an individual file or a directory."""

from pathlib import Path
from typing import List


def load_pdf_paths(path: Path) -> List[Path]:
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"Input path does not exist: {resolved}")
    if resolved.is_file():
        if resolved.suffix.lower() != ".pdf":
            raise ValueError(f"Input file is not a PDF: {resolved}")
        return [resolved]
    return sorted(
        item
        for item in resolved.rglob("*")
        if item.is_file() and item.suffix.lower() == ".pdf"
    )
