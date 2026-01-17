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
