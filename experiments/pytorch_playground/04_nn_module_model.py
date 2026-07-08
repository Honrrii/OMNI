import torch


# A custom PyTorch model.
# Almost every serious PyTorch model is built by subclassing torch.nn.Module.
class TinyLinearModel(torch.nn.Module):
    def __init__(self):
        super().__init__()

        # This layer means:
        # input size = 1
        # output size = 1
        self.linear = torch.nn.Linear(1, 1)

    def forward(self, x):
        # This defines how data moves through the model.
        return self.linear(x)


# Training data: y = 2x + 1
x_train = torch.tensor([[1.0], [2.0], [3.0], [4.0]])
y_train = torch.tensor([[3.0], [5.0], [7.0], [9.0]])

model = TinyLinearModel()

loss_fn = torch.nn.MSELoss()
optimizer = torch.optim.SGD(model.parameters(), lr=0.01)

for epoch in range(1000):
    predictions = model(x_train)
    loss = loss_fn(predictions, y_train)

    optimizer.zero_grad()
    loss.backward()
    optimizer.step()

    if epoch % 100 == 0:
        print(f"Epoch {epoch}, Loss: {loss.item():.6f}")

# Test the model
model.eval()

with torch.no_grad():
    test_x = torch.tensor([[10.0]])
    predicted_y = model(test_x)

print("\nTest input:", test_x.item())
print("Predicted output:", predicted_y.item())

print("\nLearned weight:", model.linear.weight.item())
print("Learned bias:", model.linear.bias.item())