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
import re
import webbrowser

# Column headers for Google Spreadsheet
column_headers = [
    "MM/DD/YYYY hh:mm:ss.SSS", "Temp", "Humidity", "Library_Version", "Session_type",
    "Device_Number", "Battery_Voltage", "Motor_Turns", "FR", "Event", "Active_Poke",
    "Left_Poke_Count", "Right_Poke_Count", "Pellet_Count", "Block_Pellet_Count",
    "Retrieval_Time", "InterPelletInterval", "Poke_Time"
]

# Google Sheets Scope
SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
]

def trigger_poke(serial_ports):
    # Sends the TRIGGER_POKE command to each port.
    for port in serial_ports:
        try:
            with serial.Serial(port, baudrate=115200, timeout=1) as ser:
                ser.write(b'TRIGGER_POKE\n')
                time.sleep(0.2)
                response = ser.readline().decode().strip()
                print(f"Response from {port}: {response}")
        except Exception as e:
            print(f"Error sending poke command to {port}: {e}")

# Splash Screen Class
class SplashScreen:
    def __init__(self, root, duration=5000):
        self.root = root
        self.root.overrideredirect(True)
        self.root.attributes("-alpha", 0)
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        self.root.geometry(f"{screen_width}x{screen_height}+0+0")
        self.root.configure(bg="black")
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

# Main GUI Application Class
class FED3MonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("RTFED(Windows OS)")
        self.root.geometry("900x700")
        self.dark_mode = False
        self.experimenter_name = tk.StringVar()
        self.experiment_name = tk.StringVar()
        self.json_path = tk.StringVar()
        self.spreadsheet_id = tk.StringVar()
        self.save_path = ""
        self.data_queue = queue.Queue()
        self.serial_ports = set(self.detect_serial_ports())
        self.threads = []
        self.port_widgets = {}
        self.port_queues = {}
        self.port_threads = {}
        self.identification_threads = {}
        self.identification_stop_events = {}
        self.log_queue = queue.Queue()
        self.recording_circle = None
        self.recording_label = None
        self.data_to_save = {}
        self.stop_event = threading.Event()
        self.logging_active = False
        self.data_saved = False
        self.gspread_client = None
        self.last_device_check_time = time.time()
        self.retry_attempts = 5
        self.retry_delay = 2
        self.port_to_device_number = {}
        self.port_to_serial = {}
        self.time_sync_commands = {}
        # Internal counter for fallback device numbering (only used if device returns "SIMULATED_POKE")
        self.next_device_number = 1

        self.setup_gui()
        self.root.after(0, self.update_gui)
        self.root.after(100, self.show_instruction_popup)
        self.root.after(200, self.start_identification_threads)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def detect_serial_ports(self):
        ports = list(serial.tools.list_ports.comports())
        fed3_ports = []
        for port in ports:
            if port.vid == 0x239A and port.pid == 0x800B:
                fed3_ports.append(port.device)
        return fed3_ports

    def setup_gui(self):
        self.main_frame = tk.Frame(self.root, highlightthickness=0, bd=0)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        self.top_frame = tk.Frame(self.main_frame, highlightthickness=0, bd=0)
        self.top_frame.pack(pady=10)
        # Experimenter Name
        self.name_label = tk.Label(self.top_frame, text="Your Name:", font=("Cascadia Code", 12, "bold"))
        self.name_label.grid(column=0, row=0, padx=5, pady=5, sticky=tk.E)
        self.experimenter_entry = tk.Entry(self.top_frame, textvariable=self.experimenter_name, width=25, highlightthickness=0, bd=1)
        self.experimenter_entry.grid(column=1, row=0, padx=5, pady=5, sticky=tk.W)
        # Experiment Name
        self.exp_label = tk.Label(self.top_frame, text="Experiment Name:", font=("Cascadia Code", 12, "bold"))
        self.exp_label.grid(column=2, row=0, padx=5, pady=5, sticky=tk.E)
        self.experiment_entry = tk.Entry(self.top_frame, textvariable=self.experiment_name, width=25, highlightthickness=0, bd=1)
        self.experiment_entry.grid(column=3, row=0, padx=5, pady=5, sticky=tk.W)
        # JSON File
        self.json_label = tk.Label(self.top_frame, text="Google API JSON File:", font=("Cascadia Code", 12, "bold"))
        self.json_label.grid(column=0, row=1, padx=5, pady=5, sticky=tk.E)
        self.json_entry = tk.Entry(self.top_frame, textvariable=self.json_path, width=50, highlightthickness=0, bd=1)
        self.json_entry.grid(column=1, row=1, columnspan=2, padx=5, pady=5, sticky=tk.W)
        self.json_button = tk.Button(self.top_frame, text="Browse JSON", command=self.browse_json)
        self.json_button.grid(column=3, row=1, padx=5, pady=5)
        # Spreadsheet ID
        self.spread_label = tk.Label(self.top_frame, text="Enter Spreadsheet ID:", font=("Cascadia Code", 12, "bold"))
        self.spread_label.grid(column=0, row=2, padx=5, pady=5, sticky=tk.E)
        self.spreadsheet_entry = tk.Entry(self.top_frame, textvariable=self.spreadsheet_id, width=50, highlightthickness=0, bd=1)
        self.spreadsheet_entry.grid(column=1, row=2, columnspan=2, padx=5, pady=5, sticky=tk.W)
        self.folder_button = tk.Button(self.top_frame, text="Browse Data Folder", command=self.browse_folder)
        self.folder_button.grid(column=3, row=2, padx=5, pady=5)
        # Start / Stop / Sync
        self.start_button = tk.Button(self.top_frame, text="START", bg="green", fg="white",
                                      font=("Cascadia Code", 12, "bold"), command=self.start_logging)
        self.start_button.grid(column=1, row=3, padx=5, pady=5)
        self.stop_button = tk.Button(self.top_frame, text="STOP and SAVE", bg="black", fg="red",
                                     font=("Cascadia Code", 12, "bold"), command=self.stop_logging)
        self.stop_button.grid(column=2, row=3, padx=5, pady=5)
        self.sync_time_button = tk.Button(self.top_frame, text="Sync FED3 Time", bg="blue", fg="white",
                                          font=("Cascadia Code", 12, "bold"), command=self.sync_all_device_times)
        self.sync_time_button.grid(column=0, row=3, padx=5, pady=5)
        self.dark_mode_button = tk.Button(self.top_frame, text="Toggle Dark Mode",
                                          command=self.toggle_dark_mode, font=("Cascadia Code", 10))
        self.dark_mode_button.grid(column=3, row=3, padx=5, pady=5)
        # NEW: Add Identify Devices button (Row 4)
        self.identify_devices_button = tk.Button(
            self.top_frame,
            text="Identify Devices",
            bg="orange",
            fg="black",
            font=("Cascadia Code", 12, "bold"),
            command=self.identify_fed3_devices
        )
        self.identify_devices_button.grid(column=0, row=4, padx=5, pady=5)
        self.ports_frame_container = tk.Frame(self.main_frame, highlightthickness=0, bd=0)
        self.ports_frame_container.pack(pady=10, fill=tk.BOTH, expand=True)
        self.ports_canvas = tk.Canvas(self.ports_frame_container, highlightthickness=0, bd=0)
        self.ports_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ports_scrollbar = ttk.Scrollbar(self.ports_frame_container, orient="vertical", command=self.ports_canvas.yview)
        ports_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.ports_canvas.configure(yscrollcommand=ports_scrollbar.set)
        self.ports_inner_frame = tk.Frame(self.ports_canvas, highlightthickness=0, bd=0)
        self.ports_inner_frame.bind("<Configure>", lambda e: self.ports_canvas.configure(scrollregion=self.ports_canvas.bbox("all")))
        self.ports_canvas.create_window((0, 0), window=self.ports_inner_frame, anchor="nw")
        self.ports_frame = self.ports_inner_frame
        if self.serial_ports:
            for idx, port in enumerate(self.serial_ports):
                self.initialize_port_widgets(port, idx)
        else:
            tk.Label(self.ports_frame, text="Connect your FED3 units and restart RTFED!",
                     font=("Cascadia Code", 20), fg="red").pack()
        self.indicator_frame = tk.Frame(self.main_frame, highlightthickness=0, bd=0)
        self.indicator_frame.pack(pady=10)
        self.canvas = tk.Canvas(self.indicator_frame, width=100, height=100, highlightthickness=0, bd=0)
        self.canvas.pack()
        self.recording_circle = self.canvas.create_oval(25, 25, 75, 75, fill="Orange", outline="")
        self.recording_label = self.canvas.create_text(50, 90, text="Standby", font=("Cascadia Code", 12), fill="black")
        self.log_frame = tk.Frame(self.main_frame, highlightthickness=0, bd=0)
        self.log_frame.pack(pady=10, fill=tk.BOTH, expand=True)
        self.log_text = tk.Text(self.log_frame, height=10, width=100, highlightthickness=0, bd=1)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scrollbar = ttk.Scrollbar(self.log_frame, orient="vertical", command=self.log_text.yview)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.configure(yscrollcommand=log_scrollbar.set)
        self.bottom_frame = tk.Frame(self.root, highlightthickness=0, bd=0)
        self.bottom_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.footer_label = tk.Label(self.bottom_frame, text="© 2025 McCutcheonLab | UiT | Norway",
                                     font=("Cascadia Code", 10), fg="royalblue")
        self.footer_label.pack(pady=5)
        self.hyperlink_label = tk.Label(
            self.bottom_frame,
            text="Developed by Hamid Taghipourbibalan",
            font=("Cascadia Code", 8, "italic"),
            cursor="hand2"
        )
        self.hyperlink_label.pack(pady=2)
        self.hyperlink_label.bind("<Button-1>", lambda e: self.open_hyperlink("https://www.linkedin.com/in/hamid-taghipourbibalan-b7239088/"))
        self.apply_theme()

    def open_hyperlink(self, URL):
        webbrowser.open_new(URL)

    def show_instruction_popup(self):
        messagebox.showinfo("Instructions", 
            "1) Have you flashed your FED3 with the RTFED library? You should see the RTS label on your FED3 screen.\n"
            "2) Press the [Identify Devices] button to trigger a poke command on each FED3 and identify devices, If set on Free Feeding mode, wait for the Pellet event to Timeout (60 sec elapsed) before identifying the devices.\n"
            "3) After devices are identified, you can press [Sync FED3 Time] to synchronize all your FED devices!")
        messagebox.showwarning("Caution", 
            "1) If you need to restart a FED3 during an experiment, do it while the internet connection is active.\n"
            "2) Restart and reconnect FED3 units one at a time if needed.\n"
            "3) IT IS VERY IMPORTANT to identify FED3 devices before pressing START or else RTFED will not log data.\n"
            "4) We recommend using a powered USB hub if many FED3 units are connected.")

    def initialize_port_widgets(self, port, idx=None):
        if port in self.port_widgets:
            return
        if idx is None:
            idx = len(self.port_widgets)
        frame = tk.LabelFrame(self.ports_frame, text=f"Port {port}", highlightthickness=0, bd=1,
                              font=("Cascadia Code", 10, "bold"))
        frame.grid(column=idx % 2, row=idx // 2, padx=10, pady=10, sticky=tk.W)
        status_label = tk.Label(frame, text="Not Ready", font=("Cascadia Code", 10, "italic"),
                                fg="red", bd=0, highlightthickness=0)
        status_label.grid(column=0, row=0, sticky=tk.W)
        text_widget = tk.Text(frame, width=40, height=5, highlightthickness=0, bd=1)
        text_widget.grid(column=0, row=1, sticky=(tk.N, tk.S, tk.E, tk.W))
        indicator_canvas = tk.Canvas(frame, width=20, height=20, highlightthickness=0, bd=0)
        indicator_canvas.grid(column=1, row=0, padx=5)
        indicator_circle = indicator_canvas.create_oval(5, 5, 15, 15, fill="gray", outline="")
        self.port_widgets[port] = {
            'frame': frame,
            'status_label': status_label,
            'text_widget': text_widget,
            'indicator_canvas': indicator_canvas,
            'indicator_circle': indicator_circle
        }
        self.port_queues[port] = queue.Queue()
        try:
            ser = serial.Serial(port, 115200, timeout=1)
            ser.close()
            status_label.config(text="Ready", fg="green")
        except serial.SerialException as e:
            status_label.config(text="Not Ready", fg="red")
            self.log_queue.put(f"Error with port {port}: {e}")

    def browse_json(self):
        self.json_path.set(filedialog.askopenfilename(title="Select JSON File"))

    def browse_folder(self):
        self.save_path = filedialog.askdirectory(title="Select Folder to Save Data")

    def start_identification_threads(self):
        for port in list(self.serial_ports):
            self.start_identification_thread(port)

    def start_identification_thread(self, port):
        if port in self.identification_threads:
            return
        stop_event = threading.Event()
        self.identification_stop_events[port] = stop_event
        def identification_with_delay():
            time.sleep(1)
            self.identification_thread(port, stop_event)
        t = threading.Thread(target=identification_with_delay)
        t.daemon = True
        t.start()
        self.identification_threads[port] = t
        self.log_queue.put(f"Started identification thread for {port}.")

    def stop_identification_threads(self):
        for port, event in list(self.identification_stop_events.items()):
            event.set()
        for port, t in list(self.identification_threads.items()):
            t.join()
            self.log_queue.put(f"Stopped identification thread for {port}.")
            del self.identification_threads[port]
            del self.identification_stop_events[port]

    def identification_thread(self, port, stop_event):
        event_index = column_headers.index("Event") - 1
        device_number_index = column_headers.index("Device_Number") - 1
        device_number_found = None
        try:
            ser = serial.Serial(port, 115200, timeout=0.1)
            while not stop_event.is_set():
                try:
                    data = ser.readline().decode('utf-8', errors='replace').strip()
                    if data:
                        data_list = data.split(",")[1:]  # Skip first item
                        if len(data_list) == len(column_headers) - 1:
                            event_value = data_list[event_index].strip()
                            dn = data_list[device_number_index].strip()
                            if event_value in ["Right", "Left", "Pellet", "LeftWithPellet", "RightWithPellet"]:
                                self.port_queues[port].put("RIGHT_POKE")
                            if dn:
                                device_number_found = dn
                                break
                except serial.SerialException as e:
                    self.log_queue.put(f"Device on {port} disconnected during identification: {e}")
                    break
                except Exception as e:
                    self.log_queue.put(f"Error in identification thread for {port}: {e}")
        except serial.SerialException as e:
            if "PermissionError" not in str(e):
                self.log_queue.put(f"Could not open serial port {port} for identification: {e}")
        except Exception as e:
            self.log_queue.put(f"Unexpected error in identification thread for {port}: {e}")
        finally:
            try:
                ser.close()
            except:
                pass
        if device_number_found:
            self.log_queue.put(f"Identified device_number={device_number_found} on port={port}")
            self.register_device_number(port, device_number_found)

    def register_device_number(self, port, device_number):
        self.port_to_device_number[port] = device_number
        if self.logging_active:
            self.start_logging_for_port(port)

    def identify_fed3_devices(self):
        """
        When the user presses the Identify Devices button, stop any existing identification threads
        and trigger a poke on all FED3 devices so that they report their device numbers.
        """
        self.stop_identification_threads()
        if not self.serial_ports:
            self.log_queue.put("No FED3 devices detected.")
            messagebox.showwarning("Warning", "No FED3 devices detected. Connect devices first!")
            return
        self.log_queue.put("Identifying devices by triggering a poke on all connected FED3 devices...")
        threading.Thread(target=self.trigger_poke_for_identification, daemon=True).start()

    def trigger_poke_for_identification(self):
        active_ports = list(self.serial_ports)
        if not active_ports:
            self.log_queue.put("No FED3 devices detected.")
            return
        self.log_queue.put("Triggering poke on all connected FED3 devices for identification...")
        for port in active_ports:
            try:
                with serial.Serial(port, baudrate=115200, timeout=1) as ser:
                    ser.write(b'TRIGGER_POKE\n')
                    start_time = time.time()
                    device_number = None
                    # Wait up to 3 seconds for a valid CSV line to appear
                    while time.time() - start_time < 3:
                        line = ser.readline().decode('utf-8', errors='replace').strip()
                        if line:
                            self.log_queue.put(f"Received from {port}: {line}")
                            # Look for a CSV line by checking for commas
                            if "," in line:
                                data_list = line.split(",")
                                # For devices with a temperature sensor the CSV row is expected to be:
                                # [DateTime, Temp, Humidity, Library_Version, Session_type, Device_Number, ...]
                                # So the device number should be at index 5.
                                if len(data_list) >= 6:
                                    device_number = data_list[5].strip()
                                    break
                    if device_number:
                        self.register_device_number(port, device_number)
                        self.log_queue.put(f"Identified device_number={device_number} on port={port}")
                    else:
                        self.log_queue.put(f"No valid device number received from {port}.")
            except Exception as e:
                self.log_queue.put(f"Error sending poke command to {port}: {e}")
        self.log_queue.put("Identification process complete.")


    def start_logging(self):
        self.stop_identification_threads()
        self.stop_event.clear()
        self.logging_active = True
        if not self.json_path.get() or not self.spreadsheet_id.get():
            messagebox.showerror("Error", "Please provide the JSON file path and Spreadsheet ID.")
            return
        experimenter_name = re.sub(r'[<>:"/\\|?*]', '_', self.experimenter_name.get().strip().lower())
        experiment_name = re.sub(r'[<>:"/\\|?*]', '_', self.experiment_name.get().strip().lower())
        self.experimenter_name.set(experimenter_name)
        self.experiment_name.set(experiment_name)
        try:
            creds = Credentials.from_service_account_file(self.json_path.get(), scopes=SCOPE)
            self.gspread_client = gspread.authorize(creds)
            self.log_queue.put("Connected to Google Sheets!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to connect to Google Sheets: {e}")
            return
        self.disable_input_fields()
        self.canvas.itemconfig(self.recording_circle, fill="yellow")
        self.canvas.itemconfig(self.recording_label, text="Logging...", fill="black")
        for port in list(self.serial_ports):
            if port in self.port_to_device_number:
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
        if port not in self.port_to_device_number:
            self.log_queue.put(f"Cannot start logging for {port}, no device_number known yet.")
            return
        device_number = self.port_to_device_number[port]
        worksheet_name = f"Device_{device_number}"
        def attempt_connection(retries=self.retry_attempts, delay=self.retry_delay):
            for attempt in range(retries):
                try:
                    ser = serial.Serial(port, 115200, timeout=0.1)
                    self.data_to_save[port] = []
                    self.port_to_serial[port] = ser
                    t = threading.Thread(
                        target=self.read_from_port,
                        args=(ser, worksheet_name, port)
                    )
                    t.daemon = True
                    t.start()
                    self.port_threads[port] = t
                    if self.port_widgets[port]['status_label'].cget("text") != "Ready":
                        self.port_widgets[port]['status_label'].config(text="Ready", fg="green")
                    self.log_queue.put(f"Started logging from {port} with sheet {worksheet_name}.")
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
        self.canvas.itemconfig(self.recording_circle, fill="red")
        self.canvas.itemconfig(self.recording_label, text="OFF", fill="red")
        self.enable_input_fields()
        threading.Thread(target=self._join_threads_and_exit).start()

    def _join_threads_and_exit(self):
        for t in list(self.port_threads.values()):
            t.join()
        self.log_queue.put("Logging stopped.")
        self.save_all_data()
        for port, ser in self.port_to_serial.items():
            try:
                if ser.is_open:
                    ser.close()
            except:
                pass
        self.port_to_serial.clear()
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
            device_number = self.port_to_device_number.get(port, "unknown")
            safe_port_name = re.sub(r'[<>:"/\\|?*]', '_', os.path.basename(port))
            filename_user = os.path.join(experiment_folder, f"{safe_port_name}_device_{device_number}_{current_time}.csv")
            try:
                with open(filename_user, mode='w', newline='') as file:
                    writer = csv.writer(file)
                    writer.writerow(column_headers)
                    writer.writerows(data_rows)
                self.log_queue.put(f"Data saved for {port} at {filename_user}.")
            except Exception as e:
                self.log_queue.put(f"Failed to save data for {port}: {e}")

    def update_gui(self):
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
        try:
            while True:
                log_message = self.log_queue.get_nowait()
                self.log_text.insert(tk.END, f"{datetime.datetime.now()}: {log_message}\n")
                self.log_text.see(tk.END)
        except queue.Empty:
            pass
        current_time = time.time()
        if current_time - self.last_device_check_time >= 5:
            self.check_device_connections()
            self.last_device_check_time = current_time
        self.root.after(100, self.update_gui)

    def check_device_connections(self):
        current_ports = set(self.detect_serial_ports())
        for port in list(self.serial_ports):
            if port not in current_ports:
                self.serial_ports.remove(port)
                if port in self.port_widgets:
                    self.port_widgets[port]['status_label'].config(text="Not Ready", fg="red")
                self.log_queue.put(f"Device on {port} disconnected.")
                if port in self.port_threads:
                    del self.port_threads[port]
                if port in self.identification_threads:
                    self.identification_stop_events[port].set()
                    self.identification_threads[port].join()
                    del self.identification_threads[port]
                    del self.identification_stop_events[port]
        for port in current_ports:
            if port not in self.serial_ports:
                self.serial_ports.add(port)
                idx = len(self.port_widgets)
                self.initialize_port_widgets(port, idx)
                self.start_identification_thread(port)
                if self.logging_active and port in self.port_to_device_number:
                    self.start_logging_for_port(port)

    def read_from_port(self, ser, worksheet_name, port_identifier):
        sheet = None
        cached_data = []
        send_interval = 5
        last_send_time = time.time()
        jam_event_occurred = False
        event_index = column_headers.index("Event") - 1
        device_number_index = column_headers.index("Device_Number") - 1
        device_number = self.port_to_device_number.get(port_identifier, "unknown")
        try:
            spreadsheet = self.gspread_client.open_by_key(self.spreadsheet_id.get())
            sheet = self.get_or_create_worksheet(spreadsheet, worksheet_name)
        except Exception as e:
            self.log_queue.put(f"Failed to access sheet {worksheet_name} at start for {port_identifier}: {e}")
            sheet = None
        while not self.stop_event.is_set():
            try:
                line = ser.readline().decode('utf-8', errors='replace').strip()
            except serial.SerialException as e:
                self.log_queue.put(f"Device on {port_identifier} disconnected: {e}")
                if port_identifier in self.port_widgets:
                    self.port_widgets[port_identifier]['status_label'].config(text="Not Ready", fg="red")
                break
            cmd_info = self.time_sync_commands.get(port_identifier)
            if cmd_info and cmd_info[0] == 'pending':
                start_t = cmd_info[1]
                elapsed = time.time() - start_t
                if line == "TIME_SET_OK":
                    self.log_queue.put(f"Time synced for device on {port_identifier}.")
                    self.time_sync_commands[port_identifier] = ('done', time.time())
                    continue
                elif line == "TIME_SET_FAIL":
                    self.log_queue.put(f"Time sync command sent to {port_identifier}, no confirmation.")
                    self.time_sync_commands[port_identifier] = ('done', time.time())
                    continue
                elif elapsed > 2.0:
                    self.log_queue.put(f"Time sync command sent to {port_identifier}, no confirmation.")
                    self.time_sync_commands[port_identifier] = ('done', time.time())
                if line:
                    data_list = line.split(",")[1:] if "," in line else []
                    if len(data_list) == len(column_headers) - 1:
                        event_value = data_list[event_index].strip()
                        row_data = [datetime.datetime.now().strftime("%m/%d/%Y %H:%M:%S.%f")[:-3]] + data_list
                        cached_data.append(row_data)
                        if port_identifier in self.port_queues:
                            self.port_queues[port_identifier].put(f"Data logged: {data_list}")
                        self.data_to_save.setdefault(port_identifier, []).append(row_data)
                        if event_value == "JAM":
                            jam_event_occurred = True
                        if event_value in ["Right", "Pellet", "Left", "LeftWithPellet", "RightWithPellet"]:
                            if port_identifier in self.port_queues:
                                self.port_queues[port_identifier].put("RIGHT_POKE")
            else:
                if line:
                    data_list = line.split(",")[1:] if "," in line else []
                    if len(data_list) == len(column_headers) - 1:
                        event_value = data_list[event_index].strip()
                        row_data = [datetime.datetime.now().strftime("%m/%d/%Y %H:%M:%S.%f")[:-3]] + data_list
                        cached_data.append(row_data)
                        if port_identifier in self.port_queues:
                            self.port_queues[port_identifier].put(f"Data logged: {data_list}")
                        self.data_to_save.setdefault(port_identifier, []).append(row_data)
                        if event_value == "JAM":
                            jam_event_occurred = True
                        if event_value in ["Right", "Pellet", "Left", "LeftWithPellet", "RightWithPellet"]:
                            if port_identifier in self.port_queues:
                                self.port_queues[port_identifier].put("RIGHT_POKE")
                    else:
                        self.log_queue.put(f"Warning: Data length mismatch on {port_identifier}")
            current_time = time.time()
            if (current_time - last_send_time >= send_interval) and sheet:
                if cached_data:
                    try:
                        sheet.append_rows(cached_data)
                        self.log_queue.put(f"Appended {len(cached_data)} rows from {port_identifier} to Google Sheets.")
                        cached_data.clear()
                    except Exception as e:
                        self.log_queue.put(f"Failed to send data to Google Sheets for {port_identifier}: {e}")
                if jam_event_occurred:
                    try:
                        jam_row = [''] * len(column_headers)
                        jam_row[0] = datetime.datetime.now().strftime("%m/%d/%Y %H:%M:%S.%f")[:-3]
                        jam_row[column_headers.index("Event")] = "JAM"
                        jam_row[column_headers.index("Device_Number")] = device_number
                        sheet.append_row(jam_row)
                        self.log_queue.put(f"JAM event logged for {port_identifier}")
                        jam_event_occurred = False
                    except Exception as e:
                        self.log_queue.put(f"Failed to send JAM event to Google Sheets for {port_identifier}: {e}")
                last_send_time = current_time
            time.sleep(0.1)
        self.log_queue.put(f"Closed serial port {port_identifier}")

    def get_or_create_worksheet(self, spreadsheet, title):
        try:
            return spreadsheet.worksheet(title)
        except gspread.exceptions.WorksheetNotFound:
            sheet = spreadsheet.add_worksheet(title=title, rows="1000", cols="20")
            sheet.append_row(column_headers)
            return sheet

    def trigger_indicator(self, port_identifier):
        if port_identifier not in self.port_widgets:
            return
        indicator_canvas = self.port_widgets[port_identifier]['indicator_canvas']
        indicator_circle = self.port_widgets[port_identifier]['indicator_circle']
        def blink(times):
            if times > 0:
                current_color = indicator_canvas.itemcget(indicator_circle, 'fill')
                next_color = 'red' if current_color == 'gray' else 'gray'
                indicator_canvas.itemconfig(indicator_circle, fill=next_color)
                self.root.after(250, lambda: blink(times - 1))
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
            for port, ser in self.port_to_serial.items():
                try:
                    if ser.is_open:
                        ser.close()
                except:
                    pass
            self.port_to_serial.clear()
            self.data_saved = True
        self.root.destroy()

    def toggle_dark_mode(self):
        self.dark_mode = not self.dark_mode
        self.apply_theme()

    def apply_theme(self):
        if self.dark_mode:
            bg_color = "#2e2e2e"
            fg_color = "#ffffff"
            entry_bg = "#3c3c3c"
            entry_fg = "#ffffff"
            text_bg = "#3c3c3c"
            text_fg = "#ffffff"
            canvas_bg = "#2e2e2e"
        else:
            bg_color = "white"
            fg_color = "black"
            entry_bg = "white"
            entry_fg = "black"
            text_bg = "white"
            text_fg = "black"
            canvas_bg = "white"
        self.root.configure(bg=bg_color)
        self.main_frame.configure(bg=bg_color)
        self.top_frame.configure(bg=bg_color)
        self.ports_frame_container.configure(bg=bg_color)
        self.ports_canvas.configure(bg=bg_color, highlightthickness=0, bd=0)
        self.ports_inner_frame.configure(bg=bg_color)
        self.indicator_frame.configure(bg=bg_color)
        self.log_frame.configure(bg=bg_color)
        self.bottom_frame.configure(bg=bg_color)
        self.name_label.configure(bg=bg_color, fg=fg_color)
        self.exp_label.configure(bg=bg_color, fg=fg_color)
        self.json_label.configure(bg=bg_color, fg=fg_color)
        self.spread_label.configure(bg=bg_color, fg=fg_color)
        self.footer_label.configure(bg=bg_color, fg="royalblue")
        self.hyperlink_label.configure(bg=bg_color, fg="blue")
        self.json_button.configure(bg=bg_color, fg=fg_color, highlightthickness=0, bd=1)
        self.folder_button.configure(bg=bg_color, fg=fg_color, highlightthickness=0, bd=1)
        self.start_button.configure(bg="green" if not self.dark_mode else "#006400", fg="white", highlightthickness=0, bd=1)
        self.stop_button.configure(bg="slategrey", fg="white", highlightthickness=0, bd=1)
        self.sync_time_button.configure(bg="blue", fg="white", highlightthickness=0, bd=1)
        self.dark_mode_button.configure(bg=bg_color, fg=fg_color, highlightthickness=0, bd=1)
        self.experimenter_entry.configure(bg=entry_bg, fg=entry_fg, insertbackground=entry_fg, highlightthickness=0)
        self.experiment_entry.configure(bg=entry_bg, fg=entry_fg, insertbackground=entry_fg, highlightthickness=0)
        self.json_entry.configure(bg=entry_bg, fg=entry_fg, insertbackground=entry_fg, highlightthickness=0)
        self.spreadsheet_entry.configure(bg=entry_bg, fg=entry_fg, insertbackground=entry_fg, highlightthickness=0)
        self.log_text.configure(bg=text_bg, fg=text_fg, insertbackground=fg_color, highlightthickness=0)
        for port, widgets in self.port_widgets.items():
            frame = widgets['frame']
            frame.configure(bg=bg_color, fg=fg_color, highlightthickness=0)
            widgets['status_label'].configure(bg=bg_color, fg=widgets['status_label'].cget("fg"))
            widgets['text_widget'].configure(bg=text_bg, fg=text_fg, insertbackground=fg_color, highlightthickness=0)
            widgets['indicator_canvas'].configure(bg=bg_color, highlightthickness=0, bd=0)
        self.canvas.configure(bg=canvas_bg, highlightthickness=0)

    def sync_all_device_times(self):
        now = datetime.datetime.now()
        time_str = f"SET_TIME:{now.year},{now.month},{now.day},{now.hour},{now.minute},{now.second}"
        if self.logging_active:
            for port, device_number in self.port_to_device_number.items():
                ser = self.port_to_serial.get(port)
                if ser and ser.is_open:
                    self.time_sync_commands[port] = ('pending', time.time())
                    try:
                        ser.write((time_str + "\n").encode('utf-8'))
                    except Exception as e:
                        self.log_queue.put(f"Failed to sync time for {port}: {e}")
                else:
                    self.log_queue.put(f"No open serial connection for {port} to sync.")
        else:
            for port in self.port_to_device_number.keys():
                self.time_sync_commands[port] = ('pending', time.time())
                try:
                    ser = serial.Serial(port, 115200, timeout=2)
                    ser.write((time_str + "\n").encode('utf-8'))
                    start_t = time.time()
                    got_response = False
                    while time.time() - start_t < 2:
                        line = ser.readline().decode('utf-8', errors='replace').strip()
                        if line == "TIME_SET_OK":
                            self.log_queue.put(f"Time synced for device on {port}.")
                            got_response = True
                            break
                        elif line == "TIME_SET_FAIL":
                            self.log_queue.put(f"Time sync command sent to {port}, no confirmation.")
                            got_response = True
                            break
                    if not got_response:
                        self.log_queue.put(f"Time sync command sent to {port}, no confirmation.")
                    ser.close()
                    self.time_sync_commands[port] = ('done', time.time())
                except Exception as e:
                    self.log_queue.put(f"Failed to sync time for {port}: {e}")
                    self.time_sync_commands[port] = ('done', time.time())

if __name__ == "__main__":
    splash_root = tk.Tk()
    SplashScreen(splash_root, duration=7000)
    splash_root.after(7000, splash_root.destroy)
    splash_root.mainloop()

    root = tk.Tk()
    app = FED3MonitorApp(root)
    root.mainloop()


# In[ ]:




