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
data_dir = "/rheed_images/films/"
output_model_path = "rheed_model.pth"

# Resize dataset
train_transform = transforms.Compose([
    transforms.Resize(256),
    transforms.RandomHorizontalFlip(),
    transforms.RandomVerticalFlip(),
    transforms.RandomRotation(30),
    transforms.RandomResizedCrop(224),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
])

# Dataset and DataLoader
train_dataset = datasets.ImageFolder(data_dir, transform = train_transform)
augmented_dataset = torch.utils.data.ConcatDataset([train_dataset, train_dataset, train_dataset, train_dataset])
train_loader = torch.utils.data.DataLoader(augmented_dataset, batch_size=4, shuffle=True)

# Confirm dataset
print("Classes in the dataset: {}".format(train_dataset.classes))
print("Number of samples: {}".format(len(train_dataset)))

# Model setup
model = models.resnet50(pretrained = True)
model.fc = nn.Linear(model.fc.in_features, 2)

# Use CPU for training
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
model.to(device)

# Loss and Optimizer
criterion = nn.CrossEntropyLoss()
optimizer = optim.Adam(model.parameters(), lr = 0.001)

# Train the model
epochs = 10
for epoch in range(epochs):
    model.train()
    running_loss = 0.0
    for inputs, labels in train_loader:
        # Move data to CPU (no CUDA here)
        inputs, labels = inputs.to(device), labels.to(device)
        
        optimizer.zero_grad()
        outputs = model(inputs)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()
        running_loss += loss.item()
    
    print("Epoch {}/{}. Loss: {:.4f}".format(epoch+1, epochs, running_loss/len(train_loader)))

# Save the model
torch.save(model.state_dict(), output_model_path)
print("Training complete. Model saved.")