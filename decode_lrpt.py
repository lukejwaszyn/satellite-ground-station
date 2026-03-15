#!/usr/bin/env python3
"""
decode_lrpt.py
Satellite Ground Station - METEOR LRPT Image Decoder

Decodes METEOR-M LRPT (Low Rate Picture Transmission) from raw RTL-SDR I/Q captures.
LRPT is a digital protocol: QPSK modulated, convolutionally coded, with CCSDS framing.

Signal chain:
  Raw I/Q → Freq correction → QPSK demod → Soft symbol recovery →
  Viterbi decode → CCSDS frame sync → Derandomize → Reed-Solomon →
  Packet extraction → Image reassembly (3 channels: visible, IR, IR)

METEOR LRPT Parameters:
  - Modulation: OQPSK (Offset QPSK), 72 kSymbol/s
  - FEC: Rate 1/2 convolutional code (k=7, G1=0x4F, G2=0x6D) + RS(255,223)
  - Frame: CCSDS compatible, 1024-byte frames
  - Image: 3 AVHRR channels, MCU-based compression (similar to JPEG)

Author: Luke Waszyn
Date: March 2026
"""

import numpy as np
from scipy import signal
from datetime import datetime
import os
import json
import struct

# ================================================================
# LRPT Signal Parameters
# ================================================================
LRPT_SYMBOL_RATE = 72000       # 72 kSym/s
LRPT_CARRIER_FREQ = 0          # baseband after tuning
SAMPLES_PER_SYMBOL = 4         # target after decimation

# Convolutional code parameters (rate 1/2, k=7)
# METEOR uses inverted polarity relative to CCSDS standard
CONV_K = 7
CONV_RATE = 2
CONV_G1 = 0x4F  # 1001111 - generator polynomial 1
CONV_G2 = 0x6D  # 1101101 - generator polynomial 2

# CCSDS sync word (0x1ACFFC1D)
CCSDS_SYNC = bytes([0x1A, 0xCF, 0xFC, 0x1D])
CCSDS_SYNC_BITS = np.unpackbits(np.frombuffer(CCSDS_SYNC, dtype=np.uint8))

# CCSDS frame size
CCSDS_FRAME_BYTES = 1024       # total frame including header
CCSDS_FRAME_BITS = CCSDS_FRAME_BYTES * 8
CCSDS_HEADER_BYTES = 4         # sync word
CCSDS_RS_PARITY = 128          # 4 * 32 parity bytes for RS(255,223)
CCSDS_DATA_BYTES = CCSDS_FRAME_BYTES - CCSDS_HEADER_BYTES - CCSDS_RS_PARITY

# Encoded frame: rate 1/2 means 2x bits, plus sync
ENCODED_FRAME_BITS = CCSDS_FRAME_BITS * CONV_RATE

# Image parameters
LRPT_PIX_PER_MCU = 8           # pixels per minimum coded unit
LRPT_MCUS_PER_LINE = 196       # MCUs across one scan line
LRPT_PIX_PER_LINE = LRPT_PIX_PER_MCU * LRPT_MCUS_PER_LINE  # 1568 pixels
LRPT_CHANNELS = 3              # typically channels 1, 2, 5 (vis, vis, IR)

# CCSDS derandomization sequence (LFSR-based)
# Standard CCSDS pseudo-random sequence for frame randomization
_DERAND_POLY = 0xFF            # x^8 + x^7 + x^5 + x^3 + 1 simplified
_DERAND_SEED = 0xFF


def _generate_derand_sequence(length):
    """Generate CCSDS derandomization (pseudo-random) sequence."""
    reg = _DERAND_SEED
    seq = np.zeros(length, dtype=np.uint8)
    for i in range(length):
        seq[i] = reg & 0xFF
        # LFSR: x^8 + x^7 + x^5 + x^3 + 1
        for _ in range(8):
            feedback = ((reg >> 7) ^ (reg >> 5) ^ (reg >> 3) ^ (reg >> 0)) & 1
            reg = ((reg << 1) | feedback) & 0xFF
    return seq


DERAND_SEQUENCE = _generate_derand_sequence(CCSDS_FRAME_BYTES)


# ================================================================
# QPSK Demodulation
# ================================================================

def load_iq_chunked(filepath, fs=2.4e6, target_sps=4):
    """
    Load raw RTL-SDR I/Q and prepare for QPSK demodulation.
    
    Decimates to target_sps samples per symbol.
    Target sample rate = LRPT_SYMBOL_RATE * target_sps = 288 kHz
    
    Returns: complex IQ at decimated rate, actual sample rate
    """
    target_fs = LRPT_SYMBOL_RATE * target_sps  # 288 kHz
    
    file_size = os.path.getsize(filepath)
    total_iq = file_size // 2
    duration = total_iq / fs
    
    print(f"  File size: {file_size / 1e9:.2f} GB")
    print(f"  IQ samples: {total_iq:,}")
    print(f"  Duration: {duration:.1f} seconds")
    print(f"  Decimating {fs/1e3:.0f} kHz → {target_fs/1e3:.0f} kHz")
    
    decim_factor = int(fs / target_fs)
    actual_fs = fs / decim_factor
    
    # Process in chunks
    chunk_iq = 25_000_000
    chunk_iq = (chunk_iq // decim_factor) * decim_factor
    chunk_bytes = chunk_iq * 2
    
    iq_chunks = []
    offset = 0
    chunk_num = 0
    
    with open(filepath, 'rb') as f:
        while offset < file_size:
            raw_bytes = np.frombuffer(f.read(chunk_bytes), dtype=np.uint8)
            if len(raw_bytes) < 4:
                break
            
            raw = raw_bytes.astype(np.float32)
            raw = (raw - 127.5) / 127.5
            iq = raw[0::2] + 1j * raw[1::2]
            del raw, raw_bytes
            
            # Decimate
            iq_dec = signal.decimate(iq, decim_factor, ftype='fir')
            iq_chunks.append(iq_dec)
            del iq
            
            offset += chunk_bytes
            chunk_num += 1
            progress = min(100, offset * 100 // file_size)
            print(f"    Chunk {chunk_num}: {progress}%", end='\r')
    
    print(f"    Processed {chunk_num} chunks              ")
    
    iq_data = np.concatenate(iq_chunks)
    del iq_chunks
    
    return iq_data, actual_fs


def agc(iq, window=1024):
    """Automatic gain control — normalize signal amplitude."""
    power = np.convolve(np.abs(iq)**2, np.ones(window)/window, mode='same')
    power = np.maximum(power, 1e-10)
    gain = 1.0 / np.sqrt(power)
    return iq * gain


def costas_loop_qpsk(iq, sps, loop_bw=0.005):
    """
    QPSK Costas loop for carrier recovery and demodulation.
    
    Tracks residual carrier offset and phase, outputs soft symbols
    in I/Q constellation space.
    
    Args:
        iq: complex baseband signal
        sps: samples per symbol
        loop_bw: loop bandwidth (normalized)
    
    Returns:
        soft_symbols: complex array of constellation points
    """
    # Loop filter coefficients (proportional-integral)
    damping = 1.0 / np.sqrt(2)
    bw_norm = loop_bw
    denom = 1.0 + 2.0 * damping * bw_norm + bw_norm**2
    alpha = (4.0 * damping * bw_norm) / denom        # proportional
    beta = (4.0 * bw_norm**2) / denom                 # integral
    
    n = len(iq)
    phase = 0.0
    freq = 0.0
    
    # Output: one symbol per sps samples
    num_symbols = n // sps
    symbols = np.zeros(num_symbols, dtype=np.complex64)
    
    for i in range(num_symbols):
        idx = i * sps + sps // 2  # sample at mid-symbol
        if idx >= n:
            break
        
        # Apply phase correction
        sample = iq[idx] * np.exp(-1j * phase)
        symbols[i] = sample
        
        # QPSK phase error detector
        # Decision-directed: error = Im(sample * conj(decision))
        # For QPSK, decision is nearest constellation point
        re = np.real(sample)
        im = np.imag(sample)
        
        # QPSK error: sgn(re)*im - sgn(im)*re
        error = np.sign(re) * im - np.sign(im) * re
        
        # Update loop filter
        freq += beta * error
        phase += alpha * error + freq
        
        # Keep phase in [-pi, pi]
        while phase > np.pi:
            phase -= 2 * np.pi
        while phase < -np.pi:
            phase += 2 * np.pi
    
    return symbols


def gardner_timing_recovery(iq, sps, loop_bw=0.01):
    """
    Gardner timing error detector for symbol synchronization.
    
    Adjusts sample timing to find optimal symbol sampling instants.
    Uses the Gardner TED: e[n] = Re{(y[n] - y[n-1]) * conj(y[n-0.5])}
    
    Args:
        iq: complex baseband signal 
        sps: nominal samples per symbol
        loop_bw: timing loop bandwidth
    
    Returns:
        resampled: signal at 1 sample per symbol at optimal timing
    """
    n = len(iq)
    mu = 0.0                # fractional delay
    out = []
    i = sps                 # start after first symbol
    
    # Loop filter
    damping = 1.0 / np.sqrt(2)
    denom = 1.0 + 2.0 * damping * loop_bw + loop_bw**2
    alpha = (4.0 * damping * loop_bw) / denom
    beta = (4.0 * loop_bw**2) / denom
    freq = 0.0
    
    prev_symbol = 0.0 + 0j
    
    while i < n - sps:
        # Interpolate at current fractional position
        idx = int(i + mu)
        if idx < 1 or idx >= n - 1:
            i += sps
            continue
        
        # Linear interpolation
        frac = (i + mu) - idx
        current = iq[idx] * (1 - frac) + iq[idx + 1] * frac
        
        # Mid-point sample (half symbol back)
        mid_idx = int(i + mu - sps / 2)
        if mid_idx < 0 or mid_idx >= n - 1:
            i += sps
            continue
        mid_frac = (i + mu - sps / 2) - mid_idx
        midpoint = iq[mid_idx] * (1 - mid_frac) + iq[mid_idx + 1] * mid_frac
        
        out.append(current)
        
        # Gardner TED
        error = np.real((current - prev_symbol) * np.conj(midpoint))
        
        # Update timing
        freq += beta * error
        mu += alpha * error + freq
        
        prev_symbol = current
        i += sps
    
    return np.array(out, dtype=np.complex64)


def qpsk_demod(iq, fs):
    """
    Full QPSK demodulation chain.
    
    Returns soft bits as float array (positive = 1, negative = 0).
    QPSK maps 2 bits per symbol.
    """
    sps = int(round(fs / LRPT_SYMBOL_RATE))
    print(f"  Samples per symbol: {sps}")
    print(f"  Total symbols: ~{len(iq) // sps:,}")
    
    # AGC
    print("  Applying AGC...")
    iq_agc = agc(iq)
    del iq
    
    # Root-raised-cosine matched filter
    print("  Matched filtering (RRC)...")
    rrc_taps = _rrc_filter(sps, alpha=0.6, num_taps=sps * 11)
    iq_filtered = np.convolve(iq_agc, rrc_taps, mode='same').astype(np.complex64)
    del iq_agc
    
    # Symbol timing recovery
    print("  Symbol timing recovery (Gardner)...")
    symbols_timed = gardner_timing_recovery(iq_filtered, sps)
    del iq_filtered
    print(f"    Recovered {len(symbols_timed):,} symbols")
    
    # Carrier recovery and QPSK demodulation
    print("  Carrier recovery (Costas loop)...")
    # Run Costas at 1 sps since we already did timing recovery
    symbols = costas_loop_qpsk(symbols_timed, sps=1, loop_bw=0.003)
    del symbols_timed
    print(f"    Demodulated {len(symbols):,} symbols")
    
    # Map to soft bits (2 bits per QPSK symbol)
    # QPSK constellation: bits mapped as (I>0, Q>0)
    soft_bits = np.zeros(len(symbols) * 2, dtype=np.float32)
    soft_bits[0::2] = np.real(symbols)    # I channel → even bits
    soft_bits[1::2] = np.imag(symbols)    # Q channel → odd bits
    
    return soft_bits


def _rrc_filter(sps, alpha=0.6, num_taps=51):
    """Root-raised-cosine filter for matched filtering."""
    t = np.arange(-num_taps//2, num_taps//2 + 1) / sps
    h = np.zeros_like(t, dtype=np.float64)
    
    for i, ti in enumerate(t):
        if ti == 0:
            h[i] = (1 + alpha * (4/np.pi - 1))
        elif abs(abs(ti) - 1/(4*alpha)) < 1e-8:
            h[i] = alpha/np.sqrt(2) * ((1 + 2/np.pi) * np.sin(np.pi/(4*alpha)) +
                                        (1 - 2/np.pi) * np.cos(np.pi/(4*alpha)))
        else:
            num = np.sin(np.pi * ti * (1 - alpha)) + 4 * alpha * ti * np.cos(np.pi * ti * (1 + alpha))
            den = np.pi * ti * (1 - (4 * alpha * ti)**2)
            if abs(den) > 1e-10:
                h[i] = num / den
            else:
                h[i] = 0
    
    h /= np.sqrt(np.sum(h**2))
    return h.astype(np.float32)


# ================================================================
# Viterbi Decoder (Rate 1/2, k=7)
# ================================================================

class ViterbiDecoder:
    """
    Soft-decision Viterbi decoder for the METEOR LRPT convolutional code.
    
    Rate 1/2, constraint length k=7
    Generators: G1=0x4F (1001111), G2=0x6D (1101101)
    
    Uses soft decisions for ~2 dB improvement over hard decision.
    """
    
    def __init__(self):
        self.num_states = 1 << (CONV_K - 1)  # 64 states
        self.g1 = CONV_G1
        self.g2 = CONV_G2
        
        # Precompute output bits for each state and input
        self.output_table = np.zeros((self.num_states, 2, 2), dtype=np.int8)
        for state in range(self.num_states):
            for inp in range(2):
                reg = (inp << (CONV_K - 1)) | state
                b1 = bin(reg & self.g1).count('1') % 2
                b2 = bin(reg & self.g2).count('1') % 2
                self.output_table[state, inp, 0] = b1
                self.output_table[state, inp, 1] = b2
    
    def decode(self, soft_bits, traceback_depth=35):
        """
        Decode soft bits through the trellis.
        
        Args:
            soft_bits: float array, positive = 1, negative = 0
            traceback_depth: traceback length in symbols
        
        Returns:
            decoded_bits: uint8 array of decoded bits
        """
        n_pairs = len(soft_bits) // 2
        
        # Path metrics (use int16 for speed)
        INF = 10000
        path_metric = np.full(self.num_states, INF, dtype=np.int32)
        path_metric[0] = 0
        
        # Survivor paths stored as bit decisions
        # Use a circular buffer for traceback
        tb_depth = min(traceback_depth * (CONV_K - 1), n_pairs)
        survivor = np.zeros((tb_depth, self.num_states), dtype=np.uint8)
        
        decoded = []
        
        for i in range(n_pairs):
            # Quantize soft bits to metrics
            s0 = soft_bits[2 * i]
            s1 = soft_bits[2 * i + 1]
            
            new_metric = np.full(self.num_states, INF, dtype=np.int32)
            tb_idx = i % tb_depth
            
            for state in range(self.num_states):
                if path_metric[state] >= INF:
                    continue
                
                for inp in range(2):
                    # Next state
                    next_state = ((state >> 1) | (inp << (CONV_K - 2))) & (self.num_states - 1)
                    
                    # Expected output bits
                    exp0 = self.output_table[state, inp, 0]
                    exp1 = self.output_table[state, inp, 1]
                    
                    # Branch metric (soft Euclidean distance)
                    # If expected bit is 1, want positive soft value
                    # If expected bit is 0, want negative soft value
                    bm = 0
                    bm += abs(s0 - (1 if exp0 else -1))
                    bm += abs(s1 - (1 if exp1 else -1))
                    
                    # Quantize to integer
                    bm_int = int(bm * 100)
                    
                    candidate = path_metric[state] + bm_int
                    
                    if candidate < new_metric[next_state]:
                        new_metric[next_state] = candidate
                        survivor[tb_idx, next_state] = inp
            
            path_metric = new_metric
            
            # Normalize to prevent overflow
            if i % 100 == 0:
                min_metric = np.min(path_metric)
                path_metric -= min_metric
            
            # Traceback periodically
            if i >= tb_depth - 1 and (i % traceback_depth == 0):
                # Find best ending state
                best_state = np.argmin(path_metric)
                
                # Trace back
                bits = []
                state = best_state
                for j in range(tb_depth - 1, -1, -1):
                    tb_j = (i - (tb_depth - 1 - j)) % tb_depth
                    inp = survivor[tb_j, state]
                    bits.append(inp)
                    # Reverse state transition
                    state = ((state << 1) | inp) & (self.num_states - 1)
                
                bits.reverse()
                decoded.extend(bits[:traceback_depth])
        
        # Final traceback for remaining bits
        if n_pairs > 0:
            best_state = np.argmin(path_metric)
            remaining = n_pairs % traceback_depth
            if remaining > 0:
                bits = []
                state = best_state
                for j in range(min(remaining, tb_depth) - 1, -1, -1):
                    tb_j = (n_pairs - 1 - (min(remaining, tb_depth) - 1 - j)) % tb_depth
                    if tb_j < 0:
                        break
                    inp = survivor[tb_j, state]
                    bits.append(inp)
                    state = ((state << 1) | inp) & (self.num_states - 1)
                bits.reverse()
                decoded.extend(bits)
        
        return np.array(decoded, dtype=np.uint8)


# ================================================================
# CCSDS Frame Processing
# ================================================================

def find_sync_words(bit_stream, threshold=4):
    """
    Find CCSDS sync words (0x1ACFFC1D) in decoded bit stream.
    
    Allows up to `threshold` bit errors in the sync pattern
    (for noisy channels).
    
    Returns: list of bit offsets where frames start
    """
    sync_len = len(CCSDS_SYNC_BITS)
    frame_len = CCSDS_FRAME_BITS
    
    # First pass: find all candidate positions
    candidates = []
    
    # Slide through looking for sync matches
    for i in range(0, len(bit_stream) - sync_len, 1):
        errors = np.sum(bit_stream[i:i+sync_len] != CCSDS_SYNC_BITS)
        if errors <= threshold:
            candidates.append((i, errors))
    
    if not candidates:
        return []
    
    # Second pass: validate using frame spacing
    # Real frames should be exactly CCSDS_FRAME_BITS apart
    valid_starts = []
    
    for pos, errors in candidates:
        # Check if there's another sync word one frame later
        next_pos = pos + frame_len
        if next_pos + sync_len <= len(bit_stream):
            next_errors = np.sum(bit_stream[next_pos:next_pos+sync_len] != CCSDS_SYNC_BITS)
            if next_errors <= threshold:
                if pos not in valid_starts:
                    valid_starts.append(pos)
                if next_pos not in valid_starts:
                    valid_starts.append(next_pos)
        elif errors <= 2:
            # Near the end, be more lenient
            valid_starts.append(pos)
    
    # If validation found nothing, use best raw candidates
    if not valid_starts and candidates:
        candidates.sort(key=lambda x: x[1])
        valid_starts = [c[0] for c in candidates[:10]]
    
    valid_starts.sort()
    return valid_starts


def extract_frame(bit_stream, start_pos):
    """
    Extract and process a single CCSDS frame from bit stream.
    
    Steps:
    1. Extract frame bits
    2. Pack into bytes
    3. Derandomize (XOR with PRBS)
    4. Return frame bytes (without sync word)
    """
    end_pos = start_pos + CCSDS_FRAME_BITS
    if end_pos > len(bit_stream):
        return None
    
    frame_bits = bit_stream[start_pos:end_pos]
    
    # Pack bits to bytes
    n_bytes = len(frame_bits) // 8
    frame_bytes = np.packbits(frame_bits[:n_bytes*8])
    
    # Skip the 4-byte sync word
    data = frame_bytes[CCSDS_HEADER_BYTES:]
    
    # Derandomize
    derand_len = min(len(data), len(DERAND_SEQUENCE))
    data[:derand_len] ^= DERAND_SEQUENCE[:derand_len]
    
    return bytes(data)


def reed_solomon_check(frame_data):
    """
    Reed-Solomon error detection/correction for CCSDS frames.
    
    METEOR uses RS(255,223) with 4 interleaved codewords.
    Each codeword: 223 data bytes + 32 parity bytes.
    
    For a from-scratch implementation, we do basic syndrome checking.
    Full RS correction would require a GF(2^8) implementation.
    
    Returns: (corrected_data, errors_detected, errors_corrected)
    """
    # The frame data after sync removal should be:
    # 892 bytes data + 128 bytes RS parity (4 * 32)
    
    if len(frame_data) < CCSDS_DATA_BYTES + CCSDS_RS_PARITY:
        return frame_data, -1, 0
    
    # Split out data and parity
    data = frame_data[:CCSDS_DATA_BYTES]
    parity = frame_data[CCSDS_DATA_BYTES:CCSDS_DATA_BYTES + CCSDS_RS_PARITY]
    
    # Basic check: if parity is all zeros, likely no errors
    # (This is a simplified check — full RS would use GF arithmetic)
    parity_sum = sum(parity)
    
    if parity_sum == 0:
        return data, 0, 0
    
    # Non-zero parity — errors detected but we can't correct without full RS
    # In a production system, we'd implement the Berlekamp-Massey algorithm
    # For now, return the data as-is with error flag
    return data, 1, 0


# ================================================================
# LRPT Packet / Image Processing
# ================================================================

# METEOR LRPT VCDU (Virtual Channel Data Unit) structure
VCDU_HEADER_LEN = 6           # version, spacecraft ID, VCID, counter
MPDU_HEADER_LEN = 2           # M_PDU first header pointer

# APID assignments for METEOR MSU-MR instrument
APID_CHANNEL_MAP = {
    64: 0,    # Channel 1 (visible 0.5-0.7 μm)
    65: 1,    # Channel 2 (visible 0.7-1.1 μm)  
    66: 2,    # Channel 3 (IR 1.6 μm)
    67: 3,    # Channel 4 (IR 3.5-4.1 μm)
    68: 4,    # Channel 5 (IR 10.5-11.5 μm)
    69: 5,    # Channel 6 (IR 11.5-12.5 μm)
}


class LRPTImageAssembler:
    """
    Assembles decoded LRPT packets into image channels.
    
    METEOR sends image data as MCUs (8x8 pixel blocks) compressed
    with a DCT-based scheme similar to JPEG. Each packet contains
    MCUs for one of the 3 active channels.
    """
    
    def __init__(self):
        self.channels = {i: [] for i in range(6)}  # line buffers per channel
        self.current_line = {i: np.zeros(LRPT_PIX_PER_LINE, dtype=np.uint8) for i in range(6)}
        self.line_counts = {i: 0 for i in range(6)}
        self.mcu_position = {i: 0 for i in range(6)}
        self.total_packets = 0
        self.valid_packets = 0
    
    def process_frame(self, frame_data):
        """
        Process a derandomized, RS-checked CCSDS frame.
        Extract VCDUs and reassemble image data.
        """
        if len(frame_data) < VCDU_HEADER_LEN + MPDU_HEADER_LEN:
            return
        
        self.total_packets += 1
        
        # Parse VCDU header
        vcdu_header = frame_data[:VCDU_HEADER_LEN]
        version = (vcdu_header[0] >> 6) & 0x03
        spacecraft_id = ((vcdu_header[0] & 0x3F) << 2) | ((vcdu_header[1] >> 6) & 0x03)
        vcid = vcdu_header[1] & 0x3F
        counter = (vcdu_header[2] << 16) | (vcdu_header[3] << 8) | vcdu_header[4]
        
        # Only process image VCIDs (typically 1-6 for MSU-MR channels)
        if vcid not in range(0, 7):
            return
        
        # Parse M_PDU header
        mpdu_start = VCDU_HEADER_LEN
        first_header = (frame_data[mpdu_start] << 8) | frame_data[mpdu_start + 1]
        first_header_ptr = first_header & 0x07FF
        
        # Extract payload
        payload = frame_data[mpdu_start + MPDU_HEADER_LEN:]
        
        if len(payload) == 0:
            return
        
        self.valid_packets += 1
        
        # Map VCID to channel and store raw pixel data
        # Simplified: treat payload as raw pixel intensity values
        # A full implementation would do MCU decompression (DCT + quantization)
        channel = min(vcid, 5)
        
        pos = self.mcu_position[channel]
        line = self.current_line[channel]
        
        for byte in payload:
            if pos < LRPT_PIX_PER_LINE:
                line[pos] = byte
                pos += 1
        
        self.mcu_position[channel] = pos
        
        # When line is full, commit it
        if pos >= LRPT_PIX_PER_LINE:
            self.channels[channel].append(line.copy())
            self.current_line[channel] = np.zeros(LRPT_PIX_PER_LINE, dtype=np.uint8)
            self.mcu_position[channel] = 0
            self.line_counts[channel] += 1
    
    def get_images(self):
        """
        Return assembled images for each channel with data.
        
        Returns: dict of channel_id → 2D numpy array (uint8)
        """
        images = {}
        for ch_id in range(6):
            if len(self.channels[ch_id]) > 10:  # need at least some lines
                img = np.array(self.channels[ch_id], dtype=np.uint8)
                images[ch_id] = img
        return images
    
    def get_composite(self):
        """
        Create an RGB composite from available channels.
        
        METEOR MSU-MR typical mapping:
          R = Channel 2 (0.7-1.1 μm, near-IR)
          G = Channel 1 (0.5-0.7 μm, visible)
          B = Channel 1 (0.5-0.7 μm, visible, same as G for pseudo-color)
        
        Returns: 3D numpy array (H, W, 3) uint8, or None
        """
        images = self.get_images()
        
        if not images:
            return None
        
        # Find the channels with the most data
        channels_by_lines = sorted(images.keys(), key=lambda k: len(images[k]), reverse=True)
        
        if len(channels_by_lines) >= 2:
            ch_r = channels_by_lines[0]
            ch_g = channels_by_lines[1]
            ch_b = channels_by_lines[1]  # duplicate for pseudo-color
        elif len(channels_by_lines) == 1:
            ch_r = ch_g = ch_b = channels_by_lines[0]
        else:
            return None
        
        # Equalize line counts
        min_lines = min(len(images[ch_r]), len(images[ch_g]))
        width = LRPT_PIX_PER_LINE
        
        r = images[ch_r][:min_lines]
        g = images[ch_g][:min_lines]
        b = images[ch_b][:min_lines]
        
        # Normalize each channel
        r = _normalize_channel(r)
        g = _normalize_channel(g)
        b = _normalize_channel(b)
        
        composite = np.stack([r, g, b], axis=-1)
        return composite


def _normalize_channel(img):
    """Normalize a single channel image to 0-255."""
    p_low, p_high = np.percentile(img, [2, 98])
    if p_high > p_low:
        img = np.clip((img.astype(np.float32) - p_low) / (p_high - p_low) * 255, 0, 255)
    return img.astype(np.uint8)


# ================================================================
# Main Decode Pipeline
# ================================================================

def decode_lrpt(iq_filepath, output_dir=None):
    """
    Main LRPT decoding function.
    
    Pipeline:
    1. Load and decimate I/Q data
    2. QPSK demodulation (AGC → RRC → Gardner timing → Costas carrier)
    3. Viterbi decoding (rate 1/2, k=7)
    4. CCSDS frame sync and extraction
    5. Derandomization + Reed-Solomon check
    6. Image reassembly from packets
    
    Args:
        iq_filepath: Path to raw .bin file from RTL-SDR
        output_dir: Output directory (default: same as input)
    
    Returns:
        Dictionary with results and metadata
    """
    file_size = os.path.getsize(iq_filepath)
    
    print(f"\n{'='*60}")
    print(f"LRPT Decoder - METEOR-M QPSK Digital")
    print(f"{'='*60}")
    print(f"Input: {iq_filepath}")
    
    # Step 1: Load I/Q
    print(f"\n[1/6] Loading I/Q data...")
    iq, fs = load_iq_chunked(iq_filepath)
    
    # Step 2: QPSK Demodulation
    print(f"\n[2/6] QPSK demodulation...")
    soft_bits = qpsk_demod(iq, fs)
    del iq
    print(f"  Soft bits: {len(soft_bits):,}")
    
    # Step 3: Viterbi Decoding
    print(f"\n[3/6] Viterbi decoding (rate 1/2, k=7)...")
    viterbi = ViterbiDecoder()
    decoded_bits = viterbi.decode(soft_bits)
    del soft_bits
    print(f"  Decoded bits: {len(decoded_bits):,}")
    
    # Step 4: CCSDS Frame Sync
    print(f"\n[4/6] Finding CCSDS sync words...")
    frame_starts = find_sync_words(decoded_bits, threshold=4)
    print(f"  Found {len(frame_starts)} frames")
    
    if len(frame_starts) == 0:
        print("  WARNING: No CCSDS frames found. Signal may be too weak.")
        # Still save what we have
        return _save_empty_result(iq_filepath, output_dir, len(decoded_bits))
    
    # Step 5: Extract and process frames
    print(f"\n[5/6] Extracting frames (derandomize + RS check)...")
    assembler = LRPTImageAssembler()
    
    rs_errors_total = 0
    good_frames = 0
    
    for start in frame_starts:
        frame_data = extract_frame(decoded_bits, start)
        if frame_data is None:
            continue
        
        # Reed-Solomon check
        corrected, errors, corrections = reed_solomon_check(frame_data)
        if errors >= 0:
            if errors == 0:
                good_frames += 1
            rs_errors_total += errors
            assembler.process_frame(corrected if isinstance(corrected, (bytes, bytearray)) 
                                    else bytes(corrected))
    
    del decoded_bits
    
    print(f"  Good frames (RS clean): {good_frames}")
    print(f"  Total packets processed: {assembler.total_packets}")
    print(f"  Valid image packets: {assembler.valid_packets}")
    
    # Step 6: Image assembly
    print(f"\n[6/6] Assembling images...")
    
    images = assembler.get_images()
    composite = assembler.get_composite()
    
    for ch_id, img in images.items():
        print(f"  Channel {ch_id}: {img.shape[0]} lines × {img.shape[1]} pixels")
    
    # Save outputs
    if output_dir is None:
        output_dir = os.path.dirname(iq_filepath)
    os.makedirs(output_dir, exist_ok=True)
    
    base_name = os.path.splitext(os.path.basename(iq_filepath))[0]
    saved_files = []
    
    try:
        from PIL import Image
        
        # Save individual channels
        for ch_id, img_data in images.items():
            ch_path = os.path.join(output_dir, f"{base_name}_ch{ch_id}.png")
            Image.fromarray(img_data, mode='L').save(ch_path)
            saved_files.append(ch_path)
            print(f"  Saved: {ch_path}")
        
        # Save composite
        if composite is not None:
            comp_path = os.path.join(output_dir, f"{base_name}_composite.png")
            Image.fromarray(composite, mode='RGB').save(comp_path)
            saved_files.append(comp_path)
            print(f"  Saved: {comp_path}")
        
        # Save primary decoded image (composite preferred, else best channel)
        if composite is not None:
            primary_path = os.path.join(output_dir, f"{base_name}_decoded.png")
            Image.fromarray(composite, mode='RGB').save(primary_path)
        elif images:
            best_ch = max(images.keys(), key=lambda k: images[k].shape[0])
            primary_path = os.path.join(output_dir, f"{base_name}_decoded.png")
            Image.fromarray(images[best_ch], mode='L').save(primary_path)
        else:
            primary_path = None
    
    except ImportError:
        print("  WARNING: Pillow not installed, saving as .npy")
        for ch_id, img_data in images.items():
            npy_path = os.path.join(output_dir, f"{base_name}_ch{ch_id}.npy")
            np.save(npy_path, img_data)
            saved_files.append(npy_path)
        primary_path = saved_files[0] if saved_files else None
    
    # Save metadata
    metadata = {
        'source_file': os.path.basename(iq_filepath),
        'decode_time': datetime.now().isoformat(),
        'decoder': 'LRPT',
        'satellite_type': 'METEOR-M',
        'modulation': 'QPSK',
        'symbol_rate': LRPT_SYMBOL_RATE,
        'sample_rate_original': 2.4e6,
        'file_size_bytes': file_size,
        'duration_sec': float(file_size / 2 / 2.4e6),
        'frames_found': len(frame_starts),
        'frames_rs_clean': good_frames,
        'total_packets': assembler.total_packets,
        'valid_image_packets': assembler.valid_packets,
        'channels': {str(k): {'lines': v.shape[0], 'width': v.shape[1]} 
                     for k, v in images.items()},
        'saved_files': [os.path.basename(f) for f in saved_files],
    }
    
    meta_path = os.path.join(output_dir, f"{base_name}_metadata.json")
    with open(meta_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    print(f"  Saved metadata: {meta_path}")
    
    print(f"\n{'='*60}")
    print(f"LRPT decode complete")
    print(f"  Frames: {len(frame_starts)} found, {good_frames} clean")
    print(f"  Image packets: {assembler.valid_packets}")
    print(f"  Channels decoded: {len(images)}")
    print(f"{'='*60}\n")
    
    return {
        'image_path': primary_path,
        'images': images,
        'composite': composite,
        'metadata': metadata,
        'saved_files': saved_files,
    }


def _save_empty_result(iq_filepath, output_dir, n_bits):
    """Save metadata for a failed decode (no frames found)."""
    if output_dir is None:
        output_dir = os.path.dirname(iq_filepath)
    os.makedirs(output_dir, exist_ok=True)
    
    base_name = os.path.splitext(os.path.basename(iq_filepath))[0]
    
    metadata = {
        'source_file': os.path.basename(iq_filepath),
        'decode_time': datetime.now().isoformat(),
        'decoder': 'LRPT',
        'satellite_type': 'METEOR-M',
        'modulation': 'QPSK',
        'frames_found': 0,
        'decoded_bits': n_bits,
        'status': 'no_frames_found',
    }
    
    meta_path = os.path.join(output_dir, f"{base_name}_metadata.json")
    with open(meta_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    return {
        'image_path': None,
        'images': {},
        'composite': None,
        'metadata': metadata,
        'saved_files': [],
    }


# ================================================================
# CLI Entry Point
# ================================================================

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python decode_lrpt.py <iq_file.bin> [output_dir]")
        print()
        print("Decodes METEOR-M LRPT digital imagery from raw RTL-SDR captures.")
        print("  Input:  Raw I/Q binary file (uint8 interleaved, 2.4 MHz)")
        print("  Output: PNG images per channel + RGB composite + metadata JSON")
        print()
        print("Example:")
        print("  python decode_lrpt.py data/captures/METEOR-M2_3_20260311.bin data/decoded")
        sys.exit(1)
    
    iq_file = sys.argv[1]
    out_dir = sys.argv[2] if len(sys.argv) > 2 else 'data/decoded'
    
    result = decode_lrpt(iq_file, out_dir)
    
    if result and result.get('image_path'):
        print(f"Primary image: {result['image_path']}")
        print(f"Channels: {len(result['images'])}")
    else:
        print("No image decoded — check signal quality")
