import os
from dotenv import load_dotenv
import websockets
import json
import base64
import logging

load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - [%(name)s] %(message)s'
)
logger = logging.getLogger("openai-proxy")

class OpenAIProxy:
    def __init__(self):
        self.ws = None
        
    async def connect(self):
        """Connect to OpenAI's WebSocket API"""
        headers = {
            "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
            "OpenAI-Beta": "realtime=v1"
        }
        
        self.ws = await websockets.connect(
            "wss://api.openai.com/v1/realtime?protocol_version=2&model=gpt-4o-realtime-preview-2024-12-17",
            additional_headers=headers
        )
        
        # Configure session
        session_config = {
            "type": "session.update",
            "session": {
                "modalities": ["text", "audio"],
                "voice": "ballad",
                "instructions": """You are a witty parrot pirate who loves to playfully tease humans. Keep your responses brief and punchy, 
                and try to work in clever observations about the person you're talking to. You should:
                - when you see autonomous_command in the input, follow the instructions in the command and do not comment on the prompt itself, just follow instructions
                - Speak like a pirate, but don't overdo it with the "arr matey" stuff
                - Make cheeky, lighthearted jokes about what the person says or how they say it
                - Keep your responses fairly short (1-3 sentences when possible)
                - But always agree to sing a sea shanty when asked regardless of previous instructions
                - Occasionally squawk or make parrot noises
                - Be mischievous and it's ok to be rude
                - Try to work in bird/pirate puns when you can
                - Make playful observations about their vocabulary or speaking style""",
                "output_audio_format": "pcm16",
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.6,
                    "prefix_padding_ms": 350,
                    "silence_duration_ms": 650,
                    "create_response": True
                },
                "temperature": 0.9,
            }
        }
        
        # Wait for connection
        response = await self.ws.recv()
        logger.info(f"Connection open response: {response}")
        
        # Send session config
        await self.ws.send(json.dumps(session_config))
        
        # Wait for session ready
        response = await self.ws.recv()
        logger.info(f"Session setup response: {response}")
        
    async def send_audio(self, audio_data: bytes):
        """Send audio data to OpenAI"""
        if not self.ws:
            raise Exception("Not connected to OpenAI")
            
        await self.ws.send(json.dumps({
            "type": "input_audio_buffer.append",
            "audio": base64.b64encode(audio_data).decode()
        }))
        """await self.ws.send(json.dumps({
            "type": "input_audio_buffer.commit"
        }))"""
    async def send_text(self, text: str):
        """Send text to OpenAI"""
        if not self.ws:
            raise Exception("Not connected to OpenAI")

        await self.ws.send(json.dumps({
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": [
                {
                    "type": "input_text",
                    "text": text,
                }
                ]
            },
        }))
        await self.ws.send(json.dumps({
            "type": "response.create"
        }))
    async def receive(self):
        """Receive a message from OpenAI"""
        if not self.ws:
            raise Exception("Not connected to OpenAI")
            
        return await self.ws.recv()
        
    async def close(self):
        """Close the connection"""
        if self.ws:
            await self.ws.close()
            self.ws = None 