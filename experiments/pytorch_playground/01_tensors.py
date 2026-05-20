import torch

# A tensor is PyTorch's core data structure.
# Think of it like a matrix/vector/array for machine learning.
x = torch.tensor([
    [1.0, 2.0],
    [3.0, 4.0]
])

print("x:")
print(x)

print("\nShape of x:")
print(x.shape)

# Random tensor
random_tensor = torch.rand(3, 4)

print("\nRandom tensor:")
print(random_tensor)

# Basic tensor math
a = torch.tensor([1.0, 2.0, 3.0])
b = torch.tensor([10.0, 20.0, 30.0])

print("\na + b:")
print(a + b)

print("\na * b:")
print(a * b)

# Matrix multiplication
matrix_a = torch.tensor([
    [1.0, 2.0],
    [3.0, 4.0]
])

matrix_b = torch.tensor([
    [5.0],
    [6.0]
])

result = matrix_a @ matrix_b

print("\nMatrix multiplication result:")
print(result)