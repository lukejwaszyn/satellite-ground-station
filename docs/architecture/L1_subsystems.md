# L1: Subsystem Architecture

## 1. Orbital Prediction Subsystem

**Purpose:** Calculate satellite passes and Doppler shifts

**Technology:** Python + Skyfield (SGP4 propagator)

**Inputs:**
- TLE data from Celestrak
- Observer location (State College, PA: 40.7934°N, 77.8600°W)

**Outputs:**
- Pass schedule (AOS/LOS/max elevation)
- Doppler frequency profile

**Key Functions:**
- Load and parse TLE files
- Propagate satellite position using SGP4 algorithm
- Calculate topocentric position (azimuth, elevation, range)
- Detect passes above horizon threshold (10° minimum elevation)
- Compute instantaneous Doppler shift throughout pass

**Performance:**
- Prediction accuracy: ±30 seconds
- Doppler calculation: <100 ms latency
- Update frequency: On-demand or scheduled (daily TLE refresh)

---

## 2. RF Front-End Subsystem

**Purpose:** Receive, amplify, and condition 137 MHz signals

**Components:**
- Custom VHF dipole antenna (λ/2 @ 137 MHz ≈ 1.09m)
- Low-noise amplifier (15-20 dB gain, <1.5 dB noise figure)
- Coaxial transmission lines (50Ω impedance)
- SMA connectors for interface continuity

**Inputs:** 
- Electromagnetic waves from satellite (137 MHz, RHCP/vertical polarization)

**Outputs:** 
- Amplified RF signal to SDR input

**Key Functions:**
- Capture vertically-polarized 137 MHz signals
- Amplify weak signals above SDR noise floor
- Filter out-of-band interference
- Maintain impedance matching (50Ω throughout RF chain)

**Performance:**
- Antenna VSWR: <2:1 at 137 MHz
- LNA gain: 15-20 dB
- LNA noise figure: <1.5 dB
- System noise figure: <3 dB

---

## 3. Digital Capture Subsystem

**Purpose:** Convert RF signals to digital I/Q samples

**Technology:** RTL-SDR v4 + librtlsdr driver

**Inputs:**
- RF signal (137 MHz ± Doppler offset)
- Doppler frequency correction commands
- Gain adjustment commands (from AI subsystem)

**Outputs:**
- Raw I/Q samples (complex float32)
- Sample rate: 250 kHz (after decimation)
- Real-time signal quality metrics (for AI feedback)

**Key Functions:**
- Tune to 137 MHz ± Doppler offset
- Sample at 2.4 MHz, decimate to 250 kHz
- Stream I/Q data to disk or real-time processing pipeline
- Update center frequency dynamically during pass (every 1-5 seconds)
- Report signal strength and quality metrics to AI subsystem

**Performance:**
- Sample rate: 2.4 MHz native, 250 kHz output
- Frequency accuracy: <1 kHz
- Dynamic range: 8-bit (RTL-SDR native)
- Latency: <50 ms for frequency updates

---

## 4. DSP & Decoding Subsystem

**Purpose:** Demodulate FM and decode APT image format

**Technology:** 
- Python (offline processing, development)
- C++ (real-time target for V4+)
- MATLAB (analysis and prototyping)

**Inputs:**
- Raw I/Q samples (complex float32, 250 kHz)

**Outputs:**
- Decoded APT image (PNG/JPEG, 8-bit grayscale)
- Metadata (timestamp, satellite ID, max elevation, SNR)
- Quality metrics (sync detection rate, estimated SNR, frequency error)

**Key Functions:**
- FM quadrature demodulation
- Lowpass filter to 11 kHz (APT bandwidth)
- Hilbert transform for APT demodulation
- Sync pulse detection and line synchronization
- Image reconstruction (2 lines/second, 2080 pixels/line)
- De-emphasis and normalization
- Compute quality metrics for AI feedback loop

**Performance:**
- Processing latency: <10 seconds (offline), <1 second target (real-time)
- Sync detection accuracy: >95%
- Image quality: Sufficient for weather pattern identification

---

## 5. Automation & Control Subsystem

**Purpose:** Schedule captures and orchestrate workflow

**Technology:** Python orchestration scripts

**Inputs:**
- Pass predictions from Orbital Prediction Subsystem
- Optimized schedule from AI Mission Planning Subsystem
- System status (SDR availability, disk space, etc.)

**Outputs:**
- Capture commands (launch C++ capture at AOS)
- Termination signals (stop capture at LOS)
- Logs and metadata (JSON format)

**Key Functions:**
- Trigger C++ capture program at AOS
- Monitor pass in progress
- Send Doppler correction updates to capture program
- Forward AI-recommended gain adjustments during capture
- Terminate capture at LOS
- Archive raw I/Q and decoded images
- Generate metadata (timestamp, max elevation, SNR estimates)
- Monitor system health and disk space
- Report mission outcomes to AI subsystem

**Performance:**
- Scheduling accuracy: ±10 seconds
- Uptime: >95% unattended operation
- Error handling: Automatic recovery from transient failures

---

## 6. AI Mission Planning Subsystem

**Purpose:** Optimize mission planning, predict outcomes, and learn from results

**Technology:**
- Python (scikit-learn, pandas, numpy)
- Optional: TensorFlow/PyTorch for deep learning extensions

**Inputs:**
- Pass predictions (from Orbital Prediction Subsystem)
- Weather forecasts (external API or manual input)
- Historical mission data (outcomes, metrics, conditions)
- Real-time signal quality (from Digital Capture Subsystem)
- Decoded image quality metrics (from DSP Subsystem)

**Outputs:**
- Optimized capture schedule (7-day rolling window)
- Per-pass success probability predictions
- Recommended gain settings per pass
- Real-time adaptive recommendations (gain adjustments, anomaly alerts)
- Performance analytics and trend reports

**Key Functions:**

### Planning Phase
- Score passes using multi-factor model (elevation, weather, time, history)
- Generate optimal schedule balancing coverage vs. success probability
- Handle resource constraints (power budget, storage, operator availability)
- Re-plan when conditions change (weather updates, hardware issues)

### Prediction Phase
- Train supervised ML models on historical data
- Features: elevation, weather conditions, time of day, antenna config, gain setting
- Target: decode success (binary) or SNR (continuous)
- Validate models using cross-validation and holdout testing

### Execution Phase
- Monitor real-time metrics during capture
- Compare observed signal quality to predictions
- Generate adaptive recommendations (increase gain, flag anomaly)
- Log all decisions and observations

### Learning Phase
- Ingest mission outcomes after each capture
- Update feature store with new data points
- Retrain models periodically (batch) or continuously (online learning)
- Identify failure patterns and generate operational recommendations

### Analytics Phase
- Generate dashboards and reports
- Track success rate trends over time
- Compare predicted vs. actual outcomes
- Identify systematic issues (e.g., certain antenna orientations underperform)

**Performance:**
- Schedule generation: <5 seconds for 7-day window
- Prediction latency: <100 ms per pass
- Model accuracy: >80% correct success/failure prediction (target)
- Learning update: Daily batch retraining or per-mission online update

**Data Requirements:**
- Minimum 20-30 historical missions for initial model training
- Weather data: temperature, cloud cover, precipitation probability
- Hardware state: antenna orientation, LNA status, SDR health

---

## Subsystem Interfaces

**Orbital Prediction → Automation:**
- Pass schedule JSON file
- Doppler frequency profile

**Orbital Prediction → AI Mission Planning:**
- Raw pass data (AOS, LOS, elevation, azimuth)
- Doppler profile for each pass

**AI Mission Planning → Automation:**
- Optimized capture schedule (which passes to capture)
- Recommended settings per pass (gain, duration margins)
- Priority rankings

**Automation → Digital Capture:**
- Start/stop commands
- Real-time Doppler correction updates
- Gain adjustment commands (from AI recommendations)

**Digital Capture → AI Mission Planning:**
- Real-time signal quality metrics (SNR estimate, frequency error)
- Hardware status

**Digital Capture → DSP/Decoding:**
- Raw I/Q binary files
- Metadata JSON (sample rate, frequency, duration)

**DSP/Decoding → AI Mission Planning:**
- Decode success/failure
- Quality metrics (sync rate, estimated SNR, image quality score)
- Detected anomalies

**DSP/Decoding → User:**
- Decoded APT images
- Performance metrics

**AI Mission Planning → User:**
- Optimized schedule
- Predictions and confidence scores
- Analytics dashboards
- Recommendations

**All Subsystems → User:**
- Logs (system events, errors, warnings)
- Status updates (current pass, next pass, system health)
