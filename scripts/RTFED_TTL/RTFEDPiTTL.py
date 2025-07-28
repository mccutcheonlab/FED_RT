#!/usr/bin/env python
# coding: utf-8

# In[1]:


#!/usr/bin/env python3
import os
import sys
import RPi.GPIO as GPIO
import serial
import threading
import datetime
import time
import logging
import re
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import queue
import csv
import webbrowser

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    stream=sys.stdout
)

# Setup GPIO pins on the Raspberry Pi (BCM mode)
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# Define GPIO pins for each device (fixed mapping by port)
gpio_pins_per_device = {
    'Port 1': {"LeftPoke": 17, "RightPoke": 27, "Pellet": 22},
    'Port 2': {"LeftPoke": 10, "RightPoke": 9,  "Pellet": 11},
    'Port 3': {"LeftPoke": 0,  "RightPoke": 5,  "Pellet": 6},
    'Port 4': {"LeftPoke": 13, "RightPoke": 19, "Pellet": 26},
    'Port 5': {"LeftPoke": 14, "RightPoke": 15, "Pellet": 18},
    'Port 6': {"LeftPoke": 23, "RightPoke": 24, "Pellet": 25},
    'Port 7': {"LeftPoke": 8,  "RightPoke": 7,  "Pellet": 1},
    'Port 8': {"LeftPoke": 12, "RightPoke": 16, "Pellet": 20},
}

# Set all pins as output and initially LOW
for device_pins in gpio_pins_per_device.values():
    for pin in device_pins.values():
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.LOW)

# Global threading and data storage variables
pellet_lock = threading.Lock()
pellet_in_well = {}
stop_event = threading.Event()

column_headers = [
    "Timestamp", "Temp", "Humidity", "Library_Version", "Session_type",
    "Device_Number", "Battery_Voltage", "Motor_Turns", "FR", "Event", "Active_Poke",
    "Left_Poke_Count", "Right_Poke_Count", "Pellet_Count", "Block_Pellet_Count",
    "Retrieval_Time", "InterPelletInterval", "Poke_Time","PelletsOrTrialToSwitch", "Prob_left", "Prob_right", "High_prob_poke" 
]

# Global known devices dictionary maps serial port path to a fixed port identifier (e.g. "Port 1")
known_devices = {}
port_names = [f"Port {i}" for i in range(1, 9)]

def send_ttl_signal(pin):
    GPIO.output(pin, GPIO.HIGH)
    time.sleep(0.1)
    GPIO.output(pin, GPIO.LOW)

def handle_pellet_event(event_type, port_identifier, gpio_pins, q):
    global pellet_in_well
    with pellet_lock:
        if port_identifier not in pellet_in_well:
            pellet_in_well[port_identifier] = False
        etype = event_type.strip().lower()
        if etype == "pellet":
            if pellet_in_well[port_identifier]:
                GPIO.output(gpio_pins["Pellet"], GPIO.LOW)
                q.put("Pellet taken, signal turned OFF.")
                pellet_in_well[port_identifier] = False
                send_ttl_signal(gpio_pins["Pellet"])
                q.put(f"TTL signal sent on {port_identifier} for {event_type}")
            else:
                q.put("No pellet was in the well, no signal for pellet taken.")
        elif etype == "pelletinwell":
            GPIO.output(gpio_pins["Pellet"], GPIO.HIGH)
            pellet_in_well[port_identifier] = True
            q.put("Pellet dispensed in well, signal ON.")

def process_event(event_type, port_identifier, gpio_pins, q, app):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    q.put(f"[{timestamp}] {port_identifier} - Event: {event_type}")
    etype = event_type.strip().lower()
    if etype == "left":
        send_ttl_signal(gpio_pins["LeftPoke"])
        q.put(f"TTL signal sent on {port_identifier} for {event_type}")
    elif etype == "right":
        send_ttl_signal(gpio_pins["RightPoke"])
        q.put(f"TTL signal sent on {port_identifier} for {event_type}")
    elif etype in ["leftwithpellet", "rightwithpellet"]:
        send_ttl_signal(gpio_pins["LeftPoke"] if etype.startswith("left") else gpio_pins["RightPoke"])
        q.put(f"TTL signal sent on {port_identifier} for {event_type}")
    elif etype in ["pellet", "pelletinwell"]:
        handle_pellet_event(event_type, port_identifier, gpio_pins, q)
    if etype in ["left", "right", "pellet", "pelletinwell", "leftwithpellet", "rightwithpellet"]:
        app.trigger_indicator(port_identifier)

def get_current_serial_devices():
    by_path_dir = '/dev/serial/by-path/'
    if not os.path.exists(by_path_dir):
        return []
    serial_devices = []
    for symlink in os.listdir(by_path_dir):
        symlink_path = os.path.join(by_path_dir, symlink)
        serial_port = os.path.realpath(symlink_path)
        if 'ttyACM' in serial_port or 'ttyUSB' in serial_port:
            serial_devices.append(serial_port)
    serial_devices.sort()
    return serial_devices

def get_device_mappings_by_usb_port():
    # Return mappings for only known devices that are currently connected.
    device_mappings = []
    for dev in get_current_serial_devices():
        if dev in known_devices:
            device_mappings.append({
                'serial_port': dev,
                'port_identifier': known_devices[dev]
            })
    return device_mappings

def read_from_fed(serial_port, port_identifier, gpio_pins, q, status_label, app):
    try:
        ser = serial.Serial(serial_port, 115200, timeout=1)
        app.port_serial_objects[port_identifier] = ser  # store for time sync
        q.put("Ready")
        status_label.config(text="Connected", foreground="green")
        while not stop_event.is_set():
            try:
                line = ser.readline().decode('utf-8', errors='replace').strip()
            except serial.SerialException:
                q.put(f"Device on {port_identifier} disconnected.")
                status_label.config(text="Not Connected", foreground="red")
                break
            # Handle time sync responses
            if port_identifier in app.time_sync_commands and app.time_sync_commands[port_identifier][0] == 'pending':
                start_t = app.time_sync_commands[port_identifier][1]
                if line == "TIME_SET_OK":
                    q.put(f"Time synced for device on {port_identifier}.")
                    app.time_sync_commands[port_identifier] = ('done', time.time())
                    continue
                elif line == "TIME_SET_FAIL":
                    q.put(f"Time sync command on {port_identifier} received failure.")
                    app.time_sync_commands[port_identifier] = ('done', time.time())
                    continue
                elif time.time() - start_t > 2.0:
                    q.put(f"Time sync command on {port_identifier} timed out.")
                    app.time_sync_commands[port_identifier] = ('done', time.time())
            if line:
                data_list = line.split(",")
                q.put(f"{port_identifier} raw data: {data_list}")
                if len(data_list) >= 10:
                    event_type = data_list[9].strip()
                    data_list[0] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                    process_event(event_type, port_identifier, gpio_pins, q, app)
                    q.put(data_list)
                    app.data_to_save.setdefault(port_identifier, []).append(data_list)
            time.sleep(0.1)
    except serial.SerialException:
        q.put(f"Error opening serial port: {serial_port}")
        status_label.config(text="Not Connected", foreground="red")
    finally:
        if 'ser' in locals() and ser.is_open:
            ser.close()
        if port_identifier in app.port_serial_objects:
            del app.port_serial_objects[port_identifier]
        q.put(f"Stopped reading from {port_identifier}")

def identification_thread(serial_port, port_identifier, q, status_label, app, local_stop_event):
    try:
        ser = serial.Serial(serial_port, 115200, timeout=0.1)
        status_label.config(text="Connected", foreground="violet")
        while not local_stop_event.is_set():
            try:
                line = ser.readline().decode('utf-8', errors='replace').strip()
                if line:
                    data_list = line.split(",")
                    # Look for a CSV response with device identification (assumes FED number in index 5)
                    if len(data_list) >= 6 and "TRIGGER_POKE" not in line:
                        device_number = data_list[5].strip()
                        if device_number:
                            q.put(f"Identified device FED number {device_number} on {port_identifier}")
                            # Do not override the fixed port mapping; update label only.
                            status_label.config(text=f"{port_identifier} (FED {device_number})", foreground="green")
                            break
                    if len(data_list) >= 10:
                        event_type = data_list[9].strip()
                        if event_type.strip().lower() in ["right", "pellet", "left"]:
                            app.trigger_indicator(port_identifier)
            except serial.SerialException:
                status_label.config(text="Not Connected", foreground="red")
                break
    except serial.SerialException:
        status_label.config(text="Not Connected", foreground="red")
    finally:
        if 'ser' in locals() and ser.is_open:
            ser.close()

class SplashScreen:
    def __init__(self, root, duration=3000):
        self.root = root
        self.root.overrideredirect(True)
        self.root.configure(bg="black")
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{sw}x{sh}+0+0")
        self.label = tk.Label(self.root, text="McCutcheonlab Technologies\n RTFED(PiTTL)", font=("Cascadia Code", 32, "bold"), bg="black", fg="lavender")
        self.label.pack(expand=True)
        self.root.after(duration, self.close_splash)
    def close_splash(self):
        self.root.destroy()

class FED3MonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("RTFED(PiTTL)")
        self.root.geometry("1200x800")
        self.port_widgets = {}
        self.port_queues = {}
        self.experimenter_name = tk.StringVar()
        self.experiment_name = tk.StringVar()
        self.save_path = ""
        self.flat_data_path = ""
        self.data_to_save = {}
        self.threads = []
        self.connected_ports = []
        self.serial_ports = {}  # Mapping: port_identifier -> serial port path
        self.logging_active = False
        self.last_device_check_time = time.time()
        self.time_sync_commands = {}  # Mapping: port_identifier -> (status, timestamp)
        #######mode‐selection################ ADD EXTRA MODES HERE, ALSO DEFINE IT IN THE FED3 RTS FIRMWARE, Hamid May 2025
        self.mode_var = tk.StringVar(value="Select Mode")
        self.mode_options = [
            "0 - Free Feeding", "1 - FR1", "2 - FR3", "3 - FR5",
            "4 - Progressive Ratio", "5 - Extinction", "6 - Light Tracking",
            "7 - FR1 (Reversed)", "8 - PR (Reversed)", "9 - Self-Stim",
            "10 - Self-Stim (Reversed)", "11 - Timed Feeding", "12 - ClosedEconomy_PR2", "13 - Probabilistic Reversal", "14 - Bandit8020", "15 - DetBandit"
        ]

        self.port_serial_objects = {}  # Mapping: port_identifier -> serial.Serial instance
        self.session_start_time = None
        self.session_timer_text = None
        self.identification_threads = {}
        self.identification_stop_events = {}
        self.stop_event = stop_event
        self.perform_initial_device_mapping()
        self.mainframe = ttk.Frame(self.root)
        self.mainframe.grid_rowconfigure(2, weight=0)
        self.mainframe.grid_columnconfigure(0, weight=1)
        self.mainframe.grid_columnconfigure(1, weight=1)

        self.mainframe.grid(column=0, row=0, sticky=(tk.N, tk.W, tk.E, tk.S))
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
      
        self.root.grid_rowconfigure(1, weight=0)
        
        footer = ttk.Frame(self.root)
        footer.grid(row=1, column=0, sticky="we")
        
        footer_label = tk.Label(footer, text="© 2025 McCutcheonlab | UiT | Norway", font=("Cascadia Code", 10), fg="black")
        footer_label.pack(pady=5)
        
        hyperlink_label = tk.Label(footer, text="Developed by Hamid Taghipourbibalan", font=("Cascadia Code", 10, "italic"), fg="blue", cursor="hand2")
        hyperlink_label.pack(pady=0)
        hyperlink_label.bind("<Button-1>", lambda e: webbrowser.open_new("https://www.linkedin.com/in/hamid-taghipourbibalan-b7239088/"))

        self.create_layout()
        self.check_connected_devices()
        self.start_identification_threads_for_connected()
        self.root.after(500, self.show_port_mapping_message)
        self.update_gui()
        self.root.after(5000, self.refresh_device_status)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)


    def perform_initial_device_mapping(self):
        serial_devices = get_current_serial_devices()
        i = 0
        for dev in serial_devices:
            if dev not in known_devices and i < len(port_names):
                known_devices[dev] = port_names[i]
                i += 1

    def show_port_mapping_message(self):
        message = (
            "1) Press Identify Devices to confirm FED3s are connected and running.\n"
            "2) Press Sync Clock to synchronize clocks on all FED3 units.\n"
            "3) If needed, you can select which FED you would like to change the mode on, after setting the mode, the selected device(s) would be restarted (one after the other). Press Identify Devices again to confirm.\n"
            "4) If you need to restart a FED3 after pressing START (e.g fixing a jam), do it one at a time and reconnect the same device to the same port, no need to Identify devices again.\n"
            "5) Ports are assigned based on the initial detection when the program started, i.e. the order the FED3s are switched on\n"
            "6) In case of noticing abnormal and unexpected behaviour from your Raspberry Pi, e.g. an open window closing itself, etc, we recommend restarting your system!\n"
            "7) GPIO pin mapping for Raspberry Pi 4B is:\n\n"
            "Port 1: Left=17, Right=27, Pellet=22\n"
            "Port 2: Left=10, Right=9,  Pellet=11\n"
            "Port 3: Left=0,  Right=5,  Pellet=6\n"
            "Port 4: Left=13, Right=19, Pellet=26\n"
            "Port 5: Left=14, Right=15, Pellet=18\n"
            "Port 6: Left=23, Right=24, Pellet=25\n"
            "Port 7: Left=8,  Right=7,  Pellet=1\n"
            "Port 8: Left=12, Right=16, Pellet=20\n"
        )
        messagebox.showinfo("Port Assignment & GPIO Pins", message)

    def identify_single_port(self, port_identifier):
        """Trigger a poke and read back the device_number for just this port."""
        # find its serial path
        mapping = next((m for m in get_device_mappings_by_usb_port()
                        if m['port_identifier']==port_identifier), None)
        if not mapping:
            self.port_queues[port_identifier].put("Port not currently mapped!")
            return
    
        serial_port = mapping['serial_port']
        q = self.port_queues[port_identifier]
        q.put("🔎 Re-identifying port...")
        try:
            with serial.Serial(serial_port, 115200, timeout=1) as ser:
                ser.write(b'TRIGGER_POKE\n')
                start = time.time()
                device_number = None
                while time.time() - start < 3:
                    line = ser.readline().decode('utf-8', errors='replace').strip()
                    if line and "," in line:
                        parts = line.split(",")
                        if len(parts) >= 6:
                            device_number = parts[5].strip()
                            break
                if device_number:
                    q.put(f"Port {port_identifier} is FED #{device_number}")
                    self.port_widgets[port_identifier]['status_label']\
                        .config(text=f"{port_identifier} (FED {device_number})", foreground="green")
                else:
                    q.put("⚠️ No device_number received.")
        except Exception as e:
            q.put(f"Error re-identifying {port_identifier}: {e}")


    def set_device_mode(self):
        sel = self.mode_var.get()
        if sel == "Select Mode":
            messagebox.showerror("Error", "Please select a valid mode.")
            return
        mode_num = int(sel.split(" - ")[0])
    
        # get a sorted list of checked ports (Port 1, Port 2, …)
        checked = [pid for pid, pw in self.port_widgets.items()
                   if pw['selected_var'].get()]
        if not checked:
            messagebox.showerror("Error", "Check at least one 'Apply Mode' box.")
            return
    
        # sort by numeric suffix
        checked.sort(key=lambda p: int(p.split()[1]))
    
        for pid in checked:
            # 1) send SET_MODE
            mapping = next((m for m in get_device_mappings_by_usb_port()
                            if m['port_identifier']==pid), None)
            if not mapping:
                self.port_queues[pid].put("Port not found on USB!")
                continue
    
            serial_port = mapping['serial_port']
            q = self.port_queues[pid]
            q.put(f"➡️ Setting mode {mode_num} on {pid}…")
            try:
                with serial.Serial(serial_port, 115200, timeout=2) as ser:
                    ser.write(f"SET_MODE:{mode_num}\n".encode())
                    start = time.time()
                    ok = False
                    while time.time() - start < 3:
                        resp = ser.readline().decode().strip()
                        if resp == "MODE_SET_OK":
                            q.put("✅ Mode set OK; rebooting…")
                            ok = True
                            break
                        if resp == "MODE_SET_FAIL":
                            q.put("❌ Mode set FAILED")
                            break
                    if not ok:
                        q.put("⚠️ No confirmation, assuming reboot anyway.")
            except Exception as e:
                q.put(f"Error sending SET_MODE to {pid}: {e}")
    
            # 2) wait for that one FED3 to reboot & re-enumerate
            time.sleep(5)   # adjust as needed for your reboot time
    
            # 3) re-identify so we know which tty now maps to this pid
            self.identify_single_port(pid)



    def create_layout(self):
        ports_frame = ttk.Frame(self.mainframe)
        ports_frame.grid(column=0, row=0, padx=10, pady=10, sticky=(tk.N, tk.S, tk.W, tk.E))
        ports_frame.grid_columnconfigure((0,1), weight=1)
        for i in range(4):
            ports_frame.grid_rowconfigure(i, weight=1)
        self.setup_port(ports_frame, 'Port 1', 0, 0)
        self.setup_port(ports_frame, 'Port 2', 0, 1)
        self.setup_port(ports_frame, 'Port 3', 1, 0)
        self.setup_port(ports_frame, 'Port 4', 1, 1)
        self.setup_port(ports_frame, 'Port 5', 2, 0)
        self.setup_port(ports_frame, 'Port 6', 2, 1)
        self.setup_port(ports_frame, 'Port 7', 3, 0)
        self.setup_port(ports_frame, 'Port 8', 3, 1)
        controls_frame = ttk.Frame(self.mainframe)
        controls_frame.grid(column=1, row=0, padx=10, pady=10, sticky=(tk.N, tk.S))
        tk.Label(controls_frame, text="Your Name:", font=("Cascadia Code", 12, "bold")).grid(column=0, row=0, sticky=tk.W, pady=5)
        self.experimenter_entry = ttk.Entry(controls_frame, textvariable=self.experimenter_name, width=20)
        self.experimenter_entry.grid(column=1, row=0, sticky=tk.W, pady=5)
        tk.Label(controls_frame, text="Experiment Name:", font=("Cascadia Code", 12, "bold")).grid(column=0, row=1, sticky=tk.W, pady=5)
        self.experiment_entry = ttk.Entry(controls_frame, textvariable=self.experiment_name, width=20)
        self.experiment_entry.grid(column=1, row=1, sticky=tk.W, pady=5)
        browse_main_button = tk.Button(controls_frame, text="Browse Experiment Folder", font=("Cascadia Code", 10), command=self.browse_folder, bg="gold")
        browse_main_button.grid(column=0, row=2, columnspan=2, sticky="we", pady=5)
        browse_flat_button = tk.Button(controls_frame, text="Browse Flat Data Folder", font=("Cascadia Code", 10), command=self.browse_flat_folder, bg="lightblue")
        browse_flat_button.grid(column=0, row=3, columnspan=2, sticky="we", pady=5)
        identify_button = tk.Button(controls_frame, text="Identify Devices", font=("Cascadia Code", 12, "bold"), bg="orange", fg="black", command=self.identify_devices)
        identify_button.grid(column=0, row=4, columnspan=2, sticky="we", pady=5)
        sync_button = tk.Button(controls_frame, text="Sync Clock", font=("Cascadia Code", 12, "bold"), bg="blue", fg="white", command=self.sync_all_device_times)
        sync_button.grid(column=0, row=5, columnspan=2, sticky="we", pady=5)
        
        tk.Label(controls_frame, text="Mode:", font=("Cascadia Code", 12, "bold")
                ).grid(column=0, row=6, sticky=tk.W, pady=5)
        self.mode_menu = ttk.Combobox(
            controls_frame,
            textvariable=self.mode_var,
            values=self.mode_options,
            width=20,
            state="readonly"
        )
        self.mode_menu.grid(column=1, row=6, sticky=tk.W, pady=5)
        
        self.set_mode_button = tk.Button(
            controls_frame,
            text="Set Mode",
            font=("Cascadia Code", 12, "bold"),
            bg="darkorange",
            fg="black",
            command=self.set_device_mode
        )
        self.set_mode_button.grid(column=0, row=7, columnspan=2, sticky="we", pady=5)


        
                
        self.start_button = tk.Button(controls_frame, text="START", font=("Cascadia Code", 12, "bold"), bg="green", fg="white", command=self.start_experiment)
        self.start_button.grid(column=0, row=8, columnspan=2, sticky="we", pady=10)
        self.stop_button = tk.Button(controls_frame, text="STOP & SAVE", font=("Cascadia Code", 12, "bold"), bg="red", fg="white", command=self.stop_experiment)
        self.stop_button.grid(column=0, row=9, columnspan=2, sticky="we", pady=10)
        self.canvas = tk.Canvas(controls_frame, width=120, height=120)
        self.canvas.grid(column=0, row=10, columnspan=2, pady=20)
        self.recording_circle = None
        self.recording_label = None
        log_frame = ttk.Frame(self.mainframe)
        log_frame.grid(column=0, row=1, columnspan=2, pady=10, sticky=(tk.N, tk.S, tk.E, tk.W))
        log_frame.grid_columnconfigure(0, weight=1)
        self.log_text = tk.Text(log_frame, height=10, width=130, font=("Cascadia Code", 10))
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.configure(yscrollcommand=log_scrollbar.set)
        

    def setup_port(self, parent, port_name, r, c):
        frame = ttk.LabelFrame(parent, text=port_name, padding="3")
        frame.grid(column=c, row=r, padx=10, pady=10, sticky=(tk.N, tk.S, tk.W, tk.E))
        status_label = ttk.Label(frame, text="Not Connected", font=("Cascadia Code", 10), foreground="red")
        status_label.grid(column=0, row=0, sticky=tk.W)
        indicator_canvas = tk.Canvas(frame, width=20, height=20)
        indicator_canvas.grid(column=1, row=0, padx=5)
        indicator_circle = indicator_canvas.create_oval(5, 5, 15, 15, fill="gray")
        text_widget = tk.Text(frame, width=40, height=6, wrap=tk.WORD, font=("Cascadia Code", 9))
        text_widget.grid(column=0, row=1, columnspan=2, sticky=(tk.N, tk.S, tk.E, tk.W))
        self.port_widgets[port_name] = {
            'status_label': status_label,
            'text_widget': text_widget,
            'indicator_canvas': indicator_canvas,
            'indicator_circle': indicator_circle
        }

        ###### Apply Mode checkbox #####################################
        selected_var = tk.BooleanVar(value=True)
        chk = tk.Checkbutton(
            frame,
            text="Apply Mode",
            variable=selected_var,
            font=("Cascadia Code", 10)
        )
        chk.grid(column=0, row=2, sticky=tk.W, pady=(5,0))
        self.port_widgets[port_name]['selected_var'] = selected_var

        self.port_queues[port_name] = queue.Queue()

    def browse_folder(self):
        self.save_path = filedialog.askdirectory(title="Select Experiment Folder")

    def browse_flat_folder(self):
        self.flat_data_path = filedialog.askdirectory(title="Select Flat Data Folder")

    def check_connected_devices(self):
        device_mappings = get_device_mappings_by_usb_port()
        current_ports = [m['port_identifier'] for m in device_mappings]
        for m in device_mappings:
            port_identifier = m['port_identifier']
            if port_identifier not in self.connected_ports:
                self.connected_ports.append(port_identifier)
            self.port_widgets[port_identifier]['status_label'].config(text="Connected", foreground="green")
            if self.logging_active and port_identifier not in self.serial_ports:
                logging.info(f"Device {port_identifier} reconnected during experiment, restarting logging thread.")
                self.start_logging_for_port(m['serial_port'], port_identifier)
        for port_name in list(self.connected_ports):
            if port_name not in current_ports:
                self.connected_ports.remove(port_name)
                self.port_widgets[port_name]['status_label'].config(text="Not Connected", foreground="red")
                if port_name in self.serial_ports:
                    del self.serial_ports[port_name]
                if port_name in self.identification_threads:
                    self.identification_stop_events[port_name].set()
                    self.identification_threads[port_name].join()
                    del self.identification_threads[port_name]
                    del self.identification_stop_events[port_name]

    def refresh_device_status(self):
        self.check_connected_devices()
        self.root.after(5000, self.refresh_device_status)

    def display_recording_indicator(self):
        if self.recording_circle is None:
            self.recording_circle = self.canvas.create_oval(10, 10, 50, 50, fill="red")
        if self.recording_label is None:
            self.recording_label = self.canvas.create_text(40, 70, text="RECORDING", font=("Cascadia Code", 10), anchor="n")
        if self.session_timer_text is None:
            self.session_timer_text = self.canvas.create_text(40, 90, text="Time: 00:00:00", font=("Cascadia Code", 7), anchor="n")

    def update_session_timer(self):
        if self.session_start_time is None:
            return
        elapsed = datetime.datetime.now() - self.session_start_time
        hours, rem = divmod(int(elapsed.total_seconds()), 3600)
        minutes, seconds = divmod(rem, 60)
        timer_str = f" Time: {hours:02d}:{minutes:02d}:{seconds:02d}"
        if self.session_timer_text is not None:
            self.canvas.itemconfig(self.session_timer_text, text=timer_str)
        if self.logging_active:
            self.root.after(1000, self.update_session_timer)

    def start_identification_threads_for_connected(self):
        device_mappings = get_device_mappings_by_usb_port()
        for m in device_mappings:
            port_identifier = m['port_identifier']
            serial_port = m['serial_port']
            if port_identifier not in self.serial_ports and port_identifier not in self.identification_threads and not self.logging_active:
                self.start_identification_thread(serial_port, port_identifier)

    def start_identification_thread(self, serial_port, port_identifier):
        logging.info(f"Starting identification thread for {port_identifier}")
        stop_event_local = threading.Event()
        self.identification_stop_events[port_identifier] = stop_event_local
        q = self.port_queues[port_identifier]
        status_label = self.port_widgets[port_identifier]['status_label']
        t = threading.Thread(target=identification_thread, args=(serial_port, port_identifier, q, status_label, self, stop_event_local))
        t.daemon = True
        t.start()
        self.identification_threads[port_identifier] = t

    def identify_devices(self):
        self.stop_identification_threads()
        device_mappings = get_device_mappings_by_usb_port()
        for m in device_mappings:
            port_identifier = m['port_identifier']
            serial_port = m['serial_port']
            q = self.port_queues[port_identifier]
            q.put("Triggering device identification...")
            try:
                with serial.Serial(serial_port, 115200, timeout=1) as ser:
                    ser.write(b'TRIGGER_POKE\n')
                    start_time = time.time()
                    device_number = None
                    while time.time() - start_time < 3:
                        line = ser.readline().decode('utf-8', errors='replace').strip()
                        if line:
                            q.put(f"Received from {port_identifier}: {line}")
                            if "," in line:
                                data_list = line.split(",")
                                if len(data_list) >= 6:
                                    device_number = data_list[5].strip()
                                    break
                    if device_number:
                        q.put(f"Identified device FED number {device_number} on {port_identifier}")
                        self.port_widgets[port_identifier]['status_label'].config(text=f"{port_identifier} (FED {device_number})", foreground="green")
                    else:
                        q.put(f"No valid device number received from {port_identifier}.")
            except Exception as e:
                q.put(f"Error sending poke command to {port_identifier}: {e}")
        self.port_queues[port_identifier].put("Identification process complete.")

    def sync_all_device_times_thread(self):
        current_time_obj = datetime.datetime.now()
        time_str = f"SET_TIME:{current_time_obj.year},{current_time_obj.month},{current_time_obj.day},{current_time_obj.hour},{current_time_obj.minute},{current_time_obj.second}\n"
        device_mappings = get_device_mappings_by_usb_port()
        for m in device_mappings:
            port_identifier = m['port_identifier']
            serial_port = m['serial_port']
            self.time_sync_commands[port_identifier] = ('pending', time.time())
            if port_identifier in self.port_serial_objects:
                ser = self.port_serial_objects[port_identifier]
                try:
                    ser.write(time_str.encode('utf-8'))
                    self.port_queues[port_identifier].put(f"Sent time sync command to {port_identifier} via open connection.")
                except Exception as e:
                    self.port_queues[port_identifier].put(f"Failed to send time sync via open connection for {port_identifier}: {e}")
            else:
                try:
                    with serial.Serial(serial_port, 115200, timeout=2) as ser_temp:
                        ser_temp.write(time_str.encode('utf-8'))
                        start_t = time.time()
                        got_response = False
                        while time.time() - start_t < 2:
                            line = ser_temp.readline().decode('utf-8', errors='replace').strip()
                            if line == "TIME_SET_OK":
                                self.port_queues[port_identifier].put(f"Time synced for device on {port_identifier}.")
                                got_response = True
                                break
                            elif line == "TIME_SET_FAIL":
                                self.port_queues[port_identifier].put(f"Time sync command sent to {port_identifier}, but received failure.")
                                got_response = True
                                break
                        if not got_response:
                            self.port_queues[port_identifier].put(f"Time sync command sent to {port_identifier}, no confirmation.")
                    self.time_sync_commands[port_identifier] = ('done', time.time())
                except Exception as e:
                    self.port_queues[port_identifier].put(f"Failed to sync time for {port_identifier}: {e}")
                    self.time_sync_commands[port_identifier] = ('done', time.time())

    def sync_all_device_times(self):
        threading.Thread(target=self.sync_all_device_times_thread, daemon=True).start()

    def start_experiment(self):
        if not self.connected_ports:
            messagebox.showwarning("No Devices", "No FED3 devices are connected.")
            return
        if not self.experimenter_name.get() or not self.experiment_name.get():
            messagebox.showerror("Error", "Please provide your name and experiment name.")
            return
        if not self.save_path or not self.flat_data_path:
            messagebox.showerror("Error", "Please provide both Experiment Folder and Flat Data Folder.")
            return
        self.experimenter_entry.config(state='disabled')
        self.experiment_entry.config(state='disabled')
        self.start_button.config(state='disabled')
        self.logging_active = True
        self.experimenter_name.set(self.experimenter_name.get().strip().lower())
        self.experiment_name.set(self.experiment_name.get().strip().lower())
        for p in self.port_widgets.keys():
            self.data_to_save[p] = []
        current_time = datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        experimenter_name = re.sub(r'[<>:"/\\|?*]', '_', self.experimenter_name.get())
        experiment_name = re.sub(r'[<>:"/\\|?*]', '_', self.experiment_name.get())
        experimenter_folder = os.path.join(self.save_path, experimenter_name)
        self.experiment_folder = os.path.join(experimenter_folder, f"{experiment_name}_{current_time}")
        os.makedirs(self.experiment_folder, exist_ok=True)
        self.stop_identification_threads()
        device_mappings = get_device_mappings_by_usb_port()
        for m in device_mappings:
            port_identifier = m['port_identifier']
            serial_port = m['serial_port']
            self.start_logging_for_port(serial_port, port_identifier)
        self.display_recording_indicator()
        self.session_start_time = datetime.datetime.now()
        self.update_session_timer()

    def start_logging_for_port(self, serial_port, port_identifier):
        if port_identifier in self.serial_ports:
            return
        gpio_pins = gpio_pins_per_device.get(port_identifier)
        if not gpio_pins:
            return
        q = self.port_queues[port_identifier]
        status_label = self.port_widgets[port_identifier]['status_label']
        logging.info(f"Starting logging thread for {port_identifier} on {serial_port}")
        t = threading.Thread(target=read_from_fed, args=(serial_port, port_identifier, gpio_pins, q, status_label, self))
        t.daemon = True
        t.start()
        self.threads.append(t)
        self.serial_ports[port_identifier] = serial_port

    def stop_identification_threads(self):
        for port, event in list(self.identification_stop_events.items()):
            event.set()
        for port, t in list(self.identification_threads.items()):
            t.join()
            del self.identification_threads[port]
            del self.identification_stop_events[port]

    def update_gui(self):
        for port_identifier, q in self.port_queues.items():
            try:
                while True:
                    message = q.get_nowait()
                    if isinstance(message, list):
                        #self.data_to_save[port_identifier].append(message)
                        continue
                    elif message == "Ready":
                        self.port_widgets[port_identifier]['status_label'].config(text="Connected", foreground="green")
                    else:
                        text_widget = self.port_widgets[port_identifier]['text_widget']
                        text_widget.insert(tk.END, message + "\n")
                        text_widget.see(tk.END)
                        self.log_text.insert(tk.END, f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}: {message}\n")
                        self.log_text.see(tk.END)
            except queue.Empty:
                pass
        if time.time() - self.last_device_check_time >= 5:
            self.check_connected_devices()
            self.last_device_check_time = time.time()
        self.root.after(100, self.update_gui)

    def stop_experiment(self):
        if not self.logging_active:
            self.root.quit()
            self.root.destroy()
            return
        stop_event.set()
        for t in self.threads:
            t.join()
        GPIO.cleanup()
        self.save_all_data()
        self.save_summary()
        self.hide_recording_indicator()
        self.logging_active = False
        messagebox.showinfo("Data Saved", "All data has been saved.")
        self.root.quit()
        self.root.destroy()

    def save_all_data(self):
        for port_identifier, data_rows in self.data_to_save.items():
            if data_rows:
                filename_user = os.path.join(self.experiment_folder, f"{port_identifier}.csv")
                try:
                    with open(filename_user, mode='w', newline='') as file:
                        writer = csv.writer(file)
                        writer.writerow(column_headers)
                        writer.writerows(data_rows)
                    logging.info(f"Data saved for {port_identifier} in {filename_user}")
                except Exception as e:
                    logging.error(f"Failed to save data for {port_identifier}: {e}")
                flat_filename = os.path.join(self.flat_data_path, f"{port_identifier}_{datetime.datetime.now().strftime('%Y_%m_%d_%H_%M_%S')}.csv")
                try:
                    with open(flat_filename, mode='w', newline='') as file:
                        writer = csv.writer(file)
                        writer.writerow(column_headers)
                        writer.writerows(data_rows)
                    logging.info(f"Flat copy saved for {port_identifier} in {flat_filename}")
                except Exception as e:
                    logging.error(f"Failed to save flat copy for {port_identifier}: {e}")
            else:
                logging.info(f"No data collected from {port_identifier}, no file saved.")

    def save_summary(self):
        for port_identifier, data_rows in self.data_to_save.items():
            if not data_rows:
                continue
            left_count = right_count = pellet_count = 0
            for row in data_rows:
                if len(row) > 9:
                    ev = row[9].strip().lower()
                    if ev in ["left", "leftwithpellet"]:
                        left_count += 1
                    elif ev in ["right", "rightwithpellet"]:
                        right_count += 1
                    elif ev == "pellet":
                        pellet_count += 1
            summary_filename = os.path.join(self.experiment_folder, f"{port_identifier}_summary.csv")
            try:
                with open(summary_filename, mode='w', newline='') as file:
                    writer = csv.writer(file)
                    writer.writerow(["Event", "Count"])
                    writer.writerow(["Left", left_count])
                    writer.writerow(["Right", right_count])
                    writer.writerow(["Pellet", pellet_count])
                logging.info(f"Summary saved for {port_identifier} in {summary_filename}")
            except Exception as e:
                logging.error(f"Failed to save summary for {port_identifier}: {e}")

    def hide_recording_indicator(self):
        if self.recording_circle is not None:
            self.canvas.delete(self.recording_circle)
            self.recording_circle = None
        if self.recording_label is not None:
            self.canvas.delete(self.recording_label)
            self.recording_label = None
        if self.session_timer_text is not None:
            self.canvas.delete(self.session_timer_text)
            self.session_timer_text = None

    def on_closing(self):
        if self.logging_active:
            if messagebox.askokcancel("Quit", "Logging is active. Do you want to stop and exit?"):
                self.stop_experiment()
        else:
            self.stop_identification_threads()
            self.root.quit()
            self.root.destroy()

    def trigger_indicator(self, port_identifier):
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

if __name__ == "__main__":
    splash_root = tk.Tk()
    splash_screen = SplashScreen(splash_root)
    splash_root.mainloop()

    root = tk.Tk()
    app = FED3MonitorApp(root)
    root.mainloop()


# In[ ]:




