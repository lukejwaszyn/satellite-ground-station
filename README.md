# Autonomous Satellite Ground Station

## Overview

Autonomous ground station for NOAA weather satellite APT image reception using custom VHF antenna, low-noise amplifier, and real-time DSP pipeline.

**Project Duration:** 7 weeks (January 16 - March 7, 2026)  
**Objective:** Autonomous NOAA APT reception with greater than 80% decode success rate

## System Architecture

This project follows a formal systems engineering methodology with requirements-driven development and staged verification:

- **L0 System Context:** End-to-end RF receive chain from antenna to decoded imagery
- **L1 Subsystems:** Orbital prediction, RF front-end, digital capture, DSP processing, automation
- **L2 Implementation:** Python/C++ implementation with hardware integration

## Verification Strategy

| Stage | Objective | Status |
|-------|-----------|--------|
| V0 | Orbital prediction validated | Complete |
| V1 | RF link established | In Progress |
| V2 | LNA integration and SNR improvement | Planned |
| V3 | Functional decode (first image) | Planned |
| V4 | Automated Doppler tracking | Planned |
| V5 | Multi-pass performance characterization | Planned |

## Technical Approach

### Hardware
- RTL-SDR v4 software-defined radio
- Custom half-wave VHF dipole antenna (137 MHz)
- Low-noise amplifier (15-20 dB gain, <1.5 dB NF)
- Coaxial RF transmission lines (50Ω impedance)

### Software
- **Orbital Mechanics:** SGP4 propagation using Skyfield library
- **Signal Processing:** FM demodulation, APT image decoding
- **Real-Time Control:** Automated Doppler frequency compensation
- **Languages:** Python (orchestration, offline processing), C++ (real-time capture)

### Methodology
Requirements definition, architecture decomposition, interface control, and staged verification with documented pass/fail criteria and measured performance metrics.

## Current Status

**V0 Verification Complete (January 16, 2026)**
- SGP4 orbital propagator implemented and validated
- Pass predictions accurate within 15 seconds vs. reference data
- Doppler frequency calculations validated
- 7-day pass forecasts generated for State College, PA

## Documentation

Complete systems engineering documentation available in `docs/`:

### Requirements
- Functional requirements (FR-1 through FR-5)
- Performance requirements (PR-1 through PR-4)
- Interface requirements (hardware, software, data)

### Architecture
- L0 system context (external entities, boundaries)
- L1 subsystem decomposition (5 subsystems with interfaces)
- L2 implementation details (directory structure, tech stack)
- Interface Control Document (5 ICDs with detailed schemas)

### Verification
- V0-V5 staged verification plan
- Pass/fail criteria for each stage
- Requirements traceability matrix

### Project Management
- Risk register (10 identified risks with mitigation strategies)

## Technologies

**Programming Languages:**
- Python 3.10+ (Skyfield, NumPy, SciPy, Matplotlib)
- MATLAB (signal processing, analysis)
- C++17 (real-time embedded systems)

**Hardware:**
- RTL-SDR v4
- Custom VHF antenna (in fabrication)
- Low-noise amplifier (in design)

**Platform:**
- Primary: macOS (Apple Silicon M4)
- Backup: Windows/Linux

## Project Structure
```
satellite-ground-station/
├── docs/                           # Systems engineering documentation
│   ├── requirements/               # Functional, performance, interface
│   ├── architecture/               # L0-L2, interface control
│   ├── verification/               # V0-V5 verification plan
│   └── project_management/         # Risk register, timeline
├── python/                         # Python implementation
│   └── predict_passes.py           # SGP4 propagator (V0)
└── README.md                       # This file
```

## Author

Luke Waszyn  
Engineering Science, The Pennsylvania State University  
[GitHub](https://github.com/lukejwaszyn)

## License

MIT License - see LICENSE file for details

## Acknowledgments

This project applies formal systems engineering methodology inspired by JPL's approach to mission design and verification. Orbital mechanics implementation uses the Skyfield library by Brandon Rhodes.
