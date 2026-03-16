# Functional Requirements

## FR-1: Orbital Prediction
- FR-1.1: System shall predict satellite passes for State College, PA (40.7934°N, 77.8600°W)
- FR-1.2: System shall calculate AOS/LOS times within ±30 seconds of actual
- FR-1.3: System shall compute azimuth, elevation, and range throughout each pass
- FR-1.4: System shall update TLE data from Celestrak daily (weather, stations, resource groups + individual NORAD ID fallback)
- FR-1.5: System shall distinguish capturable satellites (APT/LRPT) from display-only satellites

## FR-2: RF Reception
- FR-2.1: System shall receive 137 MHz signals from NOAA and METEOR satellites
- FR-2.2: System shall maintain carrier lock throughout pass (±5 kHz Doppler)
- FR-2.3: System shall amplify signals with 15-20 dB gain before SDR (SAWbird NOAA LNA)
- FR-2.4: System shall reject out-of-band interference (SAW filter at 137.5 MHz)

## FR-3: Signal Processing — APT (NOAA)
- FR-3.1: System shall perform FM demodulation of NOAA APT signal
- FR-3.2: System shall decode APT image format (2 lines/second, 2080 pixels/line)
- FR-3.3: System shall detect sync pulses for line synchronization
- FR-3.4: System shall output grayscale image in PNG format
- FR-3.5: System shall support chunked processing for captures exceeding available RAM

## FR-3A: Signal Processing — LRPT (METEOR)
- FR-3A.1: System shall perform QPSK demodulation of METEOR LRPT signal (72 kSym/s)
- FR-3A.2: System shall perform Viterbi decoding (rate 1/2, constraint length k=7)
- FR-3A.3: System shall detect and synchronize to CCSDS frame boundaries (0x1ACFFC1D sync word)
- FR-3A.4: System shall derandomize CCSDS frames using standard PRBS sequence
- FR-3A.5: System shall perform Reed-Solomon error detection on RS(255,223) codewords
- FR-3A.6: System shall reassemble multi-channel imagery from VCDU packets (up to 6 AVHRR channels)
- FR-3A.7: System shall generate RGB composite from available channels
- FR-3A.8: System shall output multi-channel PNG images and composite

## FR-3B: Decoder Routing
- FR-3B.1: System shall automatically select APT or LRPT decoder based on satellite identity
- FR-3B.2: System shall tag decoded images with signal type (APT/LRPT) in mission log
- FR-3B.3: Server shall route METEOR captures to decode_lrpt.py and NOAA captures to decode_apt.py

## FR-3C: Quality Estimation
- FR-3C.1: System shall estimate SNR of decoded images using block variance analysis
- FR-3C.2: System shall compute image entropy as a content richness metric
- FR-3C.3: System shall detect edges to distinguish real imagery from noise
- FR-3C.4: System shall detect periodic interference patterns via FFT analysis
- FR-3C.5: System shall assign quality grade (GOOD / MARGINAL / NOISE) to every decoded image
- FR-3C.6: System shall output quality report JSON alongside decoded images

## FR-3D: Decoder Validation
- FR-3D.1: System shall support running SatDump and custom decoder on the same capture
- FR-3D.2: System shall generate side-by-side comparison images
- FR-3D.3: System shall produce comparison report with SNR estimates from both decoders

## FR-4: Doppler Compensation
- FR-4.1: System shall calculate instantaneous Doppler shift in real-time
- FR-4.2: System shall adjust SDR center frequency every 1-5 seconds
- FR-4.3: System shall maintain frequency error <1 kHz during pass

## FR-5: Automation
- FR-5.1: System shall trigger capture automatically at predicted AOS
- FR-5.2: System shall terminate capture at predicted LOS
- FR-5.3: System shall operate unattended for 24+ hour periods
- FR-5.4: System shall log all captures with timestamp, satellite, signal type, and metadata

## FR-6: AI Mission Planning

### FR-6.1: Pass Selection Optimization
- FR-6.1.1: System shall score passes based on predicted success probability
- FR-6.1.2: System shall incorporate elevation, weather, time-of-day, signal type, and history into scoring
- FR-6.1.3: System shall generate optimal 7-day capture schedule given resource constraints
- FR-6.1.4: System shall re-optimize schedule when conditions change

### FR-6.2: Predictive Modeling
- FR-6.2.1: System shall train ML models on historical pass data
- FR-6.2.2: System shall predict decode success probability for each scheduled pass
- FR-6.2.3: System shall estimate expected SNR based on pass parameters
- FR-6.2.4: System shall identify optimal gain settings per pass

### FR-6.3: Adaptive Execution
- FR-6.3.1: System shall monitor real-time signal quality during capture
- FR-6.3.2: System shall recommend gain adjustments when SNR deviates from predicted
- FR-6.3.3: System shall flag anomalies (interference, hardware degradation, signal loss)

### FR-6.4: Post-Mission Learning
- FR-6.4.1: System shall compute mission success metrics after each capture (auto-graded by quality estimator)
- FR-6.4.2: System shall update ML models with new mission data
- FR-6.4.3: System shall identify systematic failure modes from historical data

### FR-6.5: Mission Analytics
- FR-6.5.1: System shall provide dashboard showing pass schedule, predictions, and outcomes
- FR-6.5.2: System shall generate performance trend reports
- FR-6.5.3: System shall compare predicted vs. actual outcomes for model validation

## FR-7: Startup/Commercial Extensibility
- FR-7.1.1: Mission planning framework shall be parameterizable for different mission types
- FR-7.1.2: System shall support configuration-driven mission definitions
- FR-7.1.3: System shall provide API for external systems to submit mission requests

## FR-8: Mission Operations Interface (HMI)

### FR-8.1: Real-Time Satellite Visualization
- FR-8.1.1: System shall render 3D globe with NASA Blue Marble texture and real-time satellite positions
- FR-8.1.2: System shall display ground station with configurable elevation visibility cone
- FR-8.1.3: System shall track multiple constellations (NOAA, METEOR, ISS, Terra, Aqua, Landsat)
- FR-8.1.4: System shall interpolate positions between propagation samples for smooth animation
- FR-8.1.5: System shall display signal type badges (APT / LRPT / TRACK) on each satellite
- FR-8.1.6: System shall support adjustable time warp (1x to 512x)

### FR-8.2: Pass Prediction Display
- FR-8.2.1: System shall display next pass timeline with AOS/TCA/LOS events
- FR-8.2.2: System shall show pass countdown timer
- FR-8.2.3: System shall render elevation profile and Doppler shift charts
- FR-8.2.4: System shall provide sortable pass schedule table with signal type column

### FR-8.3: Mission Control
- FR-8.3.1: System shall display SDR connection status
- FR-8.3.2: System shall provide AOS-gated capture button
- FR-8.3.3: System shall display mission log with decode results and quality grades
- FR-8.3.4: System shall serve decoded images for viewing
