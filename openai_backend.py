"""OpenAI Realtime API backend implementation"""

import asyncio
import websockets
import json
import base64
from typing import Dict, Any
from voice_backend import VoiceBackend


class OpenAIBackend(VoiceBackend):
    """OpenAI Realtime API voice backend"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.ws = None
        self.api_key = config.get('api_key')
        self.voice = config.get('voice', 'ballad')
        self.model = config.get('model', 'gpt-4o-realtime-preview-2024-12-17')
        self.instructions = config.get('instructions', '')
        self.ws_url = f"wss://api.openai.com/v1/realtime?protocol_version=2&model={self.model}"
    
    async def connect(self):
        """Connect to OpenAI Realtime API"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "OpenAI-Beta": "realtime=v1"
        }
        
        self.ws = await websockets.connect(self.ws_url, additional_headers=headers)
        self.is_connected = True
        
        # Start receiving messages
        asyncio.create_task(self._receive_messages())
    
    async def disconnect(self):
        """Disconnect from OpenAI"""
        if self.ws:
            await self.ws.close()
            self.is_connected = False
    
    async def start_session(self):
        """Initialize OpenAI session with configuration"""
        session_config = {
            "event_type": "session",
            "session": {
                "instructions": self.instructions,
                "tools": self.config.get('tools', []),
                "voice": self.voice,
                "disable_audio": False,
                "detect_silence": False,
                "modalities": ["text", "audio"],
                "output_audio_format": "pcm16",
                "input_audio_format": "pcm16",
                "input_audio_transcription": {
                    "enabled": True,
                    "model": "whisper-1"
                },
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.5,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 500
                },
                "temperature": 0.9,
                "max_response_output_tokens": 4096
            }
        }
        
        await self.ws.send(json.dumps(session_config))
        print(f"[OpenAI] Session configured with audio enabled: {not session_config['session']['disable_audio']}")
        print(f"[OpenAI] Audio format: {session_config['session']['output_audio_format']}")
    
    async def end_session(self):
        """End OpenAI session"""
        # OpenAI doesn't require explicit session end
        pass
    
    async def send_audio(self, audio_data: bytes):
        """Send audio to OpenAI"""
        if not self.ws or not self.is_connected:
            return
        
        # Convert to base64 for OpenAI API
        base64_audio = base64.b64encode(audio_data).decode('utf-8')
        
        message = {
            "event_type": "audio",
            "audio": base64_audio
        }
        
        await self.ws.send(json.dumps(message))
    
    async def send_text(self, text: str):
        """Send text to OpenAI"""
        if not self.ws or not self.is_connected:
            return
        
        message = {
            "event_type": "message",
            "message": {
                "role": "user",
                "content": text
            }
        }
        
        await self.ws.send(json.dumps(message))
    
    async def _receive_messages(self):
        """Receive and process messages from OpenAI"""
        try:
            async for message in self.ws:
                data = json.loads(message)
                event_type = data.get("event_type")
                
                if event_type == "audio.delta":
                    # Decode audio data
                    audio_chunk = base64.b64decode(data["audio"]["data"])
                    print(f"[OpenAI] Received audio.delta event: {len(audio_chunk)} bytes")
                    if self.on_audio_callback:
                        await self.on_audio_callback(audio_chunk)
                
                elif event_type == "message" and data.get("message", {}).get("role") == "assistant":
                    # Handle text messages
                    content = data["message"].get("content", "")
                    if content and self.on_transcript_callback:
                        await self.on_transcript_callback("assistant", content)
                
                elif event_type == "message" and data.get("message", {}).get("role") == "user":
                    # Handle user transcripts
                    content = data["message"].get("content", "")
                    if content and self.on_transcript_callback:
                        await self.on_transcript_callback("user", content)
                
                elif event_type == "error":
                    print(f"[OpenAI] Error event: {data.get('error', 'Unknown error')}")
                    if self.on_error_callback:
                        await self.on_error_callback(data.get("error", "Unknown error"))
                
                elif event_type:
                    # Log other events for debugging
                    print(f"[OpenAI] Event: {event_type}")
        
        except websockets.exceptions.ConnectionClosed:
            self.is_connected = False
            if self.on_error_callback:
                await self.on_error_callback("WebSocket connection closed")
        except Exception as e:
            if self.on_error_callback:
                await self.on_error_callback(f"Error receiving messages: {e}")