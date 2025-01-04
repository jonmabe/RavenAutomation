// !!! DRIVER VERSION: 0.6.4a !!!
// !!! Api Version: 7 !!!

#include "src/BottangoCore.h"
#include "src/BasicCommands.h"
#include <WiFi.h>
#include <WebSocketsClient.h>
#include <driver/i2s.h>

// WiFi credentials
const char* ssid = "***REMOVED***";
const char* password = "***REMOVED***";

// Bottango WebSocket settings
const char* wsHost = "192.168.1.174";
const int wsPort = 8080;
const char* wsPath = "/bottango";

// Audio WebSocket settings
const int wsPortAudio = 8001;
const char* wsPathAudio = "/audio-stream";
const int wsPortMic = 8002;
const char* wsPathMic = "/microphone";

const int MOUTH_PIN = 27;
const int HEAD_TILT_PIN = 14;
const int WING_PIN = 13;
const int HEAD_ROTATION_PIN = 12;

// I2S Speaker pins
const int I2S_BCLK = 18;
const int I2S_LRC = 19;
const int I2S_DOUT = 23;

// I2S Microphone pins
const int I2S_MIC_SCK = 16;
const int I2S_MIC_WS = 17;
const int I2S_MIC_SD = 21;

// I2S configuration
const i2s_port_t I2S_PORT = I2S_NUM_0;
const i2s_port_t I2S_MIC_PORT = I2S_NUM_1;
const int BUFFER_SIZE = 1024;
const int DMA_BUFFER_COUNT = 8;
const size_t MIC_BUFFER_SIZE = 1024;
int16_t micBuffer[MIC_BUFFER_SIZE];

// WebSocket clients
WebSocketsClient bottangoWebSocket;  // Renamed from webSocket
WebSocketsClient audioWebSocket;     // For speaker
WebSocketsClient micWebSocket;       // For microphone

// State variables
String commandBuffer = "";
bool isConfigured = false;
bool wsCommandInProgress = false;
unsigned long wsTimeOfLastChar = 0;
bool wasConnected = false;
unsigned long lastReconnectAttempt = 0;
const unsigned long RECONNECT_INTERVAL = 5000;
const int WIFI_RETRY_DELAY = 5000;
const int WIFI_TIMEOUT = 10000;
const unsigned long WIFI_CHECK_INTERVAL = 30000;

// Add I2S configuration functions
void configureI2S() {
    const uint32_t SAMPLE_RATE = 24000;
    const uint8_t CHANNELS = 1;
    const uint8_t BITS_PER_SAMPLE = 16;
    
    Serial.printf("Configuring I2S - Sample Rate: %d Hz, Channels: %d, Bits: %d\n", 
                 SAMPLE_RATE, CHANNELS, BITS_PER_SAMPLE);

    // Try to uninstall, but ignore errors
    i2s_driver_uninstall(I2S_PORT);
    
    i2s_config_t i2s_config = {
        .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
        .sample_rate = SAMPLE_RATE,
        .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
        .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
        .communication_format = I2S_COMM_FORMAT_STAND_I2S,
        .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
        .dma_buf_count = DMA_BUFFER_COUNT,
        .dma_buf_len = BUFFER_SIZE,
        .use_apll = false,
        .tx_desc_auto_clear = true,
        .fixed_mclk = -1  // Changed to -1 to disable MCLK output
    };

    // Install I2S driver
    esp_err_t err = i2s_driver_install(I2S_PORT, &i2s_config, 0, NULL);
    if (err != ESP_OK) {
        Serial.printf("Failed to install I2S driver: %d\n", err);
        return;
    }

    // Configure I2S pins
    i2s_pin_config_t pin_config = {
        .mck_io_num = I2S_PIN_NO_CHANGE,  // MCK must come first
        .bck_io_num = I2S_BCLK,
        .ws_io_num = I2S_LRC,
        .data_out_num = I2S_DOUT,
        .data_in_num = I2S_PIN_NO_CHANGE
    };
    
    err = i2s_set_pin(I2S_PORT, &pin_config);
    if (err != ESP_OK) {
        Serial.printf("Failed to set I2S pins: %d\n", err);
        return;
    }

    i2s_zero_dma_buffer(I2S_PORT);
    Serial.println("I2S configured successfully");

    isConfigured = true;
}

void setupMicI2S() {
    // Try to uninstall, but ignore errors
    i2s_driver_uninstall(I2S_MIC_PORT);
    
    i2s_config_t i2s_mic_config = {
        .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
        .sample_rate = 24000,
        .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
        .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
        .communication_format = I2S_COMM_FORMAT_STAND_I2S,
        .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
        .dma_buf_count = 8,
        .dma_buf_len = MIC_BUFFER_SIZE,
        .use_apll = false,
        .tx_desc_auto_clear = false,
        .fixed_mclk = -1  // Changed to -1 to disable MCLK output
    };
    
    i2s_pin_config_t mic_pin_config = {
        .mck_io_num = I2S_PIN_NO_CHANGE,  // MCK must come first
        .bck_io_num = I2S_MIC_SCK,
        .ws_io_num = I2S_MIC_WS,
        .data_out_num = I2S_PIN_NO_CHANGE,
        .data_in_num = I2S_MIC_SD
    };
    
    esp_err_t err = i2s_driver_install(I2S_MIC_PORT, &i2s_mic_config, 0, NULL);
    if (err != ESP_OK) {
        Serial.printf("Failed to install I2S mic driver: %d\n", err);
        return;
    }
    
    err = i2s_set_pin(I2S_MIC_PORT, &mic_pin_config);
    if (err != ESP_OK) {
        Serial.printf("Failed to set I2S mic pins: %d\n", err);
        return;
    }
    
    Serial.println("I2S microphone configured successfully");
}

// WebSocket event handlers
void bottangoWebSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
    switch(type) {
        case WStype_DISCONNECTED:
            Serial.println("WebSocket Disconnected!");
            wsCommandInProgress = false;
            wsTimeOfLastChar = 0;
            commandBuffer = "";
            break;
            
        case WStype_CONNECTED:
            Serial.println("WebSocket Connected!");
            break;
            
        case WStype_TEXT:
            wsCommandInProgress = true;
            wsTimeOfLastChar = millis();
            
            // Process the command
            char cmdBuffer[MAX_COMMAND_LENGTH];
            strncpy(cmdBuffer, (char*)payload, sizeof(cmdBuffer) - 1);
            cmdBuffer[sizeof(cmdBuffer) - 1] = '\0';
            
            //Serial.print("Command: ");
            //Serial.println(cmdBuffer);
            
            BottangoCore::processWebSocketCommand(cmdBuffer);
            
            wsCommandInProgress = false;
            wsTimeOfLastChar = 0;
            break;
    }
}

void audioWebSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
    switch(type) {
        case WStype_CONNECTED:
            Serial.println("Audio WebSocket Connected");
            break;
            
        case WStype_DISCONNECTED:
            Serial.println("Audio WebSocket Disconnected");
            break;
            
        case WStype_BIN:
            if (isConfigured) {
                size_t bytes_written = 0;
                Serial.printf("Writing %zu bytes to I2S\n", length);
                i2s_write(I2S_PORT, payload, length, &bytes_written, portMAX_DELAY);
            }
            break;
    }
}

void micWebSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
    switch(type) {
        case WStype_CONNECTED:
            Serial.println("Microphone WebSocket Connected");
            break;
            
        case WStype_DISCONNECTED:
            Serial.println("Microphone WebSocket Disconnected");
            break;
    }
}

void initializeServos() {
    BottangoCore::initialized = true;
    BottangoCore::effectorPool.dump();
    Callbacks::onThisControllerStarted();

    // Initialize all servos with their parameters
    String commands[] = {
        "rSVPin," + String(HEAD_TILT_PIN) + ",850,2100,3000,1760",   // Head tilt
        "rSVPin," + String(MOUTH_PIN) + ",1450,1700,3000,1700",      // Mouth
        "rSVPin," + String(WING_PIN) + ",1500,2000,3000,2000",       // Wing
        "rSVPin," + String(HEAD_ROTATION_PIN) + ",1275,1725,5000,1500"  // Head rotation
    };
    
    char cmdBuffer[MAX_COMMAND_LENGTH];  // Safe buffer for command processing
    for (const String& cmd : commands) {
        Serial.println("Initializing: " + cmd);
        cmd.toCharArray(cmdBuffer, sizeof(cmdBuffer));
        BottangoCore::processWebSocketCommand(cmdBuffer);
        delay(100);
    }
}

void setup() {
    Serial.begin(115200);
    
    // WiFi setup
    WiFi.mode(WIFI_STA);
    WiFi.setSleep(false);
    WiFi.setAutoReconnect(true);
    
    unsigned long startAttempt = millis();
    WiFi.begin(ssid, password);
    
    while (WiFi.status() != WL_CONNECTED) {
        if (millis() - startAttempt > WIFI_TIMEOUT) {
            ESP.restart();
        }
        delay(500);
        Serial.print(".");
    }
    
    Serial.println("\nWiFi connected");
    Serial.println("IP address: " + WiFi.localIP().toString());

    // Configure I2S
    configureI2S();
    setupMicI2S();
    
    // Initialize Bottango
    BottangoCore::bottangoSetup();
    initializeServos();
    
    // Setup all WebSocket connections
    bottangoWebSocket.begin(wsHost, wsPort, wsPath);
    bottangoWebSocket.onEvent(bottangoWebSocketEvent);
    bottangoWebSocket.setReconnectInterval(5000);
    
    audioWebSocket.begin(wsHost, wsPortAudio, wsPathAudio);
    audioWebSocket.onEvent(audioWebSocketEvent);
    audioWebSocket.setReconnectInterval(5000);
    audioWebSocket.enableHeartbeat(15000, 3000, 2);
    
    micWebSocket.begin(wsHost, wsPortMic, wsPathMic);
    micWebSocket.onEvent(micWebSocketEvent);
    micWebSocket.setReconnectInterval(5000);
}

void checkWiFiConnection() {
    static unsigned long lastCheck = 0;
    
    if (millis() - lastCheck >= WIFI_CHECK_INTERVAL) {
        lastCheck = millis();
        
        if (WiFi.status() != WL_CONNECTED) {
            Serial.println("WiFi connection lost. Reconnecting...");
            WiFi.disconnect();
            WiFi.begin(ssid, password);
            
            // Wait briefly for reconnection
            unsigned long startAttempt = millis();
            while (WiFi.status() != WL_CONNECTED && millis() - startAttempt < WIFI_RETRY_DELAY) {
                delay(100);
            }
            
            if (WiFi.status() != WL_CONNECTED) {
                Serial.println("Reconnection failed. Restarting device...");
                ESP.restart();
            }
        }
    }
}

void loop() {
    checkWiFiConnection();
    
    // Handle all WebSocket connections
    bottangoWebSocket.loop();
    audioWebSocket.loop();
    micWebSocket.loop();
    
    // Handle Bottango updates
    if (BottangoCore::initialized) {
        BottangoCore::effectorPool.updateAllDriveTargets();
    }
    
    // Handle microphone data
    if (micWebSocket.isConnected()) {
        size_t bytes_read = 0;
        esp_err_t result = i2s_read(I2S_MIC_PORT, micBuffer, sizeof(micBuffer), &bytes_read, 0);
        
        if (result == ESP_OK && bytes_read > 0) {
            micWebSocket.sendBIN((uint8_t*)micBuffer, bytes_read);
        }
    }
    
    // Handle command timeout
    if (wsCommandInProgress && millis() - wsTimeOfLastChar >= READ_TIMEOUT) {
        BasicCommands::printOutputString(BasicCommands::TIMEOUT);
        commandBuffer = "";
        wsCommandInProgress = false;
        wsTimeOfLastChar = 0;
    }
    
    delay(1);
}
