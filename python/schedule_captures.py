#!/usr/bin/env python3
"""
schedule_captures.py
Satellite Ground Station - Capture Scheduler & Orchestrator

Schedules and executes satellite captures based on pass predictions.
Coordinates: prediction -> Doppler calc -> capture -> decode -> log

Workflow:
    1. Load upcoming passes from predict_passes.py
    2. Filter passes meeting minimum elevation criteria
    3. Generate Doppler profiles for selected passes
    4. Wait for AOS, trigger capture
    5. Stop capture at LOS
    6. Run decoder on captured data
    7. Log results to data store

Author: Luke Waszyn
Date: February 2026
"""

import os
import sys
import json
import time
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from python.predict_passes import main as predict_passes
from python.doppler_calc import calculate_doppler_profile, save_doppler_profile

# Configuration
CONFIG = {
    'min_elevation_deg': 20,        # Minimum max elevation to attempt capture
    'pre_aos_margin_sec': 30,       # Start capture this many seconds before AOS
    'post_los_margin_sec': 30,      # Continue capture this many seconds after LOS
    'capture_sample_rate': 2.4e6,   # RTL-SDR sample rate
    'capture_gain_db': 40,          # SDR gain
    'data_dir': 'data',
    'captures_dir': 'data/captures',
    'decoded_dir': 'data/decoded',
    'schedules_dir': 'data/schedules',
    'doppler_dir': 'data/doppler',
}


def ensure_directories():
    """Create necessary data directories."""
    for key in ['data_dir', 'captures_dir', 'decoded_dir', 'schedules_dir', 'doppler_dir']:
        Path(CONFIG[key]).mkdir(parents=True, exist_ok=True)


def get_upcoming_passes(hours_ahead=24, min_elevation=None):
    """
    Get upcoming satellite passes.
    
    Returns list of pass dictionaries with AOS, LOS, max elevation, etc.
    """
    from skyfield.api import load, wgs84
    
    if min_elevation is None:
        min_elevation = CONFIG['min_elevation_deg']
    
    # Observer location (State College, PA)
    LATITUDE = 40.7934
    LONGITUDE = -77.8600
    ELEVATION = 376
    
    ts = load.timescale()
    observer = wgs84.latlon(LATITUDE, LONGITUDE, elevation_m=ELEVATION)
    
    # Load satellites
    tle_file = 'weather.txt'
    url = 'https://celestrak.org/NORAD/elements/gp.php?GROUP=weather&FORMAT=tle'
    
    if not os.path.exists(tle_file):
        satellites = load.tle_file(url, filename=tle_file)
    else:
        # Check if TLE is stale (>24 hours old)
        tle_age = time.time() - os.path.getmtime(tle_file)
        if tle_age > 86400:
            print("TLE file is stale, refreshing...")
            satellites = load.tle_file(url, filename=tle_file, reload=True)
        else:
            satellites = load.tle_file(tle_file)
    
    # Filter to NOAA satellites
    noaa_sats = [sat for sat in satellites if 'NOAA' in sat.name and any(n in sat.name for n in ['15', '18', '19', '20'])]
    
    passes = []
    t0 = ts.now()
    t1 = ts.tt_jd(t0.tt + hours_ahead / 24.0)
    
    for satellite in noaa_sats:
        try:
            t, events = satellite.find_events(observer, t0, t1, altitude_degrees=10)
            
            current_pass = {}
            for ti, event in zip(t, events):
                if event == 0:  # AOS
                    current_pass = {
                        'satellite': satellite.name,
                        'aos_time': ti.utc_datetime(),
                    }
                    diff = satellite - observer
                    topo = diff.at(ti)
                    alt, az, _ = topo.altaz()
                    current_pass['aos_az'] = az.degrees
                    
                elif event == 1:  # Max elevation
                    if current_pass:
                        current_pass['max_time'] = ti.utc_datetime()
                        diff = satellite - observer
                        topo = diff.at(ti)
                        alt, az, _ = topo.altaz()
                        current_pass['max_elevation'] = alt.degrees
                        current_pass['max_az'] = az.degrees
                        
                elif event == 2:  # LOS
                    if current_pass and 'max_elevation' in current_pass:
                        current_pass['los_time'] = ti.utc_datetime()
                        diff = satellite - observer
                        topo = diff.at(ti)
                        alt, az, _ = topo.altaz()
                        current_pass['los_az'] = az.degrees
                        current_pass['duration_sec'] = (current_pass['los_time'] - current_pass['aos_time']).total_seconds()
                        
                        # Filter by elevation
                        if current_pass['max_elevation'] >= min_elevation:
                            passes.append(current_pass)
                        
                        current_pass = {}
        except Exception as e:
            print(f"Warning: Error processing {satellite.name}: {e}")
    
    # Sort by AOS time
    passes.sort(key=lambda p: p['aos_time'])
    
    return passes


def select_best_pass(passes):
    """Select the best upcoming pass based on elevation and timing."""
    if not passes:
        return None
    
    # Score passes: higher elevation = better, sooner = slightly better
    now = datetime.utcnow()
    
    def score_pass(p):
        # Elevation is primary factor (0-90 degrees)
        el_score = p['max_elevation']
        
        # Time factor: slight preference for sooner passes
        hours_until = (p['aos_time'] - now).total_seconds() / 3600
        time_score = max(0, 10 - hours_until)  # Up to 10 bonus points for passes within 10 hours
        
        return el_score + time_score
    
    return max(passes, key=score_pass)


def wait_for_pass(pass_info):
    """Wait until it's time to start capture."""
    aos = pass_info['aos_time']
    start_time = aos - timedelta(seconds=CONFIG['pre_aos_margin_sec'])
    
    now = datetime.utcnow()
    wait_seconds = (start_time - now).total_seconds()
    
    if wait_seconds <= 0:
        print("Pass is starting now or already in progress!")
        return True
    
    print(f"\nWaiting {wait_seconds:.0f} seconds until capture start...")
    print(f"  AOS: {aos.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"  Capture starts: {start_time.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"  Current time: {now.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    
    # Wait with periodic updates
    while wait_seconds > 0:
        if wait_seconds > 60:
            print(f"  {wait_seconds/60:.1f} minutes remaining...")
            time.sleep(60)
        elif wait_seconds > 10:
            print(f"  {wait_seconds:.0f} seconds remaining...")
            time.sleep(10)
        else:
            time.sleep(1)
        
        now = datetime.utcnow()
        wait_seconds = (start_time - now).total_seconds()
    
    return True


def execute_capture(pass_info, doppler_profile):
    """
    Execute the capture for a satellite pass.
    
    This calls the C++ capture program or falls back to rtl_sdr command.
    """
    sat_name = pass_info['satellite'].replace(' ', '_').replace('(', '').replace(')', '')
    timestamp = pass_info['aos_time'].strftime('%Y%m%d_%H%M%S')
    
    output_file = os.path.join(CONFIG['captures_dir'], f"{sat_name}_{timestamp}.bin")
    doppler_file = os.path.join(CONFIG['doppler_dir'], f"{sat_name}_{timestamp}_doppler.json")
    
    # Save Doppler profile for the tracker
    save_doppler_profile(doppler_profile, doppler_file)
    
    # Calculate capture duration
    duration_sec = pass_info['duration_sec'] + CONFIG['pre_aos_margin_sec'] + CONFIG['post_los_margin_sec']
    
    # Get center frequency
    center_freq = doppler_profile['center_freq_hz']
    
    print(f"\n{'='*60}")
    print("STARTING CAPTURE")
    print(f"{'='*60}")
    print(f"Satellite: {pass_info['satellite']}")
    print(f"Frequency: {center_freq/1e6:.4f} MHz")
    print(f"Duration: {duration_sec:.0f} seconds")
    print(f"Output: {output_file}")
    print(f"{'='*60}\n")
    
    # Try C++ capture first, fall back to rtl_sdr
    cpp_capture = './cpp/build/rtlsdr_capture'
    
    if os.path.exists(cpp_capture):
        cmd = [
            cpp_capture,
            '-f', str(int(center_freq)),
            '-s', str(int(CONFIG['capture_sample_rate'])),
            '-g', str(int(CONFIG['capture_gain_db'])),
            '-d', str(int(duration_sec)),
            '-o', output_file,
            '--doppler', doppler_file
        ]
    else:
        # Fall back to rtl_sdr command
        num_samples = int(duration_sec * CONFIG['capture_sample_rate'])
        cmd = [
            'rtl_sdr',
            '-f', str(int(center_freq)),
            '-s', str(int(CONFIG['capture_sample_rate'])),
            '-g', str(int(CONFIG['capture_gain_db'])),
            '-n', str(num_samples),
            output_file
        ]
    
    print(f"Executing: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=duration_sec + 60)
        
        if result.returncode == 0:
            print("\nCapture completed successfully!")
            return output_file
        else:
            print(f"\nCapture failed with return code {result.returncode}")
            print(f"stderr: {result.stderr}")
            return None
            
    except subprocess.TimeoutExpired:
        print("\nCapture timed out!")
        return None
    except FileNotFoundError:
        print(f"\nCapture program not found. Install rtl_sdr or build C++ capture.")
        return None


def decode_capture(capture_file, pass_info):
    """Run APT decoder on captured file."""
    if not capture_file or not os.path.exists(capture_file):
        print("No capture file to decode")
        return None
    
    sat_name = pass_info['satellite'].replace(' ', '_').replace('(', '').replace(')', '')
    timestamp = pass_info['aos_time'].strftime('%Y%m%d_%H%M%S')
    
    output_dir = CONFIG['decoded_dir']
    
    print(f"\n{'='*60}")
    print("DECODING CAPTURE")
    print(f"{'='*60}")
    
    try:
        # Import decoder
        from python.demod.decode_apt import decode_apt
        
        result = decode_apt(capture_file, output_dir)
        
        print(f"\nDecode completed!")
        print(f"Image: {result['png_path']}")
        
        return result
        
    except Exception as e:
        print(f"Decode failed: {e}")
        return None


def log_mission(pass_info, capture_file, decode_result):
    """Log mission results to data store."""
    mission_log = {
        'timestamp': datetime.utcnow().isoformat(),
        'satellite': pass_info['satellite'],
        'aos_utc': pass_info['aos_time'].isoformat(),
        'los_utc': pass_info['los_time'].isoformat(),
        'max_elevation_deg': pass_info['max_elevation'],
        'duration_sec': pass_info['duration_sec'],
        'capture_file': capture_file,
        'capture_success': capture_file is not None and os.path.exists(capture_file) if capture_file else False,
        'decode_success': decode_result is not None,
        'image_file': decode_result['png_path'] if decode_result else None,
    }
    
    # Append to mission log
    log_file = os.path.join(CONFIG['data_dir'], 'mission_log.json')
    
    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            logs = json.load(f)
    else:
        logs = []
    
    logs.append(mission_log)
    
    with open(log_file, 'w') as f:
        json.dump(logs, f, indent=2)
    
    print(f"\nMission logged: {log_file}")
    
    return mission_log


def run_single_capture(pass_info=None):
    """Run a single capture mission."""
    ensure_directories()
    
    # Get passes if not provided
    if pass_info is None:
        print("Finding upcoming passes...")
        passes = get_upcoming_passes(hours_ahead=24)
        
        if not passes:
            print("No suitable passes found in next 24 hours")
            return None
        
        print(f"Found {len(passes)} passes")
        pass_info = select_best_pass(passes)
    
    print(f"\nSelected pass:")
    print(f"  Satellite: {pass_info['satellite']}")
    print(f"  AOS: {pass_info['aos_time'].strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"  Max El: {pass_info['max_elevation']:.1f}°")
    print(f"  Duration: {pass_info['duration_sec']/60:.1f} minutes")
    
    # Generate Doppler profile
    print("\nCalculating Doppler profile...")
    doppler_profile = calculate_doppler_profile(
        pass_info['satellite'],
        pass_info['aos_time'],
        pass_info['los_time']
    )
    
    print(f"  Doppler range: {doppler_profile['min_doppler_hz']:.0f} to {doppler_profile['max_doppler_hz']:.0f} Hz")
    
    # Wait for pass
    wait_for_pass(pass_info)
    
    # Execute capture
    capture_file = execute_capture(pass_info, doppler_profile)
    
    # Decode
    decode_result = decode_capture(capture_file, pass_info)
    
    # Log mission
    mission_log = log_mission(pass_info, capture_file, decode_result)
    
    return mission_log


def run_daemon(hours=24):
    """Run continuous capture daemon for specified duration."""
    print(f"\n{'='*60}")
    print("SATELLITE CAPTURE DAEMON")
    print(f"Running for {hours} hours")
    print(f"{'='*60}\n")
    
    ensure_directories()
    end_time = datetime.utcnow() + timedelta(hours=hours)
    
    while datetime.utcnow() < end_time:
        # Get upcoming passes
        passes = get_upcoming_passes(hours_ahead=min(hours, 12))
        
        if not passes:
            print("No passes found, sleeping for 30 minutes...")
            time.sleep(1800)
            continue
        
        # Run next capture
        next_pass = passes[0]
        
        # Check if pass is soon enough to wait for
        time_until = (next_pass['aos_time'] - datetime.utcnow()).total_seconds()
        
        if time_until > 3600:  # More than 1 hour away
            sleep_time = time_until - 3600  # Wake up 1 hour before
            print(f"Next pass in {time_until/3600:.1f} hours, sleeping for {sleep_time/60:.0f} minutes...")
            time.sleep(sleep_time)
        
        # Run capture
        run_single_capture(next_pass)
        
        # Brief pause before looking for next pass
        time.sleep(60)
    
    print("\nDaemon finished.")


def list_upcoming_passes():
    """List upcoming passes without capturing."""
    passes = get_upcoming_passes(hours_ahead=48)
    
    print(f"\n{'='*60}")
    print("UPCOMING PASSES (next 48 hours)")
    print(f"{'='*60}\n")
    
    if not passes:
        print("No passes found")
        return
    
    for i, p in enumerate(passes, 1):
        print(f"{i}. {p['satellite']}")
        print(f"   AOS: {p['aos_time'].strftime('%Y-%m-%d %H:%M:%S')} UTC")
        print(f"   Max El: {p['max_elevation']:.1f}° at {p['max_time'].strftime('%H:%M:%S')}")
        print(f"   Duration: {p['duration_sec']/60:.1f} min")
        print()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Satellite Capture Scheduler')
    parser.add_argument('command', nargs='?', default='list',
                        choices=['list', 'capture', 'daemon'],
                        help='Command to run')
    parser.add_argument('--hours', type=int, default=24,
                        help='Hours to run daemon (default: 24)')
    
    args = parser.parse_args()
    
    if args.command == 'list':
        list_upcoming_passes()
    elif args.command == 'capture':
        run_single_capture()
    elif args.command == 'daemon':
        run_daemon(args.hours)
