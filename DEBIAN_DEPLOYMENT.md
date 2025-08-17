# Direct Docker Deployment on Debian Server

Simple deployment guide for running the Parrot Server directly with Docker on your Debian server (192.168.1.172).

## Prerequisites

### 1. Clean Server Setup
After removing CapRover, ensure your server is clean:
```bash
# Remove any leftover CapRover containers
sudo docker stop $(sudo docker ps -aq) 2>/dev/null || true
sudo docker rm $(sudo docker ps -aq) 2>/dev/null || true

# Remove unused images (optional)
sudo docker system prune -a

# Free up ports
sudo netstat -tulpn | grep :8001
sudo netstat -tulpn | grep :8002
```

### 2. Install Docker (if needed)
```bash
sudo apt update
sudo apt install docker.io docker-compose git
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker $USER
newgrp docker  # Or logout/login
```

### 3. Verify Docker Installation
```bash
docker --version
docker ps  # Should work without sudo
```

## Deployment Steps

### 1. Clone Repository on Server
```bash
cd /opt
sudo git clone https://github.com/jonmabe/RavenAutomation.git parrot-server
sudo chown -R $USER:$USER /opt/parrot-server
cd /opt/parrot-server
```

### 2. Configure Environment
```bash
# Copy and edit environment file
cp .env.example .env
nano .env  # Add your OPENAI_API_KEY
```

### 3. Deploy with Script
```bash
chmod +x deploy.sh
./deploy.sh
```

The script will:
- ✅ Check Docker installation
- ✅ Stop any existing containers
- ✅ Build the Docker image
- ✅ Start the container with proper ports
- ✅ Show status and connection info

### 4. Verify Deployment
```bash
# Check container status
docker ps | grep parrot-server

# Test connectivity
python test_connectivity.py 192.168.1.172

# View logs
docker logs -f parrot-server
```

## Auto-Start Setup (Optional)

### 1. Install Systemd Service
```bash
sudo cp parrot-server.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable parrot-server.service
```

### 2. Test Service
```bash
sudo systemctl start parrot-server
sudo systemctl status parrot-server
```

## Manual Management

### Start/Stop Container
```bash
# Start
docker start parrot-server

# Stop  
docker stop parrot-server

# Restart
docker restart parrot-server

# View logs
docker logs -f parrot-server
```

### Update Deployment
```bash
cd /opt/parrot-server
git pull
./deploy.sh  # Rebuilds and redeploys
```

### Remove Deployment
```bash
docker stop parrot-server
docker rm parrot-server
docker rmi parrot-server
```

## Network Configuration

### Firewall (if enabled)
```bash
# Allow required ports
sudo ufw allow 8001/tcp
sudo ufw allow 8002/tcp
sudo ufw allow 8080/tcp

# Check status
sudo ufw status
```

### Port Verification
```bash
# Check if ports are listening
sudo netstat -tulpn | grep -E ':800[0-2]'

# Expected output:
# tcp6  0  0  :::8001  :::*  LISTEN  -/docker-proxy
# tcp6  0  0  :::8002  :::*  LISTEN  -/docker-proxy
# tcp6  0  0  :::8080  :::*  LISTEN  -/docker-proxy
```

## ESP32 Configuration

Your ESP32 code is already configured with IP `192.168.1.172`. After deployment:

### 1. Compile and Upload ESP32
```bash
# On your development machine
arduino-cli compile --fqbn esp32:esp32:esp32s3 ParrotDriver/
arduino-cli upload -p /dev/cu.usbmodem5A4E1311211 --fqbn esp32:esp32:esp32s3 ParrotDriver/
```

### 2. Monitor Connection
```bash
arduino-cli monitor -p /dev/cu.usbmodem5A4E1311211 -c baudrate=115200
```

You should see:
```
WiFi connected
IP address: [ESP32_IP]
Connecting to server at: 192.168.1.172:8001
Starting Audio WebSocket connection...
Audio WebSocket Connected
Starting Microphone WebSocket connection...
Microphone WebSocket Connected
```

## Troubleshooting

### Container Won't Start
```bash
# Check logs
docker logs parrot-server

# Common issues:
# - Missing .env file
# - Invalid OPENAI_API_KEY
# - Port conflicts
```

### ESP32 Can't Connect
```bash
# Test server connectivity
python test_connectivity.py 192.168.1.172

# Check server logs
docker logs -f parrot-server

# Verify ESP32 IP range can reach server
ping 192.168.1.172  # From ESP32 network
```

### Port Conflicts
```bash
# Find what's using ports
sudo lsof -i :8001
sudo lsof -i :8002

# Kill conflicting processes
sudo kill -9 [PID]
```

## Server URLs

After successful deployment:
- **Audio Stream**: `ws://192.168.1.172:8001/audio-stream`
- **Microphone**: `ws://192.168.1.172:8002/microphone`  
- **Control**: `ws://192.168.1.172:8080/`

Much simpler than CapRover! 🎉