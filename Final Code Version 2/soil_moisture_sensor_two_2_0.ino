/*
 * Enhanced Soil Moisture Sensor Reading - Two Sensors
 * 
 * This sketch reads data from two soil moisture sensors connected to analog pins A0 and A1.
 * It includes multiple readings for better accuracy, error detection, sensor calibration,
 * and power management for longer battery life in remote deployments.
 * 
 * Hardware:
 * - Arduino Uno
 * - First soil moisture sensor connected to A0
 * - Second soil moisture sensor connected to A1
 * - Optional: Power control for sensors via digital pins
 */

// Pin definitions
const int moistureSensorA0 = A0;  // First soil moisture sensor on A0
const int moistureSensorA1 = A1;  // Second soil moisture sensor on A1

// Optional power control pins (set to -1 if not using)
const int sensorPowerPinA0 = 7;   // Connect sensor 1 VCC to digital pin 7 for power control
const int sensorPowerPinA1 = 8;   // Connect sensor 2 VCC to digital pin 8 for power control

// Timing variables (non-blocking)
const unsigned long sendInterval = 5000;   // Send data every 5 seconds
const unsigned long powerPrewarmTime = 100; // Time to wait after powering sensor before reading (ms)
unsigned long lastSendTime = 0;

// Calibration values (adjust these based on your sensors)
// Sensor A0 calibration
const int airValueA0 = 1023;    // Value when sensor is in air (dry)
const int waterValueA0 = 300;   // Value when sensor is in water (wet)

// Sensor A1 calibration
const int airValueA1 = 1023;    // Value when sensor is in air (dry)
const int waterValueA1 = 300;   // Value when sensor is in water (wet)

// Reading variables
const int numReadings = 5;    // Number of readings to average for better accuracy
int readingsA0[numReadings];  // Array to store readings for A0
int readingsA1[numReadings];  // Array to store readings for A1
int readIndex = 0;           // Current position in the array
int totalReadingA0 = 0;      // Running total of A0 readings
int totalReadingA1 = 0;      // Running total of A1 readings
int averageReadingA0 = 0;    // Average reading for A0
int averageReadingA1 = 0;    // Average reading for A1

// Data variables
int rawValueA0 = 0;
int rawValueA1 = 0;
int percentageA0 = 0;
int percentageA1 = 0;
int lastGoodReadingA0 = -1;  // Store last valid reading in case of errors
int lastGoodReadingA1 = -1;  // Store last valid reading in case of errors
bool sensorErrorA0 = false;  // Flag for sensor A0 errors
bool sensorErrorA1 = false;  // Flag for sensor A1 errors

void setup() {
  Serial.begin(9600);  // Initialize serial communication
  
  // Wait for serial connection to establish
  while (!Serial) {
    ; // Wait for serial port to connect
  }
  
  // If using power control, set up the power pins
  if (sensorPowerPinA0 != -1) {
    pinMode(sensorPowerPinA0, OUTPUT);
    digitalWrite(sensorPowerPinA0, LOW);  // Start with sensor off to save power
  }
  
  if (sensorPowerPinA1 != -1) {
    pinMode(sensorPowerPinA1, OUTPUT);
    digitalWrite(sensorPowerPinA1, LOW);  // Start with sensor off to save power
  }
  
  // Initialize the readings arrays
  for (int i = 0; i < numReadings; i++) {
    readingsA0[i] = 0;
    readingsA1[i] = 0;
  }
  
  // Print startup message
  Serial.println("Soil Moisture Dual Sensor System Starting");
  Serial.println("Format: timestamp,moisture_A0,moisture_A1");
  
  // Perform initial readings to verify the sensors
  checkSensor(moistureSensorA0, &sensorErrorA0);
  checkSensor(moistureSensorA1, &sensorErrorA1);
}

void loop() {
  // Check if it's time to send data
  if (millis() - lastSendTime >= sendInterval) {
    // Read the moisture sensors
    readSensors();
    
    // Send data
    sendData();
    
    // Update the last send time
    lastSendTime = millis();
  }
}

// Power on a sensor and check if it's responding properly
bool checkSensor(int sensorPin, bool *errorFlag) {
  // Determine which power pin to use based on sensor pin
  int powerPin = (sensorPin == moistureSensorA0) ? sensorPowerPinA0 : sensorPowerPinA1;
  
  // If using power control, turn on the sensor
  if (powerPin != -1) {
    digitalWrite(powerPin, HIGH);
    delay(powerPrewarmTime);  // Give the sensor time to stabilize
  }
  
  // Read the sensor
  int testReading = analogRead(sensorPin);
  
  // If using power control, turn off the sensor to save power
  if (powerPin != -1) {
    digitalWrite(powerPin, LOW);
  }
  
  // Check if reading is reasonable (0 or 1023 often indicate connection issues)
  if (testReading == 0 || testReading == 1023) {
    if (!(*errorFlag)) {  // Only print the first time the error occurs
      Serial.print("ERROR: Sensor on pin A");
      Serial.print(sensorPin - A0);  // Convert analog pin to number (A0 -> 0, A1 -> 1)
      Serial.println(" reading out of expected range. Check connections.");
      *errorFlag = true;
    }
    return false;
  }
  
  *errorFlag = false;
  return true;
}

// Read both soil moisture sensors
void readSensors() {
  // Read sensor A0
  readSensor(moistureSensorA0, sensorPowerPinA0, readingsA0, &totalReadingA0, 
             &rawValueA0, &percentageA0, &lastGoodReadingA0, &sensorErrorA0,
             airValueA0, waterValueA0);
             
  // Read sensor A1
  readSensor(moistureSensorA1, sensorPowerPinA1, readingsA1, &totalReadingA1, 
             &rawValueA1, &percentageA1, &lastGoodReadingA1, &sensorErrorA1,
             airValueA1, waterValueA1);
}

// Read a single soil moisture sensor
void readSensor(int sensorPin, int powerPin, int readings[], int *totalReading,
                int *rawValue, int *percentage, int *lastGoodReading, bool *sensorError,
                int airValue, int waterValue) {
  
  // If using power control, turn on the sensor
  if (powerPin != -1) {
    digitalWrite(powerPin, HIGH);
    delay(powerPrewarmTime);  // Give the sensor time to stabilize
  }
  
  // Check if sensor is working properly
  if (checkSensor(sensorPin, sensorError)) {
    // Take multiple readings for averaging
    *totalReading = *totalReading - readings[readIndex];  // Subtract the old reading
    
    // Read the sensor multiple times and store in temp array
    int tempReadings[numReadings];
    for (int i = 0; i < numReadings; i++) {
      tempReadings[i] = analogRead(sensorPin);
      delay(10); // Short delay between readings
    }
    
    // Sort the readings (simple bubble sort)
    for (int i = 0; i < numReadings - 1; i++) {
      for (int j = 0; j < numReadings - i - 1; j++) {
        if (tempReadings[j] > tempReadings[j + 1]) {
          // Swap values
          int temp = tempReadings[j];
          tempReadings[j] = tempReadings[j + 1];
          tempReadings[j + 1] = temp;
        }
      }
    }
    
    // Use the median reading (middle value after sorting)
    *rawValue = tempReadings[numReadings / 2];
    
    // Update the circular buffer
    readings[readIndex] = *rawValue;
    *totalReading = *totalReading + *rawValue;
    
    // Calculate the rolling average
    int average = *totalReading / numReadings;
    
    // Map the raw value to a percentage (0-100%)
    // Note: Higher analog values mean drier soil
    *percentage = map(average, airValue, waterValue, 0, 100);
    
    // Constrain the percentage to 0-100 range to handle values outside calibration
    *percentage = constrain(*percentage, 0, 100);
    
    // Store this as a good reading
    *lastGoodReading = *rawValue;
  } else {
    // Use the last known good reading if available
    if (*lastGoodReading != -1) {
      *rawValue = *lastGoodReading;
      // Map the raw value to a percentage
      *percentage = map(*rawValue, airValue, waterValue, 0, 100);
      *percentage = constrain(*percentage, 0, 100);
      
      Serial.print("WARNING: Using last good reading for A");
      Serial.print(sensorPin - A0);  // Convert analog pin to number (A0 -> 0, A1 -> 1)
      Serial.print(": ");
      Serial.println(*rawValue);
    }
  }
  
  // If using power control, turn off the sensor to save power
  if (powerPin != -1) {
    digitalWrite(powerPin, LOW);
  }
}

// Send the data in CSV format over serial
void sendData() {
  // Get the current timestamp
  unsigned long timestamp = millis();
  
  // Send data in the format: timestamp,moisture_A0,moisture_A1
  Serial.print(timestamp);
  Serial.print(",");
  Serial.print(rawValueA0);
  Serial.print(",");
  Serial.println(rawValueA1);
}
