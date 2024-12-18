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

@app.websocket("/proxy-openai")
async def proxy_openai(websocket: WebSocket):
    await websocket.accept()
    logger.info("Client connected")
    
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
                    "instructions": "You are a helpful AI assistant."
                }
            }))
            
            # Wait for session to be ready
            response = await openai_ws.recv()
            logger.info(f"Session setup response: {response}")
            
            # Send initial prompt
            await openai_ws.send(json.dumps({
                "type": "response.create"
            }))
            
            # Process responses
            while True:
                try:
                    response = await openai_ws.recv()
                    response_data = json.loads(response)
                    response_type = response_data.get("type", "")
                    logger.info(f"Got response type: {response_type}")
                    
                    if "audio.delta" in response_type:
                        audio_base64 = response_data.get("delta", "")
                        if audio_base64:
                            # Decode and process audio
                            raw_audio = base64.b64decode(audio_base64)
                            audio_array = np.frombuffer(raw_audio, dtype=np.int16)
                            audio_data = audio_array.astype('<i2').tobytes()
                            
                            # Send to client
                            await websocket.send_bytes(audio_data)
                            logger.info(f"Sent {len(audio_data)} bytes to client")
                    
                    elif response_type == "response.done":
                        logger.info("Response completed")
                        
                except Exception as e:
                    logger.error(f"Error processing response: {e}")
                    logger.error(traceback.format_exc())
                    break
            
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        logger.error(traceback.format_exc())
    finally:
        await websocket.close()
        logger.info("Connection closed")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 