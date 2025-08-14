"""Configuration for voice backends"""

import os
from dotenv import load_dotenv

load_dotenv()

# Voice backend selection: 'openai' or 'vapi'
VOICE_BACKEND = os.getenv('VOICE_BACKEND', 'openai').lower()

# OpenAI Configuration
OPENAI_CONFIG = {
    'api_key': os.getenv('OPENAI_API_KEY'),
    'voice': os.getenv('OPENAI_VOICE', 'ballad'),
    'model': os.getenv('OPENAI_MODEL', 'gpt-4o-realtime-preview-2024-12-17'),
    'instructions': """You are a pirate parrot named Polly. You are sarcastic, mischievous, and love treasure. 
Keep responses brief and parrot-like. You can use squawks and bird sounds. Always maintain your pirate persona.

You have the following commands available:
/whistle - Make a whistle sound
/squawk - Make a squawk sound
/flap - Flap wings animation
/headtilt - Tilt head animation
/preen - Preening animation

Use these naturally in conversation when appropriate.""",
    'tools': []
}

# VAPI Configuration
VAPI_CONFIG = {
    'api_key': os.getenv('VAPI_API_KEY'),
    'public_key': os.getenv('VAPI_PUBLIC_KEY'),
    'assistant_id': os.getenv('VAPI_ASSISTANT_ID'),
    # Optional: Override assistant settings
    'assistant_config': {
        'voice': {
            'provider': os.getenv('VAPI_VOICE_PROVIDER', 'elevenlabs'),
            'voice_id': os.getenv('VAPI_VOICE_ID'),
            'model': os.getenv('VAPI_VOICE_MODEL', 'eleven_turbo_v2')
        },
        'model': {
            'provider': os.getenv('VAPI_MODEL_PROVIDER', 'openai'),
            'model': os.getenv('VAPI_MODEL', 'gpt-4'),
            'temperature': float(os.getenv('VAPI_TEMPERATURE', '0.9'))
        },
        'transcriber': {
            'provider': os.getenv('VAPI_TRANSCRIBER_PROVIDER', 'deepgram'),
            'model': os.getenv('VAPI_TRANSCRIBER_MODEL', 'nova-2')
        }
    }
}

# Audio Configuration (shared by all backends)
AUDIO_CONFIG = {
    'sample_rate': 24000,
    'channels': 1,
    'chunk_size': 960,  # 40ms at 24kHz
    'format': 'pcm16'
}

def get_voice_backend_config():
    """Get configuration for the selected voice backend"""
    if VOICE_BACKEND == 'vapi':
        return VAPI_CONFIG
    else:
        return OPENAI_CONFIG