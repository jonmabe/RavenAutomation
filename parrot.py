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
            )
        ]
        #ParrotBehavior(
        #    name="cracker",
        #    prompt="Ask for a cracker in a creative or funny way.",
        #    frequency=0.3,
        #    min_silence=10.0
        #),
        #ParrotBehavior(
        #    name="story",
        #    prompt="Offer to tell a very short story about your adventures as a pirate parrot.",
        #    frequency=0.4,
        #    min_silence=15.0,
        #    cooldown=120.0
        #),
        #ParrotBehavior(
        #    name="joke",
        #    prompt="Offer to tell a short bird or pirate related joke.",
        #    frequency=0.5,
        #    min_silence=12.0,
        #    cooldown=60.0
        #),
        #ParrotBehavior(
        #    name="observation",
        #    prompt="Make a cheeky observation about the room or the situation.",
        #    frequency=0.6,
        #    min_silence=8.0
        #),
        
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
    def __init__(self):
        # Audio configuration
        self.CHUNK = 960  # 40ms at 24kHz
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 24000
        self.running = True
        
        # Initialize robot driver
        from robot_driver_websocket import BottangoDriver
        self.robot = BottangoDriver()
        self.robot.start_server_background()
        
        # State management
        self.is_recording = False
        self.is_speaking = False
        self.audio_end_time = 0
        
        # Animation parameters
        self.mouth_next_position = 0.0
        self.mouth_current_position = 0.0
        self.wing_next_position = 0.0
        self.wing_current_position = 0.0
        self.head_tilt_next_position = 0.0
        self.head_tilt_current_position = 0.0
        self.head_rotation_next_position = 0.0
        self.head_rotation_current_position = 0.0
        
        # Animation timing
        self.last_idle_time = time.time()
        self.idle_interval = 0.5
        self.idle_variance = 0.3
        self.energy_smoothing = 0.5
        self.last_energy = 0.0
        self.animation_resolution = 0.05
        
        # Head movement state
        self.head_looking_left = True
        self.head_movement_type = 'side'
        
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
        # Connect to OpenAI
        await self.openai.connect()
        print("Connected to OpenAI")
        
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
            
            try:
                while True:
                    try:
                        # Receive audio data from ESP32 microphone
                        data = await websocket.receive_bytes()
                        if not self.is_speaking:
                            # Forward microphone data to OpenAI
                            await self.openai.send_audio(data)
                    except Exception as e:
                        print(f"Error in microphone websocket: {e}")
                        break
            finally:
                self.mic_connections.remove(websocket)
                print("ESP32 Microphone client disconnected")
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
                asyncio.create_task(self.animation_loop()),
                asyncio.create_task(self.receive_from_openai()),
                asyncio.create_task(self.manage_speaking_state()),
                #asyncio.create_task(self.manage_autonomous_behaviors())
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

    async def animation_loop(self):
        """Main animation loop with parrot-like head movements"""
        try:
            while self.running:
                current_time = time.time()
                
                # Handle idle animations when not speaking
                if not self.is_speaking:
                    if current_time - self.last_idle_time > self.idle_interval + np.random.uniform(0, self.idle_variance):
                        if self.head_movement_type == 'side':
                            self.head_looking_left = not self.head_looking_left
                            self.head_rotation_next_position = 0.8 if self.head_looking_left else 0.2
                            self.head_movement_type = 'tilt' if np.random.random() < 0.5 else 'side'
                        else:
                            self.head_tilt_next_position = np.random.uniform(0.2, 0.8)
                            self.head_movement_type = 'side'
                        
                        self.last_idle_time = current_time
                        self.idle_interval = 0.5 + np.random.uniform(-0.2, 0.2)
                
                # Update positions with faster movements
                if self.mouth_current_position != self.mouth_next_position:
                    await self.robot.set_mouth(self.mouth_next_position)
                    self.mouth_current_position = self.mouth_next_position
                
                if self.wing_current_position != self.wing_next_position:
                    delta = self.wing_next_position - self.wing_current_position
                    self.wing_current_position += delta * 0.6
                    await self.robot.set_wing(self.wing_current_position)
                
                if self.head_tilt_current_position != self.head_tilt_next_position:
                    delta = self.head_tilt_next_position - self.head_tilt_current_position
                    self.head_tilt_current_position += delta * 0.7
                    await self.robot.set_head_tilt(self.head_tilt_current_position)
                
                if self.head_rotation_current_position != self.head_rotation_next_position:
                    delta = self.head_rotation_next_position - self.head_rotation_current_position
                    self.head_rotation_current_position += delta * 0.7
                    await self.robot.set_head_rotation(self.head_rotation_current_position)
                
                await asyncio.sleep(self.animation_resolution)
                
        except Exception as e:
            print(f"Error in animation loop: {e}")
            traceback.print_exc()

    async def receive_from_openai(self):
        """Receive and process audio from OpenAI"""
        try:
            while self.running:
                response = await self.openai.receive()
                response_data = json.loads(response)
                response_type = response_data.get("type", "")

                if "response.audio.delta" in response_type:
                    audio_base64 = response_data.get("delta", "")
                    if audio_base64:
                        self.is_speaking = True
                        audio_data = base64.b64decode(audio_base64)
                        audio_length = len(audio_data)/self.RATE
                        print(f"Received {audio_length:.3f}s of audio")
                        
                        if USE_WEBSOCKET_AUDIO:
                            await self.stream_to_speakers(audio_data)
                        else:
                            # Handle local playback if implemented
                            pass
                    self.last_automation_input = time.time()
                elif response_type == "input_audio_buffer.speech_started":
                    # Update last voice input time when we get microphone data
                    self.last_automation_input = time.time()
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
            animation_start_time = self.audio_end_time
            if self.audio_end_time == 0: 
                self.audio_end_time = time.time() + audio_duration
            else:
                self.audio_end_time += audio_duration
            
            # Start animation calculation in a separate task
            animation_task = asyncio.create_task(
                self.calculate_animation_positions(audio_data, audio_duration, animation_start_time)
            )
            
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

    async def calculate_animation_positions(self, audio_data, audio_duration, audio_start_time):
        """Calculate next positions for all animated components"""
        try:
            if not audio_data or len(audio_data) == 0:
                return
            
            while audio_start_time > time.time():
                await asyncio.sleep(0.0001)
            
            # Calculate how many samples per animation frame
            samples_per_frame = int(self.RATE * 2 * self.animation_resolution)  # 2 bytes per sample
            num_frames = len(audio_data) // samples_per_frame
            
            print(f"Calculating {num_frames} animation frames over {audio_duration:.3f}s")
            
            for frame in range(num_frames):
                # Get the audio chunk for this frame
                start = frame * samples_per_frame
                end = start + samples_per_frame
                chunk = audio_data[start:end]
                
                # Calculate positions for this frame
                audio_array = np.frombuffer(chunk, dtype=np.int16)
                amplitude = np.percentile(np.abs(audio_array), 80)
                
                self.mouth_next_position = np.random.uniform(0.0, 0.5) if amplitude > 800 else 1.0
                
                current_energy = min(1.0, amplitude / 2000)
                smoothed_energy = (current_energy * (1 - self.energy_smoothing) + 
                                 self.last_energy * self.energy_smoothing)
                self.last_energy = smoothed_energy
                
                wing_energy = smoothed_energy * 1.2
                wing_base = 0.2
                wing_random = np.random.uniform(-0.1, 0.1)
                self.wing_next_position = wing_base + wing_energy * 0.8 + wing_random
                self.wing_next_position = max(0.0, min(1.0, self.wing_next_position))
                
                tilt_energy = smoothed_energy * 0.3
                self.head_tilt_next_position = 0.4 + tilt_energy * 0.6
                
                self.head_rotation_next_position = 0.5 + np.random.uniform(-0.1, 0.1)
                
                # Wait for one animation frame duration
                await asyncio.sleep(self.animation_resolution)
            
        except Exception as e:
            print(f"Error in animation calculation: {e}")
            traceback.print_exc()

    async def manage_autonomous_behaviors(self):
        """Manage autonomous parrot behaviors during periods of silence"""
        try:
            while self.running:
                if self.autonomous_mode and not self.is_speaking:
                    current_time = time.time()
                    silence_duration = current_time - self.last_automation_input
                    
                    behavior = self.behavior_manager.should_trigger_behavior(silence_duration)
                    if behavior:
                        print(f"Triggering autonomous behavior: {behavior.name}")
                        # Send behavior prompt to OpenAI
                        await self.openai.send_text("autonomous_command: " + behavior.prompt)
                        # Reset silence timer
                        self.last_automation_input = current_time
                        
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
                        await self.openai.send_audio(data)
                        # Update last voice input time when we get microphone data
                        self.last_automation_input = time.time()
                    except Exception as e:
                        print(f"Error sending to OpenAI: {e}")
                await asyncio.sleep(0.0001)
                
        except Exception as e:
            print(f"Error in microphone processing: {e}")
            traceback.print_exc()

# Create FastAPI app for audio websocket
audio_app = FastAPI()

async def main():
    """Main entry point for the application"""
    client = AudioClient()
    
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
    # Run the main async function
    asyncio.run(main()) 