"""MobileNetV3 model factory used by training and inference."""
def build_model(num_classes: int = 8, pretrained: bool = False):
    try:
        from torchvision.models import mobilenet_v3_large, MobileNet_V3_Large_Weights
    except Exception as exc:
        raise RuntimeError("Torch and a compatible Torchvision installation are required.") from exc
    weights = MobileNet_V3_Large_Weights.DEFAULT if pretrained else None
    model = mobilenet_v3_large(weights=weights)
    model.classifier[3] = __import__("torch").nn.Linear(model.classifier[3].in_features, num_classes)
    return model
