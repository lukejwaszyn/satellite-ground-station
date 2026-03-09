#!/usr/bin/env python3
"""
decode_apt.py
Satellite Ground Station - APT Image Decoder (Memory-Efficient)

Decodes NOAA APT weather satellite images from raw RTL-SDR I/Q captures.
Processes data in chunks to fit within 16 GB RAM.

RTL-SDR raw format: interleaved uint8 I/Q (values 0-255, centered at 127)
APT format: 2 lines/second, 2080 pixels/line, FM modulated, AM subcarrier

Author: Luke Waszyn
Date: February 2026
"""

import numpy as np
from scipy import signal
from scipy.io import loadmat
from datetime import datetime
import os
import json

# APT Signal Parameters
APT_LINES_PER_SEC = 2
APT_PIXELS_PER_LINE = 2080
APT_SAMPLE_RATE = 20800  # 2080 pixels * 2 lines/sec * 5 samples/pixel
APT_SYNC_FREQ = 1040  # Hz - sync pulse frequency
APT_LINE_DURATION = 0.5  # seconds per line


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
        # Raw binary: RTL-SDR uint8 interleaved I/Q (values 0-255, centered at 127)
        raw = np.fromfile(filepath, dtype=np.uint8).astype(np.float32)
        raw = (raw - 127.5) / 127.5  # Normalize to [-1, 1]
        iq = raw[0::2] + 1j * raw[1::2]
        return iq.astype(np.complex64), 2.4e6  # Assume default rate
    
    else:
        raise ValueError(f"Unsupported file format: {ext}")


def load_iq_chunked(filepath, fs=2.4e6, target_fs=48000):
    """
    Load and decimate raw RTL-SDR I/Q data in chunks.
    
    Processes the file in ~50 MB blocks to keep peak RAM under 8 GB.
    Each chunk is: load uint8 -> normalize -> complex -> FM demod -> decimate
    
    Returns: decimated FM audio (float32), decimated sample rate
    """
    ext = os.path.splitext(filepath)[1].lower()
    
    if ext != '.bin':
        # For non-binary formats, load normally and decimate
        iq, fs = load_iq(filepath)
        fm = np.angle(iq[1:] * np.conj(iq[:-1]))
        del iq
        decim_factor = int(fs / target_fs)
        fm_dec = signal.decimate(fm, decim_factor, ftype='fir')
        del fm
        return fm_dec, target_fs
    
    file_size = os.path.getsize(filepath)
    total_iq_samples = file_size // 2  # 2 bytes per complex sample (I + Q)
    
    decim_factor = int(fs / target_fs)
    
    # Process in chunks of ~50M IQ samples (~100 MB raw)
    # Must be divisible by decim_factor for clean decimation
    chunk_iq_samples = 50_000_000
    chunk_iq_samples = (chunk_iq_samples // decim_factor) * decim_factor
    chunk_bytes = chunk_iq_samples * 2  # 2 bytes per IQ sample
    
    fm_chunks = []
    offset = 0
    chunk_num = 0
    prev_sample = None  # For FM demod continuity across chunks
    
    print(f"  Processing {total_iq_samples:,} IQ samples in chunks of {chunk_iq_samples:,}")
    
    with open(filepath, 'rb') as f:
        while offset < file_size:
            # Read chunk of raw bytes
            raw_bytes = np.frombuffer(f.read(chunk_bytes), dtype=np.uint8)
            if len(raw_bytes) < 4:
                break
            
            # Convert to normalized complex IQ
            raw = raw_bytes.astype(np.float32)
            raw = (raw - 127.5) / 127.5
            iq = raw[0::2] + 1j * raw[1::2]
            del raw, raw_bytes
            
            # FM demodulate: angle(iq[n] * conj(iq[n-1]))
            # Handle boundary between chunks
            if prev_sample is not None:
                iq_with_prev = np.concatenate(([prev_sample], iq))
                product = iq_with_prev[1:] * np.conj(iq_with_prev[:-1])
            else:
                product = iq[1:] * np.conj(iq[:-1])
            
            prev_sample = iq[-1]
            del iq
            
            fm = np.angle(product).astype(np.float32)
            del product
            
            # Decimate this chunk
            # Trim to multiple of decim_factor
            trim_len = (len(fm) // decim_factor) * decim_factor
            if trim_len > 0:
                fm_trimmed = fm[:trim_len]
                fm_dec = signal.decimate(fm_trimmed, decim_factor, ftype='fir')
                fm_chunks.append(fm_dec)
                del fm_trimmed, fm_dec
            
            del fm
            offset += chunk_bytes
            chunk_num += 1
            
            progress = min(100, offset * 100 // file_size)
            print(f"    Chunk {chunk_num}: {progress}% complete", end='\r')
    
    print(f"    Processed {chunk_num} chunks                    ")
    
    # Concatenate all decimated chunks
    fm_decimated = np.concatenate(fm_chunks)
    del fm_chunks
    
    return fm_decimated, target_fs


def fm_demodulate(iq):
    """
    FM demodulation using quadrature discriminator.
    """
    product = iq[1:] * np.conj(iq[:-1])
    fm_out = np.angle(product)
    return fm_out


def lowpass_filter(data, cutoff_hz, sample_rate, order=5):
    """
    Apply lowpass Butterworth filter.
    """
    nyq = sample_rate / 2
    normalized_cutoff = cutoff_hz / nyq
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
    """
    analytic = signal.hilbert(data)
    envelope = np.abs(analytic)
    return envelope


def find_sync_pulses(data, sample_rate):
    """
    Find APT sync pulses to determine line boundaries.
    
    APT sync pattern:
    - Channel A sync: 7 cycles of 1040 Hz (7 * 1/1040 ≈ 6.73 ms)
    - Channel B sync: 7 cycles of 832 Hz
    
    We correlate against a 1040 Hz sync template.
    """
    # Generate sync A template (1040 Hz, 7 cycles)
    sync_duration = 7 / APT_SYNC_FREQ
    t_sync = np.arange(0, sync_duration, 1/sample_rate)
    sync_template = np.sin(2 * np.pi * APT_SYNC_FREQ * t_sync)
    
    # Samples per APT line
    samples_per_line = int(sample_rate / APT_LINES_PER_SEC)
    
    # Correlate in chunks to save memory
    chunk_size = min(len(data), sample_rate * 30)  # 30 seconds at a time
    all_peaks = []
    
    for start in range(0, len(data) - len(sync_template), chunk_size):
        end = min(start + chunk_size + len(sync_template), len(data))
        chunk = data[start:end]
        
        correlation = np.correlate(chunk, sync_template, mode='valid')
        correlation = np.abs(correlation)
        
        threshold = np.max(correlation) * 0.5
        peaks, _ = signal.find_peaks(correlation, height=threshold, 
                                      distance=int(samples_per_line * 0.9))
        
        # Offset peaks by chunk start position
        all_peaks.extend(peaks + start)
    
    # Remove duplicate peaks near chunk boundaries
    if len(all_peaks) > 0:
        all_peaks = np.array(sorted(set(all_peaks)))
        # Remove peaks that are too close together
        if len(all_peaks) > 1:
            diffs = np.diff(all_peaks)
            keep = np.concatenate(([True], diffs > samples_per_line * 0.5))
            all_peaks = all_peaks[keep]
    else:
        all_peaks = np.array([], dtype=int)
    
    return all_peaks, samples_per_line


def extract_lines(data, sync_positions, samples_per_line):
    """
    Extract image lines starting from sync positions.
    """
    lines = []
    
    for i, start in enumerate(sync_positions):
        start = int(start)
        end = int(start + samples_per_line)
        
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
    if p_high > p_low:
        image = (image - p_low) / (p_high - p_low) * 255
    else:
        image = np.zeros_like(image)
    
    image = image.astype(np.uint8)
    
    return image


def decode_apt(iq_filepath, output_dir=None, station_offset_hz=0):
    """
    Main decoding function.
    
    Uses chunked processing for raw .bin files to stay within 16 GB RAM.
    
    Args:
        iq_filepath: Path to I/Q file (.mat or .bin)
        output_dir: Output directory (default: same as input)
        station_offset_hz: Frequency offset if station not centered
    
    Returns:
        Dictionary with results and metadata
    """
    file_size = os.path.getsize(iq_filepath)
    ext = os.path.splitext(iq_filepath)[1].lower()
    
    print(f"Loading I/Q data from: {iq_filepath}")
    print(f"  File size: {file_size / 1e9:.2f} GB")
    
    # For large .bin files, use chunked processing
    if ext == '.bin' and file_size > 500_000_000:  # > 500 MB
        fs = 2.4e6
        target_fs = 48000
        
        total_iq = file_size // 2
        duration = total_iq / fs
        print(f"  Samples: {total_iq:,}")
        print(f"  Sample rate: {fs/1e6:.2f} MHz")
        print(f"  Duration: {duration:.1f} seconds")
        print(f"  Using chunked processing (memory-efficient mode)")
        
        # Chunked load + FM demod + decimate
        fm_decimated, fs_decimated = load_iq_chunked(iq_filepath, fs, target_fs)
        
        # Lowpass filter at decimated rate
        print("Lowpass filtering...")
        lpf_cutoff = 17000  # Hz
        fm_filtered = lowpass_filter(fm_decimated, lpf_cutoff, fs_decimated)
        del fm_decimated
        
    else:
        # Small files: load entirely
        iq, fs = load_iq(iq_filepath)
        print(f"  Samples: {len(iq):,}")
        print(f"  Sample rate: {fs/1e6:.2f} MHz")
        print(f"  Duration: {len(iq)/fs:.1f} seconds")
        
        # Frequency shift if needed
        if station_offset_hz != 0:
            print(f"  Applying frequency shift: {station_offset_hz} Hz")
            t = np.arange(len(iq)) / fs
            iq = iq * np.exp(-1j * 2 * np.pi * station_offset_hz * t)
        
        # FM Demodulation
        print("FM demodulating...")
        fm_audio = fm_demodulate(iq)
        del iq
        
        # Lowpass filter
        print("Lowpass filtering...")
        lpf_cutoff = 17000
        fm_filtered = lowpass_filter(fm_audio, lpf_cutoff, fs)
        del fm_audio
        
        # Decimate
        decim_factor = int(fs / 48000)
        print(f"Decimating by {decim_factor}...")
        fm_filtered = signal.decimate(fm_filtered, decim_factor, ftype='fir')
        fs_decimated = fs / decim_factor
    
    # Resample to APT sample rate
    print(f"Resampling to {APT_SAMPLE_RATE} Hz...")
    apt_signal = resample_signal(fm_filtered, fs_decimated, APT_SAMPLE_RATE)
    del fm_filtered
    
    # AM Demodulation
    print("AM demodulating (envelope detection)...")
    envelope = am_demodulate(apt_signal)
    del apt_signal
    
    # Find sync pulses
    print("Finding sync pulses...")
    sync_positions, samples_per_line = find_sync_pulses(envelope, APT_SAMPLE_RATE)
    print(f"  Found {len(sync_positions)} sync pulses")
    
    if len(sync_positions) < 10:
        print("WARNING: Few sync pulses found. Falling back to fixed line extraction.")
        # Use first sync as anchor if available, otherwise start at 0
        start_offset = int(sync_positions[0]) if len(sync_positions) > 0 else 0
        num_lines = int((len(envelope) - start_offset) / samples_per_line)
        sync_positions = start_offset + np.arange(num_lines) * samples_per_line
        sync_positions = sync_positions.astype(int)
    
    # Extract image lines
    print("Extracting image lines...")
    image = extract_lines(envelope, sync_positions, samples_per_line)
    print(f"  Image shape: {image.shape}")
    del envelope
    
    # Normalize for display
    print("Normalizing image...")
    image_normalized = normalize_image(image)
    
    # Save outputs
    if output_dir is None:
        output_dir = os.path.dirname(iq_filepath)
    
    os.makedirs(output_dir, exist_ok=True)
    
    base_name = os.path.splitext(os.path.basename(iq_filepath))[0]
    
    # Save PNG
    png_path = os.path.join(output_dir, f"{base_name}_decoded.png")
    
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
        'source_file': os.path.basename(iq_filepath),
        'decode_time': datetime.now().isoformat(),
        'sample_rate': float(fs_decimated) if 'fs_decimated' in dir() else 48000.0,
        'original_sample_rate': 2.4e6,
        'duration_sec': float(file_size / 2 / 2.4e6) if ext == '.bin' else 0,
        'sync_pulses_found': int(len(sync_positions)),
        'image_shape': list(image_normalized.shape),
        'station_offset_hz': station_offset_hz,
    }
    
    meta_path = os.path.join(output_dir, f"{base_name}_metadata.json")
    with open(meta_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    print(f"Saved metadata: {meta_path}")
    
    return {
        'image': image_normalized,
        'image_path': png_path,
        'metadata': metadata,
    }


# CLI entry point
if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python decode_apt.py <iq_file> [output_dir]")
        print("  Supports .mat and .bin (RTL-SDR raw uint8) files")
        sys.exit(1)
    
    iq_file = sys.argv[1]
    out_dir = sys.argv[2] if len(sys.argv) > 2 else 'data/decoded'
    
    result = decode_apt(iq_file, out_dir)
    
    if result:
        print(f"\nDecode complete: {result['image_path']}")
        print(f"  Sync pulses: {result['metadata']['sync_pulses_found']}")
        print(f"  Image size: {result['metadata']['image_shape']}")
