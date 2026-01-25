# qcx_ultimate_gui_with_scrollbars.py
# Ultimate QCX-mini CAT Control - Added vertical scrollbar to main window

import serial
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import time
from datetime import datetime

class QCXUltimateGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("QCX-mini ULTIMATE CAT CONTROL by AJ6BC + Grok")
        self.root.geometry("800x900")  # Slightly smaller height to force scroll if needed
        self.root.configure(bg="#1a1a1a")

        self.ser = None
        self.tx_timer = None
        self.debug_window = None
        self.debug_active = False
        self.log_file = None

        # === Main Canvas + Scrollbar for whole GUI ===
        canvas = tk.Canvas(root, bg="#1a1a1a")
        scrollbar = tk.Scrollbar(root, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        # Inner frame for all content
        inner_frame = tk.Frame(canvas, bg="#1a1a1a")
        canvas.create_window((0, 0), window=inner_frame, anchor="nw")

        # Update scroll region when size changes
        inner_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        # === Disclaimer ===
        disclaimer = tk.Label(inner_frame, text="Experimental CAT interface - use at your own risk. 100% no liability for damages.",
                              fg="red", bg="#1a1a1a", font=("Arial", 10, "italic"))
        disclaimer.pack(pady=5)

        # === Connect + Debug Toggle ===
        top_frame = tk.Frame(inner_frame, bg="#1a1a1a")
        top_frame.pack(pady=10)
        tk.Label(top_frame, text="COM Port:", fg="cyan", bg="#1a1a1a", font=("Arial", 12)).pack(side=tk.LEFT)
        self.port_var = tk.StringVar(value="COM3")
        tk.Entry(top_frame, textvariable=self.port_var, width=8).pack(side=tk.LEFT, padx=5)
        tk.Button(top_frame, text="CONNECT", command=self.connect, bg="#00ff00", fg="black", font=("Arial", 12, "bold")).pack(side=tk.LEFT, padx=5)
        self.status_label = tk.Label(top_frame, text="Not connected", fg="red", bg="#1a1a1a", font=("Arial", 12, "bold"))
        self.status_label.pack(side=tk.LEFT, padx=20)

        # Debug checkbox
        self.debug_var = tk.BooleanVar()
        tk.Checkbutton(top_frame, text="Debug Console", variable=self.debug_var, command=self.toggle_debug,
                       bg="#1a1a1a", fg="yellow", selectcolor="#333333").pack(side=tk.LEFT, padx=20)

        # === VFO Display ===
        vfo_frame = tk.Frame(inner_frame, bg="#1a1a1a")
        vfo_frame.pack(pady=10)
        self.vfoa_label = tk.Label(vfo_frame, text="VFO A: ?.?????? MHz", fg="#00ff00", bg="#1a1a1a", font=("Arial", 32, "bold"))
        self.vfoa_label.pack()
        self.vfob_label = tk.Label(vfo_frame, text="VFO B: ?.?????? MHz", fg="#ff8800", bg="#1a1a1a", font=("Arial", 28, "bold"))
        self.vfob_label.pack()
        self.mode_label = tk.Label(vfo_frame, text="Mode: ?", fg="cyan", bg="#1a1a1a", font=("Arial", 28, "bold"))
        self.mode_label.pack(pady=8)
        self.rit_label = tk.Label(vfo_frame, text="RIT: 0 Hz", fg="yellow", bg="#1a1a1a", font=("Arial", 20))
        self.rit_label.pack()
        self.s_meter_label = tk.Label(vfo_frame, text="S-Meter: -", fg="#00ffff", bg="#1a1a1a", font=("Arial", 22, "bold"))
        self.s_meter_label.pack()
        self.practice_label = tk.Label(vfo_frame, text="Practice Mode: Set in menu 4.7", fg="magenta", bg="#1a1a1a", font=("Arial", 20))
        self.practice_label.pack()

        # === Set Frequency + VFO Selector + Mouse Wheel Tuning ===
        setf_frame = tk.Frame(inner_frame, bg="#1a1a1a")
        setf_frame.pack(pady=5)
        tk.Label(setf_frame, text="Set Freq (MHz):", fg="white", bg="#1a1a1a", font=("Arial", 14)).grid(row=0, column=0)
        self.freq_entry = tk.Entry(setf_frame, width=12, font=("Arial", 14))
        self.freq_entry.grid(row=0, column=1, padx=5)
        self.vfo_select_var = tk.StringVar(value="A")
        vfo_combo = ttk.Combobox(setf_frame, textvariable=self.vfo_select_var, values=["A", "B"], width=4)
        vfo_combo.grid(row=0, column=2, padx=5)
        tk.Button(setf_frame, text="TUNE", command=self.set_freq, bg="#0088ff", fg="white", font=("Arial", 14)).grid(row=0, column=3, padx=5)

        # Mouse wheel tuning
        self.freq_entry.bind("<MouseWheel>", self.wheel_tune)
        self.freq_entry.bind("<Button-4>", self.wheel_tune)
        self.freq_entry.bind("<Button-5>", self.wheel_tune)

        # === Band Buttons ===
        band_frame = tk.LabelFrame(inner_frame, text="BAND", fg="cyan", bg="#1a1a1a")
        band_frame.pack(pady=10)
        bands = ["160m","80m","60m","40m","30m","20m","17m","15m","12m","10m","6m"]
        freqs = [1.84,3.58,5.357,7.03,10.116,14.06,18.1,21.06,24.92,28.06,50.1]
        for i, (band, freq) in enumerate(zip(bands, freqs)):
            tk.Button(band_frame, text=band, command=lambda f=freq: self.band_change(f), width=6, bg="#444444", fg="white").grid(row=i//6, column=i%6, padx=5, pady=5)

        # === RIT Buttons ===
        rit_frame = tk.LabelFrame(inner_frame, text="RIT", fg="cyan", bg="#1a1a1a")
        rit_frame.pack(pady=10)
        tk.Button(rit_frame, text="-100 Hz", command=lambda: self.rit_adjust(-100), bg="#ff8800", fg="black").pack(side=tk.LEFT, padx=5)
        tk.Button(rit_frame, text="0", command=self.rit_zero, bg="#888888", fg="white").pack(side=tk.LEFT, padx=5)
        tk.Button(rit_frame, text="+100 Hz", command=lambda: self.rit_adjust(100), bg="#ff8800", fg="black").pack(side=tk.LEFT, padx=5)

        # === Keyer Speed ===
        speed_frame = tk.LabelFrame(inner_frame, text="KEYER SPEED", fg="cyan", bg="#1a1a1a")
        speed_frame.pack(pady=10)
        self.speed_var = tk.IntVar(value=20)
        tk.Scale(speed_frame, from_=5, to=40, orient=tk.HORIZONTAL, variable=self.speed_var, length=300, bg="#333333", fg="white").pack()
        tk.Button(speed_frame, text="SET", command=self.set_speed, bg="#ffaa00", fg="black").pack(pady=5)

        # === Preset CW Messages ===
        msg_frame = tk.LabelFrame(inner_frame, text="PRESET CW MESSAGES", fg="cyan", bg="#1a1a1a")
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

        # === Custom Message ===
        cust_frame = tk.Frame(inner_frame, bg="#1a1a1a")
        cust_frame.pack(pady=10)
        self.msg_entry = tk.Entry(cust_frame, width=50, font=("Arial", 14))
        self.msg_entry.pack()
        tk.Button(cust_frame, text="SEND CUSTOM MESSAGE", command=self.send_custom, bg="#ff00ff", fg="white", font=("Arial", 12)).pack(pady=5)

        # === VFO A/B + Split + Practice Buttons ===
        vfo_control_frame = tk.Frame(inner_frame, bg="#1a1a1a")
        vfo_control_frame.pack(pady=10)
        tk.Button(vfo_control_frame, text="VFO A", command=lambda: self.set_vfo("A"), bg="#00aa00", fg="white", font=("Arial", 12, "bold"), width=8, height=1).pack(side=tk.LEFT, padx=10)
        tk.Button(vfo_control_frame, text="VFO B", command=lambda: self.set_vfo("B"), bg="#aa5500", fg="white", font=("Arial", 12, "bold"), width=8, height=1).pack(side=tk.LEFT, padx=10)
        tk.Button(vfo_control_frame, text="SPLIT", command=self.toggle_split, bg="#ff8800", fg="black", font=("Arial", 12, "bold"), width=8, height=1).pack(side=tk.LEFT, padx=10)
        tk.Button(vfo_control_frame, text="PRACTICE", command=self.toggle_practice, bg="#00ffff", fg="black", font=("Arial", 12, "bold"), width=10, height=1).pack(side=tk.LEFT, padx=10)

        # === TX Control ===
        tx_frame = tk.Frame(inner_frame, bg="#1a1a1a")
        tx_frame.pack(pady=20)
        tk.Button(tx_frame, text="TX ON", command=self.tx_on, bg="#ff0000", fg="white", font=("Arial", 16, "bold"), width=10).pack(side=tk.LEFT, padx=30)
        tk.Button(tx_frame, text="TX OFF", command=self.tx_off, bg="#888888", fg="white", font=("Arial", 16, "bold"), width=10).pack(side=tk.LEFT, padx=30)
        tk.Button(tx_frame, text="STOP TX NOW", command=self.tx_off, bg="#ffff00", fg="black", font=("Arial", 16, "bold"), width=14).pack(side=tk.LEFT, padx=30)

        # === Clear Decode Buffer Button ===
        clear_tb_frame = tk.Frame(inner_frame, bg="#1a1a1a")
        clear_tb_frame.pack(pady=5)
        tk.Button(clear_tb_frame, text="Clear Decode Buffer", command=self.clear_decode_buffer, bg="#ffaa00", fg="black").pack()

        # === Frequency Presets ===
        preset_frame = tk.LabelFrame(inner_frame, text="FREQUENCY PRESETS", fg="cyan", bg="#1a1a1a")
        preset_frame.pack(pady=10)
        self.preset_vars = [tk.StringVar(value="0.000000") for _ in range(8)]
        for i in range(8):
            row = i // 4
            col = i % 4
            tk.Button(preset_frame, text=f"P{i+1}", command=lambda n=i+1: self.recall_preset(n), width=6, bg="#444444", fg="white").grid(row=row, column=col*2, padx=5)
            tk.Button(preset_frame, text="Store", command=lambda n=i+1: self.store_preset(n), width=6, bg="#aa5500", fg="white").grid(row=row, column=col*2+1, padx=5)

        # === Macro Editor ===
        macro_frame = tk.LabelFrame(inner_frame, text="MACRO EDITOR", fg="cyan", bg="#1a1a1a")
        macro_frame.pack(pady=10)
        self.macro_vars = [tk.StringVar(value="") for _ in range(12)]
        for i in range(12):
            row = i // 3
            col = i % 3
            tk.Label(macro_frame, text=f"M{i+1}:", fg="white", bg="#1a1a1a").grid(row=row, column=col*3, sticky="e")
            tk.Entry(macro_frame, textvariable=self.macro_vars[i], width=30).grid(row=row, column=col*3+1, padx=5)
            tk.Button(macro_frame, text="Save", command=lambda n=i+1: self.save_macro(n), bg="#ffaa00", fg="black").grid(row=row, column=col*3+2, padx=5)

        # === Beacon Mode Controls ===
        beacon_frame = tk.LabelFrame(inner_frame, text="BEACON MODE", fg="cyan", bg="#1a1a1a")
        beacon_frame.pack(pady=10)
        tk.Button(beacon_frame, text="Beacon ON", command=lambda: self.send_cmd('BN1'), bg="#00ff00", fg="black").pack(side=tk.LEFT, padx=10)
        tk.Button(beacon_frame, text="Beacon OFF", command=lambda: self.send_cmd('BN0'), bg="#ff0000", fg="white").pack(side=tk.LEFT, padx=10)
        tk.Label(beacon_frame, text="Delay (s):", fg="white", bg="#1a1a1a").pack(side=tk.LEFT, padx=10)
        self.beacon_delay_var = tk.IntVar(value=60)
        tk.Spinbox(beacon_frame, from_=1, to=999, textvariable=self.beacon_delay_var, width=5).pack(side=tk.LEFT, padx=5)
        tk.Button(beacon_frame, text="Set Delay", command=self.set_beacon_delay, bg="#ffaa00", fg="black").pack(side=tk.LEFT, padx=10)

        tk.Label(beacon_frame, text="Frame:", fg="white", bg="#1a1a1a").pack(side=tk.LEFT, padx=10)
        self.beacon_frame_var = tk.IntVar(value=1)
        tk.Spinbox(beacon_frame, from_=1, to=99, textvariable=self.beacon_frame_var, width=5).pack(side=tk.LEFT, padx=5)
        tk.Button(beacon_frame, text="Set Frame", command=self.set_beacon_frame, bg="#ffaa00", fg="black").pack(side=tk.LEFT, padx=10)

        # === Status Bar ===
        status_bar = tk.Frame(inner_frame, bg="#333333")
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        self.status_text = tk.Label(status_bar, text="Status: Idle", fg="white", bg="#333333", font=("Arial", 12))
        self.status_text.pack(side=tk.LEFT, padx=10)

        # === TB Decode Buffer (append only) ===
        tb_frame = tk.LabelFrame(inner_frame, text="CW DECODE BUFFER (TB)", fg="cyan", bg="#1a1a1a")
        tb_frame.pack(pady=10, fill=tk.BOTH, expand=True, padx=20)
        self.tb_text = scrolledtext.ScrolledText(tb_frame, height=8, font=("Courier", 12), bg="#000000", fg="#00ff00")
        self.tb_text.pack(fill=tk.BOTH, expand=True)

        self.poll_status()

    def connect(self):
        if self.ser:
            self.ser.close()
        try:
            self.ser = serial.Serial(self.port_var.get(), 38400, timeout=1)
            self.status_label.config(text="CONNECTED", fg="#00ff00")
            self.send_cmd('QU1')
            self.send_cmd('TB1')
            # Start logging
            self.log_file = open(f"qso_log_{datetime.now():%Y%m%d_%H%M%S}.csv", "a", newline="")
            self.log_file.write("Time,Call,Freq,RST Sent,RST Rcvd,Notes\n")
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
            messagebox.showerror("CAT Error", f"Command failed: {cmd}\n{e}")
            return "?"

    def poll_status(self):
        if self.ser:
            # VFO A
            fa_resp = self.send_cmd('FA')
            if fa_resp.startswith('FA'):
                vfoa = int(fa_resp[2:13]) / 1e6
                self.vfoa_label.config(text=f"VFO A: {vfoa:.6f} MHz")

            # VFO B
            fb_resp = self.send_cmd('FB')
            if fb_resp.startswith('FB'):
                vfob = int(fb_resp[2:13]) / 1e6
                self.vfob_label.config(text=f"VFO B: {vfob:.6f} MHz")

            # Full status
            if_resp = self.send_cmd('IF')
            if if_resp.startswith('IF') and len(if_resp) >= 32:
                rit = int(if_resp[18:23]) if if_resp[18:23].strip() else 0
                self.rit_label.config(text=f"RIT: {rit:+} Hz")
                s_meter = if_resp[29] if len(if_resp) > 29 and if_resp[29].isdigit() else "0"
                self.s_meter_label.config(text=f"S-Meter: S{s_meter}")

                # TX state (bit in IF response)
                tx_state = if_resp[30] if len(if_resp) > 30 else "0"
                self.status_text.config(text=f"Status: {'TX' if tx_state == '1' else 'RX'}")

            # VFO Mode
            ft_resp = self.send_cmd('FT')
            if ft_resp == 'FT0':
                self.mode_label.config(text="Mode: VFO A", fg="#00ff00")
            elif ft_resp == 'FT1':
                self.mode_label.config(text="Mode: VFO B", fg="#ff8800")
            elif ft_resp == 'FT2':
                self.mode_label.config(text="Mode: SPLIT", fg="#ff0000")
            else:
                self.mode_label.config(text="Mode: Unknown", fg="cyan")

            # TB; — GET command for decoded CW (clears buffer)
            tb_resp = self.send_cmd('TB')
            if tb_resp.startswith('TB') and len(tb_resp) > 2:
                decoded = tb_resp[2:].strip()
                if decoded:
                    self.tb_text.insert(tk.END, decoded + " ")
                    self.tb_text.see(tk.END)

        self.root.after(1000, self.poll_status)

    def clear_decode_buffer(self):
        self.tb_text.delete(1.0, tk.END)

    def recall_preset(self, n):
        resp = self.send_cmd(f'PS{n}')
        if resp.startswith('PS'):
            freq = int(resp[2:13]) / 1e6
            self.freq_entry.delete(0, tk.END)
            self.freq_entry.insert(0, f"{freq:.6f}")
            self.set_freq()

    def store_preset(self, n):
        try:
            f = float(self.freq_entry.get())
            freq_hz = int(f * 1e6)
            self.send_cmd(f'PS{n}{str(freq_hz).zfill(11)}')
        except: pass

    def save_macro(self, n):
        msg = self.macro_vars[n-1].get()
        self.send_cmd(f'MG{n}{msg}')

    def set_beacon_delay(self):
        delay = self.beacon_delay_var.get()
        self.send_cmd(f'BD{delay:03d}')

    def set_beacon_frame(self):
        frame = self.beacon_frame_var.get()
        self.send_cmd(f'BF{frame:02d}')

    def log_qso(self):
        call = "CALL"  # Placeholder
        freq = self.vfoa_label.cget("text").split(":")[1].strip()
        time_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        if self.log_file:
            self.log_file.write(f"{time_str},{call},{freq},599,599,\n")
            self.log_file.flush()

    def set_vfo(self, vfo):
        if vfo == "A":
            self.send_cmd('FT0')
        elif vfo == "B":
            self.send_cmd('FT1')
        self.root.after(100, self.poll_status)

    def toggle_split(self):
        current = self.send_cmd('FT')
        if current == 'FT2':
            self.send_cmd('FT0')
        else:
            self.send_cmd('FT2')
        self.root.after(100, self.poll_status)

    def toggle_practice(self):
        messagebox.showinfo("Practice Mode", "Practice Mode is set manually in menu 4.7\n(No CAT control available)")

    def band_change(self, freq):
        self.freq_entry.delete(0, tk.END)
        self.freq_entry.insert(0, str(freq))
        self.set_freq()

    def set_freq(self):
        try:
            f = float(self.freq_entry.get())
            freq_hz = int(f * 1e6)
            vfo = self.vfo_select_var.get()
            cmd = f'FA{str(freq_hz).zfill(11)}' if vfo == "A" else f'FB{str(freq_hz).zfill(11)}'
            self.send_cmd(cmd)
        except: pass

    def wheel_tune(self, event):
        try:
            current = float(self.freq_entry.get())
        except ValueError:
            return

        # Detect modifiers and direction
        shift = event.state & 0x1  # Shift
        ctrl = event.state & 0x4   # Ctrl

        if event.num == 5 or event.delta < 0:
            direction = -1
        else:
            direction = 1

        if ctrl:
            step = 1.0  # 1 kHz
        elif shift:
            step = 0.1  # 100 Hz
        else:
            step = 0.01  # 10 Hz

        new_freq = current + direction * step
        self.freq_entry.delete(0, tk.END)
        self.freq_entry.insert(0, f"{new_freq:.6f}")
        self.set_freq()

    def rit_adjust(self, step):
        self.send_cmd(f'RD{abs(step):04d}' if step < 0 else f'RU{step:04d}')

    def rit_zero(self):
        self.send_cmd('RU0')

    def set_speed(self):
        wpm = self.speed_var.get()
        self.send_cmd(f'KS{int(wpm):02d}')

    def send_message(self, msg):
        threading.Thread(target=self._send, args=(msg,), daemon=True).start()
        self.log_qso()

    def send_custom(self):
        msg = self.msg_entry.get()
        if msg:
            threading.Thread(target=self._send, args=(msg,), daemon=True).start()
            self.log_qso()

    def _send(self, msg):
        self.send_cmd(f'KY {msg}')

    def tx_on(self):
        self.send_cmd('TQ1')
        messagebox.showwarning("TX ACTIVE", "Transmitter ON — watch your power!")
        self.tx_timer = self.root.after(60000, self._auto_tx_off)
        self.log_qso()

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

if __name__ == "__main__":
    root = tk.Tk()
    app = QCXUltimateGUI(root)
    root.mainloop()