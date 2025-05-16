/*
 * Soil Moisture Sensor Reading - Single Sensor
 * 
 * This sketch reads data from a soil moisture sensor connected to analog pin A0.
 * It converts the raw analog value to a moisture percentage and sends the data
 * via Serial in a structured format for easy parsing by the Raspberry Pi.
 * 
 * Hardware:
 * - Arduino Uno
 * - Soil Moisture Sensor connected to A0
 */

// Pin definitions
const int moistureSensorPin = A0;  // Soil moisture sensor connected to A0

// Timing variables (non-blocking)
const unsigned long readInterval = 5000;  // Read sensor every 5 seconds
unsigned long previousMillis = 0;

// Calibration values (adjust these based on your sensor)
const int airValue = 1023;    // Value when sensor is in air (dry)
const int waterValue = 300;   // Value when sensor is in water (wet)

// Data variables
int rawMoistureValue = 0;
int moisturePercentage = 0;

void setup() {
  // Initialize serial communication at 9600 baud rate
  Serial.begin(9600);
  
  // Wait a moment for serial connection to establish
  delay(1000);
  
  // Print startup message
  Serial.println("Soil Moisture Sensor System Starting");
  Serial.println("Format: DATA,raw_value,moisture_percentage");
}

void loop() {
  // Get current time
  unsigned long currentMillis = millis();
  
  // Check if it's time to read the sensor (every readInterval milliseconds)
  if (currentMillis - previousMillis >= readInterval) {
    // Save the current time
    previousMillis = currentMillis;
    
    // Read the soil moisture sensor
    readSoilMoisture();
    
    // Send data in structured format
    sendData();
  }
}

// Read soil moisture sensor and calculate percentage
void readSoilMoisture() {
  // Read the raw analog value
  rawMoistureValue = analogRead(moistureSensorPin);
  
  // Map the raw value to a percentage (0-100%)
  // Note: The map is inverted because higher analog values mean drier soil
  moisturePercentage = map(rawMoistureValue, airValue, waterValue, 0, 100);
  
  // Constrain the percentage to 0-100 range to handle values outside calibration
  moisturePercentage = constrain(moisturePercentage, 0, 100);
}

// Send the data in a formatted string for easy parsing
void sendData() {
  // Format: DATA,raw_value,moisture_percentage
  Serial.print("DATA,");
  Serial.print(rawMoistureValue);
  Serial.print(",");
  Serial.println(moisturePercentage);
}
 
