# VAPI.ai Setup Guide

This guide explains how to set up VAPI.ai as the voice backend for RavenAutomation.

## Overview

VAPI.ai provides a managed voice AI platform that abstracts away the complexities of:
- Speech-to-text (transcription)
- Language models (AI intelligence)
- Text-to-speech (voice synthesis)

## Setup Steps

### 1. Create VAPI Account

1. Sign up at [vapi.ai](https://vapi.ai)
2. Navigate to your dashboard

### 2. Get API Keys

1. Go to Settings → API Keys
2. Copy your:
   - Private API Key (for server-side use)
   - Public API Key (if using web SDK)

### 3. Create an Assistant

1. Go to Assistants → Create New
2. Configure your assistant with:

```json
{
  "name": "Pirate Parrot",
  "firstMessage": "Ahoy there, matey! Polly wants a cracker!",
  "systemPrompt": "You are a pirate parrot named Polly. You are sarcastic, mischievous, and love treasure. Keep responses brief and parrot-like. You can use squawks and bird sounds. Always maintain your pirate persona.",
  "voice": {
    "provider": "elevenlabs",
    "voiceId": "your_voice_id",
    "model": "eleven_turbo_v2"
  },
  "model": {
    "provider": "openai",
    "model": "gpt-4",
    "temperature": 0.9
  },
  "transcriber": {
    "provider": "deepgram",
    "model": "nova-2"
  }
}
```

3. Save the assistant and copy the Assistant ID

### 4. Configure Environment

Update your `.env` file:

```bash
# Set VAPI as the backend
VOICE_BACKEND=vapi

# VAPI credentials
VAPI_API_KEY=your_private_api_key
VAPI_ASSISTANT_ID=your_assistant_id

# Optional: Override assistant settings
VAPI_VOICE_PROVIDER=elevenlabs
VAPI_VOICE_ID=your_voice_id
```

### 5. Install Dependencies

```bash
pip install -r requirements.txt
```

### 6. Run the Server

```bash
python parrot_server.py
```

## Voice Options

VAPI supports multiple voice providers:

### ElevenLabs
- High-quality, natural voices
- Low latency with turbo models
- Custom voice cloning available

### OpenAI
- Voices: alloy, echo, fable, onyx, nova, shimmer
- Good for consistent, clear speech

### PlayHT
- Ultra-realistic voices
- Good emotion control

### Deepgram
- Fast, affordable option
- Good for high-volume applications

## Features

### Tools/Functions
You can add custom tools to your VAPI assistant:

```json
{
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "squawk",
        "description": "Make a squawk sound",
        "parameters": {}
      }
    },
    {
      "type": "function", 
      "function": {
        "name": "flap_wings",
        "description": "Flap the parrot's wings",
        "parameters": {}
      }
    }
  ]
}
```

### Server URL
Configure a webhook to receive real-time events:
- Transcripts
- Function calls
- Call status updates

## Troubleshooting

### Connection Issues
- Verify API keys are correct
- Check network connectivity
- Ensure assistant ID is valid

### Audio Quality
- VAPI handles audio format conversion automatically
- Ensure your microphone provides clear input
- Check speaker/headphone connections

### Latency
- Choose voice providers with low latency (ElevenLabs Turbo, Deepgram)
- Use geographically closer servers if available
- Consider using VAPI's edge locations

## Cost Considerations

VAPI pricing includes:
- Per-minute charges for voice calls
- Additional costs for premium voices
- Transcription and model costs

Monitor usage in the VAPI dashboard to track costs.