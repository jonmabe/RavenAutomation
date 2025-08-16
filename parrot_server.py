from fastapi import FastAPI, WebSocket
import asyncio
import websockets
import pyaudio
import numpy as np
import traceback
import base64
import json
import time
import uvicorn
from typing import Set, Optional, List, Callable
from openai import OpenAIProxy  # Replace FastAPI WebSocket client with direct OpenAI proxy
from dataclasses import dataclass
import random
import wave
from datetime import datetime
import os
from scipy import signal
import argparse

# Global configuration
USE_WEBSOCKET_AUDIO = True  # Control whether to use websocket or local audio
USE_WEBSOCKET_MIC = True   # Control whether to use ESP32 or local microphone
AUDIO_WS_PORT = 8001  # Port for audio websocket server
MICROPHONE_WS_PORT = 8002  # Port for microphone WebSocket server

@dataclass
class ParrotBehavior:
    name: str
    prompt: str
    frequency: float  # 0-1, how often this behavior should occur
    min_silence: float  # minimum seconds of silence before this can trigger
    last_used: float = 0  # timestamp of last use
    cooldown: float = 30.0  # minimum seconds between uses

class BehaviorManager:
    def __init__(self):
        self.behaviors: List[ParrotBehavior] = [
            ParrotBehavior(
                name="whistle",
                prompt="/whistle",
                frequency=0.7,
                min_silence=5.0
            ),
            ParrotBehavior(
                name="squawk",
                prompt="/squawk",
                frequency=0.7,
                min_silence=5.0
            ),
            ParrotBehavior(
                name="sing",
                prompt="Sing a very short snippet of a sea shanty.",
                frequency=0.4,
                min_silence=20.0,
                cooldown=180.0
            ),
            ParrotBehavior(
                name="cracker",
                prompt="Ask for a cracker in a creative or funny way.",
                frequency=0.3,
                min_silence=10.0
            ),
            ParrotBehavior(
                name="story",
                prompt="Offer to tell a very short story about your adventures as a pirate parrot.",
                frequency=0.4,
                min_silence=15.0,
                cooldown=120.0
            ),
            ParrotBehavior(
                name="joke",
                prompt="Offer to tell a short bird or pirate related joke.",
                frequency=0.5,
                min_silence=12.0,
                cooldown=60.0
            ),
            ParrotBehavior(
                name="observation",
                prompt="Make a cheeky observation about the room or the situation.",
                frequency=0.6,
                min_silence=8.0
            )
        ]
        
        
        self.last_interaction = time.time()
        self.base_probability = 0.2  # Base chance of any behavior triggering
        self.max_silence = 30.0  # Probability increases after this much silence

    def should_trigger_behavior(self, silence_duration: float) -> Optional[ParrotBehavior]:
        current_time = time.time()
        
        # Increase probability based on silence duration
        probability_multiplier = min(3.0, 1.0 + (silence_duration / self.max_silence))
        
        # Check each behavior
        eligible_behaviors = []
        for behavior in self.behaviors:
            # Check if behavior is eligible (enough silence and not on cooldown)
            if (silence_duration >= behavior.min_silence and 
                current_time - behavior.last_used >= behavior.cooldown):
                eligible_behaviors.append(behavior)
        
        print(f"Eligible behaviors: {[b.name for b in eligible_behaviors]}, probability multiplier: {probability_multiplier}, base probability: {self.base_probability}, silence duration: {silence_duration}, current time: {current_time}, behavior count: {len(eligible_behaviors)}, eligible behaviors: {eligible_behaviors}")
        
        # Weight behaviors by frequency
        weights = [b.frequency for b in eligible_behaviors]
        
        # Random chance to trigger any behavior
        if (eligible_behaviors and 
            random.random() < self.base_probability * probability_multiplier):
            # Choose behavior based on frequencies
            chosen = random.choices(eligible_behaviors, weights=weights, k=1)[0]
            chosen.last_used = current_time
            return chosen
            
        return None

class AudioClient:
    def __init__(self, save_recordings=False):
        # Audio configuration
        self.CHUNK = 960  # 40ms at 24kHz
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 24000
        self.running = True
        self.save_recordings = save_recordings
                
        # State management
        self.is_recording = False
        self.is_speaking = False
        self.audio_end_time = 0
        
        # Audio processing
        self.p = pyaudio.PyAudio()
        self.input_device_index = self.get_default_input_device() if not USE_WEBSOCKET_MIC else None
        self.recording_stream = None
        
        # WebSocket connections
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.active_audio_connections: Set[WebSocket] = set()
        
        # Tasks
        self.tasks = []
        
        # Initialize OpenAI connection
        self.openai = OpenAIProxy()
        
        # Behavior management
        self.behavior_manager = BehaviorManager()
        self.last_automation_input = time.time()
        self.autonomous_mode = True  # Can be toggled to disable autonomous behaviors
        
        # Add microphone WebSocket server
        self.mic_app = FastAPI()
        self.mic_connections: Set[WebSocket] = set()
        
        # Add audio recording buffers
        self.current_audio_chunks = []
        self.recordings_dir = "mic_recordings"
        os.makedirs(self.recordings_dir, exist_ok=True)
        
        # Voice activity detection
        self.voice_threshold = 1000  # Adjust based on your environment
        self.silence_duration = 0
        self.max_silence_duration = 1.5  # seconds of silence before saving
        self.recording_active = False
        self.last_voice_time = 0
        
        # Add audio processing parameters
        self.dc_offset = 0  # Will be calculated dynamically
        self.alpha = 0.95   # For DC offset estimation
        self.gain = 1.5     # Adjustable gain factor
        
        # Add connection lock to prevent concurrent OpenAI connections
        self.openai_connection_lock = asyncio.Lock()
    
    @property
    def has_esp32_connected(self):
        """Check if any ESP32 client is connected"""
        return len(self.active_audio_connections) > 0 or len(self.mic_connections) > 0
    
    def save_audio_recording(self, audio_chunks, prefix="recording"):
        """Save audio chunks to a WAV file"""
        if not audio_chunks or not self.save_recordings:
            return
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{prefix}_{timestamp}.wav"
        filepath = os.path.join(self.recordings_dir, filename)
        
        # Combine all audio chunks
        audio_data = b''.join(audio_chunks)
        
        # Save as WAV file
        with wave.open(filepath, 'wb') as wf:
            wf.setnchannels(self.CHANNELS)
            wf.setsampwidth(2)  # 16-bit audio
            wf.setframerate(self.RATE)
            wf.writeframes(audio_data)
        
        print(f"Saved recording: {filename} ({len(audio_data)/self.RATE/2:.1f} seconds)")
        return filepath
    
    def detect_voice_activity(self, audio_data):
        """Detect if audio contains voice based on amplitude"""
        # Convert bytes to numpy array
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
        
        # Calculate RMS (root mean square) for volume level
        rms = np.sqrt(np.mean(audio_array.astype(np.float32) ** 2))
        
        return rms > self.voice_threshold
    
    async def manage_openai_connection(self):
        """Connect to OpenAI only when ESP32 is connected"""
        async with self.openai_connection_lock:
            try:
                if self.has_esp32_connected and self.openai.ws is None:
                    print("ESP32 connected, establishing OpenAI connection...")
                    await self.openai.connect()
                    print("Connected to OpenAI")
                elif not self.has_esp32_connected and self.openai.ws is not None:
                    print("No ESP32 clients, closing OpenAI connection...")
                    await self.openai.disconnect()
                    print("Disconnected from OpenAI")
            except Exception as e:
                print(f"Error managing OpenAI connection: {e}")
                # Reset the WebSocket to None in case of error
                self.openai.ws = None
        
    def get_default_input_device(self):
        """Find the default input device index"""
        default_device = None
        default_device_info = self.p.get_default_input_device_info()
        print(f"\nDefault input device: {default_device_info['name']}")
        
        print("\nAvailable input devices:")
        for i in range(self.p.get_device_count()):
            dev_info = self.p.get_device_info_by_index(i)
            if dev_info.get('maxInputChannels') > 0:
                print(f"Device {i}: {dev_info.get('name')}")
                if dev_info['index'] == default_device_info['index']:
                    default_device = i
                    print("  ↑ DEFAULT DEVICE")
        
        return default_device

    async def setup(self):
        """Initialize all async components"""
        # Don't connect to OpenAI immediately - wait for ESP32
        print("Server started. Waiting for ESP32 connection...")
        print(f"Audio WebSocket listening on port {AUDIO_WS_PORT}")
        print(f"Microphone WebSocket listening on port {MICROPHONE_WS_PORT}")
        
        # Start the FastAPI server for audio WebSocket
        if USE_WEBSOCKET_AUDIO:
            self.app = FastAPI()
            self.setup_audio_websocket()
            # Start the server in the background
            config = uvicorn.Config(self.app, host="0.0.0.0", port=AUDIO_WS_PORT, log_level="error")
            self.server = uvicorn.Server(config)
            self.server_task = asyncio.create_task(self.server.serve())
            await asyncio.sleep(1)  # Give server time to start
        
        # Start the microphone WebSocket server only if using ESP32 mic
        if USE_WEBSOCKET_MIC:
            mic_config = uvicorn.Config(self.mic_app, host="0.0.0.0", port=MICROPHONE_WS_PORT, log_level="error")
            self.mic_server = uvicorn.Server(mic_config)
            self.mic_server_task = asyncio.create_task(self.mic_server.serve())
        
        # Setup microphone WebSocket endpoint
        @self.mic_app.websocket("/microphone")
        async def microphone_websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            self.mic_connections.add(websocket)
            print("ESP32 Microphone client connected")
            
            # Connect to OpenAI when first ESP32 connects
            await self.manage_openai_connection()
            
            try:
                while True:
                    try:
                        data = await websocket.receive_bytes()
                        if not self.is_speaking:
                            current_time = time.time()
                            
                            # Check for voice activity
                            has_voice = self.detect_voice_activity(data)
                            
                            if has_voice:
                                # Voice detected
                                if not self.recording_active:
                                    self.recording_active = True
                                    self.current_audio_chunks = []
                                    print("Started recording (voice detected)")
                                
                                self.last_voice_time = current_time
                                self.current_audio_chunks.append(data)
                                
                            elif self.recording_active:
                                # No voice but still recording
                                self.current_audio_chunks.append(data)
                                
                                # Check if silence duration exceeded
                                silence_time = current_time - self.last_voice_time
                                if silence_time > self.max_silence_duration:
                                    # Save the recording
                                    self.save_audio_recording(self.current_audio_chunks, "voice")
                                    self.recording_active = False
                                    self.current_audio_chunks = []
                                    print("Stopped recording (silence detected)")
                            
                            # Send audio to OpenAI
                            await self.openai.send_audio(data)
                    except Exception as e:
                        print(f"Error in microphone websocket: {e}")
                        break
            finally:
                self.mic_connections.remove(websocket)
                print("ESP32 Microphone client disconnected")
                
                # Disconnect from OpenAI if no more clients
                await self.manage_openai_connection()
                
                try:
                    await websocket.close()
                except:
                    pass

    def setup_audio_websocket(self):
        """Setup FastAPI WebSocket endpoint"""
        @self.app.websocket("/audio-stream")
        async def audio_websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            self.active_audio_connections.add(websocket)
            print("ESP32 Audio client connected")
            
            # Connect to OpenAI when first ESP32 connects
            await self.manage_openai_connection()
            
            try:
                while True:
                    try:
                        await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
                    except asyncio.TimeoutError:
                        continue
                    except Exception as e:
                        print(f"Error in audio websocket: {e}")
                        break
            finally:
                self.active_audio_connections.remove(websocket)
                print("ESP32 Audio client disconnected")
                
                # Disconnect from OpenAI if no more clients
                await self.manage_openai_connection()
                
                try:
                    await websocket.close()
                except:
                    pass

    async def cleanup(self):
        """Cleanup all resources"""
        self.running = False
        
        # Cancel all tasks
        for task in self.tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # Close WebSocket connections
        if self.ws:
            await self.ws.close()
        
        # Stop recording if active
        if self.recording_stream:
            self.recording_stream.stop_stream()
            self.recording_stream.close()
        
        # Cleanup PyAudio
        self.p.terminate()

    def start_recording(self):
        """Start audio recording"""
        if not self.is_recording:
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
                print("Recording started")
            except Exception as e:
                print(f"Error starting recording: {e}")
                traceback.print_exc()

    def stop_recording(self):
        """Stop audio recording"""
        if self.is_recording:
            self.is_recording = False
            if self.recording_stream:
                self.recording_stream.stop_stream()
                self.recording_stream.close()
                self.recording_stream = None
            print("Recording stopped") 

    async def main_loop(self):
        """Main entry point for all async operations"""
        try:
            await self.setup()
            
            # Only start recording if using local microphone
            if not USE_WEBSOCKET_MIC:
                self.start_recording()
            
            # Create all tasks
            self.tasks = [
                asyncio.create_task(self.receive_from_openai()),
                asyncio.create_task(self.manage_speaking_state()),
                asyncio.create_task(self.manage_autonomous_behaviors())
            ]
            
            # Add process_microphone task only if using local microphone
            if not USE_WEBSOCKET_MIC:
                self.tasks.append(asyncio.create_task(self.process_microphone()))
            
            await asyncio.gather(*self.tasks)
            
        except Exception as e:
            print(f"Error in main loop: {e}")
            traceback.print_exc()
        finally:
            if not USE_WEBSOCKET_MIC:
                self.stop_recording()
            await self.cleanup()

    async def receive_from_openai(self):
        """Receive and process audio from OpenAI"""
        try:
            while self.running:
                # Only try to receive if connected to OpenAI
                if self.openai.ws is None:
                    await asyncio.sleep(1)
                    continue
                    
                response = await self.openai.receive()
                response_data = json.loads(response)
                response_type = response_data.get("type", "")

                if "response.audio.delta" in response_type:
                    audio_base64 = response_data.get("delta", "")
                    if audio_base64:
                        # Save any ongoing recording before parrot speaks
                        if self.recording_active and self.current_audio_chunks:
                            self.save_audio_recording(self.current_audio_chunks, "voice_before_response")
                            self.recording_active = False
                            self.current_audio_chunks = []
                        
                        self.is_speaking = True
                        audio_data = base64.b64decode(audio_base64)
                        audio_length = len(audio_data)/self.RATE
                        
                        if USE_WEBSOCKET_AUDIO:
                            await self.stream_to_speakers(audio_data)
                        else:
                            # Handle local playback if implemented
                            pass
                    self.last_automation_input = time.time()
                elif response_type == "input_audio_buffer.speech_started":
                    self.current_audio_chunks = []  # Clear buffer for new recording
                    self.last_automation_input = time.time()
                elif response_type == "input_audio_buffer.speech_stopped":
                    # Save the recorded audio to a WAV file
                    if self.save_recordings and self.current_audio_chunks:
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = os.path.join(self.recordings_dir, f"mic_recording_{timestamp}.wav")
                        
                        with wave.open(filename, 'wb') as wav_file:
                            wav_file.setnchannels(self.CHANNELS)
                            wav_file.setsampwidth(2)  # 16-bit audio
                            wav_file.setframerate(self.RATE)
                            wav_file.writeframes(b''.join(self.current_audio_chunks))
                        
                        print(f"Saved recording to {filename}")
                        self.current_audio_chunks = []  # Clear the buffer
                elif response_type == "response.done":
                    pass
                        
        except Exception as e:
            print(f"Error in receive audio: {e}")
            traceback.print_exc()

    async def manage_speaking_state(self):
        """Manage speaking state based on audio timing"""
        try:
            while self.running:
                current_time = time.time()
                if self.is_speaking:
                    if current_time >= (self.audio_end_time + .25):
                        print("Audio playback complete")
                        self.is_speaking = False
                        self.audio_end_time = 0
                await asyncio.sleep(0.1)
                
        except Exception as e:
            print(f"Error in speaking state management: {e}")
            traceback.print_exc() 

    async def stream_to_speakers(self, audio_data):
        """Stream audio data to all connected ESP32 clients"""
        if not self.active_audio_connections:
            print("No ESP32 audio clients connected")
            return
            
        try:
            # Calculate audio duration and update end time
            audio_duration = len(audio_data) / (self.RATE * 2)  # 2 bytes per sample
            
            if self.audio_end_time == 0: 
                self.audio_end_time = time.time() + audio_duration
            else:
                self.audio_end_time += audio_duration
            
            # Stream the audio data
            chunk_size = 1024  # Network chunks
            for i in range(0, len(audio_data), chunk_size):
                chunk = audio_data[i:i + chunk_size]
                                
                # Create a copy of connections to avoid modification during iteration
                clients = list(self.active_audio_connections)
                
                # Send to each client sequentially
                for client in clients:
                    try:
                        await client.send_bytes(chunk)
                    except Exception as e:
                        print(f"Error sending to client: {e}")
                        if client in self.active_audio_connections:
                            self.active_audio_connections.remove(client)
                
                # Minimal delay to prevent overwhelming the connection
                await asyncio.sleep(0.0005)
                
        except Exception as e:
            print(f"Error in stream_to_speakers: {e}")
            traceback.print_exc()

    async def manage_autonomous_behaviors(self):
        """Manage autonomous parrot behaviors during periods of silence"""
        try:
            while self.running:
                # Only run behaviors if ESP32 is connected
                if self.autonomous_mode and not self.is_speaking and self.has_esp32_connected:
                    current_time = time.time()
                    silence_duration = current_time - self.last_automation_input
                    
                    behavior = self.behavior_manager.should_trigger_behavior(silence_duration)
                    if behavior:
                        print(f"Triggering autonomous behavior: {behavior.name}")
                        # Send behavior prompt to OpenAI
                        try:
                            await self.openai.send_text("autonomous_command: " + behavior.prompt)
                            # Reset silence timer
                            self.last_automation_input = current_time
                        except websockets.exceptions.ConnectionClosedError:
                            print("WebSocket disconnected during autonomous behavior, reconnecting...")
                            # Will reconnect on next loop iteration
                            pass
                elif not self.has_esp32_connected and self.autonomous_mode:
                    # Log once when no client is connected
                    await asyncio.sleep(5)  # Check less frequently when no client
                    continue
                        
                await asyncio.sleep(1.0)  # Check every second
                
        except Exception as e:
            print(f"Error in autonomous behaviors: {e}")
            traceback.print_exc()

    async def process_microphone(self):
        """Process local microphone input"""
        try:
            while self.running and self.recording_stream:
                if not self.is_speaking:
                    try:
                        data = self.recording_stream.read(self.CHUNK, exception_on_overflow=False)

                        # Store the processed audio chunk
                        self.current_audio_chunks.append(data)
                        
                        # Send to OpenAI
                        await self.openai.send_audio(data)
                        self.last_automation_input = time.time()
                    except Exception as e:
                        print(f"Error sending to OpenAI: {e}")
                await asyncio.sleep(0.0001)
                
        except Exception as e:
            print(f"Error in microphone processing: {e}")
            traceback.print_exc()

# Create FastAPI app for audio websocket
audio_app = FastAPI()

async def main(save_recordings=False):
    """Main entry point for the application"""
    client = AudioClient(save_recordings=save_recordings)
    
    try:
        await client.main_loop()
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"Error in main: {e}")
        traceback.print_exc()
    finally:
        await client.cleanup()

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Parrot Server')
    parser.add_argument('--save-recordings', action='store_true',
                        help='Save audio recordings when voice is detected')
    args = parser.parse_args()
    
    if args.save_recordings:
        print("Audio recording enabled - recordings will be saved to 'mic_recordings' directory")
    
    # Run the main async function
    asyncio.run(main(save_recordings=args.save_recordings)) 