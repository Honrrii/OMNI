from pathlib import Path

import torch
from torch import nn


CLASS_NAMES = [
    "T-shirt/top",
    "Trouser",
    "Pullover",
    "Dress",
    "Coat",
    "Sandal",
    "Shirt",
    "Sneaker",
    "Bag",
    "Ankle boot",
]


class FashionMNISTClassifier(nn.Module):
    def __init__(self):
        super().__init__()

        self.network = nn.Sequential(
            nn.Flatten(),
            nn.Linear(28 * 28, 128),
            nn.ReLU(),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 10),
        )

    def forward(self, x):
        return self.network(x)


def get_model_path() -> Path:
    return Path(__file__).resolve().parent / "models" / "fashion_mnist_mlp.pt"


def load_fashion_mnist_model(device: str = "cpu") -> FashionMNISTClassifier:
    model = FashionMNISTClassifier()

    model_path = get_model_path()

    if not model_path.exists():
        raise FileNotFoundError(
            f"Fashion-MNIST model not found at {model_path}. "
            "Run experiments/pytorch_playground/07_fashion_mnist.py first."
        )

    state_dict = torch.load(model_path, map_location=device)
    model.load_state_dict(state_dict)
    model.to(device)
    model.eval()

    return model