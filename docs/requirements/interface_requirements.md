# Interface Requirements

## IF-1: Hardware Interfaces
IF-1.1: Antenna → LNA: SMA coax, 50Ω impedance
IF-1.2: LNA → RTL-SDR: SMA coax, 50Ω impedance
IF-1.3: RTL-SDR → Computer: USB 2.0
IF-1.4: Power: LNA requires 5V DC, <100 mA

## IF-2: Software Interfaces
IF-2.1: Python orbital predictor → C++ capture program (pass schedule JSON)
IF-2.2: C++ capture → Python decoder (raw I/Q file format)
IF-2.3: TLE source: Celestrak HTTPS API (multiple groups: weather, stations, resource, NOAA, individual NORAD ID)
IF-2.4: Output format: PNG/JPEG images, metadata JSON
IF-2.5: Orbital data backend → Mission operations HMI (orbital_data.json)

## IF-3: Data Interfaces
IF-3.1: I/Q sample rate: 250 kHz (after decimation from 2.4 MHz)
IF-3.2: I/Q data type: complex float32
IF-3.3: APT line rate: 2 lines/second, 2080 pixels/line
IF-3.4: Image format: 8-bit grayscale

## IF-4: Mission Operations HMI Interfaces
IF-4.1: Backend → Frontend: orbital_data.json (satellite positions, passes, Doppler profiles)
IF-4.2: Celestrak → Backend: TLE files via HTTPS (weather, stations, resource groups + individual NORAD ID queries)
IF-4.3: Frontend rendering: Three.js r128 via WebGL
IF-4.4: Local serving: HTTP server (python -m http.server) required for JSON fetch
IF-4.5: Position coordinate system: ECEF (km) from Skyfield, converted to Three.js scene units
IF-4.6: Time synchronization: UTC timestamps, Unix epoch for interpolation
