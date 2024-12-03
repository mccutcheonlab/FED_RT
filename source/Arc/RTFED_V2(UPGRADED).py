#!/usr/bin/env python
# coding: utf-8

# ## <font color = "deepskyblue"> 1) Install necessary modules and packages and libraries </font>

# In[ ]:


#installing necessary dependencies and packages 
get_ipython().system('pip install pyserial')
get_ipython().system('pip install --upgrade google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client')
get_ipython().system('pip install gspread')


# ## <font color = "deepskyblue"> 2) Once you have your Google Spreadsheet and API credentials ready, replace the fileds based on directories, port numbers, etc on your computer and run the code below</font>

# In[ ]:


import serial
import threading
import datetime
import gspread
from google.oauth2.service_account import Credentials
import time

# Define the column headers based on your desired CSV structure
column_headers = [
    "MM/DD/YYYY hh:mm:ss.SSS", "Temp", "Humidity", "Library_Version", "Session_type",
    "Device_Number", "Battery_Voltage", "Motor_Turns", "FR", "Event", "Active_Poke",
    "Left_Poke_Count", "Right_Poke_Count", "Pellet_Count", "Block_Pellet_Count",
    "Retrieval_Time", "InterPelletInterval", "Poke_Time"
]

# Here we setup the Google Sheets
SCOPE = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/spreadsheets',
         "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]

# Path to your downloaded JSON file
CREDS_FILE = r"/pathway/.json"

# Replace with the ID of your Google Sheets document
SPREADSHEET_ID = "Copy the ID and paste here"

def get_or_create_worksheet(spreadsheet, title):
    try:
        # Try to open the worksheet by title
        sheet = spreadsheet.worksheet(title)
        print(f"Worksheet '{title}' found.")
    except gspread.exceptions.WorksheetNotFound:
        # If the worksheet is not found, create it
        print(f"Worksheet '{title}' not found. Creating a new one.")
        sheet = spreadsheet.add_worksheet(title=title, rows="1000", cols="20")
        sheet.append_row(column_headers)
    return sheet

def read_from_port(ser, worksheet_name):
    cached_data = []  # List to store data when internet is down

    # Initialize Google Sheets client and worksheet outside the loop
    creds = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPE)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    sheet = get_or_create_worksheet(spreadsheet, worksheet_name)

    # Time interval to attempt sending cached data (in seconds)
    send_interval = 5
    last_send_time = time.time()

    while True:
        try:
            # Read data from serial port
            data = ser.readline().decode('utf-8', errors='replace').strip()
            if data:
                data_list = data.split(",")
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                data_list = data_list[1:]  # Skip the FED device timestamp
                print(f"Data from {ser.port}: {data}")

                # Validate data length
                if len(data_list) == len(column_headers) - 1:
                    row_data = [timestamp] + data_list
                    # Add current data to cached_data
                    cached_data.append(row_data)
                else:
                    print(f"Warning: Data length {len(data_list)} does not match header length {len(column_headers) - 1}")
        except Exception as e:
            print(f"Error reading from {ser.port}: {e}")

        # Periodically attempt to send cached data
        current_time = time.time()
        if cached_data and (current_time - last_send_time >= send_interval):
            try:
                # Append all cached data at once for efficiency
                sheet.append_rows(cached_data)
                print(f"Cached data sent to Google Sheets for {ser.port}")
                cached_data.clear()
            except gspread.exceptions.APIError as e:
                error_code = e.response.status_code
                print(f"Failed to send cached data for {ser.port}: {e}")
                if error_code == 429:
                    print("Quota exceeded, backing off...")
                    time.sleep(60)  # Wait before retrying
            except Exception as e:
                print(f"Failed to send cached data for {ser.port}: {e}")
            last_send_time = current_time  # Update last send time
        time.sleep(0.1)  # Small delay to avoid busy waiting

# Define your ports and baud rate
ports = ["COM5"]  # Replace with your COM ports
baud_rate = 115200

# Start reading from each port in a separate thread
for port in ports:
    try:
        worksheet_name = f"Port_{port}"  # Create a unique worksheet name for each port
        # Set a timeout on the serial port
        ser = serial.Serial(port, baud_rate, timeout=1)
        threading.Thread(target=read_from_port, args=(ser, worksheet_name), daemon=True).start()
    except serial.SerialException as e:
        print(f"Failed to open serial port {port}: {e}")

# Keep the main thread alive
while True:
    time.sleep(1)

