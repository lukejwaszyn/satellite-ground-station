# Functional Requirements

## FR-1: Orbital Prediction
FR-1.1: System shall predict NOAA satellite passes for State College, PA
FR-1.2: System shall calculate AOS/LOS times within 30 seconds of actual
FR-1.3: System shall compute azimuth, elevation, and range throughout pass
FR-1.4: System shall update TLE data from Celestrak daily

## FR-2: RF Reception
FR-2.1: System shall receive 137 MHz signals from NOAA satellites
FR-2.2: System shall maintain carrier lock throughout pass (±5 kHz Doppler)
FR-2.3: System shall amplify signals with 15-20 dB gain before SDR
FR-2.4: System shall reject out-of-band interference

## FR-3: Signal Processing
FR-3.1: System shall perform FM demodulation of APT signal
FR-3.2: System shall decode APT image format (2 lines/second, 2080 pixels/line)
FR-3.3: System shall detect sync pulses for line synchronization
FR-3.4: System shall output grayscale image in PNG/JPEG format

## FR-4: Doppler Compensation
FR-4.1: System shall calculate instantaneous Doppler shift in real-time
FR-4.2: System shall adjust SDR center frequency every 1-5 seconds
FR-4.3: System shall maintain frequency error < 1 kHz during pass

## FR-5: Automation
FR-5.1: System shall trigger capture automatically at predicted AOS
FR-5.2: System shall terminate capture at predicted LOS
FR-5.3: System shall operate unattended for 24+ hour periods
FR-5.4: System shall log all captures with timestamp and metadata

## FR-6: AI Mission Planning

### FR-6.1: Pass Selection Optimization
FR-6.1.1: System shall score upcoming passes based on predicted success probability
FR-6.1.2: System shall incorporate elevation, weather, time-of-day, and historical performance into scoring
FR-6.1.3: System shall generate optimal 7-day capture schedule given resource constraints
FR-6.1.4: System shall re-optimize schedule when conditions change (weather updates, hardware status)

### FR-6.2: Predictive Modeling
FR-6.2.1: System shall train ML models on historical pass data (features: elevation, weather, gain, antenna config)
FR-6.2.2: System shall predict decode success probability for each scheduled pass
FR-6.2.3: System shall estimate expected SNR based on pass parameters
FR-6.2.4: System shall identify optimal gain settings per pass based on learned patterns

### FR-6.3: Adaptive Execution
FR-6.3.1: System shall monitor real-time signal quality during capture
FR-6.3.2: System shall recommend gain adjustments when SNR deviates from predicted
FR-6.3.3: System shall flag anomalies (interference, hardware degradation, unexpected signal loss)
FR-6.3.4: System shall log all adaptive decisions for post-mission analysis

### FR-6.4: Post-Mission Learning
FR-6.4.1: System shall compute mission success metrics after each capture
FR-6.4.2: System shall update ML models with new mission data (online learning or batch retraining)
FR-6.4.3: System shall identify systematic failure modes from historical data
FR-6.4.4: System shall generate recommendations for operational improvements

### FR-6.5: Mission Analytics
FR-6.5.1: System shall provide dashboard showing pass schedule, predictions, and outcomes
FR-6.5.2: System shall generate performance trend reports (success rate over time, SNR trends)
FR-6.5.3: System shall compare predicted vs. actual outcomes for model validation
FR-6.5.4: System shall export metrics in standard formats (CSV, JSON) for external analysis

## FR-7: Startup/Commercial Extensibility

### FR-7.1: Generalization
FR-7.1.1: Mission planning framework shall be parameterizable for different mission types
FR-7.1.2: System shall support configuration-driven mission definitions (not hardcoded to NOAA APT)
FR-7.1.3: System shall provide API for external systems to submit mission requests

### FR-7.2: Multi-User Support
FR-7.2.1: System shall support multiple concurrent mission types (future capability)
FR-7.2.2: System shall prioritize missions based on configurable priority rules
FR-7.2.3: System shall handle resource conflicts (antenna, SDR, compute) gracefully
