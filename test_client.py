import asyncio
import websockets
import pyaudio
import numpy as np
import aioconsole
import traceback
import base64
import json
import webrtcvad
from array import array
from collections import deque

class AudioClient:
    def __init__(self):
        self.CHUNK = 960  # 40ms at 24kHz
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 24000  # Match OpenAI's sample rate
        self.p = pyaudio.PyAudio()
        self.running = True
        self.is_recording = False
        
        # Find default input device
        self.input_device_index = self.get_default_input_device()
        
        # Initialize audio streams
        self.recording_stream = None
        self.playback_stream = self.p.open(
            format=self.FORMAT,
            channels=self.CHANNELS,
            rate=self.RATE,
            output=True,
            frames_per_buffer=self.CHUNK
        )

    def get_default_input_device(self):
        """Find the default input device index"""
        default_device = None
        default_device_info = self.p.get_default_input_device_info()
        print(f"\nDefault input device: {default_device_info['name']}")
        
        print("\nAvailable input devices:")
        for i in range(self.p.get_device_count()):
            dev_info = self.p.get_device_info_by_index(i)
            if dev_info.get('maxInputChannels') > 0:  # Only show input devices
                print(f"Device {i}: {dev_info.get('name')}")
                if dev_info['index'] == default_device_info['index']:
                    default_device = i
                    print("  ↑ DEFAULT DEVICE")
        
        return default_device

    def start_recording(self):
        if not self.is_recording:
            print("\nInitializing recording stream...")
            try:
                self.recording_stream = self.p.open(
                    format=self.FORMAT,
                    channels=self.CHANNELS,
                    rate=self.RATE,
                    input=True,
                    input_device_index=self.input_device_index,
                    frames_per_buffer=self.CHUNK
                )
                self.is_recording = True
                print(f"Recording stream initialized successfully using device index: {self.input_device_index}")
                
            except Exception as e:
                print(f"\nError initializing recording stream: {e}")
                traceback.print_exc()
                return

    def stop_recording(self):
        if self.is_recording:
            self.is_recording = False
            if self.recording_stream:
                self.recording_stream.stop_stream()
                self.recording_stream.close()
                self.recording_stream = None
            print("\nRecording stopped")

    async def connect_websocket(self):
        self.ws = await websockets.connect('ws://localhost:8000/proxy-openai')
        print("Connected to server")
        
    async def send_audio(self):
        """Send raw audio to server"""
        print("Starting audio streaming...")
        bytes_sent = 0
        chunks_sent = 0
        
        while self.running and self.is_recording:
            try:
                # Read audio data
                audio_data = self.recording_stream.read(self.CHUNK, exception_on_overflow=False)
                if audio_data:
                    # Send raw audio to server as binary message
                    await self.ws.send(audio_data)  # websockets automatically handles binary data
                    
                    bytes_sent += len(audio_data)
                    chunks_sent += 1
                    if chunks_sent % 25 == 0:  # Update every second
                        print(f"\rStreaming... Sent: {bytes_sent/1024:.1f}KB", end='')
                
                await asyncio.sleep(0.01)
                
            except Exception as e:
                print(f"\nError sending audio: {e}")
                traceback.print_exc()
                continue
        
        print(f"\nStopped streaming. Total sent: {bytes_sent/1024:.2f}KB")

    async def receive_audio(self):
        """Receive audio from server"""
        print("Starting audio receive loop")
        while self.running:
            try:
                message = await self.ws.recv()
                if isinstance(message, bytes):
                    print(f"\nReceived {len(message)} bytes of audio")
                    self.playback_stream.write(message)
                    print("Played audio chunk")
                elif isinstance(message, str):
                    msg_data = json.loads(message)
                    msg_type = msg_data.get("type", "")
                    if "transcript" in msg_type:
                        print(f"\nTranscript: {msg_data.get('delta', '')}")
                    else:
                        print(f"\nReceived message: {msg_type}")
            except Exception as e:
                print(f"\nError receiving audio: {e}")
                traceback.print_exc()
                break

    def cleanup(self):
        """Clean up audio resources"""
        self.running = False
        self.stop_recording()
        if self.playback_stream:
            self.playback_stream.stop_stream()
            self.playback_stream.close()
        self.p.terminate()

async def main():
    client = AudioClient()
    
    try:
        await client.connect_websocket()
        receive_task = asyncio.create_task(client.receive_audio())
        
        print("Press 'r' to start/stop recording, 'q' to quit")
        
        while client.running:
            command = await aioconsole.ainput()
            if command.lower() == 'r':
                if not client.is_recording:
                    client.start_recording()
                    asyncio.create_task(client.send_audio())
                else:
                    client.stop_recording()
            elif command.lower() == 'q':
                break
                
        client.cleanup()
        receive_task.cancel()
        try:
            await receive_task
        except asyncio.CancelledError:
            pass
        await client.ws.close()
        
    except Exception as e:
        print(f"Error in main: {e}")
    finally:
        client.cleanup()

if __name__ == "__main__":
    asyncio.run(main()) 