#!/bin/bash

# Parrot Server - Direct Docker Deployment Script
# For Debian/Ubuntu servers

set -e  # Exit on any error

echo "🤖 Parrot Server Docker Deployment"
echo "=================================="

# Configuration
CONTAINER_NAME="parrot-server"
IMAGE_NAME="parrot-server"
HOST_IP="192.168.1.172"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if we're on the server
if [ "$(hostname -I | grep -o '192.168.1.172')" != "192.168.1.172" ]; then
    log_warning "This script should be run on the server (192.168.1.172)"
    log_info "Current IP: $(hostname -I)"
    read -p "Continue anyway? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    log_error "Docker is not installed. Please install Docker first:"
    echo "  sudo apt update"
    echo "  sudo apt install docker.io docker-compose"
    echo "  sudo systemctl enable docker"
    echo "  sudo systemctl start docker"
    echo "  sudo usermod -aG docker \$USER"
    echo "  newgrp docker"
    exit 1
fi

# Check if running as root or in docker group
if [ "$EUID" -ne 0 ] && ! groups | grep -q docker; then
    log_error "You need to be root or in the docker group"
    echo "Run: sudo usermod -aG docker \$USER && newgrp docker"
    exit 1
fi

log_info "Checking Docker installation..."
docker --version
log_success "Docker is available"

# Stop and remove existing container if it exists
if docker ps -a | grep -q $CONTAINER_NAME; then
    log_info "Stopping existing container..."
    docker stop $CONTAINER_NAME || true
    docker rm $CONTAINER_NAME || true
    log_success "Removed existing container"
fi

# Remove existing image if it exists
if docker images | grep -q $IMAGE_NAME; then
    log_info "Removing existing image..."
    docker rmi $IMAGE_NAME || true
fi

# Check if .env file exists
if [ ! -f .env ]; then
    log_warning ".env file not found. Creating template..."
    cat > .env << EOF
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_VOICE=ballad
OPENAI_MODEL=gpt-4o-realtime-preview-2024-12-17
VOICE_BACKEND=openai

# Optional VAPI Configuration
VAPI_API_KEY=
VAPI_PUBLIC_KEY=
VAPI_ASSISTANT_ID=
EOF
    log_error "Please edit .env file with your API keys before continuing"
    exit 1
fi

# Check if OPENAI_API_KEY is set
if grep -q "your_openai_api_key_here" .env; then
    log_error "Please set your OPENAI_API_KEY in the .env file"
    exit 1
fi

log_info "Building Docker image..."
docker build -t $IMAGE_NAME .
log_success "Docker image built successfully"

log_info "Starting container..."
docker run -d \
    --name $CONTAINER_NAME \
    --restart unless-stopped \
    -p 8001:8001 \
    -p 8002:8002 \
    -p 8080:8080 \
    --env-file .env \
    $IMAGE_NAME

log_success "Container started successfully"

# Wait a moment for container to start
sleep 3

# Check container status
if docker ps | grep -q $CONTAINER_NAME; then
    log_success "Container is running!"
    
    echo ""
    echo "📊 Container Status:"
    docker ps | grep $CONTAINER_NAME
    
    echo ""
    echo "🔍 Container Logs (last 20 lines):"
    docker logs --tail 20 $CONTAINER_NAME
    
    echo ""
    echo "🌐 Server URLs:"
    echo "   Audio Stream:  ws://$HOST_IP:8001/audio-stream"
    echo "   Microphone:    ws://$HOST_IP:8002/microphone"
    echo "   Control:       ws://$HOST_IP:8080/"
    
    echo ""
    echo "🧪 Test connectivity:"
    echo "   python test_connectivity.py $HOST_IP"
    
    echo ""
    echo "📝 Useful commands:"
    echo "   View logs:     docker logs -f $CONTAINER_NAME"
    echo "   Stop server:   docker stop $CONTAINER_NAME"
    echo "   Start server:  docker start $CONTAINER_NAME"
    echo "   Restart:       docker restart $CONTAINER_NAME"
    echo "   Remove:        docker stop $CONTAINER_NAME && docker rm $CONTAINER_NAME"
    
else
    log_error "Container failed to start"
    echo ""
    echo "Container logs:"
    docker logs $CONTAINER_NAME
    exit 1
fi

echo ""
log_success "Deployment complete! 🎉"