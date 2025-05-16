#!/usr/bin/env python3
import serial
import time
import csv
import os
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Serial connection settings
SERIAL_PORT = '/dev/ttyACM0'  # This might be different on your Pi
BAUD_RATE = 9600

# Local CSV file settings
CSV_FILENAME = 'soil_moisture_data.csv'
CSV_HEADERS = ['timestamp', 'date_time', 'moisture_raw', 'moisture_percentage']

# Google Sheets settings
CREDENTIALS_FILE = 'credentials.json'  # Your Google API credentials file
SPREADSHEET_ID = '1xh-K5skSSNAZY8TDhlqyhwn1b_l6Fiw-rHMWqjYrc9k'  # Replace with your actual spreadsheet ID
WORKSHEET_NAME = 'SingleSensorReadings'

def setup_google_sheets():
    """Set up connection to Google Sheets."""
    print("Setting up Google Sheets connection...")
    
    # Set up the credentials with expanded scope
    scope = [
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive',
        'https://www.googleapis.com/auth/spreadsheets'
    ]
    
    try:
        credentials = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
        print(f"Using service account: {credentials.service_account_email}")
        client = gspread.authorize(credentials)
        print("Successfully authorized with Google")
    except Exception as e:
        print(f"Authentication error: {str(e)}")
        return None
    
    # Open spreadsheet by ID
    try:
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        print(f"Successfully opened spreadsheet: {spreadsheet.title}")
        
        # List all worksheets
        worksheets = spreadsheet.worksheets()
        print("Available worksheets:", [ws.title for ws in worksheets])
        
    except Exception as e:
        print(f"Error opening spreadsheet: {str(e)}")
        return None
    
    # Open or create the worksheet
    try:
        worksheet = spreadsheet.worksheet(WORKSHEET_NAME)
        print(f"Found existing worksheet: {WORKSHEET_NAME}")
        
        # Check if the headers match our expected headers
        current_headers = worksheet.row_values(1)
        if current_headers != CSV_HEADERS:
            print(f"Updating worksheet headers from {current_headers} to {CSV_HEADERS}")
            for i, header in enumerate(CSV_HEADERS, start=1):
                worksheet.update_cell(1, i, header)
            
    except Exception as e:
        print(f"Worksheet not found, creating new one: {str(e)}")
        try:
            worksheet = spreadsheet.add_worksheet(title=WORKSHEET_NAME, rows="1000", cols="4")
            worksheet.append_row(CSV_HEADERS)
            print(f"Created new worksheet: {WORKSHEET_NAME}")
        except Exception as e:
            print(f"Error creating worksheet: {str(e)}")
            return None
    
    return worksheet

def create_csv_if_not_exists():
    """Create local CSV file if it doesn't exist."""
    if not os.path.isfile(CSV_FILENAME):
        with open(CSV_FILENAME, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(CSV_HEADERS)
        print(f"Created local CSV file: {CSV_FILENAME}")
    else:
        # Check if we need to update headers in existing file
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
            print(f"Updated local CSV file: {CSV_FILENAME}")
        else:
            print(f"Using existing CSV file: {CSV_FILENAME}")

def upload_to_sheets(worksheet, data):
    """Upload a row of data to Google Sheets."""
    if worksheet is None:
        print("Worksheet not available, skipping upload")
        return False
    
    try:
        worksheet.append_row(data)
        print(f"Successfully uploaded data: {data}")
        # Add a delay to prevent rate limiting
        time.sleep(1)
        return True
    except Exception as e:
        print(f"Failed to upload data: {str(e)}")
        return False

def save_to_csv(data):
    """Save a row of data to the local CSV file."""
    try:
        with open(CSV_FILENAME, 'a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(data)
        print("Saved to local CSV")
        return True
    except Exception as e:
        print(f"Error saving to CSV: {str(e)}")
        return False

def main():
    print("Starting Soil Moisture Monitoring Program - Single Sensor")
    print("Press Ctrl+C to exit")
    
    # Set up local CSV file
    create_csv_if_not_exists()
    
    # Set up Google Sheets
    worksheet = setup_google_sheets()
    
    if worksheet is None:
        print("WARNING: Google Sheets setup failed. Data will only be saved locally.")
    
    # Open serial connection to Arduino
    try:
        arduino = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        print(f"Connected to Arduino on {SERIAL_PORT}")
        
        # Give serial connection time to establish
        time.sleep(2)
        
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
                            
                            # Create timestamp
                            timestamp = int(time.time())
                            date_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            
                            print(f"Received: Raw={raw_value}, Moisture={moisture_percentage}%")
                            
                            # Prepare data row
                            data_row = [timestamp, date_time, raw_value, moisture_percentage]
                            
                            # Save locally
                            save_to_csv(data_row)
                            
                            # Upload to Google Sheets
                            upload_success = upload_to_sheets(worksheet, data_row)
                            
                            if not upload_success and worksheet is not None:
                                # Try refreshing the connection
                                print("Refreshing Google Sheets connection...")
                                worksheet = setup_google_sheets()
                                # Try upload again
                                upload_to_sheets(worksheet, data_row)
                                
                        except ValueError as e:
                            print(f"Error parsing values: {str(e)}")
                    else:
                        print(f"Invalid data format: {line}")
            
            # Small delay to prevent CPU overuse
            time.sleep(0.1)
            
    except serial.SerialException as e:
        print(f"Error opening serial port: {str(e)}")
    except KeyboardInterrupt:
        print("\nProgram terminated by user")
    finally:
        if 'arduino' in locals() and arduino.is_open:
            arduino.close()
            print("Closed Arduino connection")

if __name__ == "__main__":
    main()

