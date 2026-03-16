#!/usr/bin/env python3
"""
quality_estimator.py
Satellite Ground Station - Post-Decode Image Quality Estimator

Analyzes decoded satellite images to estimate signal quality and
automatically classify captures as GOOD, MARGINAL, or NOISE.

Metrics computed:
  - Estimated SNR (block variance method)
  - Sync pulse quality (for APT)
  - Image entropy (information content)
  - Feature detection (edges = real imagery vs noise)
  - Stripe/interference pattern detection

This feeds directly into:
  1. Mission log (auto-tag quality without manual review)
  2. ML training pipeline (only train on GOOD captures)
  3. Decoder debugging (compare before/after changes)

Usage:
    python quality_estimator.py <decoded_image.png> [metadata.json]
    
    # Or use programmatically:
    from quality_estimator import estimate_quality
    result = estimate_quality('decoded.png', metadata_path='metadata.json')

Author: Luke Waszyn
Date: March 2026
"""

import numpy as np
import os
import sys
import json
from pathlib import Path


# Quality grade thresholds
GRADE_THRESHOLDS = {
    'snr_good': 12.0,       # dB — clear features visible
    'snr_marginal': 6.0,    # dB — some features, noisy
    'entropy_good': 5.0,    # bits — rich image content
    'entropy_marginal': 3.0, # bits — some content
    'edge_good': 0.08,      # edge density fraction
    'edge_marginal': 0.03,
}


def load_image(image_path):
    """Load image as numpy array (grayscale)."""
    try:
        from PIL import Image
        img = Image.open(image_path)
        if img.mode == 'RGB' or img.mode == 'RGBA':
            img = img.convert('L')
        return np.array(img, dtype=np.float64)
    except ImportError:
        # Fallback: try matplotlib
        try:
            import matplotlib.pyplot as plt
            img = plt.imread(image_path)
            if len(img.shape) == 3:
                img = np.mean(img, axis=2)
            return img.astype(np.float64)
        except ImportError:
            print("ERROR: Need Pillow or matplotlib to load images")
            return None


def estimate_snr(image, block_size=32):
    """
    Estimate signal-to-noise ratio using block variance analysis.
    
    Splits image into blocks, computes variance of each block.
    Signal blocks (features, edges) have high variance.
    Noise blocks (static) have low, uniform variance.
    
    SNR = 10 * log10(signal_variance / noise_variance)
    
    Returns: SNR in dB
    """
    h, w = image.shape
    
    block_vars = []
    for y in range(0, h - block_size, block_size):
        for x in range(0, w - block_size, block_size):
            block = image[y:y+block_size, x:x+block_size]
            block_vars.append(np.var(block))
    
    if len(block_vars) < 8:
        return 0.0
    
    block_vars = np.array(block_vars)
    sorted_vars = np.sort(block_vars)
    n = len(sorted_vars)
    
    # Noise = bottom 25% of block variances
    # Signal = top 25%
    noise_var = np.mean(sorted_vars[:max(1, n//4)])
    signal_var = np.mean(sorted_vars[max(1, 3*n//4):])
    
    if noise_var <= 0:
        return 0.0
    
    snr = 10 * np.log10(signal_var / noise_var)
    return round(snr, 2)


def compute_entropy(image, bins=256):
    """
    Compute Shannon entropy of the image histogram.
    
    High entropy = diverse pixel values = rich content.
    Low entropy = uniform/flat = noise or blank.
    
    Returns: entropy in bits
    """
    hist, _ = np.histogram(image.flatten(), bins=bins, range=(0, 255))
    hist = hist[hist > 0]  # remove zeros
    probs = hist / hist.sum()
    entropy = -np.sum(probs * np.log2(probs))
    return round(entropy, 3)


def detect_edges(image, threshold=30):
    """
    Simple edge detection using Sobel-like gradient.
    
    Real satellite imagery has edges (coastlines, cloud boundaries).
    Pure noise has uniformly low gradient everywhere.
    
    Returns: fraction of pixels that are edges (0.0 - 1.0)
    """
    # Horizontal and vertical gradients
    gx = np.abs(np.diff(image, axis=1))
    gy = np.abs(np.diff(image, axis=0))
    
    # Trim to same size
    min_h = min(gx.shape[0], gy.shape[0])
    min_w = min(gx.shape[1], gy.shape[1])
    gx = gx[:min_h, :min_w]
    gy = gy[:min_h, :min_w]
    
    gradient_mag = np.sqrt(gx**2 + gy**2)
    edge_pixels = np.sum(gradient_mag > threshold)
    total_pixels = gradient_mag.size
    
    edge_density = edge_pixels / total_pixels if total_pixels > 0 else 0
    return round(edge_density, 4)


def detect_interference_pattern(image):
    """
    Detect periodic interference patterns (diagonal stripes, moiré).
    
    Uses 2D FFT to find strong periodic components that indicate
    USB noise injection or clock interference.
    
    Returns: interference_score (0.0 = clean, 1.0 = heavy interference)
    """
    # Downsample for speed
    h, w = image.shape
    step = max(1, min(h, w) // 256)
    small = image[::step, ::step]
    
    # 2D FFT
    fft = np.fft.fft2(small)
    fft_shift = np.fft.fftshift(fft)
    magnitude = np.abs(fft_shift)
    
    # Suppress DC component
    cy, cx = magnitude.shape[0] // 2, magnitude.shape[1] // 2
    magnitude[cy-2:cy+3, cx-2:cx+3] = 0
    
    # Normalize
    if magnitude.max() > 0:
        magnitude = magnitude / magnitude.max()
    
    # Strong spectral peaks indicate periodic interference
    # Count pixels above 0.3 of max (excluding DC)
    strong_peaks = np.sum(magnitude > 0.3)
    total = magnitude.size
    
    # Normalize: a few peaks is normal (image features), many = interference
    score = min(1.0, strong_peaks / (total * 0.001))
    return round(score, 3)


def analyze_sync_quality(image, metadata=None):
    """
    Analyze APT sync pulse quality from the decoded image.
    
    In a good APT decode, the left edge of the image shows
    consistent sync bars. In a bad decode, they're missing or noisy.
    
    Returns: sync_quality score (0.0 - 1.0)
    """
    if metadata and metadata.get('decoder') == 'LRPT':
        # LRPT doesn't have visual sync bars
        return None
    
    h, w = image.shape
    if w < 100:
        return 0.0
    
    # APT sync is in the first ~40 pixels of each line
    sync_region = image[:, :40]
    
    if sync_region.size == 0:
        return 0.0
    
    # Good sync = high contrast, periodic pattern in sync region
    # Compute row-to-row correlation in sync region
    if h < 3:
        return 0.0
    
    correlations = []
    for i in range(1, min(h, 100)):
        corr = np.corrcoef(sync_region[i-1], sync_region[i])[0, 1]
        if not np.isnan(corr):
            correlations.append(corr)
    
    if not correlations:
        return 0.0
    
    # High mean correlation in sync region = good sync lock
    mean_corr = np.mean(correlations)
    score = max(0, min(1, (mean_corr + 1) / 2))  # map [-1,1] to [0,1]
    return round(score, 3)


def grade_quality(snr_db, entropy, edge_density, interference, sync_quality=None,
                  metadata=None):
    """
    Assign an overall quality grade based on all metrics.
    
    Grades:
      GOOD     — Clear satellite imagery with visible features
      MARGINAL — Some signal present but noisy/partial
      NOISE    — No useful image content
      
    Returns: (grade, confidence, reasons)
    """
    reasons = []
    scores = []  # 0 = bad, 1 = good
    
    # SNR scoring
    if snr_db >= GRADE_THRESHOLDS['snr_good']:
        scores.append(1.0)
        reasons.append(f'SNR {snr_db:.1f} dB (good)')
    elif snr_db >= GRADE_THRESHOLDS['snr_marginal']:
        scores.append(0.5)
        reasons.append(f'SNR {snr_db:.1f} dB (marginal)')
    else:
        scores.append(0.0)
        reasons.append(f'SNR {snr_db:.1f} dB (poor)')
    
    # Entropy scoring
    if entropy >= GRADE_THRESHOLDS['entropy_good']:
        scores.append(1.0)
        reasons.append(f'Entropy {entropy:.2f} bits (rich content)')
    elif entropy >= GRADE_THRESHOLDS['entropy_marginal']:
        scores.append(0.5)
        reasons.append(f'Entropy {entropy:.2f} bits (some content)')
    else:
        scores.append(0.0)
        reasons.append(f'Entropy {entropy:.2f} bits (flat/noisy)')
    
    # Edge density scoring
    if edge_density >= GRADE_THRESHOLDS['edge_good']:
        scores.append(1.0)
        reasons.append(f'Edge density {edge_density:.3f} (features detected)')
    elif edge_density >= GRADE_THRESHOLDS['edge_marginal']:
        scores.append(0.5)
        reasons.append(f'Edge density {edge_density:.3f} (weak features)')
    else:
        scores.append(0.0)
        reasons.append(f'Edge density {edge_density:.3f} (no features)')
    
    # Interference penalty
    if interference > 0.5:
        scores.append(0.0)
        reasons.append(f'Interference {interference:.2f} (strong periodic pattern)')
    elif interference > 0.2:
        scores.append(0.5)
        reasons.append(f'Interference {interference:.2f} (mild pattern)')
    else:
        scores.append(1.0)
        reasons.append(f'Interference {interference:.2f} (clean)')
    
    # Sync quality (APT only)
    if sync_quality is not None:
        if sync_quality > 0.7:
            scores.append(1.0)
            reasons.append(f'Sync quality {sync_quality:.2f} (locked)')
        elif sync_quality > 0.4:
            scores.append(0.5)
            reasons.append(f'Sync quality {sync_quality:.2f} (partial)')
        else:
            scores.append(0.0)
            reasons.append(f'Sync quality {sync_quality:.2f} (no lock)')
    
    # Sync pulse count from metadata
    if metadata:
        sync_count = metadata.get('sync_pulses_found', metadata.get('frames_found', 0))
        duration = metadata.get('duration_sec', 0)
        if duration > 0 and sync_count > 0:
            # Expected ~2 syncs/sec for APT, varies for LRPT
            expected = duration * 2 if metadata.get('decoder', 'APT') == 'APT' else duration * 0.5
            sync_ratio = sync_count / max(1, expected)
            if sync_ratio > 0.5:
                reasons.append(f'Sync coverage {sync_ratio:.0%} ({sync_count} found)')
            else:
                reasons.append(f'Sync coverage {sync_ratio:.0%} ({sync_count}/{int(expected)} expected)')
    
    # Compute overall score
    avg_score = np.mean(scores)
    
    if avg_score >= 0.7:
        grade = 'GOOD'
    elif avg_score >= 0.35:
        grade = 'MARGINAL'
    else:
        grade = 'NOISE'
    
    confidence = round(avg_score, 2)
    
    return grade, confidence, reasons


def estimate_quality(image_path, metadata_path=None):
    """
    Main quality estimation function.
    
    Args:
        image_path: Path to decoded image (PNG/JPG)
        metadata_path: Optional path to decode metadata JSON
    
    Returns: dict with all metrics, grade, and reasons
    """
    # Load image
    image = load_image(image_path)
    if image is None:
        return {'error': 'Could not load image', 'grade': 'UNKNOWN'}
    
    # Load metadata if available
    metadata = None
    if metadata_path and os.path.exists(metadata_path):
        with open(metadata_path) as f:
            metadata = json.load(f)
    elif metadata_path is None:
        # Try to find metadata alongside image
        base = os.path.splitext(image_path)[0]
        for suffix in ['_metadata.json', '.json']:
            candidate = base.replace('_decoded', '') + suffix
            if os.path.exists(candidate):
                with open(candidate) as f:
                    metadata = json.load(f)
                break
    
    # Compute metrics
    snr = estimate_snr(image)
    entropy = compute_entropy(image)
    edges = detect_edges(image)
    interference = detect_interference_pattern(image)
    sync = analyze_sync_quality(image, metadata)
    
    # Grade
    grade, confidence, reasons = grade_quality(
        snr, entropy, edges, interference, sync, metadata
    )
    
    result = {
        'image_path': str(image_path),
        'image_shape': list(image.shape),
        'metrics': {
            'snr_db': snr,
            'entropy_bits': entropy,
            'edge_density': edges,
            'interference_score': interference,
            'sync_quality': sync,
        },
        'grade': grade,
        'confidence': confidence,
        'reasons': reasons,
        'metadata_used': metadata_path or 'auto-detected' if metadata else None,
    }
    
    return result


def print_report(result):
    """Pretty-print a quality report."""
    print(f"\n{'='*50}")
    print(f"  IMAGE QUALITY REPORT")
    print(f"{'='*50}")
    print(f"  Image: {result.get('image_path', '?')}")
    print(f"  Shape: {result.get('image_shape', '?')}")
    print()
    
    metrics = result.get('metrics', {})
    print(f"  SNR:           {metrics.get('snr_db', '?')} dB")
    print(f"  Entropy:       {metrics.get('entropy_bits', '?')} bits")
    print(f"  Edge Density:  {metrics.get('edge_density', '?')}")
    print(f"  Interference:  {metrics.get('interference_score', '?')}")
    if metrics.get('sync_quality') is not None:
        print(f"  Sync Quality:  {metrics.get('sync_quality')}")
    
    grade = result.get('grade', '?')
    conf = result.get('confidence', 0)
    
    # Color-code grade
    grade_colors = {'GOOD': '\033[92m', 'MARGINAL': '\033[93m', 'NOISE': '\033[91m'}
    color = grade_colors.get(grade, '')
    reset = '\033[0m' if color else ''
    
    print(f"\n  Grade: {color}{grade}{reset} (confidence: {conf})")
    print()
    for reason in result.get('reasons', []):
        print(f"    • {reason}")
    print(f"{'='*50}\n")


# CLI entry point
if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python quality_estimator.py <decoded_image.png> [metadata.json]")
        print()
        print("Estimates decoded satellite image quality and assigns a grade.")
        print("  GOOD     — Clear imagery with visible features")
        print("  MARGINAL — Some signal but noisy or partial")
        print("  NOISE    — No useful content")
        print()
        print("Examples:")
        print("  python quality_estimator.py data/decoded/NOAA_19_decoded.png")
        print("  python quality_estimator.py decoded.png metadata.json")
        sys.exit(1)
    
    image_path = sys.argv[1]
    metadata_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    if not os.path.exists(image_path):
        print(f"ERROR: Image not found: {image_path}")
        sys.exit(1)
    
    result = estimate_quality(image_path, metadata_path)
    print_report(result)
    
    # Save result JSON alongside image
    out_path = os.path.splitext(image_path)[0] + '_quality.json'
    with open(out_path, 'w') as f:
        json.dump(result, f, indent=2)
    print(f"Saved: {out_path}")
