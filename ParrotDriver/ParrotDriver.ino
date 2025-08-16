// !!! DRIVER VERSION: 0.6.4a !!!
// !!! Api Version: 7 !!!

#include "src/BottangoCore.h"
#include "src/BasicCommands.h"
#include <WiFi.h>
#include <WebSocketsClient.h>
#include <driver/i2s.h>
#include <WiFiManager.h>
#include <ESP32Servo.h>

const char* wsHost = "192.168.1.174";
const int wsPort = 8080;

// Audio WebSocket settings
const int wsPortAudio = 8001;
const char* wsPathAudio = "/audio-stream";
const int wsPortMic = 8002;
const char* wsPathMic = "/microphone";

// Servo pins - Updated for new ESP32-S3 wiring
const int MOUTH_PIN = 6;           // Was GPIO27
const int HEAD_TILT_PIN = 5;       // Was GPIO14
const int HEAD_ROTATION_PIN = 8;   // Was GPIO12, moved from GPIO4 then GPIO10
const int WING_PIN = 3;            // Was GPIO13

// I2S Speaker pins - Updated for new ESP32-S3 wiring
const int I2S_BCLK = 42;           // Was GPIO18
const int I2S_LRC = 41;            // Was GPIO19
const int I2S_DOUT = 40;           // Was GPIO23 (DIN on amplifier)

// I2S Microphone pins - Updated for new ESP32-S3 wiring
const int I2S_MIC_SCK = 15;        // Was GPIO16 (BCLK) - Alternative pin
const int I2S_MIC_WS = 16;         // Was GPIO17 (LRCLK) - Alternative pin
const int I2S_MIC_SD = 17;         // Was GPIO21 (Data) - Alternative pin

// Status LED pins - Available GPIO on ESP32-S3
const int LED_POWER = 11;          // Green - System powered on
const int LED_SERVER = 12;         // Blue - Connected to server
const int LED_MIC = 13;            // Yellow - Microphone detecting voice
const int LED_SPEAKER = 14;        // Red - Audio playback active

// I2S configuration
const i2s_port_t I2S_PORT = I2S_NUM_0;
const i2s_port_t I2S_MIC_PORT = I2S_NUM_1;
const int BUFFER_SIZE = 1024;
const int DMA_BUFFER_COUNT = 8;
const size_t MIC_BUFFER_SIZE = 1024;
int32_t micBuffer32[MIC_BUFFER_SIZE];  // 32-bit buffer for I2S input
int16_t micBuffer16[MIC_BUFFER_SIZE];  // 16-bit buffer for WebSocket output

// Add a simple moving average filter
const int FILTER_SIZE = 4;
int32_t filter_buffer[FILTER_SIZE];
int filter_index = 0;

// WebSocket clients
WebSocketsClient audioWebSocket;     // For speaker
WebSocketsClient micWebSocket;       // For microphone

// State variables
String commandBuffer = "";
bool isConfigured = false;
bool wsCommandInProgress = false;
unsigned long wsTimeOfLastChar = 0;
const unsigned long WIFI_CHECK_INTERVAL = 30000;

// Add these constants at the top
const int HEARTBEAT_INTERVAL = 15000; // 15 seconds (back to original)
const int HEARTBEAT_TIMEOUT = 3000;   // 3 seconds
const int HEARTBEAT_RETRIES = 2;

// Add animation parameters near other constants
const float ENERGY_SMOOTHING = 0.5;
const float ANIMATION_RESOLUTION = 0.250;
const int IDLE_INTERVAL = 1500;  // 500ms
const int IDLE_VARIANCE = 100;  // ±300ms
const float HEAD_MOVEMENT_RANGE = 0.2;  // 20% movement range

// Add animation state variables
float mouth_next_position = 0.0;
float mouth_current_position = 0.0;
float wing_next_position = 0.0;
float wing_current_position = 0.0;
float head_tilt_next_position = 0.0;
float head_tilt_current_position = 0.0;
float head_rotation_next_position = 0.0;
float head_rotation_current_position = 0.0;
float last_energy = 0.0;
bool head_looking_left = true;
unsigned long last_idle_time = 0;

const uint8_t HEAD_SIDE = 0;
const uint8_t HEAD_TILT = 1;

// Add these variables with other state variables
uint8_t head_movement_type = HEAD_SIDE;
bool is_speaking = false;

// Add a timestamp for animation updates
unsigned long last_animation_update = 0;

// LED timing variables
unsigned long mic_led_timer = 0;
unsigned long speaker_led_timer = 0;

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
}

void audioWebSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
    switch(type) {
        case WStype_CONNECTED:
            Serial.println("Audio WebSocket Connected");
            digitalWrite(LED_SERVER, HIGH);  // Turn on server LED
            break;
            
        case WStype_DISCONNECTED:
            Serial.println("Audio WebSocket Disconnected");
            digitalWrite(LED_SERVER, LOW);   // Turn off server LED
            break;
            
        case WStype_ERROR:
            Serial.println("Audio WebSocket Error - Attempting reconnect");
            audioWebSocket.disconnect();
            delay(1000);
            audioWebSocket.begin(wsHost, wsPortAudio, wsPathAudio);
            break;
            
        case WStype_TEXT:
            // Handle text messages (like ping from server)
            if (length > 0 && strncmp((char*)payload, "ping", 4) == 0) {
                audioWebSocket.sendTXT("pong");
            }
            break;
            
        case WStype_BIN:
            if (isConfigured) {
                // Extend speaker LED timer instead of turning on immediately
                speaker_led_timer = millis() + 500;  // Keep LED on for 500ms after last audio
                digitalWrite(LED_SPEAKER, HIGH);  // Turn on speaker LED
                
                const size_t MAX_CHUNK = 512;
                size_t processed = 0;
                
                while (processed < length) {
                    is_speaking = true;
                    size_t chunk_size = min(MAX_CHUNK, length - processed);
                    
                    // Calculate animation for this chunk
                    calculateAnimationPositions(payload + processed, chunk_size);
                    
                    // Keep extending the LED timer as audio plays
                    speaker_led_timer = millis() + 500;
                    
                    // Create stereo buffer and process audio as before
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
                    if (processed < length) {
                        delay(1);
                    }
                }
                is_speaking = false;
                // Don't turn off LED immediately - let the timer handle it
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

// Global servo objects for direct control
Servo mouthServo;
Servo headTiltServo;  
Servo headRotationServo;
Servo wingServo;
bool servosAttached = false;

void attachServosForControl() {
    if (!servosAttached) {
        mouthServo.attach(MOUTH_PIN);
        headTiltServo.attach(HEAD_TILT_PIN);
        headRotationServo.attach(HEAD_ROTATION_PIN);
        wingServo.attach(WING_PIN);
        servosAttached = true;
        Serial.println("Servos attached for direct control");
    }
}

void testServos() {
    Serial.println("\n=== TESTING SERVOS DIRECTLY ===");
    Servo testServo;
    
    // Test each servo briefly
    int pins[] = {MOUTH_PIN, HEAD_TILT_PIN, HEAD_ROTATION_PIN, WING_PIN};
    const char* names[] = {"Mouth", "Head Tilt", "Head Rotation", "Wing"};
    
    for (int i = 0; i < 4; i++) {
        Serial.print("Testing ");
        Serial.print(names[i]);
        Serial.print(" on GPIO");
        Serial.println(pins[i]);
        
        testServo.attach(pins[i]);
        testServo.writeMicroseconds(1500);  // Center
        delay(300);
        testServo.writeMicroseconds(1600);  // Small movement
        delay(300);
        testServo.writeMicroseconds(1500);  // Back to center
        testServo.detach();
        delay(200);
    }
    Serial.println("=== SERVO TEST COMPLETE ===\n");
}

void initializeServos() {
    // Test servos first
    testServos();
    
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
    for (String cmd : commands) {
        // Add hash for Bottango
        int hash = 0;
        for (int i = 0; i < cmd.length(); i++) {
            hash += cmd.charAt(i);
        }
        cmd += ",h" + String(hash);
        Serial.println("Initializing: " + cmd);
        cmd.toCharArray(cmdBuffer, sizeof(cmdBuffer));
        BottangoCore::processWebSocketCommand(cmdBuffer);
        delay(100);
    }
    BottangoCore::initialized = true;
}

// Add animation helper functions
void calculateAnimationPositions(uint8_t* audio_data, size_t length) {
    // Convert audio bytes to int16 samples
    int16_t* samples = (int16_t*)audio_data;
    size_t sample_count = length / 2;
    
    // Calculate amplitude using percentile-like approach
    int32_t sorted_samples[sample_count];
    for (size_t i = 0; i < sample_count; i++) {
        sorted_samples[i] = abs(samples[i]);
    }
    
    // Simple bubble sort for the 80th percentile (not efficient but works for small samples)
    size_t percentile_index = (sample_count * 80) / 100;
    for (size_t i = 0; i < percentile_index; i++) {
        for (size_t j = 0; j < sample_count - 1; j++) {
            if (sorted_samples[j] > sorted_samples[j + 1]) {
                int32_t temp = sorted_samples[j];
                sorted_samples[j] = sorted_samples[j + 1];
                sorted_samples[j + 1] = temp;
            }
        }
    }
    float amplitude = sorted_samples[percentile_index];
    
    // Calculate energy and smooth it
    float current_energy = min(1.0f, amplitude / 2000.0f);
    float smoothed_energy = (current_energy * (1.0f - ENERGY_SMOOTHING) + 
                           last_energy * ENERGY_SMOOTHING);
    last_energy = smoothed_energy;
    
    // Mouth movement (inverted: 0 = open, 1 = closed)
    mouth_next_position = (amplitude > 800) ? random(0, 50) / 100.0f : 1.0f;
    
    // Wing movement
    float wing_energy = smoothed_energy * 1.2f;
    float wing_base = 0.2f;
    float wing_random = random(-10, 10) / 100.0f;
    wing_next_position = constrain(wing_base + wing_energy * 0.8f + wing_random, 0.0f, 1.0f);
    
    // Head tilt
    float tilt_energy = smoothed_energy * 0.3f;
    head_tilt_next_position = 0.4f + tilt_energy * 0.6f;
    
    // Head rotation - Add more dynamic movement during speech
    float rotation_energy = smoothed_energy * 0.4f;  // Use audio energy for rotation
    float rotation_random = random(-15, 15) / 100.0f;  // Add some randomness
    // Center position (0.5) plus energy-based movement and randomness
    head_rotation_next_position = 0.5f + (rotation_energy * rotation_random);
    // Constrain to valid range
    head_rotation_next_position = constrain(head_rotation_next_position, 0.2f, 0.8f);
}

void updateIdleAnimation() {
    unsigned long current_time = millis();
    
    // Check if it's time for a new idle movement
    if (current_time - last_idle_time >= IDLE_INTERVAL + random(-IDLE_VARIANCE, IDLE_VARIANCE)) {
        // Alternate head looking left and right
        head_looking_left = !head_looking_left;
        head_rotation_next_position = head_looking_left ? 0.3f : 0.7f;
        
        // Random head tilt
        head_tilt_next_position = 0.5f + random(-15, 15) / 100.0f;
        
        // Occasional wing movement
        if (random(100) < 30) {  // 30% chance
            wing_next_position = random(20, 40) / 100.0f;
        } else {
            wing_next_position = 0.0f;
        }
        
        // Mouth stays mostly closed
        mouth_next_position = random(0, 10) / 100.0f;
        
        last_idle_time = current_time;
    }
}

void animation_loop() {
    unsigned long current_time = millis();

    if (current_time - last_animation_update < ANIMATION_RESOLUTION)
        return;
    
    last_animation_update = current_time;
    
    // Attach servos for direct control
    attachServosForControl();
    
    // Debug: Check if we're running idle animation
    static unsigned long lastDebugPrint = 0;
    
    // Handle idle animations when not speaking
    if (!is_speaking) {
       updateIdleAnimation();
       if (millis() - lastDebugPrint > 5000) {
           Serial.println("Idle animation running - positions: Mouth=" + String(mouth_next_position) + 
                         " Wing=" + String(wing_next_position) + 
                         " Tilt=" + String(head_tilt_next_position) + 
                         " Rot=" + String(head_rotation_next_position));
           lastDebugPrint = millis();
       }
    }
    
    // DIRECT SERVO CONTROL - bypass Bottango
    // Map positions (0.0-1.0) to PWM values and write directly
    mouthServo.writeMicroseconds(1450 + (int)(mouth_next_position * 250));  // 1450-1700
    wingServo.writeMicroseconds(1500 + (int)(wing_next_position * 500));     // 1500-2000  
    headTiltServo.writeMicroseconds(850 + (int)(head_tilt_next_position * 1250)); // 850-2100
    headRotationServo.writeMicroseconds(1275 + (int)(head_rotation_next_position * 450)); // 1275-1725
    
    return; // Skip the Bottango command sending below
    char cmdBuffer[MAX_COMMAND_LENGTH];
    String command = "";
    // Update positions with smooth movements
    if (mouth_current_position != mouth_next_position) {
        mouth_current_position = mouth_next_position;

        command = "sCI," + String(MOUTH_PIN) + "," + String(mouth_current_position * 8192);
        // Add a simple hash to make Bottango accept the command
        int hash = 0;
        for (int i = 0; i < command.length(); i++) {
            hash += command.charAt(i);
        }
        command += ",h" + String(hash);
        command.toCharArray(cmdBuffer, sizeof(cmdBuffer));
        Serial.println("Sending: " + command);  // Debug output
        BottangoCore::processWebSocketCommand(cmdBuffer);
    }
    
    if (wing_current_position != wing_next_position) {
        float delta = wing_next_position - wing_current_position;
        wing_current_position += delta * 0.3f;
        command = "sCI," + String(WING_PIN) + "," + String(wing_current_position * 8192);
        // Add hash
        int hash = 0;
        for (int i = 0; i < command.length(); i++) hash += command.charAt(i);
        command += ",h" + String(hash);
        command.toCharArray(cmdBuffer, sizeof(cmdBuffer));        
        BottangoCore::processWebSocketCommand(cmdBuffer);
    }
    
    if (head_tilt_current_position != head_tilt_next_position) {
        float delta = head_tilt_next_position - head_tilt_current_position;
        head_tilt_current_position += delta * 0.4f;
        command = "sCI," + String(HEAD_TILT_PIN) + "," + String(head_tilt_current_position * 8192);
        // Add hash
        int hash = 0;
        for (int i = 0; i < command.length(); i++) hash += command.charAt(i);
        command += ",h" + String(hash);
        command.toCharArray(cmdBuffer, sizeof(cmdBuffer));        
        BottangoCore::processWebSocketCommand(cmdBuffer);
    }
    
    if (head_rotation_current_position != head_rotation_next_position) {
        float delta = head_rotation_next_position - head_rotation_current_position;
        head_rotation_current_position += delta * 0.4f;
        command = "sCI," + String(HEAD_ROTATION_PIN) + "," + String(head_rotation_current_position * 8192);
        // Add hash
        int hash = 0;
        for (int i = 0; i < command.length(); i++) hash += command.charAt(i);
        command += ",h" + String(hash);
        command.toCharArray(cmdBuffer, sizeof(cmdBuffer));        
        BottangoCore::processWebSocketCommand(cmdBuffer);
    }
}

void testSpeaker() {
    Serial.println("\n=== TESTING SPEAKER ===");
    if (!isConfigured) {
        Serial.println("I2S not configured, skipping speaker test");
        return;
    }
    
    // Generate a 1kHz beep for 500ms
    const int freq = 1000;
    const int duration = 500;
    const int sampleRate = 24000;
    const int numSamples = (sampleRate * duration) / 1000;
    
    int16_t* beepBuffer = (int16_t*)malloc(numSamples * 2 * sizeof(int16_t)); // Stereo
    if (!beepBuffer) {
        Serial.println("Failed to allocate beep buffer");
        return;
    }
    
    // Generate sine wave
    for (int i = 0; i < numSamples; i++) {
        int16_t sample = (int16_t)(5000 * sin(2.0 * PI * freq * i / sampleRate));
        beepBuffer[i * 2] = sample;     // Left channel
        beepBuffer[i * 2 + 1] = sample; // Right channel
    }
    
    size_t bytes_written = 0;
    esp_err_t err = i2s_write(I2S_PORT, beepBuffer, numSamples * 2 * sizeof(int16_t), &bytes_written, portMAX_DELAY);
    
    if (err == ESP_OK) {
        Serial.println("Speaker test beep sent (" + String(bytes_written) + " bytes)");
    } else {
        Serial.println("Failed to send beep: " + String(err));
    }
    
    free(beepBuffer);
    Serial.println("=== SPEAKER TEST COMPLETE ===\n");
}

void setup() {
    Serial.begin(115200);
    
    // Initialize status LEDs
    pinMode(LED_POWER, OUTPUT);
    pinMode(LED_SERVER, OUTPUT);
    pinMode(LED_MIC, OUTPUT);
    pinMode(LED_SPEAKER, OUTPUT);
    
    // Turn on power LED immediately
    digitalWrite(LED_POWER, HIGH);
    
    // Turn off other LEDs initially
    digitalWrite(LED_SERVER, LOW);
    digitalWrite(LED_MIC, LOW);
    digitalWrite(LED_SPEAKER, LOW);
    
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
    Serial.println("Connecting to server at: " + String(wsHost) + ":" + String(wsPortAudio));

    // Configure I2S
    configureI2S();
    setupMicI2S();
    
    // Skip test speaker beep
    // testSpeaker();
    
    // Initialize Bottango
    BottangoCore::bottangoSetup();
    initializeServos();
    
    // Audio WebSocket
    Serial.println("Starting Audio WebSocket connection...");
    audioWebSocket.begin(wsHost, wsPortAudio, wsPathAudio);
    audioWebSocket.onEvent(audioWebSocketEvent);
    audioWebSocket.setReconnectInterval(5000);
    audioWebSocket.enableHeartbeat(HEARTBEAT_INTERVAL, HEARTBEAT_TIMEOUT, HEARTBEAT_RETRIES);
    
    // Microphone WebSocket
    Serial.println("Starting Microphone WebSocket connection...");
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
    audioWebSocket.loop();
    micWebSocket.loop();
    
    // Turn off mic LED after timeout
    if (mic_led_timer > 0 && millis() > mic_led_timer) {
        digitalWrite(LED_MIC, LOW);
        mic_led_timer = 0;
    }
    
    // Turn off speaker LED after timeout
    if (speaker_led_timer > 0 && millis() > speaker_led_timer) {
        digitalWrite(LED_SPEAKER, LOW);
        speaker_led_timer = 0;
    }
    
    // Process Bottango commands
    BottangoCore::bottangoLoop();
    
    // Run animation loop for idle movements
    animation_loop();
    
    // Update Bottango effectors
    if (BottangoCore::initialized) {
        BottangoCore::effectorPool.updateAllDriveTargets();
        delay(2); // Give servo library time to process
    } else {
        static unsigned long lastInitCheck = 0;
        if (millis() - lastInitCheck > 5000) {
            Serial.println("WARNING: BottangoCore not initialized!");
            lastInitCheck = millis();
        }
    }
        
    // Handle microphone data with rate limiting
    static unsigned long lastMicRead = 0;
    const unsigned long MIC_READ_INTERVAL = 20;  // 20ms between reads
    
    if (micWebSocket.isConnected() && millis() - lastMicRead >= MIC_READ_INTERVAL) {
        size_t bytes_read = 0;
        esp_err_t result = i2s_read(I2S_MIC_PORT, micBuffer32, sizeof(micBuffer32), &bytes_read, 0);
        
        // Debug info only when needed
        static unsigned long lastMicDebug = 0;
        if (millis() - lastMicDebug > 5000) {  // Every 5 seconds
            // Serial.println("Mic read result: " + String(result) + " bytes: " + String(bytes_read));
            lastMicDebug = millis();
        }
        
        if (result == ESP_OK && bytes_read > 0) {
            // Debug: Check if we're getting any audio level
            int32_t maxVal = 0;
            int32_t minVal = 0;
            for (int i = 0; i < bytes_read/4; i++) {
                if (micBuffer32[i] > maxVal) maxVal = micBuffer32[i];
                if (micBuffer32[i] < minVal) minVal = micBuffer32[i];
            }
            
            // Only log if we have actual audio data
            if (maxVal != 0 || minVal != 0) {
                // Show the actual 32-bit range we're getting
                Serial.println("Mic raw range: " + String(minVal) + " to " + String(maxVal) + 
                              " (bytes: " + String(bytes_read) + ")");
                
                // Light up mic LED only for voice-level audio
                // Voice typically ranges from 5-50 million in our 32-bit range
                // Background noise is usually under 3 million
                long threshold = 5000000;  // Adjust this based on your mic sensitivity
                if (abs(maxVal) > threshold || abs(minVal) > threshold) {
                    digitalWrite(LED_MIC, HIGH);
                    mic_led_timer = millis() + 200;  // Keep LED on for 200ms for better visibility
                }
            } else {
                digitalWrite(LED_MIC, LOW);  // No audio, turn off LED
            }
            
            // Convert 32-bit samples to 16-bit with proper scaling
            size_t sample_count = bytes_read / 4;  // 4 bytes per 32-bit sample
            
            for (size_t i = 0; i < sample_count; i++) {
                // Get 32-bit sample and scale down to 16-bit
                // The INMP441 outputs 24-bit data in 32-bit container, left-aligned
                // So we need to shift right by 16 to get to 16-bit range
                int32_t sample = micBuffer32[i] >> 14;  // Shift by 14 for some headroom
                
                // Clip to 16-bit range
                sample = constrain(sample, -32768, 32767);
                
                // Store in the 16-bit buffer
                micBuffer16[i] = (int16_t)sample;
            }
            
            // Send the 16-bit samples
            micWebSocket.sendBIN((uint8_t*)micBuffer16, sample_count * 2);
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
    
    animation_loop();

    if (BottangoCore::initialized) {
        BottangoCore::effectorPool.updateAllDriveTargets();
    }
    
    delay(2);
}
