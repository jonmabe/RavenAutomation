#include <Arduino.h>
#include "driver/i2s.h"

#define I2S_BCLK_PIN 27
#define I2S_WCLK_PIN 26
#define I2S_DOUT_PIN 25

#define SAMPLE_RATE 44100
#define BUFFER_SIZE 64

// Define I2S pins
const i2s_pin_config_t i2s_pin_config = {
    .bck_io_num = 26,    // BCK (Bit Clock)
    .ws_io_num = 25,     // LRCK (Word Select/Left Right Clock)
    .data_out_num = 22,  // DATA (Serial Data)
    .data_in_num = I2S_PIN_NO_CHANGE  // We're not using input
};

void setup() {
    Serial.begin(115200);
    while (!Serial) {
        ; // Wait for serial port to connect
    }
    Serial.println("ESP32 Audio Test");
    
    // Configure I2S
    i2s_config_t i2s_config = {
        .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
        .sample_rate = 44100,
        .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
        .channel_format = I2S_CHANNEL_FMT_RIGHT_LEFT,
        .communication_format = I2S_COMM_FORMAT_STAND_I2S,
        .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
        .dma_buf_count = 8,
        .dma_buf_len = 64,
        .use_apll = false,
        .tx_desc_auto_clear = true,
        .fixed_mclk = 0
    };
    
    // Install and start I2S driver
    if (i2s_driver_install(I2S_NUM_0, &i2s_config, 0, NULL) != ESP_OK) {
        Serial.println("Failed to install I2S driver");
        return;
    }
    
    if (i2s_set_pin(I2S_NUM_0, &i2s_pin_config) != ESP_OK) {
        Serial.println("Failed to set I2S pins");
        return;
    }
    
    Serial.println("I2S initialized successfully");
}

void loop() {
    if (Serial.available()) {
        String command = Serial.readStringUntil('\n');
        command.trim();

        Serial.print("Command: " + command);
        Serial.flush();
        if (command == "PLAY" || command == "PLAY_WAV" || command == "PLAY_TONE") {
            Serial.println("ESP32: READY " + command);
            Serial.flush();
            
            // Start receiving audio data
            while (true) {
                if (Serial.available() >= 2) {
                    uint8_t buffer[2];
                    Serial.readBytes(buffer, 2);
                    int16_t sample = (buffer[1] << 8) | buffer[0];
                    
                    size_t bytes_written;
                    i2s_write(I2S_NUM_0, &sample, sizeof(sample), &bytes_written, portMAX_DELAY);
                }
                
                // Check for STOP command
                if (Serial.available() && Serial.peek() == 'S') {
                    String cmd = Serial.readStringUntil('\n');
                    if (cmd == "STOP" || cmd == "STOP_PLAY") {
                        Serial.println("Playback stopped");
                        break;
                    }
                }
            }
        }
        else if (command == "GENERATE_TONE") {
            // Generate a 440Hz tone
            const int freq = 440;
            const int sample_rate = 44100;
            const float period = (float)sample_rate / freq;
            float phase = 0;
            unsigned long start_time = millis();
            
            Serial.println("ESP32: READY " + command);
            Serial.flush();
            
            while (millis() - start_time < 2000) {
                int16_t sample = 32767 * sin(2 * PI * phase);
                phase += 1.0 / period;
                if (phase >= 1.0) phase -= 1.0;
                
                size_t bytes_written;
                i2s_write(I2S_NUM_0, &sample, sizeof(sample), &bytes_written, portMAX_DELAY);
                
                // Check for STOP command
                if (Serial.available() && Serial.peek() == 'S') {
                    String cmd = Serial.readStringUntil('\n');
                    if (cmd == "STOP" || cmd == "STOP_PLAY") {
                        Serial.println("Playback stopped");
                        break;
                    }
                }
            }
        }
    }
}