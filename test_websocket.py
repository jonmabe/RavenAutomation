import pytest
import asyncio
from fastapi.testclient import TestClient
from server import app, WebSocketDebugger

@pytest.mark.asyncio
async def test_websocket_connection():
    async with TestClient(app).websocket_connect("/proxy-openai") as websocket:
        assert await websocket.receive_text() == "Connected"

@pytest.mark.asyncio
async def test_audio_processing():
    debugger = WebSocketDebugger()
    
    # Create test audio data (1 second of silence)
    test_audio = bytes(48000)  # 24000 samples * 2 bytes
    
    async with TestClient(app).websocket_connect("/proxy-openai") as websocket:
        await websocket.send_bytes(test_audio)
        
        # Wait for processing
        await asyncio.sleep(0.1)
        
        # Check debugger stats
        stats = debugger.get_message_stats()
        assert stats['incoming_bytes'] > 0
        assert stats['error_count'] == 0

@pytest.mark.asyncio
async def test_invalid_data():
    debugger = WebSocketDebugger()
    
    async with TestClient(app).websocket_connect("/proxy-openai") as websocket:
        # Send invalid data
        await websocket.send_text("invalid data")
        
        # Wait for processing
        await asyncio.sleep(0.1)
        
        # Check debugger stats
        stats = debugger.get_message_stats()
        assert stats['error_count'] > 0 