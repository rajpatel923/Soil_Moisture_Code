#!/usr/bin/env python3
import serial
import time
import csv
import os
from datetime import datetime

# Serial connection settings
SERIAL_PORT = '/dev/ttyACM0'  # This might be different on your Pi
BAUD_RATE = 9600

# Local CSV file settings
CSV_FILENAME = 'soil_moisture_data_local_single.csv'
CSV_HEADERS = ['timestamp', 'date_time', 'moisture_raw', 'moisture_percentage']

def create_csv_if_not_exists():
    """Create or verify CSV file with headers."""
    try:
        if not os.path.isfile(CSV_FILENAME):
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(CSV_FILENAME) or '.', exist_ok=True)
            
            # Create the file with headers
            with open(CSV_FILENAME, 'w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(CSV_HEADERS)
            print(f"Created new CSV file: {CSV_FILENAME}")
        else:
            # Check if headers need to be updated
            with open(CSV_FILENAME, 'r') as file:
                reader = csv.reader(file)
                existing_headers = next(reader, None)
            
            if existing_headers != CSV_HEADERS:
                print(f"Headers in CSV need updating. Creating new file.")
                # Backup the old file
                os.rename(CSV_FILENAME, f"{CSV_FILENAME}.bak")
                # Create new file with correct headers
                with open(CSV_FILENAME, 'w', newline='') as file:
                    writer = csv.writer(file)
                    writer.writerow(CSV_HEADERS)
                print(f"Updated CSV file: {CSV_FILENAME}")
            else:
                print(f"Using existing CSV file: {CSV_FILENAME}")
    except Exception as e:
        print(f"Error setting up CSV file: {str(e)}")

def save_to_csv(data):
    """Save a row of data to the CSV file."""
    try:
        with open(CSV_FILENAME, 'a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(data)
        print(f"Data saved to CSV: {data}")
        return True
    except Exception as e:
        print(f"Error saving to CSV: {str(e)}")
        return False

def main():
    print("Starting Soil Moisture Monitoring - Single Sensor (Local Storage Only)")
    print("Press Ctrl+C to exit")
    
    # Set up local CSV file
    create_csv_if_not_exists()
    
    # Attempt to open serial connection to Arduino
    try:
        arduino = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        print(f"Connected to Arduino on {SERIAL_PORT}")
        
        # Give serial connection time to establish
        time.sleep(2)
        
        print("Waiting for data from Arduino...")
        
        while True:
            if arduino.in_waiting > 0:
                # Read line from serial
                line = arduino.readline().decode('utf-8').strip()
                
                if line:
                    # Expected format from Arduino: DATA,raw_value,moisture_percentage
                    parts = line.split(',')
                    
                    if len(parts) == 3 and parts[0] == 'DATA':
                        try:
                            raw_value = parts[1]
                            moisture_percentage = parts[2]
                            
                            # Create timestamp and formatted date/time
                            timestamp = int(time.time())
                            date_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            
                            print(f"Received: Raw={raw_value}, Moisture={moisture_percentage}%")
                            
                            # Prepare data row
                            data_row = [timestamp, date_time, raw_value, moisture_percentage]
                            
                            # Save to CSV
                            save_to_csv(data_row)
                                
                        except ValueError as e:
                            print(f"Error parsing values: {str(e)}")
                    else:
                        print(f"Invalid data format: {line}")
            
            # Small delay to prevent CPU overuse
            time.sleep(0.1)
            
    except serial.SerialException as e:
        print(f"Error opening serial port: {str(e)}")
        print("Check if Arduino is connected and the port is correct.")
        print(f"Current port setting: {SERIAL_PORT}")
        
    except KeyboardInterrupt:
        print("\nProgram terminated by user")
    finally:
        if 'arduino' in locals() and arduino.is_open:
            arduino.close()
            print("Closed Arduino connection")
            
if __name__ == "__main__":
    main()



