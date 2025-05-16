const int moistureSensorA0 = A0;  // First soil moisture sensor on A0
const int moistureSensorA1 = A1;  // Second soil moisture sensor on A1
unsigned long lastSendTime = 0;
const unsigned long sendInterval = 5000;  // Send data every 5 seconds

void setup() {
  Serial.begin(9600);  // Initialize serial communication
  while (!Serial) {
    ; // Wait for serial port to connect
  }
}

void loop() {
  // Check if it's time to send data
  if (millis() - lastSendTime >= sendInterval) {
    // Read the moisture values
    int moistureValueA0 = analogRead(moistureSensorA0);
    int moistureValueA1 = analogRead(moistureSensorA1);
    
    // Get the current timestamp (milliseconds since the Arduino started)
    unsigned long timestamp = millis();
    
    // Send data in the format: timestamp,moisture_A0,moisture_A1
    Serial.print(timestamp);
    Serial.print(",");
    Serial.print(moistureValueA0);
    Serial.print(",");
    Serial.println(moistureValueA1);
    
    // Update the last send time
    lastSendTime = millis();
  }
}
