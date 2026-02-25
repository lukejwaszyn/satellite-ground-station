#!/usr/bin/env python3
"""
generate_orbital_data.py
Satellite Ground Station - Orbital Data Generator for 3D Visualizer

Fetches real TLEs from Celestrak, propagates with SGP4 via Skyfield,
and exports satellite positions, pass predictions, and Doppler profiles
as JSON for the SATCOM 3D visualizer.

Tracks a mix of satellites for a full mission ops display:
  - NOAA 20 (primary imaging target)
  - NOAA 21, METEOR-M (weather constellation)
  - ISS, Landsat, Terra, Aqua (display)

Reuses patterns from:
  - predict_passes.py  (SGP4 propagation, pass detection, event grouping)
  - doppler_calc.py    (radial velocity, Doppler shift calculation)
  - schedule_captures.py (multi-satellite pass finding, TLE caching)

Usage:
    python generate_orbital_data.py
    python generate_orbital_data.py --hours 24 --step 30 -o orbital_data.json

Author: Luke Waszyn
Date: February 2026
"""

import json
import math
import argparse
import sys
import os
import time as time_module
from datetime import datetime, timedelta, timezone

try:
    from skyfield.api import load, wgs84
    import numpy as np
except ImportError as e:
    print(f"ERROR: Missing dependency: {e}")
    print("Install with:")
    print("  pip install skyfield numpy")
    sys.exit(1)


# =============================================================
# Ground Station — State College, PA
# Matches predict_passes.py and doppler_calc.py
# =============================================================
GS_LAT = 40.7934
GS_LON = -77.8600
GS_ELEV = 376.0
MIN_ELEVATION = 10.0

# Speed of light (m/s) — matches doppler_calc.py
C = 299792458.0

# =============================================================
# Satellite Catalog
#
# role:
#   'primary'  — imaging target (NOAA 20), gets Doppler profiles
#   'weather'  — other weather sats, gets Doppler profiles
#   'display'  — tracked for visualization only, no Doppler
#
# freq_hz:
#   Set for satellites with known downlink (used for Doppler calc).
#   None for display-only satellites.
#
# group:
#   Celestrak TLE group the satellite lives in.
#   Used to know which bulk file to fetch.
#   'individual' means fetch by NORAD ID directly.
# =============================================================
TRACKED_SATS = {
    # === Primary imaging target ===
    'NOAA 20': {
        'freq_hz': 137.1000e6,
        'color': '#34d399',
        'norad_id': 43013,
        'role': 'primary',
        'group': 'weather',
        'search_names': ['NOAA 20', 'NOAA-20', 'JPSS-1'],
    },

    # === Weather constellation ===
    'NOAA 21': {
        'freq_hz': 137.1000e6,
        'color': '#2dd4bf',
        'norad_id': 54234,
        'role': 'weather',
        'group': 'weather',
        'search_names': ['NOAA 21', 'NOAA-21', 'JPSS-2'],
    },
    'NOAA 18': {
        'freq_hz': 137.9125e6,
        'color': '#38bdf8',
        'norad_id': 28654,
        'role': 'weather',
        'group': 'individual',
        'search_names': ['NOAA 18', 'NOAA-18'],
    },
    'NOAA 19': {
        'freq_hz': 137.1000e6,
        'color': '#a78bfa',
        'norad_id': 33591,
        'role': 'weather',
        'group': 'individual',
        'search_names': ['NOAA 19', 'NOAA-19'],
    },
    'NOAA 15': {
        'freq_hz': 137.6200e6,
        'color': '#f472b6',
        'norad_id': 25338,
        'role': 'weather',
        'group': 'individual',
        'search_names': ['NOAA 15', 'NOAA-15'],
    },
    'METEOR-M2 3': {
        'freq_hz': 137.9000e6,
        'color': '#fb923c',
        'norad_id': 57166,
        'role': 'weather',
        'group': 'weather',
        'search_names': ['METEOR-M2 3', 'METEOR-M 2-3', 'METEOR M2-3'],
    },
    'METEOR-M2 4': {
        'freq_hz': 137.1000e6,
        'color': '#f97316',
        'norad_id': 59051,
        'role': 'weather',
        'group': 'weather',
        'search_names': ['METEOR-M2 4', 'METEOR-M 2-4', 'METEOR M2-4'],
    },

    # === Display satellites ===
    'ISS': {
        'freq_hz': None,
        'color': '#fbbf24',
        'norad_id': 25544,
        'role': 'display',
        'group': 'stations',
        'search_names': ['ISS (ZARYA)', 'ISS', 'ZARYA'],
    },
    'TERRA': {
        'freq_hz': None,
        'color': '#94a3b8',
        'norad_id': 25994,
        'role': 'display',
        'group': 'resource',
        'search_names': ['TERRA'],
    },
    'AQUA': {
        'freq_hz': None,
        'color': '#67e8f9',
        'norad_id': 27424,
        'role': 'display',
        'group': 'resource',
        'search_names': ['AQUA'],
    },
    'LANDSAT 9': {
        'freq_hz': None,
        'color': '#86efac',
        'norad_id': 49260,
        'role': 'display',
        'group': 'resource',
        'search_names': ['LANDSAT 9'],
    },
}

# Celestrak group URLs
CELESTRAK_GROUPS = {
    'weather':  'https://celestrak.org/NORAD/elements/gp.php?GROUP=weather&FORMAT=tle',
    'stations': 'https://celestrak.org/NORAD/elements/gp.php?GROUP=stations&FORMAT=tle',
    'resource': 'https://celestrak.org/NORAD/elements/gp.php?GROUP=resource&FORMAT=tle',
    'noaa':     'https://celestrak.org/NORAD/elements/gp.php?GROUP=noaa&FORMAT=tle',
}
INDIVIDUAL_URL = 'https://celestrak.org/NORAD/elements/gp.php?CATNR={}&FORMAT=tle'


def fetch_tles(tle_dir='.', max_age_hours=24):
    """
    Fetch TLEs from multiple Celestrak groups plus individual lookups.
    Returns matched satellites and Skyfield timescale.
    """
    ts = load.timescale()
    all_sats = []

    # Determine which groups we need
    needed_groups = set()
    for info in TRACKED_SATS.values():
        if info['group'] != 'individual':
            needed_groups.add(info['group'])

    # Fetch each group
    for group_name in sorted(needed_groups):
        url = CELESTRAK_GROUPS.get(group_name)
        if not url:
            continue

        cache_file = os.path.join(tle_dir, f'tle_{group_name}.txt')
        need_fetch = True

        if os.path.exists(cache_file):
            age_sec = time_module.time() - os.path.getmtime(cache_file)
            if age_sec < max_age_hours * 3600:
                need_fetch = False

        if need_fetch:
            print(f"[TLE] Fetching '{group_name}' group...")
            try:
                sats = load.tle_file(url, filename=cache_file, reload=True)
                all_sats.extend(sats)
                print(f"[TLE]   {len(sats)} satellites")
            except Exception as e:
                print(f"[TLE]   Fetch failed: {e}")
                if os.path.exists(cache_file):
                    all_sats.extend(load.tle_file(cache_file))
        else:
            sats = load.tle_file(cache_file)
            all_sats.extend(sats)
            print(f"[TLE] Cached '{group_name}' group ({len(sats)} sats)")

    # Fetch individual satellites not found in any group
    seen_norad = {sat.model.satnum for sat in all_sats}
    for sat_name, info in TRACKED_SATS.items():
        if info['group'] == 'individual' or info['norad_id'] not in seen_norad:
            cache_file = os.path.join(tle_dir, f"tle_{info['norad_id']}.txt")
            need_fetch = True

            if os.path.exists(cache_file):
                age_sec = time_module.time() - os.path.getmtime(cache_file)
                if age_sec < max_age_hours * 3600:
                    need_fetch = False

            if need_fetch:
                print(f"[TLE] Fetching {sat_name} (NORAD {info['norad_id']})...")
                try:
                    url = INDIVIDUAL_URL.format(info['norad_id'])
                    ind_sats = load.tle_file(url, filename=cache_file, reload=True)
                    all_sats.extend(ind_sats)
                    print(f"[TLE]   OK")
                except Exception as e:
                    print(f"[TLE]   Failed: {e}")
                    if os.path.exists(cache_file):
                        all_sats.extend(load.tle_file(cache_file))
            else:
                ind_sats = load.tle_file(cache_file)
                all_sats.extend(ind_sats)

    # Match satellites
    by_number = {sat.model.satnum: sat for sat in all_sats}
    by_name = {sat.name: sat for sat in all_sats}

    def normalize(s):
        return s.upper().replace('-', ' ').replace('[', '').replace(']', '').replace('(', '').replace(')', '').strip()

    matched = {}
    for display_name, info in TRACKED_SATS.items():
        # Strategy 1: NORAD ID
        if info['norad_id'] in by_number:
            sat = by_number[info['norad_id']]
            matched[display_name] = sat
            epoch_str = sat.epoch.utc_strftime('%Y-%m-%d %H:%M')
            print(f"[TLE] Matched: {display_name} -> {sat.name} (NORAD {info['norad_id']}, epoch: {epoch_str})")
            continue

        # Strategy 2: Name matching
        found = False
        for search_name in info.get('search_names', []):
            norm_search = normalize(search_name)
            for tle_name, sat in by_name.items():
                if norm_search in normalize(tle_name):
                    matched[display_name] = sat
                    epoch_str = sat.epoch.utc_strftime('%Y-%m-%d %H:%M')
                    print(f"[TLE] Matched: {display_name} -> {sat.name} (name, epoch: {epoch_str})")
                    found = True
                    break
            if found:
                break

        if not found:
            print(f"[TLE] WARNING: Could not match {display_name} (NORAD {info['norad_id']})")

    print(f"[TLE] Matched {len(matched)}/{len(TRACKED_SATS)} satellites")

    if not matched:
        print("[TLE] ERROR: No satellites matched")
        sys.exit(1)

    return matched, ts


def propagate_positions(satellite, ts, observer, t_start_tt, duration_hours, step_seconds):
    """
    Propagate satellite. Returns position samples for 3D rendering.
    """
    num_steps = int(duration_hours * 3600 / step_seconds) + 1
    positions = []

    for i in range(num_steps):
        offset_days = (i * step_seconds) / 86400.0
        t = ts.tt_jd(t_start_tt + offset_days)

        geocentric = satellite.at(t)
        pos_km = geocentric.position.km

        subpoint = wgs84.subpoint(geocentric)
        lat = subpoint.latitude.degrees
        lon = subpoint.longitude.degrees
        alt_km = subpoint.elevation.km

        difference = satellite - observer
        topocentric = difference.at(t)
        topo_alt, topo_az, topo_range = topocentric.altaz()

        positions.append({
            'ts': round(i * step_seconds, 1),
            'ecef': [round(float(pos_km[0]), 2),
                     round(float(pos_km[1]), 2),
                     round(float(pos_km[2]), 2)],
            'lat': round(float(lat), 4),
            'lon': round(float(lon), 4),
            'alt_km': round(float(alt_km), 1),
            'el': round(float(topo_alt.degrees), 2),
            'az': round(float(topo_az.degrees), 2),
            'range_km': round(float(topo_range.km), 1),
        })

    return positions


def find_passes(satellite, sat_name, ts, observer, t_start_tt, duration_hours, freq_hz=None):
    """
    Find passes above MIN_ELEVATION. Includes Doppler if freq_hz is set.
    """
    t0 = ts.tt_jd(t_start_tt)
    t1 = ts.tt_jd(t_start_tt + duration_hours / 24.0)

    try:
        t_events, events = satellite.find_events(
            observer, t0, t1, altitude_degrees=MIN_ELEVATION
        )
    except Exception as e:
        print(f"  [WARN] find_events failed for {sat_name}: {e}")
        return []

    passes = []
    current_pass = {}

    for ti, event in zip(t_events, events):
        difference = satellite - observer
        topocentric = difference.at(ti)
        alt, az, dist = topocentric.altaz()

        if event == 0:  # AOS
            current_pass = {
                'aos_utc': ti.utc_datetime().isoformat(),
                'aos_az': round(float(az.degrees), 1),
                'aos_unix': round(ti.utc_datetime().timestamp(), 1),
            }
        elif event == 1:  # TCA
            if current_pass:
                current_pass['tca_utc'] = ti.utc_datetime().isoformat()
                current_pass['max_el'] = round(float(alt.degrees), 1)
                current_pass['tca_az'] = round(float(az.degrees), 1)
                current_pass['tca_range_km'] = round(float(dist.km), 1)
                current_pass['tca_unix'] = round(ti.utc_datetime().timestamp(), 1)
        elif event == 2:  # LOS
            if current_pass and 'max_el' in current_pass:
                current_pass['los_utc'] = ti.utc_datetime().isoformat()
                current_pass['los_az'] = round(float(az.degrees), 1)
                current_pass['los_unix'] = round(ti.utc_datetime().timestamp(), 1)

                aos_dt = datetime.fromisoformat(current_pass['aos_utc'])
                los_dt = datetime.fromisoformat(current_pass['los_utc'])
                current_pass['duration_sec'] = round(
                    (los_dt - aos_dt).total_seconds(), 1
                )

                # Doppler only for satellites with known frequency
                if freq_hz:
                    current_pass['doppler'] = compute_doppler_for_pass(
                        satellite, observer, ts, aos_dt, los_dt, freq_hz
                    )
                else:
                    current_pass['doppler'] = None

                passes.append(current_pass)
            current_pass = {}

    return passes


def compute_doppler_for_pass(satellite, observer, ts, aos_dt, los_dt,
                             center_freq_hz, time_step_sec=5.0):
    """
    Doppler shift profile for a pass. Mirrors doppler_calc.py exactly.
    """
    duration_sec = (los_dt - aos_dt).total_seconds()
    num_points = int(duration_sec / time_step_sec) + 1

    times_sec = []
    doppler_hz = []
    elevations = []

    for i in range(num_points):
        dt = aos_dt + timedelta(seconds=i * time_step_sec)
        t = ts.utc(dt.year, dt.month, dt.day,
                    dt.hour, dt.minute, dt.second + dt.microsecond / 1e6)

        difference = satellite - observer
        topocentric = difference.at(t)
        alt, az, distance = topocentric.altaz()

        pos = topocentric.position.km
        vel = topocentric.velocity.km_per_s

        range_km = float(np.linalg.norm(pos))
        if range_km > 0:
            range_unit = pos / range_km
            v_radial_m_s = float(np.dot(vel, range_unit)) * 1000.0
            doppler = -center_freq_hz * (v_radial_m_s / C)
        else:
            doppler = 0.0

        times_sec.append(round(i * time_step_sec, 1))
        doppler_hz.append(round(doppler, 1))
        elevations.append(round(float(alt.degrees), 2))

    return {
        'times_sec': times_sec,
        'doppler_hz': doppler_hz,
        'elevations_deg': elevations,
        'max_doppler_hz': round(max(doppler_hz), 1) if doppler_hz else 0,
        'min_doppler_hz': round(min(doppler_hz), 1) if doppler_hz else 0,
    }


def generate_data(duration_hours=24, position_step_sec=30, output_path='orbital_data.json'):
    """
    Main pipeline: TLE fetch -> propagation -> pass finding -> JSON export.
    """
    print("=" * 60)
    print("SATCOM - Orbital Data Generator")
    print("=" * 60)
    print(f"Ground Station: State College, PA")
    print(f"  Lat: {GS_LAT} N  Lon: {GS_LON} E  Elev: {GS_ELEV}m")
    print(f"Duration: {duration_hours} hours")
    print(f"Position step: {position_step_sec} seconds")
    print(f"Min elevation: {MIN_ELEVATION} deg")
    print(f"Satellites: {len(TRACKED_SATS)}")
    print()

    matched_sats, ts = fetch_tles()
    observer = wgs84.latlon(GS_LAT, GS_LON, elevation_m=GS_ELEV)

    t_now = ts.now()
    t_start_tt = t_now.tt
    generation_time = t_now.utc_datetime()

    print(f"\n[TIME] Now: {generation_time.isoformat()}")
    print(f"[TIME] Window: now -> +{duration_hours}h\n")

    satellites_data = {}

    for sat_name, sat_info in TRACKED_SATS.items():
        if sat_name not in matched_sats:
            print(f"[{sat_name}] Skipping - not in TLE data")
            continue

        satellite = matched_sats[sat_name]
        print(f"[{sat_name}] Propagating...")

        positions = propagate_positions(
            satellite, ts, observer,
            t_start_tt, duration_hours, position_step_sec
        )
        print(f"  {len(positions)} position samples")

        print(f"[{sat_name}] Finding passes...")
        passes = find_passes(
            satellite, sat_name, ts, observer,
            t_start_tt, duration_hours,
            freq_hz=sat_info['freq_hz']
        )
        print(f"  {len(passes)} passes")

        for i, p in enumerate(passes):
            dop_str = ""
            if p.get('doppler'):
                dop_str = (f" | Doppler: {p['doppler']['min_doppler_hz']:.0f} to "
                           f"+{p['doppler']['max_doppler_hz']:.0f} Hz")
            print(f"    Pass {i+1}: {p['aos_utc'][:16]} -> {p['los_utc'][11:16]} "
                  f"| Max El: {p['max_el']} deg | Dur: {p['duration_sec']/60:.1f}min{dop_str}")

        inc = satellite.model.inclo * 180.0 / math.pi
        period_min = 2.0 * math.pi / satellite.model.no_kozai

        satellites_data[sat_name] = {
            'name': sat_name,
            'tle_name': satellite.name,
            'norad_id': satellite.model.satnum,
            'freq_hz': sat_info['freq_hz'],
            'freq_mhz': round(sat_info['freq_hz'] / 1e6, 4) if sat_info['freq_hz'] else None,
            'color': sat_info['color'],
            'role': sat_info['role'],
            'epoch': satellite.epoch.utc_datetime().isoformat(),
            'inclination_deg': round(inc, 2),
            'period_min': round(period_min, 2),
            'positions': positions,
            'passes': passes,
        }

    output = {
        'generated_utc': generation_time.isoformat(),
        'generated_unix': round(generation_time.timestamp(), 1),
        'duration_hours': duration_hours,
        'position_step_sec': position_step_sec,
        'ground_station': {
            'name': 'State College, PA',
            'lat': GS_LAT,
            'lon': GS_LON,
            'elevation_m': GS_ELEV,
            'min_elevation_deg': MIN_ELEVATION,
        },
        'satellites': satellites_data,
    }

    total_passes = sum(len(s['passes']) for s in satellites_data.values())
    total_positions = sum(len(s['positions']) for s in satellites_data.values())

    # Summary by role
    by_role = {}
    for s in satellites_data.values():
        r = s['role']
        by_role[r] = by_role.get(r, 0) + 1

    print(f"\n{'='*60}")
    print(f"Summary: {len(satellites_data)} satellites, {total_passes} passes, "
          f"{total_positions} position samples")
    for role, count in sorted(by_role.items()):
        print(f"  {role}: {count} sats")

    with open(output_path, 'w') as f:
        json.dump(output, f, separators=(',', ':'))

    file_size_kb = os.path.getsize(output_path) / 1024
    print(f"Output: {output_path} ({file_size_kb:.0f} KB)")
    print("=" * 60)

    return output


def main():
    parser = argparse.ArgumentParser(
        description='Generate orbital data for SATCOM 3D visualizer',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python generate_orbital_data.py                        # 24h, 30s steps
  python generate_orbital_data.py --hours 48 --step 60   # 48h, 1-min steps
  python generate_orbital_data.py -o viz_data.json       # Custom output
"""
    )
    parser.add_argument('--hours', type=float, default=24,
                        help='Prediction window in hours (default: 24)')
    parser.add_argument('--step', type=float, default=30,
                        help='Position sample interval in seconds (default: 30)')
    parser.add_argument('--output', '-o', type=str, default='orbital_data.json',
                        help='Output JSON path (default: orbital_data.json)')

    args = parser.parse_args()
    generate_data(
        duration_hours=args.hours,
        position_step_sec=args.step,
        output_path=args.output,
    )


if __name__ == '__main__':
    main()
