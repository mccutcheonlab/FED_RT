import serial
import threading
import datetime  
import gspread
from google.oauth2.service_account import Credentials

# the data coming from serial monitor is separated by "," and stored in one single string
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

# Path to your downloaded JSON file(the file you downloaded making API on google console service)
CREDS_FILE = r""

creds = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPE)
client = gspread.authorize(creds)

# Replace with the ID of your Google Sheets document
# open your spreadsheet on your Google drive, in the address bar, copy the ID which is between "/d/" and "/edit"
SPREADSHEET_ID = ""

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
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    sheet = get_or_create_worksheet(spreadsheet, worksheet_name)
    
    while True:
        data = ser.readline().decode('utf-8').strip()
        data_list = data.split(",")  # Split the data string into a list
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]  # Get current timestamp with milliseconds
        # to sync all the FED units with each other, I tend not to rely on FED clock,
        # Ignore the first field (timestamp from FED device) and use the computer's timestamp
        data_list = data_list[1:]  # Skip the FED device timestamp
        
        print(f"Data from {ser.port}: {data}")

        # Assuming the data matches the order of the remaining column_headers
        if len(data_list) == len(column_headers) - 1:  # -1 because timestamp is added
            # Append the row to Google Sheet
            sheet.append_row([timestamp] + data_list)
        else:
            print(f"Warning: Data length {len(data_list)} does not match header length {len(column_headers) - 1}")

# Define your ports and baud rate
ports = ["COM16"]  # Replace with your COM ports, on Mac systems the port number is different and longer
baud_rate = 115200

# Start reading from each port in a separate thread
for port in ports:
    worksheet_name = f"Port_{port}"  # Create a unique worksheet name for each port
    ser = serial.Serial(port, baud_rate)
    threading.Thread(target=read_from_port, args=(ser, worksheet_name)).start()
