"""Classification configuration; no model is downloaded implicitly."""
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = Path(os.getenv("WASTE_MODEL_DIR", PROJECT_ROOT / "models" / "waste_classifier"))
CHECKPOINT_PATH = MODEL_DIR / "mobilenet_v3_large.pt"
IMAGE_SIZE = 224
MAX_UPLOAD_BYTES = int(os.getenv("WASTE_MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
MIN_IMAGE_SIDE = 32
MAX_IMAGE_SIDE = 10000
MAX_IMAGE_PIXELS = 40_000_000
UNCERTAINTY_THRESHOLD = float(os.getenv("WASTE_UNCERTAINTY_THRESHOLD", "0.55"))
MODEL_VERSION = "mobilenet_v3_large-v1"
