# qcx_ultimate_main.py
# QCX-mini / QMX / QMX+ ULTIMATE CAT CONTROL by AJ6BC + Grok
# Main window: All controls, CAT, scanning, messages, FT8 launch, etc.
# Graphs are in separate file qcx_graphs.py

import serial
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import time
import subprocess
import platform
import pyaudio
import csv
from datetime import datetime

# Import graphs module
import qcx_graphs

# Import the CW decoder window
import qcx_cw_decoder

class QCXUltimateGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("QCX-mini ULTIMATE CAT CONTROL by AJ6BC + Grok")
        self.root.geometry("740x1000")
        self.root.configure(bg="#1a1a1a")

        # Main scrollable canvas
        main_canvas = tk.Canvas(root, bg="#1a1a1a", highlightthickness=0)
        main_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        v_scrollbar = ttk.Scrollbar(root, orient="vertical", command=main_canvas.yview)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        main_canvas.configure(yscrollcommand=v_scrollbar.set)

        self.main_frame = tk.Frame(main_canvas, bg="#1a1a1a")
        main_canvas.create_window((0, 0), window=self.main_frame, anchor="nw")

        self.main_frame.bind("<Configure>", lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all")))
        main_canvas.bind("<Configure>", lambda e: main_canvas.itemconfig(main_canvas.find_withtag("all"), width=e.width))

        def _on_mousewheel(event):
            main_canvas.yview_scroll(-1*(event.delta//120), "units")
        main_canvas.bind_all("<MouseWheel>", _on_mousewheel)
        main_canvas.bind_all("<Button-4>", lambda e: main_canvas.yview_scroll(-1, "units"))
        main_canvas.bind_all("<Button-5>", lambda e: main_canvas.yview_scroll(1, "units"))

        frame = self.main_frame

        self.ser = None
        self.tx_timer = None
        self.debug_window = None
        self.debug_active = False
        self.poll_interval = 1000
        self.scanning = False
        self.scan_thread = None
        self.activity_detected = False
        self.waterfall_data = []
        self.max_waterfall_rows = 50

        self.scan_center = 7.030
        self.scan_steps = 0
        self.scan_step_khz = 5

        self.continuous_waterfall = False
        self.continuous_thread = None

        self.device_var = tk.StringVar(value="QCX")
        self.variant_var = tk.StringVar(value="Low")

        # QSL logging
        self.qsl_log_file = "qsl_log.csv"
        self.last_decoded_call = ""  # Auto-fill from decoder

        # Disclaimer
        disclaimer = tk.Label(frame, text="This is an experimental CAT interface; use at your own risk. I am 100% indemnified from any damages whatsoever.",
                              fg="red", bg="#1a1a1a", font=("Arial", 10, "italic"))
        disclaimer.pack(pady=5)

        # Connect + Debug + Polling
        top_frame = tk.Frame(frame, bg="#1a1a1a")
        top_frame.pack(pady=10)
        tk.Label(top_frame, text="Device:", fg="cyan", bg="#1a1a1a", font=("Arial", 12)).pack(side=tk.LEFT, padx=5)
        self.device_combo = ttk.Combobox(top_frame, textvariable=self.device_var, values=["QCX", "QMX", "QMX+"], width=6)
        self.device_combo.pack(side=tk.LEFT, padx=5)
        self.device_combo.bind("<<ComboboxSelected>>", self.on_device_change)

        tk.Label(top_frame, text="Variant:", fg="cyan", bg="#1a1a1a", font=("Arial", 12)).pack(side=tk.LEFT, padx=5)
        self.variant_combo = ttk.Combobox(top_frame, textvariable=self.variant_var, values=["Low", "Mid", "High"], width=5)
        self.variant_combo.pack(side=tk.LEFT, padx=5)

        tk.Label(top_frame, text="COM Port:", fg="cyan", bg="#1a1a1a", font=("Arial", 12)).pack(side=tk.LEFT)
        self.port_var = tk.StringVar(value="COM3")
        tk.Entry(top_frame, textvariable=self.port_var, width=8).pack(side=tk.LEFT, padx=5)
        tk.Button(top_frame, text="CONNECT", command=self.connect, bg="#00ff00", fg="black", font=("Arial", 12, "bold")).pack(side=tk.LEFT, padx=5)
        self.status_label = tk.Label(top_frame, text="Not connected", fg="red", bg="#1a1a1a", font=("Arial", 12, "bold"))
        self.status_label.pack(side=tk.LEFT, padx=20)

        self.debug_var = tk.BooleanVar()
        tk.Checkbutton(top_frame, text="Debug Console", variable=self.debug_var, command=self.toggle_debug,
                       bg="#1a1a1a", fg="yellow", selectcolor="#333333").pack(side=tk.LEFT, padx=20)

        tk.Label(top_frame, text="Polling:", fg="cyan", bg="#1a1a1a", font=("Arial", 12)).pack(side=tk.LEFT, padx=10)
        self.poll_label = tk.Label(top_frame, text="1.0 s", fg="white", bg="#1a1a1a", font=("Arial", 12))
        self.poll_label.pack(side=tk.LEFT)
        self.poll_var = tk.DoubleVar(value=1.0)
        tk.Spinbox(top_frame, from_=0.1, to=10.0, increment=0.1, textvariable=self.poll_var, width=5, command=self.update_poll_interval).pack(side=tk.LEFT, padx=5)

        # VFO Display
        vfo_frame = tk.Frame(frame, bg="#1a1a1a")
        vfo_frame.pack(pady=10)
        self.vfoa_label = tk.Label(vfo_frame, text="VFO A: ?.?????? MHz", fg="#00ff00", bg="#1a1a1a", font=("Arial", 28, "bold"))
        self.vfoa_label.pack()
        self.vfob_label = tk.Label(vfo_frame, text="VFO B: ?.?????? MHz", fg="#ff8800", bg="#1a1a1a", font=("Arial", 22, "bold"))
        self.vfob_label.pack()
        self.mode_label = tk.Label(vfo_frame, text="Mode: ?", fg="cyan", bg="#1a1a1a", font=("Arial", 24, "bold"))
        self.mode_label.pack(pady=8)
        self.rit_label = tk.Label(vfo_frame, text="RIT: 0 Hz", fg="yellow", bg="#1a1a1a", font=("Arial", 16))
        self.rit_label.pack()
        self.s_meter_label = tk.Label(vfo_frame, text="S-Meter: -", fg="#00ffff", bg="#1a1a1a", font=("Arial", 18, "bold"))
        self.s_meter_label.pack()
        self.practice_label = tk.Label(vfo_frame, text="Practice Mode: Set in menu 4.7", fg="magenta", bg="#1a1a1a", font=("Arial", 16))
        self.practice_label.pack()

        # Set Frequency + + / - buttons
        setf_frame = tk.Frame(frame, bg="#1a1a1a")
        setf_frame.pack(pady=5)
        tk.Label(setf_frame, text="Set Freq (MHz):", fg="white", bg="#1a1a1a").grid(row=0, column=0)
        self.freq_entry = tk.Entry(setf_frame, width=12, font=("Arial", 12))
        self.freq_entry.grid(row=0, column=1, padx=5)
        self.vfo_select_var = tk.StringVar(value="A")
        ttk.Combobox(setf_frame, textvariable=self.vfo_select_var, values=["A", "B"], width=4).grid(row=0, column=2, padx=5)
        tk.Button(setf_frame, text="TUNE", command=self.set_freq, bg="#0088ff", fg="white").grid(row=0, column=3, padx=5)

        bump_frame = tk.Frame(setf_frame, bg="#1a1a1a")
        bump_frame.grid(row=1, column=0, columnspan=4, pady=5)
        tk.Button(bump_frame, text="-100 Hz", command=lambda: self.vfo_bump(-100), bg="#ff8800", fg="black", width=10).pack(side=tk.LEFT, padx=5)
        tk.Button(bump_frame, text="-10 Hz", command=lambda: self.vfo_bump(-10), bg="#ff8800", fg="black", width=10).pack(side=tk.LEFT, padx=5)
        tk.Button(bump_frame, text="+10 Hz", command=lambda: self.vfo_bump(10), bg="#00ff88", fg="black", width=10).pack(side=tk.LEFT, padx=5)
        tk.Button(bump_frame, text="+100 Hz", command=lambda: self.vfo_bump(100), bg="#00ff88", fg="black", width=10).pack(side=tk.LEFT, padx=5)

        self.freq_entry.bind("<MouseWheel>", self.wheel_tune)
        self.freq_entry.bind("<Button-4>", self.wheel_tune)
        self.freq_entry.bind("<Button-5>", self.wheel_tune)

        # Band Buttons + 40m FT8
        band_frame = tk.LabelFrame(frame, text="BAND", fg="cyan", bg="#1a1a1a")
        band_frame.pack(pady=10)
        bands = ["160m","80m","60m","40m","30m","20m","17m","15m","12m","11m","10m","6m"]
        freqs = [1.84,3.58,5.357,7.03,10.116,14.06,18.1,21.06,24.92,27.0,28.06,50.1]
        self.band_freqs = dict(zip(bands, freqs))

        tk.Button(band_frame, text="40m FT8", command=lambda: self.band_change(7.074), width=8, bg="#00aaaa", fg="white", font=("Arial", 10, "bold")).grid(row=0, column=0, padx=5, pady=5, columnspan=2)

        self.update_bands()
        for i, (band, freq) in enumerate(zip(bands, freqs)):
            col = (i % 6) + 2 if i < 6 else i % 6
            row = 0 if i < 6 else 1
            tk.Button(band_frame, text=band, command=lambda f=freq: self.band_change(f), width=6, bg="#444444", fg="white").grid(row=row, column=col, padx=5, pady=5)

        # RIT
        rit_frame = tk.LabelFrame(frame, text="RIT", fg="cyan", bg="#1a1a1a")
        rit_frame.pack(pady=10)
        tk.Button(rit_frame, text="-100 Hz", command=lambda: self.rit_adjust(-100), bg="#ff8800", fg="black").pack(side=tk.LEFT, padx=5)
        tk.Button(rit_frame, text="0", command=self.rit_zero, bg="#888888", fg="white").pack(side=tk.LEFT, padx=5)
        tk.Button(rit_frame, text="+100 Hz", command=lambda: self.rit_adjust(100), bg="#ff8800", fg="black").pack(side=tk.LEFT, padx=5)

        # Keyer Speed
        speed_frame = tk.LabelFrame(frame, text="KEYER SPEED", fg="cyan", bg="#1a1a1a")
        speed_frame.pack(pady=10)
        self.speed_var = tk.IntVar(value=20)
        tk.Scale(speed_frame, from_=5, to=40, orient=tk.HORIZONTAL, variable=self.speed_var, length=300, bg="#333333", fg="white").pack()
        tk.Button(speed_frame, text="SET", command=self.set_speed, bg="#ffaa00", fg="black").pack(pady=5)

        # Preset Messages
        msg_frame = tk.LabelFrame(frame, text="PRESET CW MESSAGES", fg="cyan", bg="#1a1a1a")
        msg_frame.pack(pady=10)
        presets = [
            ("CQ", "CQ CQ CQ DE AJ6BC AJ6BC K"),
            ("DE", "DE AJ6BC"),
            ("599", "5NN CA"),
            ("TU", "TU 73 DE AJ6BC"),
            ("QTH", "QTH CALIFORNIA"),
            ("NAME", "NAME JOHN")
        ]
        for text, msg in presets:
            tk.Button(msg_frame, text=text, command=lambda m=msg: self.send_message(m), width=8, bg="#ff00ff", fg="white").pack(side=tk.LEFT, padx=5)

        # Custom Message
        cust_frame = tk.Frame(frame, bg="#1a1a1a")
        cust_frame.pack(pady=10)
        self.msg_entry = tk.Entry(cust_frame, width=50, font=("Arial", 14))
        self.msg_entry.pack()
        tk.Button(cust_frame, text="SEND CUSTOM MESSAGE", command=self.send_custom, bg="#ff00ff", fg="white", font=("Arial", 12)).pack(pady=5)

        # VFO Controls
        vfo_control_frame = tk.Frame(frame, bg="#1a1a1a")
        vfo_control_frame.pack(pady=10)
        tk.Button(vfo_control_frame, text="VFO A", command=lambda: self.set_vfo("A"), bg="#00aa00", fg="white", font=("Arial", 12, "bold"), width=8, height=1).pack(side=tk.LEFT, padx=10)
        tk.Button(vfo_control_frame, text="VFO B", command=lambda: self.set_vfo("B"), bg="#aa5500", fg="white", font=("Arial", 12, "bold"), width=8, height=1).pack(side=tk.LEFT, padx=10)
        tk.Button(vfo_control_frame, text="SPLIT", command=self.toggle_split, bg="#ff8800", fg="black", font=("Arial", 12, "bold"), width=8, height=1).pack(side=tk.LEFT, padx=10)
        tk.Button(vfo_control_frame, text="PRACTICE", command=self.toggle_practice, bg="#00ffff", fg="black", font=("Arial", 12, "bold"), width=10, height=1).pack(side=tk.LEFT, padx=10)

        # TX Control
        tx_frame = tk.Frame(frame, bg="#1a1a1a")
        tx_frame.pack(pady=20)
        tk.Button(tx_frame, text="TX ON", command=self.tx_on, bg="#ff0000", fg="white", font=("Arial", 16, "bold"), width=10).pack(side=tk.LEFT, padx=30)
        tk.Button(tx_frame, text="TX OFF", command=self.tx_off, bg="#888888", fg="white", font=("Arial", 16, "bold"), width=10).pack(side=tk.LEFT, padx=30)
        tk.Button(tx_frame, text="STOP TX NOW", command=self.tx_off, bg="#ffff00", fg="black", font=("Arial", 16, "bold"), width=14).pack(side=tk.LEFT, padx=30)

        # CW Decode Buffer
        tb_frame = tk.LabelFrame(frame, text="CW DECODE BUFFER (TB)", fg="cyan", bg="#1a1a1a")
        tb_frame.pack(pady=10, fill=tk.BOTH, expand=True, padx=20)
        self.tb_text = scrolledtext.ScrolledText(tb_frame, height=8, font=("Courier", 12), bg="#000000", fg="#00ff00")
        self.tb_text.pack(fill=tk.BOTH, expand=True)

        # CW Scan
        scan_frame = tk.LabelFrame(frame, text="CW SCAN (Listen for activity)", fg="cyan", bg="#1a1a1a")
        scan_frame.pack(pady=15, fill=tk.X, padx=20)
        tk.Label(scan_frame, text="Band:", fg="white", bg="#1a1a1a").pack(side=tk.LEFT, padx=10)
        self.scan_band_var = tk.StringVar(value="40m")
        ttk.Combobox(scan_frame, textvariable=self.scan_band_var, values=bands, width=6).pack(side=tk.LEFT, padx=5)
        tk.Label(scan_frame, text="Delay (s):", fg="white", bg="#1a1a1a").pack(side=tk.LEFT, padx=10)
        self.scan_delay_var = tk.DoubleVar(value=2.0)
        tk.Spinbox(scan_frame, from_=0.1, to=10.0, increment=0.1, textvariable=self.scan_delay_var, width=5).pack(side=tk.LEFT, padx=5)
        tk.Label(scan_frame, text="Width:", fg="white", bg="#1a1a1a").pack(side=tk.LEFT, padx=10)
        self.scan_width_var = tk.StringVar(value="±50 kHz")
        ttk.Combobox(scan_frame, textvariable=self.scan_width_var, values=["±10 kHz", "±50 kHz", "±100 kHz", "Full Band"], width=10).pack(side=tk.LEFT, padx=5)
        tk.Label(scan_frame, text="Step (kHz):", fg="white", bg="#1a1a1a").pack(side=tk.LEFT, padx=10)
        self.scan_step_var = tk.StringVar(value="5")
        ttk.Combobox(scan_frame, textvariable=self.scan_step_var, values=["1", "2", "5", "10"], width=4).pack(side=tk.LEFT, padx=5)
        tk.Label(scan_frame, text="Activity S>:", fg="white", bg="#1a1a1a").pack(side=tk.LEFT, padx=10)
        self.activity_threshold_var = tk.IntVar(value=3)
        tk.Spinbox(scan_frame, from_=0, to=9, textvariable=self.activity_threshold_var, width=3).pack(side=tk.LEFT, padx=5)
        self.scan_button = tk.Button(scan_frame, text="START SCAN", command=self.toggle_scan, bg="#00ff88", fg="black", font=("Arial", 12, "bold"))
        self.scan_button.pack(side=tk.LEFT, padx=20)
        self.scan_status_label = tk.Label(scan_frame, text="Scan stopped", fg="gray", bg="#1a1a1a", font=("Arial", 12))
        self.scan_status_label.pack(side=tk.LEFT)

        # Continuous Waterfall Button
        self.cont_waterfall_btn = tk.Button(frame, text="CONTINUOUS WATERFALL", command=self.toggle_continuous_waterfall,
                                            bg="#00aa00", fg="white", font=("Arial", 14, "bold"), height=2)
        self.cont_waterfall_btn.pack(pady=10, fill=tk.X, padx=50)

        # Open CW Decoder Button
        cw_decoder_btn = tk.Button(frame, text="OPEN CW DECODER", command=self.open_cw_decoder_window,
                                   bg="#ffaa00", fg="black", font=("Arial", 14, "bold"), height=2)
        cw_decoder_btn.pack(pady=10, fill=tk.X, padx=50)

        # QSL Logging Button
        qsl_btn = tk.Button(frame, text="LOG QSL", command=self.open_qsl_log_window,
                            bg="#00aaff", fg="white", font=("Arial", 14, "bold"), height=2)
        qsl_btn.pack(pady=10, fill=tk.X, padx=50)

        # Open Graphs Button
        graphs_btn = tk.Button(frame, text="OPEN GRAPHS (Waterfall + Audio Spectrum)", command=self.open_graphs_window,
                               bg="#00ff00", fg="black", font=("Arial", 14, "bold"), height=2)
        graphs_btn.pack(pady=10, fill=tk.X, padx=50)

        # FT8 Section
        ft8_frame = tk.LabelFrame(frame, text="FT8 / DIGITAL MODES (WSJT-X)", fg="cyan", bg="#1a1a1a")
        ft8_frame.pack(pady=15, fill=tk.X, padx=20)
        tk.Label(ft8_frame, text="QCX/QMX does not decode FT8 internally.\nUse WSJT-X for full FT8/FT4/WSPR/etc operation.\nConnect USB audio + CAT (Kenwood TS-480 in WSJT-X).", 
                 fg="yellow", bg="#1a1a1a", justify=tk.LEFT, font=("Arial", 11)).pack(pady=5)
        tk.Button(ft8_frame, text="LAUNCH WSJT-X", command=self.launch_wsjtx, bg="#00aaff", fg="white", font=("Arial", 14, "bold")).pack(pady=10)

        self.poll_status()

    def open_qsl_log_window(self):
        log_win = tk.Toplevel(self.root)
        log_win.title("QSL Log Entry")
        log_win.geometry("500x400")
        log_win.configure(bg="#1a1a1a")

        # Current values from VFO and recent decode
        current_freq = self.freq_entry.get() or "7.000"
        current_call = self.last_decoded_call or ""

        tk.Label(log_win, text="Callsign:", fg="cyan", bg="#1a1a1a", font=("Arial", 12)).pack(pady=5)
        call_entry = tk.Entry(log_win, width=20, font=("Arial", 12))
        call_entry.insert(0, current_call)
        call_entry.pack()

        tk.Label(log_win, text="Frequency (MHz):", fg="cyan", bg="#1a1a1a", font=("Arial", 12)).pack(pady=5)
        freq_entry = tk.Entry(log_win, width=20, font=("Arial", 12))
        freq_entry.insert(0, current_freq)
        freq_entry.pack()

        tk.Label(log_win, text="Mode:", fg="cyan", bg="#1a1a1a", font=("Arial", 12)).pack(pady=5)
        mode_entry = tk.Entry(log_win, width=20, font=("Arial", 12))
        mode_entry.insert(0, "CW")
        mode_entry.pack()

        tk.Label(log_win, text="RST Sent:", fg="cyan", bg="#1a1a1a", font=("Arial", 12)).pack(pady=5)
        rst_sent = tk.Entry(log_win, width=20, font=("Arial", 12))
        rst_sent.insert(0, "599")
        rst_sent.pack()

        tk.Label(log_win, text="RST Received:", fg="cyan", bg="#1a1a1a", font=("Arial", 12)).pack(pady=5)
        rst_rcvd = tk.Entry(log_win, width=20, font=("Arial", 12))
        rst_rcvd.insert(0, "599")
        rst_rcvd.pack()

        def save_log():
            entry = {
                "DateTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Callsign": call_entry.get(),
                "Frequency": freq_entry.get(),
                "Mode": mode_entry.get(),
                "RST Sent": rst_sent.get(),
                "RST Received": rst_rcvd.get()
            }
            with open(self.qsl_log_file, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=entry.keys())
                if f.tell() == 0:
                    writer.writeheader()
                writer.writerow(entry)
            messagebox.showinfo("QSL Logged", "Entry saved to qsl_log.csv")
            log_win.destroy()

        tk.Button(log_win, text="Save QSL Log", command=save_log, bg="#00ff00", fg="black", font=("Arial", 12, "bold")).pack(pady=20)

        # View recent logs
        view_btn = tk.Button(log_win, text="View Last 10 Logs", command=self.view_qsl_logs, bg="#0088ff", fg="white")
        view_btn.pack(pady=10)

    def view_qsl_logs(self):
        try:
            with open(self.qsl_log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()[-10:]  # last 10
            log_text = "".join(lines)
            log_win = tk.Toplevel(self.root)
            log_win.title("Recent QSL Logs")
            log_win.geometry("600x400")
            text = scrolledtext.ScrolledText(log_win, font=("Courier", 12))
            text.insert(tk.END, log_text)
            text.pack(fill=tk.BOTH, expand=True)
        except Exception as e:
            messagebox.showerror("Error", f"No log file or error reading: {e}")

    def on_device_change(self, event=None):
        device = self.device_var.get()
        if device == "QMX+":
            self.variant_combo.config(state="disabled")
            self.supported_bands = list(self.band_freqs.keys())
        else:
            self.variant_combo.config(state="normal")
            self.update_bands()

    def open_graphs_window(self):
        qcx_graphs.open_graphs(self)

    def open_cw_decoder_window(self):
        qcx_cw_decoder.open_cw_decoder(self)

    def connect(self):
        if self.ser:
            self.ser.close()
        try:
            baud = 38400
            self.ser = serial.Serial(self.port_var.get(), baud, timeout=1)
            self.status_label.config(text="CONNECTED", fg="#00ff00")
            self.send_cmd('QU1')
            self.send_cmd('TB1')
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def send_cmd(self, cmd):
        if not self.ser: return "?"
        try:
            self.ser.write((cmd + ';').encode())
            resp = self.ser.read_until(b';').decode().strip()
            self.debug_print(f"> {cmd};   ← {resp}")
            return resp
        except Exception as e:
            self.debug_print(f"[ERROR] {e}")
            return "?"

    def update_poll_interval(self):
        interval = self.poll_var.get()
        self.poll_interval = int(interval * 1000)
        self.poll_label.config(text=f"{interval:.1f} s")
        if hasattr(self, 'poll_id'):
            self.root.after_cancel(self.poll_id)
        self.poll_status()

    def poll_status(self):
        if self.ser:
            fa_resp = self.send_cmd('FA')
            if fa_resp.startswith('FA'):
                vfoa = int(fa_resp[2:13]) / 1e6
                self.vfoa_label.config(text=f"VFO A: {vfoa:.6f} MHz")

            fb_resp = self.send_cmd('FB')
            if fb_resp.startswith('FB'):
                vfob = int(fb_resp[2:13]) / 1e6
                self.vfob_label.config(text=f"VFO B: {vfob:.6f} MHz")

            if_resp = self.send_cmd('IF')
            if if_resp.startswith('IF') and len(if_resp) >= 32:
                rit = int(if_resp[18:23]) if if_resp[18:23].strip() else 0
                self.rit_label.config(text=f"RIT: {rit:+} Hz")

            s_meter = if_resp[29] if len(if_resp) > 29 and if_resp[29].isdigit() else "0"
            self.s_meter_label.config(text=f"S-Meter: S{s_meter}")

            ft_resp = self.send_cmd('FT')
            if ft_resp == 'FT0':
                self.mode_label.config(text="Mode: VFO A", fg="#00ff00")
            elif ft_resp == 'FT1':
                self.mode_label.config(text="Mode: VFO B", fg="#ff8800")
            elif ft_resp == 'FT2':
                self.mode_label.config(text="Mode: SPLIT", fg="#ff0000")

            tb_resp = self.send_cmd('TB')
            if tb_resp.startswith('TB') and len(tb_resp) > 4:
                decoded = tb_resp[2:].strip()
                if decoded and decoded != "000" and not decoded.isdigit():
                    self.tb_text.insert(tk.END, decoded + " ")
                    self.tb_text.see(tk.END)
                    if self.scanning:
                        self.activity_detected = True

        self.poll_id = self.root.after(self.poll_interval, self.poll_status)

    def toggle_scan(self):
        if self.scanning:
            self.scanning = False
            self.scan_button.config(text="START SCAN", bg="#00ff88")
            self.scan_status_label.config(text="Scan stopped", fg="gray")
        else:
            if not self.ser:
                messagebox.showwarning("Not connected", "Connect to radio first!")
                return
            self.scanning = True
            self.waterfall_data = []
            self.scan_button.config(text="STOP SCAN", bg="#ff0000")
            self.scan_status_label.config(text="Scanning...", fg="#00ff00")
            self.scan_thread = threading.Thread(target=self.scan_loop, daemon=True)
            self.scan_thread.start()

    def scan_loop(self):
        band = self.scan_band_var.get()
        center_freq = self.band_freqs.get(band, 7.030)
        width_str = self.scan_width_var.get()

        if width_str == "Full Band" and band == "40m":
            center_freq = 7.150
            width_khz = 150
        elif width_str == "Full Band":
            width_khz = 50
        else:
            width_khz = int(width_str.replace("±", "").replace(" kHz", ""))

        step_khz = int(self.scan_step_var.get())
        steps = int((width_khz * 2) / step_khz) + 1
        delay = self.scan_delay_var.get()
        threshold = self.activity_threshold_var.get()

        self.scan_center = center_freq
        self.scan_steps = steps
        self.scan_step_khz = step_khz

        while self.scanning:
            scan_s_values = []
            for i in range(steps):
                if not self.scanning: break
                self.activity_detected = False
                offset = (i - steps // 2) * step_khz * 1000
                freq_hz = int(center_freq * 1e6 + offset)
                cmd = f'FA{str(freq_hz).zfill(11)}'
                self.send_cmd(cmd)
                self.root.after(0, lambda f=freq_hz/1e6: self.freq_entry.delete(0, tk.END) or self.freq_entry.insert(0, f"{f:.6f}"))
                time.sleep(delay)
                s_text = self.s_meter_label.cget("text")
                if "S-Meter: S" in s_text:
                    s_str = s_text.split("S-Meter: S")[1].strip()
                    s_val = int(s_str) if s_str.isdigit() else 0
                else:
                    s_val = 0
                scan_s_values.append(s_val)
                if s_val > threshold or self.activity_detected:
                    self.scan_status_label.config(text="Activity detected! Pausing...", fg="#ff8800")
                    time.sleep(10)
                    self.scan_status_label.config(text="Scanning...", fg="#00ff00")
            if scan_s_values:
                self.waterfall_data.append(scan_s_values)
                if len(self.waterfall_data) > self.max_waterfall_rows:
                    self.waterfall_data.pop(0)

    def toggle_continuous_waterfall(self):
        if self.continuous_waterfall:
            self.continuous_waterfall = False
            self.cont_waterfall_btn.config(text="CONTINUOUS WATERFALL", bg="#00aa00")
        else:
            if not self.ser:
                messagebox.showwarning("Not connected", "Connect to radio first!")
                return
            self.continuous_waterfall = True
            self.cont_waterfall_btn.config(text="STOP CONTINUOUS", bg="#aa0000")
            self.waterfall_data = []
            self.continuous_thread = threading.Thread(target=self.continuous_waterfall_loop, daemon=True)
            self.continuous_thread.start()

    def continuous_waterfall_loop(self):
        while self.continuous_waterfall:
            if not self.ser:
                break
            if_resp = self.send_cmd('IF')
            if if_resp.startswith('IF') and len(if_resp) >= 32:
                s_meter = if_resp[29] if if_resp[29].isdigit() else "0"
                s_val = int(s_meter)
                self.waterfall_data.append([s_val])
                if len(self.waterfall_data) > self.max_waterfall_rows:
                    self.waterfall_data.pop(0)
            time.sleep(0.5)

    def vfo_bump(self, hz):
        if not self.ser:
            messagebox.showwarning("Not connected", "Connect to radio first!")
            return
        vfo = self.vfo_select_var.get()
        if hz > 0:
            cmd = f'RU{hz:04d}'
        else:
            cmd = f'RD{abs(hz):04d}'
        self.send_cmd(cmd)
        self.root.after(100, self.poll_status)

    def set_vfo(self, vfo):
        if vfo == "A":
            self.send_cmd('FT0')
            self.mode_label.config(text="Mode: VFO A", fg="#00ff00")
        elif vfo == "B":
            self.send_cmd('FT1')
            self.mode_label.config(text="Mode: VFO B", fg="#ff8800")
        self.root.after(100, self.poll_status)

    def toggle_split(self):
        current = self.send_cmd('FT')
        if current == 'FT2':
            self.send_cmd('FT0')
            self.mode_label.config(text="Mode: VFO A", fg="#00ff00")
        else:
            self.send_cmd('FT2')
            self.mode_label.config(text="Mode: SPLIT", fg="#ff0000")
        self.root.after(100, self.poll_status)

    def toggle_practice(self):
        messagebox.showinfo("Practice Mode", "Practice Mode is set manually in menu 4.7\n(No CAT control available)")

    def band_change(self, freq):
        self.freq_entry.delete(0, tk.END)
        self.freq_entry.insert(0, str(freq))
        self.set_freq()

    def wheel_tune(self, event):
        try:
            current = float(self.freq_entry.get())
        except:
            return
        shift = event.state & 0x1
        ctrl = event.state & 0x4
        step = -1 if (event.num == 5 or event.delta < 0) else 1
        delta = step * (1000 if ctrl else 100 if shift else 10)
        new_freq = current + delta / 1e6
        self.freq_entry.delete(0, tk.END)
        self.freq_entry.insert(0, f"{new_freq:.6f}")
        self.set_freq()

    def set_freq(self):
        try:
            f = float(self.freq_entry.get())
            freq_hz = int(f * 1e6)
            vfo = self.vfo_select_var.get()
            cmd = f'FA{str(freq_hz).zfill(11)}' if vfo == "A" else f'FB{str(freq_hz).zfill(11)}'
            self.send_cmd(cmd)
        except: pass

    def rit_adjust(self, step):
        self.send_cmd(f'RD{abs(step):04d}' if step < 0 else f'RU{step:04d}')

    def rit_zero(self):
        self.send_cmd('RU0')

    def set_speed(self):
        wpm = self.speed_var.get()
        self.send_cmd(f'KS{int(wpm):02d}')

    def send_message(self, msg):
        threading.Thread(target=self._send, args=(msg,), daemon=True).start()

    def send_custom(self):
        msg = self.msg_entry.get()
        if msg:
            threading.Thread(target=self._send, args=(msg,), daemon=True).start()

    def _send(self, msg):
        self.send_cmd(f'KY {msg}')

    def tx_on(self):
        self.send_cmd('TQ1')
        messagebox.showwarning("TX ACTIVE", "Transmitter ON — watch your power!")
        self.tx_timer = self.root.after(60000, self._auto_tx_off)

    def tx_off(self):
        self.send_cmd('TQ0')
        if self.tx_timer:
            self.root.after_cancel(self.tx_timer)
            self.tx_timer = None

    def _auto_tx_off(self):
        self.tx_off()
        messagebox.showwarning("AUTO TX OFF", "TX turned off after 1 minute for safety!")

    def toggle_debug(self):
        if self.debug_var.get():
            if not self.debug_window:
                self.debug_window = tk.Toplevel(self.root)
                self.debug_window.title("Debug Console")
                self.debug_window.geometry("800x400")
                self.debug_text = scrolledtext.ScrolledText(self.debug_window, font=("Courier", 10), bg="#000000", fg="#00ff00")
                self.debug_text.pack(fill=tk.BOTH, expand=True)
            self.debug_active = True
        else:
            if self.debug_window:
                self.debug_window.destroy()
                self.debug_window = None
            self.debug_active = False

    def debug_print(self, text):
        if self.debug_active and self.debug_window:
            self.debug_text.insert(tk.END, text + "\n")
            self.debug_text.see(tk.END)

    def update_bands(self):
        device = self.device_var.get()
        if device == "QMX+":
            self.supported_bands = list(self.band_freqs.keys())
        elif device == "QMX":
            variant = self.variant_var.get()
            if variant == "Low":
                self.supported_bands = ["80m", "60m", "40m", "30m", "20m"]
            elif variant == "Mid":
                self.supported_bands = ["60m", "40m", "30m", "20m", "17m", "15m"]
            elif variant == "High":
                self.supported_bands = ["20m", "17m", "15m", "12m", "11m", "10m"]
        else:
            self.supported_bands = list(self.band_freqs.keys())

    def launch_wsjtx(self):
        try:
            if platform.system() == "Windows":
                subprocess.Popen(["wsjtx"])
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", "-a", "WSJT-X"])
            else:
                subprocess.Popen(["wsjtx"])
        except Exception as e:
            messagebox.showerror("Launch Error", f"Could not launch WSJT-X: {e}\nInstall WSJT-X and ensure it's in PATH.")

if __name__ == "__main__":
    root = tk.Tk()
    app = QCXUltimateGUI(root)
    root.mainloop()