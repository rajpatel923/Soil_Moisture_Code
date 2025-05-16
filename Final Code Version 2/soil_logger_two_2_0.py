#!/usr/bin/env python3
import serial
import time
import csv
import os
import socket
import subprocess
import urllib.request
import queue
from threading import Thread, Lock
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Serial connection settings
SERIAL_PORT = '/dev/ttyACM0'  # This might be different on your Pi
BAUD_RATE = 9600

# Local CSV file settings
CSV_FILENAME = 'soil_moisture_data.csv'
BACKUP_CSV = 'unsent_data.csv'
CSV_HEADERS = ['timestamp', 'date_time', 'moisture_value_A0', 'moisture_value_A1']

# Google Sheets settings
CREDENTIALS_FILE = 'credentials.json'  # Your Google API credentials file
SPREADSHEET_ID = '1xh-K5skSSNAZY8TDhlqyhwn1b_l6Fiw-rHMWqjYrc9k'  # Replace with your actual spreadsheet ID
WORKSHEET_NAME = 'Readings_improved'

# Internet connection settings
CHECK_INTERNET_INTERVAL = 60  # Check internet connection every 60 seconds
RECONNECT_ATTEMPTS = 3        # Number of times to try reconnecting
RECONNECT_DELAY = 5           # Seconds between reconnection attempts

# Queue for storing data that hasn't been sent to Google Sheets
unsent_data_queue = queue.Queue()
queue_lock = Lock()

def check_internet(host="8.8.8.8", port=53, timeout=3):
    """Check if internet connection is available by trying to connect to Google's DNS."""
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except Exception as e:
        print(f"Internet check failed: {str(e)}")
        return False

def try_reconnect_internet():
    """Attempt to reconnect to the internet if connection is lost."""
    print("Attempting to reconnect to the internet...")
    
    # Try resetting the network interface
    for attempt in range(RECONNECT_ATTEMPTS):
        print(f"Reconnection attempt {attempt+1}/{RECONNECT_ATTEMPTS}")
        
        try:
            # For WiFi, you might use these commands
            subprocess.call(["sudo", "ifconfig", "wlan0", "down"])
            time.sleep(1)
            subprocess.call(["sudo", "ifconfig", "wlan0", "up"])
            
            # For Ethernet
            # subprocess.call(["sudo", "ifconfig", "eth0", "down"])
            # time.sleep(1)
            # subprocess.call(["sudo", "ifconfig", "eth0", "up"])
            
            # If using 4G HAT (modify for your specific HAT commands)
            # subprocess.call(["sudo", "your_4g_hat_restart_command"])
            
            time.sleep(RECONNECT_DELAY)
            
            if check_internet():
                print("Successfully reconnected to the internet!")
                return True
        except Exception as e:
            print(f"Error during reconnection attempt: {str(e)}")
    
    print("Failed to reconnect to the internet after multiple attempts")
    return False

def setup_google_sheets():
    """Set up connection to Google Sheets."""
    if not check_internet():
        print("No internet connection available. Skipping Google Sheets setup.")
        return None
        
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

def create_csv_if_not_exists(filename, headers):
    """Create CSV file if it doesn't exist."""
    if not os.path.isfile(filename):
        with open(filename, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(headers)
        print(f"Created CSV file: {filename}")
    else:
        # Check if we need to update headers in existing file
        with open(filename, 'r') as file:
            reader = csv.reader(file)
            existing_headers = next(reader, None)
        
        if existing_headers != headers:
            print(f"Headers in {filename} need updating. Creating new file.")
            # Backup the old file
            os.rename(filename, f"{filename}.bak")
            # Create new file with correct headers
            with open(filename, 'w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(headers)
            print(f"Updated CSV file: {filename}")
        else:
            print(f"Using existing CSV file: {filename}")

def upload_to_sheets(worksheet, data):
    """Upload a row of data to Google Sheets."""
    if worksheet is None:
        # Queue the data for later upload when connection is restored
        with queue_lock:
            unsent_data_queue.put(data)
            save_to_backup_csv(data)
        return False
    
    try:
        worksheet.append_row(data)
        print(f"Successfully uploaded data: {data}")
        # Add a delay to prevent rate limiting
        time.sleep(1)
        return True
    except Exception as e:
        print(f"Failed to upload data: {str(e)}")
        # Queue the data for later upload
        with queue_lock:
            unsent_data_queue.put(data)
            save_to_backup_csv(data)
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
        print(f"Error saving to main CSV: {str(e)}")
        
        # Try creating a directory if it doesn't exist
        try:
            os.makedirs(os.path.dirname(CSV_FILENAME) or '.', exist_ok=True)
            with open(CSV_FILENAME, 'a', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(data)
            print("Successfully saved after creating directory")
            return True
        except Exception as e2:
            print(f"Fatal error saving data: {str(e2)}")
            return False

def save_to_backup_csv(data):
    """Save failed uploads to a backup CSV for later retry."""
    try:
        with open(BACKUP_CSV, 'a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(data)
        print(f"Saved to backup CSV for later upload")
        return True
    except Exception as e:
        print(f"Error saving to backup CSV: {str(e)}")
        
        # Try creating a directory if it doesn't exist
        try:
            os.makedirs(os.path.dirname(BACKUP_CSV) or '.', exist_ok=True)
            with open(BACKUP_CSV, 'a', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(data)
            print("Successfully saved backup after creating directory")
            return True
        except Exception as e2:
            print(f"Fatal error saving backup data: {str(e2)}")
            return False

def process_unsent_data(worksheet):
    """Process any data that couldn't be sent previously."""
    if worksheet is None:
        return
    
    print("Checking for unsent data...")
    
    # Process data from the queue first
    data_processed = 0
    data_count = unsent_data_queue.qsize()
    
    if data_count > 0:
        print(f"Found {data_count} unsent items in memory queue")
        
        while not unsent_data_queue.empty():
            try:
                with queue_lock:
                    data = unsent_data_queue.get(block=False)
                
                success = upload_to_sheets(worksheet, data)
                if success:
                    data_processed += 1
                else:
                    # Put it back in the queue if upload fails
                    with queue_lock:
                        unsent_data_queue.put(data)
                    break  # Stop processing if we encounter an error
            except queue.Empty:
                break
    
    # Process data from backup file if it exists
    if os.path.exists(BACKUP_CSV) and os.path.getsize(BACKUP_CSV) > 0:
        try:
            # Read all data from backup file
            backup_data = []
            with open(BACKUP_CSV, 'r', newline='') as file:
                reader = csv.reader(file)
                next(reader, None)  # Skip header
                for row in reader:
                    if row:  # Only add non-empty rows
                        backup_data.append(row)
            
            if backup_data:
                print(f"Found {len(backup_data)} records in backup CSV")
                
                # Clear the backup file but keep the header
                with open(BACKUP_CSV, 'w', newline='') as file:
                    writer = csv.writer(file)
                    writer.writerow(CSV_HEADERS)
                
                # Try to upload each row
                for row in backup_data:
                    success = upload_to_sheets(worksheet, row)
                    if success:
                        data_processed += 1
                    else:
                        # Save back to backup file if upload fails
                        save_to_backup_csv(row)
                        # Stop processing if we encounter an error
                        break
        except Exception as e:
            print(f"Error processing backup file: {str(e)}")
    
    if data_processed > 0:
        print(f"Successfully processed {data_processed} pending data items")
    
    return data_processed > 0

def internet_monitoring_thread(worksheet_ref):
    """Thread for monitoring internet connection and processing unsent data."""
    last_check_time = 0
    worksheet = worksheet_ref[0]  # Use list to allow updating reference
    
    while True:
        current_time = time.time()
        
        # Check internet connection periodically
        if current_time - last_check_time > CHECK_INTERNET_INTERVAL:
            last_check_time = current_time
            
            if not check_internet():
                print("Internet connection lost or unavailable")
                internet_available = try_reconnect_internet()
                
                if internet_available:
                    # Refresh Google Sheets connection
                    print("Reconnected to internet, refreshing Google Sheets connection")
                    new_worksheet = setup_google_sheets()
                    if new_worksheet:
                        worksheet_ref[0] = new_worksheet
                        worksheet = new_worksheet
                        # Process any data that couldn't be sent while offline
                        process_unsent_data(worksheet)
            else:
                # Internet is available, try to process any unsent data
                if worksheet is None:
                    print("Internet available but Google Sheets connection isn't. Trying to reconnect...")
                    new_worksheet = setup_google_sheets()
                    if new_worksheet:
                        worksheet_ref[0] = new_worksheet
                        worksheet = new_worksheet
                
                if worksheet:
                    process_unsent_data(worksheet)
        
        # Sleep to prevent high CPU usage
        time.sleep(5)

def main():
    print("Starting Enhanced Soil Moisture Monitoring System - Two Sensors")
    print("Press Ctrl+C to exit")
    
    # Set up local CSV files
    create_csv_if_not_exists(CSV_FILENAME, CSV_HEADERS)
    create_csv_if_not_exists(BACKUP_CSV, CSV_HEADERS)
    
    # Check internet connection first
    internet_available = check_internet()
    print(f"Internet connection available: {internet_available}")
    
    # Set up Google Sheets
    worksheet = setup_google_sheets() if internet_available else None
    
    # Use a list to hold the worksheet reference so it can be updated by the monitoring thread
    worksheet_ref = [worksheet]
    
    # Start internet monitoring thread
    monitor_thread = Thread(target=internet_monitoring_thread, args=(worksheet_ref,), daemon=True)
    monitor_thread.start()
    
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
                    # Parse data (format: timestamp,moisture_value_A0,moisture_value_A1)
                    try:
                        parts = line.split(',')
                        if len(parts) == 3:  # Make sure we have all three values
                            timestamp, moisture_value_A0, moisture_value_A1 = parts
                            # Convert timestamp to human-readable date/time
                            date_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            
                            print(f"Received data - Timestamp: {timestamp}, Value A0: {moisture_value_A0}, Value A1: {moisture_value_A1}")
                            
                            # Prepare data row
                            data_row = [timestamp, date_time, moisture_value_A0, moisture_value_A1]
                            
                            # Always save locally first (this is critical for data preservation)
                            save_success = save_to_csv(data_row)
                            if not save_success:
                                print("WARNING: Failed to save to primary CSV. Trying backup...")
                                save_to_backup_csv(data_row)
                            
                            # Upload to Google Sheets if connection is available
                            current_worksheet = worksheet_ref[0]
                            if current_worksheet:
                                upload_success = upload_to_sheets(current_worksheet, data_row)
                                
                                if not upload_success:
                                    print("Google Sheets upload failed. Data saved locally and will be uploaded later.")
                            else:
                                print("Google Sheets connection unavailable. Data saved locally only.")
                                # Queue for later upload
                                with queue_lock:
                                    unsent_data_queue.put(data_row)
                                    save_to_backup_csv(data_row)
                        else:
                            print(f"Invalid data format: expected 3 values but got {len(parts)}: {line}")
                            
                    except ValueError as e:
                        print(f"Invalid data format: {line}, Error: {str(e)}")
            
            # Small delay to prevent CPU overuse
            time.sleep(0.1)
            
    except serial.SerialException as e:
        print(f"Error opening serial port: {str(e)}")
        
        # Try reconnecting to Arduino
        retry_count = 0
        max_retries = 5
        
        while retry_count < max_retries:
            print(f"Attempting to reconnect to Arduino ({retry_count+1}/{max_retries})...")
            time.sleep(5)  # Wait before retry
            
            try:
                arduino = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
                print("Successfully reconnected to Arduino!")
                time.sleep(2)  # Allow connection to stabilize
                break
            except serial.SerialException as e:
                print(f"Reconnection attempt failed: {str(e)}")
                retry_count += 1
        
        if retry_count >= max_retries:
            print("Failed to reconnect to Arduino after multiple attempts. Exiting.")
            return
            
    except KeyboardInterrupt:
        print("\nProgram terminated by user")
    finally:
        if 'arduino' in locals() and arduino.is_open:
            arduino.close()
            print("Closed Arduino connection")

if __name__ == "__main__":
    main()

