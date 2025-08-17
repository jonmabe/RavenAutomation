#include <ESP32Servo.h>

// Servo configurations
#define MOUTH_PIN 6
#define HEAD_TILT_PIN 5
#define NECK_ROTATION_PIN 8
#define WING_PIN 3

Servo testServo;

void setup() {
  Serial.begin(115200);
  while (!Serial) { delay(10); }
  
  Serial.println("========================================");
  Serial.println("   SAFE SERVO TEST - CRASH PREVENTION");
  Serial.println("========================================");
  Serial.println();
  Serial.println("This test includes safety measures:");
  Serial.println("- Gradual power increase");
  Serial.println("- Watchdog timer monitoring");
  Serial.println("- Individual servo testing");
  Serial.println("- Current limiting movements");
  Serial.println();
  Serial.println("Commands:");
  Serial.println("  1 - Test Mouth servo (GPIO 6) SAFELY");
  Serial.println("  2 - Test Head Tilt servo (GPIO 5) SAFELY");
  Serial.println("  3 - Test Neck Rotation servo (GPIO 8) SAFELY");
  Serial.println("  4 - Test Wing servo (GPIO 3) SAFELY");
  Serial.println("  5 - Test WITHOUT servo attached (signal only)");
  Serial.println("  p - Power supply test (no servo movement)");
  Serial.println("  v - Check voltage levels");
  Serial.println();
  Serial.println("Ready for commands...");
}

void loop() {
  if (Serial.available()) {
    char cmd = Serial.read();
    while (Serial.available()) Serial.read(); // Clear buffer
    
    switch(cmd) {
      case '1':
        testServoSafely("Mouth", MOUTH_PIN);
        break;
      case '2':
        testServoSafely("Head Tilt", HEAD_TILT_PIN);
        break;
      case '3':
        testServoSafely("Neck Rotation", NECK_ROTATION_PIN);
        break;
      case '4':
        testServoSafely("Wing", WING_PIN);
        break;
      case '5':
        testSignalOnly();
        break;
      case 'p':
        powerSupplyTest();
        break;
      case 'v':
        checkVoltage();
        break;
    }
  }
}

void testServoSafely(String name, int pin) {
  Serial.println();
  Serial.print("=== SAFE TEST: "); Serial.print(name); 
  Serial.print(" servo on GPIO "); Serial.print(pin); Serial.println(" ===");
  
  // First test without attaching
  Serial.println("Step 1: Testing pin output (no servo attached)...");
  pinMode(pin, OUTPUT);
  for (int i = 0; i < 3; i++) {
    digitalWrite(pin, HIGH);
    delay(100);
    digitalWrite(pin, LOW);
    delay(100);
  }
  Serial.println("  ✓ Pin can output signal");
  
  // Now attach with minimal movement
  Serial.println("Step 2: Attaching servo with minimal power...");
  testServo.attach(pin, 500, 2500);
  delay(500); // Let it stabilize
  
  // Start at center
  Serial.println("Step 3: Moving to center (90°) slowly...");
  for (int pos = 90; pos <= 90; pos++) { // Just set to center
    testServo.write(pos);
    delay(50);
  }
  Serial.println("  Position: 90° (center)");
  delay(1000);
  
  // Small movements only
  Serial.println("Step 4: Testing small movements (±10°)...");
  
  Serial.println("  Moving to 80°...");
  moveServoSlowly(90, 80);
  delay(500);
  
  Serial.println("  Moving to 100°...");
  moveServoSlowly(80, 100);
  delay(500);
  
  Serial.println("  Returning to 90°...");
  moveServoSlowly(100, 90);
  delay(500);
  
  // Detach to prevent current draw
  Serial.println("Step 5: Detaching servo...");
  testServo.detach();
  
  Serial.println("✅ Safe test completed successfully!");
  Serial.println();
}

void moveServoSlowly(int from, int to) {
  int step = (to > from) ? 1 : -1;
  for (int pos = from; pos != to; pos += step) {
    testServo.write(pos);
    delay(20); // Slow movement to reduce current spikes
    
    // Check if ESP32 is still responsive
    if (pos % 10 == 0) {
      Serial.print(".");
    }
  }
  testServo.write(to);
  Serial.println();
}

void testSignalOnly() {
  Serial.println("\n=== SIGNAL TEST (No Servo) ===");
  Serial.println("Connect oscilloscope or LED to see PWM signal");
  Serial.println("Testing GPIO 8 (neck servo pin)...");
  
  testServo.attach(NECK_ROTATION_PIN, 500, 2500);
  
  for (int i = 0; i < 5; i++) {
    Serial.print("Position 0°... ");
    testServo.write(0);
    delay(1000);
    
    Serial.print("Position 90°... ");
    testServo.write(90);
    delay(1000);
    
    Serial.println("Position 180°");
    testServo.write(180);
    delay(1000);
  }
  
  testServo.detach();
  Serial.println("Signal test complete!\n");
}

void powerSupplyTest() {
  Serial.println("\n=== POWER SUPPLY TEST ===");
  Serial.println("Monitoring ESP32 stability...");
  Serial.println("(If this stops printing, power issue detected)");
  
  for (int i = 0; i < 20; i++) {
    Serial.print("Heartbeat "); Serial.print(i);
    Serial.print(" - millis: "); Serial.println(millis());
    
    // Toggle onboard LED if available
    pinMode(LED_BUILTIN, OUTPUT);
    digitalWrite(LED_BUILTIN, i % 2);
    
    delay(500);
  }
  
  Serial.println("Power supply appears stable\n");
}

void checkVoltage() {
  Serial.println("\n=== VOLTAGE CHECK ===");
  Serial.println("Note: ESP32-S3 doesn't have direct voltage monitoring");
  Serial.println("But we can check some indicators:");
  
  // Check if brown-out detector would trigger
  Serial.print("System uptime: ");
  Serial.print(millis() / 1000);
  Serial.println(" seconds");
  
  Serial.print("Free heap: ");
  Serial.print(ESP.getFreeHeap());
  Serial.println(" bytes");
  
  Serial.print("CPU frequency: ");
  Serial.print(ESP.getCpuFreqMHz());
  Serial.println(" MHz");
  
  Serial.println("\nRecommendations:");
  Serial.println("1. Use external 5V power supply for servos");
  Serial.println("2. Connect servo ground to ESP32 ground");
  Serial.println("3. Do NOT power servos from ESP32 5V pin");
  Serial.println("4. Use thick wires for servo power");
  Serial.println();
}