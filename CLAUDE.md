# RavenAutomation ESP32 Deployment Guide

## ESP32-S3 Pin Configuration

### Current Pin Mappings
- **Servo Motors:**
  - Mouth: GPIO 6
  - Head Tilt: GPIO 5
  - Head Rotation: GPIO 8 (moved from GPIO 10, then 9 due to pin conflicts)
  - Wing: GPIO 3

- **Speaker I2S (MAX98357A Amplifier):**
  - BCLK: GPIO 42
  - LRC: GPIO 41
  - DOUT: GPIO 40
  - Power: 3.3V (NOT 5V - important!)

- **Microphone I2S (INMP441):**
  - SCK (BCLK): GPIO 15 (alternative pins if issues)
  - WS (LRCLK): GPIO 16
  - SD (Data): GPIO 17
  - L/R: GND (for left channel)
  - Power: 3.3V

- **Status LEDs:**
  - Power (Green): GPIO 11 - Always on when powered
  - Server (Blue): GPIO 12 - On when connected to WebSocket
  - Microphone (Yellow): GPIO 13 - Flashes when detecting voice
  - Speaker (Red): GPIO 14 - On during audio playback

## Deployment Workflow

### 1. Compile and Upload
```bash
# Compile the sketch
arduino-cli compile --fqbn esp32:esp32:esp32s3 ParrotDriver/

# Upload to ESP32 (make sure Arduino IDE is closed first!)
arduino-cli upload -p /dev/cu.usbmodem5A4E1311211 --fqbn esp32:esp32:esp32s3 ParrotDriver/
```

### 2. Monitor Serial Output
After deployment, always check the serial output to verify the device is working:

```bash
# Option 1: Arduino CLI monitor (recommended)
arduino-cli monitor -p /dev/cu.usbmodem5A4E1311211 -c baudrate=115200

# Option 2: Direct cat (less reliable)
cat /dev/cu.usbmodem5A4E1311211
```

### 3. Common Issues
- **Port busy error**: Close Arduino IDE or any serial monitors before uploading
- **Upload fails**: Unplug and replug the ESP32, then retry
- **No serial output**: Check baud rate is set to 115200

## Testing Features

On boot, the device:
1. **Servo Test**: Each servo briefly moves to verify connections
2. **LED Test**: All status LEDs initialize (power LED stays on)
3. **Idle Animation**: Natural movements including:
   - Head rotation (looking left/right)
   - Head tilt variations
   - Occasional wing movements
   - Runs continuously when not actively speaking

## Server Configuration
- Server IP: 192.168.1.174
- WebSocket Ports:
  - Control: 8080
  - Audio Stream: 8001
  - Microphone: 8002

## WiFi Setup
On first boot or after reset:
1. Connect to "ParrotConfig-XXXX" WiFi network (XXXX is device specific)
2. Open browser to 192.168.4.1
3. Enter home WiFi credentials
4. Device will save credentials and auto-connect on future boots

## Troubleshooting

### Hardware Issues
- **Servos not responding**: Check ground connection between ESP32 and Bottango boards
- **Speaker no audio**: Ensure MAX98357A is connected to 3.3V, not 5V
- **Microphone not working**: Verify INMP441 L/R pin is grounded for left channel
- **GPIO 4 issues**: This pin doesn't work reliably on ESP32-S3
- **GPIO 10 issues**: If this pin has problems, use GPIO 9 as alternative

### LED Indicators
- **No blue LED**: Server connection failed - check WiFi and server IP
- **Yellow LED not flashing**: Microphone not detecting audio - check wiring
- **Red LED stuck on**: Audio playback issue - restart device

### Direct Servo Control
The system now uses direct PWM control instead of Bottango commands for reliability:
- Servos are controlled directly via ESP32Servo library
- Idle animations run independently of server connection
- More stable and responsive than Bottango protocol