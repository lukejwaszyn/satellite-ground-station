#!/usr/bin/env python3
"""
compare_decoders.py
Satellite Ground Station - Decoder Comparison Tool

Runs both the custom decoder (decode_apt.py or decode_lrpt.py) and SatDump
on the same raw I/Q capture file, then compares the results side-by-side.

This is the primary validation tool for ensuring our decoders produce
correct output. SatDump serves as the ground truth reference.

Usage:
    python compare_decoders.py <capture.bin> [--satellite NOAA19] [--output-dir results/]

Output:
    - Custom decoder image + metadata
    - SatDump decoder image + metadata
    - Comparison report (sync count, image dimensions, SNR estimate)
    - Side-by-side composite image

Requirements:
    - SatDump CLI installed (https://github.com/SatDump/SatDump)
    - Custom decoders (decode_apt.py, decode_lrpt.py)

Author: Luke Waszyn
Date: March 2026
"""

import os
import sys
import json
import subprocess
import shutil
import argparse
import numpy as np
from datetime import datetime
from pathlib import Path

# Add parent directories for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def detect_satellite_type(filename, satellite=None):
    """
    Determine satellite and signal type from filename or explicit argument.
    
    Returns: (satellite_name, signal_type) e.g. ('NOAA 19', 'APT') or ('METEOR-M2 3', 'LRPT')
    """
    name = (satellite or filename).upper()
    
    if 'METEOR' in name:
        return satellite or 'METEOR-M2 3', 'LRPT'
    elif 'NOAA' in name:
        # Extract NOAA number
        for n in ['15', '18', '19']:
            if n in name:
                return f'NOAA {n}', 'APT'
        return satellite or 'NOAA 19', 'APT'
    else:
        # Default to APT
        return satellite or 'Unknown', 'APT'


def run_custom_decoder(capture_path, signal_type, output_dir):
    """
    Run our custom decoder on the capture file.
    
    Returns: dict with results or None on failure
    """
    print(f"\n{'='*50}")
    print(f"  CUSTOM DECODER ({signal_type})")
    print(f"{'='*50}")
    
    custom_dir = os.path.join(output_dir, 'custom')
    os.makedirs(custom_dir, exist_ok=True)
    
    try:
        if signal_type == 'APT':
            from python.demod.decode_apt import decode_apt
            result = decode_apt(capture_path, custom_dir)
        elif signal_type == 'LRPT':
            from python.demod.decode_lrpt import decode_lrpt
            result = decode_lrpt(capture_path, custom_dir)
        else:
            print(f"  Unknown signal type: {signal_type}")
            return None
        
        if result:
            print(f"\n  Image: {result.get('image_path', 'None')}")
            print(f"  Metadata: {json.dumps(result.get('metadata', {}), indent=2)[:500]}")
        
        return result
        
    except Exception as e:
        print(f"  FAILED: {e}")
        import traceback
        traceback.print_exc()
        return None


def run_satdump(capture_path, satellite_name, signal_type, output_dir):
    """
    Run SatDump CLI on the capture file.
    
    SatDump command format:
        satdump <pipeline> <input_level> <input_file> <output_dir> [options]
    
    For APT:
        satdump noaa_apt baseband <file.bin> <output> --samplerate 2400000 --source_id 0
    For LRPT:
        satdump meteor_m2_lrpt baseband <file.bin> <output> --samplerate 2400000
    
    Returns: dict with results or None on failure
    """
    print(f"\n{'='*50}")
    print(f"  SATDUMP REFERENCE ({signal_type})")
    print(f"{'='*50}")
    
    # Check if SatDump is installed
    satdump_path = shutil.which('satdump')
    if not satdump_path:
        # Try common install locations
        for path in ['/usr/local/bin/satdump', '/opt/homebrew/bin/satdump', 
                     os.path.expanduser('~/SatDump/build/satdump')]:
            if os.path.exists(path):
                satdump_path = path
                break
    
    if not satdump_path:
        print("  SatDump not found in PATH.")
        print("  Install from: https://github.com/SatDump/SatDump")
        print("  Or specify path with --satdump-path")
        return None
    
    print(f"  Using: {satdump_path}")
    
    satdump_dir = os.path.join(output_dir, 'satdump')
    os.makedirs(satdump_dir, exist_ok=True)
    
    # Build SatDump command
    if signal_type == 'APT':
        pipeline = 'noaa_apt'
        cmd = [
            satdump_path, pipeline, 'baseband',
            capture_path, satdump_dir,
            '--samplerate', '2400000',
            '--baseband_format', 'cu8',
        ]
    elif signal_type == 'LRPT':
        pipeline = 'meteor_m2-x_lrpt'
        cmd = [
            satdump_path, pipeline, 'baseband',
            capture_path, satdump_dir,
            '--samplerate', '2400000',
            '--baseband_format', 'cu8',
        ]
    else:
        print(f"  Unsupported signal type for SatDump: {signal_type}")
        return None
    
    print(f"  Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=600
        )
        
        print(f"  Exit code: {result.returncode}")
        if result.stdout:
            # Print last 20 lines of output
            lines = result.stdout.strip().split('\n')
            for line in lines[-20:]:
                print(f"    {line}")
        if result.returncode != 0 and result.stderr:
            print(f"  Stderr: {result.stderr[:500]}")
        
        # Find output images
        images = []
        for ext in ['*.png', '*.jpg', '*.jpeg']:
            images.extend(Path(satdump_dir).rglob(ext))
        
        # Find metadata
        metadata_files = list(Path(satdump_dir).rglob('dataset.json'))
        metadata = {}
        if metadata_files:
            with open(metadata_files[0]) as f:
                metadata = json.load(f)
        
        return {
            'images': [str(p) for p in images],
            'metadata': metadata,
            'output_dir': satdump_dir,
            'returncode': result.returncode,
        }
        
    except subprocess.TimeoutExpired:
        print("  TIMEOUT (600s)")
        return None
    except Exception as e:
        print(f"  FAILED: {e}")
        return None


def estimate_image_snr(image_array):
    """
    Estimate signal-to-noise ratio of a decoded image.
    
    Method: Compare variance in "signal" regions (high local variance = features)
    vs "noise" regions (low local variance = static/noise).
    
    Returns: estimated SNR in dB, or None
    """
    if image_array is None or image_array.size == 0:
        return None
    
    img = image_array.astype(np.float64)
    
    # Split image into blocks
    block_size = 32
    h, w = img.shape[:2]
    if len(img.shape) == 3:
        img = np.mean(img, axis=2)  # convert to grayscale
    
    block_vars = []
    for y in range(0, h - block_size, block_size):
        for x in range(0, w - block_size, block_size):
            block = img[y:y+block_size, x:x+block_size]
            block_vars.append(np.var(block))
    
    if len(block_vars) < 4:
        return None
    
    block_vars = np.array(block_vars)
    
    # Signal blocks = top 25% variance, noise blocks = bottom 25%
    sorted_vars = np.sort(block_vars)
    n = len(sorted_vars)
    noise_var = np.mean(sorted_vars[:n//4])
    signal_var = np.mean(sorted_vars[3*n//4:])
    
    if noise_var <= 0:
        return None
    
    snr_db = 10 * np.log10(signal_var / noise_var)
    return round(snr_db, 1)


def generate_comparison_report(capture_path, satellite, signal_type,
                                custom_result, satdump_result, output_dir):
    """
    Generate a comparison report between the two decoders.
    """
    print(f"\n{'='*60}")
    print(f"  COMPARISON REPORT")
    print(f"{'='*60}")
    
    report = {
        'timestamp': datetime.now().isoformat(),
        'capture_file': os.path.basename(capture_path),
        'capture_size_mb': round(os.path.getsize(capture_path) / 1e6, 1),
        'satellite': satellite,
        'signal_type': signal_type,
        'custom': {},
        'satdump': {},
    }
    
    # Custom decoder results
    if custom_result:
        meta = custom_result.get('metadata', {})
        report['custom'] = {
            'success': custom_result.get('image_path') is not None,
            'image_path': custom_result.get('image_path'),
            'sync_pulses': meta.get('sync_pulses_found', meta.get('frames_found', 0)),
            'image_shape': meta.get('image_shape'),
            'duration_sec': meta.get('duration_sec'),
        }
        
        # Estimate SNR from custom image
        if custom_result.get('image') is not None:
            snr = estimate_image_snr(custom_result['image'])
            report['custom']['estimated_snr_db'] = snr
        elif custom_result.get('image_path'):
            try:
                from PIL import Image
                img = np.array(Image.open(custom_result['image_path']))
                snr = estimate_image_snr(img)
                report['custom']['estimated_snr_db'] = snr
            except Exception:
                pass
    else:
        report['custom'] = {'success': False, 'error': 'Decoder failed'}
    
    # SatDump results
    if satdump_result:
        report['satdump'] = {
            'success': satdump_result['returncode'] == 0 and len(satdump_result['images']) > 0,
            'images': [os.path.basename(p) for p in satdump_result['images']],
            'image_count': len(satdump_result['images']),
            'metadata': satdump_result['metadata'],
        }
        
        # Estimate SNR from SatDump's best image
        if satdump_result['images']:
            try:
                from PIL import Image
                img = np.array(Image.open(satdump_result['images'][0]))
                snr = estimate_image_snr(img)
                report['satdump']['estimated_snr_db'] = snr
            except Exception:
                pass
    else:
        report['satdump'] = {'success': False, 'error': 'SatDump not available or failed'}
    
    # Print summary
    c = report['custom']
    s = report['satdump']
    
    print(f"\n  Capture: {report['capture_file']} ({report['capture_size_mb']} MB)")
    print(f"  Satellite: {satellite} ({signal_type})")
    print(f"  Duration: {c.get('duration_sec', '?')}s")
    print()
    print(f"  {'Metric':<25} {'Custom':<20} {'SatDump':<20}")
    print(f"  {'-'*65}")
    print(f"  {'Success':<25} {str(c.get('success', '?')):<20} {str(s.get('success', '?')):<20}")
    print(f"  {'Sync/Frames':<25} {str(c.get('sync_pulses', '?')):<20} {'—':<20}")
    print(f"  {'Image Shape':<25} {str(c.get('image_shape', '?')):<20} {str(s.get('image_count', '?')) + ' images':<20}")
    print(f"  {'Est. SNR (dB)':<25} {str(c.get('estimated_snr_db', '?')):<20} {str(s.get('estimated_snr_db', '?')):<20}")
    
    # Verdict
    print()
    if c.get('success') and s.get('success'):
        c_snr = c.get('estimated_snr_db', 0) or 0
        s_snr = s.get('estimated_snr_db', 0) or 0
        diff = c_snr - s_snr
        if abs(diff) < 3:
            verdict = "COMPARABLE — both decoders producing similar quality"
        elif diff > 0:
            verdict = f"CUSTOM BETTER — +{diff:.1f} dB over SatDump"
        else:
            verdict = f"SATDUMP BETTER — +{abs(diff):.1f} dB over custom decoder"
        print(f"  Verdict: {verdict}")
    elif c.get('success') and not s.get('success'):
        print(f"  Verdict: CUSTOM ONLY — SatDump failed, custom decoder succeeded")
    elif not c.get('success') and s.get('success'):
        print(f"  Verdict: SATDUMP ONLY — Custom decoder failed, investigate decoder bugs")
    else:
        print(f"  Verdict: BOTH FAILED — likely an RF/capture issue, not a decoder issue")
    
    # Save report
    report_path = os.path.join(output_dir, 'comparison_report.json')
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"\n  Report saved: {report_path}")
    
    return report


def create_side_by_side(custom_result, satdump_result, output_dir):
    """
    Create a side-by-side comparison image.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
        
        images = []
        labels = []
        
        # Custom decoder image
        if custom_result and custom_result.get('image_path') and os.path.exists(custom_result['image_path']):
            images.append(Image.open(custom_result['image_path']).convert('RGB'))
            labels.append('CUSTOM DECODER')
        
        # SatDump best image
        if satdump_result and satdump_result.get('images'):
            for img_path in satdump_result['images']:
                if os.path.exists(img_path) and img_path.endswith('.png'):
                    images.append(Image.open(img_path).convert('RGB'))
                    labels.append(f'SATDUMP: {os.path.basename(img_path)}')
                    break
        
        if len(images) < 2:
            print("  Cannot create side-by-side: need images from both decoders")
            return None
        
        # Resize to same height
        target_h = min(img.height for img in images)
        resized = []
        for img in images:
            ratio = target_h / img.height
            new_w = int(img.width * ratio)
            resized.append(img.resize((new_w, target_h), Image.LANCZOS))
        
        # Combine side by side with labels
        gap = 20
        total_w = sum(img.width for img in resized) + gap
        composite = Image.new('RGB', (total_w, target_h + 30), (10, 12, 16))
        
        x = 0
        draw = ImageDraw.Draw(composite)
        for img, label in zip(resized, labels):
            composite.paste(img, (x, 30))
            draw.text((x + 10, 8), label, fill=(56, 189, 248))
            x += img.width + gap
        
        comp_path = os.path.join(output_dir, 'side_by_side.png')
        composite.save(comp_path)
        print(f"  Side-by-side saved: {comp_path}")
        return comp_path
        
    except ImportError:
        print("  Pillow not available for side-by-side composite")
        return None
    except Exception as e:
        print(f"  Side-by-side failed: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(
        description='Compare custom decoder vs SatDump on the same capture',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python compare_decoders.py data/captures/NOAA_19_20260306.bin
  python compare_decoders.py capture.bin --satellite "NOAA 18"
  python compare_decoders.py capture.bin --satellite "METEOR-M2 3" --output-dir results/
"""
    )
    parser.add_argument('capture', help='Path to raw I/Q capture file (.bin)')
    parser.add_argument('--satellite', '-s', help='Satellite name (auto-detected from filename if omitted)')
    parser.add_argument('--output-dir', '-o', default=None, help='Output directory (default: data/comparisons/<capture_name>/)')
    parser.add_argument('--satdump-path', help='Path to SatDump binary')
    parser.add_argument('--skip-satdump', action='store_true', help='Skip SatDump (only run custom decoder)')
    parser.add_argument('--skip-custom', action='store_true', help='Skip custom decoder (only run SatDump)')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.capture):
        print(f"ERROR: Capture file not found: {args.capture}")
        sys.exit(1)
    
    # Detect satellite type
    satellite, signal_type = detect_satellite_type(args.capture, args.satellite)
    
    # Setup output directory
    if args.output_dir:
        output_dir = args.output_dir
    else:
        base = os.path.splitext(os.path.basename(args.capture))[0]
        output_dir = os.path.join('data', 'comparisons', base)
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"\n{'='*60}")
    print(f"  DECODER COMPARISON")
    print(f"{'='*60}")
    print(f"  Capture:   {args.capture}")
    print(f"  Size:      {os.path.getsize(args.capture) / 1e6:.1f} MB")
    print(f"  Satellite: {satellite}")
    print(f"  Signal:    {signal_type}")
    print(f"  Output:    {output_dir}")
    
    # Run custom decoder
    custom_result = None
    if not args.skip_custom:
        custom_result = run_custom_decoder(args.capture, signal_type, output_dir)
    
    # Run SatDump
    satdump_result = None
    if not args.skip_satdump:
        if args.satdump_path:
            # Override SatDump path
            os.environ['SATDUMP_PATH'] = args.satdump_path
        satdump_result = run_satdump(args.capture, satellite, signal_type, output_dir)
    
    # Generate comparison report
    report = generate_comparison_report(
        args.capture, satellite, signal_type,
        custom_result, satdump_result, output_dir
    )
    
    # Create side-by-side image
    if custom_result and satdump_result:
        create_side_by_side(custom_result, satdump_result, output_dir)
    
    print(f"\n{'='*60}")
    print(f"  All outputs in: {output_dir}")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()
