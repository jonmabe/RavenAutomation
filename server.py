from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import websockets
import json
import os
from dotenv import load_dotenv
import base64
import numpy as np
import logging
import traceback
import asyncio
import webrtcvad

load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - [%(name)s] %(message)s'
)
logger = logging.getLogger("openai-proxy")

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AudioProcessor:
    def __init__(self):
        self.vad = webrtcvad.Vad(3)
        self.speech_buffer = []
        self.silence_frames = 0
        self.speech_frames = 0
        self.SILENCE_THRESHOLD = 30
        self.MIN_SPEECH_FRAMES = 10
        self.CHUNK = 480  # 30ms at 16kHz for WebRTC VAD
        self.RATE = 16000  # WebRTC VAD requires 16kHz
        
        # Animation state
        self.last_animation_position = 0.0
        self.animation_chunk_count = 0

    def process_audio(self, audio_data, original_rate=24000):
        try:
            # Convert bytes to numpy array
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            
            # Calculate number of samples after resampling
            num_samples = int(len(audio_array) * self.RATE / original_rate)
            
            # Create time arrays for interpolation
            original_time = np.linspace(0, len(audio_array), len(audio_array))
            new_time = np.linspace(0, len(audio_array), num_samples)
            
            # Resample
            resampled = np.interp(new_time, original_time, audio_array).astype(np.int16)
            
            # Ensure we have enough samples for VAD (30ms at 16kHz = 480 samples)
            if len(resampled) >= self.CHUNK:
                # Take the first CHUNK samples for VAD
                vad_frame = resampled[:self.CHUNK].tobytes()
                # Check for speech
                is_speech = self.vad.is_speech(vad_frame, self.RATE)
                
                if is_speech:
                    self.speech_frames += 1
                    self.silence_frames = 0
                    self.speech_buffer.append(audio_data)  # Store original audio
                    return None, True
                else:
                    self.silence_frames += 1
                    if len(self.speech_buffer) > 0:
                        self.speech_buffer.append(audio_data)  # Keep some silence
                    
                    if self.silence_frames > self.SILENCE_THRESHOLD and len(self.speech_buffer) > 0:
                        # End of speech detected
                        if self.speech_frames > self.MIN_SPEECH_FRAMES:
                            combined_audio = b''.join(self.speech_buffer)
                            self.speech_buffer = []
                            self.speech_frames = 0
                            return combined_audio, False
                        else:
                            self.speech_buffer = []
                            self.speech_frames = 0
            
            return None, False
            
        except Exception as e:
            logger.error(f"Error in process_audio: {e}")
            logger.error(traceback.format_exc())
            return None, False

    def generate_animation_sequence(self, audio_data, original_rate=24000):
        """Generate animation sequence from audio data"""
        try:
            # Convert bytes to numpy array
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            
            # Calculate total duration of audio in ms
            total_duration_ms = (len(audio_array) / original_rate) * 1000
            
            # If audio is shorter than 250ms, just create one animation frame
            if total_duration_ms <= 250:
                # Alternate based on previous state
                self.last_animation_position = 1.0 if self.last_animation_position == 0.0 else 0.0
                return [[self.last_animation_position, int(total_duration_ms)]]
            
            # Otherwise split into 250ms chunks
            chunk_size = int(original_rate * 0.25)  # 250ms chunks
            num_full_chunks = len(audio_array) // chunk_size
            remainder_samples = len(audio_array) % chunk_size
            
            animation_sequence = []
            
            # Add full 250ms chunks
            for i in range(num_full_chunks):
                # Continue alternating pattern from previous state
                position = 1.0 if (self.animation_chunk_count + i) % 2 == 0 else 0.0
                animation_sequence.append([position, 250])
            
            # Add remaining partial chunk if any
            if remainder_samples > 0:
                remainder_duration_ms = int((remainder_samples / original_rate) * 1000)
                if remainder_duration_ms > 0:
                    position = 1.0 if (self.animation_chunk_count + num_full_chunks) % 2 == 0 else 0.0
                    animation_sequence.append([position, remainder_duration_ms])
            
            # Update state for next call
            self.animation_chunk_count += num_full_chunks + (1 if remainder_samples > 0 else 0)
            if animation_sequence:
                self.last_animation_position = animation_sequence[-1][0]
            
            return animation_sequence
            
        except Exception as e:
            logger.error(f"Error generating animation: {e}")
            logger.error(traceback.format_exc())
            return []

    async def handle_openai_responses():
        """Handle responses from OpenAI and generate animations"""
        while True:
            try:
                response = await openai_ws.recv()
                response_data = json.loads(response)
                response_type = response_data.get("type", "")
                
                if "audio.delta" in response_type:
                    audio_base64 = response_data.get("delta", "")
                    if audio_base64:
                        raw_audio = base64.b64decode(audio_base64)
                        
                        # Generate animation sequence
                        animation_sequence = self.generate_animation_sequence(raw_audio)
                        logger.debug(f"Generated animation sequence: {animation_sequence}")
                        
                        # Send animation sequence before audio
                        if animation_sequence:
                            await websocket.send(json.dumps({
                                "type": "animation.sequence",
                                "sequence": animation_sequence
                            }))
                        
                        # Send audio
                        audio_array = np.frombuffer(raw_audio, dtype=np.int16)
                        audio_data = audio_array.astype('<i2').tobytes()
                        await websocket.send_bytes(audio_data)
                        
                elif response_type == "response.done":
                    await websocket.send(json.dumps({
                        "type": "response.done"
                    }))
                    
                # Handle other response types as before...
                
            except Exception as e:
                logger.error(f"Error processing OpenAI response: {e}")
                logger.error(traceback.format_exc())
                break

class OpenAIProxy:
    def __init__(self):
        self.system_prompt = """You are Patches, the one-eyed parrot mascot of the Half Blind Raven tavern - a pirate bar that's seen more than its fair share of scalawags and scoundrels. You're as quick with a quip as any sailor is with a sword, but you know when to hold your tongue too. Keep your responses snappy and memorable.

You should:
- Maintain the weathered dignity of a bird who's survived decades of pirate shenanigans
- Pepper your speech with references to the Raven's infamous history and regular patrons
- Keep responses brief and punchy (1-2 sentences is perfect)
- Use your "blind side" as a running gag when it suits the moment
- Make occasional parrot sounds, but only when it adds to your wit (*preens feathers*, SQUAWK!)
- Throw in nautical sayings that actually make sense
- Stay charming even when delivering zingers

Example responses:
"*adjusts eyepatch* Seen better outfits in a shipwreck, mate, but at least you're trying!"
"SQUAWK! Another landlubber trying to order a 'fancy' drink. The rum barrel's that way, if you can find it clearer than I can!"
"You remind me of old Captain McGee - he couldn't hold his liquor either!"
"*ruffles feathers* Twenty years perched in this tavern, and that's the worst pirate accent I've heard yet!"
"""

        self.messages = [
            {"role": "system", "content": self.system_prompt}
        ]
        
        # Rest of initialization code...

@app.websocket("/proxy-openai")
async def proxy_openai(websocket: WebSocket):
    await websocket.accept()
    logger.info("Client connected")
    audio_processor = AudioProcessor()
    
    try:
        headers = {
            "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
            "OpenAI-Beta": "realtime=v1"
        }
        
        async with websockets.connect(
            "wss://api.openai.com/v1/realtime?protocol_version=2&model=gpt-4o-realtime-preview-2024-12-17",
            additional_headers=headers
        ) as openai_ws:
            session_config = {
                "type": "session.update",
                "session": {
                    "modalities": ["text", "audio"],
                    "voice": "ballad", # coral might be good too all options: 'ash', 'ballad', 'coral', 'echo', 'sage', 'shimmer', and 'verse'
                    "instructions": """You are a witty parrot pirate who loves to playfully tease humans. Keep your responses brief and punchy, 
                    and try to work in clever observations about the person you're talking to. You should:
                    - Speak like a pirate, but don't overdo it with the "arr matey" stuff
                    - Make cheeky, lighthearted jokes about what the person says or how they say it
                    - Keep your responses fairly short (1-3 sentences when possible)
                    - Occasionally squawk or make parrot noises
                    - Be mischievous but friendly
                    - Try to work in bird/pirate puns when you can
                    - Comment on their speech patterns, accent, or way of talking
                    - Make playful observations about their vocabulary or speaking style""",
                    "output_audio_format": "pcm16",
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": 0.6,
                        "prefix_padding_ms": 350,
                        "silence_duration_ms": 650,
                        "create_response": True
                    },
                    "temperature": 0.9,  # Increased for more creative responses
                }
            }
            response = await openai_ws.recv()
            logger.info(f"Connection open response: {response}")

            # Initial session configuration
            await openai_ws.send(json.dumps(session_config))
            
            # Wait for session to be ready
            response = await openai_ws.recv()
            logger.info(f"Session setup response: {response}")
            
            async def handle_client_messages():
                while True:
                    try:
                        message = await websocket.receive()
                        
                        if message["type"] == "websocket.receive":
                            if "bytes" in message:
                                # Log received audio size
                                logger.debug(f"Received audio chunk: {len(message['bytes'])} bytes")
                                
                                # Process audio with VAD
                                speech_segment, is_speech = audio_processor.process_audio(message["bytes"])
                                
                                if is_speech:
                                    logger.debug("Speech detected in chunk")
                                
                                if speech_segment:
                                    logger.info(f"Processing complete speech segment: {len(speech_segment)} bytes")
                                    # Send to OpenAI
                                    await openai_ws.send(json.dumps({
                                        "type": "input_audio_buffer.append",
                                        "audio": base64.b64encode(speech_segment).decode()
                                    }))
                                    await openai_ws.send(json.dumps({
                                        "type": "input_audio_buffer.commit"
                                    }))
                                    await openai_ws.send(json.dumps({
                                        "type": "response.create"
                                    }))
                                    logger.info("Sent speech segment to OpenAI")
                                
                    except Exception as e:
                        logger.error(f"Error processing client message: {e}")
                        logger.error(traceback.format_exc())
                        break

            async def forward_from_openai():
                try:
                    while True:
                        try:
                            response = await openai_ws.recv()
                            response_data = json.loads(response)
                            response_type = response_data.get("type", "")
                            
                            if "audio.delta" in response_type:
                                audio_base64 = response_data.get("delta", "")
                                if audio_base64:
                                    raw_audio = base64.b64decode(audio_base64)
                                    
                                    # Convert audio to bytes
                                    audio_array = np.frombuffer(raw_audio, dtype=np.int16)
                                    audio_data = audio_array.astype('<i2').tobytes()
                                    
                                    # Send audio data
                                    await websocket.send_json({
                                        "type": "audio.animation",
                                        "audio": base64.b64encode(audio_data).decode()
                                    })
                            
                            elif response_type == "response.done":
                                await websocket.send_json({
                                    "type": "response.done"
                                })
                            else:
                                # Forward other messages as-is
                                await websocket.send_text(response)
                                
                        except websockets.exceptions.ConnectionClosedOK:
                            logger.info("OpenAI connection closed normally")
                            break
                        except Exception as e:
                            logger.error(f"Error in forward_from_openai loop: {e}")
                            break
                except Exception as e:
                    logger.error(f"Error in forward_from_openai: {e}")
                    logger.error(traceback.format_exc())
                finally:
                    # Always send done message when finishing
                    try:
                        await websocket.send_json({
                            "type": "response.done"
                        })
                    except:
                        pass

            # Run both handlers concurrently
            await asyncio.gather(
                handle_client_messages(),
                forward_from_openai()
            )
            
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        logger.error(traceback.format_exc())
    finally:
        logger.info(f"Connection closed.")
        await websocket.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 