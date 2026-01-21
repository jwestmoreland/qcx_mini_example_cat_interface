# decode_mp3_morse_goertzel.py
# Standalone Morse decoder from MP3 files using Goertzel (non-FFT version)
# Latest version - improved word spacing, prosign handling, clean output

import sys
import numpy as np
from pydub import AudioSegment
from collections import deque
import time
import math
import statistics

# Full Morse dictionary with prosigns and punctuation/symbols
MORSE_DICT = {
    '.-': 'A', '-...': 'B', '-.-.': 'C', '-..': 'D', '.': 'E',
    '..-.': 'F', '--.': 'G', '....': 'H', '..': 'I', '.---': 'J',
    '-.-': 'K', '.-..': 'L', '--': 'M', '-.': 'N', '---': 'O',
    '.--.': 'P', '--.-': 'Q', '.-.': 'R', '...': 'S', '-': 'T',
    '..-': 'U', '...-': 'V', '.--': 'W', '-..-': 'X', '-.--': 'Y',
    '--..': 'Z', '.----': '1', '..---': '2', '...--': '3', '....-': '4',
    '.....': '5', '-....': '6', '--...': '7', '---..': '8', '----.': '9',
    '-----': '0',
    # Prosigns (prioritize these)
    '.-.-.': '<AR>', '...-.-': '<SK>', '-...-': '<BT>', '-...-.-': 'BK',
    '-.--.': '<KN>', '.-...': '<AS>', '-.-...': '<CL>', '......': '<HH>',
    '...---...': '<SOS>', '-.-': '<K>',
    # Punctuation and symbols
    '.----.': '.', '--..--': ',', '..--..': '?', '-..-.': '/', '---...': ':',
    '-.-.-.': ';', '-.--.-': '(', '-.--.-': ')', '.-..-.': '"', '.----.': '\'',
    '-...-': '=', '.-.-.-': '+', '..--.-': '@', '----..': '$'
}

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

def decode_morse_from_mp3(mp3_path, target_freq=600, chunk_size=1024, sample_rate=48000):
    audio = AudioSegment.from_mp3(mp3_path)
    audio = audio.set_frame_rate(sample_rate).set_channels(1).set_sample_width(2)
    raw_data = audio.raw_data
    samples = np.frombuffer(raw_data, dtype=np.int16).astype(np.float32)

    print(f"Loaded MP3: {len(samples)} samples at {sample_rate} Hz")

    test_freqs = np.arange(400, 1101, 20)
    noise_floor = deque(maxlen=100)
    element_times = deque(maxlen=50)
    key_state = False
    last_transition = 0.0
    current_symbol = ""
    last_char_time = 0.0
    decoded_text = ""
    last_word_end = 0.0
    sim_time = 0.0
    chunk_duration = chunk_size / sample_rate

    for i in range(0, len(samples), chunk_size):
        chunk = samples[i:i+chunk_size]
        if len(chunk) < chunk_size // 2:
            break

        mags = [goertzel(chunk, sample_rate, f) for f in test_freqs]
        max_idx = np.argmax(mags)
        tone_freq = test_freqs[max_idx]
        tone_mag = mags[max_idx]

        noise_mag = np.mean(mags[:5] + mags[-5:])
        noise_floor.append(noise_mag)
        avg_noise = np.mean(noise_floor) if noise_floor else noise_mag

        dynamic_thresh = avg_noise * 3.0
        key_down = tone_mag > dynamic_thresh

        sim_time += chunk_duration

        if key_down != key_state:
            duration = sim_time - last_transition
            if duration > 0.01:
                element_times.append(duration)

            if key_down:
                print(f"Key down at {sim_time:.2f}s, freq: {tone_freq:.0f} Hz, mag: {tone_mag:.2f}")
            else:
                if element_times:
                    avg_dot = statistics.median(element_times) if element_times else 0.1
                    if duration < avg_dot * 1.4:
                        current_symbol += "."
                    else:
                        current_symbol += "-"

            key_state = key_down
            last_transition = sim_time
            last_char_time = sim_time

        if not key_down and current_symbol:
            silence_time = sim_time - last_char_time
            char_space_threshold = max(0.02, statistics.median(element_times) * 0.6 if element_times else 0.02)
# To this (add space only after prosign or word space):
            if silence_time > char_space_threshold:
                decoded_symbol = current_symbol
                print(f"Inter-character space detected ({silence_time:.3f}s > {char_space_threshold:.3f}s) - decoding: {decoded_symbol} (length: {len(decoded_symbol)})")
                if len(decoded_symbol) > 30:
                    print(f"Symbol too long ({len(decoded_symbol)} symbols) - resetting and inserting '?'")
                    decoded_text += '?'
                    current_symbol = ""
                else:
                    char = MORSE_DICT.get(decoded_symbol, '?')
                    if char == '?' and all(c == '.' for c in decoded_symbol):
                        if len(decoded_symbol) == 1:
                            char = 'E'
                        elif len(decoded_symbol) == 4:
                            char = 'H'
                        elif len(decoded_symbol) == 5:
                            char = '5'
                    decoded_text += char
                    if char in ['<AR>', '<SK>', '<BT>', '<KN>', '<AS>', '<CL>', '<HH>', '<SOS>', '<K>', 'BK']:  # Prosigns
                        decoded_text += " "  # Add space after prosign
                    print(f"Decoded: {char} (symbol: {decoded_symbol})")
                    current_symbol = ""
                last_char_time = sim_time

# Word space detection (lower threshold for better spacing)
        if not key_down and (sim_time - last_transition) > 0.35:
            decoded_text += " "
            print(f"Word space at {sim_time:.2f}s")
            last_transition = sim_time

    # Final cleanup: remove multiple spaces, trim
    decoded_text = ' '.join(decoded_text.split()).strip()

    print("\nFinal decoded text:")
    print(decoded_text)
    with open("decoded_morse_goertzel-3.txt", "w", encoding="utf-8") as f:
        f.write(decoded_text)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python decode_mp3_morse_goertzel.py your_file.mp3")
        sys.exit(1)

    mp3_file = sys.argv[1]
    decode_morse_from_mp3(mp3_file, target_freq=700)