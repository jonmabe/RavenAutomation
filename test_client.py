import asyncio
import websockets
import pyaudio
import numpy as np
import aioconsole
import traceback

class AudioClient:
    def __init__(self):
        self.CHUNK = 4800  # 200ms at 24kHz
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 24000
        self.p = pyaudio.PyAudio()
        self.running = True
        
        # Initialize playback stream
        self.playback_stream = self.p.open(
            format=self.FORMAT,
            channels=self.CHANNELS,
            rate=self.RATE,
            output=True,
            frames_per_buffer=self.CHUNK
        )

    async def connect_websocket(self):
        self.ws = await websockets.connect('ws://localhost:8000/proxy-openai')
        print("Connected to server")
        
    async def receive_audio(self):
        """Receive audio from server"""
        print("Starting audio receive loop")
        while self.running:
            try:
                message = await self.ws.recv()
                if isinstance(message, bytes):
                    print(f"\nReceived {len(message)} bytes of audio")
                    self.playback_stream.write(message)
                    print("Played audio chunk")
            except Exception as e:
                print(f"\nError receiving audio: {e}")
                traceback.print_exc()
                break

    def cleanup(self):
        """Clean up audio resources"""
        self.running = False
        if self.playback_stream:
            self.playback_stream.stop_stream()
            self.playback_stream.close()
        self.p.terminate()

async def main():
    client = AudioClient()
    
    try:
        await client.connect_websocket()
        receive_task = asyncio.create_task(client.receive_audio())
        
        print("Press 'q' to quit")
        
        while client.running:
            command = await aioconsole.ainput()
            if command.lower() == 'q':
                break
                
        client.cleanup()
        receive_task.cancel()
        try:
            await receive_task
        except asyncio.CancelledError:
            pass
        await client.ws.close()
        
    except Exception as e:
        print(f"Error in main: {e}")
    finally:
        client.cleanup()

if __name__ == "__main__":
    asyncio.run(main()) 