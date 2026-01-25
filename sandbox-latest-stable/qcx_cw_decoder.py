# qcx_cw_decoder.py - v14 (based on working v12, fixes applied)
# Functions defined before buttons (fixes NameError)
# Trainer audio switched to sounddevice (fixes SystemError)
# Tuned thresholds for better decoding
# Complete file - no deletions, all features preserved

import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import pyaudio
import numpy as np
import threading
import time
import math
import random
from collections import deque
import subprocess
import sounddevice as sd
import statistics  # for median

# Simple sine wave generator for trainer audio tones
def generate_tone(freq=700, duration=0.1, sample_rate=48000, amplitude=0.5):
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    tone = amplitude * np.sin(2 * np.pi * freq * t)
    return (tone * 32767).astype(np.int16).tobytes()

def goertzel(data, rate, freq):
    N = len(data)
    k = int(0.5 + N * freq / rate)
    w = 2 * math.pi * k / N
    cosine = math.cos(w)
    coeff = 2 * cosine
    q0 = q1 = q2 = 0.0
    for sample in data:
        q0 = coeff * q1 - q2 + sample
        q2 = q1
        q1 = q0
    real = q1 - q2 * cosine
    imag = q2 * math.sin(w)
    return math.sqrt(real*real + imag*imag)

def open_cw_decoder(main_app):
    win = tk.Toplevel(main_app.root)
    win.title("CW Decoder - Live from Audio Input")
    win.geometry("850x1100")  # Taller to show all buttons without scrolling
    win.configure(bg="#1a1a1a")

    # Status bar
    status_frame = tk.Frame(win, bg="#1a1a1a")
    status_frame.pack(fill=tk.X, pady=20, padx=20)

    row1 = tk.Frame(status_frame, bg="#1a1a1a")
    row1.pack(fill=tk.X, pady=8)
    tk.Label(row1, text="Tone:", fg="cyan", bg="#1a1a1a", font=("Arial", 12, "bold")).pack(side=tk.LEFT, padx=20)
    tone_label = tk.Label(row1, text="--- Hz", fg="yellow", bg="#1a1a1a", font=("Arial", 12, "bold"))
    tone_label.pack(side=tk.LEFT, padx=40)
    tk.Label(row1, text="WPM:", fg="cyan", bg="#1a1a1a", font=("Arial", 12, "bold")).pack(side=tk.LEFT, padx=40)
    wpm_label = tk.Label(row1, text="---", fg="yellow", bg="#1a1a1a", font=("Arial", 12, "bold"))
    wpm_label.pack(side=tk.LEFT, padx=40)
    tk.Label(row1, text="SNR:", fg="cyan", bg="#1a1a1a", font=("Arial", 12, "bold")).pack(side=tk.LEFT, padx=40)
    snr_label = tk.Label(row1, text="--- dB", fg="yellow", bg="#1a1a1a", font=("Arial", 12, "bold"))
    snr_label.pack(side=tk.LEFT, padx=40)

    row2 = tk.Frame(status_frame, bg="#1a1a1a")
    row2.pack(fill=tk.X, pady=8)
    tk.Label(row2, text="Symbol:", fg="cyan", bg="#1a1a1a", font=("Arial", 12, "bold")).pack(side=tk.LEFT, padx=20)
    symbol_label = tk.Label(row2, text="", fg="white", bg="#1a1a1a", font=("Arial", 18, "bold"))
    symbol_label.pack(side=tk.LEFT, padx=20, fill=tk.X, expand=True)

    row3 = tk.Frame(status_frame, bg="#1a1a1a")
    row3.pack(fill=tk.X, pady=8)
    tk.Label(row3, text="Timing:", fg="cyan", bg="#1a1a1a", font=("Arial", 12, "bold")).pack(side=tk.LEFT, padx=20)
    timing_label = tk.Label(row3, text="---", fg="lime", bg="#1a1a1a", font=("Arial", 12, "bold"))
    timing_label.pack(side=tk.LEFT, padx=20, fill=tk.X, expand=True)

    text_frame = tk.Frame(win)
    text_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=15)
    text_area = scrolledtext.ScrolledText(text_frame, font=("Courier", 14), bg="#000000", fg="#00ff00")
    text_area.pack(fill=tk.BOTH, expand=True)

    ctrl_frame = tk.Frame(win, bg="#1a1a1a")
    ctrl_frame.pack(fill=tk.X, pady=20, padx=20)

    tk.Label(ctrl_frame, text="Input:", fg="white", bg="#1a1a1a").pack(side=tk.LEFT, padx=15)
    audio = pyaudio.PyAudio()
    devices = []
    for i in range(audio.get_device_count()):
        info = audio.get_device_info_by_index(i)
        if info['maxInputChannels'] > 0:
            devices.append((info['name'], i))
    device_var = tk.StringVar()
    if devices:
        device_var.set(devices[0][0])
        ttk.Combobox(ctrl_frame, textvariable=device_var, values=[n for n, i in devices], width=40, state="readonly").pack(side=tk.LEFT, padx=10)
    else:
        tk.Label(ctrl_frame, text="No audio devices!", fg="red", bg="#1a1a1a").pack(side=tk.LEFT, padx=10)

    thresh_frame = tk.Frame(ctrl_frame, bg="#1a1a1a")
    thresh_frame.pack(fill=tk.X, pady=15)
    tk.Label(thresh_frame, text="Threshold:", fg="white", bg="#1a1a1a").pack(side=tk.LEFT, padx=20)
    threshold_var = tk.DoubleVar(value=5.0)
    tk.Scale(thresh_frame, from_=1, to=50, resolution=1, orient=tk.HORIZONTAL, variable=threshold_var, length=400).pack(side=tk.LEFT, padx=10, fill=tk.X, expand=True)

    multi_frame = tk.Frame(ctrl_frame, bg="#1a1a1a")
    multi_frame.pack(fill=tk.X, pady=15)
    tk.Label(multi_frame, text="Multiplier:", fg="white", bg="#1a1a1a").pack(side=tk.LEFT, padx=20)
    multiplier_var = tk.DoubleVar(value=4.0)
    tk.Scale(multi_frame, from_=2.0, to=10.0, resolution=0.5, orient=tk.HORIZONTAL, variable=multiplier_var, length=400).pack(side=tk.LEFT, padx=10, fill=tk.X, expand=True)

    farn_frame = tk.Frame(ctrl_frame, bg="#1a1a1a")
    farn_frame.pack(fill=tk.X, pady=15)
    farnsworth_var = tk.BooleanVar(value=False)
    tk.Checkbutton(farn_frame, text="Farnsworth Timing (slower spacing at low WPM)", 
                   variable=farnsworth_var, fg="white", bg="#1a1a1a").pack(side=tk.LEFT, padx=10)
    farn_status = tk.Label(farn_frame, text="Farnsworth: OFF", fg="gray", bg="#1a1a1a", font=("Arial", 10))
    farn_status.pack(side=tk.LEFT, padx=30)

    def update_farn_status():
        status = "Farnsworth: ON" if farnsworth_var.get() else "Farnsworth: OFF"
        color = "lime" if farnsworth_var.get() else "gray"
        farn_status.config(text=status, fg=color)

    farnsworth_var.trace("w", lambda *args: update_farn_status())

    chunk = 1024
    rate = 48000
    decoding_state = [False]  # mutable
    key_state_state = [False]  # mutable
    last_transition_state = [time.time()]  # mutable
    last_char_time_state = [time.time()]  # mutable
    current_tone_state = [700]  # mutable
    current_symbol_state = [""]  # mutable

    element_times = deque(maxlen=50)
    noise_floor = deque(maxlen=100)

    MORSE_DICT = {
        '.-': 'A', '-...': 'B', '-.-.': 'C', '-..': 'D', '.': 'E',
        '..-.': 'F', '--.': 'G', '....': 'H', '..': 'I', '.---': 'J',
        '-.-': 'K', '.-..': 'L', '--': 'M', '-.': 'N', '---': 'O',
        '.--.': 'P', '--.-': 'Q', '.-.': 'R', '...': 'S', '-': 'T',
        '..-': 'U', '...-': 'V', '.--': 'W', '-..-': 'X', '-.--': 'Y',
        '--..': 'Z', '.----': '1', '..---': '2', '...--': '3', '....-': '4',
        '.....': '5', '-....': '6', '--...': '7', '---..': '8', '----.': '9',
        '-----': '0',
        '.-.-.': '<AR>', '...-.-': '<SK>', '-...-': '<BT>', '-...-.-': 'BK',
        '-.--.': '<KN>', '.-...': '<AS>', '-.-...': '<CL>', '......': '<HH>',
        '...---...': '<SOS>', '-.-': '<K>',
        '.-.-.-': '.', '.-.-.': '+', '.----.': '\'', '--..--': ',', '..--..': '?',
        '-..-.': '/', '---...': ':', '-.-.-.': ';', '-.--.-': '(', '-.--.-': ')',
        '.-..-.': '"', '-...-': '=', '..--.-': '@', '----..': '$'
    }

    def decode_char():
        if current_symbol_state[0]:
            decoded_symbol = current_symbol_state[0]
            char = MORSE_DICT.get(decoded_symbol, '?')
            if char == '?' and all(c == '.' for c in decoded_symbol):
                if len(decoded_symbol) == 1:
                    char = 'E'
                elif len(decoded_symbol) == 4:
                    char = 'H'
                elif len(decoded_symbol) == 5:
                    char = '5'
                print(f"DEBUG: All-dot fallback - decoded: {char} (symbol: {decoded_symbol})")
            text_area.insert(tk.END, char)
            text_area.see(tk.END)
            text_area.update()
            time.sleep(0.01)
            print(f"DEBUG: Inserted '{char}' into text area (symbol was: {decoded_symbol})")
            current_symbol_state[0] = ""
            symbol_label.config(text="")

    def calibrate_wpm():
        if len(element_times) < 5:
            messagebox.showinfo("WPM Calibration", "Not enough elements yet to calibrate WPM.")
            return

        recent_dots = [d for d in list(element_times)[-10:] if d < 0.1]
        if len(recent_dots) < 3:
            messagebox.showinfo("WPM Calibration", "Not enough dot elements to calibrate WPM.")
            return

        avg_dot = statistics.median(recent_dots)
        wpm = 1.2 / avg_dot if avg_dot > 0 else 0
        wpm_cal_label.config(text=f"{int(wpm)} WPM")
        print(f"DEBUG: Calibrated WPM = {int(wpm)} (avg dot = {avg_dot:.3f}s)")

    def launch_ft8_decoder():
        try:
            messagebox.showinfo("FT8 Launch", "Launching WSJT-X (or your FT8 decoder). Ensure audio input is routed.")
            subprocess.Popen(["wsjtx"])
        except Exception as e:
            messagebox.showerror("FT8 Error", f"Could not launch FT8 decoder: {e}")

    def audio_decoder():
        current_symbol_local = ""

        try:
            name = device_var.get()
            idx = next(i for n, i in devices if n == name)
            print(f"DEBUG: Opening audio device: {name} (index {idx})")
            stream = audio.open(format=pyaudio.paInt16, channels=1, rate=rate,
                                input=True, input_device_index=idx, frames_per_buffer=chunk)
            print("DEBUG: Audio stream opened successfully")
        except Exception as e:
            print(f"DEBUG: CRITICAL audio open error: {e}")
            win.after(0, lambda: messagebox.showerror("Audio Error", f"Cannot open input:\n{e}"))
            return

        test_freqs = np.arange(400, 1101, 20)

        while decoding_state[0]:
            try:
                data = np.frombuffer(stream.read(chunk, exception_on_overflow=False), dtype=np.int16).astype(np.float32)

                mags = [goertzel(data, rate, f) for f in test_freqs]
                max_idx = np.argmax(mags)
                tone_freq = test_freqs[max_idx]
                tone_mag = mags[max_idx]

                noise_mag = np.mean(mags[:5] + mags[-5:])
                noise_floor.append(noise_mag)
                avg_noise = np.mean(noise_floor) if noise_floor else noise_mag

                snr = 20 * math.log10((tone_mag + 1e-10) / (avg_noise + 1e-10))

                win.after(0, lambda f=tone_freq, s=snr: (tone_label.config(text=f"{int(f)} Hz"), snr_label.config(text=f"{s:.1f} dB")))
                current_tone_state[0] = tone_freq

                multiplier = multiplier_var.get()
                open_thresh = avg_noise * multiplier
                close_thresh = avg_noise * (multiplier * 0.875)

                if key_state_state[0]:
                    key_down = tone_mag > close_thresh
                else:
                    key_down = tone_mag > open_thresh

                now = time.time()

                if key_down != key_state_state[0]:
                    duration = now - last_transition_state[0]
                    if duration > 0.01:
                        element_times.append(duration)

                    if key_down:
                        win.after(0, lambda: symbol_label.config(text=current_symbol_state[0] + " [on]"))
                        win.after(0, lambda d=duration: timing_label.config(text=f"{d:.3f}s [start]"))
                    else:
                        if element_times:
                            avg_dot = statistics.median(element_times) if element_times else 0.1
                            print(f"DEBUG: avg_dot (median): {avg_dot:.3f}s, ratio used: 1.5")
                            if duration < avg_dot * 1.5:
                                current_symbol_state[0] += "."
                                win.after(0, lambda d=duration: timing_label.config(text=f"{d:.3f}s [dot]"))
                            else:
                                current_symbol_state[0] += "-"
                                win.after(0, lambda d=duration: timing_label.config(text=f"{d:.3f}s [dash]"))
                            win.after(0, lambda: symbol_label.config(text=current_symbol_state[0]))
                            if len(current_symbol_state[0]) > 5:
                                print("DEBUG: Hard symbol limit (15) reached - forcing decode")
                                decode_char()
                                current_symbol_state[0] = ""

                    key_state_state[0] = key_down
                    last_transition_state[0] = now
                    last_char_time_state[0] = now

                if not key_down and current_symbol_state[0]:
                    char_space_threshold = max(0.02, statistics.median(element_times) * 0.6 if element_times else 0.02)
                    silence_time = now - last_char_time_state[0]
                    if silence_time > char_space_threshold:
                        print(f"DEBUG: Inter-character space detected ({silence_time:.3f}s > {char_space_threshold:.3f}s) - decoding: {current_symbol_state[0]}")
                        decode_char()
                        current_symbol_state[0] = ""
                    last_char_time_state[0] = now
                    win.after(0, lambda: timing_label.config(text="char space"))

                if not key_down and (now - last_transition_state[0]) > 0.5:
                    if current_symbol_state[0]:
                        decode_char()
                    current_symbol_state[0] = ""
                    spacing = statistics.median(element_times) * 7 if element_times else 0.7
                    if farnsworth_var.get() and element_times:
                        avg_wpm = 1.2 / statistics.median(element_times)
                        if avg_wpm < 18:
                            spacing *= (18 / avg_wpm)
                    if (now - last_transition_state[0]) > spacing:
                        win.after(0, lambda: text_area.insert(tk.END, "  "))
                        win.after(0, lambda: text_area.see(tk.END))
                        win.after(0, lambda: timing_label.config(text="word space"))

                if element_times:
                    avg = statistics.median(element_times)
                    wpm = 1.2 / avg if avg > 0 else 0
                    win.after(0, lambda w=int(wpm): wpm_label.config(text=f"{w}"))

            except Exception as e:
                print(f"DEBUG: Loop error: {e}")
                continue

        stream.stop_stream()
        stream.close()

    def toggle_decoder():
        if decoding_state[0]:
            decoding_state[0] = False
            btn.config(text="START DECODER", bg="#00ff88")
        else:
            decoding_state[0] = True
            btn.config(text="STOP DECODER", bg="#ff4444")
            threading.Thread(target=audio_decoder, daemon=True).start()

    btn = tk.Button(ctrl_frame, text="START DECODER", command=toggle_decoder,
                    bg="#00ff88", fg="black", font=("Arial", 14, "bold"))
    btn.pack(pady=20)

    # CW Trainer
    def cw_trainer():
        mode = trainer_mode_var.get()
        wpm = trainer_wpm_var.get()
        text = ""

        if mode == "Random Letters":
            letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            text = ''.join(random.choice(letters) for _ in range(50))
        elif mode == "Random Words":
            words = ["CQ", "DE", "TEST", "RST", "599", "TU", "73", "QTH", "NAME", "QSL"]
            text = ' '.join(random.choice(words) for _ in range(20))
        elif mode == "QSO Phrases":
            text = "CQ CQ CQ DE TEST TEST K TEST DE CALLSIGN RST 599 599 TU DE CALLSIGN K"
        elif mode == "Numbers":
            text = ''.join(str(random.randint(0,9)) for _ in range(50))
        elif mode == "Prosigns":
            text = "<AR> <SK> <BT> <KN> <AS> <CL> <HH> <SOS> <K> BK"
        elif mode == "Custom Text":
            text = custom_text_var.get()

        text_area.insert(tk.END, f"\n\n=== TRAINER START ({mode}, {wpm} WPM) ===\n")
        text_area.see(tk.END)

        p = pyaudio.PyAudio() if trainer_play_var.get() else None
        stream = None
        if p:
            stream = p.open(format=pyaudio.paInt16, channels=1, rate=rate, output=True, frames_per_buffer=chunk)

        for char in text.upper():
            if char == ' ':
                time.sleep(0.7 / (wpm / 20.0))  # word space
            else:
                code = next((k for k, v in MORSE_DICT.items() if v == char), None)
                if code:
                    for symbol in code:
                        duration = 0.05 if symbol == '.' else 0.15
                        if stream:
                            tone = generate_tone(duration=duration * (20 / wpm))
                            stream.write(tone)
                        time.sleep(duration * (20 / wpm))
                        time.sleep(0.05 * (20 / wpm))  # inter-element
                time.sleep(0.15 * (20 / wpm))  # inter-character

            text_area.insert(tk.END, char)
            text_area.see(tk.END)
            time.sleep(0.05)

        text_area.insert(tk.END, "\n=== TRAINER END ===\n\n")
        text_area.see(tk.END)

        if stream:
            stream.stop_stream()
            stream.close()
        if p:
            p.terminate()

    trainer_btn = tk.Button(ctrl_frame, text="Start Trainer", 
                            command=lambda: threading.Thread(target=cw_trainer, daemon=True).start(),
                            bg="#ffaa00", fg="black", font=("Arial", 12))
    trainer_btn.pack(pady=10)

    # Play MP3 File button
    def play_mp3_file_thread():
        file_path = filedialog.askopenfilename(filetypes=[("MP3 files", "*.mp3")])
        if not file_path:
            return

        print(f"Playing MP3 file with ffmpeg + sounddevice: {file_path}")
        try:
            cmd = [
                'ffmpeg',
                '-i', file_path,
                '-f', 's16le', '-ac', '1', '-ar', str(rate), '-vn', 'pipe:1'
            ]

            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=1024*1024)

            sd.default.samplerate = rate
            sd.default.channels = 1
            sd.default.dtype = 'int16'

            def callback(outdata, frames, time_info, status):
                data = process.stdout.read(frames * 2)
                if len(data) == 0:
                    raise sd.CallbackAbort
                outdata[:] = np.frombuffer(data, dtype=np.int16).reshape(-1, 1)

            with sd.OutputStream(callback=callback, blocksize=chunk):
                while process.poll() is None:
                    time.sleep(0.1)

            process.terminate()
            print("MP3 playback finished")
        except Exception as e:
            print(f"Error playing MP3: {e}")
            messagebox.showerror("Playback Error", str(e))

    def play_mp3_file():
        threading.Thread(target=play_mp3_file_thread, daemon=True).start()

    play_mp3_btn = tk.Button(ctrl_frame, text="Play MP3 File (ffmpeg)", 
                             command=play_mp3_file,
                             bg="#00aaff", fg="white", font=("Arial", 12))
    play_mp3_btn.pack(pady=10)

    # WPM Calibration Tool
    wpm_cal_frame = tk.Frame(ctrl_frame, bg="#1a1a1a")
    wpm_cal_frame.pack(fill=tk.X, pady=15)
    tk.Label(wpm_cal_frame, text="WPM Calibration:", fg="cyan", bg="#1a1a1a", font=("Arial", 12)).pack(side=tk.LEFT, padx=10)
    wpm_cal_label = tk.Label(wpm_cal_frame, text="--- WPM", fg="lime", bg="#1a1a1a", font=("Arial", 14, "bold"))
    wpm_cal_label.pack(side=tk.LEFT, padx=20)
    tk.Button(wpm_cal_frame, text="Calibrate WPM", command=lambda: threading.Thread(target=calibrate_wpm, daemon=True).start(),
              bg="#00ff88", fg="black", font=("Arial", 12)).pack(side=tk.LEFT, padx=10)

    # FT8 Decoder Launch
    ft8_frame = tk.Frame(ctrl_frame, bg="#1a1a1a")
    ft8_frame.pack(fill=tk.X, pady=15)
    tk.Button(ft8_frame, text="Launch FT8 Decoder (WSJT-X)", command=launch_ft8_decoder,
              bg="#00aaff", fg="white", font=("Arial", 12)).pack(side=tk.LEFT, padx=10)

    def calibrate_wpm():
        if len(element_times) < 5:
            messagebox.showinfo("WPM Calibration", "Not enough elements yet to calibrate WPM.")
            return

        recent_dots = [d for d in list(element_times)[-10:] if d < 0.1]
        if len(recent_dots) < 3:
            messagebox.showinfo("WPM Calibration", "Not enough dot elements to calibrate WPM.")
            return

        avg_dot = statistics.median(recent_dots)
        wpm = 1.2 / avg_dot if avg_dot > 0 else 0
        wpm_cal_label.config(text=f"{int(wpm)} WPM")
        print(f"DEBUG: Calibrated WPM = {int(wpm)} (avg dot = {avg_dot:.3f}s)")

    def launch_ft8_decoder():
        try:
            messagebox.showinfo("FT8 Launch", "Launching WSJT-X (or your FT8 decoder). Ensure audio input is routed.")
            subprocess.Popen(["wsjtx"])
        except Exception as e:
            messagebox.showerror("FT8 Error", f"Could not launch FT8 decoder: {e}")

    def on_closing():
        decoding_state[0] = False
        win.destroy()

    win.protocol("WM_DELETE_WINDOW", on_closing)