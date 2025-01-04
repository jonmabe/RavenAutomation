// !!! DRIVER VERSION: 0.6.4a !!!
// !!! Api Version: 7 !!!

#include "src/BottangoCore.h"
#include "src/BasicCommands.h"
#include <WiFi.h>
#include <WebSocketsClient.h>

// WiFi credentials
const char* ssid = "***REMOVED***";
const char* password = "***REMOVED***";

// WebSocket settings
const char* wsHost = "192.168.1.174";  // Your server IP
const int wsPort = 8080;  // Your WebSocket port
const char* wsPath = "/bottango";  // Your WebSocket path

WebSocketsClient webSocket;
String commandBuffer = "";
bool isConfigured = false;
bool wsCommandInProgress = false;
unsigned long wsTimeOfLastChar = 0;

// Add these constants at the top with other definitions
const int WIFI_RETRY_DELAY = 5000;
const int WIFI_TIMEOUT = 10000;
const unsigned long WIFI_CHECK_INTERVAL = 30000;  // Check every 30 seconds

void initializeServos() {

    BottangoCore::initialized = true;
    BottangoCore::effectorPool.dump();
    Callbacks::onThisControllerStarted();

    // Initialize all servos with their parameters
    const char* commands[] = {
        "rSVPin,14,850,2100,3000,1760",   // Head tilt
        "rSVPin,27,1450,1700,3000,1700",  // Mouth
        "rSVPin,13,1500,2000,3000,2000",   // Wing
        "rSVPin,12,1275,1725,5000,1500"  // Head rotation
    };
    
    char cmdBuffer[MAX_COMMAND_LENGTH];  // Safe buffer for command processing
    for (const char* cmd : commands) {
        Serial.println("Initializing: " + String(cmd));
        strncpy(cmdBuffer, cmd, sizeof(cmdBuffer) - 1);
        cmdBuffer[sizeof(cmdBuffer) - 1] = '\0';  // Ensure null termination
        BottangoCore::processWebSocketCommand(cmdBuffer);
        delay(100);
    }
}

void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
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
    
    // Configure WebSocket client
    webSocket.begin(wsHost, wsPort, wsPath);
    webSocket.onEvent(webSocketEvent);
    webSocket.setReconnectInterval(5000);
    
    Serial.println("WebSocket client started");

    // Initialize servos when we connect
    BottangoCore::bottangoSetup();
    initializeServos();  // Initialize servo parameters
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
    checkWiFiConnection();  // Add this line at the start of loop()
    
    webSocket.loop();  // Handle WebSocket events
    
    // Handle command timeout
    if (wsCommandInProgress && millis() - wsTimeOfLastChar >= READ_TIMEOUT) {
        BasicCommands::printOutputString(BasicCommands::TIMEOUT);
        commandBuffer = "";
        wsCommandInProgress = false;
        wsTimeOfLastChar = 0;
    }
    
    // Update effectors
    if (BottangoCore::initialized) {
        BottangoCore::effectorPool.updateAllDriveTargets();
    }
    
    // Small delay to prevent tight loop
    delay(1);
}
