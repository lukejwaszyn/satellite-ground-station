# Autonomous Satellite Ground Station

## Overview

Autonomous ground station and mission operations platform for NOAA weather satellite APT image reception. Features custom VHF antenna, low-noise amplifier, real-time DSP pipeline, AI-driven mission planning, and an interactive 3D mission operations interface tracking 12 satellites across multiple constellations.

**Project Duration:** 10 weeks (January 16 - March 30, 2026)

**Objective:** Autonomous NOAA APT reception with >80% decode success rate, ML-optimized mission scheduling, and real-time operator situational awareness

---

## Mission Operations Interface

The system includes SATCOM, a 3D mission operations interface built with Three.js that provides real-time situational awareness:

- **Multi-constellation tracking:** 12 satellites across NOAA, METEOR, ISS, Landsat, Terra, and Aqua
- **Real SGP4 propagation:** Skyfield backend with live TLE data from Celestrak
- **Pass prediction:** AOS/TCA/LOS timeline with countdown, azimuth, elevation, range
- **Doppler visualization:** Real-time Doppler shift profiles with TCA zero-crossing
- **Elevation profiles:** Pass geometry charts for each upcoming pass
- **Satellite roles:** Primary imaging target (NOAA 20), weather constellation, and display satellites

```bash
# Generate orbital data and launch visualizer
python3 generate_orbital_data.py
python3 -m http.server 8080 &
open http://localhost:8080/satellite-viz.html
```

---

## System Architecture

This project follows a formal systems engineering methodology with requirements-driven development and staged verification:

- **L0 System Context:** End-to-end RF receive chain from antenna to decoded imagery, plus mission operations display
- **L1 Subsystems:** Orbital prediction, RF front-end, digital capture, DSP processing, automation, AI mission planning, mission operations HMI
- **L2 Implementation:** Python/C++/JavaScript/MATLAB implementation with hardware integration and ML pipeline

---

## Verification Strategy

| Stage | Objective | Status |
|-------|-----------|--------|
| V0 | Orbital prediction validated | Complete |
| V0.5 | Mission operations HMI validated | Complete |
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
| Python | Orbital mechanics, ML pipeline, orchestration, APT decoding, orbital data generation |
| C++ | Real-time I/Q capture, Doppler tracking |
| JavaScript | 3D mission operations interface (Three.js / WebGL) |
| MATLAB | Signal processing, PSD analysis, verification |

### Core Capabilities

- **Orbital Mechanics:** SGP4 propagation via Skyfield, multi-constellation tracking (12 satellites)
- **Signal Processing:** FM demodulation, APT sync detection, image reconstruction
- **Real-Time Control:** Automated Doppler frequency compensation in C++
- **ML Mission Planning:** Pass scoring, success prediction, schedule optimization
- **Mission Operations HMI:** 3D globe with real-time satellite positions, pass timeline, Doppler/elevation charts

---

## Current Status

### Software Complete
All software subsystems are implemented and ready for hardware integration:

- **Orbital Prediction:** SGP4 propagator, pass scheduling, Doppler calculation (predict_passes.py, doppler_calc.py)
- **APT Decoding:** FM demodulation, sync detection, image reconstruction (decode_apt.py, decode_apt_wav.py)
- **Real-Time Capture:** C++ I/Q streaming with Doppler tracking (rtlsdr_capture.cpp, doppler_tracker.cpp)
- **Mission Automation:** End-to-end autonomous capture orchestration (schedule_captures.py, run_mission.py)
- **ML Pipeline:** Feature engineering, pass scoring, success prediction, schedule optimization, model training (6 modules)
- **Mission Operations HMI:** 3D multi-constellation visualizer with Skyfield SGP4 backend (generate_orbital_data.py, satellite-viz.html)

### Verification Progress

| Stage | Objective | Status |
|-------|-----------|--------|
| V0 | Orbital prediction validated (±15s accuracy) | Complete |
| V0.5 | Mission operations HMI validated (12 satellites, 5 constellations) | Complete |
| V1 | RF link established | In Progress (antenna built, awaiting LNA) |
| V2 | LNA integration and SNR improvement | Planned (PCB in fabrication) |
| V3 | Functional decode (first image) | Planned |
| V4+ | Automated Doppler, multi-pass, ML integration | Planned |

### V1 In Progress
- Custom VHF dipole antenna fabricated and ready
- LNA PCB in fabrication
- Awaiting LNA assembly for full RF chain integration

---

## Project Structure

```
satellite-ground-station/
├── hmi/
│   ├── generate_orbital_data.py   # Skyfield SGP4 multi-constellation backend    [DONE]
│   └── satellite-viz.html         # 3D mission operations frontend (Three.js)    [DONE]
│
├── python/
│   ├── predict_passes.py          # SGP4 propagator                              [DONE]
│   ├── doppler_calc.py            # Doppler frequency profiles                   [DONE]
│   ├── decode_apt.py              # APT image decoder                            [DONE]
│   ├── decode_apt_wav.py          # WAV-based APT decoder                        [DONE]
│   ├── schedule_captures.py       # Automation orchestrator                      [DONE]
│   ├── run_mission.py             # End-to-end mission execution                 [DONE]
│   └── ml/
│       ├── feature_engineering.py # ML feature extraction                        [DONE]
│       ├── pass_scorer.py         # Rule-based pass scoring                      [DONE]
│       ├── ml_predictor.py        # ML success prediction                        [DONE]
│       ├── scheduler_optimizer.py # Schedule optimization                        [DONE]
│       ├── model_trainer.py       # Model training pipeline                      [DONE]
│       └── data_store.py          # Historical data management                   [DONE]
│
├── cpp/
│   ├── src/
│   │   ├── rtlsdr_test.cpp        # Hardware verification                       [DONE]
│   │   ├── rtlsdr_capture.cpp     # Real-time I/Q streaming                     [DONE]
│   │   └── doppler_tracker.cpp    # Real-time frequency correction               [DONE]
│   └── CMakeLists.txt                                                            [DONE]
│
├── matlab/
│   └── tests/                     # SDR and signal verification scripts          [DONE]
│
├── docs/
│   ├── requirements/              # FR-1 to FR-8, performance, interface
│   ├── architecture/              # L0-L2, interface control, verification plan
│   └── ml/                        # ML architecture, feature specs, model cards
│
└── data/
    ├── tle/                       # Cached TLE files
    ├── captures/                  # Raw I/Q recordings
    ├── decoded/                   # APT images
    └── ml/                        # Training data, models, predictions
```

---

## Documentation

### Requirements
- Functional requirements (FR-1 through FR-8, including HMI)
- Performance requirements (PR-1 through PR-5)
- Interface requirements (hardware, software, data, HMI)

### Architecture
- L0 system context (external entities, boundaries, multi-constellation tracking)
- L1 subsystem decomposition (7 subsystems including AI mission planning and HMI)
- L2 implementation details (multi-language stack, ML pipeline, HMI data flows)
- Interface Control Document (6 ICDs with schemas)

### ML System
- ML architecture specification
- Feature definitions
- Model training and validation procedures

### Verification
- V0-V6 staged verification plan (plus V0.5 for HMI)
- Pass/fail criteria for each stage
- Requirements traceability matrix

---

## Technologies

**Languages:**
- Python 3.10+ (Skyfield, NumPy, SciPy, scikit-learn, pandas)
- JavaScript (Three.js r128, WebGL, HTML5 Canvas)
- C++17 (librtlsdr, real-time DSP)
- MATLAB R2025b (Signal Processing, Communications, Satellite Comms Toolboxes)

**ML Stack:**
- scikit-learn (RandomForest, preprocessing pipelines)
- XGBoost (optional)
- joblib (model persistence)

**HMI Stack:**
- Three.js r128 (3D globe, satellite meshes, orbital trails)
- HTML5 Canvas (elevation and Doppler charts)
- Skyfield (SGP4 propagation backend)

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

This project applies formal systems engineering methodology inspired by JPL's approach to mission design and verification. Orbital mechanics implementation uses the Skyfield library by Brandon Rhodes. 3D visualization built with Three.js.
