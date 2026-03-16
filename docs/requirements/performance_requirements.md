# Performance Requirements

## PR-1: Timing Accuracy
- PR-1.1: Pass prediction accuracy: ±30 seconds
- PR-1.2: Doppler calculation latency: <100 ms
- PR-1.3: Frequency update rate: 0.2-1.0 Hz (every 1-5 seconds)

## PR-2: RF Performance
- PR-2.1: Antenna VSWR: <2:1 at 137 MHz
- PR-2.2: LNA noise figure: <1.5 dB
- PR-2.3: LNA gain: 15-20 dB
- PR-2.4: System noise figure: <3 dB (antenna + LNA + SDR)

## PR-3: Signal Quality
- PR-3.1: Minimum SNR for APT decode: 10 dB
- PR-3.2: APT decode success rate: >80% for passes >30° max elevation
- PR-3.3: Carrier lock stability: <1 kHz RMS frequency error
- PR-3.4: LRPT frame detection rate: >50% of transmitted frames at SNR >8 dB

## PR-4: Operational
- PR-4.1: Unattended operation duration: 24+ hours
- PR-4.2: Storage per pass: <500 MB raw I/Q, <5 MB decoded images
- PR-4.3: APT decode processing time: <60 seconds for 12-minute pass
- PR-4.4: LRPT decode processing time: <120 seconds for 12-minute pass
- PR-4.5: Quality estimation latency: <5 seconds per image

## PR-5: Mission Operations Interface
- PR-5.1: 3D visualization frame rate: >30 FPS at 1080p
- PR-5.2: Smooth satellite interpolation at 30-second propagation intervals
- PR-5.3: Orbital data generation: <60 seconds for 24-hour, 11-satellite window
- PR-5.4: JSON data payload: <5 MB for 24-hour prediction window
- PR-5.5: UI update latency: <100 ms for status, countdown, and chart refresh
- PR-5.6: Demo mode fallback: <2 seconds to generate synthetic orbital data
- PR-5.7: TLE fetch and cache: <30 seconds for multi-group Celestrak retrieval

## PR-6: ML Performance
- PR-6.1: Schedule generation: <5 seconds for 7-day window
- PR-6.2: Prediction latency: <100 ms per pass
- PR-6.3: Model accuracy: >75% on holdout set (target)
- PR-6.4: Model retraining: <30 seconds for batch update
