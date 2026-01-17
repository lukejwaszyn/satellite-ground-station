# L2: Implementation Architecture

## Software Structure

```
satellite-ground-station/
├── python/
│   ├── predict_passes.py          # SGP4 propagator, pass forecasting
│   ├── doppler_calc.py            # Real-time Doppler frequency calculator
│   ├── schedule_captures.py       # Automation: orchestrates captures
│   ├── decode_apt.py              # Offline APT image decoder
│   └── utils/
│       ├── tle_fetch.py           # TLE download from Celestrak
│       └── logging_config.py      # Centralized logging setup
│
├── cpp/
│   ├── rtlsdr_capture.cpp         # Real-time I/Q streaming
│   ├── doppler_tracker.cpp        # Real-time frequency correction loop
│   ├── fm_demod.cpp               # FM discriminator (future real-time)
│   └── CMakeLists.txt             # Build configuration
│
├── matlab/
│   ├── analysis/
│   │   ├── analyze_pass.m         # Post-pass SNR, spectral metrics
│   │   └── visualize_orbit.m      # Ground track, elevation profile
│   └── utilities/
│       └── compute_metrics.m      # Reuse from RTL-SDR V4 project
│
├── data/
│   ├── tle/                       # Cached TLE files (updated daily)
│   ├── captures/                  # Raw I/Q recordings (.bin + .json)
│   ├── decoded/                   # APT images (.png, .jpg)
│   └── logs/                      # System logs, error reports
│
├── docs/
│   ├── requirements/              # Functional, performance, interface
│   ├── architecture/              # L0, L1, L2, interface control
│   ├── verification/              # V0-V5 results, test reports
│   └── project_management/        # Timeline, risks, decisions
│
└── tests/
    ├── test_sgp4.py               # Unit tests for orbital propagation
    ├── test_doppler.py            # Doppler calculation validation
    └── test_apt_decode.py         # APT decoder smoke tests
```

---

## Data Flow Architecture

### 1. **Orbital Prediction Flow**
```
Celestrak (HTTPS) → tle_fetch.py → data/tle/NOAA.txt
                 ↓
           predict_passes.py (SGP4) → Pass schedule JSON
                 ↓
           doppler_calc.py → Doppler profile (frequency vs time)
```

### 2. **Automated Capture Flow**
```
schedule_captures.py (reads pass schedule)
        ↓
    [At AOS] Launch rtlsdr_capture (C++)
        ↓
    rtlsdr_capture.cpp (streams I/Q from SDR)
        ├→ Writes raw I/Q to data/captures/NOAA18_YYYYMMDD_HHMMSS.bin
        └→ Reads Doppler corrections from doppler_tracker.cpp
        ↓
    [At LOS] Terminate capture
        ↓
    decode_apt.py (processes raw I/Q)
        ├→ FM demodulation
        ├→ APT sync detection
        └→ Image reconstruction
        ↓
    Output: data/decoded/NOAA18_YYYYMMDD_HHMMSS.png
```

### 3. **Real-Time Doppler Compensation (V4+)**
```
predict_passes.py → Doppler profile (pre-computed)
        ↓
doppler_tracker.cpp (reads profile, updates SDR in real-time)
        ├→ Calculates instantaneous frequency offset
        └→ Sends tuning command to rtlsdr_capture.cpp every 1-5 sec
```

---

## Key Technologies

### Python Stack
- **Skyfield:** SGP4 orbital propagation, pass prediction
- **NumPy:** Numerical arrays, signal processing
- **SciPy:** Filtering, resampling, signal analysis
- **Matplotlib:** Visualization (orbits, spectra, images)
- **Requests:** TLE download from Celestrak

### C++ Stack
- **librtlsdr:** SDR hardware interface
- **Boost (optional):** File I/O, threading, time handling
- **Standard Library:** Vectors, file streams, chrono

### MATLAB (Analysis Only)
- **Signal Processing Toolbox:** PSD analysis, filtering
- **Communications Toolbox:** RTL-SDR interface (for manual testing)
- Reuse existing utilities from RTL-SDR project

---

## Development Phases

### Phase 1: Python Prototype (Weeks 1-5)
- All processing in Python (predict, capture via librtlsdr wrapper, decode)
- Validates algorithms and workflows
- Slower than real-time, but functional

### Phase 2: C++ Real-Time (Week 6)
- Port capture + Doppler tracking to C++ for performance
- Python handles orchestration and decoding
- Achieves real-time operation with automated frequency tracking

### Phase 3: Polish & Optimization (Week 7)
- Performance tuning
- Error handling and robustness
- Documentation and test coverage

---

## Build & Deployment

### Python Environment
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows

# Install dependencies
pip install skyfield numpy scipy matplotlib requests
```

### C++ Build
```bash
# Install librtlsdr (macOS example)
brew install librtlsdr

# Build C++ programs
cd cpp/
mkdir build && cd build
cmake ..
make

# Binaries output to cpp/build/
```

### MATLAB Setup
- Ensure Communications Toolbox installed
- Add `matlab/` subdirectories to MATLAB path
- Link to RTL-SDR utilities from previous project

---

## Configuration Management

### System Configuration (config.json)
```json
{
  "observer": {
    "latitude": 40.7934,
    "longitude": -77.8600,
    "elevation_m": 350,
    "name": "State College, PA"
  },
  "satellites": {
    "NOAA-15": {"frequency_hz": 137620000, "active": true},
    "NOAA-18": {"frequency_hz": 137912500, "active": true},
    "NOAA-19": {"frequency_hz": 137100000, "active": true}
  },
  "capture": {
    "sample_rate_hz": 2400000,
    "output_sample_rate_hz": 250000,
    "min_elevation_deg": 10,
    "sdr_gain_db": 40
  },
  "paths": {
    "tle_cache": "data/tle/",
    "captures": "data/captures/",
    "decoded": "data/decoded/",
    "logs": "data/logs/"
  }
}
```

---

## Logging Strategy

- **Python:** Standard `logging` module, INFO level default
- **C++:** Simple stdout logging with timestamps
- **Log rotation:** Daily log files, keep last 30 days
- **Error alerting:** Critical errors logged to dedicated file

**Log locations:**
- `data/logs/predict_YYYYMMDD.log`
- `data/logs/capture_YYYYMMDD.log`
- `data/logs/decode_YYYYMMDD.log`
- `data/logs/errors.log` (all errors from all subsystems)

---

## Testing Strategy

### Unit Tests
- `tests/test_sgp4.py`: Validate pass predictions against known data
- `tests/test_doppler.py`: Check Doppler calculation accuracy
- `tests/test_apt_decode.py`: Decode known-good I/Q file

### Integration Tests
- End-to-end test: Predict → Capture (simulated) → Decode
- Verify file formats and interfaces

### System Tests
- Capture actual satellite pass
- Validate decoded image quality
- Measure timing accuracy (AOS/LOS within ±30s)

---

## Performance Targets

### Python Performance
- Pass prediction: <1 second for 7-day forecast
- Doppler calculation: <100 ms per time step
- APT decode: <10 seconds for 10-minute pass

### C++ Performance (V4+)
- I/Q capture: Real-time at 250 kHz (no sample drops)
- Doppler tracking: <10 ms latency for frequency updates
- CPU usage: <50% on typical laptop during capture

### Storage Requirements
- Raw I/Q per pass: ~300 MB (10 minutes @ 250 kHz, float32)
- Decoded image: ~2 MB (PNG, lossless compression)
- TLE cache: <1 MB
- Logs: ~10 MB/day

---

## Platform Compatibility

**Primary Development Platform:**
- macOS (Apple Silicon M4 - MacBook Air)

**Backup Platform:**
- Windows/Linux (ASUS ROG G14)

**Dependencies:**
- Python 3.10+
- librtlsdr (installed via Homebrew on macOS)
- C++17 compiler (clang on macOS, GCC on Linux)
- MATLAB R2023b+ (for analysis only)

**Cross-Platform Notes:**
- Python code is platform-agnostic
- C++ uses standard library + librtlsdr (available on all platforms)
- MATLAB analysis scripts portable across macOS/Windows/Linux
