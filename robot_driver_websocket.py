from fastapi import FastAPI, WebSocket
import uvicorn
from typing import Set
import asyncio
import threading
import time
app = FastAPI()

class BottangoDriver:
    _instance = None  # Singleton instance
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.active_connections: Set[WebSocket] = set()
            self._server_thread = None
            self._current_websocket = None
            self.initialized = True
            print("BottangoDriver initialized")
    
    def start_server_background(self):
        """Start the server in a background thread"""
        if self._server_thread is None:
            self._server_thread = threading.Thread(
                target=lambda: uvicorn.run(app, host="0.0.0.0", port=8080),
                daemon=True
            )
            self._server_thread.start()
            print("WebSocket server started in background")
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        self._current_websocket = websocket
        print(f"New client connected (id: {id(websocket)})")
        print(f"Active connections: {len(self.active_connections)}")
        print(f"Current websocket id: {id(self._current_websocket)}")
        
    def disconnect(self, websocket: WebSocket):
        print(f"Disconnecting client (id: {id(websocket)})")
        self.active_connections.remove(websocket)
        if self._current_websocket == websocket:
            self._current_websocket = None
        print(f"Client disconnected. Active connections: {len(self.active_connections)}")

    async def send_command(self, command: str):
        """Send a command to the current client"""
        if not self._current_websocket:
            #print("No active connection")
            #print(f"Active connections: {len(self.active_connections)}")
            if self.active_connections:
                #print("Setting new current websocket from active connections")
                self._current_websocket = next(iter(self.active_connections))
            else:
                return False
        
        try:
            #print(f"Sending command to websocket (id: {id(self._current_websocket)})")
            await self._current_websocket.send_text(command)
            return True
        except Exception as e:
            print(f"Error sending command: {e}")
            return False

    def set_mouth(self, position: float):
        """Sync wrapper for async set_mouth"""
        loop = asyncio.get_event_loop()
        return loop.create_task(self._set_mouth(position))
        
    async def _set_mouth(self, position: float):
        """Async implementation of set_mouth"""
        position = max(0.0, min(1.0, position))
        bottango_position = int(position * 8192)
        await self.send_command(f"sCI,27,{bottango_position}\n")

    def set_head_rotation(self, position: float):
        """Sync wrapper for async set_head_rotation"""
        loop = asyncio.get_event_loop()
        return loop.create_task(self._set_head_rotation(position))
        
    async def _set_head_rotation(self, position: float):
        position = max(0.0, min(1.0, position))
        bottango_position = int(position * 8192)
        await self.send_command(f"sCI,12,{bottango_position}\n")

    def set_head_tilt(self, position: float):
        """Sync wrapper for async set_head_tilt"""
        loop = asyncio.get_event_loop()
        return loop.create_task(self._set_head_tilt(position))
        
    async def _set_head_tilt(self, position: float):
        """Async implementation of set_head_tilt"""
        position = max(0.0, min(1.0, position))
        bottango_position = int(position * 8192)
        return await self.send_command(f"sCI,14,{bottango_position}\n")

    def set_wing(self, position: float):
        """Sync wrapper for async set_wing"""
        loop = asyncio.get_event_loop()
        return loop.create_task(self._set_wing(position))
        
    async def _set_wing(self, position: float):
        """Async implementation of set_wing"""
        position = max(0.0, min(1.0, position))
        bottango_position = int(position * 8192)
        await self.send_command(f"sCI,13,{bottango_position}\n")

    async def test_sequence(self):
        """Run a test sequence"""
        if self._current_websocket:
            print("Running test sequence...")
            self.set_head_rotation(0.0)
            time.sleep(1.5)
            self.set_head_rotation(0.5)
            time.sleep(1.5)
            self.set_head_rotation(1.0)
            time.sleep(1.5)
            self.set_head_rotation(0.0)
            time.sleep(1)

# Create the singleton instance
driver = BottangoDriver()

@app.websocket("/bottango")
async def websocket_endpoint(websocket: WebSocket):
    # Use the singleton instance
    global driver
    print(f"New connection request (id: {id(websocket)})")
    await driver.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            print(f"Received: {data}")
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        driver.disconnect(websocket)

# Add new test functionality at the end
async def run_standalone_test():
    """Run test sequence forever until interrupted"""
    test_driver = BottangoDriver()  # Will use singleton
    test_driver.start_server_background()
    print("Started server, waiting for connection...")
    
    try:
        while True:
            if test_driver._current_websocket:
                await test_driver.test_sequence()
            else:
                print("Waiting for client connection...")
                await asyncio.sleep(100)
    except KeyboardInterrupt:
        print("\nTest sequence interrupted")
    except Exception as e:
        print(f"Error in test sequence: {e}")

if __name__ == "__main__":
    print("Starting standalone test mode. Press Ctrl+C to stop.")
    asyncio.run(run_standalone_test())

