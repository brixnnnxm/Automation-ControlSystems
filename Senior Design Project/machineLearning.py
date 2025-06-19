# Imports
import asyncio
import cv2
import numpy as np
import os
from PIL import Image
import serial
import serial.tools.list_ports
import tensorflow as tf
from keras import layers, models
import time
import torch
from torchvision import datasets, transforms, models
from torch.utils.data import DataLoader, Dataset
import torch.nn as nn
import torch.optim as optim

# Paths
recentImages = '/rheed_images'
model_path = 'rheed_model.pth'
flatline = True
doPrediction = None
beamTimer = 0
lastImage = None

# Prepare for classification
model = models.resnet50(pretrained = False)
model.fc = nn.Linear(model.fc.in_features, 2)
model.load_state_dict(torch.load(model_path))
model.eval()
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
model.to(device)

# Transformation definitions
transform = transforms.Compose([ 
    transforms.Resize(256),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
])

# Function to find the serial port
def find_serial_port():
    ports = serial.tools.list_ports.comports()
    for port in ports:
        if 'USB' in port.description:
            return port.device
    return None

# Connect to microcontroller
def connectionTest():
    port = find_serial_port()
    global flatline
    
    if port:
        try:
            # Use 115200 baud rate to match the microcontroller's setting
            ser = serial.Serial(port, 115200, timeout=1)
            print(f"Connected to {port}\n")
            ser.write(b'MARCO!')

            # Listening for connection confirmation
            while True:
                if ser.in_waiting > 0:
                    piPico = ser.read().strip()
                    if piPico == b'POLO!':
                        flatline = False
                        print("Successfully connected to Raspberry Pi Pico!\n")
                        break

            return ser
        
        except serial.SerialException as e:
            print("Failed to connect:\n", e)
            return False
    else:
        print("No port found.\n")
        return False

# Ensure the connection is always there
async def heartbeat(ser, event):
    global flatline
    while not flatline:
        await event.wait()
        try:
            # Send heartbeat signal every 5 seconds
            await ser.write(b'PULSE')       
            await asyncio.sleep(5)
            flatline = False
            
        except serial.SerialException:
            print("Lost connection. Microcontroller will end process soon.\n")
            flatline = True
            break

# Handle incoming data without blocking
async def incomingSignals(ser, event):
    global flatline
    global doPrediction
    global beamTimer
    minutes = 0
    seconds = 0

    while not flatline:
        heartbeat.set()
        tag = b'PWD:' # To properly detect password
        if ser.any():
            received = ser.readline().strip().decode()
            
            if received.startswith('STOP'):
                print("Ending current process.\n")

            elif received.isdigit():
                beamTimer = int(received)
                minutes = beamTimer // 60
                seconds = beamTimer % 60

            elif received.startswith('BEAM ON'):
                print("Beam was just unblanked.\n")
                print(f"Beam Timer: {minutes} minutes and {seconds} seconds.\n") # In the event of consecutive runs

            elif received.startswith('BEAM OFF'):
                print("Beam was just blanked.\n")
                print(f"Beam Timer: {minutes} minutes and {seconds} seconds.\n")
            
            elif received.startswith('VERIFY'):
                print("Hold down the GREEN or RED button until the white LED turns off.\n")
                print("GREEEN continues with classification and RED retakes the image.\n")

            elif received.startswith('PROCEED'):
                print("Ready to classify.\n")
                doPrediction = True
            
            elif received.startswith('REDO'):
                print("Retaking image.\n")
                print(f"Beam Timer: {minutes} minutes and {seconds} seconds.\n")
                doPrediction = False

            elif received.startswith('PASSWORD'):
                attemptPassword = input("Please enter the correct password to unlock the microcontroller.\n")
                tryPassword = tag + str(attemptPassword).encode()
                event.clear()
                await ser.write(tryPassword)
                await asyncio.sleep(1)
                event.set()

            elif received.startswith('INCORRECT'):
                attemptPassword = input("The password you entered was incorrect. Please try again.\n")
                tryPassword = tag + attemptPassword
                event.clear()
                await ser.write(tryPassword)
                await asyncio.sleep(1)
                event.set()

            elif received.startswith('CRITICAL'):
                print("WARNING: Pi Pico suspects that the beam has been on too long. Locking finite state machine.\n")
                print(f"Beam Timer: {minutes} minutes and {seconds} seconds\n")

            elif received.startswith('HANG'):
                print("WARNING: The finite state machine entered an unreachable state. Ending current process.\n")

# Get the most recent image from folder
def getRecent(folderPath):
    files = os.listdir(folderPath)
    if not files:
        return None
    
    # Get the most recent by modification time
    recentFile = max([os.path.join(folderPath, f) for f in files], key = os.path.getmtime)
    return recentFile

# Display image
def displayImage(imagePath, ser, event):
    picture = cv2.imread(imagePath)
    cv2.imshow("Image Viewer", picture)
    cv2.waitKey(1)
    event.clear()
    time.sleep(1)
    ser.write(b'READY')
    event.set()

# Classification function
def classify():
    global recentImages 

    imagePath = getRecent(recentImages)
    image = Image.open(imagePath)
    image = transform(image)
    image = image.unsqueeze(0)
    image = image.to(device)

    with torch.no_grad():
        outputs = model(image)
        _, preds = torch.max(outputs, 1)
    
    classifications = ['monocrystalline','polycrystalline']
    print(f"Classified as: {classifications[preds]}")

# Main function
def main(ser):
    global doPrediction
    global flatline
    global lastImage

    event = asyncio.Event()
    event.set()

    asyncio.run(incomingSignals(ser, event))
    asyncio.run(heartbeat(ser, event))

    while (flatline != True):
        newImage = getRecent(recentImages)
        if (newImage and newImage != lastImage):
            lastImage = newImage
            displayImage(lastImage, ser, event)
            while (flatline != True):
                if (doPrediction != None):
                    if (doPrediction == True):
                        classify()
                        doPrediction == None
                        break

                    elif (doPrediction == False):
                        doPrediction == None
                        break

                else:
                    continue

        else:
            continue

if __name__ == "__main__":
    while True:
        connect = connectionTest()
        if connect:
            ser = serial.Serial(connect, 115200)
            main(ser)