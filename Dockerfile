# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for PyAudio and other packages
RUN apt-get update && apt-get install -y \
    portaudio19-dev \
    libasound2-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY *.py ./
COPY start.sh ./

# Create directory for recordings
RUN mkdir -p mic_recordings

# Make startup script executable
RUN chmod +x start.sh

# Expose the ports used by the server
EXPOSE 8080 8001 8002

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV VOICE_BACKEND=openai

# Run the parrot server
CMD ["./start.sh"]