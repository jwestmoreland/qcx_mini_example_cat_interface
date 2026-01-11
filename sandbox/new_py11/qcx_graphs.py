# qcx_graphs.py
# Separate window for Waterfall and Audio Spectrum Analyzer
# Now properly synced with main app data

import tkinter as tk
from tkinter import ttk
import pyaudio
import numpy as np
from scipy.fft import fft
import threading
import time

def open_graphs(main_app):
    win = tk.Toplevel(main_app.root)
    win.title("QCX Graphs - Waterfall & Audio Spectrum")
    win.geometry("800x720")
    win.configure(bg="#1a1a1a")

    # Waterfall
    wf_frame = tk.LabelFrame(win, text="WATERFALL (Signal Strength over Freq/Time)", fg="cyan", bg="#1a1a1a")
    wf_frame.pack(pady=10, fill=tk.X, padx=20)
    wf_canvas = tk.Canvas(wf_frame, width=720, height=300, bg="#000000")
    wf_canvas.pack()
    pixel_size = 12

    calib_frame = tk.Frame(wf_frame, bg="#1a1a1a")
    calib_frame.pack(pady=5)
    min_s = tk.IntVar(value=0)
    max_s = tk.IntVar(value=9)
    tk.Label(calib_frame, text="Waterfall Min S:", fg="white", bg="#1a1a1a").pack(side=tk.LEFT)
    tk.Scale(calib_frame, from_=0, to=9, orient=tk.HORIZONTAL, variable=min_s, length=150).pack(side=tk.LEFT, padx=10)
    tk.Label(calib_frame, text="Max S:", fg="white", bg="#1a1a1a").pack(side=tk.LEFT)
    tk.Scale(calib_frame, from_=0, to=9, orient=tk.HORIZONTAL, variable=max_s, length=150).pack(side=tk.LEFT, padx=10)

    # Audio Spectrum
    spec_frame = tk.LabelFrame(win, text="AUDIO SPECTRUM ANALYZER (Real-time from PC Microphone)", fg="cyan", bg="#1a1a1a")
    spec_frame.pack(pady=15, fill=tk.X, padx=20)

    audio = pyaudio.PyAudio()
    devices = []
    for i in range(audio.get_device_count()):
        info = audio.get_device_info_by_index(i)
        if info['maxInputChannels'] > 0:
            devices.append((info['name'], i))
    device_var = tk.StringVar()
    if devices:
        device_var.set(devices[0][0])

    ctrl_frame = tk.Frame(spec_frame, bg="#1a1a1a")
    ctrl_frame.pack(pady=5)
    tk.Label(ctrl_frame, text="Input Device:", fg="white", bg="#1a1a1a").pack(side=tk.LEFT)
    if devices:
        ttk.Combobox(ctrl_frame, textvariable=device_var, values=[n for n, i in devices], width=40, state="readonly").pack(side=tk.LEFT, padx=10)
    else:
        tk.Label(ctrl_frame, text="No input devices found!", fg="red", bg="#1a1a1a").pack(side=tk.LEFT, padx=10)

    spec_canvas = tk.Canvas(spec_frame, width=600, height=250, bg="#000000")
    spec_canvas.pack(pady=5)

    freq_labels = tk.Frame(spec_frame, bg="#1a1a1a")
    freq_labels.pack()
    for f in [0, 500, 1000, 1500, 2000, 2500, 3000]:
        tk.Label(freq_labels, text=f"{f} Hz", fg="white", bg="#1a1a1a", font=("Arial", 8)).pack(side=tk.LEFT, expand=True)

    # Real-time waterfall update from main app
    def update_waterfall():
        wf_canvas.delete("all")
        data = main_app.waterfall_data[-main_app.max_waterfall_rows:]
        if not data:
            win.after(500, update_waterfall)
            return

        row_h = wf_canvas.winfo_height() / main_app.max_waterfall_rows
        min_val = min_s.get()
        max_val = max_s.get() if max_s.get() > min_val else min_val + 1

        for row_idx, values in enumerate(reversed(data)):
            for col, s in enumerate(values):
                norm = max(0, min(1, (s - min_val) / (max_val - min_val)))
                colors = ["#000000", "#00008b", "#0000ff", "#00bfff", "#00ff00", "#7fff00", "#ffff00", "#ff7f00", "#ff0000", "#ff0000"]
                color = colors[int(norm * 9)]
                x0 = col * pixel_size
                y0 = row_idx * row_h
                wf_canvas.create_rectangle(x0, y0, x0 + pixel_size, y0 + row_h, fill=color, outline="")

        if main_app.continuous_waterfall and hasattr(main_app, 'vfoa_label'):
            current_text = main_app.vfoa_label.cget("text")
            if "VFO A:" in current_text:
                freq = current_text.split("VFO A:")[1].strip().split(" ")[0]
                x = wf_canvas.winfo_width() // 2
                y = wf_canvas.winfo_height() - 10
                wf_canvas.create_text(x, y, text=f"Current: {freq} MHz", fill="yellow", font=("Arial", 10, "bold"))
        elif main_app.scan_steps > 0:
            step = max(1, main_app.scan_steps // 10)
            for col in range(0, main_app.scan_steps, step):
                freq = main_app.scan_center + (col - main_app.scan_steps // 2) * main_app.scan_step_khz / 1000
                x = col * pixel_size + pixel_size / 2
                y = wf_canvas.winfo_height() - 10
                wf_canvas.create_text(x, y, text=f"{freq:.3f}", fill="white", font=("Arial", 8))

        win.after(500, update_waterfall)

    update_waterfall()

    # Audio spectrum
    chunk = 2048
    rate = 48000
    spectrum_active = False

    def spectrum_loop():
        nonlocal spectrum_active
        try:
            name = device_var.get()
            idx = next(i for n, i in devices if n == name)
            stream = audio.open(format=pyaudio.paInt16, channels=1, rate=rate, input=True, input_device_index=idx, frames_per_buffer=chunk)
        except Exception as e:
            win.after(0, lambda: messagebox.showerror("Audio Error", str(e)))
            return

        while spectrum_active:
            try:
                data = np.frombuffer(stream.read(chunk, exception_on_overflow=False), dtype=np.int16)
                yf = fft(data)
                mag = np.abs(yf[:chunk//2])
                mag_db = 20 * np.log10(mag + 1e-10)
                mag_db -= np.max(mag_db)
                freqs = np.linspace(0, rate/2, chunk//2)
                mask = freqs <= 3000
                xf = freqs[mask]
                mag_db = mag_db[mask]
                win.after(0, lambda x=xf, m=mag_db: draw_spectrum(x, m))
                time.sleep(0.05)
            except:
                break
        stream.stop_stream()
        stream.close()

    def draw_spectrum(xf, mag_db):
        spec_canvas.delete("all")
        w = spec_canvas.winfo_width()
        h = spec_canvas.winfo_height()
        if len(xf) < 2:
            return
        for f in [500, 1000, 1500, 2000, 2500, 3000]:
            x = f / 3000 * w
            spec_canvas.create_line(x, 0, x, h, fill="#333333", dash=(2,2))
        for db in [-60, -40, -20]:
            y = h - (db + 60)/60 * h
            spec_canvas.create_line(0, y, w, y, fill="#333333", dash=(2,2))
        points = []
        for i in range(len(xf)):
            x = i / (len(xf)-1) * w
            y = h - (mag_db[i] + 60)/60 * h
            y = max(0, min(h, y))
            points += [x, y]
        spec_canvas.create_line(points, fill="#00ff00", width=2)
        for db in [0, -20, -40, -60]:
            y = h - (db + 60)/60 * h
            spec_canvas.create_text(10, y, text=f"{db} dB", fill="white", anchor="w", font=("Arial", 8))

    def toggle_spectrum():
        nonlocal spectrum_active
        if spectrum_active:
            spectrum_active = False
            btn.config(text="START SPECTRUM", bg="#00ff88")
        else:
            spectrum_active = True
            btn.config(text="STOP SPECTRUM", bg="#ff0000")
            threading.Thread(target=spectrum_loop, daemon=True).start()

    btn = tk.Button(ctrl_frame, text="START SPECTRUM", command=toggle_spectrum, bg="#00ff88", fg="black", font=("Arial", 12, "bold"))
    btn.pack(side=tk.LEFT, padx=20)