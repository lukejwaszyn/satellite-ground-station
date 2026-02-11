#!/usr/bin/env python3
"""
decode_apt.py
Satellite Ground Station - APT Image Decoder

Decodes NOAA APT weather satellite images from raw I/Q captures.

Signal chain:
    Raw I/Q (137 MHz centered, 2.4 MHz sample rate)
    → FM Demodulation (quadrature discriminator)
    → Lowpass Filter (17 kHz cutoff)
    → Resample to 20800 Hz
    → AM Demodulation (envelope detection)
    → Sync Detection (find line boundaries)
    → Image Reconstruction (2080 pixels/line)
    → PNG Output

Author: Luke Waszyn
Date: February 2026
"""

import numpy as np
from scipy import signal
from scipy.io import loadmat, wavfile
import os
import json
from datetime import datetime

# APT Format Constants
APT_LINES_PER_SEC = 2
APT_PIXELS_PER_LINE = 2080
APT_CARRIER_FREQ = 2400  # Hz
APT_SAMPLE_RATE = 20800  # Hz (4 samples per pixel at 2 lines/sec)

# Sync pulse pattern (approximate - 7 cycles of specific frequency)
SYNC_A_FREQ = 1040  # Hz - Sync A (channel A start)
SYNC_B_FREQ = 832   # Hz - Sync B (channel B start)


def load_iq(filepath):
    """
    Load I/Q data from file.
    Supports .mat (MATLAB) and .bin (raw binary) formats.
    
    Returns: iq_data (complex), sample_rate
    """
    ext = os.path.splitext(filepath)[1].lower()
    
    if ext == '.mat':
        # MATLAB format from our capture scripts
        data = loadmat(filepath)
        
        # Try common variable names
        if 'x' in data:
            iq = data['x'].flatten()
        elif 'iq' in data:
            iq = data['iq'].flatten()
        else:
            # Find first complex array
            for key, val in data.items():
                if not key.startswith('_') and np.iscomplexobj(val):
                    iq = val.flatten()
                    break
            else:
                raise ValueError("No I/Q data found in .mat file")
        
        # Get sample rate from metadata if available
        if 'meta' in data:
            meta = data['meta']
            if hasattr(meta, 'dtype') and 'Fs' in meta.dtype.names:
                fs = float(meta['Fs'][0][0])
            else:
                fs = 2.4e6  # Default
        elif 'Fs' in data:
            fs = float(data['Fs'].flatten()[0])
        else:
            fs = 2.4e6  # Default RTL-SDR rate
            
        return iq.astype(np.complex64), fs
    
    elif ext == '.bin':
        # Raw binary: interleaved float32 I/Q
        raw = np.fromfile(filepath, dtype=np.float32)
        iq = raw[0::2] + 1j * raw[1::2]
        return iq.astype(np.complex64), 2.4e6  # Assume default rate
    
    else:
        raise ValueError(f"Unsupported file format: {ext}")


def fm_demodulate(iq):
    """
    FM demodulation using quadrature discriminator.
    
    d/dt(phase) = instantaneous frequency
    
    For discrete samples:
    freq[n] = angle(iq[n] * conj(iq[n-1]))
    """
    # Quadrature discriminator
    # Multiply each sample by conjugate of previous sample
    # Phase difference = instantaneous frequency
    
    product = iq[1:] * np.conj(iq[:-1])
    fm_out = np.angle(product)
    
    return fm_out


def lowpass_filter(data, cutoff_hz, sample_rate, order=5):
    """
    Apply lowpass Butterworth filter.
    """
    nyq = sample_rate / 2
    normalized_cutoff = cutoff_hz / nyq
    
    # Clamp to valid range
    normalized_cutoff = min(normalized_cutoff, 0.99)
    
    b, a = signal.butter(order, normalized_cutoff, btype='low')
    filtered = signal.filtfilt(b, a, data)
    
    return filtered


def resample_signal(data, original_rate, target_rate):
    """
    Resample signal to target sample rate.
    """
    num_samples = int(len(data) * target_rate / original_rate)
    resampled = signal.resample(data, num_samples)
    return resampled


def am_demodulate(data):
    """
    AM demodulation via envelope detection.
    
    The APT signal uses a 2400 Hz AM subcarrier.
    We detect the envelope using the Hilbert transform.
    """
    # Hilbert transform gives us the analytic signal
    analytic = signal.hilbert(data)
    
    # Envelope is the magnitude
    envelope = np.abs(analytic)
    
    return envelope


def find_sync_pulses(data, sample_rate):
    """
    Find APT sync pulses to determine line boundaries.
    
    APT sync pattern:
    - 7 pulses of sync tone
    - Distinctive frequency pattern
    
    We use correlation with expected sync pattern.
    """
    samples_per_line = int(sample_rate / APT_LINES_PER_SEC)
    
    # Generate expected sync pulse pattern (simplified)
    # Sync A is 7 cycles of 1040 Hz square wave
    sync_duration = 0.005  # ~5ms sync pulse
    t_sync = np.arange(0, sync_duration, 1/sample_rate)
    sync_pattern = np.sin(2 * np.pi * SYNC_A_FREQ * t_sync)
    sync_pattern = (sync_pattern > 0).astype(float)  # Square wave
    
    # Correlate to find sync positions
    correlation = signal.correlate(data, sync_pattern, mode='valid')
    
    # Find peaks in correlation
    # These indicate sync pulse locations
    threshold = np.max(correlation) * 0.5
    peaks, _ = signal.find_peaks(correlation, height=threshold, distance=samples_per_line * 0.9)
    
    return peaks, samples_per_line


def extract_lines(data, sync_positions, samples_per_line):
    """
    Extract image lines starting from sync positions.
    """
    lines = []
    
    for i, start in enumerate(sync_positions):
        end = start + samples_per_line
        
        if end > len(data):
            break
            
        line = data[start:end]
        
        # Resample line to exactly APT_PIXELS_PER_LINE pixels
        line_resampled = signal.resample(line, APT_PIXELS_PER_LINE)
        lines.append(line_resampled)
    
    return np.array(lines)


def normalize_image(image):
    """
    Normalize image to 0-255 range for PNG output.
    """
    # Remove outliers
    p_low, p_high = np.percentile(image, [2, 98])
    image = np.clip(image, p_low, p_high)
    
    # Normalize to 0-255
    image = (image - p_low) / (p_high - p_low) * 255
    image = image.astype(np.uint8)
    
    return image


def decode_apt(iq_filepath, output_dir=None, station_offset_hz=0):
    """
    Main decoding function.
    
    Args:
        iq_filepath: Path to I/Q file (.mat or .bin)
        output_dir: Output directory (default: same as input)
        station_offset_hz: Frequency offset if station not centered
    
    Returns:
        Dictionary with results and metadata
    """
    print(f"Loading I/Q data from: {iq_filepath}")
    iq, fs = load_iq(iq_filepath)
    print(f"  Samples: {len(iq):,}")
    print(f"  Sample rate: {fs/1e6:.2f} MHz")
    print(f"  Duration: {len(iq)/fs:.1f} seconds")
    
    # Frequency shift if needed
    if station_offset_hz != 0:
        print(f"  Applying frequency shift: {station_offset_hz} Hz")
        t = np.arange(len(iq)) / fs
        iq = iq * np.exp(-1j * 2 * np.pi * station_offset_hz * t)
    
    # Step 1: FM Demodulation
    print("FM demodulating...")
    fm_audio = fm_demodulate(iq)
    
    # Step 2: Lowpass filter to APT bandwidth (~17 kHz)
    print("Lowpass filtering...")
    lpf_cutoff = 17000  # Hz
    fm_filtered = lowpass_filter(fm_audio, lpf_cutoff, fs)
    
    # Step 3: Decimate to manageable rate
    # Go from 2.4 MHz to ~48 kHz first
    decim_factor = int(fs / 48000)
    print(f"Decimating by {decim_factor}...")
    fm_decimated = signal.decimate(fm_filtered, decim_factor, ftype='fir')
    fs_decimated = fs / decim_factor
    
    # Step 4: Resample to APT sample rate
    print(f"Resampling to {APT_SAMPLE_RATE} Hz...")
    apt_signal = resample_signal(fm_decimated, fs_decimated, APT_SAMPLE_RATE)
    
    # Step 5: AM Demodulation
    print("AM demodulating (envelope detection)...")
    envelope = am_demodulate(apt_signal)
    
    # Step 6: Find sync pulses
    print("Finding sync pulses...")
    sync_positions, samples_per_line = find_sync_pulses(envelope, APT_SAMPLE_RATE)
    print(f"  Found {len(sync_positions)} sync pulses")
    
    if len(sync_positions) < 10:
        print("WARNING: Few sync pulses found. Falling back to fixed line extraction.")
        # Fall back: assume lines start at regular intervals
        num_lines = int(len(envelope) / samples_per_line)
        sync_positions = np.arange(num_lines) * samples_per_line
        sync_positions = sync_positions.astype(int)
    
    # Step 7: Extract image lines
    print("Extracting image lines...")
    image = extract_lines(envelope, sync_positions, samples_per_line)
    print(f"  Image shape: {image.shape}")
    
    # Step 8: Normalize for display
    print("Normalizing image...")
    image_normalized = normalize_image(image)
    
    # Step 9: Save outputs
    if output_dir is None:
        output_dir = os.path.dirname(iq_filepath)
    
    os.makedirs(output_dir, exist_ok=True)
    
    base_name = os.path.splitext(os.path.basename(iq_filepath))[0]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save PNG
    png_path = os.path.join(output_dir, f"{base_name}_decoded.png")
    
    # Use PIL if available, otherwise matplotlib
    try:
        from PIL import Image
        img = Image.fromarray(image_normalized, mode='L')
        img.save(png_path)
    except ImportError:
        import matplotlib.pyplot as plt
        plt.imsave(png_path, image_normalized, cmap='gray')
    
    print(f"Saved image: {png_path}")
    
    # Save metadata
    metadata = {
        'input_file': iq_filepath,
        'output_file': png_path,
        'timestamp': timestamp,
        'sample_rate_hz': fs,
        'duration_sec': len(iq) / fs,
        'image_width': image.shape[1],
        'image_height': image.shape[0],
        'sync_pulses_found': len(sync_positions),
        'station_offset_hz': station_offset_hz
    }
    
    meta_path = os.path.join(output_dir, f"{base_name}_metadata.json")
    with open(meta_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"Saved metadata: {meta_path}")
    
    return {
        'image': image_normalized,
        'metadata': metadata,
        'png_path': png_path
    }


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python decode_apt.py <iq_file.mat> [output_dir] [freq_offset_hz]")
        print("")
        print("Arguments:")
        print("  iq_file.mat     - Raw I/Q capture file (.mat or .bin)")
        print("  output_dir      - Output directory (optional)")
        print("  freq_offset_hz  - Station frequency offset in Hz (optional)")
        sys.exit(1)
    
    iq_file = sys.argv[1]
    out_dir = sys.argv[2] if len(sys.argv) > 2 else None
    offset = float(sys.argv[3]) if len(sys.argv) > 3 else 0
    
    result = decode_apt(iq_file, out_dir, offset)
    
    print("\n" + "="*50)
    print("DECODE COMPLETE")
    print("="*50)
    print(f"Image: {result['png_path']}")
    print(f"Size: {result['metadata']['image_width']} x {result['metadata']['image_height']}")
