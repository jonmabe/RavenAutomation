from fastapi import FastAPI, WebSocket
import wave
import struct
import asyncio
from pathlib import Path

app = FastAPI()

class AudioStreamer:
    def __init__(self):
        self.active_connections = set()
        self.wav_file = "CantinaBand60.wav"  # Default audio file
        self.is_streaming = False
        self.stream_task = None
        
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        
        # Start streaming if not already streaming
        if not self.is_streaming:
            self.is_streaming = True
            self.stream_task = asyncio.create_task(self.stream_wav(self.wav_file))
        
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        if not self.active_connections and self.stream_task:
            self.is_streaming = False
            self.stream_task.cancel()
        
    async def stream_wav(self, wav_file_path: str, chunk_size: int = 1024):
        try:
            wav_path = Path(wav_file_path)
            if not wav_path.exists():
                raise FileNotFoundError(f"WAV file not found: {wav_file_path}")
                
            while self.is_streaming:  # Loop continuously while streaming
                with wave.open(wav_file_path, 'rb') as wav_file:
                    print(f"Starting stream of {wav_file_path}")
                    # Send configuration first
                    config_data = struct.pack('<BBL', 
                        wav_file.getnchannels(),
                        wav_file.getsampwidth(),
                        wav_file.getframerate()
                    )
                    
                    for connection in self.active_connections:
                        try:
                            await connection.send_bytes(config_data)
                        except Exception as e:
                            print(f"Error sending config: {e}")
                            continue
                    
                    # Stream audio data
                    while self.is_streaming:
                        data = wav_file.readframes(chunk_size)
                        if not data:
                            wav_file.rewind()  # Loop back to start
                            continue
                            
                        for connection in self.active_connections:
                            try:
                                await connection.send_bytes(data)
                            except Exception as e:
                                print(f"Error sending audio data: {e}")
                                continue
                            
                        await asyncio.sleep(0.01)  # Prevent overwhelming the network
                        
        except Exception as e:
            print(f"Streaming error: {e}")
        finally:
            self.is_streaming = False

streamer = AudioStreamer()

@app.websocket("/audio-stream")
async def websocket_endpoint(websocket: WebSocket):
    print("New client connecting...")
    await streamer.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # Keep connection alive
    except Exception as e:
        print(f"Client disconnected: {e}")
    finally:
        streamer.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    import sys
    
    # Allow wav file to be specified as command line argument
    if len(sys.argv) > 1:
        streamer.wav_file = sys.argv[1]
    
    print(f"Starting server, will stream: {streamer.wav_file}")
    uvicorn.run(app, host="0.0.0.0", port=8001)