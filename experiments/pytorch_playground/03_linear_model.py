import torch

# -----------------------------
# Goal:
# Teach a model to learn this pattern:
#
# y = 2x + 1
#
# Example:
# x = 1 -> y = 3
# x = 2 -> y = 5
# x = 3 -> y = 7
# -----------------------------

# Training data
x_train = torch.tensor([[1.0], [2.0], [3.0], [4.0]])
y_train = torch.tensor([[3.0], [5.0], [7.0], [9.0]])

# A simple linear model:
# y = weight * x + bias
model = torch.nn.Linear(1, 1)

# Loss function:
# Measures how wrong the model is.
loss_fn = torch.nn.MSELoss()

# Optimizer:
# Updates the model's weight and bias.
optimizer = torch.optim.SGD(model.parameters(), lr=0.01)

# Training loop
for epoch in range(1000):
    # 1. Make predictions
    predictions = model(x_train)

    # 2. Calculate loss
    loss = loss_fn(predictions, y_train)

    # 3. Clear old gradients
    optimizer.zero_grad()

    # 4. Backpropagation
    loss.backward()

    # 5. Update weights
    optimizer.step()

    # Print progress occasionally
    if epoch % 100 == 0:
        print(f"Epoch {epoch}, Loss: {loss.item():.6f}")

# Test after training
test_x = torch.tensor([[10.0]])
predicted_y = model(test_x)

print("\nTest input:", test_x.item())
print("Predicted output:", predicted_y.item())

# Show learned weight and bias
weight = model.weight.item()
bias = model.bias.item()

print("\nLearned weight:", weight)
print("Learned bias:", bias)