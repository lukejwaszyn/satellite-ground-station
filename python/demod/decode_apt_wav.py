#!/usr/bin/env python3
"""
decode_apt_wav.py
APT decoder for WAV files (already FM demodulated)

This handles the case where you have audio from:
- SDR software that already did FM demod
- Online sample files
- Our synthetic test signal
"""

import numpy as np
from scipy import signal
from scipy.io import wavfile
import os
import json
from datetime import datetime

# APT Format Constants
APT_LINES_PER_SEC = 2
APT_PIXELS_PER_LINE = 2080
APT_SAMPLE_RATE = 20800


def am_demodulate(data):
    """Envelope detection via Hilbert transform."""
    analytic = signal.hilbert(data)
    envelope = np.abs(analytic)
    return envelope


def find_sync_pulses(data, sample_rate):
    """Find sync pulses using correlation."""
    samples_per_line = int(sample_rate / APT_LINES_PER_SEC)
    
    # Sync A pattern: 1040 Hz
    sync_duration = 0.005
    t_sync = np.arange(0, sync_duration, 1/sample_rate)
    sync_pattern = np.sin(2 * np.pi * 1040 * t_sync)
    sync_pattern = (sync_pattern > 0).astype(float)
    
    correlation = signal.correlate(data, sync_pattern, mode='valid')
    
    threshold = np.max(correlation) * 0.4
    peaks, _ = signal.find_peaks(correlation, height=threshold, distance=samples_per_line * 0.8)
    
    return peaks, samples_per_line


def decode_wav(wav_path, output_dir=None):
    """Decode APT image from WAV file."""
    
    print(f"Loading: {wav_path}")
    sample_rate, audio = wavfile.read(wav_path)
    
    # Convert to float
    if audio.dtype == np.int16:
        audio = audio.astype(np.float32) / 32767.0
    elif audio.dtype == np.int32:
        audio = audio.astype(np.float32) / 2147483647.0
    
    # Handle stereo
    if len(audio.shape) > 1:
        audio = audio[:, 0]
    
    print(f"  Sample rate: {sample_rate} Hz")
    print(f"  Duration: {len(audio)/sample_rate:.1f} seconds")
    print(f"  Samples: {len(audio):,}")
    
    # Resample to APT rate if needed
    if sample_rate != APT_SAMPLE_RATE:
        print(f"  Resampling {sample_rate} -> {APT_SAMPLE_RATE} Hz...")
        num_samples = int(len(audio) * APT_SAMPLE_RATE / sample_rate)
        audio = signal.resample(audio, num_samples)
        sample_rate = APT_SAMPLE_RATE
    
    # AM demodulation
    print("AM demodulating...")
    envelope = am_demodulate(audio)
    
    # Find sync pulses
    print("Finding sync pulses...")
    sync_positions, samples_per_line = find_sync_pulses(envelope, sample_rate)
    print(f"  Found {len(sync_positions)} sync pulses")
    
    # Fallback if few syncs found
    if len(sync_positions) < 5:
        print("  Using fixed line extraction...")
        num_lines = int(len(envelope) / samples_per_line)
        sync_positions = (np.arange(num_lines) * samples_per_line).astype(int)
    
    # Extract lines
    print("Extracting image lines...")
    lines = []
    for start in sync_positions:
        end = start + samples_per_line
        if end > len(envelope):
            break
        line = envelope[start:end]
        line_resampled = signal.resample(line, APT_PIXELS_PER_LINE)
        lines.append(line_resampled)
    
    image = np.array(lines)
    print(f"  Image shape: {image.shape}")
    
    # Normalize
    p_low, p_high = np.percentile(image, [2, 98])
    image = np.clip(image, p_low, p_high)
    image = ((image - p_low) / (p_high - p_low) * 255).astype(np.uint8)
    
    # Save
    if output_dir is None:
        output_dir = os.path.dirname(wav_path) or '.'
    
    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(wav_path))[0]
    png_path = os.path.join(output_dir, f"{base_name}_decoded.png")
    
    try:
        from PIL import Image
        img = Image.fromarray(image, mode='L')
        img.save(png_path)
    except ImportError:
        import matplotlib.pyplot as plt
        plt.imsave(png_path, image, cmap='gray')
    
    print(f"\nSaved: {png_path}")
    print(f"Size: {image.shape[1]} x {image.shape[0]} pixels")
    
    return png_path, image


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python decode_apt_wav.py <audio.wav> [output_dir]")
        sys.exit(1)
    
    wav_file = sys.argv[1]
    out_dir = sys.argv[2] if len(sys.argv) > 2 else None
    
    decode_wav(wav_file, out_dir)
