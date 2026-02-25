# Verification Plan

## Overview

This document defines the staged verification strategy (V0-V6) for the Autonomous Satellite Ground Station project. Each verification stage has clear objectives, methods, pass criteria, and deliverables.

V0-V5 cover core satellite reception capabilities. V6 extends the system with AI/ML mission planning and optimization.

---

## V0: Orbital Prediction Validation

**Status:** COMPLETE (January 16, 2026)

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
- Python pass prediction script
- 7-day pass forecast for State College, PA
- Doppler frequency profiles
- Comparison table vs. Heavens-Above

---

## V0.5: Mission Operations Interface Validation

**Status:** COMPLETE (February 25, 2026)

**Objective:** Validate 3D mission operations HMI with real SGP4 orbital data

**Method:**
1. Implement Python backend (generate_orbital_data.py) using Skyfield SGP4
2. Fetch TLEs from multiple Celestrak groups (weather, stations, resource, individual NORAD ID)
3. Propagate 12 satellites across NOAA, METEOR, ISS, Landsat, Terra, Aqua constellations
4. Compute pass predictions and Doppler profiles for satellites with known downlink frequencies
5. Export orbital_data.json for frontend consumption
6. Implement Three.js 3D frontend (satellite-viz.html) with real-time satellite visualization
7. Verify satellite positions match backend propagation data
8. Verify pass timeline, elevation chart, and Doppler chart display correctly
9. Verify demo mode fallback operates when orbital_data.json is unavailable

**Pass Criteria:**
- All satellites render at correct orbital positions on 3D globe
- Pass predictions match generate_orbital_data.py output exactly
- Doppler chart shows correct S-curve with zero-crossing at TCA
- Elevation profile matches computed pass geometry
- Satellite roles (primary/weather/display) sort and badge correctly
- Frontend maintains >30 FPS at 1080p
- Demo mode activates gracefully when JSON is missing

**Results:**
- 12 satellites tracked across 5 constellations
- NOAA 20 correctly identified as primary imaging target
- Doppler profiles validated against doppler_calc.py calculations
- Pass predictions consistent with predict_passes.py output
- 3D visualization renders smoothly with satellite interpolation
- Skyfield SGP4 data source badge displays correctly

**Deliverables:**
- generate_orbital_data.py (Skyfield SGP4 multi-constellation backend)
- satellite-viz.html (Three.js 3D mission operations frontend)
- orbital_data.json (sample output)
- Screenshot of operational HMI

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

**Deliverables:**
- Raw I/Q capture file (archived)
- PSD plot showing carrier peak
- Spectrogram showing Doppler shift over time
- Measured SNR and noise floor values
- V1 verification report

---

## V2: LNA Integration & SNR Improvement

**Target Date:** February 12, 2026 (End of Week 4)

**Objective:** Validate that LNA improves system noise figure and signal quality

**Prerequisites:**
- LNA PCB fabricated and assembled
- LNA characterized on VNA (S-parameters measured)

**Method:**
1. VNA characterization (S21, S11, S22, stability factor)
2. A/B comparison: capture with and without LNA
3. Measure noise floor reduction and SNR improvement

**Pass Criteria:**
- LNA gain measured: 15-20 dB (±1 dB of design target)
- Noise floor reduction: >10 dB
- SNR improvement: >8 dB
- No spurious signals or distortion

**Deliverables:**
- VNA S-parameter plots
- A/B comparison PSD plots
- V2 verification report

---

## V3: Functional Decode (First Image)

**Target Date:** February 19, 2026 (End of Week 5)

**Objective:** Decode first intelligible APT weather satellite image

**Prerequisites:**
- RF link established (V1 complete)
- Preferably LNA integrated (V2 complete)
- DSP decoding pipeline implemented

**Method:**
1. Capture high-quality pass (>40° elevation, clear weather)
2. FM demodulation (quadrature discriminator)
3. APT demodulation (Hilbert transform, sync detection)
4. Image reconstruction (2080 pixels/line, 2 lines/second)

**Pass Criteria:**
- Image shows recognizable Earth features
- Sync pulses correctly detected (>90% detection rate)
- Minimal line skew or distortion

**Deliverables:**
- Decoded APT image (PNG)
- Processing parameters log
- V3 verification report

---

## V4: Automated Doppler Tracking

**Target Date:** February 26, 2026 (End of Week 6)

**Objective:** System operates with real-time frequency correction, no manual intervention

**Prerequisites:**
- V3 complete
- C++ real-time capture program implemented
- Real-time Doppler tracking loop functional

**Method:**
1. Implement C++ librtlsdr interface
2. Implement real-time Doppler tracking loop
3. Compare automated vs. manual capture quality

**Pass Criteria:**
- Frequency error <1 kHz RMS throughout pass
- Image quality equal to or better than manual method
- System operates without user intervention

**Deliverables:**
- Automated vs. manual comparison
- Frequency error time-series
- C++ source code
- V4 verification report

---

## V5: Multi-Pass Performance Characterization

**Target Date:** March 10-20, 2026 (Weeks 8-9)

**Objective:** Validate system reliability and characterize performance across varying conditions

**Prerequisites:**
- V4 complete (automated system operational)
- System configured for unattended operation

**Method:**
1. Schedule 10+ passes over 3-4 days
2. Automated capture and decode
3. Analyze success rate, SNR vs. elevation, frequency stability
4. Identify failure modes

**Pass Criteria:**
- Decode success rate: >80% for passes with max elevation >30°
- System uptime: >95%
- Predictable performance trends

**Deliverables:**
- Multi-pass dataset (10+ decoded images)
- Statistical analysis report
- V5 verification report
- Training data for ML (feature vectors + outcomes)

---

## V6: AI Mission Planning Integration

**Target Date:** March 21-28, 2026 (Weeks 10-11)

**Objective:** Validate that AI/ML mission planning improves system performance

**Prerequisites:**
- V5 complete (sufficient historical data for training)
- ML subsystem implemented (rule-based or ML-based)
- Minimum 20 historical missions logged

### Phase 1: Rule-Based Optimizer Validation

**Target Date:** March 21-23, 2026

**Objective:** Validate deterministic pass scoring and schedule optimization

**Method:**
1. Implement pass scoring function (elevation, weather, time factors)
2. Generate optimized schedule for 7-day window
3. Compare optimized schedule vs. random/naive selection
4. Execute optimized schedule, measure outcomes

**Pass Criteria:**
- Scoring function produces sensible rankings (high elevation + clear weather scores higher)
- Schedule respects resource constraints
- Optimized schedule success rate >= naive schedule success rate

**Deliverables:**
- Pass scoring implementation
- Schedule comparison analysis
- V6-Phase1 verification report

### Phase 2: ML Model Training and Validation

**Target Date:** March 24-26, 2026

**Objective:** Train and validate ML prediction model on historical data

**Method:**
1. Extract feature vectors from V5 historical data
2. Split data: 80% training, 20% validation
3. Train RandomForestClassifier (or alternative)
4. Evaluate: accuracy, precision, recall, ROC-AUC
5. Analyze feature importance
6. Cross-validate with k-fold

**Pass Criteria:**
- Model accuracy: >75% on holdout set
- Precision: >70% (don't skip too many good passes)
- Recall: >80% (don't attempt too many bad passes)
- Top features match domain expectations (elevation, weather should rank high)

**Deliverables:**
- Trained model file (.pkl)
- Validation metrics report
- Feature importance analysis
- Model card documentation

### Phase 3: Online Prediction Validation

**Target Date:** March 27-28, 2026

**Objective:** Validate ML predictions improve operational decisions

**Method:**
1. Use trained model to predict success for upcoming passes
2. Execute predicted high-probability passes
3. Compare: predicted success rate vs. actual success rate
4. Compare: ML-optimized schedule vs. rule-based schedule
5. Measure: did ML improve over rule-based baseline?

**Pass Criteria:**
- Predicted vs. actual correlation: >0.6
- ML schedule success rate >= rule-based success rate
- No systematic bias (not always predicting success or failure)
- Calibration: predicted 80% success passes should succeed ~80% of time

**Deliverables:**
- Prediction log (predicted vs. actual for each pass)
- Calibration plot
- Performance comparison: ML vs. rule-based vs. naive
- V6-Phase3 verification report

### Phase 4: Adaptive Execution Validation (Optional)

**Target Date:** Week 12+ (if time permits)

**Objective:** Validate real-time adaptive recommendations improve capture quality

**Method:**
1. Monitor signal quality during capture
2. Compare observed vs. predicted SNR
3. Generate gain adjustment recommendations
4. Measure: did adaptive adjustments improve outcomes?

**Pass Criteria:**
- Anomaly detection correctly identifies degraded passes
- Gain adjustments improve SNR when recommended
- No false alarms causing unnecessary adjustments

**Deliverables:**
- Adaptive controller implementation
- Real-time recommendation log
- Impact analysis

---

## Post-V6: Documentation & Release

**Target Date:** March 29-30, 2026

**Objective:** Finalize project documentation and prepare for release

**Tasks:**
1. Complete all verification reports (V0-V6)
2. Update README with ML capabilities
3. Document ML architecture and model specifications
4. Add example outputs (decoded images, prediction logs)
5. Code cleanup and commenting
6. Create GitHub release (v2.0)
7. Prepare startup pitch deck (optional)

**Deliverables:**
- Complete GitHub repository
- Professional README
- Hardware documentation
- ML system documentation
- Example outputs and results
- Tagged release (v2.0)

---

## Verification Traceability Matrix

| Requirement | Verification Stage | Method | Status |
|-------------|-------------------|--------|--------|
| FR-1.1 (Predict passes) | V0 | Analysis | Complete |
| FR-1.2 (AOS/LOS timing) | V0 | Analysis | Complete |
| FR-2.1 (Receive 137 MHz) | V1 | Test | Planned |
| FR-2.2 (Carrier lock) | V4 | Test | Planned |
| FR-2.3 (LNA gain) | V2 | Test | Planned |
| FR-3.1 (FM demod) | V3 | Test | Planned |
| FR-3.2 (APT decode) | V3 | Test | Planned |
| FR-4.1 (Doppler calc) | V0 | Analysis | Complete |
| FR-4.2 (SDR tuning) | V4 | Test | Planned |
| FR-5.1 (Auto trigger) | V4 | Test | Planned |
| FR-5.3 (Unattended) | V5 | Test | Planned |
| FR-6.1.1 (Pass scoring) | V6-P1 | Test | Planned |
| FR-6.1.3 (Optimal schedule) | V6-P1 | Test | Planned |
| FR-6.2.1 (Train ML model) | V6-P2 | Test | Planned |
| FR-6.2.2 (Predict success) | V6-P3 | Test | Planned |
| FR-6.4.2 (Update models) | V6-P3 | Test | Planned |
| FR-6.5.3 (Pred vs actual) | V6-P3 | Test | Planned |
| FR-8.1.1 (3D satellite viz) | V0.5 | Demonstration | Complete |
| FR-8.1.3 (Multi-constellation) | V0.5 | Demonstration | Complete |
| FR-8.2.1 (Pass timeline) | V0.5 | Demonstration | Complete |
| FR-8.2.4 (Elevation chart) | V0.5 | Demonstration | Complete |
| FR-8.2.5 (Doppler chart) | V0.5 | Demonstration | Complete |
| FR-8.3.3 (Satellite roles) | V0.5 | Demonstration | Complete |
| FR-8.5.1 (JSON data integration) | V0.5 | Test | Complete |
| FR-8.5.5 (Demo mode fallback) | V0.5 | Test | Complete |
| PR-1.1 (±30s timing) | V0 | Analysis | Complete |
| PR-2.1 (VSWR <2:1) | V2 | Test | Planned |
| PR-2.2 (NF <1.5 dB) | V2 | Test | Planned |
| PR-3.1 (SNR >10 dB) | V3 | Test | Planned |
| PR-3.2 (80% success) | V5 | Test | Planned |
| PR-5.1 (>30 FPS) | V0.5 | Demonstration | Complete |
| PR-5.3 (<60s data gen) | V0.5 | Test | Complete |

---

## Risk Management During Verification

**High-Risk Areas:**
1. **LNA fabrication delay:** Mitigated by early PCB order, proceed without if necessary
2. **Poor weather:** Multiple pass opportunities, can delay by 1-2 days
3. **C++ performance issues:** Fall back to Python for V4 if needed
4. **Insufficient training data for ML:** Extend V5 data collection, use rule-based as fallback
5. **ML model underperforms:** Rule-based optimizer provides baseline capability

**Contingency Planning:**
- V3 is minimum viable project (functional decode)
- V5 is complete without ML (multi-pass characterization)
- V6 can be partial (rule-based only) if ML training data insufficient
- Each stage has clear success/failure criteria to guide decisions

**Decision Gates:**
- After V1: Decide whether to optimize antenna or proceed
- After V2: Decide whether LNA meets requirements or needs redesign
- After V3: Decide whether to proceed to real-time (V4) or iterate on decode quality
- After V5: Decide whether sufficient data for ML training
- After V6-P2: Decide whether ML improves over rule-based (if not, ship rule-based)
