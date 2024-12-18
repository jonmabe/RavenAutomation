#include <WiFi.h>
#include <WebSocketsClient.h>
#include <driver/i2s.h>

// WiFi credentials
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// WebSocket server details
const char* websocket_server = "your_server_ip";
const uint16_t websocket_port = 8000;

WebSocketsClient webSocket;

// I2S configuration
const i2s_port_t I2S_PORT = I2S_NUM_0;
const int BUFFER_SIZE = 1024;
int16_t sBuffer[BUFFER_SIZE];

// Audio configuration
const int SAMPLE_RATE = 16000;
const int CHANNELS = 1;
const int BITS_PER_SAMPLE = 16;

void setup() {
    Serial.begin(115200);
    
    // Connect to WiFi
    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    Serial.println("WiFi connected");

    // Configure I2S for input (microphone)
    i2s_config_t i2s_config = {
        .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX | I2S_MODE_TX),
        .sample_rate = SAMPLE_RATE,
        .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
        .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
        .communication_format = I2S_COMM_FORMAT_STAND_I2S,
        .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
        .dma_buf_count = 8,
        .dma_buf_len = BUFFER_SIZE,
        .use_apll = false
    };
    
    i2s_pin_config_t pin_config = {
        .bck_io_num = 26,    // Bit clock
        .ws_io_num = 25,     // Word select
        .data_out_num = 22,  // Data out (for speaker)
        .data_in_num = 23    // Data in (for microphone)
    };

    i2s_driver_install(I2S_PORT, &i2s_config, 0, NULL);
    i2s_set_pin(I2S_PORT, &pin_config);
    i2s_start(I2S_PORT);

    // Connect to WebSocket server
    webSocket.begin(websocket_server, websocket_port, "/audio-stream");
    webSocket.onEvent(webSocketEvent);
    webSocket.setReconnectInterval(5000);
}

void loop() {
    webSocket.loop();
    
    if (webSocket.isConnected()) {
        // Read from microphone
        size_t bytesRead = 0;
        i2s_read(I2S_PORT, sBuffer, sizeof(sBuffer), &bytesRead, portMAX_DELAY);
        
        if (bytesRead > 0) {
            // Apply simple noise gate
            if (isAudioAboveThreshold(sBuffer, bytesRead/2)) {
                webSocket.sendBIN((uint8_t*)sBuffer, bytesRead);
            }
        }
    }
}

bool isAudioAboveThreshold(int16_t* buffer, size_t samples) {
    const int16_t THRESHOLD = 500; // Adjust this value based on your microphone
    int32_t sum = 0;
    
    for (size_t i = 0; i < samples; i++) {
        sum += abs(buffer[i]);
    }
    
    int16_t average = sum / samples;
    return average > THRESHOLD;
}

void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
    switch(type) {
        case WStype_DISCONNECTED:
            Serial.println("Disconnected from WebSocket server");
            break;
        case WStype_CONNECTED:
            Serial.println("Connected to WebSocket server");
            break;
        case WStype_BIN:
            playAudio(payload, length);
            break;
    }
}

void playAudio(uint8_t* audio_data, size_t length) {
    size_t bytesWritten = 0;
    i2s_write(I2S_PORT, audio_data, length, &bytesWritten, portMAX_DELAY);
} 