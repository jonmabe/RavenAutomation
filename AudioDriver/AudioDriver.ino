#include <WiFi.h>
#include <WebSocketsClient.h>
#include <driver/i2s.h>
#include <soc/rtc.h>
#include <soc/gpio_periph.h>
#include <soc/gpio_struct.h>
#include <soc/io_mux_reg.h>

// WiFi credentials
const char* ssid = "***REMOVED***";
const char* password = "***REMOVED***";

// WebSocket settings
const char* wsHost = "192.168.1.174";  // Your server IP
const int wsPort = 8001;  // Different from main server port
const char* wsPath = "/audio-stream";

// I2S pins
const int I2S_BCLK = 27;    // Bit clock
const int I2S_LRC = 26;     // Left/Right clock
const int I2S_DOUT = 25;    // Data out

// I2S configuration
const i2s_port_t I2S_PORT = I2S_NUM_0;
const int BUFFER_SIZE = 1024;  // Increased for network streaming
const int DMA_BUFFER_COUNT = 8;

// Add near the top with other constants
const size_t NETWORK_BUFFER_SIZE = 8192;  // Network buffer size

// Add these constants at the top with other definitions
const int WIFI_RETRY_DELAY = 5000;
const int WIFI_TIMEOUT = 10000;
const unsigned long WIFI_CHECK_INTERVAL = 30000;  // Check every 30 seconds

// Add these pins for the microphone
const int I2S_MIC_SCK = 14;    // Serial Clock
const int I2S_MIC_WS = 15;     // Word Select
const int I2S_MIC_SD = 32;     // Serial Data

// Add second I2S port for microphone
const i2s_port_t I2S_MIC_PORT = I2S_NUM_1;

// Add second WebSocket client for microphone
WebSocketsClient micWebSocket;
const int wsPortMic = 8002;  // Microphone WebSocket port
const char* wsPathMic = "/microphone";  // Microphone WebSocket path

// Add microphone buffer
const size_t MIC_BUFFER_SIZE = 1024;
int16_t micBuffer[MIC_BUFFER_SIZE];

WebSocketsClient webSocket;
bool isConfigured = false;

// Add these variables near the top with other globals
unsigned long lastReconnectAttempt = 0;
const unsigned long RECONNECT_INTERVAL = 5000;  // 5 seconds
bool wasConnected = false;

void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
    switch(type) {
        case WStype_CONNECTED:
            Serial.println("WebSocket Connected");
            wasConnected = true;
            isConfigured = true;
            break;
            
        case WStype_DISCONNECTED:
            Serial.println("WebSocket Disconnected");
            isConfigured = false;
            wasConnected = false;
            break;
            
        case WStype_BIN:
            if (isConfigured) {
                size_t bytes_written = 0;
                Serial.printf("Received %d bytes of audio data\n", length);
                i2s_write(I2S_PORT, payload, length, &bytes_written, portMAX_DELAY);
            } else {
                Serial.println("Received audio data before I2S configuration!");
            }
            break;
            
        case WStype_ERROR:
            Serial.println("WebSocket Error");
            isConfigured = false;
            break;
    }
}

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

void setup() {
    Serial.begin(115200);
    
    // Enhanced WiFi setup
    WiFi.mode(WIFI_STA);
    WiFi.setSleep(false);  // Disable WiFi sleep mode for better stability
    WiFi.setAutoReconnect(true);
    
    // Connect to WiFi with timeout
    unsigned long startAttempt = millis();
    WiFi.begin(ssid, password);
    
    while (WiFi.status() != WL_CONNECTED) {
        if (millis() - startAttempt > WIFI_TIMEOUT) {
            Serial.println("\nWiFi connection timeout. Restarting...");
            ESP.restart();
        }
        delay(500);
        Serial.print(".");
    }
    
    Serial.println("\nWiFi connected");
    Serial.println("IP address: " + WiFi.localIP().toString());
    
     // Configure speaker I2S
    configureI2S(); 
    
    // Configure WebSocket
    webSocket.begin(wsHost, wsPort, wsPath);
    webSocket.onEvent(webSocketEvent);
    webSocket.setReconnectInterval(5000);
    webSocket.enableHeartbeat(15000, 3000, 2);
    
    // Configure microphone I2S
    setupMicI2S();
    
    // Configure microphone WebSocket
    micWebSocket.begin(wsHost, wsPortMic, wsPathMic);
    micWebSocket.onEvent(micWebSocketEvent);
    micWebSocket.setReconnectInterval(5000);
}

// Add this function to check WiFi status
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

    webSocket.loop();

    // If we were previously connected and now we're not, try to reconnect
    if (wasConnected && !webSocket.isConnected()) {
        unsigned long currentMillis = millis();
        if (currentMillis - lastReconnectAttempt >= RECONNECT_INTERVAL) {
            Serial.println("Attempting to reconnect WebSocket...");
            webSocket.begin(wsHost, wsPort, wsPath);
            lastReconnectAttempt = currentMillis;
        }
    }
    
    // Handle microphone WebSocket
    micWebSocket.loop();
    
    // Read and send microphone data
    if (micWebSocket.isConnected()) {
        size_t bytes_read = 0;
        esp_err_t result = i2s_read(I2S_MIC_PORT, micBuffer, sizeof(micBuffer), &bytes_read, 0);
        
        if (result == ESP_OK && bytes_read > 0) {
            micWebSocket.sendBIN((uint8_t*)micBuffer, bytes_read);
        }
    }
    
    // Small delay to prevent overwhelming the system
    delay(1);
}