import torch

# This creates a tensor with the value 2.0.
# requires_grad=True tells PyTorch:
# "Track the math done with this value because I may need derivatives later."
x = torch.tensor(2.0, requires_grad=True)

# Define a simple math function:
# y = x^2 + 3x + 1
y = x**2 + 3*x + 1

print("x:", x.item())
print("y:", y.item())

# backward() asks PyTorch to compute the derivative dy/dx.
y.backward()

print("dy/dx at x=2:", x.grad.item())