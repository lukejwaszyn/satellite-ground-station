# Satellite Ground Station Project - Comprehensive Overview

## Document Purpose

This document serves as a complete reference for the Autonomous Satellite Ground Station project. It contains all context necessary to provide accurate assistance without re-asking questions or losing track of project state.

---

## Project Identity

**Project Name:** Autonomous Satellite Ground Station
**Owner:** Luke Waszyn
**Affiliation:** Engineering Science, The Pennsylvania State University
**Timeline:** January 16 - March 30, 2026 (10 weeks)
**Repository:** github.com/lukejwaszyn/satellite-ground-station

---

## Mission Statement

Build an autonomous system that receives NOAA weather satellite transmissions, decodes APT imagery, and uses machine learning to optimize mission planning — with an integrated 3D mission operations interface that provides real-time situational awareness across multiple satellite constellations. Demonstrates end-to-end systems engineering from RF hardware through intelligent software to operator-facing visualization.

---

## Success Criteria

### Tier 1 - Minimum Viable (V3)
- One decoded satellite image with recognizable Earth features
- Proves: antenna → LNA → SDR → DSP → image pipeline works

### Tier 2 - Strong (V5)
- 25+ decoded images captured autonomously
- Multi-day unattended operation
- Quantified metrics: success rate >80% for passes >30° elevation

### Tier 3 - Exceptional (V6)
- ML model predicts mission success probability
- System optimizes which passes to capture
- Performance improves over time through learning

---

## Technical Architecture

### Hardware Stack
| Component | Specification | Status |
|-----------|---------------|--------|
| SDR | RTL-SDR Blog V4 (R828D tuner) | Verified |
| Antenna | Custom λ/2 dipole @ 137 MHz | Materials acquired |
| LNA | 15-20 dB gain, <1.5 dB NF | Design phase |
| Feedline | RG-58/RG-59 coax, 50Ω | Acquired |
| Connectors | SMA male to SDR | Acquired |

### Software Stack
| Language | Role | Key Libraries |
|----------|------|---------------|
| Python | Orchestration, ML, APT decode, orbital data generation | Skyfield, scikit-learn, NumPy, SciPy |
| C++ | Real-time capture, Doppler tracking | librtlsdr |
| JavaScript | 3D mission operations interface | Three.js r128 (WebGL) |
| MATLAB | Signal analysis, verification | Comms Toolbox, Signal Processing Toolbox |

### Subsystems (L1)
1. **Orbital Prediction** — SGP4 propagation, pass scheduling, Doppler calculation
2. **RF Front-End** — Antenna, LNA, impedance matching
3. **Digital Capture** — RTL-SDR interface, I/Q streaming
4. **DSP & Decoding** — FM demod, APT sync detection, image reconstruction
5. **Automation & Control** — Mission orchestration, logging
6. **AI Mission Planning** — Feature engineering, prediction, optimization
7. **Mission Operations Interface (HMI)** — 3D satellite visualization, pass timeline, Doppler/elevation charts, multi-constellation tracking

---

## Verification Stages

| Stage | Objective | Status | Key Deliverable |
|-------|-----------|--------|-----------------|
| V0 | Orbital prediction | COMPLETE | predict_passes.py validated ±15s accuracy |
| V0.5 | Mission operations HMI | COMPLETE | 3D multi-constellation visualizer with Skyfield SGP4 |
| V1 | RF link establishment | IN PROGRESS | Carrier detection in PSD |
| V2 | LNA integration | PLANNED | SNR improvement >8 dB |
| V3 | First image decode | PLANNED | Decoded APT image (PNG) |
| V4 | Automated Doppler | PLANNED | Real-time frequency tracking |
| V5 | Multi-pass characterization | PLANNED | 25+ images, performance stats |
| V6 | ML integration | PLANNED | Predictive model operational |

---

## File Inventory

### Exists Now
| File | Location | Purpose |
|------|----------|---------|
| predict_passes.py | python/ | SGP4 pass prediction |
| doppler_calc.py | python/ | Doppler frequency profiles |
| schedule_captures.py | python/ | Automation orchestrator |
| decode_apt.py | python/ | APT image decoder |
| decode_apt_wav.py | python/ | WAV-based APT decoder |
| run_mission.py | python/ | End-to-end mission execution |
| data_store.py | python/ml/ | Historical data management |
| feature_engineering.py | python/ml/ | ML feature extraction |
| pass_scorer.py | python/ml/ | Rule-based pass scoring |
| ml_predictor.py | python/ml/ | ML success prediction |
| scheduler_optimizer.py | python/ml/ | Schedule optimization |
| model_trainer.py | python/ml/ | ML model training pipeline |
| generate_orbital_data.py | hmi/ | Skyfield SGP4 multi-constellation backend |
| satellite-viz.html | hmi/ | 3D mission operations frontend (Three.js) |
| rtlsdr_test.cpp | cpp/src/ | C++ hardware verification |
| rtlsdr_capture.cpp | cpp/src/ | Real-time I/Q streaming |
| doppler_tracker.cpp | cpp/src/ | Real-time frequency correction |
| CMakeLists.txt | cpp/ | C++ build config |
| rtlsdr_spectrum_test.m | matlab/tests/ | MATLAB SDR verification |

---

## Key Technical Parameters

### RF Parameters
- **Center Frequency:** 137 MHz (NOAA APT band)
- **NOAA-20 (Primary):** 137.100 MHz
- **NOAA-15:** 137.620 MHz
- **NOAA-18:** 137.9125 MHz
- **NOAA-19:** 137.100 MHz
- **NOAA-21:** 137.100 MHz
- **Bandwidth:** ~40 kHz (APT signal)
- **Doppler Range:** ±3.5 kHz typical

### SDR Parameters
- **Sample Rate:** 2.4 MHz (native), decimate to 250 kHz
- **Gain:** 20-40 dB (tunable)
- **ADC Resolution:** 8-bit

### APT Format
- **Line Rate:** 2 lines/second
- **Pixels per Line:** 2080
- **Subcarrier:** 2400 Hz AM
- **Sync Pattern:** 7-line sync pulses

### Observer Location
- **Latitude:** 40.7934°N
- **Longitude:** 77.8600°W
- **Elevation:** 376 m
- **Location:** State College, PA

### Performance Targets
- **Pass Prediction Accuracy:** ±30 seconds
- **Doppler Tracking Error:** <1 kHz RMS
- **Decode Success Rate:** >80% (passes >30° elevation)
- **ML Prediction Accuracy:** >75%

---

## Development Environment

### Primary Machine
- **Hardware:** 2025 MacBook Air M4
- **OS:** macOS
- **MATLAB:** R2025b with Communications, Signal Processing, Satellite Comms Toolboxes

### Backup Machine
- **Hardware:** ASUS ROG G14 (keyboard damaged)
- **OS:** Windows/Linux
- **Use Case:** Heavy compute if needed

### Tools Verified
- Homebrew installed
- librtlsdr installed (/opt/homebrew/)
- CMake configured
- C++17 compiler (clang)
- Python 3.10+
- Git + SSH authentication to GitHub

---

## Interface Specifications

### ICD-1: Python Predictor → C++ Capture
- **Format:** JSON file
- **Location:** data/schedules/next_pass.json
- **Contents:** AOS/LOS times, Doppler profile, frequency, satellite ID

### ICD-2: C++ Capture → Python Decoder
- **Format:** Binary I/Q + JSON metadata
- **I/Q Format:** Interleaved float32 (I0,Q0,I1,Q1,...)
- **Metadata:** Sample rate, frequency, duration, gain

### ICD-3: Celestrak TLE API
- **Endpoints:** Multiple groups (weather, stations, resource, NOAA) + individual NORAD ID queries
- **Update Frequency:** Daily (24h cache)
- **Cache Location:** data/tle/

### ICD-4: Decoder → Output Images
- **Format:** PNG (lossless) or JPEG
- **Resolution:** 2080 x variable (depends on pass duration)
- **Metadata:** Embedded in PNG text fields

### ICD-5: All Systems → Data Store
- **Format:** CSV or SQLite
- **Fields:** timestamp, satellite, elevation, weather, config, outcome, metrics

### ICD-6: Orbital Data Backend → Mission Operations HMI
- **Format:** JSON (orbital_data.json) served via local HTTP
- **Contents:** Satellite positions (ECEF), passes (AOS/TCA/LOS), Doppler profiles, metadata
- **Generation:** generate_orbital_data.py (Skyfield SGP4)
- **Consumption:** satellite-viz.html (Three.js frontend)

---

## ML Feature Specification

### Input Features
| Feature | Type | Source |
|---------|------|--------|
| max_elevation_deg | float | Orbital prediction |
| duration_min | float | Orbital prediction |
| time_of_day | category | AOS timestamp |
| satellite_id | category | TLE |
| cloud_cover_pct | float | Weather API |
| precip_prob | float | Weather API |
| antenna_config | category | Config |
| gain_db | float | Config |
| recent_success_rate | float | Historical data |

### Target Variables
| Variable | Type | Use |
|----------|------|-----|
| decode_success | binary | Classification target |
| snr_db | float | Regression target |
| sync_rate | float | Quality metric |

### Model Specification
- **Algorithm:** RandomForestClassifier (primary)
- **Minimum Training Data:** 20-30 missions
- **Retraining Frequency:** Daily or after each mission
- **Persistence:** joblib (.pkl files)

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Antenna underperforms | Medium | High | V2 LNA provides margin |
| LNA fabrication delay | Medium | Medium | Proceed without, accept lower SNR |
| C++ real-time drops samples | Low | High | Optimize I/O, reduce sample rate |
| Weather blocks passes | High | Low | Multiple opportunities per day |
| Insufficient ML training data | Medium | Medium | Rule-based fallback |
| APT sync detection fails | Low | High | Iterate on algorithm |

---

## Timeline Summary

| Week | Dates | Focus | Milestone |
|------|-------|-------|-----------|
| 1 | Jan 16-22 | Orbital prediction | V0 complete |
| 2 | Jan 23-29 | Antenna build | V1 RF link |
| 3 | Jan 30 - Feb 5 | LNA design | PCB ordered |
| 4 | Feb 6-12 | LNA integration | V2 complete |
| 5 | Feb 13-19 | APT decode | V3 first image |
| 6 | Feb 20-26 | Real-time DSP | V4 Doppler tracking |
| 8-9 | Mar 10-20 | Autonomous operation | V5 25+ images |
| 10-11 | Mar 21-28 | ML integration | V6 complete |

---

## Startup Context

This project serves as proof-of-concept for an AI mission planning platform ("Palantir for missions"):

- **Core Insight:** Mission planning, execution, and success evaluation can be optimized with ML
- **Target Markets:** Defense, aerospace, commercial space
- **Differentiation:** Palantir does data integration; this does mission automation
- **Validation:** Satellite ground station demonstrates the concept on real hardware

The V6 ML layer is designed to be generalizable beyond NOAA APT to other mission types.

---

## Contact

- **Email:** lukejwasz@gmail.com / ljw5734@psu.edu
- **GitHub:** lukejwaszyn

---

## Document History

| Date | Update |
|------|--------|
| 2026-01-16 | V0 complete, project initiated |
| 2026-01-30 | C++ environment verified, MATLAB tested |
| 2026-02-01 | ML architecture documented, comprehensive overview created |
| 2026-02-25 | V0.5 complete: Mission Operations HMI with 3D multi-constellation tracking, FR-8 added, 7th subsystem defined |
