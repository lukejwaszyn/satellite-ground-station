# Autonomous Satellite Ground Station

## Overview

Autonomous ground station and mission operations platform for NOAA weather satellite APT image reception. Features custom VHF antenna, low-noise amplifier, real-time DSP pipeline, AI-driven mission planning, and an interactive 3D mission operations interface tracking 12 satellites across multiple constellations — all integrated through a unified mission server with REST API.

**Project Duration:** 10 weeks (January 16 - March 30, 2026)

**Objective:** Autonomous NOAA APT reception with >80% decode success rate, ML-optimized mission scheduling, and real-time operator situational awareness

---

## Quick Start

```bash
git clone https://github.com/lukejwaszyn/satellite-ground-station.git
cd satellite-ground-station
python3 satcom_server.py
# Open http://localhost:8080
```

Edit `config.json` with your station coordinates. No hardware required for tracking mode — add an RTL-SDR and antenna to capture signals.

---

## Mission Operations Interface

The system includes SATCOM, a 3D mission operations interface built with Three.js that provides real-time situational awareness and integrated mission control:

- **Multi-constellation tracking:** 12 satellites across NOAA, METEOR, ISS, Landsat, Terra, and Aqua
- **Real SGP4 propagation:** Skyfield backend with live TLE data from Celestrak
- **Pass prediction:** AOS/TCA/LOS timeline with live state transitions, countdown, azimuth, elevation, range
- **Doppler visualization:** Real-time Doppler shift profiles with TCA zero-crossing
- **Elevation profiles:** Pass geometry charts for each upcoming pass
- **Mission control panel:** SDR status indicator, next capturable pass with AOS gate, one-click capture trigger
- **Mission log:** Capture history with decode status and image links served from the HMI
- **Satellite roles:** Primary imaging target (NOAA 20), weather constellation, and display satellites

---

## Mission Server & REST API

All subsystems are integrated through `satcom_server.py`, a unified backend that serves the HMI and exposes programmatic control:

```bash
python3 satcom_server.py                # Default port 8080
python3 satcom_server.py --port 3000    # Custom port
python3 satcom_server.py --no-generate  # Skip initial orbital data generation
```

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Mission operations HMI |
| `/api/orbital-data` | GET | Live orbital data (SGP4 propagation, 10-min cache) |
| `/api/passes` | GET | Upcoming passes with elevation/role filtering |
| `/api/status` | GET | System status (SDR, capture state, uptime) |
| `/api/capture` | POST | Trigger satellite capture (AOS-gated) |
| `/api/missions` | GET | Mission history and decoded images |
| `/api/config` | GET/PUT | Station configuration |
| `/api/refresh` | POST | Force orbital data regeneration |
| `/api/decoded/<file>` | GET | Serve decoded APT images |

### Integration Architecture

```
Browser (localhost:8080)
  └── satellite-viz.html (Three.js 3D globe + mission control panel)
        │
        ├── GET  /api/orbital-data  → generate_orbital_data.py (Skyfield SGP4)
        ├── GET  /api/passes        → schedule_captures.py (pass prediction)
        ├── GET  /api/status        → system state (SDR, capture, uptime)
        ├── POST /api/capture       → run_capture_async → rtlsdr_capture (C++)
        │                                                → decode_apt.py (DSP)
        │                                                → data_store.py (ML log)
        ├── GET  /api/missions      → mission_log.json
        └── GET  /api/decoded/*     → decoded APT images (PNG)
```

---

## System Architecture

This project follows a formal systems engineering methodology with requirements-driven development and staged verification:

- **L0 System Context:** End-to-end RF receive chain from antenna to decoded imagery, plus mission operations display
- **L1 Subsystems:** Orbital prediction, RF front-end, digital capture, DSP processing, automation, AI mission planning, mission operations HMI
- **L2 Implementation:** Python/C++/JavaScript/MATLAB implementation with hardware integration and ML pipeline

### Subsystem Status

| # | Subsystem | Technology | Status |
|---|-----------|-----------|--------|
| 1 | Orbital Prediction | Python/Skyfield SGP4 | Complete |
| 2 | RF Front-End | Custom VHF dipole, LNA (BFP420) | Antenna built, LNA in fab |
| 3 | Digital Capture | C++/librtlsdr async streaming | Complete |
| 4 | DSP & Decoding | Python/SciPy FM demod + APT sync | Complete |
| 5 | Automation & Control | Python orchestration + REST API | Complete |
| 6 | AI Mission Planning | Python/scikit-learn RandomForest | Complete |
| 7 | Mission Operations HMI | JavaScript/Three.js/WebGL | Complete |

---

## Verification Strategy

| Stage | Objective | Status |
|-------|-----------|--------|
| V0 | Orbital prediction validated (±15s accuracy) | **Complete** |
| V0.5 | Mission operations HMI validated (12 satellites, 5 constellations) | **Complete** |
| V1 | RF link established (SDR captures signal) | **Complete** — first capture Feb 27, 2026 |
| V2 | LNA integration and SNR improvement | Planned (PCB in fabrication) |
| V3 | Functional decode (first image) | Pipeline validated with public NOAA 19 sample |
| V4 | Automated Doppler tracking | Software complete |
| V5 | Multi-pass performance characterization (25+ images) | Planned |
| V6 | ML mission planning integration | Software complete |

### First Capture (V1 Milestone — February 27, 2026)

The system executed its first end-to-end capture via the mission operations HMI:
- **Satellite:** NOAA 18 at 89.4° max elevation (nearly overhead)
- **Pipeline:** HMI capture button → REST API → C++ async I/Q recording (717s) → APT decoder → mission log
- **Result:** Full 7-subsystem integration validated end-to-end

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
- Low-noise amplifier (15-20 dB gain, <1.5 dB NF) — PCB in fabrication
- Coaxial RF transmission lines (50Ω impedance)

### Software Stack

| Language | Purpose |
|----------|---------|
| Python | Orbital mechanics, ML pipeline, orchestration, APT decoding, mission server |
| C++ | Real-time async I/Q capture, ring buffer, Doppler tracking |
| JavaScript | 3D mission operations interface (Three.js / WebGL) |
| MATLAB | Signal processing, PSD analysis, verification |

### Core Capabilities

- **Orbital Mechanics:** SGP4 propagation via Skyfield, multi-constellation tracking (12 satellites)
- **Signal Processing:** FM demodulation, APT sync detection, image reconstruction
- **Real-Time Control:** Automated Doppler frequency compensation in C++
- **ML Mission Planning:** Pass scoring, success prediction, schedule optimization
- **Mission Server:** REST API integrating all subsystems with AOS-gated capture control
- **Mission Operations HMI:** 3D globe with real-time satellite positions, pass timeline, Doppler/elevation charts, mission control panel

---

## Current Status

### Software Complete
All software subsystems are implemented, integrated, and operational:

- **Mission Server:** Unified REST API backend connecting all subsystems (satcom_server.py)
- **Orbital Prediction:** SGP4 propagator, pass scheduling, Doppler calculation (predict_passes.py, doppler_calc.py)
- **APT Decoding:** FM demodulation, sync detection, image reconstruction (decode_apt.py, decode_apt_wav.py)
- **Real-Time Capture:** C++ async I/Q streaming with ring buffer (rtlsdr_capture.cpp, doppler_tracker.cpp)
- **Mission Automation:** End-to-end autonomous capture orchestration (schedule_captures.py, run_mission.py)
- **ML Pipeline:** Feature engineering, pass scoring, success prediction, schedule optimization, model training (6 modules)
- **Mission Operations HMI:** 3D multi-constellation visualizer with integrated mission control (satellite-viz.html)

### V1 Complete — First Capture
- First end-to-end capture executed February 27, 2026 via HMI
- NOAA 18 at 89.4° elevation, 717-second I/Q recording
- Full pipeline validated: HMI → API → C++ capture → APT decode → mission log
- Custom VHF dipole antenna fabricated and operational
- LNA PCB in fabrication

---

## Project Structure

```
satellite-ground-station/
├── satcom_server.py               # Mission operations server (REST API)         [DONE]
├── config.json                    # Station configuration
│
├── hmi/
│   ├── generate_orbital_data.py   # Skyfield SGP4 multi-constellation backend    [DONE]
│   └── satellite-viz.html         # 3D mission ops frontend (Three.js)           [DONE]
│
├── python/
│   ├── predict_passes.py          # SGP4 propagator                              [DONE]
│   ├── doppler_calc.py            # Doppler frequency profiles                   [DONE]
│   ├── schedule_captures.py       # Automation orchestrator                      [DONE]
│   ├── run_mission.py             # End-to-end mission execution                 [DONE]
│   ├── data_store.py              # Mission logging + ML data store              [DONE]
│   ├── demod/
│   │   ├── decode_apt.py          # Raw I/Q APT decoder                          [DONE]
│   │   └── decode_apt_wav.py      # WAV APT decoder (testing)                    [DONE]
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
│   │   ├── rtlsdr_capture.cpp     # Async I/Q streaming with ring buffer        [DONE]
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
    ├── decoded/                   # APT images (PNG)
    ├── doppler/                   # Doppler profiles (JSON)
    ├── test_samples/              # Pipeline validation samples
    └── ml/                        # Training data, models, predictions
```

---

## Configuration

Edit `config.json` to set your station location:

```json
{
  "station": {
    "name": "My Ground Station",
    "lat": 40.7934,
    "lon": -77.8600,
    "elevation_m": 376.0,
    "min_elevation_deg": 10.0
  },
  "capture": {
    "sample_rate": 2.4e6,
    "gain_db": 40,
    "primary_freq_hz": 137.1e6
  },
  "hmi": {
    "propagation_hours": 24,
    "position_step_sec": 30,
    "http_port": 8080
  }
}
```

---

## Command-Line Tools

```bash
# List upcoming passes
python3 python/schedule_captures.py list

# Generate optimized capture schedule
PYTHONPATH=. python3 python/ml/scheduler_optimizer.py --hours 48

# Run a capture mission directly
python3 python/run_mission.py --min-el 30

# Decode a test WAV file
python3 python/demod/decode_apt_wav.py data/test_samples/argentina.wav

# Run 24hr capture daemon
python3 python/schedule_captures.py daemon --hours 24
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
- joblib (model persistence)

**HMI Stack:**
- Three.js r128 (3D globe, satellite meshes, orbital trails)
- HTML5 Canvas (elevation and Doppler charts)
- Skyfield (SGP4 propagation backend)

**Server:**
- Python http.server (zero external dependencies)
- REST API with JSON responses
- Background thread capture execution

**Hardware:**
- RTL-SDR Blog V4 (R828D tuner)
- Custom VHF dipole antenna
- Custom LNA PCB (BFP420)

**Platform:**
- Primary: macOS (Apple Silicon M4)
- Compatible: Linux, Windows (WSL)

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

- Orbital mechanics via [Skyfield](https://rhodesmill.org/skyfield/) by Brandon Rhodes
- 3D visualization built with [Three.js](https://threejs.org/)
- TLE data from [Celestrak](https://celestrak.org/)
- APT decode pipeline validated with sample from [noaa-apt](https://noaa-apt.mbernardi.com.ar/)
- RTL-SDR community for hardware documentation and librtlsdr
- Systems engineering methodology inspired by JPL mission design practices
