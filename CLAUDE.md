# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RavenAutomation is an AI-powered animatronic parrot that combines:
- **Python server** (FastAPI) for AI interaction and audio processing
- **ESP32 microcontroller** (Arduino/C++) for hardware control
- **OpenAI real-time API** for conversational AI

## Development Setup

### Python Environment
```bash
# Activate virtual environment
source venv/bin/activate  # On macOS/Linux
# or
venv\Scripts\activate  # On Windows

# Install dependencies
pip install -r requirements.txt

# Create .env file with API keys
cp .env.example .env
# Edit .env to add your API keys and select backend
```

### Running the Server
```bash
# Start the main Python server
python parrot_server.py
```

The server runs multiple services:
- Port 8080: Main WebSocket server
- Port 8001: Audio output endpoint
- Port 8002: Microphone input endpoint

### ESP32 Development
- Use Arduino IDE with ESP32 board support
- Required libraries: WebSocketsClient, WiFiManager, ESP32Servo
- Main sketch: `/ParrotDriver/ParrotDriver.ino`
- Upload to ESP32 board via USB

## Architecture

### Server Architecture (Python)
- **parrot_server.py**: Main server orchestrating all components
  - WebSocket endpoints for ESP32 communication
  - Audio streaming management
  - Behavior pattern control
- **Voice Backend System**:
  - **voice_backend.py**: Abstract base class for voice providers
  - **openai_backend.py**: OpenAI Realtime API implementation
  - **vapi_backend.py**: VAPI.ai integration (supports multiple TTS providers)
  - **voice_factory.py**: Factory for creating backend instances
  - **config.py**: Configuration management for backends
- **openai.py**: Legacy OpenAI WebSocket proxy (being phased out)
- **mic_processor.py**: Audio input processing
  - Voice activity detection (VAD)
  - Audio format conversion

### ESP32 Architecture
- **ParrotDriver.ino**: Main controller
  - WebSocket client connecting to Python server
  - Servo control (4 servos: mouth, head tilt, wing, head rotation)
  - I2S audio input/output
- **Bottango library** in `/src/`: Animation framework
  - Smooth servo movements
  - Pre-programmed animation sequences

### Key Communication Flow
1. ESP32 connects to Python server via WebSocket
2. Microphone audio → ESP32 → Python server → OpenAI
3. OpenAI response → Python server → ESP32 → Speaker
4. Server sends servo commands based on speech/behavior

## Important Considerations

### Hardware Pins (ESP32)
- Servo pins: 13 (mouth), 27 (head tilt), 4 (wing), 16 (head rotation)
- I2S Speaker: BCLK=25, LRC=26, DIN=22
- I2S Microphone: SCK=14, WS=15, SD=32

### Network Configuration
- ESP32 uses WiFiManager for initial setup
- Access point mode if no saved network
- WebSocket reconnection handled automatically

### Audio Processing
- 16kHz sample rate for all audio
- PCM format for OpenAI compatibility
- Voice activity detection prevents constant streaming

### No Test Framework
Currently no automated tests. Manual testing required for:
- WebSocket connectivity
- Audio streaming
- Servo movements
- AI responses