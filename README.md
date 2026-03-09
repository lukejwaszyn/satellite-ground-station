# Autonomous Satellite Ground Station

## Overview

Autonomous ground station for NOAA weather satellite APT image reception with integrated mission operations interface, real-time orbital tracking, and ML-driven mission planning. Built as a solo project with 7 integrated subsystems, 7,000+ lines of source code across Python, C++, JavaScript, and MATLAB.

**Project Duration:** January 16 - Present (ongoing)  
**Author:** Luke Waszyn, Engineering Science, Penn State  
**Status:** V3 Complete - First satellite signal decoded, image quality iteration in progress

---

## Quick Start

```bash
# Install dependencies
pip install skyfield numpy scipy pillow scikit-learn pandas

# Start the mission server
cd satellite-ground-station
python3 satcom_server.py

# Open the HMI
# Navigate to http://localhost:8080
```

The mission server automatically generates orbital data for 11 satellites across 5 constellations, starts the REST API, and serves the 3D mission operations interface.

---

## System Architecture

Formal systems engineering methodology with requirements-driven development and staged verification:

- **L0 System Context:** End-to-end RF receive chain from antenna to decoded imagery
- **L1 Subsystems:** 7 subsystems (orbital prediction, RF front-end, digital capture, DSP/decode, mission server, HMI, ML planning)
- **L2 Implementation:** Python/C++/JavaScript with hardware integration

### Integration Architecture

```
Browser HMI (Three.js/WebGL)
    |
    | HTTP/REST
    v
Mission Server (Python Flask - satcom_server.py)
    |
    |--- Orbital Predictor (Skyfield SGP4)
    |--- Doppler Calculator 
    |--- Capture Orchestrator --> C++ Binary (rtlsdr_capture)
    |--- APT Decoder (decode_apt.py)
    |--- ML Pipeline (scikit-learn)
    |--- Mission Logger
    |
    v
RTL-SDR v4 --> SAWbird LNA --> VHF Antenna
```

---

## Mission Operations Interface

The browser-based HMI provides real-time mission operations:

- **3D Globe:** Real-time satellite positions for 12 spacecraft across 5 constellations (NOAA, METEOR, ISS, GOES, Landsat)
- **Pass Timeline:** Live AOS/TCA/LOS state transitions with satellite-specific data
- **Mission Control Panel:** SDR status, AOS-gated capture button, frequency display
- **Mission Log:** Capture history with decoded image display
- **Orbit Visualization:** Ground tracks, coverage footprints, orbital planes

---

## Verification Status

| Stage | Objective | Status | Date |
|-------|-----------|--------|------|
| V0 | Orbital prediction validated | **Complete** | Jan 16, 2026 |
| V0.5 | SDR environment verified | **Complete** | Jan 30, 2026 |
| V1 | RF link established (first capture) | **Complete** | Feb 27, 2026 |
| V2 | LNA integration (SAWbird NOAA) | **Complete** | Mar 6, 2026 |
| V3 | Signal decoded (831 sync pulses) | **Complete** | Mar 6, 2026 |
| V3+ | Clean decoded image with features | **In Progress** | - |
| V4 | Automated Doppler tracking | Planned | - |
| V5 | Multi-pass characterization (25+ images) | Planned | - |
| V6 | ML mission planning integration | Planned | - |

---

## Hardware

| Component | Specification |
|-----------|--------------|
| SDR | RTL-SDR Blog V4 (R828D tuner, 24-1766 MHz) |
| LNA | Nooelec SAWbird NOAA (20 dB gain, 0.7 dB NF, 137.5 MHz center, SAW filter) |
| Antenna | Stock VHF dipole (QFH antenna in fabrication) |
| Feed | 50 ohm coaxial with SMA interface |

**RF Chain:** Antenna --> SAWbird LNA --> Coax --> RTL-SDR v4 --> USB --> MacBook Air M4

---

## Software Stack

| Language | Lines | Purpose |
|----------|-------|---------|
| Python | ~4,200 | Orbital mechanics, ML pipeline, orchestration, APT decoding, mission server |
| JavaScript/HTML | ~1,300 | 3D mission operations interface (Three.js, WebGL) |
| C++ | ~580 | Real-time I/Q capture with async streaming, Doppler tracking |
| MATLAB | ~70 | Spectrum analysis, verification |
| **Total** | **~7,100** | |

### Key Files

| File | Lines | Description |
|------|-------|-------------|
| `satellite-viz.html` | 1,293 | 3D HMI with mission control |
| `satcom_server.py` | 736 | Unified REST API mission server |
| `generate_orbital_data.py` | 582 | Multi-constellation orbital predictor |
| `schedule_captures.py` | 465 | Capture orchestration and pipeline |
| `model_trainer.py` | 418 | ML model training pipeline |
| `data_store.py` | 410 | Mission database layer |
| `decode_apt.py` | 358 | Memory-efficient APT decoder (chunked processing) |
| `pass_scorer.py` | 338 | Rule-based and ML pass scoring |
| `feature_engineering.py` | 337 | ML feature extraction |
| `scheduler_optimizer.py` | 315 | Schedule optimization engine |
| `run_mission.py` | 315 | Autonomous mission execution |
| `ml_predictor.py` | 309 | ML prediction interface |
| `doppler_tracker.cpp` | 303 | Real-time Doppler compensation |
| `rtlsdr_capture.cpp` | 280 | Async I/Q capture with ring buffer |
| `doppler_calc.py` | 225 | Doppler frequency profiles |

---

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Mission operations HMI |
| `/api/status` | GET | System status (SDR, capture state, satellite info) |
| `/api/passes` | GET | Predicted passes with Doppler profiles |
| `/api/capture` | POST | Trigger satellite capture |
| `/api/config` | GET | Station configuration |
| `/api/missions` | GET | Mission log history |
| `/api/decoded/<file>` | GET | Decoded image retrieval |
| `/api/orbital-data` | GET | Current orbital data for HMI |

---

## Milestone History

### V1 - First Capture (February 27, 2026)
- NOAA 18 at 89.4 deg elevation, 717-second pass
- Full pipeline executed: HMI capture button --> REST API --> C++ binary --> decoder
- Image was black due to frequency bug (captured at 137.1 MHz instead of NOAA 18's 137.9125 MHz)
- Root cause identified and fixed: frontend now sends satellite-specific frequency

### V1.5 - Decoder Fix (March 3, 2026)
- Identified critical dtype bug: decoder read raw binary as float32 instead of uint8
- This caused it to process only 1/4 of actual samples with garbage values
- Fixed to read as uint8 with normalization to [-1, 1]
- Re-decoded NOAA 19 capture: first sync pulses detected (2 found)

### V2 - LNA Integration (March 6, 2026)
- Nooelec SAWbird NOAA integrated into RF chain
- 20 dB gain, 0.7 dB noise figure, built-in SAW bandpass filter
- Powered via bias tee or microUSB
- Verified amplification via spectrum scan (power levels -19 to -24 dB vs noise floor)

### V3 - First Signal Decode (March 6, 2026)
- NOAA 15 at 20.4 deg: 135 sync pulses detected, APT frame structure visible
- NOAA 19 at 89.0 deg: 831 sync pulses detected, full-length pass decoded
- Memory-efficient chunked decoder implemented (processes 3+ GB files in ~2-3 GB RAM)
- Image noisy but APT structure confirmed, antenna upgrade (QFH) in progress

---

## Decoded Signal Progression

| Date | Satellite | Elevation | Sync Pulses | Result |
|------|-----------|-----------|-------------|--------|
| Feb 27 | NOAA 18 | 89.4 deg | 0 | Black (wrong frequency) |
| Mar 3 | NOAA 19 | 41.6 deg | 0 (dtype bug) | Black (float32 vs uint8) |
| Mar 3 | NOAA 19 | 41.6 deg | 2 (reprocessed) | Faint sync lines visible |
| Mar 6 | NOAA 15 | 20.4 deg | 135 | APT frame structure visible |
| Mar 6 | NOAA 19 | 89.0 deg | 831 | Full pass decoded, noisy image |

---

## Next Steps

- **Antenna:** Build QFH antenna from speaker wire for circular polarization and skyward gain pattern
- **Image Quality:** Verify LNA power delivery, tune antenna element length, optimize decoder
- **Daytime Capture:** Visible channel (Channel A) for higher contrast features
- **Weather API:** Integrate cloud cover data for capture quality prediction
- **ML Training:** Collect 20+ captures to build training dataset for V6

---

## Documentation

All documentation follows formal systems engineering standards:

- **Requirements:** Functional (FR-1 to FR-8), performance (PR-1 to PR-4), interface
- **Architecture:** L0 system context, L1 subsystem decomposition (7 subsystems), L2 implementation
- **Interface Control:** 6 ICDs with data schemas and protocols
- **Verification:** V0-V6 staged plan with pass/fail criteria and requirements traceability
- **ML Architecture:** Feature definitions, model specs, training procedures

---

## Technologies

**Languages:** Python 3.10+, C++17, JavaScript (ES6+), MATLAB  
**Libraries:** Skyfield, NumPy, SciPy, Pillow, scikit-learn, pandas, Three.js, WebGL  
**Hardware:** RTL-SDR Blog V4, Nooelec SAWbird NOAA, VHF dipole antenna  
**Platform:** macOS (Apple Silicon M4)  
**Build:** CMake (C++), pip (Python)

---

## License

MIT License - see LICENSE file for details

---

## Acknowledgments

This project applies formal systems engineering methodology inspired by JPL's approach to mission design and verification. Orbital mechanics implementation uses the Skyfield library by Brandon Rhodes. APT signal format based on NOAA KLM User's Guide.
