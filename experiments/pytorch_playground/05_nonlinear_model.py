import torch


# -----------------------------
# Goal:
# Train a neural network to learn a curved pattern:
#
# y = x^2
#
# This is nonlinear, so one simple Linear layer is not enough.
# We need hidden layers + activation functions.
# -----------------------------


class TinyNeuralNetwork(torch.nn.Module):
    def __init__(self):
        super().__init__()

        self.network = torch.nn.Sequential(
            torch.nn.Linear(1, 16),
            torch.nn.ReLU(),
            torch.nn.Linear(16, 16),
            torch.nn.ReLU(),
            torch.nn.Linear(16, 1),
        )

    def forward(self, x):
        return self.network(x)


# Make training data
# x values from -5 to 5
x_train = torch.linspace(-10, 10, 200).reshape(-1, 1)

# Target pattern: y = x^2
y_train = x_train ** 2

model = TinyNeuralNetwork()

loss_fn = torch.nn.MSELoss()
optimizer = torch.optim.Adam(model.parameters(), lr=0.01)

for epoch in range(3000):
    predictions = model(x_train)
    loss = loss_fn(predictions, y_train)

    optimizer.zero_grad()
    loss.backward()
    optimizer.step()

    if epoch % 300 == 0:
        print(f"Epoch {epoch}, Loss: {loss.item():.6f}")


# Test the model
model.eval()

test_values = torch.tensor([
    [-10.0],
    [-6.0],
    [-4.0],
    [0.0],
    [4.0],
    [6.0],
    [10.0],
])

with torch.no_grad():
    predictions = model(test_values)

print("\nTest results:")
for x, pred in zip(test_values, predictions):
    true_y = x.item() ** 2
    print(f"x = {x.item():>5.1f} | predicted = {pred.item():>8.3f} | true = {true_y:>8.3f}")