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
            text="McCutcheonLab Technologies\nRTFED (Windows OS)",
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
        self.root.title("RTFED(Windows OS)")
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
        self.identification_threads = {}  # Threads for identification before logging
        self.identification_stop_events = {}  # Events to stop identification threads
        self.log_queue = queue.Queue()  # For logging messages
        self.recording_circle = None
        self.recording_label = None
        self.data_to_save = {}
        self.stop_event = threading.Event()  # Event to stop logging threads
        self.logging_active = False
        self.data_saved = False  # Flag to prevent duplicate data saving

        self.gspread_client = None

        self.last_device_check_time = time.time()  # Initialize device check timer

        # Retry parameters
        self.retry_attempts = 5
        self.retry_delay = 2  # seconds

        self.setup_gui()

        # Schedule startup methods after mainloop starts with slight delays
        self.root.after(0, self.update_gui)
        self.root.after(100, self.show_instruction_popup)
        self.root.after(200, self.start_identification_threads)

        # Handle window close event
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def detect_serial_ports(self):
        ports = list(serial.tools.list_ports.comports())
        fed3_ports = []
        for port in ports:
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
        self.experimenter_entry = ttk.Entry(top_frame, textvariable=self.experimenter_name, width=25)
        self.experimenter_entry.grid(column=1, row=0, padx=5, pady=5, sticky=tk.W)

        # Experiment Name
        tk.Label(top_frame, text="Experiment Name:", font=("Cascadia Code", 12, "bold")).grid(column=2, row=0, padx=5, pady=5, sticky=tk.E)
        self.experiment_entry = ttk.Entry(top_frame, textvariable=self.experiment_name, width=25)
        self.experiment_entry.grid(column=3, row=0, padx=5, pady=5, sticky=tk.W)

        # JSON File
        tk.Label(top_frame, text="Google API JSON File:", font=("Cascadia Code", 12, "bold")).grid(column=0, row=1, padx=5, pady=5, sticky=tk.E)
        self.json_entry = ttk.Entry(top_frame, textvariable=self.json_path, width=50)
        self.json_entry.grid(column=1, row=1, columnspan=2, padx=5, pady=5, sticky=tk.W)
        tk.Button(top_frame, text="Browse JSON", command=self.browse_json).grid(column=3, row=1, padx=5, pady=5)

        # Spreadsheet ID
        tk.Label(top_frame, text="Enter Spreadsheet ID:", font=("Cascadia Code", 12, "bold")).grid(column=0, row=2, padx=5, pady=5, sticky=tk.E)
        self.spreadsheet_entry = ttk.Entry(top_frame, textvariable=self.spreadsheet_id, width=50)
        self.spreadsheet_entry.grid(column=1, row=2, columnspan=2, padx=5, pady=5, sticky=tk.W)
        tk.Button(top_frame, text="Browse Data Folder", command=self.browse_folder).grid(column=3, row=2, padx=5, pady=5)

        # Start and Stop Buttons
        tk.Button(top_frame, text="START", bg="green", fg="white", font=("Cascadia Code", 12, "bold"), command=self.start_logging).grid(column=1, row=3, padx=5, pady=5)
        tk.Button(top_frame, text="STOP and SAVE", bg="slategrey", fg="white", font=("Cascadia Code", 12, "bold"), command=self.stop_logging).grid(column=2, row=3, padx=5, pady=5)

        # Make ports_frame scrollable
        ports_frame_container = tk.Frame(main_frame)
        ports_frame_container.pack(pady=10, fill=tk.BOTH, expand=True)

        self.ports_canvas = tk.Canvas(ports_frame_container)
        self.ports_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        ports_scrollbar = ttk.Scrollbar(ports_frame_container, orient="vertical", command=self.ports_canvas.yview)
        ports_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.ports_canvas.configure(yscrollcommand=ports_scrollbar.set)
        self.ports_inner_frame = tk.Frame(self.ports_canvas)

        # Bind the frame's change in size to update the scroll region
        self.ports_inner_frame.bind("<Configure>", lambda e: self.ports_canvas.configure(scrollregion=self.ports_canvas.bbox("all")))

        self.ports_canvas.create_window((0,0), window=self.ports_inner_frame, anchor="nw")

        # Now use self.ports_inner_frame instead of self.ports_frame to hold the devices
        self.ports_frame = self.ports_inner_frame

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
        hyperlink_label = tk.Label(
            bottom_frame,
            text= "Developed by Hamid Taghipourbibalan",
            font= ("Cascadia Code", 8, "italic"),
            cursor="hand2"
        )
        hyperlink_label.pack(pady=2)
        hyperlink_label.bind("<Button-1>",lambda e: self.open_hyperlink("https://www.linkedin.com/in/hamid-taghipourbibalan-b7239088/"))

    def open_hyperlink(self, URL ):
        import webbrowser
        webbrowser.open_new(URL)
        
    def show_instruction_popup(self):
        messagebox.showinfo("Instructions", "Make a right poke or trigger the pellet sensor on each FED3 to find the port!")
        messagebox.showwarning("Caution", "If you need to restart a FED3 during an experiment(e.g. after fixing a jam), we recommend doing it while the internet connection is on")

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

        # Add the indicator canvas
        indicator_canvas = tk.Canvas(frame, width=20, height=20)
        indicator_canvas.grid(column=1, row=0, padx=5)
        indicator_circle = indicator_canvas.create_oval(5, 5, 15, 15, fill="gray")

        self.port_widgets[port] = {
            'status_label': status_label,
            'text_widget': text_widget,
            'indicator_canvas': indicator_canvas,
            'indicator_circle': indicator_circle
        }
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

    def start_identification_threads(self):
        # Start identification threads for each port
        for port in list(self.serial_ports):
            self.start_identification_thread(port)

    def start_identification_thread(self, port):
        if port in self.identification_threads:
            # Identification thread already running
            return

        stop_event = threading.Event()
        self.identification_stop_events[port] = stop_event

        def identification_with_delay():
            time.sleep(1)  # Wait for 1 second before attempting to connect
            self.identification_thread(port, stop_event)

        t = threading.Thread(target=identification_with_delay)
        t.daemon = True
        t.start()
        self.identification_threads[port] = t
        self.log_queue.put(f"Started identification thread for {port}.")

    def stop_identification_threads(self):
        # Stop identification threads
        for port, event in list(self.identification_stop_events.items()):
            event.set()
        for port, t in list(self.identification_threads.items()):
            t.join()
            self.log_queue.put(f"Stopped identification thread for {port}.")
            del self.identification_threads[port]
            del self.identification_stop_events[port]

    def identification_thread(self, port, stop_event):
        # Avoid opening the port if it's already in use
        if port in self.port_threads:
            self.log_queue.put(f"Skipping identification for {port} as it is already in use.")
            return
    
        try:
            ser = serial.Serial(port, 115200, timeout=0.1)
            # Get index of 'Event' column
            event_index_in_headers = column_headers.index("Event")
            event_index_in_data = event_index_in_headers - 1  # Adjust for timestamp
    
            while not stop_event.is_set():
                try:
                    data = ser.readline().decode('utf-8', errors='replace').strip()
                    if data:
                        data_list = data.split(",")
                        data_list = data_list[1:]  # Skip the first item if necessary
                        if len(data_list) == len(column_headers) - 1:
                            event_value = data_list[event_index_in_data].strip()
                            if event_value in ["Right","Pellet"]:
                                # Send message to GUI to trigger indicator
                                self.port_queues[port].put("RIGHT_POKE")
                except serial.SerialException as e:
                    self.log_queue.put(f"Device on {port} disconnected during identification: {e}")
                    break  # Exit the loop and end the thread
                except Exception as e:
                    self.log_queue.put(f"Error in identification thread for {port}: {e}")
        except serial.SerialException as e:
            # Log only if port is truly inaccessible
            if "PermissionError" not in str(e):
                self.log_queue.put(f"Could not open serial port {port} for identification: {e}")
        except Exception as e:
            self.log_queue.put(f"Unexpected error in identification thread for {port}: {e}")
        finally:
            try:
                ser.close()
            except:
                pass


    def start_logging(self):
        # Stop identification threads before starting logging
        self.stop_identification_threads()

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

        # Disable input fields
        self.disable_input_fields()

        # Change recording indicator to ON
        self.canvas.itemconfig(self.recording_circle, fill="yellow")
        self.canvas.itemconfig(self.recording_label, text="Logging...", fill="black")

        # Start serial threads with retry logic
        for port in list(self.serial_ports):
            self.start_logging_for_port(port)

    def disable_input_fields(self):
        self.experimenter_entry.config(state='disabled')
        self.experiment_entry.config(state='disabled')
        self.json_entry.config(state='disabled')
        self.spreadsheet_entry.config(state='disabled')

    def enable_input_fields(self):
        self.experimenter_entry.config(state='normal')
        self.experiment_entry.config(state='normal')
        self.json_entry.config(state='normal')
        self.spreadsheet_entry.config(state='normal')

    def start_logging_for_port(self, port):
        if port in self.port_threads:
            return

        def attempt_connection(retries=self.retry_attempts, delay=self.retry_delay):
            for attempt in range(retries):
                try:
                    ser = serial.Serial(port, 115200, timeout=0.1)
                    self.data_to_save[port] = []
                    t = threading.Thread(target=self.read_from_port, args=(ser, f"Port_{port}", port))
                    t.daemon = True
                    t.start()
                    self.port_threads[port] = t
                    if self.port_widgets[port]['status_label'].cget("text") != "Ready":
                        self.port_widgets[port]['status_label'].config(text="Ready", foreground="green")
                    self.log_queue.put(f"Started logging from {port}.")
                    return
                except serial.SerialException as e:
                    self.log_queue.put(f"Attempt {attempt+1}: Error with port {port}: {e}")
                    time.sleep(delay)
            self.log_queue.put(f"Failed to connect to port {port} after {retries} attempts.")

        threading.Thread(target=attempt_connection).start()

    def stop_logging(self):
        self.stop_event.set()
        self.logging_active = False
        self.log_queue.put("Stopping logging...")

        # Change recording indicator to OFF
        self.canvas.itemconfig(self.recording_circle, fill="red")
        self.canvas.itemconfig(self.recording_label, text="OFF", fill="red")

        # Re-enable input fields
        self.enable_input_fields()

        # Start a background thread to join threads and save data
        threading.Thread(target=self._join_threads_and_exit).start()

    def _join_threads_and_exit(self):
        for t in list(self.port_threads.values()):
            t.join()
        self.log_queue.put("Logging stopped.")

        # Save data
        self.save_all_data()
        self.data_saved = True

        self.root.after(0, self._finalize_exit)

    def _finalize_exit(self):
        messagebox.showinfo("Data Saved", "All data has been saved locally.")
        self.root.after(0, self.root.destroy)

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
            try:
                with open(filename_user, mode='w', newline='') as file:
                    writer = csv.writer(file)
                    writer.writerow(column_headers)
                    writer.writerows(data_rows)
                self.log_queue.put(f"Data saved for {port} at {filename_user}.")
            except Exception as e:
                self.log_queue.put(f"Failed to save data for {port}: {e}")

    def update_gui(self):
        # Update port text widgets
        for port_identifier, q in list(self.port_queues.items()):
            try:
                while True:
                    message = q.get_nowait()
                    if message == "RIGHT_POKE":
                        self.trigger_indicator(port_identifier)
                    else:
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

        # Periodically check device connections every 5 seconds
        current_time = time.time()
        if current_time - self.last_device_check_time >= 5:
            self.check_device_connections()
            self.last_device_check_time = current_time

        self.root.after(100, self.update_gui)

    def check_device_connections(self):
        current_ports = set(self.detect_serial_ports())
        # Check for disconnected devices
        for port in list(self.serial_ports):
            if port not in current_ports:
                self.serial_ports.remove(port)
                if port in self.port_widgets:
                    self.port_widgets[port]['status_label'].config(text="Not Ready", foreground="red")
                self.log_queue.put(f"Device on {port} disconnected.")
                if port in self.port_threads:
                    del self.port_threads[port]
                if port in self.identification_threads:
                    self.identification_stop_events[port].set()
                    self.identification_threads[port].join()
                    del self.identification_threads[port]
                    del self.identification_stop_events[port]

        # Check for newly connected devices
        for port in current_ports:
            if port not in self.serial_ports:
                self.serial_ports.add(port)
                idx = len(self.port_widgets)
                self.initialize_port_widgets(port, idx)
                self.start_identification_thread(port)
                if self.logging_active:
                    self.start_logging_for_port(port)

    def read_from_port(self, ser, worksheet_name, port_identifier):
        try:
            spreadsheet = self.gspread_client.open_by_key(self.spreadsheet_id.get())
            sheet = self.get_or_create_worksheet(spreadsheet, worksheet_name)
            cached_data = []
            send_interval = 5
            last_send_time = time.time()
            jam_event_occurred = False
            device_number = None

            event_index_in_headers = column_headers.index("Event")
            event_index_in_data = event_index_in_headers - 1

            device_number_index_in_headers = column_headers.index("Device_Number")
            device_number_index_in_data = device_number_index_in_headers - 1

            while not self.stop_event.is_set():
                try:
                    data = ser.readline().decode('utf-8', errors='replace').strip()
                except serial.SerialException as e:
                    self.log_queue.put(f"Device on {port_identifier} disconnected: {e}")
                    if port_identifier in self.port_widgets:
                        self.port_widgets[port_identifier]['status_label'].config(text="Not Ready", foreground="red")
                    break
                if data:
                    data_list = data.split(",")
                    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                    data_list = data_list[1:]
                    if len(data_list) == len(column_headers) - 1:
                        row_data = [timestamp] + data_list
                        cached_data.append(row_data)
                        self.port_queues[port_identifier].put(f"Data logged: {data_list}")
                        self.data_to_save[port_identifier].append(row_data)

                        device_number = data_list[device_number_index_in_data].strip()

                        event_value = data_list[event_index_in_data].strip()
                        if event_value == "JAM":
                            jam_event_occurred = True

                        if event_value in ["Right","Pellet"]:
                            self.port_queues[port_identifier].put("RIGHT_POKE")
                    else:
                        self.log_queue.put(f"Warning: Data length mismatch on {port_identifier}")

                current_time = time.time()
                if cached_data and (current_time - last_send_time >= send_interval):
                    try:
                        sheet.append_rows(cached_data)
                        cached_data.clear()

                        if jam_event_occurred:
                            jam_row = [''] * len(column_headers)
                            jam_row[0] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                            jam_row[event_index_in_headers] = "JAM"
                            jam_row[device_number_index_in_headers] = device_number
                            sheet.append_row(jam_row)
                            self.log_queue.put(f"Additional JAM event logged for {port_identifier} due to prior outage.")
                            jam_event_occurred = False
                    except Exception as e:
                        self.log_queue.put(f"Failed to send data to Google Sheets for {port_identifier}: {e}")
                    last_send_time = current_time
                time.sleep(0.01)
        except Exception as e:
            self.log_queue.put(f"Error reading from {ser.port}: {e}")
        finally:
            try:
                ser.close()
                self.log_queue.put(f"Closed serial port {ser.port}")
            except:
                pass

    def get_or_create_worksheet(self, spreadsheet, title):
        try:
            return spreadsheet.worksheet(title)
        except gspread.exceptions.WorksheetNotFound:
            sheet = spreadsheet.add_worksheet(title=title, rows="1000", cols="20")
            sheet.append_row(column_headers)
            return sheet

    def trigger_indicator(self, port_identifier):
        indicator_canvas = self.port_widgets[port_identifier]['indicator_canvas']
        indicator_circle = self.port_widgets[port_identifier]['indicator_circle']
        def blink(times):
            if times > 0:
                current_color = indicator_canvas.itemcget(indicator_circle, 'fill')
                next_color = 'red' if current_color == 'gray' else 'gray'
                indicator_canvas.itemconfig(indicator_circle, fill=next_color)
                self.root.after(250, lambda: blink(times -1))
            else:
                indicator_canvas.itemconfig(indicator_circle, fill='gray')
        blink(6)

    def on_closing(self):
        if not self.data_saved:
            self.stop_identification_threads()
            self.stop_event.set()
            self.logging_active = False
            for t in list(self.identification_threads.values()):
                t.join()
            for t in list(self.port_threads.values()):
                t.join()
            self.save_all_data()
            self.data_saved = True
        self.root.destroy()

# Main execution
if __name__ == "__main__":
    # Splash screen
    splash_root = tk.Tk()
    SplashScreen(splash_root, duration=7000)
    splash_root.after(7000, splash_root.destroy)
    splash_root.mainloop()

    # Main GUI
    root = tk.Tk()
    app = FED3MonitorApp(root)
    root.mainloop()


# In[ ]:




