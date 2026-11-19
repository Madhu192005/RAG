"""Singleton-friendly checkpoint-backed inference service."""
from pathlib import Path
from threading import Lock

from ai_engine.classification.class_mapping import CLASS_LABELS
from ai_engine.classification.config import CHECKPOINT_PATH, IMAGE_SIZE, MODEL_VERSION, UNCERTAINTY_THRESHOLD
from ai_engine.classification.model import build_model
from ai_engine.classification.preprocessing import decode_image, preprocess_image

class ModelUnavailable(RuntimeError):
    pass

class WasteClassifier:
    def __init__(self, checkpoint: Path = CHECKPOINT_PATH, threshold: float = UNCERTAINTY_THRESHOLD):
        self.checkpoint = Path(checkpoint)
        self.threshold = threshold
        self.device = None
        self.model = None
        self.temperature = 1.0
        self._lock = Lock()

    def load(self):
        if self.model is not None:
            return
        with self._lock:
            self._load_locked()

    def _load_locked(self):
        if self.model is not None:
            return
        if not self.checkpoint.is_file():
            raise ModelUnavailable(f"Classifier checkpoint not found: {self.checkpoint}")
        try:
            import torch
        except ImportError as exc:
            raise ModelUnavailable("Install the configured PyTorch and Torchvision dependencies first.") from exc
        try:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            checkpoint = torch.load(self.checkpoint, map_location=self.device, weights_only=True)
            labels = checkpoint.get("class_labels", CLASS_LABELS)
            if labels != CLASS_LABELS:
                raise ModelUnavailable("Checkpoint class labels do not match the supported class order.")
            self.model = build_model(num_classes=len(CLASS_LABELS))
            self.model.load_state_dict(checkpoint["state_dict"])
            self.temperature = max(float(checkpoint.get("temperature", 1.0)), 1e-6)
            self.model.to(self.device).eval()
        except ModelUnavailable:
            raise
        except Exception as exc:
            raise ModelUnavailable("Classifier checkpoint could not be loaded.") from exc

    def predict(self, data: bytes):
        image = decode_image(data)
        self.load()
        import torch
        with self._lock, torch.inference_mode():
            logits = self.model(preprocess_image(image).unsqueeze(0).to(self.device)) / self.temperature
            scores = torch.softmax(logits, dim=1)[0]
        values, indexes = torch.topk(scores, k=min(3, len(CLASS_LABELS)))
        top = [{"class_name": CLASS_LABELS[i], "score": float(score)} for score, i in zip(values.cpu(), indexes.cpu())]
        score = top[0]["score"]
        if score < self.threshold:
            return {"status": "uncertain", "message": "The waste item could not be identified confidently. Please verify the item manually.", "prediction": None, "top_predictions": top, "confidence_score": score}
        return {"status": "success", "predicted_class": top[0]["class_name"], "confidence_score": score,
                "top_predictions": top, "model_version": MODEL_VERSION}
