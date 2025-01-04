from fastapi import FastAPI, WebSocket
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
from robot_driver_websocket import BottangoDriver
import time

# Global configuration
USE_WEBSOCKET_AUDIO = True  # Control whether to use websocket or local audio
AUDIO_WS_PORT = 8001  # Port for audio websocket server

# Create FastAPI app with custom WebSocket settings
audio_app = FastAPI()
active_audio_connections = set()

@audio_app.websocket("/audio-stream")
async def audio_websocket_endpoint(websocket: WebSocket):
    # Configure WebSocket with longer ping interval
    websocket.ping_interval = 30.0  # Increase ping interval to 30 seconds
    websocket.ping_timeout = 10.0   # Increase ping timeout to 10 seconds
    
    await websocket.accept()
    active_audio_connections.add(websocket)
    print("ESP32 Audio client connected")
    
    try:
        while True:
            try:
                # Use a timeout for the receive operation
                await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
            except asyncio.TimeoutError:
                # Connection is still alive, just no message received
                continue
            except websockets.exceptions.ConnectionClosed as e:
                print(f"ESP32 Audio client connection closed: {e.code} {e.reason}")
                break
            except Exception as e:
                print(f"Error in websocket connection: {e}")
                break
    finally:
        if websocket in active_audio_connections:
            active_audio_connections.remove(websocket)
        print("ESP32 Audio client disconnected")
        try:
            await websocket.close()
        except:
            pass

class AudioClient:
    def __init__(self):
        self.CHUNK = 960  # 40ms at 24kHz
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 24000  # Match OpenAI's sample rate
        self.p = pyaudio.PyAudio()
        self.running = True
        self.is_recording = False
        self.is_speaking = False
        self.audio_buffer = []  # Buffer to store audio segments
        self.segment_size = 480  # 20ms at 24kHz
        self.audio_buffer_length = 0
        self.animation_resolution = 0.1


        self.mouth_next_position = 0.0
        self.mouth_current_position = 0.0
        self.wing_next_position = 0.0
        self.wing_current_position = 0.0
        self.head_tilt_next_position = 0.0
        self.head_tilt_current_position = 0.0
        self.head_rotation_next_position = 0.0
        self.head_rotation_current_position = 0.0
        
        # Animation parameters
        self.last_idle_time = time.time()
        self.idle_interval = 1.0  # Even more frequent movements
        self.idle_variance = 0.8  # Less variance for more consistent movement
        self.energy_smoothing = 0.7
        self.last_energy = 0.0
        
        # Head movement state
        self.head_looking_left = True  # Track head direction for alternating looks
        self.head_movement_type = 'side'  # 'side' or 'tilt'
        
        # Initialize robot driver
        self.robot = BottangoDriver()  # Will use singleton instance
        self.robot.start_server_background()
        time.sleep(1)  # Give the server a moment to start
        
        # Find default input device
        self.input_device_index = self.get_default_input_device()
        
        # Initialize audio streams
        self.recording_stream = None
        self.current_audio_data = None
        self.audio_pos = 0
        
        # Audio playback state
        self.audio_queue = deque()  # Queue for pending audio chunks
        self.is_playing = False
        
        # Audio playback configuration
        if USE_WEBSOCKET_AUDIO:
            # Start audio websocket server
            self._start_audio_server()
            self.playback_stream = None
        else:
            # Create local playback stream with callback
            self.playback_stream = self.p.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                output=True,
                frames_per_buffer=self.CHUNK,
                stream_callback=self._audio_callback
            )
            self.playback_stream.start_stream()
        
        # Add new audio timing management
        self.audio_end_time = time.time()  # Track when current audio should finish
        self.audio_timing_task = None  # Task to manage speaking state

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
                # Don't send audio while the AI is speaking
                if self.is_speaking:
                    await asyncio.sleep(0.2)
                    continue
                
                # Read audio data
                audio_data = self.recording_stream.read(self.CHUNK, exception_on_overflow=False)
                if audio_data:
                    # Send raw audio to server as binary message
                    await self.ws.send(audio_data)
                    
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

    async def animation_loop(self):
        """Main animation loop with parrot-like head movements"""
        last_command_time = {}  # Track last command time for each type
        
        while self.running:
            current_time = time.time()
            
            # Handle idle animations when not speaking
            if not self.is_speaking:
                if current_time - self.last_idle_time > self.idle_interval + np.random.uniform(0, self.idle_variance):
                    # Alternate between side-to-side and up-down movements
                    if np.random.random() < 0.7:  # 70% chance of side-to-side movement
                        # Extreme side-to-side head rotation (parrot looking with alternate eyes)
                        self.head_looking_left = not self.head_looking_left
                        self.head_rotation_next_position = 0.9 if self.head_looking_left else 0.1
                        # Slight tilt when looking sideways
                        self.head_tilt_next_position = np.random.uniform(0.4, 0.6)
                        self.head_movement_type = 'side'
                    else:
                        # Occasional up-down movement
                        self.head_tilt_next_position = np.random.uniform(0.1, 0.9)  # More extreme tilt
                        # Center rotation during tilt
                        self.head_rotation_next_position = 0.5 + np.random.uniform(-0.1, 0.1)
                        self.head_movement_type = 'tilt'

                    # Wings move slightly with head movements
                    self.wing_next_position = np.random.uniform(0.2, 0.4)  # Subtle wing adjustments
                    
                    self.last_idle_time = current_time
                    self.idle_interval = 1.0 + np.random.uniform(-0.3, 0.3)  # Quick movements
                
                # Add micro-movements between major position changes
                elif self.head_movement_type == 'side' and np.random.random() < 0.1:  # 10% chance each frame
                    # Small adjustments to current position
                    current_rotation = self.head_rotation_current_position
                    self.head_rotation_next_position = current_rotation + np.random.uniform(-0.05, 0.05)
                    self.head_tilt_next_position = self.head_tilt_current_position + np.random.uniform(-0.05, 0.05)
            
            # Apply current positions with rate limiting
            current_time = time.time()
            
            if self.mouth_current_position != self.mouth_next_position:
                try:
                    await self.robot.set_mouth(self.mouth_next_position)
                    self.mouth_current_position = self.mouth_next_position
                    last_command_time['mouth'] = current_time
                except Exception as e:
                    print(f"Error sending mouth command: {e}")
                
            if self.wing_current_position != self.wing_next_position:
                try:
                    delta = self.wing_next_position - self.wing_current_position
                    self.wing_current_position += delta * 0.4
                    await self.robot.set_wing(self.wing_current_position)
                    last_command_time['wing'] = current_time
                except Exception as e:
                    print(f"Error sending wing command: {e}")
                
            if self.head_tilt_current_position != self.head_tilt_next_position:
                try:
                    delta = self.head_tilt_next_position - self.head_tilt_current_position
                    self.head_tilt_current_position += delta * 0.5
                    await self.robot.set_head_tilt(self.head_tilt_current_position)
                    last_command_time['head_tilt'] = current_time
                except Exception as e:
                    print(f"Error sending head tilt command: {e}")
                
            if self.head_rotation_current_position != self.head_rotation_next_position:
                try:
                    delta = self.head_rotation_next_position - self.head_rotation_current_position
                    self.head_rotation_current_position += delta * 0.5
                    await self.robot.set_head_rotation(self.head_rotation_current_position)
                    last_command_time['head_rotation'] = current_time
                except Exception as e:
                    print(f"Error sending head rotation command: {e}")
            
            await asyncio.sleep(self.animation_resolution)

    async def receive_audio(self):
        """Receive audio from OpenAI and handle playback"""
        print("Starting audio receive loop")
        
        while self.running:
            try:
                message = await self.ws.recv()
                if isinstance(message, str):
                    msg_data = json.loads(message)
                    msg_type = msg_data.get("type", "")
                    
                    if msg_type == "audio.animation":
                        self.is_speaking = True
                        audio_data = base64.b64decode(msg_data["audio"])
                        audio_length = len(audio_data)/self.RATE
                        print(f"Received {audio_length:.3f}s of audio")
                        
                        if USE_WEBSOCKET_AUDIO:
                            # Stream directly without creating a new task
                            await self.stream_to_speakers(audio_data)
                        else:
                            # Use local playback
                            if self.is_playing:
                                self.audio_queue.append(audio_data)
                            else:
                                self.current_audio_data = audio_data
                                self.audio_pos = 0
                                self.is_playing = True
                        
                        self.audio_buffer_length += audio_length
                        
            except Exception as e:
                print(f"\nError receiving audio: {e}")
                traceback.print_exc()
                self.is_speaking = False
                #await self.robot.set_mouth(1.0)
                break

    def cleanup(self):
        """Clean up resources"""
        self.running = False
        self.is_speaking = False
        
        if not USE_WEBSOCKET_AUDIO and self.playback_stream:
            self.playback_stream.stop_stream()
            self.playback_stream.close()
            
        self.p.terminate()
        
        # Reset mouth position
        if hasattr(self, 'robot'):
            self.robot.set_mouth(1.0)

    def _audio_callback(self, in_data, frame_count, time_info, status):
        """Callback for audio playback"""
        try:
            if self.current_audio_data is not None:
                self.is_speaking = True
                # Calculate remaining bytes
                remaining = len(self.current_audio_data) - self.audio_pos
                
                if remaining >= frame_count * 2:  # 2 bytes per sample
                    # Get next chunk of audio
                    output_data = self.current_audio_data[self.audio_pos:self.audio_pos + frame_count * 2]
                    self.audio_pos += frame_count * 2
                else:
                    # Handle end of data
                    output_data = self.current_audio_data[self.audio_pos:]
                    
                    # Check if there's more audio in the queue
                    if self.audio_queue:
                        self.current_audio_data = self.audio_queue.popleft()
                        additional_data_length = frame_count * 2 - len(output_data) 
                        if len(self.current_audio_data) > additional_data_length:
                            output_data += self.current_audio_data[:additional_data_length]
                            self.audio_pos = additional_data_length
                        else:
                            output_data += self.current_audio_data
                            self.audio_pos = 0
                        print(f"Starting next audio chunk ({len(self.current_audio_data)/self.RATE:.3f}s)")
                    else:
                        self.current_audio_data = None
                        self.audio_pos = 0
                        self.is_playing = False
                        self.is_speaking = False # problem is that this is set to false before the last bit of audio is played
                        print("Finished playing all audio")
                
                # Only calculate animations if we have valid output data
                if output_data and len(output_data) > 0:
                    self.calculate_animation_positions(output_data)

                # Pad with silence if needed
                output_data += b'\x00' * (frame_count * 2 - len(output_data)) # make sure we don't lose our callback loop. if we send back a frame shorter than the chunk size, we'll lose the callback loop

                return (output_data, pyaudio.paContinue)
            elif self.audio_queue:
                # Start playing next chunk from queue
                self.current_audio_data = self.audio_queue.popleft()
                self.audio_pos = 0
                self.is_playing = True
                print(f"Starting new audio chunk ({len(self.current_audio_data)/self.RATE:.3f}s)")
                return self._audio_callback(in_data, frame_count, time_info, status)
            else:
                # No data to play, return silence
                self.is_speaking = False
                return (b'\x00' * frame_count * 2, pyaudio.paContinue)
                
        except Exception as e:
            print(f"Error in audio callback: {e}")
            self.is_speaking = False
            return (b'\x00' * frame_count * 2, pyaudio.paContinue)

    def calculate_animation_positions(self, audio_data):
        """Calculate next positions for all animated components"""
        if not audio_data or len(audio_data) == 0:
            return
        
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
        amplitude = np.percentile(np.abs(audio_array), 80)
        
        # Mouth animation (keep existing behavior)
        self.mouth_next_position = np.random.uniform(0.0, 0.5) if amplitude > 800 else 1.0
        
        # Calculate energy level (0.0 to 1.0) with smoothing
        current_energy = min(1.0, amplitude / 2000)  # Increased sensitivity (was 4000)
        smoothed_energy = (current_energy * (1 - self.energy_smoothing) + 
                         self.last_energy * self.energy_smoothing)
        self.last_energy = smoothed_energy
        
        # Wings respond much more dramatically to energy
        wing_energy = smoothed_energy * 1.2  # Increased from 0.7 for more dramatic movement
        wing_base = 0.2  # Lower base position for more range
        wing_random = np.random.uniform(-0.1, 0.1)  # Add some randomness
        self.wing_next_position = wing_base + wing_energy * 0.8 + wing_random  # Increased range
        self.wing_next_position = max(0.0, min(1.0, self.wing_next_position))  # Clamp values
        
        # Head tilt responds more subtly (keep as is)
        tilt_energy = smoothed_energy * 0.3
        self.head_tilt_next_position = 0.4 + tilt_energy * 0.6
        
        # Head rotation stays relatively still during speech
        self.head_rotation_next_position = 0.5 + np.random.uniform(-0.1, 0.1)

    def _start_audio_server(self):
        """Start the audio websocket server in a background thread"""
        import uvicorn
        import threading
        
        def run_server():
            uvicorn.run(audio_app, host="0.0.0.0", port=AUDIO_WS_PORT)
            
        self.audio_server_thread = threading.Thread(target=run_server, daemon=True)
        self.audio_server_thread.start()
        time.sleep(1)  # Give server time to start

    async def manage_speaking_state(self):
        """Global task to manage speaking state based on audio timing"""
        while self.running:
            current_time = time.time()
            if current_time >= self.audio_end_time:
                if self.is_speaking:
                    print("Audio playback complete")
                    self.is_speaking = False
            await asyncio.sleep(0.1)  # Check every 100ms

    async def stream_to_speakers(self, audio_data):
        """Stream audio data to all connected ESP32 clients"""
        if not active_audio_connections:
            print("No ESP32 audio clients connected")
            return
            
        try:
            # Calculate audio duration and update end time
            audio_duration = len(audio_data) / (self.RATE * 2)
            self.audio_end_time += audio_duration
            print(f"Streaming {audio_duration:.3f}s of audio, will finish at {self.audio_end_time:.3f}")
            
            # Start the speaking state management task if needed
            if not self.audio_timing_task or self.audio_timing_task.done():
                self.audio_timing_task = asyncio.create_task(self.manage_speaking_state())
            
            self.is_speaking = True
            
            # Stream the audio data with rate limiting
            chunk_size = 512  # Smaller chunks
            delay = 0.002    # Slightly longer delay between chunks
            
            for i in range(0, len(audio_data), chunk_size):
                chunk = audio_data[i:i + chunk_size]
                
                # Get a snapshot of current connections
                clients = list(active_audio_connections)
                
                # Send to each client sequentially to avoid overwhelming the connection
                for client in clients:
                    try:
                        await client.send_bytes(chunk)
                    except Exception as e:
                        print(f"Error sending to client: {e}")
                        if client in active_audio_connections:
                            active_audio_connections.remove(client)
                
                # Rate limiting delay
                await asyncio.sleep(delay)
                
        except Exception as e:
            print(f"Error in stream_to_speakers: {e}")
            traceback.print_exc()

async def main():
    client = AudioClient()  # No need for async context manager
    try:
        animation_task = asyncio.create_task(client.animation_loop())
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
                
        # Cancel receive task when done
        receive_task.cancel()
        try:
            await receive_task
        except asyncio.CancelledError:
            pass
        
        animation_task.cancel()
        try:
            await animation_task
        except asyncio.CancelledError:
            pass
        
    except Exception as e:
        print(f"Error in main: {e}")
    finally:
        client.cleanup()

if __name__ == "__main__":
    asyncio.run(main()) 