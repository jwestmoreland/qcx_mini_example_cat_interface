# new_cat3.py - Fixed CW decode with TB; (correct GET command)

import serial
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import time

class QCXUltimateGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("QCX-mini ULTIMATE CAT CONTROL by AJ6BC + Grok")
        self.root.geometry("720x1100")
        self.root.configure(bg="#1a1a1a")

        self.ser = None
        self.tx_timer = None
        self.debug_window = None
        self.debug_active = False

        # === Disclaimer ===
        disclaimer = tk.Label(root, text="This is an experimental CAT interface; use at your own risk. I am 100% indemnified from any damages whatsoever.",
                              fg="red", bg="#1a1a1a", font=("Arial", 10, "italic"))
        disclaimer.pack(pady=5)

        # === Connect + Debug Toggle ===
        top_frame = tk.Frame(root, bg="#1a1a1a")
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
        vfo_frame = tk.Frame(root, bg="#1a1a1a")
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

        # === Set Frequency + VFO Selector ===
        setf_frame = tk.Frame(root, bg="#1a1a1a")
        setf_frame.pack(pady=5)
        tk.Label(setf_frame, text="Set Freq (MHz):", fg="white", bg="#1a1a1a").grid(row=0, column=0)
        self.freq_entry = tk.Entry(setf_frame, width=12, font=("Arial", 12))
        self.freq_entry.grid(row=0, column=1, padx=5)
        self.vfo_select_var = tk.StringVar(value="A")
        vfo_combo = ttk.Combobox(setf_frame, textvariable=self.vfo_select_var, values=["A", "B"], width=4)
        vfo_combo.grid(row=0, column=2, padx=5)
        tk.Button(setf_frame, text="TUNE", command=self.set_freq, bg="#0088ff", fg="white").grid(row=0, column=3, padx=5)

        # === Band Buttons ===
        band_frame = tk.LabelFrame(root, text="BAND", fg="cyan", bg="#1a1a1a")
        band_frame.pack(pady=10)
        bands = ["160m","80m","60m","40m","30m","20m","17m","15m","12m","10m","6m"]
        freqs = [1.84,3.58,5.357,7.03,10.116,14.06,18.1,21.06,24.92,28.06,50.1]
        for i, (band, freq) in enumerate(zip(bands, freqs)):
            tk.Button(band_frame, text=band, command=lambda f=freq: self.band_change(f), width=6, bg="#444444", fg="white").grid(row=i//6, column=i%6, padx=5, pady=5)

        # === RIT Buttons ===
        rit_frame = tk.LabelFrame(root, text="RIT", fg="cyan", bg="#1a1a1a")
        rit_frame.pack(pady=10)
        tk.Button(rit_frame, text="-100 Hz", command=lambda: self.rit_adjust(-100), bg="#ff8800", fg="black").pack(side=tk.LEFT, padx=5)
        tk.Button(rit_frame, text="0", command=self.rit_zero, bg="#888888", fg="white").pack(side=tk.LEFT, padx=5)
        tk.Button(rit_frame, text="+100 Hz", command=lambda: self.rit_adjust(100), bg="#ff8800", fg="black").pack(side=tk.LEFT, padx=5)

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

        # === Custom Message ===
        cust_frame = tk.Frame(root, bg="#1a1a1a")
        cust_frame.pack(pady=10)
        self.msg_entry = tk.Entry(cust_frame, width=50, font=("Arial", 14))
        self.msg_entry.pack()
        tk.Button(cust_frame, text="SEND CUSTOM MESSAGE", command=self.send_custom, bg="#ff00ff", fg="white", font=("Arial", 12)).pack(pady=5)

        # === VFO A/B + Split + Practice Buttons ===
        vfo_control_frame = tk.Frame(root, bg="#1a1a1a")
        vfo_control_frame.pack(pady=10)
        tk.Button(vfo_control_frame, text="VFO A", command=lambda: self.set_vfo("A"), bg="#00aa00", fg="white", font=("Arial", 12, "bold"), width=8, height=1).pack(side=tk.LEFT, padx=10)
        tk.Button(vfo_control_frame, text="VFO B", command=lambda: self.set_vfo("B"), bg="#aa5500", fg="white", font=("Arial", 12, "bold"), width=8, height=1).pack(side=tk.LEFT, padx=10)
        tk.Button(vfo_control_frame, text="SPLIT", command=self.toggle_split, bg="#ff8800", fg="black", font=("Arial", 12, "bold"), width=8, height=1).pack(side=tk.LEFT, padx=10)
        tk.Button(vfo_control_frame, text="PRACTICE", command=self.toggle_practice, bg="#00ffff", fg="black", font=("Arial", 12, "bold"), width=10, height=1).pack(side=tk.LEFT, padx=10)

        # === TX Control ===
        tx_frame = tk.Frame(root, bg="#1a1a1a")
        tx_frame.pack(pady=20)
        tk.Button(tx_frame, text="TX ON", command=self.tx_on, bg="#ff0000", fg="white", font=("Arial", 16, "bold"), width=10).pack(side=tk.LEFT, padx=30)
        tk.Button(tx_frame, text="TX OFF", command=self.tx_off, bg="#888888", fg="white", font=("Arial", 16, "bold"), width=10).pack(side=tk.LEFT, padx=30)
        tk.Button(tx_frame, text="STOP TX NOW", command=self.tx_off, bg="#ffff00", fg="black", font=("Arial", 16, "bold"), width=14).pack(side=tk.LEFT, padx=30)

        # === TB Decode Buffer (append only) ===
        tb_frame = tk.LabelFrame(root, text="CW DECODE BUFFER (TB)", fg="cyan", bg="#1a1a1a")
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
            # Enable CW decoder notifications
            self.send_cmd('QU1')
            self.send_cmd('TB1')  # Enable decode flag
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

            # RIT
            if_resp = self.send_cmd('IF')
            if if_resp.startswith('IF') and len(if_resp) >= 32:
                rit = int(if_resp[18:23]) if if_resp[18:23].strip() else 0
                self.rit_label.config(text=f"RIT: {rit:+} Hz")

            # S-meter
            s_meter = if_resp[29] if len(if_resp) > 29 and if_resp[29].isdigit() else "0"
            self.s_meter_label.config(text=f"S-Meter: S{s_meter}")

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

    # ... (all other methods unchanged from your original file) ...

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

    # === Debug Console Methods ===
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