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

# Import graphs module
import qcx_graphs

# Import the CW decoder window
import qcx_cw_decoder

class QCXUltimateGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("QCX-mini ULTIMATE CAT CONTROL by AJ6BC + Grok")
        self.root.geometry("740x900")
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
        self.status_label = tk.Label(top_frame, text="Not connected", fg="red", bg="#1a1a1a", font=("Arial", 12))
        self.status_label.pack(side=tk.LEFT, padx=5)

        self.debug_var = tk.BooleanVar(value=False)
        tk.Checkbutton(top_frame, text="Debug", variable=self.debug_var, command=self.toggle_debug, fg="white", bg="#1a1a1a").pack(side=tk.LEFT, padx=5)

        # Polling interval
        tk.Label(top_frame, text="Poll (ms):", fg="cyan", bg="#1a1a1a", font=("Arial", 12)).pack(side=tk.LEFT, padx=5)
        self.poll_entry = tk.Entry(top_frame, width=6)
        self.poll_entry.pack(side=tk.LEFT, padx=5)
        self.poll_entry.insert(0, str(self.poll_interval))
        tk.Button(top_frame, text="Set Poll", command=self.set_poll, bg="#00aaff", fg="white", font=("Arial", 12)).pack(side=tk.LEFT, padx=5)

        # Frequency control
        freq_frame = tk.Frame(frame, bg="#1a1a1a")
        freq_frame.pack(pady=10)
        tk.Label(freq_frame, text="Frequency (MHz):", fg="cyan", bg="#1a1a1a", font=("Arial", 12)).pack(side=tk.LEFT, padx=5)
        self.freq_entry = tk.Entry(freq_frame, width=12)
        self.freq_entry.pack(side=tk.LEFT, padx=5)
        self.freq_entry.insert(0, "7.030000")
        tk.Button(freq_frame, text="Set Freq", command=self.set_freq, bg="#00aaff", fg="white", font=("Arial", 12)).pack(side=tk.LEFT, padx=5)

        # VFO selection
        self.vfo_select_var = tk.StringVar(value="A")
        tk.Label(freq_frame, text="VFO:", fg="cyan", bg="#1a1a1a", font=("Arial", 12)).pack(side=tk.LEFT, padx=5)
        ttk.Combobox(freq_frame, textvariable=self.vfo_select_var, values=["A", "B"], width=5).pack(side=tk.LEFT, padx=5)

        # RIT controls
        rit_frame = tk.Frame(frame, bg="#1a1a1a")
        rit_frame.pack(pady=10)
        tk.Label(rit_frame, text="RIT:", fg="cyan", bg="#1a1a1a", font=("Arial", 12)).pack(side=tk.LEFT, padx=5)
        tk.Button(rit_frame, text="-500Hz", command=lambda: self.rit_adjust(-500), bg="#ff4444", fg="white", font=("Arial", 12)).pack(side=tk.LEFT, padx=5)
        tk.Button(rit_frame, text="-100Hz", command=lambda: self.rit_adjust(-100), bg="#ff4444", fg="white", font=("Arial", 12)).pack(side=tk.LEFT, padx=5)
        tk.Button(rit_frame, text="0Hz", command=self.rit_zero, bg="#ffaa00", fg="black", font=("Arial", 12)).pack(side=tk.LEFT, padx=5)
        tk.Button(rit_frame, text="+100Hz", command=lambda: self.rit_adjust(100), bg="#00ff88", fg="black", font=("Arial", 12)).pack(side=tk.LEFT, padx=5)
        tk.Button(rit_frame, text="+500Hz", command=lambda: self.rit_adjust(500), bg="#00ff88", fg="black", font=("Arial", 12)).pack(side=tk.LEFT, padx=5)

        # Speed control
        speed_frame = tk.Frame(frame, bg="#1a1a1a")
        speed_frame.pack(pady=10)
        tk.Label(speed_frame, text="Speed (WPM):", fg="cyan", bg="#1a1a1a", font=("Arial", 12)).pack(side=tk.LEFT, padx=5)
        self.speed_var = tk.IntVar(value=15)
        tk.Scale(speed_frame, from_=5, to=60, orient=tk.HORIZONTAL, variable=self.speed_var, length=200).pack(side=tk.LEFT, padx=5)
        tk.Button(speed_frame, text="Set Speed", command=self.set_speed, bg="#00aaff", fg="white", font=("Arial", 12)).pack(side=tk.LEFT, padx=5)

        # Messages
        msg_frame = tk.Frame(frame, bg="#1a1a1a")
        msg_frame.pack(pady=10)
        tk.Label(msg_frame, text="Messages:", fg="cyan", bg="#1a1a1a", font=("Arial", 12)).pack(side=tk.LEFT, padx=5)
        tk.Button(msg_frame, text="CQ", command=lambda: self.send_message("CQ CQ DE AJ6BC K"), bg="#00aaff", fg="white", font=("Arial", 12)).pack(side=tk.LEFT, padx=5)
        tk.Button(msg_frame, text="73", command=lambda: self.send_message("73 DE AJ6BC SK"), bg="#00aaff", fg="white", font=("Arial", 12)).pack(side=tk.LEFT, padx=5)
        tk.Button(msg_frame, text="RST 599", command=lambda: self.send_message("RST 599 599"), bg="#00aaff", fg="white", font=("Arial", 12)).pack(side=tk.LEFT, padx=5)
        self.msg_entry = tk.Entry(msg_frame, width=20)
        self.msg_entry.pack(side=tk.LEFT, padx=5)
        tk.Button(msg_frame, text="Send Custom", command=self.send_custom, bg="#00aaff", fg="white", font=("Arial", 12)).pack(side=tk.LEFT, padx=5)

        # TX control
        tx_frame = tk.Frame(frame, bg="#1a1a1a")
        tx_frame.pack(pady=10)
        tk.Label(tx_frame, text="TX:", fg="cyan", bg="#1a1a1a", font=("Arial", 12)).pack(side=tk.LEFT, padx=5)
        tk.Button(tx_frame, text="TX ON", command=self.tx_on, bg="#ff4444", fg="white", font=("Arial", 12, "bold")).pack(side=tk.LEFT, padx=5)
        tk.Button(tx_frame, text="TX OFF", command=self.tx_off, bg="#00ff88", fg="black", font=("Arial", 12, "bold")).pack(side=tk.LEFT, padx=5)

        # CW Decoder button
        decoder_frame = tk.Frame(frame, bg="#1a1a1a")
        decoder_frame.pack(pady=10)
        tk.Button(decoder_frame, text="Open CW Decoder", command=lambda: qcx_cw_decoder.open_cw_decoder(self), bg="#00aaff", fg="white", font=("Arial", 12)).pack(side=tk.LEFT, padx=5)

        # QSL Log button
        qsl_frame = tk.Frame(frame, bg="#1a1a1a")
        qsl_frame.pack(pady=10)
        tk.Button(qsl_frame, text="Open QSL Log", command=self.open_qsl_log, bg="#00aaff", fg="white", font=("Arial", 12)).pack(side=tk.LEFT, padx=5)

        # Band selection
        band_frame = tk.Frame(frame, bg="#1a1a1a")
        band_frame.pack(pady=10)
        tk.Label(band_frame, text="Band:", fg="cyan", bg="#1a1a1a", font=("Arial", 12)).pack(side=tk.LEFT, padx=5)
        self.band_var = tk.StringVar(value="40m")
        self.band_combo = ttk.Combobox(band_frame, textvariable=self.band_var, values=self.update_bands, width=6)
        self.band_combo.pack(side=tk.LEFT, padx=5)
        tk.Button(band_frame, text="Set Band", command=self.set_band, bg="#00aaff", fg="white", font=("Arial", 12)).pack(side=tk.LEFT, padx=5)

        # Scan section
        scan_frame = tk.Frame(frame, bg="#1a1a1a")
        scan_frame.pack(pady=10)
        tk.Label(scan_frame, text="Scan Center (MHz):", fg="cyan", bg="#1a1a1a", font=("Arial", 12)).pack(side=tk.LEFT, padx=5)
        self.scan_center_entry = tk.Entry(scan_frame, width=12)
        self.scan_center_entry.pack(side=tk.LEFT, padx=5)
        self.scan_center_entry.insert(0, str(self.scan_center))
        tk.Label(scan_frame, text="Steps:", fg="cyan", bg="#1a1a1a", font=("Arial", 12)).pack(side=tk.LEFT, padx=5)
        self.scan_steps_entry = tk.Entry(scan_frame, width=6)
        self.scan_steps_entry.pack(side=tk.LEFT, padx=5)
        self.scan_steps_entry.insert(0, str(self.scan_steps))
        tk.Label(scan_frame, text="Step kHz:", fg="cyan", bg="#1a1a1a", font=("Arial", 12)).pack(side=tk.LEFT, padx=5)
        self.scan_step_entry = tk.Entry(scan_frame, width=6)
        self.scan_step_entry.pack(side=tk.LEFT, padx=5)
        self.scan_step_entry.insert(0, str(self.scan_step_khz))
        tk.Button(scan_frame, text="Start Scan", command=self.start_scan, bg="#00ff88", fg="black", font=("Arial", 12)).pack(side=tk.LEFT, padx=5)
        tk.Button(scan_frame, text="Stop Scan", command=self.stop_scan, bg="#ff4444", fg="white", font=("Arial", 12)).pack(side=tk.LEFT, padx=5)

        # Graphs buttons
        graphs_frame = tk.Frame(frame, bg="#1a1a1a")
        graphs_frame.pack(pady=10)
        tk.Button(graphs_frame, text="Open Graphs", command=qcx_graphs.open_graphs, bg="#00aaff", fg="white", font=("Arial", 12)).pack(side=tk.LEFT, padx=5)

        # FT8 button
        ft8_frame = tk.Frame(frame, bg="#1a1a1a")
        ft8_frame.pack(pady=10)
        tk.Button(ft8_frame, text="Launch FT8", command=self.launch_wsjtx, bg="#00aaff", fg="white", font=("Arial", 12)).pack(side=tk.LEFT, padx=5)

        # Continuous waterfall
        continuous_frame = tk.Frame(frame, bg="#1a1a1a")
        continuous_frame.pack(pady=10)
        tk.Button(continuous_frame, text="Start Continuous Waterfall", command=self.start_continuous_waterfall, bg="#00ff88", fg="black", font=("Arial", 12)).pack(side=tk.LEFT, padx=5)
        tk.Button(continuous_frame, text="Stop Continuous Waterfall", command=self.stop_continuous_waterfall, bg="#ff4444", fg="white", font=("Arial", 12)).pack(side=tk.LEFT, padx=5)

        # Waterfall display
        self.waterfall_label = tk.Label(frame, text="Waterfall Data:", fg="cyan", bg="#1a1a1a", font=("Arial", 12))
        self.waterfall_label.pack(pady=5)
        self.waterfall_text = scrolledtext.ScrolledText(frame, font=("Courier", 10), bg="#000000", fg="#00ff00", height=10)
        self.waterfall_text.pack(pady=5, padx=20, fill=tk.X)

        # Update bands
        self.update_bands()

    def on_device_change(self, event):
        self.update_bands()

    def connect(self):
        port = self.port_var.get()
        try:
            self.ser = serial.Serial(port, 38400, timeout=1)
            self.status_label.config(text="Connected", fg="green")
            self.poll()
        except Exception as e:
            messagebox.showerror("Connection Error", str(e))

    def poll(self):
        if self.ser:
            try:
                self.send_cmd('FA;')
                freq = self.ser.readline().decode().strip()
                self.debug_print(f"Frequency: {freq}")
                # Add more polling as needed
            except Exception as e:
                self.debug_print(f"Poll error: {e}")
            self.root.after(self.poll_interval, self.poll)

    def set_poll(self):
        try:
            self.poll_interval = int(self.poll_entry.get())
        except:
            messagebox.showerror("Error", "Invalid poll interval")

    def start_scan(self):
        self.scanning = True
        self.scan_thread = threading.Thread(target=self.scan, daemon=True)
        self.scan_thread.start()

    def stop_scan(self):
        self.scanning = False
        self.activity_detected = False

    def scan(self):
        if not self.ser:
            return

        center = float(self.scan_center_entry.get())
        steps = int(self.scan_steps_entry.get())
        step_khz = int(self.scan_step_entry.get())

        for s in range(-steps, steps + 1):
            if not self.scanning:
                break
            f = center + s * step_khz / 1000
            self.freq_entry.delete(0, tk.END)
            self.freq_entry.insert(0, f"{f:.6f}")
            self.set_freq()
            time.sleep(5)  # Adjust as needed
            # Check for activity
            if self.activity_detected:
                break

    def start_continuous_waterfall(self):
        self.continuous_waterfall = True
        self.continuous_thread = threading.Thread(target=self.continuous_waterfall_loop, daemon=True)
        self.continuous_thread.start()

    def stop_continuous_waterfall(self):
        self.continuous_waterfall = False

    def continuous_waterfall_loop(self):
        while self.continuous_waterfall:
            # Simulate waterfall data
            data = f"Frequency: {random.uniform(7.0, 7.1):.4f} MHz, Signal: {random.randint(0, 100)} dB"
            self.waterfall_data.append(data)
            if len(self.waterfall_data) > self.max_waterfall_rows:
                self.waterfall_data.pop(0)
            self.waterfall_text.delete(1.0, tk.END)
            self.waterfall_text.insert(tk.END, "\n".join(self.waterfall_data))
            time.sleep(1)  # Adjust as needed

    def open_qsl_log(self):
        qsl_window = tk.Toplevel(self.root)
        qsl_window.title("QSL Log")
        qsl_window.geometry("800x600")

        qsl_text = scrolledtext.ScrolledText(qsl_window, font=("Courier", 10), bg="#000000", fg="#00ff00")
        qsl_text.pack(fill=tk.BOTH, expand=True)

        # Load QSL log - assume ADIF or text file (placeholder - replace with actual file)
        try:
            with open("qsl_log.adif", "r") as f:
                log_content = f.read()
            qsl_text.insert(tk.END, log_content)
        except FileNotFoundError:
            qsl_text.insert(tk.END, "No QSL log file found. Create 'qsl_log.adif' or add logging feature.")

    def send_cmd(self, cmd):
        if self.ser:
            self.ser.write((cmd + ';').encode())
            self.debug_print(f"Sent: {cmd};")

    def on_device_change(self, event):
        self.update_bands()

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

    def toggle_debug(seslf):
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

if __name__ == "__main__":
    root = tk.Tk()
    app = QCXUltimateGUI(root)
    root.mainloop()