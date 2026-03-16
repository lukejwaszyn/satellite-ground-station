# Interface Control Document (ICD)

## ICD-1: Python Predictor → C++ Capture
**Interface Type:** File-based (JSON)
**File:** `data/schedules/next_pass.json`

Contains satellite name, AOS/LOS times, frequency, max elevation, and Doppler profile array. C++ capture reads on launch. Updated before each pass.

## ICD-2: C++ Capture → Decoder Pipeline
**Interface Type:** File-based (binary I/Q + JSON metadata)

**I/Q File:** `data/captures/<SAT>_YYYYMMDD_HHMMSS.bin`
- Format: Interleaved uint8 I/Q (RTL-SDR native, values 0-255 centered at 127)
- Sample rate: 2.4 MHz
- No header: raw binary

**Metadata:** `data/captures/<SAT>_YYYYMMDD_HHMMSS_meta.json`
- Fields: satellite, frequency_hz, sample_rate_hz, start_utc, end_utc, duration_sec, gain_db, max_elevation_deg, doppler_corrected

## ICD-3: Celestrak TLE API
**Interface Type:** HTTPS GET

Multiple endpoints:
- Weather group: `celestrak.org/NORAD/elements/gp.php?GROUP=weather&FORMAT=tle`
- Stations group: `...?GROUP=stations&FORMAT=tle`
- Resource group: `...?GROUP=resource&FORMAT=tle`
- Individual: `...?CATNR={NORAD_ID}&FORMAT=tle`

Local cache: `data/tle/tle_<group>.txt`, 24-hour staleness threshold. Falls back to cached TLE on fetch failure.

## ICD-4: Decoder → Output Images

### APT Output (NOAA)
- **Image:** `data/decoded/<SAT>_YYYYMMDD_HHMMSS_decoded.png` — 8-bit grayscale, 2080px wide
- **Metadata:** `<base>_metadata.json` — sync_pulses_found, image_shape, duration_sec, sample_rate

### LRPT Output (METEOR)
- **Per-channel:** `<base>_ch0.png` through `<base>_ch5.png` — 8-bit grayscale, 1568px wide
- **Composite:** `<base>_composite.png` — RGB composite from best available channels
- **Primary:** `<base>_decoded.png` — composite preferred, else best single channel
- **Metadata:** `<base>_metadata.json` — frames_found, frames_rs_clean, channels decoded, total_packets

## ICD-5: Automation Controller → All Subsystems
**Interface Type:** Command-line + subprocess

C++ capture launched via subprocess with --schedule, --output, --gain, --sample-rate args. Python decoder called programmatically. Process control via SIGTERM/SIGKILL. Exit codes: 0=success, 1=error, 2=partial.

## ICD-6: Decoder Router (satcom_server.py)
**Interface Type:** Programmatic (Python import)

The server inspects the satellite name from pass_info:
- If name contains "METEOR" → `from python.demod.decode_lrpt import decode_lrpt`
- Otherwise → `from python.demod.decode_apt import decode_apt`

Mission log entries include: `decode_type` ("APT" or "LRPT"), `channels_decoded` (LRPT only).

Pass API response includes: `signal_type` ("APT", "LRPT", or null for display satellites).

## ICD-7: Quality Estimator → Mission Log
**Interface Type:** File-based (JSON) + programmatic

**Input:** Decoded image path + optional metadata JSON
**Output:** `<base>_quality.json` containing:
- metrics: snr_db, entropy_bits, edge_density, interference_score, sync_quality
- grade: "GOOD" / "MARGINAL" / "NOISE"
- confidence: 0.0-1.0
- reasons: array of human-readable scoring explanations

Can be called from CLI (`python quality_estimator.py image.png`) or imported by the server to auto-tag mission log entries.

## ICD-8: SatDump Comparison Tool
**Interface Type:** CLI + subprocess

**Input:** Raw .bin capture file + satellite name
**Output directory:** `data/comparisons/<capture_name>/`
- `custom/` — custom decoder output
- `satdump/` — SatDump CLI output
- `comparison_report.json` — side-by-side metrics
- `side_by_side.png` — visual comparison composite

Detects satellite type from filename, runs both decoders, estimates SNR for each, produces verdict (COMPARABLE / CUSTOM BETTER / SATDUMP BETTER / BOTH FAILED).

## ICD-9: Orbital Data Backend → HMI Frontend
**Interface Type:** JSON via HTTP

**Endpoint:** `/api/orbital-data` (cached 10 minutes) or static `orbital_data.json`
**Contents:** Per-satellite: ECEF positions (30s intervals), passes (AOS/TCA/LOS + Doppler profiles), metadata (NORAD ID, frequency, color, role, signal_type)
**Ground station:** name, lat, lon, elevation_m, min_elevation_deg
**Generation:** `hmi/generate_orbital_data.py` via Skyfield SGP4

Frontend interpolates between position samples for smooth animation, renders pass timeline for next visible pass, and uses signal_type to display APT/LRPT/TRACK badges.
