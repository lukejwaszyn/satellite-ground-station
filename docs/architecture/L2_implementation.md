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
├── python/ml/                     # AI Mission Planning module
│   ├── __init__.py
│   ├── feature_engineering.py     # Extract features from pass/weather data
│   ├── pass_scorer.py             # Rule-based pass scoring (Phase 1)
│   ├── ml_predictor.py            # ML-based success prediction (Phase 2)
│   ├── scheduler_optimizer.py     # Generate optimal capture schedule
│   ├── adaptive_controller.py     # Real-time recommendations during capture
│   ├── model_trainer.py           # Train/retrain ML models
│   ├── analytics.py               # Generate reports and dashboards
│   └── data_store.py              # Historical data management
│
├── cpp/
│   ├── src/
│   │   ├── rtlsdr_test.cpp        # SDR hardware verification
│   │   ├── rtlsdr_capture.cpp     # Real-time I/Q streaming
│   │   ├── doppler_tracker.cpp    # Real-time frequency correction loop
│   │   └── fm_demod.cpp           # FM discriminator (future real-time)
│   ├── include/
│   │   └── rtlsdr_utils.h         # Shared utilities
│   └── CMakeLists.txt             # Build configuration
│
├── matlab/
│   ├── tests/
│   │   ├── rtlsdr_spectrum_test.m # SDR spectrum capture verification
│   │   ├── env_sanity_check.m     # Environment validation
│   │   └── v2_orientation_placement_test.m
│   ├── capture/
│   │   ├── v3_capture_iq.m        # FM demodulation capture
│   │   └── v4_capture_iq_gain_sweep.m
│   ├── analysis/
│   │   ├── v3_fm_demod_mono.m     # Mono FM demodulation
│   │   ├── v4_batch_analyze_v4runs.m
│   │   ├── analyze_pass.m         # Post-pass SNR, spectral metrics
│   │   └── visualize_orbit.m      # Ground track, elevation profile
│   └── utilities/
│       └── v4_compute_metrics.m   # PSD-based metrics computation
│
├── data/
│   ├── tle/                       # Cached TLE files (updated daily)
│   ├── captures/                  # Raw I/Q recordings (.bin + .json)
│   ├── decoded/                   # APT images (.png, .jpg)
│   ├── logs/                      # System logs, error reports
│   ├── ml/                        # ML-specific data
│   │   ├── training/              # Training datasets
│   │   ├── models/                # Saved model files (.pkl, .h5)
│   │   └── predictions/           # Prediction logs
│   └── weather/                   # Weather forecast cache
│
├── docs/
│   ├── requirements/              # Functional, performance, interface
│   ├── architecture/              # L0, L1, L2, interface control
│   ├── verification/              # V0-V6 results, test reports
│   ├── ml/                        # ML system documentation
│   │   ├── ml_architecture.md     # ML subsystem design
│   │   ├── feature_spec.md        # Feature definitions
│   │   └── model_cards.md         # Model documentation
│   └── project_management/        # Timeline, risks, decisions
│
└── tests/
    ├── test_sgp4.py               # Unit tests for orbital propagation
    ├── test_doppler.py            # Doppler calculation validation
    ├── test_apt_decode.py         # APT decoder smoke tests
    ├── test_pass_scorer.py        # Pass scoring validation
    └── test_ml_predictor.py       # ML prediction tests
```

---

## Data Flow Architecture

### 1. Orbital Prediction Flow
```
Celestrak (HTTPS) → tle_fetch.py → data/tle/NOAA.txt
                 ↓
           predict_passes.py (SGP4) → Pass schedule JSON
                 ↓
           doppler_calc.py → Doppler profile (frequency vs time)
```

### 2. AI Mission Planning Flow
```
Pass schedule JSON + Weather forecast + Historical data
                 ↓
           feature_engineering.py → Feature vectors per pass
                 ↓
           pass_scorer.py (rule-based) OR ml_predictor.py (ML-based)
                 ↓
           scheduler_optimizer.py → Optimized schedule JSON
                 ↓
           schedule_captures.py → Execute captures
```

### 3. Automated Capture Flow
```
schedule_captures.py (reads optimized schedule)
        ↓
    [At AOS] Launch rtlsdr_capture (C++)
        ↓
    rtlsdr_capture.cpp (streams I/Q from SDR)
        ├→ Writes raw I/Q to data/captures/NOAA18_YYYYMMDD_HHMMSS.bin
        ├→ Reads Doppler corrections from doppler_tracker.cpp
        └→ Reports real-time metrics to adaptive_controller.py
        ↓
    adaptive_controller.py (monitors, recommends adjustments)
        ↓
    [At LOS] Terminate capture
        ↓
    decode_apt.py (processes raw I/Q)
        ├→ FM demodulation
        ├→ APT sync detection
        └→ Image reconstruction
        ↓
    Output: data/decoded/NOAA18_YYYYMMDD_HHMMSS.png
        ↓
    Metrics → data_store.py → Training dataset update
```

### 4. ML Learning Flow
```
Mission outcomes (success/fail, metrics)
        ↓
    data_store.py → Append to historical dataset
        ↓
    model_trainer.py (periodic retraining)
        ├→ Load training data
        ├→ Feature engineering
        ├→ Train model (RandomForest, XGBoost, or NN)
        ├→ Validate (cross-validation, holdout)
        └→ Save model to data/ml/models/
        ↓
    ml_predictor.py loads updated model for future predictions
```

### 5. Real-Time Doppler Compensation (V4+)
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
- **Pandas:** Data manipulation, feature engineering
- **Matplotlib:** Visualization (orbits, spectra, images)
- **Requests:** TLE download, weather API calls
- **scikit-learn:** ML models (RandomForest, GradientBoosting)
- **XGBoost:** High-performance gradient boosting (optional)
- **Joblib:** Model serialization

### C++ Stack
- **librtlsdr:** SDR hardware interface
- **Boost (optional):** File I/O, threading, time handling
- **Standard Library:** Vectors, file streams, chrono

### MATLAB Stack
- **Signal Processing Toolbox:** PSD analysis, filtering
- **Communications Toolbox:** RTL-SDR interface, FM demod
- **Deep Learning Toolbox:** Neural network prototyping (optional)
- **Satellite Communications Toolbox:** Link budget, orbital viz

### ML/AI Stack
- **scikit-learn:** Primary ML framework
  - RandomForestClassifier (success prediction)
  - RandomForestRegressor (SNR prediction)
  - StandardScaler, OneHotEncoder (preprocessing)
- **XGBoost:** Alternative gradient boosting
- **Optuna:** Hyperparameter optimization (optional)
- **MLflow:** Experiment tracking (optional, for production)

---

## ML Implementation Phases

### Phase 1: Rule-Based Optimizer (V5 Extension)
Simple deterministic scoring:
```python
def score_pass(elevation, weather_clear_prob, time_since_last):
    score = elevation * 0.5
    score += weather_clear_prob * 0.3
    score += min(time_since_last / 12, 1.0) * 0.2
    return score
```
- No training required
- Immediate deployment
- Baseline for comparison

### Phase 2: ML-Based Predictor (V6)
Supervised learning on historical data:
```python
from sklearn.ensemble import RandomForestClassifier

features = ['elevation', 'weather_clear', 'time_of_day', 'gain_db', 'antenna_config']
X = historical_passes[features]
y = historical_passes['decode_success']

model = RandomForestClassifier(n_estimators=100, max_depth=10)
model.fit(X, y)

future_passes['success_prob'] = model.predict_proba(future_passes[features])[:, 1]
```
- Requires 20-30 historical missions minimum
- Cross-validation for model selection
- Feature importance analysis

### Phase 3: Reinforcement Learning (Future)
Agent learns optimal capture strategy:
```python
# State: satellite position, weather, hardware status
# Action: capture now, wait, adjust gain
# Reward: +1 success, -0.1 failure, -0.01 missed opportunity
```
- Research-level complexity
- Requires extensive data
- Potential senior thesis extension

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

### Phase 3: ML Integration (Week 7+)
- Implement rule-based optimizer (immediate)
- Collect training data from V5 multi-pass campaign
- Train initial ML model when data sufficient
- Validate improvement over rule-based baseline

### Phase 4: Polish & Documentation (Ongoing)
- Performance tuning
- Error handling and robustness
- Documentation and test coverage
- Startup pitch preparation

---

## Build & Deployment

### Python Environment
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install skyfield numpy scipy pandas matplotlib requests
pip install scikit-learn xgboost joblib
```

### C++ Build
```bash
# Install librtlsdr (macOS)
brew install librtlsdr

# Build C++ programs
cd cpp/
mkdir build && cd build
cmake ..
make
```

### MATLAB Setup
- Ensure Communications Toolbox installed
- Ensure Signal Processing Toolbox installed
- Ensure Satellite Communications Toolbox installed
- Add `matlab/` subdirectories to MATLAB path

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
  "ml": {
    "model_type": "random_forest",
    "retrain_interval_hours": 24,
    "min_training_samples": 20,
    "prediction_threshold": 0.5
  },
  "paths": {
    "tle_cache": "data/tle/",
    "captures": "data/captures/",
    "decoded": "data/decoded/",
    "logs": "data/logs/",
    "ml_models": "data/ml/models/",
    "ml_training": "data/ml/training/"
  }
}
```

---

## Feature Specification (ML)

### Pass Features
| Feature | Type | Description | Source |
|---------|------|-------------|--------|
| max_elevation_deg | float | Maximum elevation during pass | Orbital prediction |
| duration_min | float | Pass duration (AOS to LOS) | Orbital prediction |
| time_of_day | category | Morning/Afternoon/Evening/Night | AOS timestamp |
| day_of_week | category | Mon-Sun | AOS timestamp |
| satellite_id | category | NOAA-15/18/19 | TLE data |

### Weather Features
| Feature | Type | Description | Source |
|---------|------|-------------|--------|
| cloud_cover_pct | float | Cloud coverage percentage | Weather API |
| precip_prob | float | Precipitation probability | Weather API |
| temperature_c | float | Surface temperature | Weather API |
| humidity_pct | float | Relative humidity | Weather API |

### Hardware Features
| Feature | Type | Description | Source |
|---------|------|-------------|--------|
| antenna_config | category | CUSTOM/STOCK | Manual input |
| gain_db | float | SDR tuner gain setting | Config |
| lna_active | bool | LNA in signal path | Hardware status |

### Historical Features
| Feature | Type | Description | Source |
|---------|------|-------------|--------|
| recent_success_rate | float | Success rate over last 10 passes | Historical data |
| same_satellite_success | float | Success rate for this satellite | Historical data |
| similar_elevation_success | float | Success rate at similar elevations | Historical data |

### Target Variables
| Variable | Type | Description |
|----------|------|-------------|
| decode_success | binary | 1 if decode succeeded, 0 otherwise |
| snr_db | float | Measured signal-to-noise ratio |
| sync_rate | float | Sync pulse detection rate |

---

## Testing Strategy

### Unit Tests
- `tests/test_sgp4.py`: Validate pass predictions against known data
- `tests/test_doppler.py`: Check Doppler calculation accuracy
- `tests/test_apt_decode.py`: Decode known-good I/Q file
- `tests/test_pass_scorer.py`: Verify scoring logic
- `tests/test_ml_predictor.py`: Test model inference

### Integration Tests
- End-to-end test: Predict → Schedule → Capture (simulated) → Decode → Learn
- Verify ML pipeline from feature extraction to prediction
- Test model retraining workflow

### ML-Specific Tests
- Model validation: cross-validation accuracy, precision/recall
- Feature importance: verify expected features rank highly
- Prediction calibration: predicted probabilities match actual rates
- Regression tests: new model performs at least as well as previous

### System Tests
- Capture actual satellite pass
- Validate decoded image quality
- Verify ML predictions improve over time
- Measure timing accuracy (AOS/LOS within ±30s)

---

## Performance Targets

### Python Performance
- Pass prediction: <1 second for 7-day forecast
- Doppler calculation: <100 ms per time step
- APT decode: <10 seconds for 10-minute pass
- ML prediction: <100 ms per pass
- Schedule optimization: <5 seconds for 7-day schedule

### C++ Performance (V4+)
- I/Q capture: Real-time at 250 kHz (no sample drops)
- Doppler tracking: <10 ms latency for frequency updates
- CPU usage: <50% on typical laptop during capture

### ML Performance
- Model accuracy: >80% correct success/failure prediction
- SNR prediction: RMSE <3 dB
- False positive rate: <20% (don't skip good passes)
- False negative rate: <10% (don't attempt hopeless passes)

### Storage Requirements
- Raw I/Q per pass: ~300 MB (10 minutes @ 250 kHz, float32)
- Decoded image: ~2 MB (PNG, lossless compression)
- TLE cache: <1 MB
- ML models: <10 MB each
- Training data: ~1 MB per 100 passes
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
- MATLAB R2025b (for analysis)

**Cross-Platform Notes:**
- Python code is platform-agnostic
- C++ uses standard library + librtlsdr (available on all platforms)
- MATLAB analysis scripts portable across macOS/Windows/Linux
- ML models saved with joblib are cross-platform compatible
