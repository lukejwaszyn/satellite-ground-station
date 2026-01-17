# Verification Plan

## Overview

This document defines the staged verification strategy (V0-V5) for the Autonomous Satellite Ground Station project. Each verification stage has clear objectives, methods, pass criteria, and deliverables.

---

## V0: Orbital Prediction Validation

**Status:** ✅ COMPLETE (January 16, 2026)

**Objective:** Validate SGP4 propagator and pass prediction accuracy

**Method:**
1. Implement Python-based SGP4 propagator using Skyfield
2. Fetch NOAA satellite TLE data from Celestrak
3. Predict all passes for 7-day window (Jan 16-23, 2026)
4. Cross-reference predictions against Heavens-Above website
5. Calculate timing errors (AOS, LOS, max elevation time)
6. Calculate angular errors (max elevation angle, azimuth at AOS/LOS)

**Pass Criteria:**
- AOS/LOS timing accuracy: ±30 seconds
- Max elevation angle accuracy: ±2 degrees
- All three NOAA satellites (15, 18, 19) validated

**Results:**
- Timing accuracy: Within 15 seconds (exceeded requirement)
- Elevation accuracy: Within 1.2 degrees (exceeded requirement)
- Doppler calculation implemented and validated

**Deliverables:**
- ✅ Python pass prediction script
- ✅ 7-day pass forecast for State College, PA
- ✅ Doppler frequency profiles
- ✅ Comparison table vs. Heavens-Above

**Lessons Learned:**
- Skyfield library provides excellent SGP4 implementation
- TLE update frequency matters (daily recommended)
- Doppler shifts range from ±3.5 kHz for NOAA satellites

---

## V1: RF Link Establishment

**Target Date:** January 29, 2026 (End of Week 2)

**Objective:** Detect NOAA carrier in captured RF spectrum

**Prerequisites:**
- Custom VHF dipole antenna fabricated
- Antenna mounted outdoors with clear sky view
- RTL-SDR configured and tested

**Method:**
1. Select high-elevation pass (>30° max elevation preferred)
2. Use pass prediction to determine AOS time
3. Deploy antenna 15 minutes before AOS
4. Configure RTL-SDR: 137.X MHz center frequency, 2.4 MHz sample rate, fixed gain
5. Start capture 2 minutes before predicted AOS
6. Capture continuously through pass (AOS to LOS + 2 min margin)
7. Stop capture 2 minutes after predicted LOS
8. Process captured I/Q:
   - Remove DC offset
   - Compute PSD using Welch method (NFFT = 32768)
   - Generate spectrogram (time-frequency plot)
9. Identify carrier peak at expected frequency ± Doppler
10. Measure peak SNR and noise floor

**Pass Criteria:**
- Carrier clearly visible in PSD with SNR > 10 dB
- Peak frequency matches predicted Doppler profile within ±2 kHz
- Carrier visible throughout pass duration (not just at peak elevation)

**Success Definition:**
- System can reliably detect satellite transmissions
- Orbital prediction accuracy confirmed via RF measurements
- Baseline SNR established for comparison with V2 (LNA integration)

**Failure Modes & Contingencies:**
- **No carrier detected:** Check antenna orientation, verify RTL-SDR tuning, retry with different pass
- **Weak SNR (<5 dB):** Acceptable for V1, proceed to V2 (LNA will improve)
- **Frequency error (>5 kHz):** Re-validate Doppler calculation, check TLE freshness

**Deliverables:**
- Raw I/Q capture file (archived)
- PSD plot showing carrier peak
- Spectrogram showing Doppler shift over time
- Measured SNR and noise floor values
- V1 verification report documenting results

**Documentation Requirements:**
- Antenna configuration (height, orientation, environment)
- Weather conditions (cloud cover, precipitation)
- RTL-SDR settings (frequency, gain, sample rate)
- Pass parameters (max elevation, AOS/LOS times)

---

## V2: LNA Integration & SNR Improvement

**Target Date:** February 12, 2026 (End of Week 4)

**Objective:** Validate that LNA improves system noise figure and signal quality

**Prerequisites:**
- LNA PCB fabricated and assembled
- LNA characterized on VNA (S-parameters measured)
- Measured LNA gain: 15-20 dB
- Measured LNA noise figure: <1.5 dB

**Method:**

### Phase 1: VNA Characterization
1. Calibrate VNA for 135-140 MHz band
2. Measure S21 (forward gain) across frequency range
3. Measure S11 (input return loss)
4. Measure S22 (output return loss)
5. Calculate stability factor (K > 1 required)
6. Document gain flatness across 137-138 MHz band

### Phase 2: A/B Comparison
1. **Baseline Capture (No LNA):**
   - Antenna → RTL-SDR (direct connection)
   - Capture during pass with elevation >30°
   - Measure noise floor and peak SNR
2. **LNA Capture:**
   - Antenna → LNA → RTL-SDR
   - Capture during similar pass (same satellite, similar elevation)
   - Measure noise floor and peak SNR
3. **Compare Results:**
   - Calculate noise floor reduction (dB)
   - Calculate SNR improvement (dB)
   - Verify no saturation or intermodulation products

**Pass Criteria:**
- LNA gain measured: 15-20 dB (±1 dB of design target)
- Noise floor reduction: >10 dB
- SNR improvement: >8 dB
- No spurious signals or distortion introduced by LNA
- System remains stable (no oscillation)

**Success Definition:**
- System noise figure reduced to <3 dB
- Signal quality sufficient for reliable APT decode
- LNA provides measurable benefit without introducing issues

**Failure Modes & Contingencies:**
- **Insufficient gain:** Check bias network, verify active device operation
- **Oscillation:** Add isolation, check grounding, reduce gain if necessary
- **No improvement:** Verify LNA in signal path, check coax connections

**Deliverables:**
- VNA S-parameter plots (gain, return loss)
- A/B comparison PSD plots (with/without LNA)
- Noise floor and SNR measurements table
- V2 verification report with analysis

**Risk Mitigation:**
- Order LNA PCB early in Week 3 to allow for 3-5 day fabrication lead time
- Have backup plan: proceed to V3 without LNA if fabrication delayed (degraded performance acceptable)

---

## V3: Functional Decode (First Image)

**Target Date:** February 19, 2026 (End of Week 5)

**Objective:** Decode first intelligible APT weather satellite image

**Prerequisites:**
- RF link established (V1 complete)
- Preferably LNA integrated (V2 complete), but not strictly required
- DSP decoding pipeline implemented and tested

**Method:**

### Capture Phase
1. Select high-quality pass:
   - Max elevation >40° (higher is better)
   - Clear weather conditions (no storms, minimal RF interference)
   - NOAA-18 or NOAA-19 preferred (stronger signals than NOAA-15)
2. Capture full pass from AOS to LOS (10-15 minutes typical)
3. Manual Doppler compensation:
   - Pre-compute Doppler offsets at 1-minute intervals
   - Manually step through frequency offsets during capture OR
   - Capture at nominal frequency, correct in post-processing

### Processing Phase
1. **FM Demodulation:**
   - Load raw I/Q samples
   - Apply quadrature discriminator: `angle(conj(x[n-1]) * x[n])`
   - Lowpass filter to 11 kHz (APT bandwidth)
2. **APT Demodulation:**
   - Resample to ~20.8 kHz (10× APT line rate)
   - Apply Hilbert transform to extract AM envelope
   - Detect sync pulses (7-line sync pattern)
3. **Image Reconstruction:**
   - Synchronize to sync pulses
   - Extract 2080 pixels per line
   - Assemble lines into 2D image array
   - Normalize and scale to 8-bit grayscale
4. **Output:**
   - Save as PNG (lossless)
   - Embed metadata (satellite, timestamp, elevation)

### Visual Inspection
1. Check for recognizable Earth features:
   - Cloud patterns
   - Coastlines (if visible in swath)
   - Day/night boundary
2. Assess image quality:
   - Sync stability (minimal line skew)
   - Noise level (grainy vs. smooth)
   - Contrast and brightness

**Pass Criteria:**
- Image shows recognizable Earth features (clouds, land/water boundaries)
- Sync pulses correctly detected (>90% detection rate)
- Minimal line skew or distortion
- Subjective image quality: "fair" or better

**Success Definition:**
- System can decode APT format end-to-end
- Image quality sufficient to identify weather patterns
- Functional capability demonstrated (even if not optimal)

**Failure Modes & Contingencies:**
- **No sync detected:** Check FM demod output, verify signal present, adjust threshold
- **Severe line skew:** Improve sync detection algorithm, check sample rate accuracy
- **Low SNR image:** Acceptable for V3, will improve with V4 Doppler tracking
- **Partial decode:** Acceptable if >50% of pass decoded successfully

**Deliverables:**
- Decoded APT image (PNG format)
- Raw I/Q file (archived for future re-processing)
- Processing parameters log (filter settings, sync threshold, etc.)
- Image quality assessment report
- V3 verification report

**Success Metrics:**
- Sync detection rate: >90%
- Image coverage: >80% of pass duration
- Subjective quality: Fair/Good/Excellent

---

## V4: Automated Doppler Tracking

**Target Date:** February 26, 2026 (End of Week 6)

**Objective:** System operates with real-time frequency correction, no manual intervention

**Prerequisites:**
- V3 complete (functional APT decode validated)
- C++ real-time capture program implemented
- Real-time Doppler tracking loop functional

**Method:**

### Implementation Phase
1. **C++ Real-Time Capture:**
   - Implement librtlsdr interface
   - Stream I/Q samples to disk
   - Accept frequency update commands via IPC or file
2. **Doppler Tracking Loop:**
   - Read pre-computed Doppler profile from JSON
   - Calculate current frequency offset based on time
   - Send tuning command to RTL-SDR every 1-5 seconds
   - Log all frequency updates with timestamps
3. **Integration Testing:**
   - Test with synthetic Doppler profile
   - Verify frequency updates apply correctly
   - Check latency (target: <100 ms)

### Comparison Test
1. **Manual Doppler Capture (Baseline):**
   - Capture pass using V3 method (manual offsets or post-processing)
   - Decode and assess image quality
2. **Automated Doppler Capture:**
   - Capture same satellite on different pass (similar elevation)
   - System runs unattended with automatic frequency tracking
   - Decode and assess image quality
3. **Performance Comparison:**
   - Image quality (subjective and SNR-based)
   - Carrier lock stability (measure frequency error over time)
   - Decode success rate

**Pass Criteria:**
- Frequency error <1 kHz RMS throughout pass
- Image quality equal to or better than manual method
- System operates without user intervention from AOS to LOS
- No sample drops or corrupted I/Q data

**Success Definition:**
- Automated system matches or exceeds manual performance
- Real-time Doppler compensation validated
- System ready for unattended operation

**Failure Modes & Contingencies:**
- **High frequency error:** Increase update rate, check Doppler calculation accuracy
- **Performance degradation:** Fall back to Python for V4 demo (acceptable, though not true real-time)
- **Sample drops:** Reduce sample rate, optimize I/O, check USB bandwidth

**Deliverables:**
- Automated vs. manual image comparison (side-by-side)
- Frequency error log (time-series plot)
- Doppler tracking performance metrics
- V4 verification report
- C++ source code (archived and documented)

**Performance Metrics:**
- Frequency error: Mean, RMS, max deviation
- Update latency: Time from Doppler calculation to SDR tuning
- CPU usage during capture
- Image quality score (sync rate, SNR estimate)

---

## V5: Multi-Pass Performance Characterization

**Target Date:** March 1-5, 2026 (Week 7)

**Objective:** Validate system reliability and characterize performance across varying conditions

**Prerequisites:**
- V4 complete (automated system operational)
- System configured for unattended operation
- Adequate disk space for multiple captures (>10 GB)

**Method:**

### Data Collection Phase
1. **Schedule 10+ Passes:**
   - All three NOAA satellites (15, 18, 19)
   - Varying elevations: low (10-20°), medium (20-40°), high (>40°)
   - Different times of day: morning, afternoon, evening
   - Capture over 3-4 consecutive days
2. **Automated Operation:**
   - System runs unattended
   - Automatic capture triggered at AOS
   - Automatic decode after LOS
   - Logs all events and errors
3. **Data Archival:**
   - Store raw I/Q (for future re-processing)
   - Store decoded images
   - Store metadata and logs

### Analysis Phase
1. **Success Rate:**
   - Count successful decodes vs. attempted captures
   - Classify failures (RF issues, software errors, environmental)
2. **SNR vs. Elevation:**
   - Plot estimated SNR vs. max elevation angle
   - Determine minimum viable elevation (where SNR > 10 dB threshold)
3. **Frequency Stability:**
   - Analyze frequency error logs
   - Check for systematic errors or drift
4. **Image Quality Metrics:**
   - Sync detection rate per pass
   - Subjective quality assessment
   - Identify common artifacts or issues
5. **System Reliability:**
   - Uptime percentage (successful vs. failed captures)
   - Mean time between failures
   - Error categorization

**Pass Criteria:**
- Decode success rate: >80% for passes with max elevation >30°
- System uptime: >95% (no crashes or hangs during test period)
- Predictable performance trends (e.g., SNR increases with elevation)
- No systematic errors or biases identified

**Success Definition:**
- System demonstrates reliable autonomous operation
- Performance characteristics well-understood and documented
- Ready for continuous operation

**Failure Modes & Contingencies:**
- **Low success rate:** Identify root causes, implement fixes, repeat V5
- **Systematic errors:** Debug and correct, validate with additional passes
- **Environmental issues:** Document and establish operational limits

**Deliverables:**
- Multi-pass dataset:
  - 10+ decoded images
  - Raw I/Q archives
  - Metadata and logs
- Statistical analysis report:
  - Success rate by elevation
  - SNR vs. elevation plot
  - Frequency stability analysis
  - Image quality trends
- V5 verification report (final system characterization)
- Identified failure modes and recommended improvements

**Analysis Outputs:**
- Performance summary table (per-pass results)
- Scatter plots (SNR vs. elevation, sync rate vs. elevation)
- Frequency error histograms
- System reliability metrics
- Recommendations for operational use

---

## Post-V5: Documentation & Release

**Target Date:** March 6-7, 2026

**Objective:** Finalize project documentation and prepare for release

**Tasks:**
1. Complete all verification reports (V0-V5)
2. Update README with project summary and results
3. Document hardware design (antenna, LNA schematics, BOM)
4. Add example outputs (decoded images, plots)
5. Code cleanup and commenting
6. Create GitHub release (v1.0)
7. Optional: Write technical blog post or LinkedIn summary

**Deliverables:**
- Complete GitHub repository
- Professional README
- Hardware documentation
- Example outputs and results
- Tagged release (v1.0)

---

## Verification Traceability Matrix

| Requirement | Verification Stage | Method | Status |
|-------------|-------------------|--------|--------|
| FR-1.1 (Predict passes) | V0 | Analysis | ✅ Complete |
| FR-1.2 (AOS/LOS timing) | V0 | Analysis | ✅ Complete |
| FR-2.1 (Receive 137 MHz) | V1 | Test | Planned |
| FR-2.2 (Carrier lock) | V4 | Test | Planned |
| FR-2.3 (LNA gain) | V2 | Test | Planned |
| FR-3.1 (FM demod) | V3 | Test | Planned |
| FR-3.2 (APT decode) | V3 | Test | Planned |
| FR-4.1 (Doppler calc) | V0 | Analysis | ✅ Complete |
| FR-4.2 (SDR tuning) | V4 | Test | Planned |
| FR-5.1 (Auto trigger) | V4 | Test | Planned |
| FR-5.3 (Unattended) | V5 | Test | Planned |
| PR-1.1 (±30s timing) | V0 | Analysis | ✅ Complete |
| PR-2.1 (VSWR <2:1) | V2 | Test | Planned |
| PR-2.2 (NF <1.5 dB) | V2 | Test | Planned |
| PR-3.1 (SNR >10 dB) | V3 | Test | Planned |
| PR-3.2 (80% success) | V5 | Test | Planned |

**Notes:**
- Each requirement mapped to specific verification stage
- Multiple requirements may be validated in same stage
- Verification methods: Analysis (calculation/simulation), Test (measured data), Inspection (visual/manual check)

---

## Risk Management During Verification

**High-Risk Areas:**
1. **LNA fabrication delay:** Mitigated by early PCB order, contingency plan (proceed without LNA)
2. **Poor weather:** Multiple pass opportunities, can delay by 1-2 days
3. **C++ performance issues:** Fall back to Python for V4 if needed
4. **Low SNR in V1:** Expected and acceptable, LNA will improve in V2

**Contingency Planning:**
- V3 is minimum viable project (functional decode)
- V4-V5 can extend into March if timeline slips
- Each stage has clear success/failure criteria to guide decisions

**Decision Gates:**
- After V1: Decide whether to optimize antenna or proceed
- After V2: Decide whether LNA meets requirements or needs redesign
- After V3: Decide whether to proceed to real-time (V4) or iterate on decode quality
- After V5: Decide whether system is ready for continuous operation or needs improvements
