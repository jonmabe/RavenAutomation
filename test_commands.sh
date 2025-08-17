#!/bin/bash

# Parrot Server Connectivity Test Commands
# Quick reference for testing your CapRover deployment

echo "🤖 Parrot Server Connectivity Test Commands"
echo "=========================================="
echo ""

# Server details
SERVER_IP="192.168.1.172"
SERVER_DOMAIN="parrot-server.your-domain.com"  # Replace with actual domain if available

echo "🖥️  Server IP: $SERVER_IP"
echo "🌐 Server Domain: $SERVER_DOMAIN"
echo ""

echo "📋 BASIC CONNECTIVITY TESTS"
echo "----------------------------"

echo "1️⃣  Test all services with IP:"
echo "   python3 test_connectivity.py $SERVER_IP"
echo ""

echo "2️⃣  Test all services with domain:"
echo "   python3 test_connectivity.py $SERVER_DOMAIN"
echo ""

echo "3️⃣  Test specific service (audio):"
echo "   python3 test_connectivity.py $SERVER_IP --service audio"
echo ""

echo "4️⃣  Test microphone endpoint:"
echo "   python3 test_mic.py"
echo ""

echo "📋 MANUAL PORT TESTS"
echo "--------------------"

echo "5️⃣  Test port connectivity with telnet:"
echo "   telnet $SERVER_IP 8080  # Control port"
echo "   telnet $SERVER_IP 8001  # Audio port"
echo "   telnet $SERVER_IP 8002  # Microphone port"
echo ""

echo "6️⃣  Test port connectivity with nc (netcat):"
echo "   nc -zv $SERVER_IP 8080 8001 8002"
echo ""

echo "📋 HTTP/WEBSOCKET TESTS"
echo "-----------------------"

echo "7️⃣  Test HTTP response (if server has HTTP endpoint):"
echo "   curl -v http://$SERVER_IP:8080/"
echo ""

echo "8️⃣  Test WebSocket with wscat (install: npm install -g wscat):"
echo "   wscat -c ws://$SERVER_IP:8080/"
echo "   wscat -c ws://$SERVER_IP:8001/audio-stream"
echo "   wscat -c ws://$SERVER_IP:8002/microphone"
echo ""

echo "📋 ESP32 DEPLOYMENT"
echo "-------------------"

echo "9️⃣  Compile ESP32 code:"
echo "   arduino-cli compile --fqbn esp32:esp32:esp32s3 ParrotDriver/"
echo ""

echo "🔟 Upload to ESP32:"
echo "   arduino-cli upload -p /dev/cu.usbmodem5A4E1311211 --fqbn esp32:esp32:esp32s3 ParrotDriver/"
echo ""

echo "1️⃣1️⃣  Monitor ESP32 serial output:"
echo "   arduino-cli monitor -p /dev/cu.usbmodem5A4E1311211 -c baudrate=115200"
echo ""

echo "📋 DOCKER/CAPROVER STATUS"
echo "------------------------"

echo "1️⃣2️⃣  Check if Docker container is running:"
echo "   docker ps | grep parrot"
echo ""

echo "1️⃣3️⃣  Check Docker container logs:"
echo "   docker logs parrot-server-container-name"
echo ""

echo "1️⃣4️⃣  Test local Docker deployment:"
echo "   docker-compose up --build"
echo ""

echo "📋 NETWORK DIAGNOSTICS"
echo "----------------------"

echo "1️⃣5️⃣  Ping server:"
echo "   ping $SERVER_IP"
echo ""

echo "1️⃣6️⃣  Check network route:"
echo "   traceroute $SERVER_IP"
echo ""

echo "1️⃣7️⃣  Scan open ports:"
echo "   nmap -p 8080,8001,8002 $SERVER_IP"
echo ""

echo ""
echo "💡 QUICK START:"
echo "   1. Run: python3 test_connectivity.py $SERVER_IP"
echo "   2. If all green, upload ESP32 code"
echo "   3. Monitor ESP32 serial for connection status"
echo ""