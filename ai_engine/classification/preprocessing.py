"""Safe image decoding and the shared MobileNetV3 input transform."""
from __future__ import annotations
from io import BytesIO

from ai_engine.classification.config import IMAGE_SIZE, MAX_IMAGE_PIXELS, MAX_IMAGE_SIDE, MIN_IMAGE_SIDE

class InvalidImageError(ValueError):
    pass

def decode_image(data: bytes) -> Image.Image:
    try:
        from PIL import Image, ImageFile, UnidentifiedImageError
    except ImportError as exc:
        raise RuntimeError("Install Pillow to enable image classification.") from exc
    ImageFile.LOAD_TRUNCATED_IMAGES = False
    if not data:
        raise InvalidImageError("The uploaded file is empty.")
    try:
        with Image.open(BytesIO(data)) as image:
            if image.format not in {"JPEG", "PNG", "WEBP"}:
                raise InvalidImageError("Only JPEG, PNG, and WebP images are supported.")
            width, height = image.size
            if (min(width, height) < MIN_IMAGE_SIDE or max(width, height) > MAX_IMAGE_SIDE
                    or width * height > MAX_IMAGE_PIXELS):
                raise InvalidImageError("Image dimensions are outside the supported range.")
            image.verify()
        with Image.open(BytesIO(data)) as image:
            image.load()
            return image.convert("RGB")
    except InvalidImageError:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError) as exc:
        raise InvalidImageError("The uploaded image is corrupted or invalid.") from exc

def preprocess_image(image: Image.Image):
    """Return a normalized CHW float tensor, importing torch only when needed."""
    import numpy as np
    import torch
    from PIL import Image
    image = image.convert("RGB").resize((IMAGE_SIZE, IMAGE_SIZE), Image.Resampling.BILINEAR)
    array = np.asarray(image, dtype=np.float32) / 255.0
    array = (array - np.array([0.485, 0.456, 0.406], dtype=np.float32)) / np.array(
        [0.229, 0.224, 0.225], dtype=np.float32
    )
    return torch.from_numpy(array.transpose(2, 0, 1).copy()).float()
