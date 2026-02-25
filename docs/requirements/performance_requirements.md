# Performance Requirements

## PR-1: Timing Accuracy
PR-1.1: Pass prediction accuracy: ±30 seconds
PR-1.2: Doppler calculation latency: <100 ms
PR-1.3: Frequency update rate: 0.2-1.0 Hz (every 1-5 seconds)

## PR-2: RF Performance
PR-2.1: Antenna VSWR: <2:1 at 137 MHz
PR-2.2: LNA noise figure: <1.5 dB
PR-2.3: LNA gain: 15-20 dB
PR-2.4: System noise figure: <3 dB (antenna + LNA + SDR)

## PR-3: Signal Quality
PR-3.1: Minimum SNR for decode: 10 dB
PR-3.2: Image decode success rate: >80% for passes >30° max elevation
PR-3.3: Carrier lock stability: <1 kHz RMS frequency error

## PR-4: Operational
PR-4.1: Development timeline: 10 weeks
PR-4.2: Unattended operation duration: 24+ hours
PR-4.3: Storage per pass: <500 MB raw I/Q, <5 MB decoded image

## PR-5: Mission Operations Interface
PR-5.1: 3D visualization frame rate: >30 FPS at 1080p resolution
PR-5.2: Satellite position interpolation: smooth animation at 30-second propagation intervals
PR-5.3: Orbital data generation: <60 seconds for 24-hour, 12-satellite propagation
PR-5.4: JSON data payload: <5 MB for 24-hour prediction window
PR-5.5: UI update latency: <100 ms for satellite status, countdown, and chart refresh
PR-5.6: Demo mode fallback: <2 seconds to generate synthetic orbital data
PR-5.7: TLE fetch and cache: <30 seconds for multi-group Celestrak retrieval
