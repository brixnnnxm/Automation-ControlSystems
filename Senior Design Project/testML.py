import matplotlib.pyplot as plt
import numpy as np
import os
from PIL import Image
import tensorflow as tf
from keras import layers, models
import torch
from torchvision import datasets, transforms, models
from torch.utils.data import DataLoader, Dataset
import torch.nn as nn
import torch.optim as optim

# Paths
data_dir = "/rheed_images/films/"  # Path to your test images
output_model_path = "rheed_model.pth"  # Path to the trained model (base or augmented)

# Test transforms (should match your training transforms)
test_transform = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
])

# Load the test dataset
test_dataset = datasets.ImageFolder(data_dir, transform=test_transform)
test_loader = DataLoader(test_dataset, batch_size=4, shuffle=False)

# Load the model (base or augmented)
model = models.resnet50(pretrained=False)  # Initialize the model without pre-trained weights
model.fc = nn.Linear(model.fc.in_features, 2)  # Ensure the model's final layer matches the number of classes

# Load the trained model weights
model.load_state_dict(torch.load(output_model_path))
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
model.to(device)

# Set the model to evaluation mode
model.eval()

# Evaluate the model
correct = 0
total = 0

with torch.no_grad():
    for inputs, labels in test_loader:
        inputs, labels = inputs.to('cpu'), labels.to('cpu')
        outputs = model(inputs)
        _, predicted = torch.max(outputs, 1)
        total += labels.size(0)
        correct += (predicted == labels).sum().item()

# Calculate accuracy
accuracy = 100 * correct / total

# print(f'Accuracy of the model on the test images: {accuracy:.2f}%')
print('Accuracy of the model on the test images: {:.2f}%'.format(accuracy))
