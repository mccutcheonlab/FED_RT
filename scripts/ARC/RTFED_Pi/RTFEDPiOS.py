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
    "Retrieval_Time", "InterPelletInterval", "Poke_Time","PelletsOrTrialToSwitch", "Prob_left", "Prob_right", "High_prob_poke"  
]

# Google Sheets Scope
SCOPE = [
    "https://spreadsheets.google.com/feeds",
    'https://www.googleapis.com/auth/spreadsheets',
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
]

class SplashScreen:
    def __init__(self, root, duration=3000):
        self.root = root
        self.root.overrideredirect(True)
        self.root.attributes("-alpha", 1)
        screen_width= self.root.winfo_screenwidth()
        screen_height= self.root.winfo_screenheight()
        self.root.geometry(f"{screen_width}x{screen_height}+0+0")
        self.root.configure(bg="black")

        self.label = tk.Label(
            self.root,
            text="McCutcheonLab Technologies\nRTFED(Raspberry Pi OS)",
            font=("Cascadia Code", 32, "bold"),
            bg="black",
            fg="violet"
        )
        self.label.pack(expand=True)
        self.fade_in_out(duration)

    def fade_in_out(self, duration):
        self.fade_in(1000, lambda: self.fade_out(2000, self.close))

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

class FED3MonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("RTFED(Pi)")
        self.root.geometry("1200x800")

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

        # Port -> Device Number
        self.port_to_device_number = {}

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

    def identify_fed3_devices(self):
        self.stop_identification_threads()
        if not self.serial_ports:
            self.log_queue.put("No FED3 devices detected.")
            messagebox.showwarning("Warning", "No FED3 devices detected. Connect devices first!")
            return
        self.log_queue.put("Identifying devices by triggering a poke on all connected FED3 devices...")
        threading.Thread(target=self.trigger_poke_for_identification, daemon=True).start()

    def trigger_poke_for_identification(self):
        for port in list(self.serial_ports):
            try:
                with serial.Serial(port, baudrate=115200, timeout=1) as ser:
                    ser.write(b'TRIGGER_POKE\n')
                    start_time = time.time()
                    device_number = None
                    while time.time() - start_time < 3:
                        line = ser.readline().decode('utf-8', errors='replace').strip()
                        if "," in line:
                            data_list = line.split(",")
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

    def sync_all_device_times(self):
        now = datetime.datetime.now()
        time_str = f"SET_TIME:{now.year},{now.month},{now.day},{now.hour},{now.minute},{now.second}"
    
        if self.logging_active:
            for port, device_number in self.port_to_device_number.items():
                try:
                    ser = serial.Serial(port, 115200, timeout=2)
                    ser.write((time_str + "\n").encode('utf-8'))
                    start_t = time.time()
                    while time.time() - start_t < 2:
                        line = ser.readline().decode('utf-8', errors='replace').strip()
                        if line == "TIME_SET_OK":
                            self.log_queue.put(f"Time synced for device on {port}.")
                            break
                except Exception as e:
                    self.log_queue.put(f"Failed to sync time for {port}: {e}")
        else:
            for port in self.port_to_device_number.keys():
                try:
                    ser = serial.Serial(port, 115200, timeout=2)
                    ser.write((time_str + "\n").encode('utf-8'))
                    ser.close()
                    self.log_queue.put(f"Time sync command sent to {port}.")
                except Exception as e:
                    self.log_queue.put(f"Failed to sync time for {port}: {e}")

    def set_device_mode(self):
        selected = self.mode_var.get()
        if not selected or selected == "Select Mode":
            messagebox.showerror("Error", "Please select a valid mode from the dropdown.")
            return
    
        mode_num = int(selected.split(" - ")[0])
        
        ports_to_set = [
            port for port, widgets in self.port_widgets.items()
            if widgets.get('selected_var') and widgets['selected_var'].get()
        ]

        for port in ports_to_set:
            try:
                with serial.Serial(port, baudrate=115200, timeout=2) as ser:
                    ser.write(f"SET_MODE:{mode_num}\n".encode('utf-8'))
                    start_time = time.time()
                    while time.time() - start_time < 3:
                        response = ser.readline().decode().strip()
                        if response == "MODE_SET_OK":
                            self.log_queue.put(f"Mode {mode_num} set on {port}. Device will restart.")
                            break
                        elif response == "MODE_SET_FAIL":
                            self.log_queue.put(f"Mode set failed on {port}.")
                            break
            except Exception as e:
                self.log_queue.put(f"Error setting mode on {port}: {e}")

    


  
    


    def setup_gui(self):
        self.root.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)
        self.root.grid_rowconfigure((0, 1, 2, 3, 4, 5, 6), weight=1)
    
        tk.Label(self.root, text="Your Name:", font=("Cascadia Code", 12, "bold")).grid(column=0, row=0, sticky=tk.E, padx=0, pady=0)
        self.experimenter_entry = ttk.Entry(self.root, textvariable=self.experimenter_name, width=15)
        self.experimenter_entry.grid(column=1, row=0, sticky=tk.W, padx=5, pady=5)
    
        tk.Label(self.root, text="Experiment Name:", font=("Cascadia Code", 12, "bold")).grid(column=2, row=0, sticky=tk.E, padx=5, pady=5)
        self.experiment_entry = ttk.Entry(self.root, textvariable=self.experiment_name, width=30)
        self.experiment_entry.grid(column=3, row=0, sticky=tk.W, padx=5, pady=5)
    
        tk.Label(self.root, text="Google API JSON File:", font=("Cascadia Code", 12, "bold")).grid(column=0, row=1, sticky=tk.E, padx=5, pady=5)
        self.json_entry = ttk.Entry(self.root, textvariable=self.json_path, width=10)
        self.json_entry.grid(column=1, row=1, sticky=tk.W, padx=5, pady=5)
        self.browse_json_button = tk.Button(self.root, text="Browse", command=self.browse_json, font=("Cascadia Code", 10))
        self.browse_json_button.grid(column=2, row=1, padx=5, pady=5, sticky=tk.W)
    
        tk.Label(self.root, text="Google Spreadsheet ID:", font=("Cascadia Code", 12, "bold")).grid(column=0, row=2, sticky=tk.E, padx=5, pady=5)
        self.spreadsheet_entry = ttk.Entry(self.root, textvariable=self.spreadsheet_id, width=50)
        self.spreadsheet_entry.grid(column=1, row=2, sticky=tk.W, padx=5, pady=5)
    
        self.start_button = tk.Button(self.root, text="START", font=("Cascadia Code", 12, "bold"), bg="green", fg="white", command=self.start_logging)
        self.start_button.grid(column=2, row=2, padx=10, pady=10, sticky=tk.W)
        self.identify_devices_button = tk.Button(
            self.root,
            text="Identify Devices",
            bg="orange",
            fg="black",
            font=("Cascadia Code", 12, "bold"),
            command=self.identify_fed3_devices
        )
        self.identify_devices_button.grid(column=2, row=3, padx=5, pady=5)
    
        self.sync_time_button = tk.Button(
            self.root,
            text="Sync FED3 Time",
            bg="blue",
            fg="white",
            font=("Cascadia Code", 12, "bold"),
            command=self.sync_all_device_times
     
        )
        self.sync_time_button.grid(column=3, row=3, padx=5, pady=5)
    
        self.mode_var = tk.StringVar(value="Select Mode")
        self.mode_options = [
            "0 - Free Feeding", "1 - FR1", "2 - FR3", "3 - FR5",
            "4 - Progressive Ratio", "5 - Extinction", "6 - Light Tracking",
            "7 - FR1 (Reversed)", "8 - PR (Reversed)", "9 - Self-Stim",
            "10 - Self-Stim (Reversed)", "11 - Timed Feeding", "12 - ClosedEconomy_PR2", "13 - Probabilistic Reversal", "14 - Bandit8020", "15 - DetBandit"
        ]
        self.mode_menu = ttk.Combobox(self.root, textvariable=self.mode_var,
                                      values=self.mode_options, width=20, state="readonly")
        self.mode_menu.grid(column=0, row=3, padx=3, pady=4)
        
        self.set_mode_button = tk.Button(
            self.root,
            text="Set Mode",
            command=self.set_device_mode,
            bg="darkorange",
            fg="black",
            font=("Cascadia Code", 12, "bold")
        )
        self.set_mode_button.grid(column=0, row=3, padx=5, pady=5, sticky=tk.E)  
    
        self.stop_button = tk.Button(self.root, text="STOP(SAVE & QUIT)", font=("Cascadia Code", 12, "bold"), bg="red", fg="white", command=self.stop_logging)
        self.stop_button.grid(column=3, row=2, padx=10, pady=10, sticky=tk.W)
        
        self.browse_button = tk.Button(self.root, text="Browse Data Folder", font=("Cascadia Code", 12, "bold"), command=self.browse_folder, bg="gold", fg="blue")
        self.browse_button.grid(column=1, row=3, columnspan=2, padx=10, pady=10)  # Centered in middle
    
        indicator_frame = tk.Frame(self.root)
        indicator_frame.grid(column=3, row=6, sticky=tk.E, pady=10)  # Moved to bottom far right
        self.canvas = tk.Canvas(indicator_frame, width=100, height=100)
        self.canvas.pack()
        self.recording_circle = self.canvas.create_oval(25, 25, 75, 75, fill="Orange")
        self.recording_label = self.canvas.create_text(50, 90, text="Standby", font=("Cascadia Code", 12), fill="black")
    
        ports_frame_container = tk.Frame(self.root)
        ports_frame_container.grid(column=0, row=4, columnspan=4, pady=20, sticky=(tk.N, tk.S, tk.E, tk.W))
        ports_canvas = tk.Canvas(ports_frame_container)
        ports_scrollbar = ttk.Scrollbar(ports_frame_container, orient="vertical", command=ports_canvas.yview)
        ports_canvas.configure(yscrollcommand=ports_scrollbar.set)
        ports_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        ports_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.ports_frame = tk.Frame(ports_canvas)
        ports_canvas.create_window((0,0), window=self.ports_frame, anchor="nw")
        self.ports_frame.bind("<Configure>", lambda event: ports_canvas.configure(scrollregion=ports_canvas.bbox("all")))
    
        if not self.serial_ports:
            tk.Label(self.ports_frame, text="Connect your FED3 devices and restart the GUI!", font=("Cascadia Code", 14), fg="red").pack()
        else:
            for idx, port in enumerate(self.serial_ports):
                self.initialize_port_widgets(port, idx)
    
        log_frame = tk.Frame(self.root)
        log_frame.grid(column=0, row=5, columnspan=4, pady=10, sticky=(tk.N, tk.S, tk.E, tk.W))
        self.log_text = tk.Text(log_frame, height=10, width=130, font=("Cascadia Code", 10))
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.configure(yscrollcommand=log_scrollbar.set)
    
        bottom_frame = tk.Frame(self.root)
        bottom_frame.grid(column=0, row=6, columnspan=4, pady=10, sticky=tk.S)  # Centered at bottom
        tk.Label(bottom_frame, text="© 2025 McCutcheonLab | UiT | Norway", font=("Cascadia Code", 10), fg="royalblue").pack(pady=5)
        hyperlink_label = tk.Label(bottom_frame, text="Developed by Hamid Taghipourbibalan", font=("Cascadia Code", 10, "italic"), fg="blue", cursor="hand2")
        hyperlink_label.pack(pady=5)
        hyperlink_label.bind("<Button-1>", lambda e: self.open_hyperlink("https://www.linkedin.com/in/hamid-taghipourbibalan-b7239088/"))

    def show_instruction_popup(self):
        messagebox.showinfo("Instructions", 
            "1) Have you flashed your FED3 with the RTFED library? You should see the RTT label on your FED3 screen.\n"
            "2) Press the [Identify Devices] button to trigger a poke command on each FED3 and identify devices. If set on Free Feeding mode, wait for the Pellet event to Timeout (60 sec elapsed) before identifying the devices.\n"
            "3) After devices are identified, a) You can press [Sync FED3 Time] to synchronize time on all your FED3 devices! b) You can click on the check-box of the ports you'd like to change the modes, select the desired mode from the drop-down menu and change it\n")
        messagebox.showwarning("Caution", 
            "1) If you need to restart a FED3 during an experiment, do it while the internet connection is active.\n"
            "2) Restart and reconnect FED3 units one at a time if needed.\n"
            "3) After restarting a device, the data file saved locally would only contain the data logged after restart, however the full length data would remain available on your Google spreadsheet.\n"                  
            "4) IT IS VERY IMPORTANT to identify FED3 devices before pressing START or else RTFED will not log data.\n"
            "5) We recommend using a powered USB hub if many FED3 units are connected.")

    def initialize_port_widgets(self, port, idx=None):
        if port in self.port_widgets:
            return

        if idx is None:
            idx = len(self.port_widgets)
        port_name = os.path.basename(port)
        frame = ttk.LabelFrame(self.ports_frame, text=f"Port {port_name}")
        frame.grid(column=idx % 2, row=idx // 2, padx=10, pady=10, sticky=tk.W)
        status_label = ttk.Label(frame, text="Not Ready", font=("Cascadia Code", 10, "italic"), foreground="red")
        status_label.grid(column=0, row=0, sticky=tk.W)
        text_widget = tk.Text(frame, width=40, height=6, font=("Cascadia Code", 9))
        text_widget.grid(column=0, row=1, sticky=(tk.N, tk.S, tk.E, tk.W))
        indicator_canvas = tk.Canvas(frame, width=20, height=20)
        indicator_canvas.grid(column=1, row=0, padx=5)
        indicator_circle = indicator_canvas.create_oval(5, 5, 15, 15, fill="gray")

        self.port_widgets[port] = {
            'status_label': status_label,
            'text_widget': text_widget,
            'indicator_canvas': indicator_canvas,
            'indicator_circle': indicator_circle
        }

        selected_var = tk.BooleanVar(value=True)
        chk = tk.Checkbutton(frame,
                             text="Apply Mode",
                             variable=selected_var,
                             font=("Cascadia Code", 10))
        chk.grid(column=0, row=2, sticky=tk.W, pady=(5,0))
        self.port_widgets[port]['selected_var'] = selected_var

        self.port_queues[port] = queue.Queue()

        try:
            ser = serial.Serial(port, 115200, timeout=1)
            ser.close()
            status_label.config(text="Ready", foreground="green")
        except serial.SerialException as e:
            status_label.config(text="Not Ready", foreground="red")
            self.log_queue.put(f"Error with port {port}: {e}")

    def browse_json(self):
        filename = filedialog.askopenfilename(title="Select JSON File", filetypes=[("JSON Files", "*.json")])
        if filename:
            self.json_path.set(filename)

    def browse_folder(self):
        self.save_path = filedialog.askdirectory(title="Select Folder to Save Data")
        if self.save_path:
            self.log_queue.put(f"Data folder selected: {self.save_path}")

    def start_identification_threads(self):
        for port in self.serial_ports:
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
        if port in self.port_threads:
            self.log_queue.put(f"Skipping identification for {port} as it is already in use.")
            return
        try:
            ser = serial.Serial(port, 115200, timeout=0.1)
            event_index = column_headers.index("Event") - 1
            device_number_index = column_headers.index("Device_Number") - 1

            device_number_found = None
            while not stop_event.is_set():
                try:
                    data = ser.readline().decode('utf-8', errors='replace').strip()
                    if data:
                        data_list = data.split(",")[1:]
                        if len(data_list) == len(column_headers)-1:
                            event_value = data_list[event_index].strip()
                            dn = data_list[device_number_index].strip()

                            # Blink indicator on "Right" event (just to show activity)
                            if event_value in ["Right","Left","Pellet","LeftWithPellet","RightWithPellet"]:
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
        # If logging already started, start logging for this new device immediately
        if self.logging_active:
            self.start_logging_for_port(port)

    def start_logging(self):
        self.stop_identification_threads()
        self.stop_event.clear()
        self.logging_active = True

        self.experimenter_name.set(self.experimenter_name.get().strip().lower())
        self.experiment_name.set(self.experiment_name.get().strip().lower())
        self.json_path.set(self.json_path.get().strip())
        self.spreadsheet_id.set(self.spreadsheet_id.get().strip())

        if not self.experimenter_name.get() or not self.experiment_name.get():
            messagebox.showerror("Error", "Please provide your name and experiment name.")
            return

        if not self.json_path.get() or not self.spreadsheet_id.get() or not self.save_path:
            messagebox.showerror("Error", "Please provide the JSON file, Spreadsheet ID, and data folder.")
            return

        experimenter_name = re.sub(r'[<>:"/\\|?*]', '_', self.experimenter_name.get())
        experiment_name = re.sub(r'[<>:"/\\|?*]', '_', self.experiment_name.get())
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
            # Start logging if device_number known
            if port in self.port_to_device_number:
                self.start_logging_for_port(port)
            else:
                self.log_queue.put(f"Device number not yet known for {port}, logging will start once identified.")

    def disable_input_fields(self):
        self.experimenter_entry.config(state='disabled')
        self.experiment_entry.config(state='disabled')
        self.json_entry.config(state='disabled')
        self.spreadsheet_entry.config(state='disabled')
        self.browse_json_button.config(state='disabled')
        self.browse_button.config(state='disabled')
        self.start_button.config(state='disabled')

    def enable_input_fields(self):
        self.experimenter_entry.config(state='normal')
        self.experiment_entry.config(state='normal')
        self.json_entry.config(state='normal')
        self.spreadsheet_entry.config(state='normal')
        self.browse_json_button.config(state='normal')
        self.browse_button.config(state='normal')
        self.start_button.config(state='normal')

    def start_logging_for_port(self, port):
        if port in self.port_threads:
            return

        # We must have device_number by now
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
                    t = threading.Thread(
                        target=self.read_from_port,
                        args=(ser, worksheet_name, port)
                    )
                    t.daemon = True
                    t.start()
                    self.port_threads[port] = t
                    if self.port_widgets[port]['status_label'].cget("text") != "Ready":
                        self.port_widgets[port]['status_label'].config(text="Ready", foreground="green")
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
        self.hide_recording_indicator()
        self.enable_input_fields()
        threading.Thread(target=self._join_threads_and_save).start()

    def _join_threads_and_save(self):
        for port, t in list(self.port_threads.items()):
            t.join()
            self.log_queue.put(f"Logging thread for {port} has stopped.")
            del self.port_threads[port]

        self.save_all_data()
        self.data_saved = True
        self.root.after(0, self._finalize_exit)

    def _finalize_exit(self):
        messagebox.showinfo("Data Saved", "All data has been saved locally.")
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
            if data_rows:
                port_name = os.path.basename(port)
                safe_port_name = re.sub(r'[<>:"/\\|?*]', '_', port_name)
                device_number = self.port_to_device_number.get(port, "unknown")
                filename_user = os.path.join(experiment_folder, f"{safe_port_name}_device_{device_number}_{current_time}.csv")
                try:
                    with open(filename_user, mode='w', newline='') as file:
                        writer = csv.writer(file)
                        writer.writerow(column_headers)
                        writer.writerows(data_rows)
                    self.log_queue.put(f"Data saved for {port} in {filename_user}.")
                except Exception as e:
                    self.log_queue.put(f"Failed to save data for {port}: {e}")

    def update_gui(self):
        # Check for messages from port_queues (e.g. "RIGHT_POKE")
        for port_identifier, q in list(self.port_queues.items()):
            try:
                while True:
                    message = q.get_nowait()
                    if message == "RIGHT_POKE":
                        self.trigger_indicator(port_identifier)
                    else:
                        if port_identifier in self.port_widgets:
                            self.port_widgets[port_identifier]['text_widget'].insert(tk.END, message + "\n")
                            self.port_widgets[port_identifier]['text_widget'].see(tk.END)
            except queue.Empty:
                pass

        # Check for log messages
        try:
            while True:
                log_message = self.log_queue.get_nowait()
                self.log_text.insert(tk.END, f"{datetime.datetime.now().strftime('%m/%d/%Y %H:%M:%S')}: {log_message}\n")
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
        # Disconnected devices
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

        # New devices
        for port in current_ports:
            if port not in self.serial_ports:
                self.serial_ports.add(port)
                idx = len(self.port_widgets)
                self.initialize_port_widgets(port, idx)
                self.start_identification_thread(port)
                # If logging is active and once we identify the device number, logging will start automatically

    def read_from_port(self, ser, worksheet_name, port_identifier):
        sheet = None
        cached_data = []
        send_interval = 5
        last_send_time = time.time()
        jam_event_occurred = False

        event_index = column_headers.index("Event") - 1
        device_number_index = column_headers.index("Device_Number") - 1

        device_number = self.port_to_device_number[port_identifier]

        try:
            spreadsheet = self.gspread_client.open_by_key(self.spreadsheet_id.get())
            sheet = self.get_or_create_worksheet(spreadsheet, worksheet_name)
        except Exception as e:
            self.log_queue.put(f"Failed to access sheet {worksheet_name} at start for {port_identifier}: {e}")
            sheet = None

        while not self.stop_event.is_set():
            try:
                data = ser.readline().decode('utf-8', errors='replace').strip()
            except serial.SerialException as e:
                self.log_queue.put(f"Device on {port_identifier} disconnected: {e}")
                if port_identifier in self.port_widgets:
                    self.port_widgets[port_identifier]['status_label'].config(text="Not Ready", foreground="red")
                break

            if data:
                data_list = data.split(",")[1:]
                timestamp = datetime.datetime.now().strftime("%m/%d/%Y %H:%M:%S.%f")[:-3]
                if len(data_list) == len(column_headers) - 1:
                    event_value = data_list[event_index].strip()

                    if event_value == "JAM":
                        jam_event_occurred = True
                    else:
                        row_data = [timestamp] + data_list
                        cached_data.append(row_data)
                        if port_identifier in self.port_queues:
                            self.port_queues[port_identifier].put(f"Data logged: {data_list}")
                        self.data_to_save.setdefault(port_identifier, []).append(row_data)

                        if event_value in ["Right","Pellet"]:
                            if port_identifier in self.port_queues:
                                self.port_queues[port_identifier].put("RIGHT_POKE")
                else:
                    self.log_queue.put(f"Warning: Data length mismatch on {port_identifier}")

            current_time = time.time()
            should_send = (current_time - last_send_time >= send_interval)
            if should_send and sheet:
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

        try:
            ser.close()
        except:
            pass
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
                self.root.after(250, lambda: blink(times -1))
            else:
                indicator_canvas.itemconfig(indicator_circle, fill='gray')
        blink(6)

    def hide_recording_indicator(self):
        self.canvas.itemconfig(self.recording_circle, fill="red")
        self.canvas.itemconfig(self.recording_label, text="OFF", fill="red")

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

if __name__ == "__main__":
    splash_root = tk.Tk()
    splash_screen = SplashScreen(splash_root, duration=7000)
    splash_root.after(7000, splash_screen.close)
    splash_root.mainloop()

    root = tk.Tk()
    app = FED3MonitorApp(root)
    root.mainloop()


# In[ ]:




