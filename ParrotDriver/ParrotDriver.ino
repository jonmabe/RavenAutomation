// !!! DRIVER VERSION: 0.6.4a !!!
// !!! Api Version: 7 !!!

#include "src/BottangoCore.h"
#include "src/BasicCommands.h"
#include <WiFi.h>
#include <WebSocketsClient.h>
#include <driver/i2s.h>
#include <WiFiManager.h>

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

// Add a simple moving average filter
const int FILTER_SIZE = 4;
int32_t filter_buffer[FILTER_SIZE];
int filter_index = 0;

// WebSocket clients
WebSocketsClient bottangoWebSocket;  // Renamed from webSocket
WebSocketsClient audioWebSocket;     // For speaker
WebSocketsClient micWebSocket;       // For microphone

// State variables
String commandBuffer = "";
bool isConfigured = false;
bool wsCommandInProgress = false;
unsigned long wsTimeOfLastChar = 0;
const unsigned long WIFI_CHECK_INTERVAL = 30000;

// Add I2S configuration functions
void configureI2S() {
    const uint32_t SAMPLE_RATE = 24000;
    const uint8_t CHANNELS = 2;
    const uint8_t BITS_PER_SAMPLE = 16;
    
    Serial.printf("Configuring I2S - Sample Rate: %d Hz, Channels: %d, Bits: %d\n", 
                 SAMPLE_RATE, CHANNELS, BITS_PER_SAMPLE);

    // Try to uninstall, but ignore errors
    i2s_driver_uninstall(I2S_PORT);
    
    i2s_config_t i2s_config = {
        .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
        .sample_rate = SAMPLE_RATE,
        .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
        .channel_format = I2S_CHANNEL_FMT_RIGHT_LEFT,
        .communication_format = I2S_COMM_FORMAT_STAND_I2S,
        .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
        .dma_buf_count = DMA_BUFFER_COUNT,
        .dma_buf_len = BUFFER_SIZE,
        .use_apll = true,
        .tx_desc_auto_clear = true,
        .fixed_mclk = -1
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

// Add these constants
const int I2S_MIC_GAIN_DB = 30;  // Microphone gain in dB

void setupMicI2S() {
    // Try to uninstall, but ignore errors
    i2s_driver_uninstall(I2S_MIC_PORT);
    
    i2s_config_t i2s_mic_config = {
        .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
        .sample_rate = 24000,
        .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT,
        .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
        .communication_format = I2S_COMM_FORMAT_STAND_I2S,
        .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
        .dma_buf_count = DMA_BUFFER_COUNT,
        .dma_buf_len = BUFFER_SIZE,
        .use_apll = true,
        .tx_desc_auto_clear = false,
        .fixed_mclk = 0
    };
    
    i2s_pin_config_t mic_pin_config = {
        .mck_io_num = I2S_PIN_NO_CHANGE,
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
    
    // Additional microphone optimizations
    err = i2s_set_clk(I2S_MIC_PORT, 24000, I2S_BITS_PER_SAMPLE_32BIT, I2S_CHANNEL_MONO);
    if (err != ESP_OK) {
        Serial.printf("Failed to set I2S clock: %d\n", err);
    }

    // Let's increase the gain in our 32-bit to 16-bit conversion
    // Modify the microphone reading code in loop()
    if (micWebSocket.isConnected()) {
        size_t bytes_read = 0;
        esp_err_t result = i2s_read(I2S_MIC_PORT, micBuffer, sizeof(micBuffer), &bytes_read, 0);
        
        if (result == ESP_OK && bytes_read > 0) {
            // Convert 32-bit samples to 16-bit with proper scaling
            int32_t* samples32 = (int32_t*)micBuffer;
            int16_t* samples16 = (int16_t*)micBuffer;
            size_t sample_count = bytes_read / 4;  // 4 bytes per 32-bit sample
            
            for (size_t i = 0; i < sample_count; i++) {
                // Scale down 32-bit to 16-bit with increased gain
                int32_t sample = samples32[i] >> 12;
                
                // Apply moving average filter
                filter_buffer[filter_index] = sample;
                filter_index = (filter_index + 1) % FILTER_SIZE;
                
                int32_t filtered_sample = 0;
                for (int j = 0; j < FILTER_SIZE; j++) {
                    filtered_sample += filter_buffer[j];
                }
                filtered_sample /= FILTER_SIZE;
                
                // Apply gain after filtering
                filtered_sample = (filtered_sample * 3) >> 1;  // 1.5x gain
                
                // Clip to prevent distortion
                filtered_sample = constrain(filtered_sample, -32768, 32767);
                
                // Store the filtered sample
                samples16[i] = (int16_t)filtered_sample;
            }
            
            // Send the 16-bit samples
            micWebSocket.sendBIN((uint8_t*)samples16, sample_count * 2);
        }
    }
}

// WebSocket event handlers
void bottangoWebSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
    switch(type) {
        case WStype_DISCONNECTED:
            Serial.println("Bottango WebSocket Disconnected!");
            wsCommandInProgress = false;
            wsTimeOfLastChar = 0;
            commandBuffer = "";
            break;
            
        case WStype_CONNECTED:
            Serial.println("Bottango WebSocket Connected!");
            break;
            
        case WStype_ERROR:
            Serial.println("Bottango WebSocket Error - Attempting reconnect");
            bottangoWebSocket.disconnect();
            delay(1000);
            bottangoWebSocket.begin(wsHost, wsPort, wsPath);
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
            
        case WStype_ERROR:
            Serial.println("Audio WebSocket Error - Attempting reconnect");
            audioWebSocket.disconnect();
            delay(1000);
            audioWebSocket.begin(wsHost, wsPortAudio, wsPathAudio);
            break;
            
        case WStype_BIN:
            if (isConfigured) {
                const size_t MAX_CHUNK = 512;  // Process in smaller chunks
                size_t processed = 0;
                
                while (processed < length) {
                    size_t chunk_size = min(MAX_CHUNK, length - processed);
                    size_t stereo_length = chunk_size * 2;
                    uint8_t* stereo_buffer = (uint8_t*)malloc(stereo_length);
                    
                    if (stereo_buffer) {
                        // Duplicate mono data to both channels
                        for (size_t i = 0; i < chunk_size; i += 2) {
                            // Copy sample to left channel
                            stereo_buffer[i*2] = payload[processed + i];
                            stereo_buffer[i*2 + 1] = payload[processed + i + 1];
                            // Copy same sample to right channel
                            stereo_buffer[i*2 + 2] = payload[processed + i];
                            stereo_buffer[i*2 + 3] = payload[processed + i + 1];
                        }
                        
                        size_t bytes_written = 0;
                        i2s_write(I2S_PORT, stereo_buffer, stereo_length, &bytes_written, portMAX_DELAY);
                        free(stereo_buffer);
                    }
                    
                    processed += chunk_size;
                    // Small delay between chunks to prevent overwhelming the system
                    if (processed < length) {
                        delay(1);
                    }
                }
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
            
        case WStype_ERROR:
            Serial.println("Microphone WebSocket Error - Attempting reconnect");
            micWebSocket.disconnect();
            delay(1000);
            micWebSocket.begin(wsHost, wsPortMic, wsPathMic);
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

// Add these constants at the top
const int HEARTBEAT_INTERVAL = 15000; // 15 seconds
const int HEARTBEAT_TIMEOUT = 3000;   // 3 seconds
const int HEARTBEAT_RETRIES = 2;

void setup() {
    Serial.begin(115200);
    
    // WiFi setup using WiFiManager
    WiFiManager wifiManager;
    
    // Uncomment to reset settings - wipe stored credentials
    // wifiManager.resetSettings();
    
    // Set custom timeout (optional)
    wifiManager.setConfigPortalTimeout(180); // 3 minutes
    
    // Custom AP name using last 4 bytes of MAC address
    uint8_t mac[6];
    WiFi.macAddress(mac);
    String apName = "ParrotConfig-" + String(mac[4], HEX) + String(mac[5], HEX);
    
    // Attempt to connect or create AP for configuration
    if(!wifiManager.autoConnect(apName.c_str())) {
        Serial.println("Failed to connect and hit timeout");
        delay(3000);
        ESP.restart();
    }
    
    Serial.println("WiFi connected");
    Serial.println("IP address: " + WiFi.localIP().toString());

    // Configure I2S
    configureI2S();
    setupMicI2S();
    
    // Initialize Bottango
    BottangoCore::bottangoSetup();
    initializeServos();
    
    // Bottango WebSocket
    bottangoWebSocket.begin(wsHost, wsPort, wsPath);
    bottangoWebSocket.onEvent(bottangoWebSocketEvent);
    bottangoWebSocket.setReconnectInterval(5000);
    bottangoWebSocket.enableHeartbeat(HEARTBEAT_INTERVAL, HEARTBEAT_TIMEOUT, HEARTBEAT_RETRIES);
    
    // Audio WebSocket
    audioWebSocket.begin(wsHost, wsPortAudio, wsPathAudio);
    audioWebSocket.onEvent(audioWebSocketEvent);
    audioWebSocket.setReconnectInterval(5000);
    audioWebSocket.enableHeartbeat(HEARTBEAT_INTERVAL, HEARTBEAT_TIMEOUT, HEARTBEAT_RETRIES);
    
    // Microphone WebSocket
    micWebSocket.begin(wsHost, wsPortMic, wsPathMic);
    micWebSocket.onEvent(micWebSocketEvent);
    micWebSocket.setReconnectInterval(5000);
    micWebSocket.enableHeartbeat(HEARTBEAT_INTERVAL, HEARTBEAT_TIMEOUT, HEARTBEAT_RETRIES);
}

void checkWiFiConnection() {
    static unsigned long lastCheck = 0;
    
    if (millis() - lastCheck >= WIFI_CHECK_INTERVAL) {
        lastCheck = millis();
        
        if (WiFi.status() != WL_CONNECTED) {
            Serial.println("WiFi connection lost. Attempting to reconnect...");
            
            WiFiManager wifiManager;
            wifiManager.setConfigPortalTimeout(60); // 1 minute timeout for reconnection
            
            if (!wifiManager.autoConnect()) {
                Serial.println("Failed to reconnect. Restarting...");
                ESP.restart();
            }
            
            Serial.println("Reconnected to WiFi");
            Serial.println("IP address: " + WiFi.localIP().toString());
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
    
    // Handle microphone data with rate limiting
    static unsigned long lastMicRead = 0;
    const unsigned long MIC_READ_INTERVAL = 20;  // 20ms between reads
    
    if (micWebSocket.isConnected() && millis() - lastMicRead >= MIC_READ_INTERVAL) {
        size_t bytes_read = 0;
        esp_err_t result = i2s_read(I2S_MIC_PORT, micBuffer, sizeof(micBuffer), &bytes_read, 0);
        
        if (result == ESP_OK && bytes_read > 0) {
            // Convert 32-bit samples to 16-bit with proper scaling
            int32_t* samples32 = (int32_t*)micBuffer;
            int16_t* samples16 = (int16_t*)micBuffer;
            size_t sample_count = bytes_read / 4;  // 4 bytes per 32-bit sample
            
            for (size_t i = 0; i < sample_count; i++) {
                // Scale down 32-bit to 16-bit with increased gain
                int32_t sample = samples32[i] >> 12;
                
                // Apply moving average filter
                filter_buffer[filter_index] = sample;
                filter_index = (filter_index + 1) % FILTER_SIZE;
                
                int32_t filtered_sample = 0;
                for (int j = 0; j < FILTER_SIZE; j++) {
                    filtered_sample += filter_buffer[j];
                }
                filtered_sample /= FILTER_SIZE;
                
                // Apply gain after filtering
                filtered_sample = (filtered_sample * 3) >> 1;  // 1.5x gain
                
                // Clip to prevent distortion
                filtered_sample = constrain(filtered_sample, -32768, 32767);
                
                // Store the filtered sample
                samples16[i] = (int16_t)filtered_sample;
            }
            
            // Send the 16-bit samples
            micWebSocket.sendBIN((uint8_t*)samples16, sample_count * 2);
            lastMicRead = millis();
        }
    }
    
    // Handle command timeout
    if (wsCommandInProgress && millis() - wsTimeOfLastChar >= READ_TIMEOUT) {
        BasicCommands::printOutputString(BasicCommands::TIMEOUT);
        commandBuffer = "";
        wsCommandInProgress = false;
        wsTimeOfLastChar = 0;
    }
    
    // Increased delay to give more time for system tasks
    delay(2);
}
