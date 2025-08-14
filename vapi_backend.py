"""VAPI.ai backend implementation"""

import asyncio
import websockets
import json
import base64
import aiohttp
from typing import Dict, Any, Optional
from voice_backend import VoiceBackend


class VAPIBackend(VoiceBackend):
    """VAPI.ai voice backend"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.ws = None
        self.api_key = config.get('api_key')
        self.assistant_id = config.get('assistant_id')
        self.public_key = config.get('public_key')
        self.base_url = "https://api.vapi.ai"
        self.call_id = None
        self.ws_url = None
    
    async def connect(self):
        """Connect to VAPI service"""
        # Create a call first to get WebSocket URL
        await self._create_call()
        
        if self.ws_url:
            self.ws = await websockets.connect(self.ws_url)
            self.is_connected = True
            
            # Start receiving messages
            asyncio.create_task(self._receive_messages())
    
    async def disconnect(self):
        """Disconnect from VAPI"""
        if self.ws:
            await self.ws.close()
            self.is_connected = False
        
        # End the call if active
        if self.call_id:
            await self._end_call()
    
    async def start_session(self):
        """Initialize VAPI session"""
        # Session is started when call is created
        # Send any initial configuration if needed
        if self.ws and self.is_connected:
            config_message = {
                "type": "session-config",
                "config": {
                    "audio_format": "pcm16",
                    "sample_rate": 24000,
                    "channels": 1
                }
            }
            await self.ws.send(json.dumps(config_message))
    
    async def end_session(self):
        """End VAPI session"""
        if self.call_id:
            await self._end_call()
    
    async def send_audio(self, audio_data: bytes):
        """Send audio to VAPI"""
        if not self.ws or not self.is_connected:
            return
        
        # VAPI expects raw PCM audio in binary frames
        await self.ws.send(audio_data)
    
    async def send_text(self, text: str):
        """Send text to VAPI"""
        if not self.ws or not self.is_connected:
            return
        
        message = {
            "type": "text",
            "text": text
        }
        
        await self.ws.send(json.dumps(message))
    
    async def _create_call(self):
        """Create a VAPI call to get WebSocket URL"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "assistant_id": self.assistant_id,
            "type": "web",
            "audio_format": "pcm16",
            "sample_rate": 24000
        }
        
        # Add custom assistant configuration if provided
        if 'assistant_config' in self.config:
            payload['assistant_overrides'] = self.config['assistant_config']
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/call",
                headers=headers,
                json=payload
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    self.call_id = data.get('id')
                    self.ws_url = data.get('websocket_url')
                else:
                    error = await response.text()
                    if self.on_error_callback:
                        await self.on_error_callback(f"Failed to create call: {error}")
    
    async def _end_call(self):
        """End the VAPI call"""
        if not self.call_id:
            return
        
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }
        
        async with aiohttp.ClientSession() as session:
            await session.delete(
                f"{self.base_url}/call/{self.call_id}",
                headers=headers
            )
        
        self.call_id = None
    
    async def _receive_messages(self):
        """Receive and process messages from VAPI"""
        try:
            async for message in self.ws:
                # VAPI sends both binary (audio) and text (JSON) frames
                if isinstance(message, bytes):
                    # Binary frame = audio data
                    if self.on_audio_callback:
                        await self.on_audio_callback(message)
                else:
                    # Text frame = JSON message
                    data = json.loads(message)
                    message_type = data.get("type")
                    
                    if message_type == "transcript":
                        role = data.get("role", "user")
                        text = data.get("transcript", "")
                        if self.on_transcript_callback:
                            await self.on_transcript_callback(role, text)
                    
                    elif message_type == "speech-update":
                        # Handle speech status updates
                        status = data.get("status")
                        if status == "started":
                            print("Assistant started speaking")
                        elif status == "stopped":
                            print("Assistant stopped speaking")
                    
                    elif message_type == "function-call":
                        # Handle function calls if implemented
                        function_name = data.get("function", {}).get("name")
                        arguments = data.get("function", {}).get("arguments")
                        print(f"Function call: {function_name} with args: {arguments}")
                    
                    elif message_type == "error":
                        if self.on_error_callback:
                            await self.on_error_callback(data.get("error", "Unknown error"))
        
        except websockets.exceptions.ConnectionClosed:
            self.is_connected = False
            if self.on_error_callback:
                await self.on_error_callback("WebSocket connection closed")
        except Exception as e:
            if self.on_error_callback:
                await self.on_error_callback(f"Error receiving messages: {e}")