import asyncio
import websockets
import pyaudio
import numpy as np

async def test_audio():
    # Setup audio playback
    p = pyaudio.PyAudio()
    stream = p.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=24000,
        output=True,
        frames_per_buffer=4800
    )
    
    try:
        async with websockets.connect('ws://localhost:8000/test-audio') as ws:
            print("Connected to test endpoint")
            
            while True:
                try:
                    message = await ws.recv()
                    if isinstance(message, bytes):
                        print(f"Received {len(message)} bytes of audio")
                        stream.write(message)
                        print("Played audio chunk")
                except websockets.exceptions.ConnectionClosed:
                    print("Connection closed")
                    break
                except Exception as e:
                    print(f"Error: {e}")
                    break
                    
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()

if __name__ == "__main__":
    asyncio.run(test_audio()) 