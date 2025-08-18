# RavenAutomation PowerShell Deployment Script
# Requires PowerShell 5.0 or higher

param(
    [Parameter(Position=0)]
    [ValidateSet('esp32', 'server', 'full', 'monitor', 'setup', 'docker')]
    [string]$Mode = '',
    
    [string]$Port = '',
    [switch]$Force
)

# Configuration
$Config = @{
    ESP32Port = 'COM3'
    ESP32Board = 'esp32:esp32:esp32s3'
    SketchPath = 'ParrotDriver'
    PythonVenv = 'venv'
    ContainerName = 'parrot-server'
    ImageName = 'parrot-server'
}

# Colors for output
function Write-ColorOutput {
    param([string]$Text, [string]$Color = 'White')
    Write-Host $Text -ForegroundColor $Color
}

function Write-Info { Write-ColorOutput "[INFO] $args" Cyan }
function Write-Success { Write-ColorOutput "[OK] $args" Green }
function Write-Warning { Write-ColorOutput "[WARNING] $args" Yellow }
function Write-Error { Write-ColorOutput "[ERROR] $args" Red }

# Banner
function Show-Banner {
    Clear-Host
    Write-Host ""
    Write-ColorOutput "=====================================" Magenta
    Write-ColorOutput "   RavenAutomation Deploy Script" White
    Write-ColorOutput "       PowerShell Edition" White
    Write-ColorOutput "=====================================" Magenta
    Write-Host ""
}

# Check if running as Administrator
function Test-Administrator {
    $currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    return $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

# Auto-detect ESP32 port
function Get-ESP32Port {
    Write-Info "Detecting ESP32 port..."
    
    # Try using Arduino CLI first
    if (Get-Command arduino-cli -ErrorAction SilentlyContinue) {
        $boards = arduino-cli board list 2>$null | Select-String "USB|usbmodem"
        if ($boards) {
            $port = ($boards -split '\s+')[0]
            Write-Success "Found ESP32 on port: $port"
            return $port
        }
    }
    
    # Fall back to WMI query
    $ports = Get-WmiObject Win32_SerialPort | Where-Object { 
        $_.Description -match "USB|Serial|CP210|CH340|FTDI|ESP32"
    }
    
    if ($ports) {
        $port = $ports[0].DeviceID
        Write-Success "Found serial device on port: $port"
        return $port
    }
    
    Write-Warning "Could not auto-detect port. Using default: $($Config.ESP32Port)"
    return $Config.ESP32Port
}

# Setup environment
function Initialize-Environment {
    Write-Host ""
    Write-Info "Setting up environment..."
    
    # Check Python
    try {
        $pythonVersion = python --version 2>&1
        Write-Success "Python found: $pythonVersion"
    } catch {
        Write-Error "Python is not installed or not in PATH"
        Write-Host "Please install Python 3.8+ from python.org"
        return $false
    }
    
    # Create virtual environment
    if (-not (Test-Path $Config.PythonVenv)) {
        Write-Info "Creating Python virtual environment..."
        python -m venv $Config.PythonVenv
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Failed to create virtual environment"
            return $false
        }
        Write-Success "Virtual environment created"
    }
    
    # Install dependencies
    Write-Info "Installing Python dependencies..."
    & "$($Config.PythonVenv)\Scripts\pip.exe" install -r requirements.txt -q
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to install dependencies"
        return $false
    }
    Write-Success "Dependencies installed"
    
    # Create .env file if missing
    if (-not (Test-Path ".env")) {
        Write-Info "Creating .env file template..."
        @"
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_VOICE=ballad
OPENAI_MODEL=gpt-4o-realtime-preview-2024-12-17
VOICE_BACKEND=openai

# Optional VAPI Configuration
VAPI_API_KEY=
VAPI_PUBLIC_KEY=
VAPI_ASSISTANT_ID=
"@ | Set-Content ".env"
        Write-Warning "Please edit .env file with your API keys"
        Start-Process notepad ".env" -Wait
    }
    
    # Check Arduino CLI
    if (Get-Command arduino-cli -ErrorAction SilentlyContinue) {
        Write-Success "Arduino CLI found"
    } else {
        Write-Warning "Arduino CLI not found"
        Write-Host "Install with: winget install Arduino.ArduinoCLI"
        Write-Host "Or download from: https://arduino.github.io/arduino-cli/"
    }
    
    Write-Success "Environment setup complete!"
    return $true
}

# Deploy ESP32
function Deploy-ESP32 {
    param([string]$CustomPort = '')
    
    Write-Host ""
    Write-Info "Starting ESP32 firmware deployment..."
    
    # Check Arduino CLI
    if (-not (Get-Command arduino-cli -ErrorAction SilentlyContinue)) {
        Write-Error "Arduino CLI is not installed"
        Write-Host "Install with: winget install Arduino.ArduinoCLI"
        return $false
    }
    
    # Determine port
    $port = if ($CustomPort) { $CustomPort } else { Get-ESP32Port }
    
    # Compile sketch
    Write-Info "Compiling sketch for $($Config.ESP32Board)..."
    arduino-cli compile --fqbn $Config.ESP32Board $Config.SketchPath
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Compilation failed"
        return $false
    }
    Write-Success "Compilation successful"
    
    # Ask before uploading
    if (-not $Force) {
        $response = Read-Host "Upload to ESP32 on ${port}? (Y/N)"
        if ($response -ne 'Y' -and $response -ne 'y') {
            return $false
        }
    }
    
    # Kill any serial monitors
    Get-Process | Where-Object { $_.ProcessName -match "arduino|serial|monitor" } | Stop-Process -Force -ErrorAction SilentlyContinue
    
    # Upload
    Write-Info "Uploading to ESP32..."
    Write-Warning "Make sure Arduino IDE is closed!"
    arduino-cli upload -p $port --fqbn $Config.ESP32Board $Config.SketchPath
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Upload failed"
        Write-Host "Tips:"
        Write-Host "  - Close Arduino IDE if open"
        Write-Host "  - Check the port in Device Manager"
        Write-Host "  - Try unplugging and replugging the ESP32"
        return $false
    }
    
    Write-Success "Upload successful!"
    
    # Ask to monitor
    if (-not $Force) {
        $response = Read-Host "Monitor serial output? (Y/N)"
        if ($response -eq 'Y' -or $response -eq 'y') {
            Start-SerialMonitor -CustomPort $port
        }
    }
    
    return $true
}

# Start Python server
function Start-PythonServer {
    Write-Host ""
    Write-Info "Starting Python server..."
    
    # Check virtual environment
    if (-not (Test-Path $Config.PythonVenv)) {
        Write-Error "Virtual environment not found"
        Write-Host "Run: .\deploy.ps1 setup"
        return $false
    }
    
    # Check .env file
    if (-not (Test-Path ".env")) {
        Write-Error ".env file not found"
        Write-Host "Run: .\deploy.ps1 setup"
        return $false
    }
    
    # Check API key
    $envContent = Get-Content ".env" -Raw
    if ($envContent -match "your_openai_api_key_here") {
        Write-Error "Please set your OPENAI_API_KEY in the .env file"
        Start-Process notepad ".env" -Wait
        return $false
    }
    
    # Get local IP
    $localIP = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notmatch "Loopback" })[0].IPAddress
    
    Write-Host ""
    Write-ColorOutput "Server URLs:" Yellow
    Write-Host "  Audio Stream:  ws://${localIP}:8001/audio-stream"
    Write-Host "  Microphone:    ws://${localIP}:8002/microphone"
    Write-Host "  Control:       ws://${localIP}:8080/"
    Write-Host ""
    Write-Host "  Local Audio:   ws://localhost:8001/audio-stream"
    Write-Host "  Local Mic:     ws://localhost:8002/microphone"
    Write-Host "  Local Control: ws://localhost:8080/"
    Write-Host ""
    Write-ColorOutput "Press Ctrl+C to stop the server" Yellow
    Write-Host ""
    
    # Start server
    & "$($Config.PythonVenv)\Scripts\python.exe" parrot_server.py
    return $true
}

# Start serial monitor
function Start-SerialMonitor {
    param([string]$CustomPort = '')
    
    Write-Host ""
    Write-Info "Starting serial monitor..."
    
    $port = if ($CustomPort) { $CustomPort } else { Get-ESP32Port }
    
    Write-Info "Monitoring $port at 115200 baud"
    Write-ColorOutput "Press Ctrl+C to stop monitoring" Yellow
    Write-Host ""
    
    if (Get-Command arduino-cli -ErrorAction SilentlyContinue) {
        arduino-cli monitor -p $port -c baudrate=115200
    } else {
        Write-Error "Arduino CLI not found. Using Python monitor..."
        if (Test-Path "monitor_serial.py") {
            python monitor_serial.py $port
        } else {
            Write-Error "No serial monitor available"
        }
    }
}

# Docker deployment
function Deploy-Docker {
    Write-Host ""
    Write-Info "Starting Docker deployment..."
    
    # Check if Docker is installed
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Error "Docker is not installed"
        Write-Host "Install Docker Desktop from: https://www.docker.com/products/docker-desktop"
        return $false
    }
    
    # Check if Docker is running
    try {
        docker ps 2>&1 | Out-Null
    } catch {
        Write-Error "Docker is not running. Please start Docker Desktop"
        return $false
    }
    
    Write-Success "Docker is available"
    
    # Stop existing container
    $existingContainer = docker ps -a --filter "name=$($Config.ContainerName)" --format "{{.Names}}"
    if ($existingContainer) {
        Write-Info "Stopping existing container..."
        docker stop $Config.ContainerName | Out-Null
        docker rm $Config.ContainerName | Out-Null
        Write-Success "Removed existing container"
    }
    
    # Build image
    Write-Info "Building Docker image..."
    docker build -t $Config.ImageName .
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Docker build failed"
        return $false
    }
    Write-Success "Docker image built"
    
    # Run container
    Write-Info "Starting container..."
    docker run -d `
        --name $Config.ContainerName `
        --restart unless-stopped `
        -p 8001:8001 `
        -p 8002:8002 `
        -p 8080:8080 `
        --env-file .env `
        $Config.ImageName
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to start container"
        return $false
    }
    
    Start-Sleep -Seconds 3
    
    # Check status
    $running = docker ps --filter "name=$($Config.ContainerName)" --format "{{.Names}}"
    if ($running) {
        Write-Success "Container is running!"
        
        Write-Host ""
        Write-ColorOutput "Container Status:" Yellow
        docker ps --filter "name=$($Config.ContainerName)"
        
        Write-Host ""
        Write-ColorOutput "Container Logs:" Yellow
        docker logs --tail 20 $Config.ContainerName
        
        Write-Host ""
        Write-ColorOutput "Useful commands:" Cyan
        Write-Host "  View logs:    docker logs -f $($Config.ContainerName)"
        Write-Host "  Stop server:  docker stop $($Config.ContainerName)"
        Write-Host "  Start server: docker start $($Config.ContainerName)"
        Write-Host "  Restart:      docker restart $($Config.ContainerName)"
        
        Write-Success "Docker deployment complete!"
    } else {
        Write-Error "Container failed to start"
        docker logs $Config.ContainerName
        return $false
    }
    
    return $true
}

# Main menu
function Show-Menu {
    Write-Host "Select deployment option:"
    Write-Host ""
    Write-ColorOutput "  [1] " -NoNewline; Write-Host "Deploy ESP32 firmware only"
    Write-ColorOutput "  [2] " -NoNewline; Write-Host "Start Python server only"
    Write-ColorOutput "  [3] " -NoNewline; Write-Host "Full deployment (ESP32 + Server)"
    Write-ColorOutput "  [4] " -NoNewline; Write-Host "Monitor ESP32 serial output"
    Write-ColorOutput "  [5] " -NoNewline; Write-Host "Setup environment (first time)"
    Write-ColorOutput "  [6] " -NoNewline; Write-Host "Docker deployment"
    Write-ColorOutput "  [Q] " -NoNewline; Write-Host "Quit"
    Write-Host ""
    
    $choice = Read-Host "Enter your choice"
    
    switch ($choice) {
        '1' { Deploy-ESP32 -CustomPort $Port }
        '2' { Start-PythonServer }
        '3' { 
            if (Deploy-ESP32 -CustomPort $Port) {
                Start-Sleep -Seconds 2
                Start-PythonServer
            }
        }
        '4' { Start-SerialMonitor -CustomPort $Port }
        '5' { Initialize-Environment }
        '6' { Deploy-Docker }
        'Q' { exit 0 }
        'q' { exit 0 }
        default {
            Write-Warning "Invalid choice. Please try again."
            Start-Sleep -Seconds 2
            Show-Menu
        }
    }
}

# Main execution
Show-Banner

# Override port if specified
if ($Port) {
    $Config.ESP32Port = $Port
}

# Handle command line mode
switch ($Mode) {
    'esp32' { Deploy-ESP32 -CustomPort $Port }
    'server' { Start-PythonServer }
    'full' {
        if (Deploy-ESP32 -CustomPort $Port) {
            Start-Sleep -Seconds 2
            Start-PythonServer
        }
    }
    'monitor' { Start-SerialMonitor -CustomPort $Port }
    'setup' { Initialize-Environment }
    'docker' { Deploy-Docker }
    default { Show-Menu }
}

Write-Host ""
Write-ColorOutput "Deployment script finished." Green
if (-not $Mode) {
    Write-Host "Press any key to exit..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}