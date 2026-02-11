# Autonomous Satellite Ground Station

## Overview

Autonomous ground station for NOAA weather satellite APT image reception using custom VHF antenna, low-noise amplifier, real-time DSP pipeline, and AI-driven mission planning.

**Project Duration:** 10 weeks (January 16 - March 30, 2026)

**Objective:** Autonomous NOAA APT reception with >80% decode success rate and ML-optimized mission scheduling

---

## System Architecture

This project follows a formal systems engineering methodology with requirements-driven development and staged verification:

- **L0 System Context:** End-to-end RF receive chain from antenna to decoded imagery
- **L1 Subsystems:** Orbital prediction, RF front-end, digital capture, DSP processing, automation, AI mission planning
- **L2 Implementation:** Python/C++/MATLAB implementation with hardware integration and ML pipeline

---

## Verification Strategy

| Stage | Objective | Status |
|-------|-----------|--------|
| V0 | Orbital prediction validated | Complete |
| V1 | RF link established | In Progress |
| V2 | LNA integration and SNR improvement | Planned |
| V3 | Functional decode (first image) | Planned |
| V4 | Automated Doppler tracking | Planned |
| V5 | Multi-pass performance characterization (25+ images) | Planned |
| V6 | ML mission planning integration | Planned |

---

## Success Tiers

**Tier 1 - Minimum Viable (V3)**
- One decoded satellite image with recognizable Earth features
- End-to-end RF chain validated: antenna → LNA → SDR → DSP → image

**Tier 2 - Strong (V5)**
- 25+ decoded images captured autonomously
- Multi-day unattended operation
- Quantified performance metrics and failure mode analysis

**Tier 3 - Exceptional (V6)**
- ML layer learns from mission outcomes
- Predictive model optimizes pass selection
- System improves performance over time

---

## Technical Approach

### Hardware

- RTL-SDR v4 software-defined radio
- Custom half-wave VHF dipole antenna (137 MHz)
- Low-noise amplifier (15-20 dB gain, <1.5 dB NF)
- Coaxial RF transmission lines (50Ω impedance)

### Software Stack

| Language | Purpose |
|----------|---------|
| Python | Orbital mechanics, ML pipeline, orchestration, APT decoding |
| C++ | Real-time I/Q capture, Doppler tracking |
| MATLAB | Signal processing, PSD analysis, verification |

### Core Capabilities

- **Orbital Mechanics:** SGP4 propagation via Skyfield
- **Signal Processing:** FM demodulation, APT sync detection, image reconstruction
- **Real-Time Control:** Automated Doppler frequency compensation in C++
- **ML Mission Planning:** Pass scoring, success prediction, schedule optimization

---

## Current Status

### V0 Verification Complete (January 16, 2026)
- SGP4 orbital propagator implemented and validated
- Pass predictions accurate within 15 seconds vs. reference
- Doppler frequency calculations validated
- 7-day pass forecasts generated for State College, PA

### Environment Verified (January 30, 2026)
- RTL-SDR v4 detected and controlled via C++
- MATLAB spectrum capture validated (FM band test)
- C++ build environment configured (CMake + librtlsdr)

### V1 In Progress
- Antenna materials acquired
- Awaiting fabrication (coax soldering)

---

## Project Structure

```
satellite-ground-station/
├── docs/
│   ├── requirements/           # Functional (FR-1 to FR-7), performance, interface
│   ├── architecture/           # L0-L2, interface control, verification plan
│   └── ml/                     # ML architecture, feature specs, model cards
│
├── python/
│   ├── predict_passes.py       # SGP4 propagator [EXISTS]
│   ├── doppler_calc.py         # Doppler frequency profiles [PLANNED]
│   ├── decode_apt.py           # APT demodulation and image decode [PLANNED]
│   ├── schedule_captures.py    # Automation orchestrator [PLANNED]
│   └── ml/
│       ├── feature_engineering.py
│       ├── pass_scorer.py
│       ├── ml_predictor.py
│       ├── scheduler_optimizer.py
│       ├── model_trainer.py
│       └── data_store.py
│
├── cpp/
│   ├── src/
│   │   ├── rtlsdr_test.cpp     # Hardware verification [EXISTS]
│   │   ├── rtlsdr_capture.cpp  # Real-time I/Q streaming [PLANNED]
│   │   └── doppler_tracker.cpp # Real-time frequency correction [PLANNED]
│   └── CMakeLists.txt          # Build configuration [EXISTS]
│
├── matlab/
│   ├── tests/                  # Environment and SDR verification
│   ├── capture/                # I/Q capture scripts
│   ├── analysis/               # Post-capture analysis
│   └── utilities/              # Metrics computation
│
└── data/
    ├── tle/                    # Cached TLE files
    ├── captures/               # Raw I/Q recordings
    ├── decoded/                # APT images
    ├── logs/                   # System logs
    └── ml/
        ├── training/           # Historical mission data
        ├── models/             # Trained model files
        └── predictions/        # Prediction logs
```

---

## Documentation

### Requirements
- Functional requirements (FR-1 through FR-7)
- Performance requirements (PR-1 through PR-4)
- Interface requirements (hardware, software, data)

### Architecture
- L0 system context (external entities, boundaries)
- L1 subsystem decomposition (6 subsystems including AI mission planning)
- L2 implementation details (multi-language stack, ML pipeline)
- Interface Control Document (5 ICDs with schemas)

### ML System
- ML architecture specification
- Feature definitions
- Model training and validation procedures

### Verification
- V0-V6 staged verification plan
- Pass/fail criteria for each stage
- Requirements traceability matrix

---

## Technologies

**Languages:**
- Python 3.10+ (Skyfield, NumPy, SciPy, scikit-learn, pandas)
- MATLAB R2025b (Signal Processing, Communications, Satellite Comms Toolboxes)
- C++17 (librtlsdr, real-time DSP)

**ML Stack:**
- scikit-learn (RandomForest, preprocessing pipelines)
- XGBoost (optional)
- joblib (model persistence)

**Hardware:**
- RTL-SDR Blog V4 (R828D tuner)
- Custom VHF dipole antenna
- Custom LNA PCB

**Platform:**
- Primary: macOS (Apple Silicon M4)
- Backup: Windows/Linux (ASUS ROG G14)

---

## Author

Luke Waszyn
Engineering Science, The Pennsylvania State University

---

## License

MIT License - see LICENSE file for details

---

## Acknowledgments

This project applies formal systems engineering methodology inspired by JPL's approach to mission design and verification. Orbital mechanics implementation uses the Skyfield library by Brandon Rhodes.
