# decode_mp3_morse_fft.py
# Standalone Morse decoder from MP3 files using FFT for tone detection
# Usage: python decode_mp3_morse_fft.py your_morse_file.mp3

import sys
import numpy as np
from pydub import AudioSegment
from collections import deque
import time
import io
import math
from collections import deque  # <-- THIS WAS MISSING - added here

# Full Morse dictionary (letters, numbers, prosigns, punctuation)
MORSE_DICT = {
    '.-': 'A', '-...': 'B', '-.-.': 'C', '-..': 'D', '.': 'E',
    '..-.': 'F', '--.': 'G', '....': 'H', '..': 'I', '.---': 'J',
    '-.-': 'K', '.-..': 'L', '--': 'M', '-.': 'N', '---': 'O',
    '.--.': 'P', '--.-': 'Q', '.-.': 'R', '...': 'S', '-': 'T',
    '..-': 'U', '...-': 'V', '.--': 'W', '-..-': 'X', '-.--': 'Y',
    '--..': 'Z', '.----': '1', '..---': '2', '...--': '3', '....-': '4',
    '.....': '5', '-....': '6', '--...': '7', '---..': '8', '----.': '9',
    '-----': '0',
    # Prosigns
    '.-.-.': '<AR>', '...-.-': '<SK>', '-...-': '<BT>', '-...-.-': 'BK',
    '-.--.': '<KN>', '.-...': '<AS>', '-.-...': '<CL>', '......': '<HH>',
    '...---...': '<SOS>', '-.-': '<K>',
    # Punctuation & symbols
    '.----.': '.', '--..--': ',', '..--..': '?', '-..-.': '/',
    '---...': ':', '-.-.-.': ';', '-.--.-': '(', '-.--.-': ')',
    '.-..-.': '"', '.----.': '\'', '-...-': '=', '.-.-.-': '+',
    '..--.-': '@', '----..': '$'
}

def load_mp3_to_samples(mp3_path, sample_rate=48000):
    audio = AudioSegment.from_mp3(mp3_path)
    audio = audio.set_frame_rate(sample_rate).set_channels(1).set_sample_width(2)
    raw_data = audio.raw_data
    samples = np.frombuffer(raw_data, dtype=np.int16).astype(np.float32)
    print(f"Loaded MP3: {len(samples)} samples at {sample_rate} Hz")
    return samples

def fft_tone_detect(chunk, sample_rate, target_freq=700, freq_range=100):
    """
    Use FFT to detect presence of tone around target_freq
    Returns: magnitude of the strongest tone in range, dominant freq
    """
    N = len(chunk)
    fft_result = np.fft.rfft(chunk)
    freqs = np.fft.rfftfreq(N, 1/sample_rate)
    
    # Find indices around target_freq
    idx_low = np.searchsorted(freqs, target_freq - freq_range)
    idx_high = np.searchsorted(freqs, target_freq + freq_range)
    
    if idx_high > len(fft_result):
        idx_high = len(fft_result)
    
    mags = np.abs(fft_result[idx_low:idx_high])
    if len(mags) == 0:
        return 0.0, target_freq
    
    max_idx = np.argmax(mags)
    peak_mag = mags[max_idx]
    peak_freq = freqs[idx_low + max_idx]
    
    return peak_mag, peak_freq

def decode_morse_from_mp3(mp3_path, target_freq=700, chunk_size=512, sample_rate=48000):
    samples = load_mp3_to_samples(mp3_path, sample_rate)
    
    # Parameters (tuned for 17 wpm ~ 0.088s dot, 0.264s dash)
    noise_floor = deque(maxlen=200)
    element_times = deque(maxlen=50)
    key_state = False
    last_transition = 0.0
    current_symbol = ""
    last_char_time = 0.0
    decoded_text = ""
    sim_time = 0.0
    chunk_duration = chunk_size / sample_rate
    tone_start_time = 0.0

    for i in range(0, len(samples), chunk_size):
        chunk = samples[i:i+chunk_size]
        if len(chunk) < chunk_size // 2:
            break

        mag, freq = fft_tone_detect(chunk, sample_rate, target_freq, freq_range=80)

        # Estimate noise floor from nearby bins (rough)
        noise_mag = np.mean(np.abs(np.fft.rfft(chunk))[:10])  # low freq bins as proxy
        noise_floor.append(noise_mag)
        avg_noise = np.mean(noise_floor) if noise_floor else noise_mag

        # Dynamic threshold (adjust multiplier as needed)
        dynamic_thresh = avg_noise * 3.5  # 10-12 dB above noise
        key_down = mag > dynamic_thresh

        sim_time += chunk_duration

        if key_down:
            if not key_state:
                tone_start_time = sim_time
            key_state = True
        else:
            if key_state:
                duration = sim_time - tone_start_time
                if duration > 0.02:  # minimum element time
                    element_times.append(duration)
                    avg_dot = np.mean(element_times) if element_times else 0.1
                    if duration < avg_dot * 1.6:  # tuned ratio
                        current_symbol += "."
                        print(f"[{sim_time:.2f}s] Added dot (dur: {duration:.3f}s, avg: {avg_dot:.3f}s)")
                    else:
                        current_symbol += "-"
                        print(f"[{sim_time:.2f}s] Added dash (dur: {duration:.3f}s, avg: {avg_dot:.3f}s)")
                key_state = False

        # Inter-character space (very sensitive)
        if not key_down and current_symbol:
            silence_time = sim_time - last_char_time
            char_space_threshold = max(0.02, np.mean(element_times) * 0.8 if element_times else 0.02)
            if silence_time > char_space_threshold:
                if current_symbol in MORSE_DICT:
                    char = MORSE_DICT[current_symbol]
                    decoded_text += char
                    print(f"[{sim_time:.2f}s] Decoded: {char} (symbol: {current_symbol})")
                else:
                    print(f"[{sim_time:.2f}s] No match for {current_symbol} → ?")
                    decoded_text += '?'
                current_symbol = ""
                last_char_time = sim_time

        # Word space
        if not key_down and (sim_time - last_transition) > 0.6:
            decoded_text += " "
            print(f"[{sim_time:.2f}s] Word space")
            last_transition = sim_time

    print("\n" + "="*60)
    print("Final decoded text:")
    print(decoded_text)
    print("="*60)

    with open("decoded_morse_fft.txt", "w", encoding="utf-8") as f:
        f.write(decoded_text)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python decode_mp3_morse_fft.py your_file.mp3")
        sys.exit(1)

    mp3_file = sys.argv[1]
    decode_morse_from_mp3(mp3_file, target_freq=680)  # change 600 to your actual tone if different