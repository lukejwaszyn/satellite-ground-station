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

**Outputs:**
- Raw I/Q samples (complex float32)
- Sample rate: 250 kHz (after decimation)

**Key Functions:**
- Tune to 137 MHz ± Doppler offset
- Sample at 2.4 MHz, decimate to 250 kHz
- Stream I/Q data to disk or real-time processing pipeline
- Update center frequency dynamically during pass (every 1-5 seconds)

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

**Inputs:**
- Raw I/Q samples (complex float32, 250 kHz)

**Outputs:**
- Decoded APT image (PNG/JPEG, 8-bit grayscale)
- Metadata (timestamp, satellite ID, max elevation, SNR)

**Key Functions:**
- FM quadrature demodulation
- Lowpass filter to 11 kHz (APT bandwidth)
- Hilbert transform for APT demodulation
- Sync pulse detection and line synchronization
- Image reconstruction (2 lines/second, 2080 pixels/line)
- De-emphasis and normalization

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
- System status (SDR availability, disk space, etc.)

**Outputs:**
- Capture commands (launch C++ capture at AOS)
- Termination signals (stop capture at LOS)
- Logs and metadata (JSON format)

**Key Functions:**
- Trigger C++ capture program at AOS
- Monitor pass in progress
- Send Doppler correction updates to capture program
- Terminate capture at LOS
- Archive raw I/Q and decoded images
- Generate metadata (timestamp, max elevation, SNR estimates)
- Monitor system health and disk space

**Performance:**
- Scheduling accuracy: ±10 seconds
- Uptime: >95% unattended operation
- Error handling: Automatic recovery from transient failures

---

## Subsystem Interfaces

**Orbital Prediction → Automation:**
- Pass schedule JSON file
- Doppler frequency profile

**Automation → Digital Capture:**
- Start/stop commands
- Real-time Doppler correction updates

**Digital Capture → DSP/Decoding:**
- Raw I/Q binary files
- Metadata JSON (sample rate, frequency, duration)

**DSP/Decoding → User:**
- Decoded APT images
- Performance metrics

**All Subsystems → User:**
- Logs (system events, errors, warnings)
- Status updates (current pass, next pass, system health)
