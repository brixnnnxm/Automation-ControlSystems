# Imports
import time
import uasyncio
import machine
from top_secret import password

# Global Variables
globalVariables = {
    # LEDs
    'rLED' : Pin(2, Pin.OUT), # Lock controls
    'yLED' : Pin(3, Pin.OUT), # Warning
    'gLED' : Pin(6, Pin.OUT), # Idle/new run
    'bLED' : Pin(5, Pin.OUT), # Process in progress
    'wLED' : Pin(4, Pin.OUT), # User input needed; won't continue
    'toggle': False, # For FSM to avoid unnecessary toggling
    'toggle4Timer' : False, # For checkTimer() to avoid unnecessary toggling

    # State Machine
    'S0' : 0, # Idle
    'S1' : 1, # Unblank Beam
    'S2' : 2, # Open Shutter
    'S3' : 3, # Take Photo
    'S4' : 4, # Verify Image
    'S5' : 5, # Close Shutter
    'S6' : 6, # Blank Beam
    'S7' : 7, # Lock Controls

    # Buttons
    'start' : Pin(0, Pin.OUT), # Start process/confirm image
    'stop' : Pin(8, Pin.OUT), # Stop process/ retake image

    # Servo Motor
    'servoPin' : Pin(7, Pin.OUT),
    'servoPWM' : None,

    # Beam
    'beamOn' : 0, # Blanks when low, unblanks when high
    'beamTimer' : 0, ## Indicates how long the beam gas been on

    # User Input
    'password' : None, # To unlock controls

    # Connections
    'uart' : machine.UART(0, baudrate=115200), 
    'flatline' : True, # Detrmines if FSM can run or not
    'pulse' : None, # Checks if communication still exists

    # Flags and Triggers
    'stopFlag' : 0, # End current process
    'snapPicture' : 0, # For triggering the camera
    'ready' : False, # For image display
    'validFlag' : None, # For image verification
    'unlockControls' : None, # For controls lock (proceed or remain locked)
    'rFlag' : 0 # Trigger control locking
}

currentState = globalVariables['S0'] # Initial state

def connectionTest():
    global globalVariables

    while True:
        if globalVariables['uart'].any():  # Check if there's data available
            data = globalVariables['uart'].read().strip()
            if data == b'MARCO!':
                globalVariables['uart'].write(b'POLO!')
                break
        time.sleep(0.1)

    globalVariables['flatline'] = False
    globalVariables['pulse'] = True

# Start other async functions and check incoming data
async def main():
    global globalVariables
    uasyncio.run(heartbeat())
    uasyncio.run(timer())
    uasyncio.run(checkTimer())
    uasyncio.run(pollStop())
    while (globalVariables['flatline'] == False):
        if globalVariables['uart'].any():
            received = globalVariables['uart'].readline().strip().decode()
            if received.startswith('PULSE'):
                globalVariables['pulse'] = True

            elif received.startswith('PWD:'):
                globalVariables['pulse'] = True
                globalVariables['password'] = received

            elif received.startswith('READY'):
                globalVariables['ready'] = True

            else:
                globalVariables['pulse'] = True

        uasyncio.run(heartbeat())

# Suspect connection lost 
async def heartbeat():
    globalVariables['pulse'] == False
    count = 0

    while (count != 10): # Wait for 2 missed pulses
        await uasyncio.sleep(1)
        if globalVariables['pulse'] == True:
            globalVariables['flatline'] = False # Connection is still there
            return
        
        else:
            count += 1 # Give it a chance to update
    
    # Assume disconnect
    globalVariables['flatline'] = True

# Toggles green, blue, and white LEDs
async def toggleLED(led):
    global globalVariables
    while (globalVariables['toggle'] == True):
        if led.on():
            led.off()
            await uasyncio.sleep(0.5)
        
        else:
            led.on()
            await uasyncio.sleep(0.5)

# Toggles yellow and red LEDs
async def toggleLED4Timer(led):
    global globalVariables
    while (globalVariables['toggle4Timer'] == True):
        if led.on():
            led.off()
            await uasyncio.sleep(0.5)
        
        else:
            led.on()
            await uasyncio.sleep(0.5)

# Beam timer
async def timer():
    global globalVariables
    while True:
        while (globalVariables['beamOn'] == 1):
            globalVariables['beamTimer'] += 1
            
        while (globalVariables['beamOn'] == 0):
            if globalVariables['beamTimer'] == 0:
                globalVariables['toggle4Timer'] = False
                globalVariables['yLED'].off()
                globalVariables['rLED'].off()
                globalVariables['rFlag'] = 0

            else:
                globalVariables['beamTimer'] -= 1
                
# Checks if stop went low except in S4
async def pollStop():
    global globalVariables
    global currentState

    while not globalVariables['flatline']:
        if (globalVariables['stop'] == 0):
            if (currentState != globalVariables['S4']):
                globalVariables['stopFlag'] = 1

            else:
                continue

        else:
            continue

# Update variables based on value of beam timer
async def checkTimer():
    while True:
        if globalVariables['beamTimer'] >= 300 and globalVariables['beamTimer'] < 390: # Beam has bean on for at least 5 minutes
            globalVariables['toggle4Timer'] = True
            uasyncio.run(toggleLED4Timer(globalVariables['yLED']))
            globalVariables['rLED'].off()
            globalVariables['rFlag'] = 0
                
        elif globalVariables['beamTimer'] >= 390 and globalVariables['beamTimer'] < 480: # Beam has bean on for at least 6 minutes + 30 seconds
            globalVariables['toggle4Timer'] = False
            await uasyncio.sleep(0.1)
            globalVariables['yLED'].on()
            globalVariables['rLED'].off()
            globalVariables['rFlag'] = 0

        elif globalVariables['beamTimer'] >= 480 and globalVariables['beamTimer'] < 570: # Beam has bean on for at least 8 minutes
            globalVariables['yLED'].off()
            globalVariables['toggle4Timer'] = True
            uasyncio.run(toggleLED4Timer(globalVariables['rLED']))
            globalVariables['rFlag'] = 0

        elif globalVariables['beamTimer'] >= 570: # Beam has bean on for at least 9 minutes + 30 seconds
            globalVariables['toggle4Timer'] = False
            await uasyncio.sleep(0.1)
            globalVariables['yLED'].off()
            globalVariables['rLED'].on()
            globalVariables['rFlag'] = 1

        else: # Beam has been on for less than 5 minutes
            globalVariables['toggle4Timer'] = False
            globalVariables['yLED'].off()
            globalVariables['rLED'].off()
            globalVariables['rFlag'] = 0

def runProcess():
    global globalVariables
    global currentState
    uasyncio.run(main())
    
    while not globalVariables['flatline']: # Stop if connection is lost
        globalVariables['uart'].write(str(globalVariables['beamTimer'].enconde()))
        time.sleep(1)

        if (currentState == globalVariables['S0']): #Idle
            globalVariables['bLED'].off()
            globalVariables['wLED'].off()
            globalVariables['gLED'].on()
            globalVariables['toggle'] = False
            
            # Reset variables
            globalVariables['beamOn'] = 0
            globalVariables['password'] = None
            globalVariables['validFlag'] = False
            globalVariables['unlockControls'] = None
            globalVariables['stopFlag'] = 0
            globalVariables['ready'] = False

            if (globalVariables['rFlag'] != 1 and globalVariables['start'] == 0):
                nextState = globalVariables['S1']
                globalVariables['gLED'].off()

            elif (globalVariables['rFlag'] == 1):
                globalVariables['uart'].write(b'CRITICAL')
                nextState = globalVariables['S7']
            
            else:
                nextState = globalVariables['S0']

            globalVariables['stopFlag'] = 0 # Only valid once process has started

        elif (currentState == globalVariables['S1']): # Unblank Beam
            globalVariables['gLED'].off()
            globalVariables['bLED'].on()
            
            if (globalVariables['rFlag'] != 1 and globalVariables['stopFlag'] != 1):
                globalVariables['beamOn'] = 1
                globalVariables['uart'].write(b'BEAM_ON')
                nextState = globalVariables['S2']
    
            elif (globalVariables['rFlag'] == 1):
                globalVariables['uart'].write(b'CRITICAL')
                nextState = globalVariables['S7']

            elif (globalVariables['stopFlag'] == 1):
                globalVariables['toggle'] = True
                uasyncio.run(toggleLED(globalVariables['bLED']))
                nextState = globalVariables['S0']

            else:
                nextState = globalVariables['S6']
        
        elif (currentState == globalVariables['S2']): # Open Shutter
            if (globalVariables['rFlag'] != 1 and globalVariables['stopFlag'] != 1):
                globalVariables['servoPWM'] = PWM(globalVariables['servoPin'])
                globalVariables['servoPWM'].freq(50)
                dutyCycle = int((60 / 180) * (115 - 40) + 40)
                globalVariables['servoPWM'].duty_u16(dutyCycle << 4)
                time.sleep(10) # Let beam hit the sample for a bit
                nextState = globalVariables['S3']

            elif (globalVariables['rFlag'] == 1):
                globalVariables['uart'].write(b'CRITICAL')
                nextState = globalVariables['S6']
            
            elif (globalVariables['stopFlag'] == 1):
                globalVariables['toggle'] = True
                uasyncio.run(toggleLED(globalVariables['bLED']))
                nextState = globalVariables['S6']

            else:
                nextState = globalVariables['S5']
        
        elif (currentState == globalVariables['S3']): # Take Photo
            # Reset in case previous state was S4
            globalVariables['validFlag'] = False
            globalVariables['ready'] = False
            
            if (globalVariables['rFlag'] != 1 and globalVariables['stopFlag'] != 1):
                globalVariables['snapPicture'] = 1
                time.sleep(3)
                globalVariables['snapPicture'] = 0
                nextState = globalVariables['S4']

            elif (globalVariables['rFlag'] == 1):
                globalVariables['uart'].write(b'CRITICAL')
                nextState = globalVariables['S5']
            
            elif (globalVariables['stopFlag'] == 1):
                globalVariables['toggle'] = True
                uasyncio.run(toggleLED(globalVariables['bLED']))
                nextState = globalVariables['S5']

            else:
                nextState = globalVariables['S5']
        
        elif (currentState == globalVariables['S4']): # Verify Image
            # Dummy loop until the new image is displayed
            while (globalVariables['ready'] != True):
                continue
            
            globalVariables['uart'].write(b'VERIFY')
            time.sleep(1)
            while (globalVariables['validFlag'] != True and globalVariables['flatline'] == False):
                globalVariables['wLED'].on()
                if (globalVariables['rFlag'] != 1):
                    if (globalVariables['start']) == 0:
                        globalVariables['validFlag'] = True
                        globalVariables['uart'].write(b'PROCEED')
                        nextState = globalVariables['S5']
                        globalVariables['wLED'].off()
                        break

                    elif (globalVariables['stop']) == 0:
                        globalVariables['validFlag'] = True
                        globalVariables['uart'].write(b'REDO')
                        nextState = globalVariables['S3']
                        globalVariables['wLED'].off()
                        break

                    else:
                        globalVariables['validFlag'] = False

                else:
                    globalVariables['uart'].write(b'CRITICAL') 
                    nextState = globalVariables['S5']       
                    break
        
        elif (currentState == globalVariables['S5']): # Close Shutter
            globalVariables['wLED'].off()
            globalVariables['servoPWM'] = PWM(globalVariables['servoPin'])
            globalVariables['servoPWM'].freq(50)
            dutyCycle = int((0 / 180) * (115 - 40) + 40)
            globalVariables['servoPWM'].duty_u16(dutyCycle << 4)
            time.sleep(1)

            nextState = globalVariables['S6']
        
        elif (currentState == globalVariables['S6']): # Blank Beam
            globalVariables['beamOn'] = 0
            globalVariables['uart'].write(b'BEAM_OFF')
            if (globalVariables['rFlag'] != 1):
                nextState = globalVariables['S0']
            
            else:
                nextState = globalVariables['S7']
            
            globalVariables['bLED'].off()

        elif (currentState == globalVariables['S7']): # Lock Controls
            globalVariables['unlockControls'] = False
            globalVariables['uart'].write(b'PASSWORD')
            globalVariables['toggle'] = True
            uasyncio.run(toggleLED(globalVariables['wLED']))
            
            while (globalVariables['unlockControls'] != True and globalVariables['flatline'] == False):
                time.sleep(5) # Give chance for user to enter a new password
                if (globalVariables['password'] != None):
                    if (globalVariables['password'] == password):
                        globalVariables['unlockControls'] = True
                        break

                    else:
                        globalVariables['uart'].write(b'INCORRECT')
                        time.sleep(1)
                        globalVariables['unlockControls'] = False
                
                else:
                    globalVariables['unlockControls'] = False

                uasyncio.run(heartbeat())  
            nextState = globalVariables['S0']
            globalVariables['toggle'] = False
            globalVariables['wLED'].off()
        
        else: # Handle Hang/Unreachable State
            globalVariables['uart'].write(b'HANG')
            nextState = globalVariables['S5'] # make sure the shutter closes and beam is turned off

        currentState = nextState
    
    # Assume disconnect
    if (currentState == globalVariables['S0'] or currentState == globalVariables['S1'] or currentState == globalVariables['S7']):
        pass

    elif (currentState == globalVariables['S2'] or currentState == globalVariables['S6']):
        globalVariables['beamOn'] = 0
        globalVariables['uart'].write(b'BEAM_OFF')

    elif (currentState == globalVariables['S3'] or currentState == globalVariables['S4'] or currentState == globalVariables['S5']):
        globalVariables['servoPWM'] = PWM(globalVariables['servoPin'])
        globalVariables['servoPWM'].freq(50)
        dutyCycle = int((0 / 180) * (115 - 40) + 40)
        globalVariables['servoPWM'].duty_u16(dutyCycle << 4)
        globalVariables['beamOn'] = 0
        globalVariables['uart'].write(b'BEAM_OFF')

    else:
        globalVariables['servoPWM'] = PWM(globalVariables['servoPin'])
        globalVariables['servoPWM'].freq(50)
        dutyCycle = int((0 / 180) * (115 - 40) + 40)
        globalVariables['servoPWM'].duty_u16(dutyCycle << 4)
        globalVariables['beamOn'] = 0
        globalVariables['uart'].write(b'BEAM_OFF')

    globalVariables['servoPWM'] = None
    globalVariables['password'] = None
    globalVariables['snapPicture'] = 0
    globalVariables['unlockControls'] = None
    globalVariables['validFlag'] = False
    globalVariables['rFlag'] = 0
    globalVariables['gLED'] = 0
    globalVariables['bLED'] = 0
    globalVariables['wLED'] = 0
    globalVariables['ready'] = 0
    globalVariables['toggle'] = False
    globalVariables['toggle4Timer'] = False
    globalVariables['beamOn'] = 0
    globalVariables['pulse'] = None
    globalVariables['stopFlag']

# Run code
while True:
    connectionTest()
    runProcess()
