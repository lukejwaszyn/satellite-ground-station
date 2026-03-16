# Verification Plan

## Overview

Staged verification strategy (V0–V6) for the Autonomous Satellite Ground Station. Each stage has clear objectives, methods, pass criteria, and deliverables.

---

## V0: Orbital Prediction Validation
**Status: COMPLETE** (January 16, 2026)

Validated SGP4 propagator via Skyfield against Heavens-Above. Timing accuracy: ±15 seconds (exceeded ±30s requirement). Elevation accuracy: ±1.2° (exceeded ±2° requirement). Doppler calculation implemented and validated.

**Deliverables:** predict_passes.py, doppler_calc.py, 7-day forecast validation

---

## V0.5: SDR Environment + Mission Operations HMI
**Status: COMPLETE** (January 30 / February 25, 2026)

RTL-SDR v4 verified on macOS (Apple Silicon M4). 3D mission operations interface implemented with Skyfield SGP4 backend tracking 11 satellites across 5 constellations (NOAA, METEOR, ISS, Terra/Aqua, Landsat). NASA Blue Marble texture, signal type badges (APT/LRPT/TRACK), pass timeline, elevation/Doppler charts, mission control panel.

**Deliverables:** satellite-viz.html, generate_orbital_data.py, satcom_server.py

---

## V1: RF Link Establishment
**Status: COMPLETE** (February 27, 2026)

NOAA 18 at 89.4° elevation, 717-second pass. Full pipeline executed end-to-end: HMI capture button → REST API → C++ binary → decoder. Image was black — root cause: frontend sent default 137.1 MHz instead of NOAA 18's 137.9125 MHz. Fixed by passing satellite-specific frequency through capture chain.

**Deliverables:** First raw I/Q capture, end-to-end pipeline validation, frequency bug fix

---

## V2: LNA Integration
**Status: COMPLETE** (March 6, 2026)

Nooelec SAWbird NOAA integrated: 20 dB gain, 0.7 dB noise figure, SAW bandpass filter at 137.5 MHz. Signal power at -19 to -24 dB vs noise floor verified via spectrum scan.

**Deliverables:** A/B comparison spectrum plots, LNA integration verification

---

## V3: First Signal Decode
**Status: COMPLETE** (March 6, 2026)

NOAA 15 at 20.4°: 135 sync pulses, APT frame structure visible. NOAA 19 at 89.0°: 831 sync pulses, full-length pass decoded. Image noisy — repeating diagonal interference pattern identified as USB adapter noise. Memory-efficient chunked decoder implemented (processes 3+ GB files in ~2-3 GB RAM).

**Key bug fixed:** dtype (float32 vs uint8) in I/Q loading — was reading 1/4 of samples with garbage values.

**Deliverables:** decode_apt.py (chunked), decoded images, dtype fix documentation

---

## V3.1: USB Adapter Fix
**Status: COMPLETE** (March 12, 2026)

Replaced cheap USB-C hub with Apple USB-A to USB-C adapter. NOAA 21 at 89.7°: 287 sync pulses with real signal structure visible (vs pure noise previously). USB interference pattern eliminated. Signal drops out mid-pass — consistent with dipole antenna null at zenith.

**Deliverables:** Before/after comparison images, Apple adapter validation

---

## V3+: Clean Decoded Image
**Status: IN PROGRESS**

First decoded image with visible weather features (coastlines, cloud patterns). Blocked by antenna upgrade — dipole has polarization mismatch and zenith null. QFH antenna build in progress with Penn State Space Systems Lab.

**Pass Criteria:**
- Image shows recognizable Earth features
- Sync detection rate >90%
- Quality estimator grades image as GOOD or MARGINAL (not NOISE)

---

## V4: Automated Doppler Tracking
**Status: PLANNED**

Real-time frequency correction during capture. C++ Doppler tracking loop reads pre-computed profile and updates SDR center frequency every 1-5 seconds.

**Pass Criteria:**
- Frequency error <1 kHz RMS throughout pass
- Image quality equal to or better than fixed-frequency capture
- No manual intervention required

---

## V5: Multi-Pass Performance Characterization
**Status: PLANNED**

25+ passes captured and decoded autonomously over 1-2 weeks. Performance characterized across elevation, weather, satellite, and signal type (APT vs LRPT).

**Pass Criteria:**
- Decode success rate >80% for passes >30° max elevation
- System uptime >95%
- Quality estimator auto-grades all captures
- SatDump comparison validates custom decoder accuracy
- LRPT decoder validated on real METEOR captures

---

## V6: ML Mission Planning Integration
**Status: PLANNED**

Train ML models on V5 dataset. Rule-based scoring (Phase 1), RandomForest prediction (Phase 2), online validation (Phase 3), adaptive execution (Phase 4).

**Pass Criteria:**
- Model accuracy >75% on holdout
- ML schedule success rate ≥ rule-based
- Quality estimator grades feed directly into training pipeline

---

## Verification Traceability Matrix

| Requirement | Stage | Method | Status |
|---|---|---|---|
| FR-1.1 (Predict passes) | V0 | Analysis | **Complete** |
| FR-1.2 (AOS/LOS timing) | V0 | Analysis | **Complete** |
| FR-1.5 (Distinguish capturable) | V3+ | Test | **Complete** (catalog fix) |
| FR-2.1 (Receive 137 MHz) | V1 | Test | **Complete** |
| FR-2.3 (LNA gain) | V2 | Test | **Complete** |
| FR-3.1 (FM demod) | V3 | Test | **Complete** |
| FR-3.2 (APT decode) | V3 | Test | **Complete** (noisy) |
| FR-3.5 (Chunked processing) | V3 | Test | **Complete** |
| FR-3A.1 (QPSK demod) | V5 | Test | Implemented, awaiting validation |
| FR-3A.2 (Viterbi decode) | V5 | Test | Implemented, awaiting validation |
| FR-3A.3 (CCSDS sync) | V5 | Test | Implemented, awaiting validation |
| FR-3B.1 (Decoder routing) | V3+ | Test | **Complete** |
| FR-3C.1-6 (Quality estimation) | V3+ | Test | **Complete** |
| FR-3D.1-3 (SatDump comparison) | V5 | Test | Implemented, awaiting captures |
| FR-4.1 (Doppler calc) | V0 | Analysis | **Complete** |
| FR-4.2 (SDR tuning) | V4 | Test | Planned |
| FR-5.1 (Auto trigger) | V4 | Test | Planned |
| FR-8.1.1 (3D visualization) | V0.5 | Demo | **Complete** |
| FR-8.1.5 (Signal type badges) | V3+ | Demo | **Complete** |
| FR-8.2.4 (Pass schedule table) | V3+ | Demo | **Complete** |
| PR-1.1 (±30s timing) | V0 | Analysis | **Complete** |
| PR-5.1 (>30 FPS) | V0.5 | Demo | **Complete** |
