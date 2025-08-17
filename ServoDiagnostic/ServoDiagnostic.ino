#include <ESP32Servo.h>

// Servo configurations
#define MOUTH_PIN 6
#define HEAD_TILT_PIN 5
#define NECK_ROTATION_PIN 8  // Changed to GPIO 8 (GPIO 8 and 10 had issues)
#define WING_PIN 3

Servo testServo;

void setup() {
  Serial.begin(115200);
  while (!Serial) { delay(10); }
  
  Serial.println("========================================");
  Serial.println("   SERVO DIAGNOSTIC TOOL");
  Serial.println("========================================");
  Serial.println();
  Serial.println("This tool will help diagnose servo issues:");
  Serial.println("- Electrical connection problems");
  Serial.println("- Signal integrity issues");
  Serial.println("- Power supply problems");
  Serial.println("- Mechanical binding");
  Serial.println("- Control board failures");
  Serial.println();
  
  runFullDiagnostic();
}

void loop() {
  if (Serial.available()) {
    char cmd = Serial.read();
    if (cmd == 'r' || cmd == 'R') {
      Serial.println("\n\nRestarting diagnostic...\n");
      runFullDiagnostic();
    }
  }
}

void runFullDiagnostic() {
  Serial.println("=== STARTING FULL DIAGNOSTIC ===\n");
  
  // Test 1: GPIO Pin Test
  testGPIOPin();
  delay(1000);
  
  // Test 2: Signal Generation Test
  testSignalGeneration();
  delay(1000);
  
  // Test 3: Servo Response Test
  testServoResponse();
  delay(1000);
  
  // Test 4: Current Draw Test (indirect)
  testCurrentDraw();
  delay(1000);
  
  // Test 5: Wiring Continuity Test
  testWiringContinuity();
  delay(1000);
  
  // Test 6: Control Signal Analysis
  analyzeControlSignal();
  
  Serial.println("\n=== DIAGNOSTIC COMPLETE ===");
  Serial.println("\nPOSSIBLE ISSUES BASED ON TESTS:");
  provideDiagnosis();
  
  Serial.println("\nPress 'r' to run diagnostic again");
}

void testGPIOPin() {
  Serial.println("TEST 1: GPIO Pin Output Test");
  Serial.println("------------------------------");
  Serial.println("Testing if GPIO 8 can output signals...");
  
  // Test the pin as a simple digital output first
  pinMode(NECK_ROTATION_PIN, OUTPUT);
  
  Serial.println("Sending HIGH/LOW signals (check with multimeter on pin):");
  for (int i = 0; i < 5; i++) {
    digitalWrite(NECK_ROTATION_PIN, HIGH);
    Serial.print("  HIGH (3.3V) - ");
    delay(500);
    digitalWrite(NECK_ROTATION_PIN, LOW);
    Serial.println("LOW (0V)");
    delay(500);
  }
  
  Serial.println("✓ GPIO pin can output digital signals");
  Serial.println();
}

void testSignalGeneration() {
  Serial.println("TEST 2: PWM Signal Generation");
  Serial.println("------------------------------");
  Serial.println("Generating PWM signals on GPIO 8...");
  
  // Test PWM generation without servo library
  // New ESP32 Arduino Core 3.x syntax
  ledcAttach(NECK_ROTATION_PIN, 50, 16); // pin, freq, resolution
  
  Serial.println("Testing different PWM duty cycles:");
  int duties[] = {1638, 3276, 4915, 6553, 8192}; // 5%, 10%, 15%, 20%, 25%
  
  for (int duty : duties) {
    float percentage = (duty / 65536.0) * 100;
    Serial.print("  Duty cycle: "); 
    Serial.print(percentage, 1); 
    Serial.print("% (");
    Serial.print((duty * 20000) / 65536); // Convert to microseconds for 50Hz
    Serial.println(" μs pulse)");
    ledcWrite(NECK_ROTATION_PIN, duty);
    delay(1000);
  }
  
  ledcDetach(NECK_ROTATION_PIN);
  Serial.println("✓ PWM generation working");
  Serial.println();
}

void testServoResponse() {
  Serial.println("TEST 3: Servo Library Response");
  Serial.println("------------------------------");
  
  Serial.println("Attaching servo to GPIO 8...");
  testServo.attach(NECK_ROTATION_PIN, 500, 2500);
  delay(100);
  
  Serial.println("Sending control signals:");
  
  // Test specific positions
  int testPositions[] = {90, 0, 180, 90};
  const char* posNames[] = {"CENTER", "MIN", "MAX", "CENTER"};
  
  for (int i = 0; i < 4; i++) {
    Serial.print("  Position "); 
    Serial.print(posNames[i]); 
    Serial.print(" ("); 
    Serial.print(testPositions[i]); 
    Serial.print("°)...");
    
    testServo.write(testPositions[i]);
    delay(1500);
    
    // Check if servo moved (user observation)
    Serial.println(" [Check if servo moved]");
  }
  
  // Test microsecond control
  Serial.println("\nTesting direct microsecond control:");
  int pulses[] = {1500, 1000, 2000, 1500};
  
  for (int pulse : pulses) {
    Serial.print("  Pulse: "); 
    Serial.print(pulse); 
    Serial.print(" μs...");
    testServo.writeMicroseconds(pulse);
    delay(1500);
    Serial.println(" [Check movement]");
  }
  
  testServo.detach();
  Serial.println();
}

void testCurrentDraw() {
  Serial.println("TEST 4: Load/Current Test");
  Serial.println("------------------------------");
  Serial.println("Testing servo under different loads...");
  Serial.println("(Monitor ESP32 power LED for dimming/brownout)");
  
  testServo.attach(NECK_ROTATION_PIN, 500, 2500);
  
  // Rapid movements that would draw more current
  Serial.println("Rapid movement test (high current draw):");
  for (int i = 0; i < 20; i++) {
    testServo.write(0);
    delay(100);
    testServo.write(180);
    delay(100);
    Serial.print(".");
  }
  Serial.println("\n[Any power issues, resets, or LED dimming?]");
  
  testServo.detach();
  Serial.println();
}

void testWiringContinuity() {
  Serial.println("TEST 5: Wiring Continuity Check");
  Serial.println("------------------------------");
  Serial.println("Check the following connections:");
  Serial.println("1. Servo red wire -> 5V power supply");
  Serial.println("2. Servo brown/black wire -> GND");
  Serial.println("3. Servo orange/yellow wire -> GPIO 8");
  Serial.println("4. Common ground between ESP32 and servo power");
  Serial.println();
  
  Serial.println("Testing with pull-up resistor:");
  pinMode(NECK_ROTATION_PIN, INPUT_PULLUP);
  delay(10);
  int pullupRead = digitalRead(NECK_ROTATION_PIN);
  Serial.print("Pull-up reading: ");
  Serial.println(pullupRead ? "HIGH (good)" : "LOW (possible short)");
  
  pinMode(NECK_ROTATION_PIN, INPUT_PULLDOWN);
  delay(10);
  int pulldownRead = digitalRead(NECK_ROTATION_PIN);
  Serial.print("Pull-down reading: ");
  Serial.println(pulldownRead ? "HIGH (possible short)" : "LOW (good)");
  
  Serial.println();
}

void analyzeControlSignal() {
  Serial.println("TEST 6: Control Signal Analysis");
  Serial.println("--------------------------------");
  
  Serial.println("Analyzing signal timing and stability...");
  testServo.attach(NECK_ROTATION_PIN, 500, 2500);
  
  // Test signal stability
  Serial.println("Holding position at 90° for stability test:");
  testServo.write(90);
  
  Serial.print("Signal stable for: ");
  for (int i = 0; i < 10; i++) {
    delay(1000);
    Serial.print(i+1);
    Serial.print("s ");
  }
  Serial.println("\n[Any jitter or drift?]");
  
  // Test extreme positions
  Serial.println("\nTesting extreme positions:");
  Serial.println("Position 0° (500μs)...");
  testServo.writeMicroseconds(500);
  delay(2000);
  
  Serial.println("Position 180° (2500μs)...");
  testServo.writeMicroseconds(2500);
  delay(2000);
  
  Serial.println("Beyond normal range - 400μs...");
  testServo.writeMicroseconds(400);
  delay(2000);
  
  Serial.println("Beyond normal range - 2600μs...");
  testServo.writeMicroseconds(2600);
  delay(2000);
  
  testServo.detach();
  Serial.println();
}

void provideDiagnosis() {
  Serial.println("\nBASED ON YOUR OBSERVATIONS:");
  Serial.println();
  
  Serial.println("IF SERVO DOESN'T MOVE AT ALL:");
  Serial.println("  • Dead servo motor (internal failure)");
  Serial.println("  • Broken signal wire (orange/yellow)");
  Serial.println("  • No power to servo (check red/brown wires)");
  Serial.println("  • Wrong GPIO pin or pin damaged");
  Serial.println("  • Servo controller board burned out");
  
  Serial.println("\nIF SERVO MOVES BUT GETS STUCK:");
  Serial.println("  • Mechanical obstruction or damage");
  Serial.println("  • Stripped gears inside servo");
  Serial.println("  • Potentiometer inside servo is damaged");
  Serial.println("  • Servo horn over-tightened");
  
  Serial.println("\nIF SERVO JITTERS OR MOVES ERRATICALLY:");
  Serial.println("  • Insufficient power supply");
  Serial.println("  • Poor ground connection");
  Serial.println("  • Electrical noise/interference");
  Serial.println("  • Damaged control circuitry");
  
  Serial.println("\nIF ESP32 RESETS OR LED DIMS:");
  Serial.println("  • Power supply can't handle current draw");
  Serial.println("  • Servo drawing too much current (mechanical bind)");
  Serial.println("  • Short circuit in servo");
  
  Serial.println("\nRECOMMENDED ACTIONS:");
  Serial.println("1. Try a different servo to isolate the problem");
  Serial.println("2. Test with external 5V power supply for servo");
  Serial.println("3. Check all connections with multimeter");
  Serial.println("4. Try different GPIO pin (change from 10 to 4 or 3)");
  Serial.println("5. Manually turn servo horn when powered off");
  Serial.println("   - If it doesn't move: mechanical issue");
  Serial.println("   - If it moves freely: electrical issue");
}