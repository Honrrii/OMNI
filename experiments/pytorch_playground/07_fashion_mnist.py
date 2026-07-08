import torch
from torch import nn
from torch.utils.data import DataLoader
from torchvision import datasets, transforms


# ----------------------------------
# Fashion-MNIST Image Classifier
#
# Goal:
# Train a neural network to classify clothing images.
#
# Each image is 28x28 pixels, grayscale.
# The model predicts one of 10 clothing categories.
# ----------------------------------


# Convert image data into PyTorch tensors
transform = transforms.ToTensor()


# Download training data
training_data = datasets.FashionMNIST(
    root="data",
    train=True,
    download=True,
    transform=transform
)

# Download testing data
test_data = datasets.FashionMNIST(
    root="data",
    train=False,
    download=True,
    transform=transform
)


# DataLoaders feed the data in batches
batch_size = 64

train_dataloader = DataLoader(
    training_data,
    batch_size=batch_size,
    shuffle=True
)

test_dataloader = DataLoader(
    test_data,
    batch_size=batch_size,
    shuffle=False
)


# Class names for Fashion-MNIST
class_names = [
    "T-shirt/top",
    "Trouser",
    "Pullover",
    "Dress",
    "Coat",
    "Sandal",
    "Shirt",
    "Sneaker",
    "Bag",
    "Ankle boot"
]


# Use GPU if available, otherwise CPU
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Using device: {device}")


class ImageClassifier(nn.Module):
    def __init__(self):
        super().__init__()

        self.network = nn.Sequential(
            nn.Flatten(),          # 28x28 image becomes 784 numbers
            nn.Linear(28 * 28, 128),
            nn.ReLU(),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 10)      # 10 output classes
        )

    def forward(self, x):
        return self.network(x)


model = ImageClassifier().to(device)

loss_fn = nn.CrossEntropyLoss()
optimizer = torch.optim.Adam(model.parameters(), lr=0.001)


def train_one_epoch():
    model.train()

    total_loss = 0.0

    for batch, (images, labels) in enumerate(train_dataloader):
        images = images.to(device)
        labels = labels.to(device)

        predictions = model(images)
        loss = loss_fn(predictions, labels)

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        total_loss += loss.item()

        if batch % 200 == 0:
            print(f"Batch {batch}, Loss: {loss.item():.4f}")

    average_loss = total_loss / len(train_dataloader)
    print(f"Average training loss: {average_loss:.4f}")


def test_model():
    model.eval()

    correct = 0
    total = 0

    with torch.no_grad():
        for images, labels in test_dataloader:
            images = images.to(device)
            labels = labels.to(device)

            predictions = model(images)

            predicted_classes = predictions.argmax(dim=1)

            correct += (predicted_classes == labels).sum().item()
            total += labels.size(0)

    accuracy = correct / total
    print(f"Test accuracy: {accuracy * 100:.2f}%")


# Train for a few epochs
epochs = 5

for epoch in range(epochs):
    print(f"\nEpoch {epoch + 1}/{epochs}")
    train_one_epoch()
    test_model()


# Try one prediction
model.eval()

with torch.no_grad():
    image, label = test_data[0]

    input_image = image.unsqueeze(0).to(device)
    prediction = model(input_image)

    predicted_class = prediction.argmax(dim=1).item()

print("\nSingle image test:")
print("Predicted:", class_names[predicted_class])
print("Actual:", class_names[label])

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = PROJECT_ROOT / "backend" / "app" / "ml" / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

MODEL_PATH = MODEL_DIR / "fashion_mnist_mlp.pt"

torch.save(model.state_dict(), MODEL_PATH)

print(f"\nSaved model to: {MODEL_PATH}")