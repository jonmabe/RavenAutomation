@echo off
setlocal enabledelayedexpansion

:: Parrot Server - Windows Deployment Script
:: For deploying ESP32 firmware and optionally starting the server

echo.
echo ====================================
echo    RavenAutomation Deploy Script
echo         Windows Edition
echo ====================================
echo.

:: Configuration
set ESP32_PORT=COM3
set ESP32_BOARD=esp32:esp32:esp32s3
set SKETCH_PATH=ParrotDriver
set PYTHON_VENV=venv

:: Check for command line arguments
if "%1"=="esp32" goto :esp32_only
if "%1"=="server" goto :server_only
if "%1"=="monitor" goto :monitor_only

:: Main menu
:menu
echo Select deployment option:
echo.
echo   [1] Deploy ESP32 firmware only
echo   [2] Start Python server only
echo   [3] Deploy ESP32 and start server
echo   [4] Monitor ESP32 serial output
echo   [5] Setup environment (first time)
echo   [Q] Quit
echo.
set /p choice="Enter your choice: "

if "%choice%"=="1" goto :esp32_only
if "%choice%"=="2" goto :server_only
if "%choice%"=="3" goto :full_deploy
if "%choice%"=="4" goto :monitor_only
if "%choice%"=="5" goto :setup_env
if /i "%choice%"=="q" goto :end
echo Invalid choice. Please try again.
echo.
goto :menu

:: Setup environment (first time setup)
:setup_env
echo.
echo [SETUP] Setting up environment...
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH
    echo Please install Python 3.8 or higher from python.org
    pause
    goto :end
)
echo [OK] Python found

:: Create virtual environment if it doesn't exist
if not exist "%PYTHON_VENV%" (
    echo [INFO] Creating Python virtual environment...
    python -m venv %PYTHON_VENV%
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment
        pause
        goto :end
    )
    echo [OK] Virtual environment created
)

:: Activate venv and install requirements
echo [INFO] Installing Python dependencies...
call %PYTHON_VENV%\Scripts\activate.bat
pip install -r requirements.txt >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies
    echo Run: pip install -r requirements.txt
    pause
    goto :end
)
echo [OK] Dependencies installed

:: Check for .env file
if not exist ".env" (
    echo [INFO] Creating .env file template...
    (
        echo # OpenAI Configuration
        echo OPENAI_API_KEY=your_openai_api_key_here
        echo OPENAI_VOICE=ballad
        echo OPENAI_MODEL=gpt-4o-realtime-preview-2024-12-17
        echo VOICE_BACKEND=openai
        echo.
        echo # Optional VAPI Configuration
        echo VAPI_API_KEY=
        echo VAPI_PUBLIC_KEY=
        echo VAPI_ASSISTANT_ID=
    ) > .env
    echo [WARNING] Please edit .env file with your API keys
    notepad .env
)

:: Check Arduino CLI
arduino-cli version >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Arduino CLI not found
    echo Download from: https://arduino.github.io/arduino-cli/
    echo Or install with: winget install Arduino.ArduinoCLI
    pause
)
echo [OK] Arduino CLI found

echo.
echo [SUCCESS] Environment setup complete!
pause
goto :menu

:: ESP32 deployment only
:esp32_only
echo.
echo [ESP32] Starting ESP32 firmware deployment...
echo.

:: Check if Arduino CLI is installed
arduino-cli version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Arduino CLI is not installed
    echo Please install from: https://arduino.github.io/arduino-cli/
    echo Or run: winget install Arduino.ArduinoCLI
    pause
    goto :end
)

:: Auto-detect ESP32 port if not specified
if "%ESP32_PORT%"=="COM3" (
    echo [INFO] Detecting ESP32 port...
    for /f "tokens=1" %%a in ('arduino-cli board list ^| findstr "USB"') do (
        set ESP32_PORT=%%a
        echo [OK] Found ESP32 on port: %%a
        goto :port_found
    )
    echo [WARNING] Could not auto-detect port. Using default COM3
)
:port_found

:: Compile the sketch
echo [INFO] Compiling sketch for %ESP32_BOARD%...
arduino-cli compile --fqbn %ESP32_BOARD% %SKETCH_PATH%
if errorlevel 1 (
    echo [ERROR] Compilation failed
    pause
    goto :end
)
echo [OK] Compilation successful

:: Ask before uploading
echo.
set /p upload="Upload to ESP32 on %ESP32_PORT%? (Y/N): "
if /i not "%upload%"=="y" goto :end

:: Upload to ESP32
echo [INFO] Uploading to ESP32...
echo [WARNING] Make sure Arduino IDE is closed!
arduino-cli upload -p %ESP32_PORT% --fqbn %ESP32_BOARD% %SKETCH_PATH%
if errorlevel 1 (
    echo [ERROR] Upload failed
    echo Tips:
    echo   - Close Arduino IDE if open
    echo   - Check the port in Device Manager
    echo   - Try unplugging and replugging the ESP32
    pause
    goto :end
)
echo [OK] Upload successful!

:: Ask to monitor
echo.
set /p monitor="Monitor serial output? (Y/N): "
if /i "%monitor%"=="y" goto :monitor_only
goto :end

:: Server deployment only
:server_only
echo.
echo [SERVER] Starting Python server...
echo.

:: Check if venv exists
if not exist "%PYTHON_VENV%" (
    echo [ERROR] Virtual environment not found
    echo Run option 5 to setup environment first
    pause
    goto :menu
)

:: Check .env file
if not exist ".env" (
    echo [ERROR] .env file not found
    echo Run option 5 to setup environment first
    pause
    goto :menu
)

:: Check if API key is set
findstr /C:"your_openai_api_key_here" .env >nul
if not errorlevel 1 (
    echo [ERROR] Please set your OPENAI_API_KEY in the .env file
    notepad .env
    pause
    goto :end
)

:: Activate venv and start server
echo [INFO] Activating virtual environment...
call %PYTHON_VENV%\Scripts\activate.bat

echo [INFO] Starting parrot server...
echo.
echo Server URLs:
echo   Audio Stream:  ws://localhost:8001/audio-stream
echo   Microphone:    ws://localhost:8002/microphone
echo   Control:       ws://localhost:8080/
echo.
echo Press Ctrl+C to stop the server
echo.
python parrot_server.py
goto :end

:: Full deployment
:full_deploy
echo.
echo [FULL] Starting full deployment...
call :esp32_only
if errorlevel 1 goto :end
echo.
echo [INFO] ESP32 deployment complete. Starting server...
timeout /t 3 /nobreak >nul
call :server_only
goto :end

:: Monitor serial output
:monitor_only
echo.
echo [MONITOR] Starting serial monitor...
echo.

:: Auto-detect port if needed
if "%ESP32_PORT%"=="COM3" (
    for /f "tokens=1" %%a in ('arduino-cli board list ^| findstr "USB"') do (
        set ESP32_PORT=%%a
        echo [OK] Found ESP32 on port: %%a
        goto :start_monitor
    )
)

:start_monitor
echo [INFO] Monitoring %ESP32_PORT% at 115200 baud
echo Press Ctrl+C to stop monitoring
echo.
arduino-cli monitor -p %ESP32_PORT% -c baudrate=115200
goto :end

:end
echo.
echo Deployment script finished.
pause