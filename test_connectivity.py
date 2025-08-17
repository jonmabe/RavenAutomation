#!/usr/bin/env python3
"""
Connectivity test script for Parrot Server deployment
Tests WebSocket connections and basic server functionality
"""
import asyncio
import websockets
import argparse
import time
import json
import sys

class ConnectivityTester:
    def __init__(self, host, use_ssl=False):
        self.host = host
        self.protocol = "wss" if use_ssl else "ws"
        self.ports = {
            'audio': 8001,
            'microphone': 8002,
            'control': 8080
        }
        self.paths = {
            'audio': '/audio-stream',
            'microphone': '/microphone',
            'control': '/'
        }
    
    def get_url(self, service):
        """Generate WebSocket URL for a service"""
        port = self.ports[service]
        path = self.paths[service]
        return f"{self.protocol}://{self.host}:{port}{path}"
    
    async def test_connection(self, service, timeout=5):
        """Test connection to a specific service"""
        url = self.get_url(service)
        print(f"Testing {service} connection: {url}")
        
        try:
            # Use asyncio.wait_for for timeout control
            websocket = await asyncio.wait_for(
                websockets.connect(url), 
                timeout=timeout
            )
            
            print(f"✅ {service.upper()} - Connection successful")
            
            # Send a test ping if it's the control port
            if service == 'control':
                try:
                    await websocket.send("ping")
                    response = await asyncio.wait_for(websocket.recv(), timeout=2)
                    print(f"   📡 Ping response: {response}")
                except asyncio.TimeoutError:
                    print(f"   ⚠️  No ping response (normal for this server)")
            
            # For audio, send a test message
            elif service == 'audio':
                try:
                    await websocket.send("ping")
                    print(f"   📡 Audio WebSocket ready for streaming")
                except Exception as e:
                    print(f"   ⚠️  Audio test message failed: {e}")
            
            # For microphone, just confirm connection
            elif service == 'microphone':
                print(f"   🎤 Microphone WebSocket ready for audio input")
            
            await websocket.close()
            return True
                
        except ConnectionRefusedError:
            print(f"❌ {service.upper()} - Connection refused (server not running or port closed)")
            return False
        except OSError as e:
            if "Connection refused" in str(e):
                print(f"❌ {service.upper()} - Connection refused (server not running or port closed)")
            else:
                print(f"❌ {service.upper()} - Network error: {e}")
            return False
        except asyncio.TimeoutError:
            print(f"❌ {service.upper()} - Connection timeout")
            return False
        except Exception as e:
            print(f"❌ {service.upper()} - Connection failed: {e}")
            return False
    
    async def test_all(self):
        """Test all services"""
        print(f"🔍 Testing connectivity to Parrot Server at {self.host}")
        print("=" * 60)
        
        results = {}
        for service in ['control', 'audio', 'microphone']:
            results[service] = await self.test_connection(service)
            time.sleep(0.5)  # Brief pause between tests
        
        print("\n" + "=" * 60)
        print("📊 CONNECTIVITY SUMMARY")
        print("=" * 60)
        
        success_count = sum(results.values())
        total_count = len(results)
        
        for service, success in results.items():
            status = "✅ ONLINE" if success else "❌ OFFLINE"
            print(f"{service.upper():12} - {status}")
        
        print(f"\nOverall: {success_count}/{total_count} services accessible")
        
        if success_count == total_count:
            print("🎉 All services are online! ESP32 should be able to connect.")
        elif success_count > 0:
            print("⚠️  Some services are offline. Check server logs and port configuration.")
        else:
            print("🚨 No services accessible. Check server deployment and network connectivity.")
        
        return success_count == total_count

def main():
    parser = argparse.ArgumentParser(description='Test Parrot Server connectivity')
    parser.add_argument('host', help='Server hostname or IP address')
    parser.add_argument('--ssl', action='store_true', help='Use WSS (secure WebSocket) connections')
    parser.add_argument('--service', choices=['control', 'audio', 'microphone'], 
                       help='Test specific service only')
    
    args = parser.parse_args()
    
    tester = ConnectivityTester(args.host, args.ssl)
    
    async def run_tests():
        if args.service:
            success = await tester.test_connection(args.service)
            sys.exit(0 if success else 1)
        else:
            success = await tester.test_all()
            sys.exit(0 if success else 1)
    
    try:
        asyncio.run(run_tests())
    except KeyboardInterrupt:
        print("\n\n⏹️  Test cancelled by user")
        sys.exit(1)

if __name__ == "__main__":
    main()