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
| V4 | Automated Doppler tracking | Software Complete |
| V5 | Multi-pass performance characterization (25+ images) | Software Complete |
| V6 | ML mission planning integration | Software Complete |

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

## Technical Stack

### Hardware
| Component | Specification |
|-----------|---------------|
| SDR | RTL-SDR Blog V4 (R828D tuner) |
| Antenna | Custom half-wave VHF dipole (137 MHz) |
| LNA | BFP420 BJT, 15-20 dB gain, <1.5 dB NF (in design) |
| Feedline | RG-59 coaxial (75Ω) |

### Software
| Language | Purpose |
|----------|---------|
| Python 3.10+ | Orbital mechanics (Skyfield), ML pipeline, APT decoding, orchestration |
| C++17 | Real-time I/Q capture, Doppler tracking, multithreaded DSP |
| MATLAB | Signal analysis, PSD computation, verification |

### ML Stack
- scikit-learn (RandomForest classifier/regressor)
- pandas/NumPy (feature engineering)
- joblib (model persistence)

---

## Development Environment

Developed entirely via Unix command line workflow:

### Build Systems & Tooling
- CMake for cross-platform C++ compilation
- Make for build automation
- Homebrew package management (librtlsdr, dependencies)
- Git version control with SSH authentication

### Systems Programming
- Multithreaded C++ with POSIX threads
- Asynchronous I/O with ring buffers for real-time capture at 2.4 MS/s
- Signal handling (SIGINT, SIGTERM) for graceful shutdown
- Direct hardware access via librtlsdr
- Daemon processes for unattended multi-day operation

### Shell & Scripting
- Bash scripting for automation and deployment
- Heredocs for multi-file generation
- sed/awk for configuration and text processing
- Process management and job control

### File System & Data Flow
- Structured directory hierarchy for multi-language project
- Binary file I/O for raw RF capture (8-bit I/Q interleaved)
- JSON for configuration, scheduling, and inter-process data exchange
- Persistent logging and mission data storage

### Platform
- Primary: macOS (Apple Silicon M4)
- Backup: Linux/Windows (ASUS ROG G14)
- Target: Raspberry Pi for field deployment

---

## Current Status

### V0 Complete (January 16, 2026)
- SGP4 orbital propagator validated to ±15s accuracy
- Doppler frequency calculations verified
- 7-day pass forecasts for State College, PA

### Environment Verified (January 30, 2026)
- RTL-SDR v4 hardware control via C++
- MATLAB spectrum capture validated
- CMake + librtlsdr build system configured

### V1 In Progress (February 2026)
- Custom VHF dipole antenna fabricated
- Awaiting first satellite capture

### V4-V6 Software Complete (February 11, 2026)
- Full automation pipeline operational
- Real-time C++ capture with ring buffer
- Doppler tracking from JSON profiles
- Mission logging and ML data store
- End-to-end runner with daemon mode
- ML pipeline: feature engineering, scoring, prediction, training, optimization
- Schedule optimizer generating ranked capture plans

---

## Project Structure
```
satellite-ground-station/
├── docs/
│   ├── requirements/           # FR-1 to FR-7, performance, interface specs
│   ├── architecture/           # L0-L2 decomposition, ICDs, verification plan
│   └── ml/                     # ML architecture, feature definitions
│
├── python/
│   ├── predict_passes.py       # SGP4 orbital propagator [COMPLETE]
│   ├── doppler_calc.py         # Doppler shift profiles [COMPLETE]
│   ├── schedule_captures.py    # Pass scheduling, daemon mode [COMPLETE]
│   ├── data_store.py           # Mission logging, ML training data [COMPLETE]
│   ├── run_mission.py          # End-to-end automation [COMPLETE]
│   ├── demod/
│   │   ├── decode_apt.py       # Raw I/Q to APT image [COMPLETE]
│   │   └── decode_apt_wav.py   # WAV decoder for testing [COMPLETE]
│   └── ml/
│       ├── feature_engineering.py  # Orbital, weather, historical features [COMPLETE]
│       ├── pass_scorer.py          # Rule-based baseline scoring [COMPLETE]
│       ├── ml_predictor.py         # ML model inference [COMPLETE]
│       ├── model_trainer.py        # RandomForest training pipeline [COMPLETE]
│       └── scheduler_optimizer.py  # Constrained schedule optimization [COMPLETE]
│
├── cpp/
│   ├── src/
│   │   ├── rtlsdr_test.cpp     # Hardware verification [COMPLETE]
│   │   ├── rtlsdr_capture.cpp  # Async I/Q streaming [COMPLETE]
│   │   └── doppler_tracker.cpp # Real-time frequency correction [COMPLETE]
│   ├── build/                  # Compiled executables
│   └── CMakeLists.txt          # Build configuration [COMPLETE]
│
├── matlab/
│   ├── tests/                  # SDR and environment verification
│   ├── capture/                # I/Q capture scripts
│   ├── analysis/               # Post-capture metrics
│   └── utilities/              # PSD, SNR computation
│
└── data/
    ├── tle/                    # Cached TLE files
    ├── captures/               # Raw I/Q recordings
    ├── decoded/                # APT images (PNG)
    ├── doppler/                # Doppler profiles (JSON)
    └── ml/
        ├── training/           # Mission outcome data
        └── models/             # Trained model files (.joblib)
```

---

## Quick Start

### Prerequisites
```bash
brew install librtlsdr cmake
pip3 install skyfield numpy scipy pillow pandas scikit-learn joblib
```

### Build C++ Components
```bash
cd cpp && mkdir -p build && cd build
cmake .. && make
```

### List Upcoming Passes
```bash
python3 python/schedule_captures.py list
```

### Generate Optimized Schedule
```bash
PYTHONPATH=. python3 python/ml/scheduler_optimizer.py --hours 48
```

### Run Mission (Dry Run)
```bash
python3 python/run_mission.py --dry-run
```

### Run Mission (Full Capture)
```bash
python3 python/run_mission.py --min-el 30
```

### Manual Capture
```bash
./cpp/build/rtlsdr_capture -f 137100000 -g 40 -d 900 -o capture.bin
```

### Decode APT Image
```bash
python3 python/demod/decode_apt.py data/captures/capture.bin
```

### Run Capture Daemon (24hr)
```bash
python3 python/schedule_captures.py daemon --hours 24
```

### Train ML Models (after 20+ missions)
```bash
PYTHONPATH=. python3 python/ml/model_trainer.py train
```

---

## ML Pipeline

The system includes a complete ML pipeline for mission optimization:

### Feature Engineering
- **Orbital:** max elevation, duration, azimuth range, time of day
- **Weather:** cloud cover, precipitation probability, temperature
- **Historical:** recent success rate, satellite-specific performance
- **Hardware:** gain setting, LNA status, antenna configuration

### Models
- **Success Classifier:** RandomForest predicting decode success (binary)
- **SNR Regressor:** RandomForest predicting signal quality (dB)

### Training
- Minimum 20 mission samples required
- 80/20 train/test split with cross-validation
- Automatic feature importance analysis
- Model versioning and metadata tracking

### Scheduling
- Constraint-based optimization (min gap, max per day, diversity)
- Ranked pass recommendations with confidence scores
- Rule-based fallback when ML models unavailable

---

## Documentation

| Document | Description |
|----------|-------------|
| Functional Requirements | FR-1 through FR-7 (orbital, RF, DSP, automation, ML) |
| Performance Requirements | PR-1 through PR-4 (timing, SNR, success rate) |
| L0-L2 Architecture | System context, subsystem decomposition, implementation |
| Interface Control | 5 ICDs covering hardware, software, data interfaces |
| Verification Plan | V0-V6 staged verification with pass/fail criteria |
| LNA Design | BFP420 schematic, 75Ω/50Ω matching, BOM, test plan |

---

## Author

Luke Waszyn  
Engineering Science, The Pennsylvania State University

GitHub: [lukejwaszyn](https://github.com/lukejwaszyn)

---

## License

MIT License - see LICENSE file for details

---

## Acknowledgments

- Systems engineering methodology inspired by JPL mission design practices
- Orbital mechanics via [Skyfield](https://rhodesmill.org/skyfield/) by Brandon Rhodes
- RTL-SDR community for hardware documentation and librtlsdr
