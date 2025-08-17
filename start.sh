#!/bin/bash

# Container startup script for Parrot Server

echo "Starting Parrot Server..."
echo "Environment: $VOICE_BACKEND backend"

# Check if required environment variables are set
if [ "$VOICE_BACKEND" = "openai" ]; then
    if [ -z "$OPENAI_API_KEY" ]; then
        echo "Error: OPENAI_API_KEY environment variable is required for OpenAI backend"
        exit 1
    fi
    echo "Using OpenAI backend with voice: ${OPENAI_VOICE:-ballad}"
elif [ "$VOICE_BACKEND" = "vapi" ]; then
    if [ -z "$VAPI_API_KEY" ] || [ -z "$VAPI_PUBLIC_KEY" ] || [ -z "$VAPI_ASSISTANT_ID" ]; then
        echo "Error: VAPI_API_KEY, VAPI_PUBLIC_KEY, and VAPI_ASSISTANT_ID are required for VAPI backend"
        exit 1
    fi
    echo "Using VAPI backend with assistant: $VAPI_ASSISTANT_ID"
else
    echo "Warning: Unknown VOICE_BACKEND '$VOICE_BACKEND', defaulting to OpenAI"
fi

# Create recordings directory if it doesn't exist
mkdir -p /app/mic_recordings

# Start the parrot server
exec python parrot_server.py "$@"