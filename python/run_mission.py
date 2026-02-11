#!/usr/bin/env python3
"""
run_mission.py
Satellite Ground Station - End-to-End Mission Runner

Single script to execute a complete mission:
    1. Find next pass
    2. Calculate Doppler profile
    3. Wait for AOS
    4. Capture I/Q data
    5. Decode APT image
    6. Log results
    7. Store ML training data

Author: Luke Waszyn
Date: February 2026
"""

import os
import sys
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from python.schedule_captures import (
    get_upcoming_passes,
    select_best_pass,
    wait_for_pass,
    execute_capture,
    ensure_directories,
    CONFIG
)
from python.doppler_calc import calculate_doppler_profile, save_doppler_profile
from python.data_store import log_mission, log_training_sample, log_metrics, print_summary


def decode_capture_file(capture_file, output_dir):
    """Decode captured I/Q file to image."""
    if not capture_file or not os.path.exists(capture_file):
        print(f"Capture file not found: {capture_file}")
        return None
    
    try:
        from python.demod.decode_apt import decode_apt
        result = decode_apt(capture_file, output_dir)
        return result
    except Exception as e:
        print(f"Decode error: {e}")
        return None


def get_weather_data():
    """
    Fetch current weather data.
    Returns None if weather API not configured.
    
    TODO: Integrate with weather API (OpenWeatherMap, etc.)
    """
    # Placeholder - return None until weather API is integrated
    return {
        'cloud_cover_pct': None,
        'precipitation_prob': None,
        'temperature_c': None
    }


def run_mission(
    satellite: str = None,
    min_elevation: float = 20.0,
    wait: bool = True,
    skip_decode: bool = False,
    dry_run: bool = False
):
    """
    Execute a complete satellite capture mission.
    
    Args:
        satellite: Specific satellite to capture (None = best available)
        min_elevation: Minimum max elevation to attempt
        wait: Wait for AOS if pass is in future
        skip_decode: Skip decode step (just capture)
        dry_run: Print plan but don't execute
    
    Returns:
        Mission result dictionary
    """
    print("\n" + "="*60)
    print("SATELLITE GROUND STATION - MISSION RUNNER")
    print("="*60)
    print(f"Time: {datetime.utcnow().replace(tzinfo=None).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"Min elevation: {min_elevation}°")
    print("="*60 + "\n")
    
    ensure_directories()
    
    # Step 1: Find passes
    print("Step 1: Finding upcoming passes...")
    passes = get_upcoming_passes(hours_ahead=24, min_elevation=min_elevation)
    
    if not passes:
        print("No suitable passes found in next 24 hours.")
        return None
    
    print(f"Found {len(passes)} passes meeting criteria.\n")
    
    # Filter by satellite if specified
    if satellite:
        passes = [p for p in passes if satellite.upper() in p['satellite'].upper()]
        if not passes:
            print(f"No passes found for satellite: {satellite}")
            return None
    
    # Select best pass
    selected_pass = select_best_pass(passes)
    
    print("Step 2: Selected pass:")
    print(f"  Satellite: {selected_pass['satellite']}")
    print(f"  AOS: {selected_pass['aos_time'].strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"  LOS: {selected_pass['los_time'].strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"  Max Elevation: {selected_pass['max_elevation']:.1f}°")
    print(f"  Duration: {selected_pass['duration_sec']/60:.1f} minutes")
    
    # Time until pass
    time_until = (selected_pass['aos_time'].replace(tzinfo=None) - datetime.utcnow().replace(tzinfo=None)).total_seconds()
    if time_until > 0:
        print(f"  Time until AOS: {time_until/60:.1f} minutes")
    else:
        print(f"  Pass is in progress!")
    
    # Step 3: Calculate Doppler
    print("\nStep 3: Calculating Doppler profile...")
    doppler_profile = calculate_doppler_profile(
        selected_pass['satellite'],
        selected_pass['aos_time'],
        selected_pass['los_time']
    )
    
    print(f"  Center frequency: {doppler_profile['center_freq_hz']/1e6:.4f} MHz")
    print(f"  Doppler range: {doppler_profile['min_doppler_hz']:.0f} to +{doppler_profile['max_doppler_hz']:.0f} Hz")
    print(f"  Total swing: {doppler_profile['max_doppler_hz'] - doppler_profile['min_doppler_hz']:.0f} Hz")
    
    # Dry run stops here
    if dry_run:
        print("\n[DRY RUN] Would execute capture and decode.")
        return {
            'pass': selected_pass,
            'doppler': doppler_profile,
            'dry_run': True
        }
    
    # Step 4: Wait for pass
    if wait and time_until > 0:
        print(f"\nStep 4: Waiting for pass...")
        wait_for_pass(selected_pass)
    elif time_until > 0 and not wait:
        print(f"\nPass is {time_until/60:.1f} minutes away. Use --wait to wait for it.")
        return None
    
    # Step 5: Execute capture
    print("\nStep 5: Executing capture...")
    capture_file = execute_capture(selected_pass, doppler_profile)
    
    capture_success = capture_file is not None and os.path.exists(capture_file) if capture_file else False
    
    if not capture_success:
        print("Capture failed!")
        
        # Log failed mission
        log_mission(
            satellite=selected_pass['satellite'],
            aos_time=selected_pass['aos_time'],
            los_time=selected_pass['los_time'],
            max_elevation=selected_pass['max_elevation'],
            capture_success=False,
            decode_success=False,
            notes="Capture failed"
        )
        return {'success': False, 'stage': 'capture'}
    
    print(f"Capture saved: {capture_file}")
    print(f"File size: {os.path.getsize(capture_file) / 1e6:.1f} MB")
    
    # Step 6: Decode
    decode_result = None
    decode_success = False
    
    if not skip_decode:
        print("\nStep 6: Decoding APT image...")
        decode_result = decode_capture_file(capture_file, CONFIG['decoded_dir'])
        decode_success = decode_result is not None
        
        if decode_success:
            print(f"Image saved: {decode_result['png_path']}")
            print(f"Image size: {decode_result['metadata']['image_width']} x {decode_result['metadata']['image_height']}")
        else:
            print("Decode failed!")
    else:
        print("\nStep 6: Skipping decode (--skip-decode)")
    
    # Step 7: Log mission
    print("\nStep 7: Logging mission...")
    
    snr_db = None
    sync_pulses = None
    if decode_result and 'metadata' in decode_result:
        sync_pulses = decode_result['metadata'].get('sync_pulses_found')
    
    mission_record = log_mission(
        satellite=selected_pass['satellite'],
        aos_time=selected_pass['aos_time'],
        los_time=selected_pass['los_time'],
        max_elevation=selected_pass['max_elevation'],
        capture_success=capture_success,
        decode_success=decode_success,
        capture_file=capture_file,
        image_file=decode_result['png_path'] if decode_result else None,
        snr_db=snr_db,
        sync_pulses_found=sync_pulses
    )
    
    # Step 8: Log ML training data
    print("Step 8: Logging ML training sample...")
    
    weather = get_weather_data()
    aos_hour = selected_pass['aos_time'].hour + selected_pass['aos_time'].minute / 60.0
    
    log_training_sample(
        satellite=selected_pass['satellite'],
        max_elevation_deg=selected_pass['max_elevation'],
        duration_min=selected_pass['duration_sec'] / 60.0,
        time_of_day_hour=aos_hour,
        day_of_week=selected_pass['aos_time'].weekday(),
        cloud_cover_pct=weather.get('cloud_cover_pct'),
        precipitation_prob=weather.get('precipitation_prob'),
        temperature_c=weather.get('temperature_c'),
        gain_db=CONFIG['capture_gain_db'],
        antenna_type='dipole',
        using_lna=False,  # Update when LNA is integrated
        decode_success=decode_success,
        snr_db=snr_db,
        sync_rate=sync_pulses / (selected_pass['duration_sec'] * 2) if sync_pulses else None
    )
    
    # Summary
    print("\n" + "="*60)
    print("MISSION COMPLETE")
    print("="*60)
    print(f"Satellite: {selected_pass['satellite']}")
    print(f"Capture: {'SUCCESS' if capture_success else 'FAILED'}")
    print(f"Decode: {'SUCCESS' if decode_success else 'FAILED'}")
    if decode_result:
        print(f"Image: {decode_result['png_path']}")
    print("="*60 + "\n")
    
    return {
        'success': decode_success,
        'pass': selected_pass,
        'capture_file': capture_file,
        'decode_result': decode_result,
        'mission_record': mission_record
    }


def main():
    parser = argparse.ArgumentParser(
        description='Run a complete satellite capture mission',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_mission.py                    # Run next best pass
  python run_mission.py --satellite NOAA-18 # Capture specific satellite
  python run_mission.py --dry-run          # Show plan without executing
  python run_mission.py --min-el 30        # Only attempt high passes
  python run_mission.py --summary          # Show data store summary
"""
    )
    
    parser.add_argument('--satellite', '-s', type=str, default=None,
                        help='Target specific satellite (e.g., NOAA-18)')
    parser.add_argument('--min-el', type=float, default=20.0,
                        help='Minimum max elevation in degrees (default: 20)')
    parser.add_argument('--no-wait', action='store_true',
                        help='Exit if pass is not imminent (don\'t wait)')
    parser.add_argument('--skip-decode', action='store_true',
                        help='Skip decode step, just capture')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show plan but don\'t execute')
    parser.add_argument('--summary', action='store_true',
                        help='Print data store summary and exit')
    
    args = parser.parse_args()
    
    if args.summary:
        print_summary()
        return
    
    result = run_mission(
        satellite=args.satellite,
        min_elevation=args.min_el,
        wait=not args.no_wait,
        skip_decode=args.skip_decode,
        dry_run=args.dry_run
    )
    
    if result and result.get('success'):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
