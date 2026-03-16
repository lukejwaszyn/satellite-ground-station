# Autonomous Satellite Ground Station

## Overview

Autonomous ground station for weather satellite image reception with multi-constellation support (NOAA APT + METEOR LRPT), a 3D mission operations interface, real-time orbital tracking, and ML-driven mission planning. Designed and built as a solo undergraduate project applying formal systems engineering methodology.

The system receives, decodes, and displays weather satellite imagery from 137 MHz polar-orbiting satellites using a software-defined radio, custom antenna, and an end-to-end software pipeline spanning orbital prediction, RF capture, signal decoding, and mission automation — 8,500+ lines of source code across Python, C++, JavaScript, and MATLAB.

**Project Duration:** January 2026 – Present (ongoing)  
**Author:** Luke Waszyn, Engineering Science, Penn State  
**Status:** V3+ — First signals decoded, antenna upgrade and image quality iteration in progress  
**Location:** State College, PA (40.7934°N, 77.8600°W, 376m ASL)

---

## Quick Start
```bash
git clone https://github.com/lukejwaszyn/satellite-ground-station.git
cd satellite-ground-station
pip install skyfield numpy scipy pillow scikit-learn pandas
python3 satcom_server.py
```

Open [http://localhost:8080](http://localhost:8080) — the mission server fetches TLEs from Celestrak, generates orbital data for 11 satellites across 5 constellations via Skyfield SGP4, and serves the 3D mission operations interface. Works in both server mode (live tracking + capture control) and standalone demo mode (no SDR required).

---

## What This System Does

1. **Predicts satellite passes** over the ground station using SGP4 orbital propagation with real TLE data from Celestrak
2. **Tracks satellites in real time** on a 3D globe (NASA Blue Marble texture, Three.js/WebGL) showing positions, ground tracks, and orbital planes for NOAA, METEOR, ISS, Terra, Aqua, and Landsat
3. **Computes Doppler profiles** for each pass to support real-time frequency correction during capture
4. **Captures raw I/Q data** from the SDR during a satellite pass, triggered from the HMI or automated by the scheduler
5. **Decodes imagery** from the raw RF data — APT (analog FM) for NOAA satellites, LRPT (digital QPSK) for METEOR satellites
6. **Scores and schedules passes** using an ML pipeline that predicts capture success based on elevation, weather, time of day, and historical performance
7. **Logs everything** — mission history, decoded images, signal metrics — accessible through the REST API and HMI

---

## System Architecture

Formal systems engineering methodology with requirements-driven development (FR/PR/IR), L0–L2 architecture decomposition, and staged V0–V6 verification.

### Integration Architecture
```
Browser HMI (Three.js/WebGL)
    │
    │ HTTP/REST
    ▼
Mission Server (satcom_server.py)
    │
    ├── Orbital Predictor (Skyfield SGP4)
    ├── Doppler Calculator
    ├── Capture Orchestrator ──► C++ Binary (rtlsdr_capture)
    ├── Decoder Router
    │     ├── NOAA  → decode_apt.py   (analog FM → AM envelope → sync → image)
    │     └── METEOR → decode_lrpt.py (QPSK → Viterbi → CCSDS → RS → image)
    ├── ML Pipeline (scikit-learn)
    └── Mission Logger
    │
    ▼
RTL-SDR v4 ──► SAWbird LNA ──► Antenna (QFH / Dipole)
```

### Subsystems (L1)

| # | Subsystem | Purpose | Key Tech |
|---|-----------|---------|----------|
| 1 | Orbital Prediction | Pass forecasting, TLE management | Skyfield, SGP4 |
| 2 | RF Front-End | Receive and amplify 137 MHz signals | QFH antenna, SAWbird LNA |
| 3 | Digital Capture | Convert RF to I/Q samples | RTL-SDR v4, librtlsdr, C++ |
| 4 | DSP & Decoding | Demodulate and decode satellite imagery | APT (FM/AM), LRPT (QPSK/Viterbi) |
| 5 | Automation & Control | Schedule captures, orchestrate pipeline | Python orchestration |
| 6 | Mission Server & HMI | REST API, 3D visualization, mission control | Flask-style HTTP, Three.js |
| 7 | AI Mission Planning | Predict success, optimize scheduling | scikit-learn, pandas |

---

## Mission Operations Interface

The browser-based HMI provides real-time mission operations at `http://localhost:8080`:

- **3D Globe:** NASA Blue Marble Earth texture with real-time satellite positions for 11 spacecraft across 5 constellations (NOAA, METEOR, ISS, Terra/Aqua, Landsat)
- **Signal Type Badges:** Each satellite labeled APT, LRPT, or TRACK to indicate decoder routing
- **Pass Timeline:** Live AOS/TCA/LOS state transitions with satellite-specific frequency and Doppler data
- **Elevation & Doppler Charts:** Real-time pass geometry visualization
- **Pass Schedule:** Sortable table of all upcoming passes with signal type, elevation, duration, frequency
- **Mission Control Panel:** SDR connection status, AOS-gated capture button, capture history
- **Mission Log:** Capture results with decoded image links
- **Keyboard Controls:** Number keys to focus satellites, +/- for time warp, P for pass schedule, R to reset

---

## Decoded Signal Types

### NOAA APT (Automatic Picture Transmission)
- **Satellites:** NOAA 15 (137.62 MHz), NOAA 18 (137.9125 MHz), NOAA 19 (137.1 MHz)
- **Modulation:** Analog FM carrier with 2400 Hz AM subcarrier
- **Format:** 2 lines/second, 2080 pixels/line, dual-channel (visible + IR)
- **Decoder:** `decode_apt.py` — FM demod → lowpass → AM envelope → sync correlation → line extraction
- **Output:** Grayscale PNG, 2080px wide

### METEOR LRPT (Low Rate Picture Transmission)
- **Satellites:** METEOR-M2 3 (137.9 MHz), METEOR-M2 4 (137.1 MHz)
- **Modulation:** OQPSK, 72 kSymbol/s
- **FEC:** Rate 1/2 convolutional code (k=7) + RS(255,223)
- **Framing:** CCSDS compatible, 1024-byte frames
- **Decoder:** `decode_lrpt.py` — AGC → RRC matched filter → Gardner timing → Costas carrier recovery → Viterbi → CCSDS sync → derandomize → Reed-Solomon → image reassembly
- **Output:** Multi-channel PNG (up to 6 AVHRR channels) + RGB composite

---

## Verification Status

| Stage | Objective | Status | Date |
|-------|-----------|--------|------|
| V0 | Orbital prediction validated (±15s accuracy) | **Complete** | Jan 16, 2026 |
| V0.5 | SDR environment verified (RTL-SDR v4 on macOS) | **Complete** | Jan 30, 2026 |
| V1 | RF link established (first capture, end-to-end pipeline) | **Complete** | Feb 27, 2026 |
| V2 | LNA integration (SAWbird NOAA, 20 dB gain) | **Complete** | Mar 6, 2026 |
| V3 | Signal decoded (831 APT sync pulses from NOAA 19) | **Complete** | Mar 6, 2026 |
| V3.1 | USB adapter fix (Apple USB-A→C, eliminated noise) | **Complete** | Mar 12, 2026 |
| V3+ | Clean decoded image with visible features | **In Progress** | — |
| V4 | Automated Doppler tracking during capture | Planned | — |
| V5 | Multi-pass characterization (25+ decoded images) | Planned | — |
| V6 | ML mission planning integration | Planned | — |

---

## Decoded Signal Progression

| Date | Satellite | Elevation | Sync Pulses | Result |
|------|-----------|-----------|-------------|--------|
| Feb 27 | NOAA 18 | 89.4° | 0 | Black image — wrong frequency (137.1 vs 137.9125 MHz) |
| Mar 3 | NOAA 19 | 41.6° | 0 | Black image — dtype bug (float32 vs uint8) |
| Mar 3 | NOAA 19 | 41.6° | 2 | Faint sync lines (reprocessed after fix) |
| Mar 6 | NOAA 15 | 20.4° | 135 | APT frame structure visible |
| Mar 6 | NOAA 19 | 89.0° | 831 | Full pass decoded — noisy, USB interference pattern |
| Mar 12 | NOAA 21 | 89.7° | 287 | Signal structure visible (Apple USB adapter), partial decode |

---

## Hardware

| Component | Specification |
|-----------|--------------|
| SDR | RTL-SDR Blog V4 (R828D tuner, 24–1766 MHz, 8-bit ADC) |
| LNA | Nooelec SAWbird NOAA (20 dB gain, 0.7 dB NF, SAW filter at 137.5 MHz) |
| Antenna | VHF dipole (QFH antenna build in progress with Penn State Space Systems Lab) |
| USB | Apple USB-A to USB-C adapter (resolved USB noise/dropout issues) |
| Feed | 50Ω coaxial, SMA connectors throughout |
| Computer | 2025 MacBook Air M4 |

**RF Chain:** Antenna → SAWbird LNA → Coax → RTL-SDR v4 → Apple USB-A→C → MacBook Air M4

---

## Software Stack

| Language | Lines | Purpose |
|----------|-------|---------|
| Python | ~6,200 | Orbital mechanics, decoders (APT + LRPT), ML pipeline, orchestration, mission server |
| JavaScript/HTML | ~1,650 | 3D mission operations interface (Three.js, WebGL) |
| C++ | ~650 | Real-time I/Q capture with async streaming, Doppler tracking |
| MATLAB | ~70 | Spectrum analysis, verification |
| **Total** | **~8,570** | |

### Key Files

| File | Lines | Description |
|------|-------|-------------|
| `hmi/satellite-viz.html` | 1,646 | 3D HMI — globe, pass timeline, mission control, pass schedule |
| `python/demod/decode_lrpt.py` | 1,001 | METEOR LRPT decoder (QPSK, Viterbi, CCSDS, Reed-Solomon) |
| `satcom_server.py` | 762 | Unified REST API — orbital data, capture control, decoder routing |
| `hmi/generate_orbital_data.py` | 582 | Multi-constellation orbital predictor (11 sats, 5 groups) |
| `python/schedule_captures.py` | 465 | Capture orchestration and automation pipeline |
| `python/demod/decode_apt.py` | 473 | NOAA APT decoder (FM demod, AM envelope, sync detection) |
| `python/ml/model_trainer.py` | 418 | ML model training pipeline |
| `python/ml/data_store.py` | 410 | Mission database layer |
| `python/ml/pass_scorer.py` | 338 | Rule-based and ML-driven pass scoring |
| `python/ml/feature_engineering.py` | 337 | ML feature extraction from pass/weather data |
| `python/run_mission.py` | 315 | Autonomous mission execution |
| `python/ml/scheduler_optimizer.py` | 315 | Schedule optimization engine |
| `python/ml/ml_predictor.py` | 309 | ML prediction interface |
| `cpp/src/doppler_tracker.cpp` | 303 | Real-time Doppler compensation (C++) |
| `cpp/src/rtlsdr_capture.cpp` | 280 | Async I/Q capture with ring buffer (C++) |
| `python/doppler_calc.py` | 225 | Doppler frequency profile generation |
| `python/demod/decode_apt_wav.py` | 143 | APT decoder for pre-recorded WAV files |
| `python/predict_passes.py` | 110 | SGP4 pass prediction utilities |

---

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Mission operations HMI |
| `/api/orbital-data` | GET | Orbital data for all tracked satellites (positions, passes, Doppler) |
| `/api/passes` | GET | Upcoming passes with signal type, filterable by elevation/role |
| `/api/status` | GET | System status (SDR connection, capture state, server uptime) |
| `/api/capture` | POST | Trigger satellite capture (AOS-gated, routes to correct decoder) |
| `/api/config` | GET/PUT | Station configuration (location, SDR settings, HMI params) |
| `/api/missions` | GET | Mission log history with decode results |
| `/api/decoded/<file>` | GET | Serve decoded images |
| `/api/refresh` | POST | Force orbital data regeneration |

---

## Milestone History

### V1 — First Capture (February 27, 2026)
NOAA 18 at 89.4° elevation, 717-second pass. Full pipeline executed end-to-end: HMI capture button → REST API → C++ binary → decoder. Image was black — root cause: frontend sent default 137.1 MHz instead of NOAA 18's actual 137.9125 MHz. Fixed by passing satellite-specific frequency through the capture chain.

### V1.5 — Decoder Fix (March 3, 2026)
Identified critical dtype bug in APT decoder: raw binary was read as float32 instead of uint8, processing only 1/4 of actual samples with garbage values. Fixed to read as uint8 with normalization to [-1, 1]. Re-decoded NOAA 19 capture: first sync pulses detected.

### V2 — LNA Integration (March 6, 2026)
Nooelec SAWbird NOAA integrated into RF chain. 20 dB gain, 0.7 dB noise figure, built-in SAW bandpass filter centered at 137.5 MHz. Verified amplification via spectrum scan showing signal power at -19 to -24 dB above noise floor.

### V3 — First Signal Decode (March 6, 2026)
NOAA 15 at 20.4°: 135 sync pulses, APT frame structure visible. NOAA 19 at 89.0°: 831 sync pulses, full-length pass decoded. Image noisy — repeating diagonal interference pattern identified as USB adapter noise injection. Memory-efficient chunked decoder implemented (processes 3+ GB captures in ~2-3 GB RAM).

### V3.1 — USB Fix (March 12, 2026)
Replaced cheap USB-C hub with Apple USB-A to USB-C adapter. NOAA 21 at 89.7°: 287 sync pulses with real signal structure visible (vs pure noise previously). USB noise/interference pattern eliminated. Signal drops out mid-pass — consistent with dipole antenna null at zenith. Antenna upgrade (QFH) in progress with Penn State Space Systems Lab.

---

## Current Focus

- **Antenna:** QFH antenna build with Dr. Bilén's Space Systems Lab for RHCP match and hemispherical coverage
- **Image Quality:** First clean decoded image with visible weather features (V3+ milestone)
- **LRPT Validation:** Test METEOR LRPT decoder on real captures once antenna is operational
- **Satellite Catalog Fix:** NOAA 20/21 (JPSS series) don't transmit APT — need reclassification to display-only or HRPT
- **SatDump Comparison:** Validate custom decoders against SatDump output on same captures

---

## Tracked Satellites

| Satellite | Role | Signal | Frequency | Status |
|-----------|------|--------|-----------|--------|
| NOAA 15 | Weather | APT | 137.620 MHz | Active — capturable |
| NOAA 18 | Weather | APT | 137.9125 MHz | Active — capturable |
| NOAA 19 | Weather | APT | 137.100 MHz | Active — capturable |
| NOAA 20 | Primary | APT* | 137.100 MHz | *JPSS — may not transmit APT* |
| NOAA 21 | Weather | APT* | 137.100 MHz | *JPSS — may not transmit APT* |
| METEOR-M2 3 | Weather | LRPT | 137.900 MHz | Active — capturable |
| METEOR-M2 4 | Weather | LRPT | 137.100 MHz | Active — capturable |
| ISS | Display | — | — | Tracked only |
| Terra | Display | — | — | Tracked only |
| Aqua | Display | — | — | Tracked only |
| Landsat 9 | Display | — | — | Tracked only |

---

## Documentation

All documentation follows formal systems engineering standards:

- **Requirements:** Functional (FR-1 through FR-8), performance (PR-1 through PR-4), interface (IR)
- **Architecture:** L0 system context, L1 subsystem decomposition (7 subsystems), L2 implementation
- **Interface Control:** 6 ICDs defining data schemas and protocols between subsystems
- **Verification:** V0–V6 staged verification plan with pass/fail criteria and requirements traceability
- **ML Architecture:** Feature definitions, model specifications, training/validation procedures

---

## Technologies

**Languages:** Python 3.10+, C++17, JavaScript ES6+, MATLAB  
**Libraries:** Skyfield, NumPy, SciPy, Pillow, scikit-learn, pandas, Three.js, WebGL  
**Hardware:** RTL-SDR Blog V4, Nooelec SAWbird NOAA, Apple USB-A→C adapter  
**Platform:** macOS (Apple Silicon M4)  
**Build:** CMake (C++), pip (Python)

---

## License

MIT License — see LICENSE file for details.

---

## Acknowledgments

This project applies formal systems engineering methodology inspired by JPL's approach to mission design and verification. Orbital mechanics via the Skyfield library by Brandon Rhodes. APT signal format per NOAA KLM User's Guide. LRPT decoding based on the CCSDS standards and METEOR-M documentation. Earth visualization uses the NASA Blue Marble texture. Built at Penn State, supported by Dr. Sven Bilén's Space Systems Research Lab.
