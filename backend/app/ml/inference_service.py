from io import BytesIO
from typing import Any, Dict

from PIL import Image
import torch
from torchvision import transforms

from backend.app.ml.fashion_mnist_model import (
    CLASS_NAMES,
    load_fashion_mnist_model,
)


_transform = transforms.Compose(
    [
        transforms.Grayscale(num_output_channels=1),
        transforms.Resize((28, 28)),
        transforms.ToTensor(),
    ]
)


def get_torch_status() -> Dict[str, Any]:
    return {
        "torch_available": True,
        "torch_version": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "device": "cuda" if torch.cuda.is_available() else "cpu",
    }


def classify_uploaded_image(image_bytes: bytes) -> Dict[str, Any]:
    device = "cuda" if torch.cuda.is_available() else "cpu"

    image = Image.open(BytesIO(image_bytes)).convert("RGB")
    input_tensor = _transform(image).unsqueeze(0).to(device)

    model = load_fashion_mnist_model(device=device)

    with torch.no_grad():
        logits = model(input_tensor)
        probabilities = torch.softmax(logits, dim=1)
        confidence, predicted_index = torch.max(probabilities, dim=1)

    predicted_index_int = predicted_index.item()
    confidence_float = confidence.item()

    return {
        "model_name": "fashion_mnist_mlp",
        "predicted_class": CLASS_NAMES[predicted_index_int],
        "predicted_index": predicted_index_int,
        "confidence": round(confidence_float, 4),
        "device": device,
        "note": (
            "This is a demo Fashion-MNIST classifier. "
            "It is not yet a robotics/CAD design understanding model."
        ),
    }