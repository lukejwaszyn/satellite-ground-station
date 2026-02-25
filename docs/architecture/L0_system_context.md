# L0: System Context Diagram

## External Entities

### 1. NOAA Satellites (Primary Imaging Target)
- **NOAA-20 (JPSS-1):** 137.1 MHz (primary imaging target)
- **NOAA-21 (JPSS-2):** 137.1 MHz
- **NOAA-15:** 137.62 MHz
- **NOAA-18:** 137.9125 MHz
- **NOAA-19:** 137.1 MHz
- **Orbit:** Sun-synchronous polar orbit, ~800-850 km altitude
- **Coverage:** Passes over State College, PA 2-4 times daily per satellite
- **Signal:** APT (Automatic Picture Transmission) format

### 2. Additional Tracked Satellites (Display/Monitoring)
- **METEOR-M2 3:** 137.9 MHz (Russian weather satellite)
- **METEOR-M2 4:** 137.1 MHz (Russian weather satellite)
- **ISS (Zarya):** NORAD 25544 (display only, no imaging)
- **TERRA:** NORAD 25994 (Earth observation, display only)
- **AQUA:** NORAD 27424 (Earth observation, display only)
- **LANDSAT 9:** NORAD 49260 (Earth observation, display only)

### 3. Celestrak TLE Database
- **Provides:** Two-Line Element sets for orbital propagation
- **Update frequency:** Daily
- **Access method:** HTTPS GET request
- **Sources:**
  - Weather group: `https://celestrak.org/NORAD/elements/gp.php?GROUP=weather&FORMAT=tle`
  - Stations group: `https://celestrak.org/NORAD/elements/gp.php?GROUP=stations&FORMAT=tle`
  - Resource group: `https://celestrak.org/NORAD/elements/gp.php?GROUP=resource&FORMAT=tle`
  - Individual lookup: `https://celestrak.org/NORAD/elements/gp.php?CATNR={NORAD_ID}&FORMAT=tle`

### 4. User / Operator
- **Receives:** Decoded APT images (PNG/JPEG)
- **Monitors:** System status, logs, pass schedules via Mission Operations HMI
- **Interacts with:** 3D mission operations interface (satellite tracking, pass visualization, Doppler charts)
- **Configures:** System parameters, location, frequency settings

## System Boundary

**Autonomous Satellite Ground Station with Mission Operations Interface**

**Inputs:**
- RF signals (137 MHz VHF band)
- TLE data (HTTPS from Celestrak, multiple groups)
- User configuration (location, operational parameters)
- User interaction (HMI mouse/keyboard input)

**Outputs:**
- Decoded APT weather satellite images (PNG/JPEG)
- System logs (JSON format)
- Pass prediction schedules
- Performance metrics (SNR, frequency error, image quality)
- 3D mission operations visualization (real-time satellite tracking, pass timeline, Doppler/elevation charts)
- Orbital data export (orbital_data.json)

**Interfaces:**
- USB 2.0 (RTL-SDR connection)
- SMA coaxial (antenna/LNA/SDR RF chain)
- Network (TLE data retrieval from Celestrak)
- File system (I/Q storage, image output, orbital data JSON)
- HTTP (local web server for HMI frontend)
- WebGL (3D rendering via Three.js)

## Data Flows

**Input Flows:**
1. EM waves (137 MHz) → Antenna
2. TLE data (HTTPS, multiple groups) → Orbital Predictor / Orbital Data Generator
3. User commands → Automation Controller
4. User interaction (mouse/keyboard) → Mission Operations HMI

**Output Flows:**
1. Decoded Images → User
2. Logs & Metadata → User
3. Pass Predictions → User / Mission Operations HMI
4. System Status → User / Mission Operations HMI
5. 3D Satellite Visualization → User (via browser)
6. Doppler/Elevation Charts → User (via HMI)

## Context Diagram Notes

The system operates as a closed-loop autonomous receiver with integrated mission operations display:
1. Fetches current orbital data from multiple Celestrak TLE groups
2. Propagates satellite positions using SGP4 for 12 satellites across multiple constellations
3. Predicts upcoming passes and computes Doppler profiles
4. Presents real-time satellite tracking and pass data via 3D mission operations HMI
5. Automatically captures RF signals during passes
6. Processes and decodes satellite imagery
7. Archives results and generates reports

External dependencies are minimal (TLE updates, user configuration). System is designed for unattended operation once configured, with the HMI providing situational awareness and mission oversight.
