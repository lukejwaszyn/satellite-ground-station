# Interface Control Document (ICD)

## ICD-1: Python Predictor → C++ Capture

**Interface Type:** File-based (JSON)

**Data Format:** JSON file containing pass schedule and Doppler profile

**File Location:** `data/schedules/next_pass.json`

**Update Frequency:** Generated before each pass (typically 15-30 minutes before AOS)

**Schema:**
```json
{
  "satellite": "NOAA-18",
  "aos_utc": "2026-01-18T14:32:15Z",
  "los_utc": "2026-01-18T14:47:03Z",
  "max_elevation_deg": 45.2,
  "max_elevation_time_utc": "2026-01-18T14:39:40Z",
  "frequency_hz": 137912500,
  "doppler_profile": [
    {"time_utc": "2026-01-18T14:32:15Z", "offset_hz": 3200},
    {"time_utc": "2026-01-18T14:33:15Z", "offset_hz": 3050},
    {"time_utc": "2026-01-18T14:34:15Z", "offset_hz": 2880},
    ...
    {"time_utc": "2026-01-18T14:47:03Z", "offset_hz": -3100}
  ]
}
```

**Field Definitions:**
- `satellite`: Satellite identifier (NOAA-15, NOAA-18, NOAA-19)
- `aos_utc`: Acquisition of Signal time (ISO 8601 UTC)
- `los_utc`: Loss of Signal time (ISO 8601 UTC)
- `max_elevation_deg`: Maximum elevation angle during pass (degrees above horizon)
- `max_elevation_time_utc`: Time of maximum elevation
- `frequency_hz`: Nominal transmission frequency (Hz)
- `doppler_profile`: Array of time-stamped Doppler offset values
  - `time_utc`: Timestamp for this Doppler value
  - `offset_hz`: Doppler shift in Hz (positive = satellite approaching, negative = receding)

**Error Handling:**
- Missing file: C++ capture aborts with error message
- Invalid JSON: C++ capture logs error and skips pass
- Missing required fields: Use defaults (offset_hz = 0 if Doppler profile absent)

**Validation:**
- Python predictor validates all fields before writing file
- C++ capture validates JSON structure on load
- Time values must be valid ISO 8601 format
- Frequencies must be within 137-138 MHz range

---

## ICD-2: C++ Capture → Python Decoder

**Interface Type:** File-based (binary I/Q + JSON metadata)

**I/Q Binary File:** `data/captures/NOAA18_YYYYMMDD_HHMMSS_IQ.bin`

**Format:**
- Interleaved complex float32 samples: [I0, Q0, I1, Q1, I2, Q2, ...]
- Sample rate: 250 kHz (decimated from 2.4 MHz)
- Endianness: Little-endian (native on x86/ARM)
- No header: raw binary data only

**File Size Estimate:**
- 10-minute pass at 250 kHz: ~300 MB
- Formula: `duration_sec * sample_rate * 8 bytes/sample`

**Metadata JSON File:** `data/captures/NOAA18_YYYYMMDD_HHMMSS_meta.json`

**Schema:**
```json
{
  "satellite": "NOAA-18",
  "frequency_hz": 137912500,
  "sample_rate_hz": 250000,
  "start_utc": "2026-01-18T14:32:15Z",
  "end_utc": "2026-01-18T14:47:03Z",
  "duration_sec": 897,
  "num_samples": 224250000,
  "sdr_gain_db": 40,
  "max_elevation_deg": 45.2,
  "doppler_corrected": true,
  "capture_notes": "Clear sky, no interference observed"
}
```

**Field Definitions:**
- `satellite`: Satellite identifier
- `frequency_hz`: Center frequency used (may vary if Doppler corrected)
- `sample_rate_hz`: I/Q sample rate (always 250000 for this project)
- `start_utc`: Capture start timestamp
- `end_utc`: Capture end timestamp
- `duration_sec`: Total capture duration
- `num_samples`: Total complex samples in binary file
- `sdr_gain_db`: RTL-SDR gain setting used
- `max_elevation_deg`: Maximum elevation during this pass
- `doppler_corrected`: Boolean indicating if Doppler tracking was active
- `capture_notes`: Optional text field for observations

**Error Handling:**
- Missing metadata: Python decoder attempts decode with default parameters
- Mismatched num_samples: Decoder uses actual file size
- Corrupted I/Q file: Decoder logs error and skips

**Validation:**
- C++ writes metadata after successful capture completion
- Python decoder validates metadata before processing
- File size consistency check: `file_size_bytes == num_samples * 8`

---

## ICD-3: Celestrak TLE API

**Interface Type:** HTTPS GET

**Endpoint:** `https://celestrak.org/NOAA.txt`

**Method:** GET

**Request Headers:**
```
User-Agent: satellite-ground-station/1.0
Accept: text/plain
```

**Response Format:** TLE (Two-Line Element Set)

**Example Response:**
```
NOAA 18
1 28654U 05018A   26017.12345678  .00000012  00000-0  20000-3 0  9990
2 28654  98.7123 123.4567 0012345  45.6789 314.5678 14.12345678123456
NOAA 19
1 33591U 09005A   26017.23456789  .00000015  00000-0  25000-3 0  9991
2 33591  99.1234 234.5678 0014567  56.7890 303.4567 14.23456789234567
```

**Update Frequency:**
- Automatic: Daily at 00:00 UTC
- Manual: On-demand via `tle_fetch.py`

**Caching:**
- Local cache: `data/tle/NOAA.txt`
- Cache expiration: 24 hours
- Fallback: Use cached TLE if download fails

**Error Handling:**
- HTTP error: Log warning, use cached TLE
- Parse error: Log error, skip invalid TLE entries
- Network timeout: Retry once, then use cache

**Validation:**
- TLE checksum validation (modulo 10 check on line 1 and 2)
- Date sanity check (TLE epoch within ±7 days of current date)
- Satellite catalog number consistency

---

## ICD-4: Python Decoder → Output Images

**Interface Type:** File-based (PNG/JPEG + JSON metadata)

**Image File:** `data/decoded/NOAA18_YYYYMMDD_HHMMSS.png`

**Format:**
- PNG (lossless) or JPEG (lossy, higher compression)
- 8-bit grayscale
- Dimensions: 2080 pixels wide × variable height (depends on pass duration)
- Resolution: 2 lines/second, 2080 pixels/line (APT standard)

**Image Metadata (embedded PNG text):**
- `Satellite`: NOAA-18
- `Capture Date`: 2026-01-18T14:32:15Z
- `Max Elevation`: 45.2°
- `Decoder Version`: 1.0

**Companion JSON File:** `data/decoded/NOAA18_YYYYMMDD_HHMMSS_decode.json`

**Schema:**
```json
{
  "input_file": "data/captures/NOAA18_20260118_143215_IQ.bin",
  "output_file": "data/decoded/NOAA18_20260118_143215.png",
  "satellite": "NOAA-18",
  "capture_start_utc": "2026-01-18T14:32:15Z",
  "max_elevation_deg": 45.2,
  "image_width_px": 2080,
  "image_height_px": 1794,
  "sync_pulses_detected": 897,
  "sync_detection_rate": 0.98,
  "estimated_snr_db": 14.5,
  "decode_quality": "good",
  "decoder_version": "1.0",
  "decode_timestamp_utc": "2026-01-18T15:00:00Z"
}
```

**Field Definitions:**
- `sync_pulses_detected`: Number of valid sync pulses found
- `sync_detection_rate`: Fraction of expected sync pulses successfully detected
- `estimated_snr_db`: Estimated signal-to-noise ratio from APT signal
- `decode_quality`: Subjective quality assessment (poor/fair/good/excellent)

**Quality Thresholds:**
- **Excellent:** SNR > 20 dB, sync rate > 0.98
- **Good:** SNR 12-20 dB, sync rate 0.90-0.98
- **Fair:** SNR 8-12 dB, sync rate 0.80-0.90
- **Poor:** SNR < 8 dB or sync rate < 0.80

---

## ICD-5: Automation Controller → All Subsystems

**Interface Type:** Command-line arguments + IPC signals

**C++ Capture Launch:**
```bash
./rtlsdr_capture \
  --schedule data/schedules/next_pass.json \
  --output data/captures/NOAA18_20260118_143215 \
  --gain 40 \
  --sample-rate 250000
```

**Arguments:**
- `--schedule`: Path to pass schedule JSON (ICD-1)
- `--output`: Output file prefix (will append _IQ.bin and _meta.json)
- `--gain`: SDR gain in dB
- `--sample-rate`: Output sample rate in Hz

**Python Decoder Launch:**
```bash
python decode_apt.py \
  --input data/captures/NOAA18_20260118_143215_IQ.bin \
  --output data/decoded/NOAA18_20260118_143215.png \
  --format png
```

**Arguments:**
- `--input`: Path to raw I/Q file (ICD-2)
- `--output`: Path to output image file (ICD-4)
- `--format`: Output format (png or jpeg)

**Process Control:**
- Start: `subprocess.Popen()` from Python
- Monitor: Poll process status
- Terminate: Send SIGTERM (graceful) or SIGKILL (force)
- Exit codes: 0 = success, 1 = error, 2 = partial success

**Logging:**
- Stdout: Redirected to log files
- Stderr: Captured for error reporting

---

## Interface Validation & Testing

**ICD-1 Test:** Generate test pass schedule, verify C++ can parse
**ICD-2 Test:** Capture synthetic I/Q, verify Python can decode
**ICD-3 Test:** Fetch TLE, validate format and checksum
**ICD-4 Test:** Decode known-good I/Q, verify image output format
**ICD-5 Test:** End-to-end automation test (simulate full pass)

**Test Execution:** Weekly during development, before each verification stage
