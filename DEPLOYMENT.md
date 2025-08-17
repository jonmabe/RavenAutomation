# Parrot Server Docker Deployment

This guide covers deploying the Python parrot server using Docker and CapRover.

## Prerequisites

- Docker installed
- CapRover instance running (for production deployment)
- API keys configured (OpenAI or VAPI)

## Local Development with Docker

### 1. Environment Setup

Copy the environment template:
```bash
cp .env.example .env
```

Edit `.env` with your API keys and configuration.

### 2. Build and Run with Docker Compose

```bash
# Build and start the container
docker-compose up --build

# Run in background
docker-compose up -d --build

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

The server will be available on:
- Control WebSocket: `ws://localhost:8080`
- Audio Stream: `ws://localhost:8001/audio-stream`
- Microphone: `ws://localhost:8002/microphone`

## CapRover Deployment

### 1. Prepare Repository

Ensure these files are in your repository root:
- `Dockerfile`
- `captain-definition`
- `requirements.txt`
- All Python source files

### 2. Deploy to CapRover

#### Option A: Git Repository Deployment
1. In CapRover dashboard, create a new app
2. Choose "Deploy from GitHub/Bitbucket/GitLab"
3. Connect your repository
4. CapRover will automatically use the `captain-definition` file

#### Option B: Tar File Upload
1. Create a deployment tar file:
   ```bash
   tar --exclude='.git' --exclude='venv' --exclude='__pycache__' \
       --exclude='*.pyc' --exclude='.DS_Store' \
       -czf parrot-server.tar.gz .
   ```
2. Upload the tar file in CapRover dashboard

### 3. Configure Environment Variables

In CapRover app settings, add environment variables:
- `OPENAI_API_KEY`: Your OpenAI API key
- `VOICE_BACKEND`: `openai` or `vapi`
- `OPENAI_VOICE`: Voice model (default: `ballad`)
- Other variables as needed (see `.env.example`)

### 4. Configure Ports

Ensure these ports are exposed in CapRover:
- `8080`: Control WebSocket
- `8001`: Audio Stream WebSocket
- `8002`: Microphone WebSocket

### 5. Enable HTTPS (Optional)

For production, enable HTTPS in CapRover for secure WebSocket connections.

## ESP32 Configuration

Update your ESP32 code to connect to your deployed server:

```cpp
// Update server IP in ParrotDriver.ino
const char* server_ip = "your-caprover-domain.com";  // or IP address
const int control_port = 8080;
const int audio_port = 8001;
const int mic_port = 8002;
```

If using HTTPS, update WebSocket URLs to use `wss://` instead of `ws://`.

## Troubleshooting

### Container Won't Start
- Check logs: `docker-compose logs`
- Verify environment variables are set
- Ensure API keys are valid

### ESP32 Can't Connect
- Verify server is running and accessible
- Check firewall settings
- Test WebSocket endpoints with a WebSocket client

### Audio Issues
- Ensure PyAudio dependencies are installed (handled in Dockerfile)
- Check if container has proper audio permissions (if using local audio)

### CapRover Deployment Issues
- Verify `captain-definition` file is in repository root
- Check CapRover build logs for errors
- Ensure all required files are included in deployment

## Monitoring

### View Logs
```bash
# Docker Compose
docker-compose logs -f parrot-server

# CapRover
# Use the CapRover dashboard logs viewer
```

### Health Check
Test the server is running by connecting to WebSocket endpoints:
```bash
# Test control port
wscat -c ws://your-server:8080

# Test audio stream
wscat -c ws://your-server:8001/audio-stream

# Test microphone
wscat -c ws://your-server:8002/microphone
```

## Scaling

For high availability:
1. Use CapRover's multiple instances feature
2. Configure a load balancer for WebSocket connections
3. Consider using external storage for recordings (if enabled)