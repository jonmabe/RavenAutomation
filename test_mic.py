#!/usr/bin/env python3
import asyncio
import websockets
import struct
import numpy as np

async def test_microphone():
    # CapRover server IP
    uri = "ws://192.168.1.172:8002/microphone"
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected to ESP32 microphone WebSocket")
            print("Listening for audio... (whistle or make noise near the mic)")
            
            max_level = 0
            sample_count = 0
            
            while True:
                try:
                    data = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    
                    # Convert bytes to int16 array
                    samples = np.frombuffer(data, dtype=np.int16)
                    
                    if len(samples) > 0:
                        # Calculate RMS (root mean square) for volume level
                        rms = np.sqrt(np.mean(samples.astype(np.float32) ** 2))
                        
                        # Track max level
                        current_max = np.max(np.abs(samples))
                        if current_max > max_level:
                            max_level = current_max
                        
                        sample_count += 1
                        
                        # Print level meter every 10 samples
                        if sample_count % 10 == 0:
                            level_bar = '#' * min(50, int(rms / 100))
                            print(f"Audio Level: {level_bar:<50} RMS: {rms:6.0f} Max: {max_level:6d}")
                            
                            # Check if we're getting reasonable audio levels
                            if max_level > 5000:
                                print("✓ Microphone is detecting audio!")
                            elif max_level > 1000:
                                print("~ Microphone sensitivity is low")
                            else:
                                print("✗ Microphone levels are very low")
                                
                except asyncio.TimeoutError:
                    print(".", end="", flush=True)
                except Exception as e:
                    print(f"Error: {e}")
                    break
                    
    except Exception as e:
        print(f"Connection failed: {e}")
        print("Make sure the ESP32 is running and connected to WiFi")

if __name__ == "__main__":
    print("ESP32 Microphone Test")
    print("=" * 50)
    asyncio.run(test_microphone())