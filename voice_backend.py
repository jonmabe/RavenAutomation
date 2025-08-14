"""Voice backend abstraction layer for RavenAutomation"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Callable
import asyncio
import json


class VoiceBackend(ABC):
    """Abstract base class for voice backends"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.on_audio_callback: Optional[Callable] = None
        self.on_transcript_callback: Optional[Callable] = None
        self.on_error_callback: Optional[Callable] = None
        self.is_connected = False
    
    @abstractmethod
    async def connect(self):
        """Establish connection to the voice service"""
        pass
    
    @abstractmethod
    async def disconnect(self):
        """Close connection to the voice service"""
        pass
    
    @abstractmethod
    async def send_audio(self, audio_data: bytes):
        """Send audio data to the voice service"""
        pass
    
    @abstractmethod
    async def send_text(self, text: str):
        """Send text to the voice service"""
        pass
    
    @abstractmethod
    async def start_session(self):
        """Initialize a new conversation session"""
        pass
    
    @abstractmethod
    async def end_session(self):
        """End the current conversation session"""
        pass
    
    def set_audio_callback(self, callback: Callable):
        """Set callback for audio output"""
        self.on_audio_callback = callback
    
    def set_transcript_callback(self, callback: Callable):
        """Set callback for transcripts"""
        self.on_transcript_callback = callback
    
    def set_error_callback(self, callback: Callable):
        """Set callback for errors"""
        self.on_error_callback = callback