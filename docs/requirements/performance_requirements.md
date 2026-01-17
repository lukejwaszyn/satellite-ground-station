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
PR-4.1: Development timeline: 7 weeks (108 hours)
PR-4.2: Unattended operation duration: 24+ hours
PR-4.3: Storage per pass: <500 MB raw I/Q, <5 MB decoded image
