#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import os
import threading
import datetime
import csv
import gspread
from google.oauth2.service_account import Credentials
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import serial
import serial.tools.list_ports
import queue
import time

# Column headers for Google Spreadsheet
column_headers = [
    "MM/DD/YYYY hh:mm:ss.SSS", "Temp", "Humidity", "Library_Version", "Session_type",
    "Device_Number", "Battery_Voltage", "Motor_Turns", "FR", "Event", "Active_Poke",
    "Left_Poke_Count", "Right_Poke_Count", "Pellet_Count", "Block_Pellet_Count",
    "Retrieval_Time", "InterPelletInterval", "Poke_Time"
]

# Google Sheets Scope
SCOPE = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/spreadsheets',
         "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]

# Splash Screen Class
class SplashScreen:
    def __init__(self, root, duration=5000):
        self.root = root
        self.root.overrideredirect(True)
        self.root.attributes("-alpha", 0)

        # Get screen dimensions
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        # Set splash screen to cover the entire screen
        self.root.geometry(f"{screen_width}x{screen_height}+0+0")
        self.root.configure(bg="black")

        # Center the text
        self.label_text = tk.Label(
            self.root,
            text="McCutcheonLab Technologies",
            font=("Cascadia Code", 40, "bold"),
            bg="black",
            fg="violet"
        )
        self.label_text.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        self.fade_in_out(duration)

    def fade_in_out(self, duration):
        self.fade_in(1000, lambda: self.fade_out(duration - 1000, self.close))

    def fade_in(self, time_ms, callback):
        alpha = 0.0
        increment = 1 / (time_ms // 50)
        def fade():
            nonlocal alpha
            if alpha < 1.0:
                alpha += increment
                self.root.attributes("-alpha", alpha)
                self.root.after(50, fade)
            else:
                callback()
        fade()

    def fade_out(self, time_ms, callback):
        alpha = 1.0
        decrement = 1 / (time_ms // 50)
        def fade():
            nonlocal alpha
            if alpha > 0.0:
                alpha -= decrement
                self.root.attributes("-alpha", alpha)
                self.root.after(50, fade)
            else:
                callback()
        fade()

    def close(self):
        self.root.destroy()

# Main GUI Class
class FED3MonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("FED3 Remote Monitor")
        self.root.geometry("900x700")

        # Variables
        self.experimenter_name = tk.StringVar()
        self.experiment_name = tk.StringVar()
        self.json_path = tk.StringVar()
        self.spreadsheet_id = tk.StringVar()
        self.save_path = ""
        self.data_queue = queue.Queue()
        self.serial_ports = set(self.detect_serial_ports())
        self.threads = []
        self.port_widgets = {}
        self.port_queues = {}  # For inter-thread communication
        self.port_threads = {}  # Mapping from port to thread
        self.log_queue = queue.Queue()  # For logging messages
        self.recording_circle = None
        self.recording_label = None
        self.data_to_save = {}
        self.stop_event = threading.Event()  # Event to stop threads
        self.logging_active = False

        self.gspread_client = None

        self.setup_gui()
        self.update_gui()  # Start the GUI update loop

    def detect_serial_ports(self):
        ports = list(serial.tools.list_ports.comports())
        fed3_ports = []
        for port in ports:
            # Debug: Print port details
            #print(f"Port: {port.device}, VID: {port.vid}, PID: {port.pid}, Manufacturer: {port.manufacturer}, Description: {port.description}")
            # Check for VID and PID matching Adafruit Feather M0
            if port.vid == 0x239A and port.pid == 0x800B:
                fed3_ports.append(port.device)
        return fed3_ports

    def setup_gui(self):
        # Main frame to hold all widgets
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Frame for top section
        top_frame = tk.Frame(main_frame)
        top_frame.pack(pady=10)

        # Experimenter Name
        tk.Label(top_frame, text="Your Name:", font=("Cascadia Code", 12, "bold")).grid(column=0, row=0, padx=5, pady=5, sticky=tk.E)
        ttk.Entry(top_frame, textvariable=self.experimenter_name, width=25).grid(column=1, row=0, padx=5, pady=5, sticky=tk.W)

        # Experiment Name
        tk.Label(top_frame, text="Experiment Name:", font=("Cascadia Code", 12, "bold")).grid(column=2, row=0, padx=5, pady=5, sticky=tk.E)
        ttk.Entry(top_frame, textvariable=self.experiment_name, width=25).grid(column=3, row=0, padx=5, pady=5, sticky=tk.W)

        # JSON File
        tk.Label(top_frame, text="Google API JSON File:", font=("Cascadia Code", 12, "bold")).grid(column=0, row=1, padx=5, pady=5, sticky=tk.E)
        ttk.Entry(top_frame, textvariable=self.json_path, width=50).grid(column=1, row=1, columnspan=2, padx=5, pady=5, sticky=tk.W)
        tk.Button(top_frame, text="Browse JSON", command=self.browse_json).grid(column=3, row=1, padx=5, pady=5)

        # Spreadsheet ID
        tk.Label(top_frame, text="Enter Spreadsheet ID:", font=("Cascadia Code", 12, "bold")).grid(column=0, row=2, padx=5, pady=5, sticky=tk.E)
        ttk.Entry(top_frame, textvariable=self.spreadsheet_id, width=50).grid(column=1, row=2, columnspan=2, padx=5, pady=5, sticky=tk.W)

        # Browse Data Folder
        tk.Button(top_frame, text="Browse Data Folder", command=self.browse_folder).grid(column=3, row=2, padx=5, pady=5)

        # Start and Stop Buttons
        tk.Button(top_frame, text="START", bg="green", fg="white", font=("Cascadia Code", 12, "bold"), command=self.start_logging).grid(column=1, row=3, padx=5, pady=5)
        tk.Button(top_frame, text="STOP and SAVE", bg="slategrey", fg="white", font=("Cascadia Code", 12, "bold"), command=self.stop_logging).grid(column=2, row=3, padx=5, pady=5)

        # Port Status Frame
        self.ports_frame = tk.Frame(main_frame)
        self.ports_frame.pack(pady=10)

        if self.serial_ports:
            for idx, port in enumerate(self.serial_ports):
                self.initialize_port_widgets(port, idx)
        else:
            tk.Label(self.ports_frame, text="Connect your FED3 and restart!", font=("Cascadia Code", 12), fg="red").pack()

        # Recording Indicator Frame
        indicator_frame = tk.Frame(main_frame)
        indicator_frame.pack(pady=10)

        self.canvas = tk.Canvas(indicator_frame, width=100, height=100)
        self.canvas.pack()
        self.recording_circle = self.canvas.create_oval(25, 25, 75, 75, fill="Orange")
        self.recording_label = self.canvas.create_text(50, 90, text="Standby", font=("Cascadia Code", 12), fill="black")

        # Log Section
        log_frame = tk.Frame(main_frame)
        log_frame.pack(pady=10, fill=tk.BOTH, expand=True)

        self.log_text = tk.Text(log_frame, height=10, width=100)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        log_scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.configure(yscrollcommand=log_scrollbar.set)

        # Copyright Information
        bottom_frame = tk.Frame(self.root)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X)

        tk.Label(bottom_frame, text="© 2024 McCutcheonLab | UiT | Norway", font=("Cascadia Code", 10), fg="royalblue").pack(pady=5)

    def initialize_port_widgets(self, port, idx=None):
        if port in self.port_widgets:
            # Widgets already initialized
            return

        if idx is None:
            idx = len(self.port_widgets)

        frame = ttk.LabelFrame(self.ports_frame, text=f"Port {port}")
        frame.grid(column=idx % 2, row=idx // 2, padx=10, pady=10, sticky=tk.W)
        status_label = ttk.Label(frame, text="Not Ready", font=("Cascadia Code", 10, "italic"), foreground="red")
        status_label.grid(column=0, row=0, sticky=tk.W)
        text_widget = tk.Text(frame, width=40, height=5)
        text_widget.grid(column=0, row=1, sticky=(tk.N, tk.S, tk.E, tk.W))
        self.port_widgets[port] = {'status_label': status_label, 'text_widget': text_widget}
        self.port_queues[port] = queue.Queue()  # Initialize queue for each port

        # Attempt to open serial port to check readiness
        try:
            ser = serial.Serial(port, 115200, timeout=1)
            ser.close()
            status_label.config(text="Ready", foreground="green")
        except serial.SerialException as e:
            status_label.config(text="Not Ready", foreground="red")
            self.log_queue.put(f"Error with port {port}: {e}")

    def browse_json(self):
        self.json_path.set(filedialog.askopenfilename(title="Select JSON File"))

    def browse_folder(self):
        self.save_path = filedialog.askdirectory(title="Select Folder to Save Data")

    def start_logging(self):
        # Reset stop event and threads list
        self.stop_event.clear()
        self.threads = []
        self.logging_active = True

        # Validate input fields
        if not self.json_path.get() or not self.spreadsheet_id.get():
            messagebox.showerror("Error", "Please provide the JSON file path and Spreadsheet ID.")
            return

        # Set up Google Sheets client
        try:
            creds = Credentials.from_service_account_file(self.json_path.get(), scopes=SCOPE)
            self.gspread_client = gspread.authorize(creds)
            self.log_queue.put("Connected to Google Sheets!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to connect to Google Sheets: {e}")
            return

        # Change recording indicator to ON
        self.canvas.itemconfig(self.recording_circle, fill="yellow")
        self.canvas.itemconfig(self.recording_label, text="Logging...", fill="black")

        # Start serial threads
        for port in self.serial_ports:
            self.start_logging_for_port(port)

    def start_logging_for_port(self, port):
        if port in self.port_threads:
            # Already logging for this port
            return
        try:
            ser = serial.Serial(port, 115200, timeout=0.1)  # Set timeout to 0.1 seconds
            self.data_to_save[port] = []
            t = threading.Thread(target=self.read_from_port, args=(ser, f"Port_{port}", port))
            t.daemon = True
            t.start()
            self.port_threads[port] = t
            # Update status label if not already set to Ready
            if self.port_widgets[port]['status_label'].cget("text") != "Ready":
                self.port_widgets[port]['status_label'].config(text="Ready", foreground="green")
            self.log_queue.put(f"Started logging from {port}.")
        except serial.SerialException as e:
            self.log_queue.put(f"Error with port {port}: {e}")

    def stop_logging(self):
        # Signal threads to stop
        self.stop_event.set()
        self.logging_active = False
        self.log_queue.put("Stopping logging...")

        # Change recording indicator to OFF
        self.canvas.itemconfig(self.recording_circle, fill="red")
        self.canvas.itemconfig(self.recording_label, text="OFF", fill="red")

        # Start a background thread to join threads and save data
        threading.Thread(target=self._join_threads_and_exit).start()

    def _join_threads_and_exit(self):
        for t in self.port_threads.values():
            t.join()
        self.log_queue.put("Logging stopped.")

        # Save data
        self.save_all_data()

        # Use root.after to call GUI methods from the main thread
        self.root.after(0, self._finalize_exit)

    def _finalize_exit(self):
        # Inform the user that data has been saved
        messagebox.showinfo("Data Saved", "All data has been saved locally.")

        # Quit and destroy the GUI
        self.root.quit()
        self.root.destroy()

    def save_all_data(self):
        if not self.save_path:
            self.log_queue.put("Error: No save path specified.")
            return

        current_time = datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        experimenter_name = self.experimenter_name.get().lower().strip()
        experiment_name = self.experiment_name.get().lower().strip()

        experimenter_folder = os.path.join(self.save_path, experimenter_name)
        experiment_folder = os.path.join(experimenter_folder, f"{experiment_name}_{current_time}")
        os.makedirs(experiment_folder, exist_ok=True)

        for port, data_rows in self.data_to_save.items():
            filename_user = f"{experiment_folder}/{port}_{current_time}.csv"
            with open(filename_user, mode='w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(column_headers)
                writer.writerows(data_rows)

    def update_gui(self):
        # Update port text widgets
        for port_identifier, q in self.port_queues.items():
            try:
                while True:
                    message = q.get_nowait()
                    text_widget = self.port_widgets[port_identifier]['text_widget']
                    text_widget.insert(tk.END, message + "\n")
                    text_widget.see(tk.END)
            except queue.Empty:
                pass

        # Update log messages
        try:
            while True:
                log_message = self.log_queue.get_nowait()
                self.log_text.insert(tk.END, f"{datetime.datetime.now()}: {log_message}\n")
                self.log_text.see(tk.END)
        except queue.Empty:
            pass

        # Periodically check device connections
        self.check_device_connections()

        # Schedule the next update
        self.root.after(100, self.update_gui)

    def check_device_connections(self):
        current_ports = set(self.detect_serial_ports())
        # Check for disconnected devices
        for port in list(self.serial_ports):
            if port not in current_ports:
                # Device disconnected
                self.serial_ports.remove(port)
                # Update status label to "Not Ready"
                if port in self.port_widgets:
                    self.port_widgets[port]['status_label'].config(text="Not Ready", foreground="red")
                self.log_queue.put(f"Device on {port} disconnected.")
                # Stop the thread associated with this port
                if port in self.port_threads:
                    # The thread will exit on its own due to exception handling
                    del self.port_threads[port]
        # Check for newly connected devices
        for port in current_ports:
            if port not in self.serial_ports:
                # New device connected
                self.serial_ports.add(port)
                # Initialize widgets and queues for the new port
                idx = len(self.port_widgets)
                self.initialize_port_widgets(port, idx)
                # Start logging from the new device if logging is active
                if self.logging_active:
                    self.start_logging_for_port(port)

    def read_from_port(self, ser, worksheet_name, port_identifier):
        try:
            spreadsheet = self.gspread_client.open_by_key(self.spreadsheet_id.get())
            sheet = self.get_or_create_worksheet(spreadsheet, worksheet_name)
            cached_data = []
            send_interval = 5
            last_send_time = time.time()
            jam_event_occurred = False  # Flag to track JAM events during outage
            device_number = None  # Variable to store Device_Number

            # Get indices for 'Event' and 'Device_Number' columns
            event_index_in_headers = column_headers.index("Event")
            event_index_in_data = event_index_in_headers - 1  # Adjust for timestamp

            device_number_index_in_headers = column_headers.index("Device_Number")
            device_number_index_in_data = device_number_index_in_headers - 1  # Adjust for timestamp

            while not self.stop_event.is_set():
                try:
                    data = ser.readline().decode('utf-8', errors='replace').strip()
                except serial.SerialException as e:
                    # Device disconnected
                    self.log_queue.put(f"Device on {port_identifier} disconnected: {e}")
                    # Update status label to "Not Ready"
                    if port_identifier in self.port_widgets:
                        self.port_widgets[port_identifier]['status_label'].config(text="Not Ready", foreground="red")
                    break  # Exit the loop and end the thread
                if data:
                    data_list = data.split(",")
                    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                    data_list = data_list[1:]  # Skip the first item if necessary
                    if len(data_list) == len(column_headers) - 1:
                        row_data = [timestamp] + data_list
                        cached_data.append(row_data)
                        # Instead of updating GUI directly, put message in queue
                        self.port_queues[port_identifier].put(f"Data logged: {data_list}")
                        self.data_to_save[port_identifier].append(row_data)

                        # Extract Device_Number
                        device_number = data_list[device_number_index_in_data].strip()

                        # Check if the event is a JAM event
                        event_value = data_list[event_index_in_data].strip()
                        if event_value == "JAM":
                            jam_event_occurred = True  # Set the flag if JAM occurs
                    else:
                        self.log_queue.put(f"Warning: Data length mismatch on {port_identifier}")
                # Periodically attempt to send cached data
                current_time = time.time()
                if cached_data and (current_time - last_send_time >= send_interval):
                    try:
                        sheet.append_rows(cached_data)
                        cached_data.clear()

                        # After successful data transmission, check for JAM event
                        if jam_event_occurred:
                            # Create a row with empty strings for all columns
                            jam_row = [''] * len(column_headers)
                            # Set the current timestamp in the first column
                            jam_row[0] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                            # Place 'JAM' in the 'Event' column
                            jam_row[event_index_in_headers] = "JAM"
                            # Include Device_Number
                            jam_row[device_number_index_in_headers] = device_number
                            # Append the JAM event to Google Sheets
                            sheet.append_row(jam_row)
                            # Log the action
                            self.log_queue.put(f"Additional JAM event logged for {port_identifier} due to prior outage.")
                            # Reset the JAM event flag
                            jam_event_occurred = False
                    except Exception as e:
                        self.log_queue.put(f"Failed to send data to Google Sheets for {port_identifier}: {e}")
                    last_send_time = current_time
                # Sleep briefly to prevent CPU overuse
                time.sleep(0.01)
        except Exception as e:
            self.log_queue.put(f"Error reading from {ser.port}: {e}")
        finally:
            ser.close()
            self.log_queue.put(f"Closed serial port {ser.port}")

    def get_or_create_worksheet(self, spreadsheet, title):
        try:
            return spreadsheet.worksheet(title)
        except gspread.exceptions.WorksheetNotFound:
            sheet = spreadsheet.add_worksheet(title=title, rows="1000", cols="20")
            sheet.append_row(column_headers)
            return sheet

# Main execution
if __name__ == "__main__":
    # Splash screen
    splash_root = tk.Tk()
    SplashScreen(splash_root, duration=7000)
    splash_root.after(3000, splash_root.destroy)
    splash_root.mainloop()

    # Main GUI
    root = tk.Tk()
    app = FED3MonitorApp(root)
    root.protocol("WM_DELETE_WINDOW", app.stop_logging)  # Handle window close event
    root.mainloop()


# In[ ]:




