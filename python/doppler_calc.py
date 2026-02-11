#!/usr/bin/env python3
"""
doppler_calc.py
Satellite Ground Station - Doppler Frequency Calculator

Calculates Doppler shift profile for a satellite pass.
Outputs time vs frequency offset for real-time tracking.

Physics:
    f_observed = f_transmitted * (1 + v_radial / c)
    Doppler shift = f_observed - f_transmitted = f_transmitted * (v_radial / c)

For NOAA satellites at ~850 km altitude:
    - Max radial velocity: ~7 km/s
    - Max Doppler at 137 MHz: ~3.2 kHz

Author: Luke Waszyn
Date: February 2026
"""

import numpy as np
from skyfield.api import load, wgs84, EarthSatellite
from datetime import datetime, timedelta
import json
import os

# Speed of light
C = 299792458.0  # m/s

# NOAA satellite frequencies (Hz)
NOAA_FREQUENCIES = {
    'NOAA 15': 137.620e6,
    'NOAA 18': 137.9125e6,
    'NOAA 19': 137.100e6,
    'NOAA 20': 137.100e6,  # NOAA 20 uses same as NOAA 19
}

# Observer location (State College, PA)
OBSERVER_LAT = 40.7934
OBSERVER_LON = -77.8600
OBSERVER_ELEV = 376  # meters


def load_satellite(sat_name, tle_file='weather.txt'):
    """Load satellite from TLE file."""
    ts = load.timescale()
    
    # Download if not exists
    if not os.path.exists(tle_file):
        url = 'https://celestrak.org/NORAD/elements/gp.php?GROUP=weather&FORMAT=tle'
        satellites = load.tle_file(url, filename=tle_file)
    else:
        satellites = load.tle_file(tle_file)
    
    by_name = {sat.name: sat for sat in satellites}
    
    # Handle various naming conventions
    for name in by_name:
        if sat_name.upper() in name.upper():
            return by_name[name], ts
    
    raise ValueError(f"Satellite {sat_name} not found. Available: {list(by_name.keys())[:10]}")


def calculate_doppler_profile(sat_name, aos_time, los_time, time_step_sec=1.0, center_freq_hz=None):
    """
    Calculate Doppler shift profile for a satellite pass.
    
    Args:
        sat_name: Satellite name (e.g., 'NOAA 18')
        aos_time: Acquisition of signal time (datetime, UTC)
        los_time: Loss of signal time (datetime, UTC)
        time_step_sec: Time resolution in seconds
        center_freq_hz: Transmit frequency (auto-detected if None)
    
    Returns:
        Dictionary with time and frequency arrays
    """
    # Load satellite
    satellite, ts = load_satellite(sat_name)
    
    # Get transmit frequency
    if center_freq_hz is None:
        for key in NOAA_FREQUENCIES:
            if key in sat_name or sat_name in key:
                center_freq_hz = NOAA_FREQUENCIES[key]
                break
        else:
            center_freq_hz = 137.5e6  # Default to mid-band
    
    # Observer position
    observer = wgs84.latlon(OBSERVER_LAT, OBSERVER_LON, elevation_m=OBSERVER_ELEV)
    
    # Generate time array
    duration_sec = (los_time - aos_time).total_seconds()
    num_points = int(duration_sec / time_step_sec) + 1
    
    times_sec = []
    doppler_hz = []
    elevations = []
    azimuths = []
    ranges_km = []
    
    for i in range(num_points):
        # Current time
        dt = aos_time + timedelta(seconds=i * time_step_sec)
        t = ts.utc(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second + dt.microsecond/1e6)
        
        # Satellite position relative to observer
        difference = satellite - observer
        topocentric = difference.at(t)
        
        # Elevation and azimuth
        alt, az, distance = topocentric.altaz()
        
        # Position and velocity
        pos = topocentric.position.km
        vel = topocentric.velocity.km_per_s
        
        # Range (distance to satellite)
        range_km = np.linalg.norm(pos)
        
        # Radial velocity (positive = moving away)
        # v_radial = dot(velocity, unit_position_vector)
        range_unit = pos / range_km
        v_radial = np.dot(vel, range_unit)  # km/s
        v_radial_mps = v_radial * 1000  # m/s
        
        # Doppler shift
        # Negative v_radial (approaching) = positive frequency shift
        doppler = -center_freq_hz * (v_radial_mps / C)
        
        times_sec.append(i * time_step_sec)
        doppler_hz.append(doppler)
        elevations.append(alt.degrees)
        azimuths.append(az.degrees)
        ranges_km.append(range_km)
    
    return {
        'satellite': sat_name,
        'center_freq_hz': center_freq_hz,
        'aos_utc': aos_time.isoformat(),
        'los_utc': los_time.isoformat(),
        'duration_sec': duration_sec,
        'time_step_sec': time_step_sec,
        'times_sec': times_sec,
        'doppler_hz': doppler_hz,
        'elevations_deg': elevations,
        'azimuths_deg': azimuths,
        'ranges_km': ranges_km,
        'max_doppler_hz': max(doppler_hz),
        'min_doppler_hz': min(doppler_hz),
        'doppler_rate_hz_per_sec': (doppler_hz[-1] - doppler_hz[0]) / duration_sec if duration_sec > 0 else 0
    }


def save_doppler_profile(profile, output_path):
    """Save Doppler profile to JSON file."""
    # Convert numpy types to native Python
    profile_clean = {}
    for key, val in profile.items():
        if isinstance(val, np.ndarray):
            profile_clean[key] = val.tolist()
        elif isinstance(val, (np.float64, np.float32)):
            profile_clean[key] = float(val)
        elif isinstance(val, (np.int64, np.int32)):
            profile_clean[key] = int(val)
        else:
            profile_clean[key] = val
    
    with open(output_path, 'w') as f:
        json.dump(profile_clean, f, indent=2)
    
    print(f"Saved Doppler profile: {output_path}")


def print_profile_summary(profile):
    """Print summary of Doppler profile."""
    print("\n" + "="*60)
    print("DOPPLER PROFILE SUMMARY")
    print("="*60)
    print(f"Satellite: {profile['satellite']}")
    print(f"Center Frequency: {profile['center_freq_hz']/1e6:.4f} MHz")
    print(f"AOS: {profile['aos_utc']}")
    print(f"LOS: {profile['los_utc']}")
    print(f"Duration: {profile['duration_sec']:.1f} seconds")
    print(f"\nDoppler Range:")
    print(f"  Max: +{profile['max_doppler_hz']:.1f} Hz (approaching)")
    print(f"  Min: {profile['min_doppler_hz']:.1f} Hz (receding)")
    print(f"  Total Swing: {profile['max_doppler_hz'] - profile['min_doppler_hz']:.1f} Hz")
    print(f"\nMax Elevation: {max(profile['elevations_deg']):.1f}°")
    print("="*60)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 4:
        print("Usage: python doppler_calc.py <satellite> <aos_utc> <los_utc> [output.json]")
        print("")
        print("Arguments:")
        print("  satellite  - Satellite name (e.g., 'NOAA 18')")
        print("  aos_utc    - AOS time in ISO format (e.g., '2026-02-03T14:30:00')")
        print("  los_utc    - LOS time in ISO format (e.g., '2026-02-03T14:45:00')")
        print("  output     - Output JSON file (optional)")
        print("")
        print("Example:")
        print("  python doppler_calc.py 'NOAA 18' '2026-02-03T14:30:00' '2026-02-03T14:45:00'")
        sys.exit(1)
    
    sat = sys.argv[1]
    aos = datetime.fromisoformat(sys.argv[2])
    los = datetime.fromisoformat(sys.argv[3])
    output = sys.argv[4] if len(sys.argv) > 4 else None
    
    profile = calculate_doppler_profile(sat, aos, los)
    print_profile_summary(profile)
    
    if output:
        save_doppler_profile(profile, output)
    else:
        # Default output location
        os.makedirs('data/doppler', exist_ok=True)
        default_path = f"data/doppler/doppler_{sat.replace(' ', '_')}_{aos.strftime('%Y%m%d_%H%M%S')}.json"
        save_doppler_profile(profile, default_path)
