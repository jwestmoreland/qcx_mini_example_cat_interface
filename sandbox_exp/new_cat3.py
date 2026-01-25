# new_cat3.py
# Updated with mouse wheel tuning (flrig-style) on frequency entry

import serial
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time

class QCXUltimateGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("QCX-mini ULTIMATE CAT CONTROL by AJ6BC + Grok")
        self.root.geometry("680x800")
        self.root.configure(bg="#1a1a1a")

        self.ser = None

        # === Disclaimer ===
        disclaimer = tk.Label(root, text="This is an experimental CAT interface; use at your own risk. I am 100% indemnified from any damages whatsoever.",
                              fg="red", bg="#1a1a1a", font=("Arial", 10, "italic"))
        disclaimer.pack(pady=5)

        # === Connect ===
        top_frame = tk.Frame(root, bg="#1a1a1a")
        top_frame.pack(pady=10)
        tk.Label(top_frame, text="COM Port:", fg="cyan", bg="#1a1a1a", font=("Arial", 12)).pack(side=tk.LEFT)
        self.port_var = tk.StringVar(value="COM3")
        tk.Entry(top_frame, textvariable=self.port_var, width=8).pack(side=tk.LEFT, padx=5)
        tk.Button(top_frame, text="CONNECT", command=self.connect, bg="#00ff00", fg="black", font=("Arial", 12, "bold")).pack(side=tk.LEFT, padx=5)
        self.status_label = tk.Label(top_frame, text="Not connected", fg="red", bg="#1a1a1a", font=("Arial", 12, "bold"))
        self.status_label.pack(side=tk.LEFT, padx=20)

        # === Frequency + RIT ===
        freq_frame = tk.Frame(root, bg="#1a1a1a")
        freq_frame.pack(pady=10)
        self.freq_label = tk.Label(freq_frame, text="?.?????? MHz", fg="#00ff00", bg="#1a1a1a", font=("Arial", 36, "bold"))
        self.freq_label.pack()
        self.rit_label = tk.Label(freq_frame, text="RIT: 0 Hz", fg="yellow", bg="#1a1a1a", font=("Arial", 16))
        self.rit_label.pack()

        # === Set Frequency ===
        setf_frame = tk.Frame(root, bg="#1a1a1a")
        setf_frame.pack(pady=5)
        tk.Label(setf_frame, text="Set Freq (MHz):", fg="white", bg="#1a1a1a").grid(row=0, column=0)
        self.freq_entry = tk.Entry(setf_frame, width=12, font=("Arial", 12))
        self.freq_entry.grid(row=0, column=1, padx=5)
        tk.Button(setf_frame, text="TUNE", command=self.set_freq, bg="#0088ff", fg="white").grid(row=0, column=2)

        # Mouse wheel tuning (flrig style)
        self.freq_entry.bind("<MouseWheel>", self.wheel_tune)  # Windows
        self.freq_entry.bind("<Button-4>", self.wheel_tune)   # Linux scroll up
        self.freq_entry.bind("<Button-5>", self.wheel_tune)   # Linux scroll down

        # === Band Buttons (only 40m for this radio) ===
        band_frame = tk.LabelFrame(root, text="BAND", fg="cyan", bg="#1a1a1a")
        band_frame.pack(pady=10)
        tk.Button(band_frame, text="40m", command=lambda: self.band_change(7.03), width=6, bg="#444444", fg="white").pack(padx=5, pady=5)

        # === RIT Buttons ===
        rit_frame = tk.LabelFrame(root, text="RIT", fg="cyan", bg="#1a1a1a")
        rit_frame.pack(pady=10)
        tk.Button(rit_frame, text="RIT -100 Hz", command=lambda: self.rit_adjust(-100), bg="#ff8800", fg="black").pack(side=tk.LEFT, padx=5)
        tk.Button(rit_frame, text="RIT 0", command=self.rit_zero, bg="#888888", fg="white").pack(side=tk.LEFT, padx=5)
        tk.Button(rit_frame, text="RIT +100 Hz", command=lambda: self.rit_adjust(100), bg="#ff8800", fg="black").pack(side=tk.LEFT, padx=5)

        # === Keyer Speed ===
        speed_frame = tk.LabelFrame(root, text="KEYER SPEED", fg="cyan", bg="#1a1a1a")
        speed_frame.pack(pady=10)
        self.speed_var = tk.IntVar(value=20)
        tk.Scale(speed_frame, from_=5, to=40, orient=tk.HORIZONTAL, variable=self.speed_var, length=300, bg="#333333", fg="white").pack()
        tk.Button(speed_frame, text="SET", command=self.set_speed, bg="#ffaa00", fg="black").pack(pady=5)

        # === Preset CW Messages ===
        msg_frame = tk.LabelFrame(root, text="PRESET CW MESSAGES", fg="cyan", bg="#1a1a1a")
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

        # === Custom Message + Split ===
        cust_frame = tk.Frame(root, bg="#1a1a1a")
        cust_frame.pack(pady=10)
        self.msg_entry = tk.Entry(cust_frame, width=40)
        self.msg_entry.pack(side=tk.LEFT, padx=5)
        tk.Button(cust_frame, text="SEND", command=self.send_custom, bg="#ff00ff", fg="white").pack(side=tk.LEFT, padx=5)
        tk.Button(cust_frame, text="VFO A/SPLIT", command=self.toggle_split, bg="#ff8800", fg="black").pack(side=tk.LEFT, padx=10)

        # === TX Control ===
        tx_frame = tk.Frame(root, bg="#1a1a1a")
        tx_frame.pack(pady=20)
        tk.Button(tx_frame, text="TX ON", command=self.tx_on, bg="#ff0000", fg="white", font=("Arial", 16, "bold"), width=10).pack(side=tk.LEFT, padx=30)
        tk.Button(tx_frame, text="TX OFF", command=self.tx_off, bg="#888888", fg="white", font=("Arial", 16, "bold"), width=10).pack(side=tk.LEFT, padx=30)
        tk.Button(tx_frame, text="STOP TX NOW", command=self.tx_off, bg="#ffff00", fg="black", font=("Arial", 16, "bold"), width=12).pack(side=tk.LEFT, padx=30)

        self.tx_timer = None
        self.poll_status()

    def connect(self):
        if self.ser:
            self.ser.close()
        try:
            self.ser = serial.Serial(self.port_var.get(), 38400, timeout=1)
            self.status_label.config(text="CONNECTED", fg="#00ff00")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def send_cmd(self, cmd):
        if not self.ser: return "?"
        try:
            self.ser.write((cmd + ';').encode())
            return self.ser.read_until(b';').decode().strip()
        except:
            return "?"

    def poll_status(self):
        if self.ser:
            resp = self.send_cmd('IF')
            if resp.startswith('IF') and len(resp) >= 32:
                freq_str = resp[2:13]
                freq = int(freq_str) / 1e6
                rit = int(resp[18:23]) if resp[18:23].strip() else 0
                self.freq_label.config(text=f"{freq:.6f} MHz")
                self.rit_label.config(text=f"RIT: {rit:+} Hz")
        self.root.after(1000, self.poll_status)

    def band_change(self, freq):
        self.freq_entry.delete(0, tk.END)
        self.freq_entry.insert(0, str(freq))
        self.set_freq()

    def set_freq(self):
        try:
            f = float(self.freq_entry.get())
            freq_hz = int(f * 1e6)
            cmd = f'FA{str(freq_hz).zfill(11)}'
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

    def send_custom(self):
        msg = self.msg_entry.get()
        if msg:
            threading.Thread(target=self._send, args=(msg,), daemon=True).start()

    def _send(self, msg):
        self.send_cmd(f'KY {msg}')

    def toggle_split(self):
        current = self.send_cmd('FT')
        self.send_cmd('FT0' if '0' in current else 'FT1')
        self.send_cmd('FT1' if '0' in current else 'FT2')
        self.send_cmd('FT2' if '0' in current else 'FT0')

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