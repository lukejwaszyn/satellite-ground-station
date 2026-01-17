# L0: System Context Diagram

## External Entities

### 1. NOAA Satellites
- **NOAA-15:** 137.62 MHz
- **NOAA-18:** 137.9125 MHz
- **NOAA-19:** 137.1 MHz
- **Orbit:** Sun-synchronous polar orbit, ~800-850 km altitude
- **Coverage:** Passes over State College, PA 2-4 times daily
- **Signal:** APT (Automatic Picture Transmission) format

### 2. Celestrak TLE Database
- **Provides:** Two-Line Element sets for orbital propagation
- **Update frequency:** Daily
- **Access method:** HTTPS GET request
- **URL:** https://celestrak.org/NOAA.txt

### 3. User
- **Receives:** Decoded APT images (PNG/JPEG)
- **Monitors:** System status, logs, pass schedules
- **Configures:** System parameters, location, frequency settings

## System Boundary

**Autonomous Satellite Ground Station**

**Inputs:**
- RF signals (137 MHz VHF band)
- TLE data (HTTPS from Celestrak)
- User configuration (location, operational parameters)

**Outputs:**
- Decoded APT weather satellite images (PNG/JPEG)
- System logs (JSON format)
- Pass prediction schedules
- Performance metrics (SNR, frequency error, image quality)

**Interfaces:**
- USB 2.0 (RTL-SDR connection)
- SMA coaxial (antenna/LNA/SDR RF chain)
- Network (TLE data retrieval)
- File system (I/Q storage, image output)

## Data Flows

**Input Flows:**
1. EM waves (137 MHz) → Antenna
2. TLE data (HTTPS) → Orbital Predictor
3. User commands → Automation Controller

**Output Flows:**
1. Decoded Images → User
2. Logs & Metadata → User
3. Pass Predictions → User
4. System Status → User

## Context Diagram Notes

The system operates as a closed-loop autonomous receiver:
1. Fetches current orbital data
2. Predicts upcoming passes
3. Automatically captures RF signals during passes
4. Processes and decodes satellite imagery
5. Archives results and generates reports

External dependencies are minimal (TLE updates, user configuration). System is designed for unattended operation once configured.
