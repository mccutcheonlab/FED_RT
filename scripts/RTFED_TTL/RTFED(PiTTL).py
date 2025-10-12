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
import sys


### just to test GUI on Windows, first remvoe import RPi.GPIO as GPIO, then uncomment below and then run the code,
# try:
#     import RPi.GPIO as GPIO
# except (ImportError, RuntimeError):
#     # Mock GPIO class for non-Pi systems
#     class MockGPIO:
#         BCM = 'BCM'
#         OUT = 'OUT'
#         IN = 'IN'
#         LOW = 0
#         HIGH = 1

#         def setmode(self, mode): print(f"[MockGPIO] setmode({mode})")
#         def setwarnings(self, flag): print(f"[MockGPIO] setwarnings({flag})")
#         def setup(self, pin, mode): print(f"[MockGPIO] setup(pin={pin}, mode={mode})")
#         def output(self, pin, state): print(f"[MockGPIO] output(pin={pin}, state={state})")
#         def input(self, pin): return self.LOW
#         def cleanup(self): print("[MockGPIO] cleanup()")

#     GPIO = MockGPIO()
#     print(" Running with MockGPIO (no real Raspberry Pi GPIO available).")



# after paper revision, I include online mode to PiTTL mode. it helps people who conduct long hours of recording 
import gspread
from google.oauth2.service_account import Credentials
from collections import defaultdict, deque

# Google Sheets Scope
SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
]

# -fter revision comments, adding this batch uploader to limit the rate of uplaods
class SheetsUploader:
    """
    Batches rows from all devices and appends them to Google Sheets
    with a global rate limit (default 1 request/sec) and chunking.
    Keeps one worksheet (tab) per device name (e.g., 'Device_007').
    """

    def __init__(self, gclient, spreadsheet_id, logger=None, rps=1.0, chunk_rows=300):
        self.gc = gclient
        self.logger = (lambda msg: None) if logger is None else logger
        self.rps = max(float(rps), 0.1)
        self.chunk_rows = max(int(chunk_rows), 1)
        self.spreadsheet = self.gc.open_by_key(spreadsheet_id)
        self.ws_cache = {}
        self.buffers = defaultdict(list)  # sheet_name -> list[rows]
        self.lock = threading.Lock()
        self.stop_evt = threading.Event()
        self.worker = threading.Thread(target=self._run, daemon=True)
        self.worker.start()

    def _log(self, msg):
        try:
            self.logger(f"{datetime.datetime.now()}: {msg}")
        except Exception:
            pass

    def _get_ws(self, title):
        ws = self.ws_cache.get(title)
        if ws is not None:
            return ws
        try:
            ws = self.spreadsheet.worksheet(title)
        except gspread.exceptions.WorksheetNotFound:
            ws = self.spreadsheet.add_worksheet(
                title=title, rows="1000", cols=str(len(column_headers))
            )
            ws.append_row(column_headers)
        self.ws_cache[title] = ws
        return ws

    def enqueue(self, sheet_name, rows):
        if not rows:
            return
        with self.lock:
            self.buffers[sheet_name].extend(rows)

    def _send_one_chunk(self, sheet_name, rows):
        ws = self._get_ws(sheet_name)
        ws.append_rows(rows)

    def _run(self):
        rr = deque()
        sleep_between_calls = 1.0 / self.rps
        while not self.stop_evt.is_set():
            with self.lock:
                if not rr:
                    for sheet, rows in list(self.buffers.items()):
                        if rows:
                            rr.append(sheet)
                sheet_name = rr.popleft() if rr else None
                chunk = None
                if sheet_name is not None and self.buffers[sheet_name]:
                    take = min(self.chunk_rows, len(self.buffers[sheet_name]))
                    chunk = self.buffers[sheet_name][:take]
                    del self.buffers[sheet_name][:take]

            if sheet_name is None or chunk is None:
                time.sleep(0.05)
                continue

            try:
                self._send_one_chunk(sheet_name, chunk)
                self._log(f"Wrote {len(chunk)} rows to '{sheet_name}'.")
                time.sleep(sleep_between_calls)  # global rate limit
            except Exception as e:
                self._log(f"Uploader error on '{sheet_name}': {e}. Re-queueing.")
                with self.lock:
                    self.buffers[sheet_name] = chunk + self.buffers.get(sheet_name, [])
                time.sleep(max(1.5, sleep_between_calls))

    def flush_and_stop(self, timeout=10):
        t0 = time.time()
        while time.time() - t0 < timeout:
            with self.lock:
                if not any(self.buffers.values()):
                    break
            time.sleep(0.1)
        self.stop_evt.set()
        self.worker.join(timeout=2)

# ################################

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    stream=sys.stdout
)

# Setup GPIO pins on the Raspberry Pi 
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
    "Retrieval_Time", "InterPelletInterval", "Poke_Time", "PelletsOrTrialToSwitch",
    "Prob_left", "Prob_right", "High_prob_poke"
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
                    # Build a row with PC timestamp in col 0, then incoming fields aligned to your headers
                    event_type = data_list[9].strip()
                    now_ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                    data_list[0] = now_ts  # overwrite device ts with PC ts in position 0
                    # Keep local save
                    app.data_to_save.setdefault(port_identifier, []).append(data_list)

                    # ===== I amding this line after paper revision, it does cache to Google buffer per port & mark last activity =====
                    app.pending_rows.setdefault(port_identifier, []).append(data_list)
                    app.last_activity[port_identifier] = time.time()
                    # ########################## ###############

                    process_event(event_type, port_identifier, gpio_pins, q, app)

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
                    # Look for a CSV response with device identification (device number is on index 5, right?)
                    if len(data_list) >= 6 and "TRIGGER_POKE" not in line:
                        device_number = data_list[5].strip()
                        if device_number:
                            q.put(f"Identified device FED number {device_number} on {port_identifier}")
                            # Store mapping for Google sheet name
                            app.port_to_device_number[port_identifier] = device_number
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
        self.label = tk.Label(self.root, text="McCutcheonlab Innovations\n RTFED(PiTTL)", font=("Cascadia Code", 32, "bold"), bg="black", fg="lavender")
        self.label.pack(expand=True)
        self.root.after(duration, self.close_splash)
    def close_splash(self):
        self.root.destroy()

class FED3MonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("RTFED(PiTTL)")
        self.root.geometry("1280x860")
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
        self.mode_var = tk.StringVar(value="Select Mode")
        self.mode_options = [
            "0 - Free Feeding", "1 - FR1", "2 - FR3", "3 - FR5",
            "4 - Progressive Ratio", "5 - Extinction", "6 - Light Tracking",
            "7 - FR1 (Reversed)", "8 - PR (Reversed)", "9 - Self-Stim",
            "10 - Self-Stim (Reversed)", "11 - Timed Feeding", "12 - ClosedEconomy_PR2",
            "13 - Probabilistic Reversal", "14 - Bandit8020", "15 - DetBandit"
        ]

        self.port_serial_objects = {}  # Mapping: port_identifier -> serial.Serial instance
        self.session_start_time = None
        self.session_timer_text = None
        self.identification_threads = {}
        self.identification_stop_events = {}
        self.stop_event = stop_event
        self.perform_initial_device_mapping()

        # Here we integarte PiTTL with Google####
        self.offline_mode = tk.BooleanVar(value=True)  # Default: Disabled Google
        self.json_path = tk.StringVar()
        self.spreadsheet_id = tk.StringVar()
        self.gspread_client = None
        self.uploader = None
        self.port_to_device_number = {}          # Port -> FED number (for sheet tab)
        self.pending_rows = defaultdict(list)    # Port -> rows pending upload
        self.last_activity = defaultdict(lambda: 0.0)  # Port -> last event ts
        self.inactivity_threshold_s = int(os.environ.get("RTFEDPITTL_SHEETS_INACT_SEC", "120"))
        # 

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

        # but, we only upload periodicly. after inactivity on the port#####
        self.root.after(1000, self._inactivity_upload_tick)

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
            "3) To change mode: tick 'Apply Mode' on target ports, pick a mode, press Set Mode.\n"
            "4) If you restart a FED3 during an experiment, do one at a time, same USB port.\n"
            "5) Ports are assigned based on initial detection order.\n"
            "6) GPIO mapping (Pi 4B):\n\n"
            "Port 1: Left=17, Right=27, Pellet=22\n"
            "Port 2: Left=10, Right=9,  Pellet=11\n"
            "Port 3: Left=0,  Right=5,  Pellet=6\n"
            "Port 4: Left=13, Right=19, Pellet=26\n"
            "Port 5: Left=14, Right=15, Pellet=18\n"
            "Port 6: Left=23, Right=24, Pellet=25\n"
            "Port 7: Left=8,  Right=7,  Pellet=1\n"
            "Port 8: Left=12, Right=16, Pellet=20\n\n"
            "Note: Google Sheets uploads are disabled by default. Enable them by unticking "
            "'Offline mode (local only)'. Uploads occur only after 120 s of no activity per port."
        )
        messagebox.showinfo("Port Assignment, GPIO & Upload Policy", message)

    def identify_single_port(self, port_identifier):
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
                    self.port_to_device_number[port_identifier] = device_number
                else:
                    q.put(" No device_number received.")
        except Exception as e:
            q.put(f"Error re-identifying {port_identifier}: {e}")

    def set_device_mode(self):
        sel = self.mode_var.get()
        if sel == "Select Mode":
            messagebox.showerror("Error", "Please select a valid mode.")
            return
        mode_num = int(sel.split(" - ")[0])

        checked = [pid for pid, pw in self.port_widgets.items()
                   if pw['selected_var'].get()]
        if not checked:
            messagebox.showerror("Error", "Check at least one 'Apply Mode' box.")
            return

        checked.sort(key=lambda p: int(p.split()[1]))
        for pid in checked:
            mapping = next((m for m in get_device_mappings_by_usb_port()
                            if m['port_identifier']==pid), None)
            if not mapping:
                self.port_queues[pid].put("Port not found on USB!")
                continue

            serial_port = mapping['serial_port']
            q = self.port_queues[pid]
            q.put(f" Setting mode {mode_num} on {pid}…")
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
                            q.put(" Mode set FAILED")
                            break
                    if not ok:
                        q.put(" No confirmation, assuming reboot anyway.")
            except Exception as e:
                q.put(f"Error sending SET_MODE to {pid}: {e}")

            time.sleep(5)   # wait for reboot
            self.identify_single_port(pid)

    def create_layout(self):
        # LEFT: Ports grid
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

        # RIGHT: Controls
        controls_frame = ttk.Frame(self.mainframe)
        controls_frame.grid(column=1, row=0, padx=10, pady=10, sticky=(tk.N, tk.S))

        # --- Name / Experiment
        tk.Label(controls_frame, text="Your Name:", font=("Cascadia Code", 12, "bold")).grid(column=0, row=0, sticky=tk.W, pady=5)
        self.experimenter_entry = ttk.Entry(controls_frame, textvariable=self.experimenter_name, width=22)
        self.experimenter_entry.grid(column=1, row=0, sticky=tk.W, pady=5)
        tk.Label(controls_frame, text="Experiment Name:", font=("Cascadia Code", 12, "bold")).grid(column=0, row=1, sticky=tk.W, pady=5)
        self.experiment_entry = ttk.Entry(controls_frame, textvariable=self.experiment_name, width=22)
        self.experiment_entry.grid(column=1, row=1, sticky=tk.W, pady=5)

        # --- Local folders
        browse_main_button = tk.Button(controls_frame, text="Browse Experiment Folder", font=("Cascadia Code", 10), command=self.browse_folder, bg="gold")
        browse_main_button.grid(column=0, row=2, columnspan=2, sticky="we", pady=5)
        browse_flat_button = tk.Button(controls_frame, text="Browse Flat Data Folder", font=("Cascadia Code", 10), command=self.browse_flat_folder, bg="lightblue")
        browse_flat_button.grid(column=0, row=3, columnspan=2, sticky="we", pady=5)

        # --- Identify / Sync
        identify_button = tk.Button(controls_frame, text="Identify Devices", font=("Cascadia Code", 12, "bold"), bg="orange", fg="black", command=self.identify_devices)
        identify_button.grid(column=0, row=4, columnspan=2, sticky="we", pady=5)
        sync_button = tk.Button(controls_frame, text="Sync Clock", font=("Cascadia Code", 12, "bold"), bg="blue", fg="white", command=self.sync_all_device_times)
        sync_button.grid(column=0, row=5, columnspan=2, sticky="we", pady=5)

        # --- Mode selection
        tk.Label(controls_frame, text="Mode:", font=("Cascadia Code", 12, "bold")
                ).grid(column=0, row=6, sticky=tk.W, pady=5)
        self.mode_menu = ttk.Combobox(
            controls_frame,
            textvariable=self.mode_var,
            values=self.mode_options,
            width=22,
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

        # adding google controls
        self.offline_check = tk.Checkbutton(
            controls_frame,
            text="Offline mode (local only)",
            variable=self.offline_mode,
            font=("Cascadia Code", 11, "bold"),
            command=self.on_offline_toggle
        )
        self.offline_check.grid(column=0, row=8, columnspan=2, sticky="w", pady=(10, 5))

        self.json_label = tk.Label(controls_frame, text="Google API JSON:", font=("Cascadia Code", 10, "bold"))
        self.json_label.grid(column=0, row=9, sticky=tk.E, pady=2)
        self.json_entry = ttk.Entry(controls_frame, textvariable=self.json_path, width=22)
        self.json_entry.grid(column=1, row=9, sticky=tk.W, pady=2)
        self.json_button = tk.Button(controls_frame, text="Browse JSON", font=("Cascadia Code", 9), command=self.browse_json)
        self.json_button.grid(column=0, row=10, columnspan=2, sticky="we", pady=2)

        self.spread_label = tk.Label(controls_frame, text="Spreadsheet ID:", font=("Cascadia Code", 10, "bold"))
        self.spread_label.grid(column=0, row=11, sticky=tk.E, pady=2)
        self.spreadsheet_entry = ttk.Entry(controls_frame, textvariable=self.spreadsheet_id, width=22)
        self.spreadsheet_entry.grid(column=1, row=11, sticky=tk.W, pady=2)

        tk.Label(controls_frame, text=f"Upload only after inactivity ≥ {self.inactivity_threshold_s}s per port",
                 font=("Cascadia Code", 8, "italic")).grid(column=0, row=12, columnspan=2, sticky="w", pady=(2, 8))

        #  Start/Stop
        self.start_button = tk.Button(controls_frame, text="START", font=("Cascadia Code", 12, "bold"), bg="green", fg="white", command=self.start_experiment)
        self.start_button.grid(column=0, row=13, columnspan=2, sticky="we", pady=10)
        self.stop_button = tk.Button(controls_frame, text="STOP & SAVE", font=("Cascadia Code", 12, "bold"), bg="red", fg="white", command=self.stop_experiment)
        self.stop_button.grid(column=0, row=14, columnspan=2, sticky="we", pady=10)

        # ###############Recording indicator + timer
        self.canvas = tk.Canvas(controls_frame, width=140, height=130)
        self.canvas.grid(column=0, row=15, columnspan=2, pady=12)
        self.recording_circle = None
        self.recording_label = None

        # Log box (bottom, full width)
        log_frame = ttk.Frame(self.mainframe)
        log_frame.grid(column=0, row=1, columnspan=2, pady=10, sticky=(tk.N, tk.S, tk.E, tk.W))
        log_frame.grid_columnconfigure(0, weight=1)
        self.log_text = tk.Text(log_frame, height=10, width=130, font=("Cascadia Code", 10))
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.configure(yscrollcommand=log_scrollbar.set)

        # Apply initial offline state to inputs
        self.on_offline_toggle()

    def on_offline_toggle(self):
        if self.offline_mode.get():
            # disable Google inputs
            self.json_entry.config(state='disabled')
            self.spreadsheet_entry.config(state='disabled')
            self.json_button.config(state='disabled')
            self.spread_label.config(text="Spreadsheet ID: (ignored in Offline)")
            self.json_label.config(text="Google API JSON: (ignored in Offline)")
            self._log_ui("Offline mode enabled: Google Sheets will be ignored; logging locally only.")
        else:
            self.json_entry.config(state='normal')
            self.spreadsheet_entry.config(state='normal')
            self.json_button.config(state='normal')
            self.spread_label.config(text="Spreadsheet ID:")
            self.json_label.config(text="Google API JSON:")
            self._log_ui("Offline mode disabled: Google Sheets upload available.")

    def _log_ui(self, msg):
        self.log_text.insert(tk.END, f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}: {msg}\n")
        self.log_text.see(tk.END)

    def setup_port(self, parent, port_name, r, c):
        frame = ttk.LabelFrame(parent, text=port_name, padding="3")
        frame.grid(column=c, row=r, padx=10, pady=10, sticky=(tk.N, tk.S, tk.W, tk.E))
        status_label = ttk.Label(frame, text="Not Connected", font=("Cascadia Code", 10), foreground="red")
        status_label.grid(column=0, row=0, sticky=tk.W)
        indicator_canvas = tk.Canvas(frame, width=20, height=20)
        indicator_canvas.grid(column=1, row=0, padx=5)
        indicator_circle = indicator_canvas.create_oval(5, 5, 15, 15, fill="gray")
        text_widget = tk.Text(frame, width=40, height=6, wrap=tk.WORD, font=("Cascadia Code", 9))
        text_widget.grid(column=0, row=1, columnspan=2, sticky=(tk.N, tk.S, tk.W, tk.E))
        self.port_widgets[port_name] = {
            'status_label': status_label,
            'text_widget': text_widget,
            'indicator_canvas': indicator_canvas,
            'indicator_circle': indicator_circle
        }
        selected_var = tk.BooleanVar(value=True)
        chk = tk.Checkbutton(frame, text="Apply Mode", variable=selected_var, font=("Cascadia Code", 10))
        chk.grid(column=0, row=2, sticky=tk.W, pady=(5,0))
        self.port_widgets[port_name]['selected_var'] = selected_var
        self.port_queues[port_name] = queue.Queue()

    def browse_folder(self):
        self.save_path = filedialog.askdirectory(title="Select Experiment Folder")

    def browse_flat_folder(self):
        self.flat_data_path = filedialog.askdirectory(title="Select Flat Data Folder")

    # Google helpers added after revision 
    def browse_json(self):
        self.json_path.set(filedialog.askopenfilename(title="Select Google API JSON"))

    def _init_google_if_needed(self):
        """Initialises Google client and uploader, if not offline and not yet done."""
        if self.offline_mode.get():
            self.gspread_client = None
            self.uploader = None
            return True
        if not self.json_path.get() or not self.spreadsheet_id.get():
            messagebox.showerror("Error", "Please provide the Google API JSON file and Spreadsheet ID (or enable Offline mode).")
            return False
        try:
            creds = Credentials.from_service_account_file(self.json_path.get(), scopes=SCOPE)
            self.gspread_client = gspread.authorize(creds)
            rps = float(os.environ.get("RTFED_SHEETS_RPS", "1"))
            chunk_rows = int(os.environ.get("RTFED_CHUNK_ROWS", "300"))
            self.uploader = SheetsUploader(
                self.gspread_client,
                self.spreadsheet_id.get(),
                logger=self._log_ui,
                rps=rps,
                chunk_rows=chunk_rows
            )
            self._log_ui(f"Connected to Google Sheets (rps={rps}, chunk_rows={chunk_rows}).")
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Failed to initialise Google Sheets: {e}")
            return False
    # =################################----######################################################################## 

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
            self.recording_circle = self.canvas.create_oval(20, 10, 80, 70, fill="red")
        if self.recording_label is None:
            self.recording_label = self.canvas.create_text(50, 80, text="RECORDING", font=("Cascadia Code", 10), anchor="n")
        if self.session_timer_text is None:
            self.session_timer_text = self.canvas.create_text(50, 100, text="Time: 00:00:00", font=("Cascadia Code", 8), anchor="n")

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
        last_port = None
        for m in device_mappings:
            port_identifier = m['port_identifier']
            last_port = port_identifier
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
                        self.port_to_device_number[port_identifier] = device_number
                    else:
                        q.put(f"No valid device number received from {port_identifier}.")
            except Exception as e:
                q.put(f"Error sending poke command to {port_identifier}: {e}")
        if last_port is not None:
            self.port_queues[last_port].put("Identification process complete.")

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

        # Init Google if enabled
        if not self._init_google_if_needed():
            return

        self.experimenter_entry.config(state='disabled')
        self.experiment_entry.config(state='disabled')
        self.start_button.config(state='disabled')
        self.logging_active = True
        self.experimenter_name.set(self.experimenter_name.get().strip().lower())
        self.experiment_name.set(self.experiment_name.get().strip().lower())

        for p in self.port_widgets.keys():
            self.data_to_save[p] = []
            self.pending_rows[p] = []
            self.last_activity[p] = 0.0  # "no activity yet"

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

    # =the inactivity gate uplaoder # # # # #23####
    def _inactivity_upload_tick(self):
        try:
            if self.logging_active and self.uploader is not None:
                now = time.time()
                for port, rows in list(self.pending_rows.items()):
                    if not rows:
                        continue
                    last = self.last_activity.get(port, 0.0)
                    if last == 0.0:
                        # no activity yet -> don't upload
                        continue
                    if (now - last) >= self.inactivity_threshold_s:
                        # decide worksheet name
                        devnum = self.port_to_device_number.get(port)
                        sheet_name = f"Device_{devnum}" if devnum else f"{port.replace(' ', '_')}"
                        # enqueue a chunk and clear cache for that port
                        try:
                            self.uploader.enqueue(sheet_name, rows[:])
                            self._log_ui(f"Enqueued {len(rows)} rows to '{sheet_name}' after inactivity on {port}.")
                            self.pending_rows[port].clear()
                        except Exception as e:
                            self._log_ui(f"Enqueue error for {port}: {e}")
        finally:
            # schedule next tick
            self.root.after(1000, self._inactivity_upload_tick)
    # ##############################################

    def stop_experiment(self):
        if not self.logging_active:
            self.root.quit()
            self.root.destroy()
            return
        stop_event.set()
        for t in self.threads:
            t.join()
        GPIO.cleanup()

        # Final push of any pending rows (even if activity < threshold)
        if self.uploader is not None:
            for port, rows in list(self.pending_rows.items()):
                if rows:
                    devnum = self.port_to_device_number.get(port)
                    sheet_name = f"Device_{devnum}" if devnum else f"{port.replace(' ', '_')}"
                    try:
                        self.uploader.enqueue(sheet_name, rows[:])
                        self._log_ui(f"Final enqueue {len(rows)} rows to '{sheet_name}' on STOP.")
                        self.pending_rows[port].clear()
                    except Exception as e:
                        self._log_ui(f"Final enqueue error for {port}: {e}")
            try:
                self.uploader.flush_and_stop(timeout=15)
                self._log_ui("SheetsUploader flushed.")
            except Exception as e:
                self._log_ui(f"SheetsUploader flush error: {e}")

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
            # If an uploader exists, flush it for good measure
            try:
                if self.uploader:
                    self.uploader.flush_and_stop(timeout=10)
            except Exception as e:
                self._log_ui(f"SheetsUploader flush error on close: {e}")
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
