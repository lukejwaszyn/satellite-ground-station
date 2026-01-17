from skyfield.api import load, wgs84
from datetime import datetime, timedelta
import numpy as np

# Observer location: State College, PA
LATITUDE = 40.7934    # degrees N
LONGITUDE = -77.8600  # degrees W  
ELEVATION = 376       # meters
MIN_ELEVATION = 10    # degrees - only passes above 10° horizon

def main():
    print("="*60)
    print("SATELLITE GROUND STATION - PASS PREDICTOR V0")
    print("="*60)
    print(f"Observer: State College, PA")
    print(f"Location: {LATITUDE}°N, {LONGITUDE}°W, {ELEVATION}m")
    print(f"Minimum elevation: {MIN_ELEVATION}°\n")
    
    # Load timescale and ephemeris
    ts = load.timescale()
    
    # Observer position
    observer = wgs84.latlon(LATITUDE, LONGITUDE, elevation_m=ELEVATION)
    
    # Download latest TLE data for NOAA weather satellites
    print("Downloading TLE data from Celestrak...")
    stations_url = 'https://celestrak.org/NORAD/elements/gp.php?GROUP=weather&FORMAT=tle'
    satellites = load.tle_file(stations_url, filename='weather.txt')
    print(f"Loaded {len(satellites)} satellites\n")
    
    # Find NOAA 20
    by_name = {sat.name: sat for sat in satellites}
    
    if 'NOAA 20 (JPSS-1)' not in by_name:
        print("ERROR: NOAA 20 not found in TLE data")
        print("Available satellites:", list(by_name.keys()))
        return
    
    noaa18 = by_name['NOAA 20 (JPSS-1)']
    
    print(f"Target: {noaa18.name}")
    print(f"TLE Epoch: {noaa18.epoch.utc_datetime()}\n")
    
    # Predict passes for next 7 days
    print("Predicting passes for next 7 days...\n")
    
    t0 = ts.now()
    t1 = ts.tt_jd(t0.tt + 7)  # 7 days from now
    
    # Find events (rise, culminate, set)
    t, events = noaa18.find_events(observer, t0, t1, altitude_degrees=MIN_ELEVATION)
    
    # Group events into passes
    passes = []
    for ti, event in zip(t, events):
        if event == 0:  # Rise (AOS)
            aos_time = ti.utc_datetime()
            difference = noaa18 - observer
            topocentric = difference.at(ti)
            alt, az, distance = topocentric.altaz()
            aos_az = az.degrees
            
            passes.append({
                'aos_time': aos_time,
                'aos_az': aos_az,
                'max_el': None,
                'max_time': None,
                'max_az': None,
                'los_time': None,
                'los_az': None
            })
        
        elif event == 1 and passes:  # Culminate (max elevation)
            difference = noaa18 - observer
            topocentric = difference.at(ti)
            alt, az, distance = topocentric.altaz()
            
            passes[-1]['max_el'] = alt.degrees
            passes[-1]['max_time'] = ti.utc_datetime()
            passes[-1]['max_az'] = az.degrees
        
        elif event == 2 and passes:  # Set (LOS)
            difference = noaa18 - observer
            topocentric = difference.at(ti)
            alt, az, distance = topocentric.altaz()
            
            passes[-1]['los_time'] = ti.utc_datetime()
            passes[-1]['los_az'] = az.degrees
    
    # Filter complete passes and display
    complete_passes = [p for p in passes if p['los_time'] is not None]
    
    print(f"Found {len(complete_passes)} passes above {MIN_ELEVATION}° elevation:\n")
    
    for i, p in enumerate(complete_passes, 1):
        duration = (p['los_time'] - p['aos_time']).seconds // 60
        
        print(f"Pass {i}:")
        print(f"  AOS: {p['aos_time'].strftime('%Y-%m-%d %H:%M:%S')} UTC (Az: {p['aos_az']:.1f}°)")
        print(f"  MAX: {p['max_time'].strftime('%Y-%m-%d %H:%M:%S')} UTC (El: {p['max_el']:.1f}°, Az: {p['max_az']:.1f}°)")
        print(f"  LOS: {p['los_time'].strftime('%Y-%m-%d %H:%M:%S')} UTC (Az: {p['los_az']:.1f}°)")
        print(f"  Duration: {duration} minutes\n")
    
    if complete_passes:
        print("="*60)
        print(f"NEXT PASS: {complete_passes[0]['aos_time'].strftime('%Y-%m-%d %H:%M:%S')} UTC")
        print(f"Max elevation: {complete_passes[0]['max_el']:.1f}°")
        print("="*60)

if __name__ == "__main__":
    main()