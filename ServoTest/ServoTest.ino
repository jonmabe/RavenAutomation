#include <ESP32Servo.h>

// Servo configurations
#define MOUTH_PIN 6
#define HEAD_TILT_PIN 5
#define NECK_ROTATION_PIN 8  // Changed to GPIO 8 (GPIO 9 and 10 had issues)
#define WING_PIN 3

#define SERVO_CENTER 90
#define SERVO_MIN 0
#define SERVO_MAX 180

Servo mouthServo;
Servo headTiltServo;
Servo neckServo;
Servo wingServo;

// Current selected servo
Servo* currentServo = nullptr;
String currentServoName = "None";
int currentServoPin = -1;

void setup() {
  Serial.begin(115200);
  while (!Serial) { delay(10); }
  
  Serial.println("=================================");
  Serial.println("Multi-Servo Diagnostic Tool");
  Serial.println("=================================");
  Serial.println();
  Serial.println("FIRST: Select a servo to test:");
  Serial.println("  m - Mouth servo (GPIO 6)");
  Serial.println("  t - Head Tilt servo (GPIO 5)");
  Serial.println("  n - Neck Rotation servo (GPIO 8)");
  Serial.println("  w - Wing servo (GPIO 3)");
  Serial.println("  a - Test ALL servos sequence");
  Serial.println();
  Serial.println("THEN use test commands:");
  Serial.println("  1 - Gentle sweep test (slow)");
  Serial.println("  2 - Vibration unstick");
  Serial.println("  3 - Progressive range test");
  Serial.println("  4 - Manual position (0-180)");
  Serial.println("  5 - Center servo");
  Serial.println("  6 - Detach/reattach servo");
  Serial.println("  7 - Pulse test");
  Serial.println("  8 - Find limits test");
  Serial.println("  9 - HAMMER MODE (aggressive unstick)");
  Serial.println("  0 - PWM SWEEP (direct pulse control)");
  Serial.println("  r - Reset and recalibrate");
  Serial.println("  h - Show this help");
  Serial.println();
  Serial.println("Select a servo first!");
}

void loop() {
  if (Serial.available()) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    
    // Servo selection commands
    if (command == "m") {
      selectServo("Mouth", MOUTH_PIN, &mouthServo);
    } else if (command == "t") {
      selectServo("Head Tilt", HEAD_TILT_PIN, &headTiltServo);
    } else if (command == "n") {
      selectServo("Neck Rotation", NECK_ROTATION_PIN, &neckServo);
    } else if (command == "w") {
      selectServo("Wing", WING_PIN, &wingServo);
    } else if (command == "a") {
      testAllServos();
    }
    // Test commands (only work if servo selected)
    else if (currentServo != nullptr) {
      if (command == "1") {
        gentleSweepTest();
      } else if (command == "2") {
        vibrationUnstick();
      } else if (command == "3") {
        progressiveRangeTest();
      } else if (command == "4") {
        Serial.println("Enter position (0-180):");
        while (!Serial.available()) { delay(10); }
        int pos = Serial.parseInt();
        manualPosition(pos);
      } else if (command == "5") {
        centerServo();
      } else if (command == "6") {
        detachReattach();
      } else if (command == "7") {
        pulseTest();
      } else if (command == "8") {
        findLimits();
      } else if (command == "9") {
        hammerMode();
      } else if (command == "0") {
        pwmSweep();
      } else if (command == "r") {
        resetAndRecalibrate();
      } else if (command == "h") {
        printHelp();
      } else if (command.toInt() >= 0 && command.toInt() <= 180) {
        manualPosition(command.toInt());
      }
    } else {
      Serial.println("Please select a servo first (m/t/n/w)");
    }
  }
}

void selectServo(String name, int pin, Servo* servo) {
  // Detach previous servo if any
  if (currentServo != nullptr) {
    currentServo->detach();
  }
  
  // Attach new servo
  currentServo = servo;
  currentServoName = name;
  currentServoPin = pin;
  
  Serial.println();
  Serial.print("=== Selected: "); Serial.print(name); 
  Serial.print(" servo on GPIO "); Serial.print(pin); Serial.println(" ===");
  
  currentServo->attach(pin, 500, 2500);
  delay(100);
  
  Serial.println("Moving to center position...");
  currentServo->write(SERVO_CENTER);
  delay(1000);
  Serial.println("Ready for test commands!");
}

void testAllServos() {
  Serial.println("\n=== Testing ALL Servos ===");
  Serial.println("Each servo will move to show it's working...");
  
  // Test Mouth
  Serial.println("\n1. Testing Mouth servo (GPIO 6)...");
  mouthServo.attach(MOUTH_PIN, 500, 2500);
  delay(100);
  mouthServo.write(SERVO_CENTER);
  delay(500);
  mouthServo.write(60);
  delay(500);
  mouthServo.write(120);
  delay(500);
  mouthServo.write(SERVO_CENTER);
  delay(500);
  mouthServo.detach();
  
  // Test Head Tilt
  Serial.println("2. Testing Head Tilt servo (GPIO 5)...");
  headTiltServo.attach(HEAD_TILT_PIN, 500, 2500);
  delay(100);
  headTiltServo.write(SERVO_CENTER);
  delay(500);
  headTiltServo.write(60);
  delay(500);
  headTiltServo.write(120);
  delay(500);
  headTiltServo.write(SERVO_CENTER);
  delay(500);
  headTiltServo.detach();
  
  // Test Neck Rotation
  Serial.println("3. Testing Neck Rotation servo (GPIO 8)...");
  neckServo.attach(NECK_ROTATION_PIN, 500, 2500);
  delay(100);
  neckServo.write(SERVO_CENTER);
  delay(500);
  neckServo.write(60);
  delay(500);
  neckServo.write(120);
  delay(500);
  neckServo.write(SERVO_CENTER);
  delay(500);
  neckServo.detach();
  
  // Test Wing
  Serial.println("4. Testing Wing servo (GPIO 3)...");
  wingServo.attach(WING_PIN, 500, 2500);
  delay(100);
  wingServo.write(SERVO_CENTER);
  delay(500);
  wingServo.write(60);
  delay(500);
  wingServo.write(120);
  delay(500);
  wingServo.write(SERVO_CENTER);
  delay(500);
  wingServo.detach();
  
  Serial.println("\nAll servos tested! Select a specific servo to diagnose.");
}

void gentleSweepTest() {
  if (currentServo == nullptr) {
    Serial.println("No servo selected!");
    return;
  }
  
  Serial.print("\n--- Gentle Sweep Test for "); Serial.print(currentServoName); Serial.println(" ---");
  Serial.println("Sweeping slowly from center to limits...");
  
  // Start from center
  currentServo->write(SERVO_CENTER);
  delay(500);
  
  // Sweep right slowly
  Serial.print("Moving right: ");
  for (int pos = SERVO_CENTER; pos <= SERVO_MAX; pos++) {
    currentServo->write(pos);
    if (pos % 10 == 0) { Serial.print(pos); Serial.print(" "); }
    delay(50);
  }
  Serial.println();
  delay(500);
  
  // Sweep left slowly
  Serial.print("Moving left: ");
  for (int pos = SERVO_MAX; pos >= SERVO_MIN; pos--) {
    currentServo->write(pos);
    if (pos % 10 == 0) { Serial.print(pos); Serial.print(" "); }
    delay(50);
  }
  Serial.println();
  delay(500);
  
  // Return to center
  Serial.println("Returning to center...");
  for (int pos = SERVO_MIN; pos <= SERVO_CENTER; pos++) {
    currentServo->write(pos);
    delay(30);
  }
  Serial.println("Sweep test complete!");
}

void vibrationUnstick() {
  if (currentServo == nullptr) {
    Serial.println("No servo selected!");
    return;
  }
  
  Serial.print("\n--- Vibration Unstick for "); Serial.print(currentServoName); Serial.println(" ---");
  Serial.println("Attempting to unstick servo with small vibrations...");
  
  int currentPos = SERVO_CENTER;
  
  // Small vibrations around current position
  for (int cycle = 0; cycle < 10; cycle++) {
    Serial.print("Cycle "); Serial.print(cycle + 1); Serial.println("/10");
    
    for (int i = 0; i < 20; i++) {
      currentServo->write(currentPos + 2);
      delay(20);
      currentServo->write(currentPos - 2);
      delay(20);
    }
    
    // Try to move slightly after vibration
    currentPos += 5;
    if (currentPos > SERVO_MAX) currentPos = SERVO_MIN;
    currentServo->write(currentPos);
    delay(200);
  }
  
  Serial.println("Vibration unstick complete!");
  centerServo();
}

void progressiveRangeTest() {
  if (currentServo == nullptr) {
    Serial.println("No servo selected!");
    return;
  }
  
  Serial.print("\n--- Progressive Range Test for "); Serial.print(currentServoName); Serial.println(" ---");
  Serial.println("Testing range incrementally from center...");
  
  currentServo->write(SERVO_CENTER);
  delay(500);
  
  // Test increasing ranges
  for (int range = 10; range <= 90; range += 10) {
    Serial.print("Testing range ±"); Serial.println(range);
    
    // Move right
    int rightPos = SERVO_CENTER + range;
    if (rightPos > SERVO_MAX) rightPos = SERVO_MAX;
    Serial.print("  Right to: "); Serial.println(rightPos);
    currentServo->write(rightPos);
    delay(1000);
    
    // Move left
    int leftPos = SERVO_CENTER - range;
    if (leftPos < SERVO_MIN) leftPos = SERVO_MIN;
    Serial.print("  Left to: "); Serial.println(leftPos);
    currentServo->write(leftPos);
    delay(1000);
    
    // Back to center
    currentServo->write(SERVO_CENTER);
    delay(500);
  }
  
  Serial.println("Progressive range test complete!");
}

void manualPosition(int pos) {
  if (pos < 0 || pos > 180) {
    Serial.println("Invalid position! Must be 0-180");
    return;
  }
  
  Serial.print("Moving to position: "); Serial.println(pos);
  currentServo->write(pos);
  delay(500);
  Serial.println("Position set!");
}

void centerServo() {
  if (currentServo == nullptr) {
    Serial.println("No servo selected!");
    return;
  }
  
  Serial.print("\n--- Centering "); Serial.print(currentServoName); Serial.println(" Servo ---");
  currentServo->write(SERVO_CENTER);
  delay(500);
  Serial.println("Servo centered at 90 degrees");
}

void detachReattach() {
  if (currentServo == nullptr) {
    Serial.println("No servo selected!");
    return;
  }
  
  Serial.print("\n--- Detach/Reattach Test for "); Serial.print(currentServoName); Serial.println(" ---");
  Serial.println("Detaching servo (will go limp)...");
  currentServo->detach();
  delay(2000);
  
  Serial.println("Reattaching servo...");
  currentServo->attach(currentServoPin, 500, 2500);
  delay(100);
  
  Serial.println("Moving to center...");
  currentServo->write(SERVO_CENTER);
  delay(500);
  Serial.println("Servo reattached and centered!");
}

void pulseTest() {
  if (currentServo == nullptr) {
    Serial.println("No servo selected!");
    return;
  }
  
  Serial.print("\n--- Pulse Test for "); Serial.print(currentServoName); Serial.println(" ---");
  Serial.println("Sending direct PWM pulses...");
  
  for (int pulse = 500; pulse <= 2500; pulse += 250) {
    Serial.print("Pulse width: "); Serial.print(pulse); Serial.println(" microseconds");
    currentServo->writeMicroseconds(pulse);
    delay(1000);
  }
  
  Serial.println("Returning to center...");
  currentServo->write(SERVO_CENTER);
  delay(500);
  Serial.println("Pulse test complete!");
}

void findLimits() {
  if (currentServo == nullptr) {
    Serial.println("No servo selected!");
    return;
  }
  
  Serial.print("\n--- Find Limits Test for "); Serial.print(currentServoName); Serial.println(" ---");
  Serial.println("CAUTION: This will test physical limits");
  Serial.println("Press 'y' to continue, any other key to cancel");
  
  while (!Serial.available()) { delay(10); }
  char confirm = Serial.read();
  while (Serial.available()) Serial.read(); // Clear buffer
  
  if (confirm != 'y' && confirm != 'Y') {
    Serial.println("Test cancelled");
    return;
  }
  
  Serial.println("Starting from center...");
  currentServo->write(SERVO_CENTER);
  delay(1000);
  
  Serial.println("Testing right limit (press any key if stuck)...");
  for (int pos = SERVO_CENTER; pos <= SERVO_MAX; pos += 5) {
    currentServo->write(pos);
    Serial.print("Position: "); Serial.println(pos);
    delay(500);
    
    if (Serial.available()) {
      Serial.read();
      Serial.print("Right limit found at: "); Serial.println(pos - 5);
      break;
    }
  }
  
  delay(1000);
  currentServo->write(SERVO_CENTER);
  delay(1000);
  
  Serial.println("Testing left limit (press any key if stuck)...");
  for (int pos = SERVO_CENTER; pos >= SERVO_MIN; pos -= 5) {
    currentServo->write(pos);
    Serial.print("Position: "); Serial.println(pos);
    delay(500);
    
    if (Serial.available()) {
      Serial.read();
      Serial.print("Left limit found at: "); Serial.println(pos + 5);
      break;
    }
  }
  
  Serial.println("Returning to center...");
  currentServo->write(SERVO_CENTER);
  delay(500);
  Serial.println("Limit test complete!");
}

void resetAndRecalibrate() {
  if (currentServo == nullptr) {
    Serial.println("No servo selected!");
    return;
  }
  
  Serial.print("\n--- Reset and Recalibrate "); Serial.print(currentServoName); Serial.println(" ---");
  
  Serial.println("1. Detaching servo...");
  currentServo->detach();
  delay(1000);
  
  Serial.println("2. Manually center the servo head now");
  Serial.println("   Press any key when centered...");
  while (!Serial.available()) { delay(10); }
  while (Serial.available()) Serial.read();
  
  Serial.println("3. Reattaching with default pulse range...");
  currentServo->attach(currentServoPin, 500, 2500);
  delay(100);
  
  Serial.println("4. Setting to center position (90)...");
  currentServo->write(SERVO_CENTER);
  delay(1000);
  
  Serial.println("5. Testing small movements...");
  for (int i = 0; i < 3; i++) {
    currentServo->write(SERVO_CENTER + 10);
    delay(500);
    currentServo->write(SERVO_CENTER - 10);
    delay(500);
    currentServo->write(SERVO_CENTER);
    delay(500);
  }
  
  Serial.println("Reset and recalibration complete!");
}

void hammerMode() {
  if (currentServo == nullptr) {
    Serial.println("No servo selected!");
    return;
  }
  
  Serial.println("\n=== HAMMER MODE - AGGRESSIVE UNSTICK ===");
  Serial.println("WARNING: This may stress the servo!");
  Serial.println("Press 'y' to continue, any other key to cancel");
  
  while (!Serial.available()) { delay(10); }
  char confirm = Serial.read();
  while (Serial.available()) Serial.read();
  
  if (confirm != 'y' && confirm != 'Y') {
    Serial.println("Cancelled");
    return;
  }
  
  Serial.println("Starting aggressive unstick routine...");
  
  // Phase 1: Rapid oscillation with increasing force
  Serial.println("Phase 1: Rapid oscillation");
  for (int force = 5; force <= 30; force += 5) {
    Serial.print("Force level: "); Serial.println(force);
    for (int i = 0; i < 50; i++) {
      currentServo->write(90 + force);
      delay(10);
      currentServo->write(90 - force);
      delay(10);
    }
  }
  
  // Phase 2: Sharp knocks from different positions
  Serial.println("Phase 2: Position knocks");
  int positions[] = {0, 45, 90, 135, 180};
  for (int basePos : positions) {
    Serial.print("Knocking from position: "); Serial.println(basePos);
    currentServo->write(basePos);
    delay(200);
    
    for (int i = 0; i < 10; i++) {
      // Sharp movement away and back
      if (basePos < 90) {
        currentServo->write(basePos + 40);
      } else {
        currentServo->write(basePos - 40);
      }
      delay(5);
      currentServo->write(basePos);
      delay(15);
    }
  }
  
  // Phase 3: Random chaos movements
  Serial.println("Phase 3: Chaos mode");
  for (int i = 0; i < 100; i++) {
    int randomPos = random(0, 181);
    currentServo->write(randomPos);
    delay(random(5, 50));
  }
  
  // Phase 4: Maximum speed sweeps
  Serial.println("Phase 4: Max speed sweeps");
  for (int sweep = 0; sweep < 5; sweep++) {
    // Fast sweep right
    for (int pos = 0; pos <= 180; pos += 10) {
      currentServo->write(pos);
      delay(5);
    }
    // Fast sweep left
    for (int pos = 180; pos >= 0; pos -= 10) {
      currentServo->write(pos);
      delay(5);
    }
  }
  
  // Phase 5: Resonance finding
  Serial.println("Phase 5: Finding resonance frequency");
  for (int freq = 5; freq <= 100; freq += 5) {
    Serial.print("Testing frequency: "); Serial.print(1000/freq); Serial.println(" Hz");
    for (int i = 0; i < 20; i++) {
      currentServo->write(100);
      delay(freq);
      currentServo->write(80);
      delay(freq);
    }
  }
  
  Serial.println("Returning to center...");
  currentServo->write(90);
  delay(500);
  Serial.println("HAMMER MODE complete!");
}

void pwmSweep() {
  if (currentServo == nullptr) {
    Serial.println("No servo selected!");
    return;
  }
  
  Serial.println("\n=== PWM SWEEP - Direct Pulse Control ===");
  Serial.println("This will sweep through the entire PWM range");
  Serial.println("Watch for where the servo responds...");
  
  // Sweep from very low to very high PWM
  Serial.println("Sweeping from 400 to 2600 microseconds...");
  
  for (int pulse = 400; pulse <= 2600; pulse += 10) {
    if (pulse % 100 == 0) {
      Serial.print("Pulse: "); Serial.print(pulse); Serial.println(" μs");
    }
    currentServo->writeMicroseconds(pulse);
    delay(20);
    
    // Check for user interrupt
    if (Serial.available()) {
      Serial.read();
      Serial.println("Sweep interrupted!");
      break;
    }
  }
  
  delay(500);
  
  // Sweep back
  Serial.println("Sweeping back...");
  for (int pulse = 2600; pulse >= 400; pulse -= 10) {
    if (pulse % 100 == 0) {
      Serial.print("Pulse: "); Serial.print(pulse); Serial.println(" μs");
    }
    currentServo->writeMicroseconds(pulse);
    delay(20);
    
    if (Serial.available()) {
      Serial.read();
      Serial.println("Sweep interrupted!");
      break;
    }
  }
  
  // Return to standard center
  Serial.println("Returning to standard center (1500 μs)...");
  currentServo->writeMicroseconds(1500);
  delay(500);
  Serial.println("PWM sweep complete!");
}

void printHelp() {
  Serial.println("\n=== Help Menu ===");
  Serial.println("SERVO SELECTION:");
  Serial.println("  m - Mouth servo (GPIO 6)");
  Serial.println("  t - Head Tilt servo (GPIO 5)");
  Serial.println("  n - Neck Rotation servo (GPIO 8)");
  Serial.println("  w - Wing servo (GPIO 3)");
  Serial.println("  a - Test ALL servos sequence");
  Serial.println("\nTEST COMMANDS (select servo first):");
  Serial.println("  1 - Gentle sweep: Slowly moves through full range");
  Serial.println("  2 - Vibration: Small rapid movements to unstick");
  Serial.println("  3 - Progressive: Gradually increases range from center");
  Serial.println("  4 - Manual: Move to specific position (0-180)");
  Serial.println("  5 - Center: Return to 90 degrees");
  Serial.println("  6 - Detach/reattach: Power cycle the servo");
  Serial.println("  7 - Pulse test: Direct PWM control");
  Serial.println("  8 - Find limits: Manually find physical limits");
  Serial.println("  9 - HAMMER MODE: Aggressive 5-phase unstick");
  Serial.println("  0 - PWM SWEEP: Full range pulse sweep");
  Serial.println("  r - Reset: Full recalibration procedure");
  Serial.print("\nCurrently selected: ");
  if (currentServo != nullptr) {
    Serial.print(currentServoName); Serial.print(" on GPIO "); Serial.println(currentServoPin);
  } else {
    Serial.println("None");
  }
  Serial.println("\nYou can also type any number 0-180 directly");
}