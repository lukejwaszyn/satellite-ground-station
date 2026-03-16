# L0: System Context

## External Entities

### 1. NOAA APT Satellites (Capturable — Analog FM)
- **NOAA 19:** 137.1 MHz — Primary imaging target (most reliable APT)
- **NOAA 18:** 137.9125 MHz
- **NOAA 15:** 137.62 MHz
- **Orbit:** Sun-synchronous polar, ~800-850 km altitude
- **Coverage:** 2-4 passes daily per satellite over State College, PA
- **Signal:** APT (Automatic Picture Transmission) — analog FM, 2400 Hz AM subcarrier

### 2. METEOR LRPT Satellites (Capturable — Digital QPSK)
- **METEOR-M2 3:** 137.9 MHz
- **METEOR-M2 4:** 137.1 MHz
- **Orbit:** Sun-synchronous polar, ~830 km altitude
- **Signal:** LRPT (Low Rate Picture Transmission) — OQPSK, 72 kSym/s, rate 1/2 FEC + RS(255,223)

### 3. Display-Only Satellites (Tracked, Not Capturable)
- **NOAA 20 (JPSS-1):** HRD at 7.8 GHz only — no 137 MHz APT
- **NOAA 21 (JPSS-2):** HRD at 7.8 GHz only — no 137 MHz APT
- **ISS (Zarya):** NORAD 25544
- **TERRA:** NORAD 25994
- **AQUA:** NORAD 27424
- **LANDSAT 9:** NORAD 49260

### 4. Celestrak TLE Database
- **Provides:** Two-Line Element sets for orbital propagation
- **Groups fetched:** weather, stations, resource + individual NORAD ID queries
- **Update frequency:** Daily (24-hour cache)

### 5. User / Operator
- **Monitors:** 3D mission operations HMI (satellite tracking, pass timeline, Doppler/elevation charts)
- **Controls:** Capture triggers, system configuration
- **Receives:** Decoded satellite imagery (APT grayscale, LRPT multi-channel color), quality reports

## System Boundary

**Autonomous Satellite Ground Station**

**Inputs:**
- RF signals (137 MHz VHF band) from NOAA and METEOR satellites
- TLE data (HTTPS from Celestrak)
- User configuration and interaction

**Outputs:**
- Decoded weather satellite images (APT: grayscale PNG; LRPT: multi-channel PNG + RGB composite)
- Automated quality grades (GOOD / MARGINAL / NOISE) per decoded image
- SatDump comparison reports for decoder validation
- Pass prediction schedules with signal type routing (APT vs LRPT)
- 3D mission operations visualization with signal type badges
- Mission logs, system status, performance metrics

**Key Interfaces:**
- USB (RTL-SDR via Apple USB-A→C adapter)
- SMA coaxial (antenna → LNA → SDR RF chain)
- HTTPS (TLE retrieval from Celestrak)
- HTTP/REST (mission server API + HMI frontend)
- File system (I/Q captures, decoded images, orbital data JSON)

## Data Flow

```
NOAA/METEOR satellites (137 MHz)
         │ RF
         ▼
Antenna → SAWbird LNA → RTL-SDR v4 → USB → MacBook
         │ Raw I/Q (.bin)
         ▼
    Decoder Router (satcom_server.py)
    ├── NOAA  → decode_apt.py  → grayscale PNG
    └── METEOR → decode_lrpt.py → multi-channel PNG + composite
         │
         ▼
    quality_estimator.py → GOOD / MARGINAL / NOISE grade
         │
         ▼
    Mission log + HMI display
```

The system operates as a closed-loop autonomous receiver: fetch TLEs → predict passes → present on 3D HMI → capture at AOS → decode with satellite-appropriate decoder → grade quality → log results → learn from outcomes.
