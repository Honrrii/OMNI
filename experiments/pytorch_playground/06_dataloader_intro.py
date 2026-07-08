import torch
from torch.utils.data import TensorDataset, DataLoader


# -----------------------------
# Dataset/DataLoader intro
#
# So far, we fed the entire training set into the model at once.
# Real ML usually feeds data in small batches.
# -----------------------------


# Training data: y = 2x + 1
x_train = torch.tensor([
    [1.0],
    [2.0],
    [3.0],
    [4.0],
    [5.0],
    [6.0],
    [7.0],
    [8.0],
])

y_train = 2 * x_train + 1


# TensorDataset pairs x values with y labels.
dataset = TensorDataset(x_train, y_train)


# DataLoader controls batching and shuffling.
dataloader = DataLoader(
    dataset,
    batch_size=2,
    shuffle=True
)


model = torch.nn.Linear(1, 1)

loss_fn = torch.nn.MSELoss()
optimizer = torch.optim.SGD(model.parameters(), lr=0.01)


for epoch in range(500):
    total_loss = 0.0

    # Each loop gives us one mini-batch.
    for batch_x, batch_y in dataloader:
        predictions = model(batch_x)
        loss = loss_fn(predictions, batch_y)

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        total_loss += loss.item()

    if epoch % 50 == 0:
        print(f"Epoch {epoch}, Total Loss: {total_loss:.6f}")


# Test after training
model.eval()

with torch.no_grad():
    test_x = torch.tensor([[10.0]])
    predicted_y = model(test_x)

print("\nTest input:", test_x.item())
print("Predicted output:", predicted_y.item())

print("\nLearned weight:", model.weight.item())
print("Learned bias:", model.bias.item())