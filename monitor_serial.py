#!/usr/bin/env python3
import serial
import time

port = "/dev/cu.usbmodem5A4E1311211"
baud = 115200

print(f"Monitoring serial port {port} at {baud} baud...")
print("Looking for microphone debug info...")
print("-" * 50)

try:
    with serial.Serial(port, baud, timeout=1) as ser:
        start_time = time.time()
        while time.time() - start_time < 10:  # Monitor for 10 seconds
            if ser.in_waiting:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if line:
                    # Show all lines but highlight mic-related ones
                    if 'mic' in line.lower() or 'audio' in line.lower() or 'i2s' in line.lower():
                        print(f">>> {line}")
                    else:
                        print(f"    {line}")
except Exception as e:
    print(f"Error: {e}")
    print("Make sure Arduino IDE or screen is not using the port")