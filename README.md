# AI Animatronic Parrot

An interactive animatronic parrot that uses AI to engage in natural conversations and display lifelike movements. The system combines ESP32-based hardware control with OpenAI's API to create a responsive and engaging robotic companion.

## Overview

The project consists of two main components:
- An ESP32-based controller that manages servo movements and audio
- A Python server that handles AI interaction and audio processing

## Features

### Voice Interaction
- Real-time conversation using OpenAI's API
- Natural speech synthesis
- Microphone input processing
- WebSocket-based audio streaming

### Animatronic Control
- Synchronized mouth movements with speech
- Natural head rotation and tilting
- Wing movements
- Idle behaviors during silence

### Autonomous Behaviors
- Random movements during idle periods
- Context-aware responses
- Variety of personalities and interactions
- Customizable behavior patterns

## Hardware Requirements

### Core Components
- ESP32 development board
- 4x servo motors
- I2S DAC (for audio output)
- I2S MEMS microphone
- Speaker (3W recommended)
- 5V power supply

### Servo Configuration
- Mouth servo: SG90 or equivalent
- Head rotation servo: MG996R recommended
- Head tilt servo: MG996R recommended
- Wing servo: SG90 or equivalent

## Software Setup

### 1. Python Environment
```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Environment Configuration
Create a `.env` file in the project root:
```
OPENAI_API_KEY=your_api_key_here
```

### 3. ESP32 Setup
1. Open `ParrotDriver/ParrotDriver.ino` in Arduino IDE
2. Install required libraries:
   - WebSocketsClient
   - WiFiManager
   - ESP32Servo
3. Configure your pins in `ParrotDriver.ino`
4. Flash to ESP32

### 4. Starting the System
```bash
# Start the Python server
python parrot_server.py

# The ESP32 will automatically connect to the server
```

## Configuration

### Servo Pins (ParrotDriver.ino)
```cpp
const int MOUTH_PIN = 27;
const int HEAD_TILT_PIN = 14;
const int WING_PIN = 13;
const int HEAD_ROTATION_PIN = 12;
```

### Audio Pins (ParrotDriver.ino)
```cpp
const int I2S_BCLK = 18;
const int I2S_LRC = 19;
const int I2S_DOUT = 23;
```

### Network Configuration
The ESP32 uses WiFiManager for initial setup. On first boot:
1. Connect to "ParrotConfig-XXXX" WiFi network
2. Configure your WiFi credentials
3. The device will automatically connect on subsequent boots

## Development

### Project Structure
```
├── ParrotDriver/           # ESP32 Arduino code
│   ├── ParrotDriver.ino    # Main ESP32 program
│   └── src/               # Supporting libraries
├── parrot_server.py       # Python server
├── requirements.txt       # Python dependencies
└── .env                  # Environment configuration
```

### Adding New Behaviors
Behaviors can be added in `parrot_server.py` by modifying the `BehaviorManager` class.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
