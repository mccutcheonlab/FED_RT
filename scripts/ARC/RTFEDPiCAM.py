#!/usr/bin/env python
# coding: utf-8

# In[ ]:


#!/usr/bin/env python3
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
import cv2
import webbrowser
import logging

# Column headers
column_headers = [
    "MM/DD/YYYY hh:mm:ss.SSS", "Temp", "Humidity", "Library_Version", "Session_type",
    "Device_Number", "Battery_Voltage", "Motor_Turns", "FR", "Event", "Active_Poke",
    "Left_Poke_Count", "Right_Poke_Count", "Pellet_Count", "Block_Pellet_Count",
    "Retrieval_Time", "InterPelletInterval", "Poke_Time",
    "PelletsOrTrialToSwitch", "Prob_left", "Prob_right", "High_prob_poke"  
]


# Google Sheets Scope
SCOPE = [
    "https://spreadsheets.google.com/feeds",
    'https://www.googleapis.com/auth/spreadsheets',
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
]

class SplashScreen:
    def __init__(self, root, duration=6000):
        self.root = root
        self.duration = duration
        self.root.overrideredirect(True)
        self.root.attributes("-alpha", 1)
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"{sw}x{sh}+0+0")
        self.root.configure(bg="black")
        self.label = tk.Label(
            self.root,
            text="McCutcheonLab Technologies\nRTFED(PiCAM)\nDetecting USB Cameras...",
            font=("Cascadia Code", 32, "bold"),
            bg="black",
            fg="violet"
        )
        self.label.pack(expand=True)
        self.fade_in(1000, self.start_camera_detection)

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

    def start_camera_detection(self):
        self.label.config(text="McCutcheonLab Technologies\nRTFED(PiCAM)\nDetecting USB Cameras...")
        self.camera_indices = []
        for index in range(20):
            cap = cv2.VideoCapture(index)
            if cap.read()[0]:
                self.camera_indices.append(str(index))
            cap.release()
        self.fade_out(2000, self.close)

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
    def __init__(self, root, camera_indices):
        self.root = root
        self.root.title("RTFED(PiCAM)")
        self.root.geometry("1200x800")
        self.logger = logging.getLogger()

        # State variables
        self.experimenter_name = tk.StringVar()
        self.experiment_name   = tk.StringVar()
        self.json_path         = tk.StringVar()
        self.spreadsheet_id    = tk.StringVar()
        self.video_trigger     = tk.StringVar(value="Pellet")
        self.save_path         = ""
        self.data_queue        = queue.Queue()
        self.serial_ports      = set(self.detect_serial_ports())
        self.threads           = []
        self.port_widgets      = {}
        self.port_queues       = {}
        self.port_threads      = {}
        self.identification_threads = {}
        self.identification_stop_events = {}
        self.log_queue         = queue.Queue()
        self.data_to_save      = {}
        self.stop_event        = threading.Event()
        self.logging_active    = False
        self.data_saved        = False
        self.gspread_client    = None
        self.last_device_check_time = time.time()
        self.retry_attempts    = 5
        self.retry_delay       = 2

        # Thread safety
        self.port_to_device_number_lock = threading.Lock()
        self.data_to_save_lock = threading.Lock()

        # Device mappings
        self.port_to_device_number = {}
        self.device_number_to_port = {}
        self.port_to_serial = {}

        # Camera handling
        self.port_to_camera_index = {}
        self.camera_objects = {}
        self.recording_states = {}
        self.last_event_times = {}
        self.recording_locks = {}
        self.camera_indices = camera_indices

        # Time sync commands
        self.time_sync_commands = {}

        # Mode selection
        self.mode_var = tk.StringVar(value="Select Mode")

        self.build_gui()
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

    def build_gui(self):
        # Configure root grid
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=0)
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=0)
        self.root.grid_rowconfigure(2, weight=0)

        # Main container frame
        main = ttk.Frame(self.root)
        main.grid(row=0, column=0, columnspan=2, sticky="nsew")
        main.grid_columnconfigure(0, weight=1)
        main.grid_columnconfigure(1, weight=0)
        main.grid_rowconfigure(0, weight=1)

  
        ports_container = ttk.Frame(main)
        ports_container.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        ports_container.grid_rowconfigure(0, weight=1)
        ports_container.grid_columnconfigure(0, weight=1)

        ports_canvas = tk.Canvas(ports_container)
        ports_scrollbar = ttk.Scrollbar(ports_container, orient="vertical", command=ports_canvas.yview)
        ports_canvas.configure(yscrollcommand=ports_scrollbar.set)
        ports_scrollbar.grid(row=0, column=1, sticky="ns")
        ports_canvas.grid(row=0, column=0, sticky="nsew")

        self.ports_frame = ttk.Frame(ports_canvas)
        ports_canvas.create_window((0, 0), window=self.ports_frame, anchor="nw")
        self.ports_frame.bind(
            "<Configure>",
            lambda event: ports_canvas.configure(scrollregion=ports_canvas.bbox("all"))
        )

        if not self.serial_ports:
            ttk.Label(self.ports_frame, text="Connect your FED3 devices and restart the GUI!",
                      font=("Cascadia Code", 14), foreground="red").pack(pady=20)
        else:
            for idx, port in enumerate(self.serial_ports):
                self.initialize_port_widgets(port, idx)

  
        controls_frame = ttk.Frame(main)
        controls_frame.grid(row=0, column=1, sticky="n", padx=(0,10), pady=10)

        label_font = ("Cascadia Code", 12, "bold")
        entry_font = ("Cascadia Code", 11)

        # Your Name
        ttk.Label(controls_frame, text="Your Name:", font=label_font).grid(column=0, row=0, sticky=tk.W, pady=5)
        self.experimenter_entry = ttk.Entry(controls_frame, textvariable=self.experimenter_name, width=25, font=entry_font)
        self.experimenter_entry.grid(column=1, row=0, pady=5)

        # Experiment Name
        ttk.Label(controls_frame, text="Experiment Name:", font=label_font).grid(column=0, row=1, sticky=tk.W, pady=5)
        self.experiment_entry = ttk.Entry(controls_frame, textvariable=self.experiment_name, width=25, font=entry_font)
        self.experiment_entry.grid(column=1, row=1, pady=5)

        # JSON File
        ttk.Label(controls_frame, text="Google API JSON File:", font=label_font).grid(column=0, row=2, sticky=tk.W, pady=5)
        self.json_entry = ttk.Entry(controls_frame, textvariable=self.json_path, width=25, font=entry_font)
        self.json_entry.grid(column=1, row=2, pady=5)
        self.browse_json_button = tk.Button(controls_frame, text="Browse", command=self.browse_json, font=("Cascadia Code", 10))
        self.browse_json_button.grid(column=2, row=2, padx=5)

        # Spreadsheet ID
        ttk.Label(controls_frame, text="Google Spreadsheet ID:", font=label_font).grid(column=0, row=3, sticky=tk.W, pady=5)
        self.spreadsheet_entry = ttk.Entry(controls_frame, textvariable=self.spreadsheet_id, width=25, font=entry_font)
        self.spreadsheet_entry.grid(column=1, row=3, pady=5)

        # Browse Data Folder
        self.browse_button = tk.Button(controls_frame, text="Browse Data Folder", font=label_font, bg="gold", fg="blue", command=self.browse_folder)
        self.browse_button.grid(column=0, row=4, columnspan=3, sticky="we", pady=8)

        # Identify / Sync
        self.identify_devices_button = tk.Button(
            controls_frame, text="Identify Devices", bg="orange", fg="black", font=label_font,
            command=self.identify_fed3_devices
        )
        self.identify_devices_button.grid(column=0, row=5, columnspan=3, sticky="we", pady=5)

        self.sync_time_button = tk.Button(
            controls_frame, text="Sync FED3 Time", bg="blue", fg="white", font=label_font,
            command=self.sync_all_device_times
        )
        self.sync_time_button.grid(column=0, row=6, columnspan=3, sticky="we", pady=5)

        # Mode selection
        self.mode_options = [
            "0 - Free Feeding", "1 - FR1", "2 - FR3", "3 - FR5",
            "4 - Progressive Ratio", "5 - Extinction", "6 - Light Tracking",
            "7 - FR1 (Reversed)", "8 - PR (Reversed)", "9 - Self-Stim",
            "10 - Self-Stim (Reversed)", "11 - Timed Feeding", "12 - ClosedEconomy_PR2",
            "13 - Probabilistic Reversal", "14 - Bandit8020", "15 - DetBandit"
        ]
        ttk.Label(controls_frame, text="Mode:", font=label_font).grid(column=0, row=7, sticky=tk.W, pady=5)
        self.mode_menu = ttk.Combobox(
            controls_frame,
            textvariable=self.mode_var,
            values=self.mode_options,
            width=23,
            state="readonly",
            font=entry_font
        )
        self.mode_menu.grid(column=1, row=7, columnspan=2, pady=5)

        self.set_mode_button = tk.Button(
            controls_frame,
            text="Set Mode",
            bg="darkorange",
            fg="black",
            font=label_font,
            command=self.set_device_mode
        )
        self.set_mode_button.grid(column=0, row=8, columnspan=3, sticky="we", pady=5)

        # Video trigger
        ttk.Label(controls_frame, text="Video Trigger:", font=label_font).grid(column=0, row=9, sticky=tk.W, pady=5)
        self.video_trigger_menu = ttk.Combobox(
            controls_frame,
            textvariable=self.video_trigger,
            values=["Pellet", "Left", "Right", "All"],
            width=23,
            state="readonly",
            font=entry_font
        )
        self.video_trigger_menu.grid(column=1, row=9, columnspan=2, pady=5)

        # START / STOP
        self.start_button = tk.Button(controls_frame, text="START", font=label_font, bg="green", fg="white", command=self.start_logging)
        self.start_button.grid(column=0, row=10, columnspan=3, sticky="we", pady=(10,5))
        self.stop_button = tk.Button(controls_frame, text="STOP (SAVE & QUIT)", font=label_font, bg="red", fg="white", command=self.stop_logging)
        self.stop_button.grid(column=0, row=11, columnspan=3, sticky="we", pady=5)

        # Recording indicator
        self.canvas = tk.Canvas(controls_frame, width=100, height=100)
        self.canvas.grid(column=0, row=12, columnspan=3, pady=15)
        self.recording_circle = self.canvas.create_oval(25, 25, 75, 75, fill="Orange")
        self.recording_label = self.canvas.create_text(50, 90, text="Standby", font=("Cascadia Code", 12), fill="black")

      
        log_frame = ttk.Frame(self.root)
        log_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=10, pady=5)
        self.log_text = tk.Text(log_frame, height=10, width=140, font=("Cascadia Code", 10))
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview).pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.configure(yscrollcommand=self.log_text.yview)

       
        footer = ttk.Frame(self.root)
        footer.grid(row=2, column=0, columnspan=2, sticky="we", pady=5)
        ttk.Label(footer, text="© 2025 McCutcheonLab | UiT | Norway",
                  font=("Cascadia Code", 10), foreground="royalblue").pack()
        hyperlink_label = tk.Label(
            footer,
            text="Developed by Hamid Taghipourbibalan",
            font=("Cascadia Code", 10, "italic"),
            fg="blue",
            cursor="hand2"
        )
        hyperlink_label.pack()
        hyperlink_label.bind("<Button-1>", lambda e: webbrowser.open_new(
            "https://www.linkedin.com/in/hamid-taghipourbibalan-b7239088/"
        ))

    def show_instruction_popup(self):
        messagebox.showinfo(
            "Instructions",
            "1) Have you flashed your FED3 with the RTFED library? You should see the RTT label on your FED3 screen.\n"
            "2) Press [Identify Devices] to trigger poke commands and identify devices.\n"
            "3) After identification, you can [Sync FED3 Time] and set modes via the checkboxes + dropdown.\n"
            "4) Select a video trigger (Pellet, Left, Right, or All) before START."
        )
        messagebox.showwarning(
            "Caution",
            "1. If restarting a FED3 after START, do it one at a time with internet on.\n"
            "2. Use a powered USB hub for multiple FED3s and cameras.\n"
            "3. Do not unplug paired cameras after START.\n"
            "4. Up to 20 cameras can be detected.\n"
            "5. Ensure sufficient disk space for video recordings."
        )

    def browse_json(self):
        filename = filedialog.askopenfilename(
            title="Select JSON File", filetypes=[("JSON Files", "*.json")]
        )
        if filename:
            self.json_path.set(filename)
            self.logger.info(f"Selected JSON file: {filename}")

    def browse_folder(self):
        folder = filedialog.askdirectory(title="Select Folder to Save Data")
        if folder:
            self.save_path = folder
            self.log_queue.put(f"Data folder selected: {self.save_path}")
            self.logger.info(f"Data folder selected: {self.save_path}")

    def initialize_port_widgets(self, port, idx=None):
        if port in self.port_widgets:
            return
        if idx is None:
            idx = len(self.port_widgets)
        port_name = os.path.basename(port)
        frame = ttk.LabelFrame(self.ports_frame, text=f"Port {port_name}")
        frame.grid(column=idx % 2, row=idx // 2, padx=10, pady=10, sticky="nw")

        status_label = ttk.Label(frame, text="Not Ready",
                                 font=("Cascadia Code", 10, "italic"),
                                 foreground="red")
        status_label.grid(column=0, row=0, sticky=tk.W)
        indicator_canvas = tk.Canvas(frame, width=20, height=20)
        indicator_canvas.grid(column=1, row=0, padx=5)
        indicator_circle = indicator_canvas.create_oval(5, 5, 15, 15, fill="gray")

        ttk.Label(frame, text="Camera Index:", font=("Cascadia Code", 9))\
            .grid(column=0, row=1, sticky=tk.W)
        camera_var = tk.StringVar(value="None")
        camera_combobox = ttk.Combobox(
            frame, textvariable=camera_var, values=["None"] + self.camera_indices,
            width=8, font=("Cascadia Code", 9)
        )
        camera_combobox.grid(column=1, row=1, sticky=tk.W)
        test_cam_button = tk.Button(
            frame, text="Test Cam", font=("Cascadia Code", 9),
            command=lambda p=port: self.test_camera(p)
        )
        test_cam_button.grid(column=2, row=1, padx=5)

        mode_label = ttk.Label(frame, text="Mode: Unknown", font=("Cascadia Code", 9))
        mode_label.grid(column=0, row=2, sticky=tk.W)
        selected_var = tk.BooleanVar(value=True)
        tk.Checkbutton(frame, text="Apply Mode", variable=selected_var,
                       font=("Cascadia Code", 10))\
            .grid(column=1, row=2, sticky=tk.W)

        text_widget = tk.Text(frame, width=50, height=8, font=("Cascadia Code", 9))
        text_widget.grid(column=0, row=3, columnspan=3, pady=5, sticky=(tk.W, tk.E))

        self.port_widgets[port] = {
            'status_label': status_label,
            'indicator_canvas': indicator_canvas,
            'indicator_circle': indicator_circle,
            'camera_var': camera_var,
            'camera_combobox': camera_combobox,
            'test_cam_button': test_cam_button,
            'mode_label': mode_label,
            'selected_var': selected_var,
            'text_widget': text_widget
        }
        self.port_queues[port] = queue.Queue()

        # Quick port readiness test
        try:
            ser = serial.Serial(port, 115200, timeout=1)
            ser.close()
            status_label.config(text="Ready", foreground="green")
        except serial.SerialException as e:
            status_label.config(text="Not Ready", foreground="red")
            self.log_queue.put(f"Error with port {port}: {e}")
            self.logger.error(f"Error with port {port}: {e}")

    def test_camera(self, port):
        camera_index_str = self.port_widgets[port]['camera_var'].get()
        if camera_index_str == 'None':
            messagebox.showinfo("Info", "Please select a camera index to test.")
            self.logger.info("Camera test attempted with no camera selected.")
            return
        camera_index = int(camera_index_str)
        cap = cv2.VideoCapture(camera_index)
        if not cap.isOpened():
            messagebox.showerror("Error", f"Cannot open camera {camera_index}")
            self.logger.error(f"Cannot open camera {camera_index}")
            return
        cv2.namedWindow(f"Camera {camera_index}", cv2.WINDOW_NORMAL)
        cv2.resizeWindow(f"Camera {camera_index}", 640, 480)
        start_time = time.time()
        while time.time() - start_time < 5:
            ret, frame = cap.read()
            if not ret:
                break
            cv2.imshow(f"Camera {camera_index}", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        cap.release()
        cv2.destroyWindow(f"Camera {camera_index}")
        self.logger.info(f"Camera {camera_index} tested for port {port}")

    def start_identification_threads(self):
        for port in self.serial_ports:
            if port not in self.port_to_device_number:
                self.start_identification_thread(port)

    def start_identification_thread(self, port):
        if port in self.identification_threads:
            return
        stop_event = threading.Event()
        self.identification_stop_events[port] = stop_event

        def identification_with_delay():
            time.sleep(1)
            self.identification_thread(port, stop_event)

        t = threading.Thread(target=identification_with_delay, daemon=True)
        t.start()
        self.identification_threads[port] = t
        self.log_queue.put(f"Started identification thread for {port}.")
        self.logger.info(f"Started identification thread for {port}.")

    def stop_identification_threads(self):
        for port, event in list(self.identification_stop_events.items()):
            event.set()
        for port, t in list(self.identification_threads.items()):
            t.join()
            self.log_queue.put(f"Stopped identification thread for {port}.")
            self.logger.info(f"Stopped identification thread for {port}.")
            del self.identification_threads[port]
            del self.identification_stop_events[port]

    def identification_thread(self, port, stop_event):
        if port in self.port_to_device_number:
            return
        try:
            ser = serial.Serial(port, 115200, timeout=0.1)
            event_idx_hdr = column_headers.index("Event")
            event_idx_data = event_idx_hdr - 1
            devnum_idx_hdr = column_headers.index("Device_Number")
            devnum_idx_data = devnum_idx_hdr - 1
            device_number_found = None
            while not stop_event.is_set():
                line = ser.readline().decode('utf-8', errors='replace').strip()
                if line and "," in line:
                    data_list = line.split(",")[1:]
                    if len(data_list) == len(column_headers) - 1:
                        ev = data_list[event_idx_data].strip()
                        dn = data_list[devnum_idx_data].strip()
                        if dn:
                            device_number_found = dn
                            break
            ser.close()
        except Exception as e:
            self.log_queue.put(f"Error in identification thread for {port}: {e}")
            self.logger.error(f"Error in identification thread for {port}: {e}")
            try:
                ser.close()
            except:
                pass
            return

        if device_number_found:
            self.log_queue.put(f"Identified device_number={device_number_found} on port={port}")
            self.logger.info(f"Identified device_number={device_number_found} on port={port}")
            self.register_device_number(port, device_number_found)

    def register_device_number(self, port, device_number):
        with self.port_to_device_number_lock:
            if device_number in self.device_number_to_port:
                old = self.device_number_to_port[device_number]
                if old != port:
                    self.log_queue.put(f"Device {device_number} reconnected on {port} (was on {old}).")
                    self.logger.info(f"Device {device_number} reconnected on {port} (was on {old}).")
                    del self.port_to_device_number[old]
            self.port_to_device_number[port] = device_number
            self.device_number_to_port[device_number] = port
        if self.logging_active:
            self.start_logging_for_port(port)

    def identify_fed3_devices(self):
        self.stop_identification_threads()
        if not self.serial_ports:
            self.log_queue.put("No FED3 devices detected.")
            messagebox.showwarning("Warning", "No FED3 devices detected. Connect devices first!")
            return
        self.log_queue.put("Identifying devices by triggering poke on all FED3s...")
        threading.Thread(target=self.trigger_poke_for_identification, daemon=True).start()

    def trigger_poke_for_identification(self):
        for port in list(self.serial_ports):
            try:
                with serial.Serial(port, 115200, timeout=1) as ser:
                    ser.write(b'TRIGGER_POKE\n')
                    start_time = time.time()
                    dn = None
                    while time.time() - start_time < 3:
                        line = ser.readline().decode('utf-8', errors='replace').strip()
                        if "," in line:
                            parts = line.split(",")
                            if len(parts) >= 6:
                                dn = parts[5].strip()
                                break
                    if dn:
                        self.register_device_number(port, dn)
                        self.log_queue.put(f"Identified device_number={dn} on port={port}")
                    else:
                        self.log_queue.put(f"No valid device number from {port}.")
            except Exception as e:
                self.log_queue.put(f"Error sending poke to {port}: {e}")

    def sync_all_device_times(self):
        now = datetime.datetime.now()
        timestr = f"SET_TIME:{now.year},{now.month},{now.day},{now.hour},{now.minute},{now.second}\n"
        if not self.port_to_device_number:
            self.log_queue.put("No devices to sync.")
            return
        self.log_queue.put(f"Syncing FED3 time: {timestr.strip()}")
        if self.logging_active:
            for port in self.port_to_device_number:
                ser = self.port_to_serial.get(port)
                if ser and ser.is_open:
                    self.time_sync_commands[port] = ('pending', time.time())
                    try:
                        ser.write(timestr.encode('utf-8'))
                    except Exception as e:
                        self.log_queue.put(f"Failed sync on {port}: {e}")
        else:
            for port in self.port_to_device_number:
                self.time_sync_commands[port] = ('pending', time.time())
                try:
                    with serial.Serial(port, 115200, timeout=2) as ser:
                        ser.write(timestr.encode('utf-8'))
                        st = time.time()
                        while time.time() - st < 2:
                            line = ser.readline().decode().strip()
                            if line in ("TIME_SET_OK","TIME_SET_FAIL"):
                                self.log_queue.put(f"{port} sync resp: {line}")
                                break
                except Exception as e:
                    self.log_queue.put(f"Failed sync on {port}: {e}")

    def set_device_mode(self):
        sel = self.mode_var.get()
        if sel == "Select Mode":
            messagebox.showerror("Error", "Please select a valid mode.")
            return
        mode_num = int(sel.split(" - ")[0])
        ports = [p for p, w in self.port_widgets.items() if w['selected_var'].get()]
        if not ports:
            messagebox.showwarning("Warning", "No devices selected.")
            return
        for port in ports:
            try:
                with serial.Serial(port, 115200, timeout=2) as ser:
                    ser.write(f"SET_MODE:{mode_num}\n".encode())
                    st = time.time()
                    while time.time() - st < 3:
                        r = ser.readline().decode().strip()
                        if r == "MODE_SET_OK":
                            self.log_queue.put(f"Mode {mode_num} set on {port}")
                            self.port_widgets[port]['mode_label'].config(text=f"Mode: {sel}")
                            break
            except Exception as e:
                self.log_queue.put(f"Error setting mode on {port}: {e}")

    def start_logging(self):
        self.stop_identification_threads()
        self.stop_event.clear()
        self.logging_active = True
        # sanitize names
        self.experimenter_name.set(re.sub(r'[<>:"/\\|?*]', '_', self.experimenter_name.get().strip().lower()))
        self.experiment_name.set(re.sub(r'[<>:"/\\|?*]', '_', self.experiment_name.get().strip().lower()))
        self.json_path.set(self.json_path.get().strip())
        self.spreadsheet_id.set(self.spreadsheet_id.get().strip())
        if not self.experimenter_name.get() or not self.experiment_name.get():
            messagebox.showerror("Error", "Provide name & experiment name.")
            return
        if not self.json_path.get() or not self.spreadsheet_id.get() or not self.save_path:
            messagebox.showerror("Error", "Provide JSON file, Spreadsheet ID, and data folder.")
            return
        try:
            creds = Credentials.from_service_account_file(self.json_path.get(), scopes=SCOPE)
            self.gspread_client = gspread.authorize(creds)
            self.log_queue.put("Connected to Google Sheets!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to connect to Google Sheets: {e}")
            return

        # disable inputs
        self.experimenter_entry.config(state='disabled')
        self.experiment_entry.config(state='disabled')
        self.json_entry.config(state='disabled')
        self.spreadsheet_entry.config(state='disabled')
        self.browse_json_button.config(state='disabled')
        self.browse_button.config(state='disabled')
        self.start_button.config(state='disabled')
        self.video_trigger_menu.config(state='disabled')
        self.mode_menu.config(state='disabled')
        self.set_mode_button.config(state='disabled')
        self.identify_devices_button.config(state='disabled')
        self.sync_time_button.config(state='disabled')

        # recording indicator
        self.canvas.itemconfig(self.recording_circle, fill="yellow")
        self.canvas.itemconfig(self.recording_label, text="Logging...", fill="black")

        # prepare experiment folder
        now = datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        base = os.path.join(self.save_path, self.experimenter_name.get())
        self.experiment_folder = os.path.join(base, f"{self.experiment_name.get()}_{now}")
        os.makedirs(self.experiment_folder, exist_ok=True)
        self.log_queue.put(f"Experiment folder: {self.experiment_folder}")

        # setup cameras
        for port, wd in self.port_widgets.items():
            wd['camera_combobox'].config(state='disabled')
            wd['test_cam_button'].config(state='disabled')
            ci = wd['camera_var'].get()
            ci = None if ci=='None' else int(ci)
            self.port_to_camera_index[port] = ci

        for port, ci in self.port_to_camera_index.items():
            if ci is not None:
                cam = cv2.VideoCapture(ci)
                if cam.isOpened():
                    self.camera_objects[ci] = cam
                    self.log_queue.put(f"Camera {ci} for port {port}.")
                    st = self.port_widgets[port]['status_label'].cget("text")
                    if "Ready" in st:
                        self.port_widgets[port]['status_label'].config(text="Ready (CAM Ready)", foreground="green")
                else:
                    self.log_queue.put(f"Camera {ci} failed for port {port}.")
                    st = self.port_widgets[port]['status_label'].cget("text")
                    if "Ready" in st:
                        self.port_widgets[port]['status_label'].config(text="Ready (CAM Not Connected)", foreground="orange")
                    cam.release()
            self.recording_states[port] = False
            self.last_event_times[port] = None
            self.recording_locks[port] = threading.Lock()

        # start logging threads
        for port in list(self.serial_ports):
            if port in self.port_to_device_number:
                self.start_logging_for_port(port)
            else:
                self.log_queue.put(f"No device_number for {port}; waiting...")

    def start_logging_for_port(self, port):
        if port in self.port_threads:
            return
        dn = self.port_to_device_number.get(port)
        if not dn:
            self.log_queue.put(f"No device_number for {port}; cannot log yet.")
            return
        ws_name = f"Device_{dn}"

        def attempt_connection():
            for attempt in range(self.retry_attempts):
                try:
                    ser = serial.Serial(port, 115200, timeout=0.1)
                    with self.data_to_save_lock:
                        self.data_to_save[port] = []
                    self.port_to_serial[port] = ser
                    t = threading.Thread(target=self.read_from_port, args=(ser, ws_name, port), daemon=True)
                    t.start()
                    self.port_threads[port] = t
                    self.port_widgets[port]['status_label'].config(text="Ready", foreground="green")
                    self.log_queue.put(f"Started logging from {port} to {ws_name}.")
                    return
                except Exception as e:
                    self.log_queue.put(f"Attempt {attempt+1} error on {port}: {e}")
                    time.sleep(self.retry_delay)
            self.log_queue.put(f"Failed to connect to {port} after retries.")

        threading.Thread(target=attempt_connection, daemon=True).start()

    def read_from_port(self, ser, worksheet_name, port_identifier):
        dn = self.port_to_device_number.get(port_identifier, 'unknown')
        spreadsheet = self.gspread_client.open_by_key(self.spreadsheet_id.get())
        sheet = self.get_or_create_worksheet(spreadsheet, worksheet_name)
        cached_data = []
        send_interval = 5
        last_send = time.time()
        jam_event = False

        ev_idx_hdr = column_headers.index("Event")
        ev_idx_data = ev_idx_hdr - 1
        dn_idx_hdr = column_headers.index("Device_Number")
        dn_idx_data = dn_idx_hdr - 1

        try:
            while not self.stop_event.is_set():
                line = ser.readline().decode('utf-8', errors='replace').strip()
                cmd_info = self.time_sync_commands.get(port_identifier)
                if cmd_info and cmd_info[0] == 'pending':
                    if line in ("TIME_SET_OK","TIME_SET_FAIL"):
                        self.log_queue.put(f"{port_identifier} time sync: {line}")
                        self.time_sync_commands[port_identifier] = ('done', time.time())
                        continue
                    elif time.time() - cmd_info[1] > 2:
                        self.log_queue.put(f"{port_identifier} time sync no resp.")
                        self.time_sync_commands[port_identifier] = ('done', time.time())
                if not line:
                    continue
                parts = line.split(",")[1:]
                if len(parts) != len(column_headers)-1:
                    self.log_queue.put(f"Length mismatch on {port_identifier}: {parts}")
                    continue
                if not self.validate_data(parts):
                    self.log_queue.put(f"Invalid data from {port_identifier}: {parts}")
                    continue
                event = parts[ev_idx_data].strip()
                row = [datetime.datetime.now().strftime("%m/%d/%Y %H:%M:%S.%f")[:-3]] + parts
                cached_data.append(row)
                self.port_queues[port_identifier].put(f"Data logged: {parts}")
                with self.data_to_save_lock:
                    self.data_to_save[port_identifier].append(row)
                if event == "JAM":
                    jam_event = True

                trigger = self.video_trigger.get()
                if ((trigger=="Pellet" and event=="Pellet") or
                    (trigger=="Left" and event=="Left") or
                    (trigger=="Right" and event=="Right") or
                    (trigger=="All" and event in ["Pellet","Left","Right"])):
                    with self.recording_locks[port_identifier]:
                        self.last_event_times[port_identifier] = datetime.datetime.now()
                        if not self.recording_states[port_identifier]:
                            self.recording_states[port_identifier] = True
                            threading.Thread(target=self.record_video, args=(port_identifier,), daemon=True).start()

                now = time.time()
                if now - last_send >= send_interval and cached_data:
                    rows = cached_data[:]
                    def attempt_append(rows):
                        for _ in range(3):
                            try:
                                sheet.append_rows(rows)
                                self.log_queue.put(f"Appended {len(rows)} rows from {port_identifier}")
                                return True
                            except gspread.exceptions.APIError as e:
                                time.sleep(2)
                        return False
                    if attempt_append(rows):
                        cached_data.clear()
                    if jam_event:
                        jam_row = [''] * len(column_headers)
                        jam_row[0] = datetime.datetime.now().strftime("%m/%d/%Y %H:%M:%S.%f")[:-3]
                        jam_row[ev_idx_hdr] = "JAM"
                        jam_row[dn_idx_hdr] = dn
                        sheet.append_row(jam_row)
                        self.log_queue.put(f"Logged JAM event for {port_identifier}")
                        jam_event = False
                    last_send = now
                time.sleep(0.1)
        except Exception as e:
            self.log_queue.put(f"Error reading from {ser.port}: {e}")
        finally:
            try: ser.close()
            except: pass
            self.log_queue.put(f"Closed serial port {ser.port}")
            if port_identifier in self.port_threads:
                del self.port_threads[port_identifier]
            self.log_queue.put(f"Logging ended for {port_identifier}")

    def record_video(self, port_identifier):
        ci = self.port_to_camera_index.get(port_identifier)
        dn = self.port_to_device_number.get(port_identifier, 'unknown')
        if ci is None or ci not in self.camera_objects:
            self.log_queue.put(f"No camera for {port_identifier}")
            return
        cam = self.camera_objects[ci]
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        safe = re.sub(r'[<>:"/\\|?*]', '_', os.path.basename(port_identifier))
        path = os.path.join(self.experiment_folder, f"Device_{dn}")
        os.makedirs(path, exist_ok=True)
        fname = os.path.join(path, f"{safe}_device_{dn}_camera_{ts}.avi")
        fw = int(cam.get(cv2.CAP_PROP_FRAME_WIDTH))
        fh = int(cam.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if fw==0 or fh==0:
            self.log_queue.put(f"Camera {ci} no frames.")
            with self.recording_locks[port_identifier]:
                self.recording_states[port_identifier] = False
                self.last_event_times[port_identifier] = None
            return
        out = cv2.VideoWriter(fname, cv2.VideoWriter_fourcc(*'XVID'), 20.0, (fw, fh))
        try:
            while True:
                with self.recording_locks[port_identifier]:
                    let = self.last_event_times[port_identifier]
                if let is None: break
                elapsed = (datetime.datetime.now() - let).total_seconds()
                maxd = 30 if self.video_trigger.get()!="All" else 60
                if elapsed > maxd: break
                ret, frame = cam.read()
                if not ret:
                    self.log_queue.put(f"Failed read frame {ci}")
                    break
                out.write(frame)
                time.sleep(0.05)
        finally:
            out.release()
            with self.recording_locks[port_identifier]:
                self.recording_states[port_identifier] = False
                self.last_event_times[port_identifier] = None
            self.log_queue.put(f"Video saved: {fname}")

    def stop_logging(self):
        self.stop_event.set()
        self.logging_active = False
        self.log_queue.put("Stopping logging...")
        # hide indicator
        self.canvas.itemconfig(self.recording_circle, fill="red")
        self.canvas.itemconfig(self.recording_label, text="OFF", fill="red")
        # enable inputs
        self.experimenter_entry.config(state='normal')
        self.experiment_entry.config(state='normal')
        self.json_entry.config(state='normal')
        self.spreadsheet_entry.config(state='normal')
        self.browse_json_button.config(state='normal')
        self.browse_button.config(state='normal')
        self.start_button.config(state='normal')
        self.video_trigger_menu.config(state='normal')
        self.mode_menu.config(state='normal')
        self.set_mode_button.config(state='normal')
        self.identify_devices_button.config(state='normal')
        self.sync_time_button.config(state='normal')
        for wd in self.port_widgets.values():
            wd['camera_combobox'].config(state='normal')
            wd['test_cam_button'].config(state='normal')
        threading.Thread(target=self._join_threads_and_save, daemon=True).start()

    def _join_threads_and_save(self):
        for port, t in list(self.port_threads.items()):
            t.join()
            self.log_queue.put(f"Logging thread for {port} stopped.")
            del self.port_threads[port]
        self.save_all_data()
        self.data_saved = True
        for cam in self.camera_objects.values():
            cam.release()
        for ser in self.port_to_serial.values():
            if ser.is_open:
                ser.close()
        self.port_to_serial.clear()
        self.root.after(0, self._finalize_exit)

    def _finalize_exit(self):
        messagebox.showinfo("Data Saved", "All data and videos have been saved locally.")
        self.root.destroy()

    def save_all_data(self):
        if not self.save_path:
            self.log_queue.put("No save path.")
            return
        for port, rows in self.data_to_save.items():
            if not rows: continue
            safe = re.sub(r'[<>:"/\\|?*]', '_', os.path.basename(port))
            dn = self.port_to_device_number.get(port, "unknown")
            fname = os.path.join(
                self.experiment_folder,
                f"{safe}_device_{dn}_{datetime.datetime.now().strftime('%Y_%m_%d_%H_%M_%S')}.csv"
            )
            try:
                with open(fname, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(column_headers)
                    writer.writerows(rows)
                self.log_queue.put(f"Saved data for {port} -> {fname}")
            except Exception as e:
                self.log_queue.put(f"Failed save for {port}: {e}")

    def update_gui(self):
        for port, q in list(self.port_queues.items()):
            try:
                while True:
                    msg = q.get_nowait()
                    if msg == "RIGHT_POKE":
                        self.trigger_indicator(port)
                    else:
                        if port in self.port_widgets:
                            tw = self.port_widgets[port]['text_widget']
                            tw.insert(tk.END, msg + "\n")
                            tw.see(tk.END)
            except queue.Empty:
                pass
        try:
            while True:
                lm = self.log_queue.get_nowait()
                self.log_text.insert(tk.END, f"{datetime.datetime.now().strftime('%m/%d/%Y %H:%M:%S')}: {lm}\n")
                self.log_text.see(tk.END)
        except queue.Empty:
            pass

        if time.time() - self.last_device_check_time >= 5:
            self.check_device_connections()
            self.last_device_check_time = time.time()

        self.root.after(100, self.update_gui)

    def check_device_connections(self):
        current = set(self.detect_serial_ports())
        # removed
        for port in list(self.serial_ports):
            if port not in current:
                if port in self.port_widgets:
                    self.port_widgets[port]['status_label'].config(text="Not Ready", foreground="red")
                self.log_queue.put(f"Device on {port} disconnected.")
                self.serial_ports.remove(port)
                if port in self.port_threads: del self.port_threads[port]
                if port in self.identification_threads:
                    self.identification_stop_events[port].set()
                    self.identification_threads[port].join()
                    del self.identification_threads[port]
                    del self.identification_stop_events[port]
        for port in current:
            if port not in self.serial_ports:
                self.serial_ports.add(port)
                idx = len(self.port_widgets)
                self.initialize_port_widgets(port, idx)
                self.start_identification_thread(port)
                if self.logging_active and port in self.port_to_device_number:
                    self.start_logging_for_port(port)
            else:
                st = self.port_widgets[port]['status_label'].cget("text")
                if "Not Ready" in st:
                    self.port_widgets[port]['status_label'].config(text="Ready", foreground="green")
                    if self.logging_active and port in self.port_to_device_number:
                        self.start_logging_for_port(port)

    def trigger_indicator(self, port_identifier):
        if port_identifier not in self.port_widgets:
            return
        cvs = self.port_widgets[port_identifier]['indicator_canvas']
        circ = self.port_widgets[port_identifier]['indicator_circle']
        def blink(times):
            if times > 0:
                cur = cvs.itemcget(circ, 'fill')
                nxt = 'red' if cur == 'gray' else 'gray'
                cvs.itemconfig(circ, fill=nxt)
                self.root.after(250, lambda: blink(times - 1))
            else:
                cvs.itemconfig(circ, fill='gray')
        blink(6)

    def get_or_create_worksheet(self, spreadsheet, title):
        try:
            return spreadsheet.worksheet(title)
        except gspread.exceptions.WorksheetNotFound:
            ws = spreadsheet.add_worksheet(title=title, rows="1000", cols="20")
            ws.append_row(column_headers)
            return ws

    def on_closing(self):
        if not self.data_saved:
            self.stop_identification_threads()
            self.stop_event.set()
            self.logging_active = False
            for t in list(self.identification_threads.values()): t.join()
            for t in list(self.port_threads.values()): t.join()
            self.save_all_data()
            for cam in self.camera_objects.values(): cam.release()
            for ser in self.port_to_serial.values():
                if ser.is_open: ser.close()
        self.root.destroy()

    def validate_data(self, data_list):
        try:
            for hdr, val in zip(column_headers[1:], data_list):
                if hdr in ["Temp","Humidity","Battery_Voltage","Motor_Turns",
                           "Left_Poke_Count","Right_Poke_Count","Pellet_Count",
                           "Block_Pellet_Count","Retrieval_Time","InterPelletInterval","Poke_Time"]:
                    if val.strip():
                        float(val.strip())
            return True
        except:
            return False

def main():
    splash_root = tk.Tk()
    splash = SplashScreen(splash_root, duration=7000)
    splash_root.mainloop()

    camera_indices = getattr(splash, 'camera_indices', [])
    root = tk.Tk()
    app = FED3MonitorApp(root, camera_indices)
    root.mainloop()

if __name__ == "__main__":
    main()

