"""Factory for creating voice backend instances"""

from typing import Optional
from voice_backend import VoiceBackend
from openai_backend import OpenAIBackend
from vapi_backend import VAPIBackend
from config import VOICE_BACKEND, get_voice_backend_config


class VoiceBackendFactory:
    """Factory class for creating voice backend instances"""
    
    @staticmethod
    def create_backend(backend_type: Optional[str] = None) -> VoiceBackend:
        """
        Create a voice backend instance
        
        Args:
            backend_type: Type of backend ('openai' or 'vapi'). 
                         If None, uses config default
        
        Returns:
            VoiceBackend instance
        
        Raises:
            ValueError: If backend type is not supported
        """
        # Use config default if not specified
        if backend_type is None:
            backend_type = VOICE_BACKEND
        
        backend_type = backend_type.lower()
        config = get_voice_backend_config()
        
        if backend_type == 'openai':
            return OpenAIBackend(config)
        elif backend_type == 'vapi':
            return VAPIBackend(config)
        else:
            raise ValueError(f"Unsupported backend type: {backend_type}")
    
    @staticmethod
    def get_available_backends():
        """Get list of available backend types"""
        return ['openai', 'vapi']