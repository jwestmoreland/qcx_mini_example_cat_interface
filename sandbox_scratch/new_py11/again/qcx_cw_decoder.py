# qcx_cw_decoder.py
# Independent CW decoder window with RFBitBanger-inspired improvements
# Features: adaptive noise/threshold, better dot/dash ratio, Farnsworth timing,
# live symbol building + timing display, noise rejection, larger symbol,
# prosigns, CW trainer with modes/custom text/audio tones

import tkinter as tk
from tkinter import ttk, scrolledtext
import pyaudio
import numpy as np
import threading
import time
import math
import random
from collections import deque

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
    win.geometry("850x800")
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

    # Decoded text
    text_frame = tk.Frame(win)
    text_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=15)
    text_area = scrolledtext.ScrolledText(text_frame, font=("Courier", 14), bg="#000000", fg="#00ff00")
    text_area.pack(fill=tk.BOTH, expand=True)

    # Controls
    ctrl_frame = tk.Frame(win, bg="#1a1a1a")
    ctrl_frame.pack(fill=tk.X, pady=20, padx=20)

    # Audio input
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

    # Threshold slider
    thresh_frame = tk.Frame(ctrl_frame, bg="#1a1a1a")
    thresh_frame.pack(fill=tk.X, pady=15)
    tk.Label(thresh_frame, text="Threshold:", fg="white", bg="#1a1a1a").pack(side=tk.LEFT, padx=20)
    threshold_var = tk.DoubleVar(value=20.0)
    tk.Scale(thresh_frame, from_=5, to=50, resolution=1, orient=tk.HORIZONTAL, variable=threshold_var, length=400).pack(side=tk.LEFT, padx=10, fill=tk.X, expand=True)

    # Farnsworth
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

    # CW Trainer
    trainer_frame = tk.Frame(ctrl_frame, bg="#1a1a1a")
    trainer_frame.pack(fill=tk.X, pady=15)

    tk.Label(trainer_frame, text="Trainer Mode:", fg="cyan", bg="#1a1a1a", font=("Arial", 12)).pack(side=tk.LEFT, padx=15)
    trainer_mode_var = tk.StringVar(value="Random Letters")
    ttk.Combobox(trainer_frame, textvariable=trainer_mode_var, 
                 values=["Random Letters", "Random Words", "QSO Phrases", "Numbers", "Prosigns", "Custom Text"], 
                 width=15).pack(side=tk.LEFT, padx=10)

    custom_text_var = tk.StringVar(value="CQ CQ DE TEST TEST K")
    custom_entry = tk.Entry(trainer_frame, textvariable=custom_text_var, width=30, font=("Arial", 12))
    custom_entry.pack(side=tk.LEFT, padx=10)

    trainer_wpm_var = tk.IntVar(value=20)
    tk.Label(trainer_frame, text="WPM:", fg="white", bg="#1a1a1a").pack(side=tk.LEFT, padx=10)
    tk.Spinbox(trainer_frame, from_=5, to=40, textvariable=trainer_wpm_var, width=5).pack(side=tk.LEFT, padx=5)

    trainer_play_var = tk.BooleanVar(value=True)
    tk.Checkbutton(trainer_frame, text="Play Audio Tones", variable=trainer_play_var, fg="white", bg="#1a1a1a").pack(side=tk.LEFT, padx=10)

    trainer_btn = tk.Button(trainer_frame, text="Start Trainer", 
                            command=lambda: threading.Thread(target=cw_trainer, daemon=True).start(),
                            bg="#ffaa00", fg="black", font=("Arial", 12))
    trainer_btn.pack(side=tk.LEFT, padx=10)

    chunk = 1024
    rate = 48000
    decoding = False

    # State
    element_times = deque(maxlen=50)
    noise_floor = deque(maxlen=100)
    key_state = False
    last_transition = time.time()
    current_symbol = ""
    last_char_time = time.time()
    current_tone = 700

    # Morse dictionary with prosigns
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
        '...---...': '<SOS>', '-.-': '<K>'
    }

    def decode_char():
        nonlocal current_symbol
        if current_symbol:
            char = MORSE_DICT.get(current_symbol, '?')
            text_area.insert(tk.END, char)
            text_area.see(tk.END)
            current_symbol = ""
            symbol_label.config(text="")

    def audio_decoder():
        nonlocal decoding, key_state, last_transition, last_char_time, current_tone

        try:
            name = device_var.get()
            idx = next(i for n, i in devices if n == name)
            stream = audio.open(format=pyaudio.paInt16, channels=1, rate=rate,
                                input=True, input_device_index=idx, frames_per_buffer=chunk)
        except Exception as e:
            win.after(0, lambda: messagebox.showerror("Audio Error", str(e)))
            return

        test_freqs = np.arange(400, 1101, 20)

        while decoding:
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
                current_tone = tone_freq

                dynamic_thresh = avg_noise * 10

                key_down = tone_mag > dynamic_thresh

                now = time.time()

                if key_down != key_state:
                    duration = now - last_transition
                    if duration > 0.01:
                        element_times.append(duration)

                    if key_down:
                        symbol_label.config(text=current_symbol + " [on]")
                        timing_label.config(text=f"{duration:.3f}s [start]")
                    else:
                        if element_times:
                            avg_dot = np.mean(element_times)
                            if duration < avg_dot * 1.8:
                                current_symbol += "."
                                timing_label.config(text=f"{duration:.3f}s [dot]")
                            else:
                                current_symbol += "-"
                                timing_label.config(text=f"{duration:.3f}s [dash]")
                            symbol_label.config(text=current_symbol)

                    key_state = key_down
                    last_transition = now
                    last_char_time = now

                if not key_down and current_symbol:
                    if (now - last_char_time) > (np.mean(element_times) * 3 if element_times else 0.3):
                        decode_char()
                        last_char_time = now
                        timing_label.config(text="char space")

                if not key_down and (now - last_transition) > 0.5:
                    if current_symbol:
                        decode_char()
                    spacing = np.mean(element_times) * 7 if element_times else 0.7
                    if farnsworth_var.get() and element_times:
                        avg_wpm = 1.2 / np.mean(element_times)
                        if avg_wpm < 18:
                            spacing *= (18 / avg_wpm)
                    if (now - last_transition) > spacing:
                        text_area.insert(tk.END, "  ")
                        text_area.see(tk.END)
                        timing_label.config(text="word space")

                if element_times:
                    avg = np.mean(element_times)
                    wpm = 1.2 / avg if avg > 0 else 0
                    win.after(0, lambda w=int(wpm): wpm_label.config(text=f"{w}"))

            except:
                continue

        stream.stop_stream()
        stream.close()

    def toggle_decoder():
        nonlocal decoding
        if decoding:
            decoding = False
            btn.config(text="START DECODER", bg="#00ff88")
        else:
            decoding = True
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
        if p:
            stream = p.open(format=pyaudio.paInt16, channels=1, rate=rate, output=True, frames_per_buffer=chunk)

        for char in text.upper():
            if char == ' ':
                time.sleep(0.7 / (wpm / 20.0))  # word space
            else:
                code = next((k for k, v in MORSE_DICT.items() if v == char), None)
                if code:
                    for symbol in code:
                        duration = 0.05 if symbol == '.' else 0.15  # relative dot/dash
                        if p:
                            tone = generate_tone(duration=duration * (20 / wpm))
                            stream.write(tone)
                        time.sleep(duration * (20 / wpm))
                        time.sleep(0.05 * (20 / wpm))  # inter-element
                time.sleep(0.15 * (20 / wpm))  # inter-character

            text_area.insert(tk.END, char)
            text_area.see(tk.END)
            time.sleep(0.05)  # slight pause for readability

        text_area.insert(tk.END, "\n=== TRAINER END ===\n\n")
        text_area.see(tk.END)

        if p:
            stream.stop_stream()
            stream.close()
            p.terminate()

    trainer_btn = tk.Button(ctrl_frame, text="Start Trainer", 
                            command=lambda: threading.Thread(target=cw_trainer, daemon=True).start(),
                            bg="#ffaa00", fg="black", font=("Arial", 12))
    trainer_btn.pack(pady=10)

    def on_closing():
        nonlocal decoding
        decoding = False
        win.destroy()

    win.protocol("WM_DELETE_WINDOW", on_closing)