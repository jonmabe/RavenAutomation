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
            "wss://api.openai.com/v1/realtime?protocol_version=2&model=gpt-4o-realtime-preview-2024-10-01",
            additional_headers=headers
        ) as openai_ws:
            # Initial session configuration
            await openai_ws.send(json.dumps({
                "type": "session.update",
                "session": {
                    "voice": "alloy",
                    "instructions": """You are a helpful AI assistant. 
                        Maintain context throughout the conversation. 
                        Respond in the same language the user speaks to you in.
                        If the user hasn't spoken yet, use English.""",
                    "input_audio_transcription": {
                        "model": "whisper-1",
                        "language": "en"  # Default to English but Whisper will auto-detect
                    },
                    "output_audio_format": "pcm16",
                    "output_audio_rate": 24000,
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": 0.5,
                        "prefix_padding_ms": 300,
                        "silence_duration_ms": 600,
                        "create_response": True
                    },
                    "temperature": 0.7,  # Add temperature to make responses more consistent
                    "conversation_history_limit": 10  # Maintain conversation history
                }
            }))
            
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

            async def handle_openai_responses():
                while True:
                    try:
                        response = await openai_ws.recv()
                        response_data = json.loads(response)
                        response_type = response_data.get("type", "")
                        logger.info(f"Got response type: {response_type}")
                        
                        # Log transcript deltas to see what OpenAI is hearing
                        if "audio_transcript" in response_type:
                            delta = response_data.get("delta", "")
                            if delta:
                                logger.info(f"Transcript: {delta}")
                        
                        if "audio.delta" in response_type:
                            audio_base64 = response_data.get("delta", "")
                            if audio_base64:
                                raw_audio = base64.b64decode(audio_base64)
                                audio_array = np.frombuffer(raw_audio, dtype=np.int16)
                                audio_data = audio_array.astype('<i2').tobytes()
                                await websocket.send_bytes(audio_data)
                                logger.info(f"Sent {len(audio_data)} bytes to client")
                        
                        elif response_type == "input_audio_buffer.speech_started":
                            logger.info("Speech detected")
                        elif response_type == "input_audio_buffer.speech_stopped":
                            logger.info("Speech stopped")
                        elif response_type == "response.done":
                            logger.info("Response completed")
                            
                    except Exception as e:
                        logger.error(f"Error processing OpenAI response: {e}")
                        logger.error(traceback.format_exc())
                        break

            # Run both handlers concurrently
            await asyncio.gather(
                handle_client_messages(),
                handle_openai_responses()
            )
            
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        logger.error(traceback.format_exc())
    finally:
        logger.info(f"Connection closed. Processed {message_count} total messages")
        await websocket.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 