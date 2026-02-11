#!/usr/bin/env python3
"""
data_store.py
Satellite Ground Station - Mission Data Store

Handles storage and retrieval of mission data for:
- Mission logs (capture attempts, outcomes)
- Performance metrics (SNR, sync rate, decode success)
- ML training data (features + labels)

Storage format: JSON for simplicity, easily migrated to SQLite later.

Author: Luke Waszyn
Date: February 2026
"""

import os
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import statistics


# Default data directory
DATA_DIR = Path('data')
MISSIONS_FILE = DATA_DIR / 'missions.json'
METRICS_FILE = DATA_DIR / 'metrics.json'
ML_FEATURES_FILE = DATA_DIR / 'ml' / 'training_data.json'


def ensure_data_dirs():
    """Create data directories if they don't exist."""
    DATA_DIR.mkdir(exist_ok=True)
    (DATA_DIR / 'ml').mkdir(exist_ok=True)
    (DATA_DIR / 'captures').mkdir(exist_ok=True)
    (DATA_DIR / 'decoded').mkdir(exist_ok=True)
    (DATA_DIR / 'doppler').mkdir(exist_ok=True)


def _load_json(filepath: Path) -> List[Dict]:
    """Load JSON file, return empty list if doesn't exist."""
    if filepath.exists():
        with open(filepath, 'r') as f:
            return json.load(f)
    return []


def _save_json(filepath: Path, data: List[Dict]):
    """Save data to JSON file."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2, default=str)


# ============================================================
# MISSION LOGGING
# ============================================================

def log_mission(
    satellite: str,
    aos_time: datetime,
    los_time: datetime,
    max_elevation: float,
    capture_success: bool,
    decode_success: bool,
    capture_file: Optional[str] = None,
    image_file: Optional[str] = None,
    snr_db: Optional[float] = None,
    sync_pulses_found: Optional[int] = None,
    weather: Optional[Dict] = None,
    notes: Optional[str] = None
) -> Dict:
    """
    Log a mission attempt.
    
    Returns the mission record.
    """
    ensure_data_dirs()
    
    mission = {
        'id': datetime.utcnow().strftime('%Y%m%d_%H%M%S'),
        'timestamp': datetime.utcnow().isoformat(),
        'satellite': satellite,
        'aos_utc': aos_time.isoformat() if isinstance(aos_time, datetime) else aos_time,
        'los_utc': los_time.isoformat() if isinstance(los_time, datetime) else los_time,
        'duration_sec': (los_time - aos_time).total_seconds() if isinstance(aos_time, datetime) else None,
        'max_elevation_deg': max_elevation,
        'capture_success': capture_success,
        'decode_success': decode_success,
        'capture_file': capture_file,
        'image_file': image_file,
        'snr_db': snr_db,
        'sync_pulses_found': sync_pulses_found,
        'weather': weather,
        'notes': notes
    }
    
    missions = _load_json(MISSIONS_FILE)
    missions.append(mission)
    _save_json(MISSIONS_FILE, missions)
    
    print(f"Mission logged: {mission['id']}")
    return mission


def get_missions(
    satellite: Optional[str] = None,
    success_only: bool = False,
    limit: Optional[int] = None
) -> List[Dict]:
    """
    Retrieve mission records.
    
    Args:
        satellite: Filter by satellite name
        success_only: Only return successful decodes
        limit: Maximum number of records to return
    
    Returns:
        List of mission dictionaries
    """
    missions = _load_json(MISSIONS_FILE)
    
    if satellite:
        missions = [m for m in missions if satellite.upper() in m['satellite'].upper()]
    
    if success_only:
        missions = [m for m in missions if m['decode_success']]
    
    # Sort by timestamp descending (most recent first)
    missions.sort(key=lambda m: m['timestamp'], reverse=True)
    
    if limit:
        missions = missions[:limit]
    
    return missions


def get_mission_count() -> Dict[str, int]:
    """Get count of missions by outcome."""
    missions = _load_json(MISSIONS_FILE)
    
    return {
        'total': len(missions),
        'capture_success': sum(1 for m in missions if m['capture_success']),
        'decode_success': sum(1 for m in missions if m['decode_success']),
        'capture_failed': sum(1 for m in missions if not m['capture_success']),
        'decode_failed': sum(1 for m in missions if m['capture_success'] and not m['decode_success'])
    }


# ============================================================
# PERFORMANCE METRICS
# ============================================================

def log_metrics(
    mission_id: str,
    snr_db: float,
    noise_floor_db: float,
    peak_signal_db: float,
    sync_rate: float,
    image_quality_score: Optional[float] = None,
    doppler_error_hz: Optional[float] = None
) -> Dict:
    """
    Log performance metrics for a mission.
    """
    ensure_data_dirs()
    
    metrics = {
        'mission_id': mission_id,
        'timestamp': datetime.utcnow().isoformat(),
        'snr_db': snr_db,
        'noise_floor_db': noise_floor_db,
        'peak_signal_db': peak_signal_db,
        'sync_rate': sync_rate,
        'image_quality_score': image_quality_score,
        'doppler_error_hz': doppler_error_hz
    }
    
    all_metrics = _load_json(METRICS_FILE)
    all_metrics.append(metrics)
    _save_json(METRICS_FILE, all_metrics)
    
    return metrics


def get_metrics_summary() -> Dict:
    """Get summary statistics of performance metrics."""
    all_metrics = _load_json(METRICS_FILE)
    
    if not all_metrics:
        return {'count': 0}
    
    snr_values = [m['snr_db'] for m in all_metrics if m['snr_db'] is not None]
    sync_values = [m['sync_rate'] for m in all_metrics if m['sync_rate'] is not None]
    
    summary = {
        'count': len(all_metrics),
    }
    
    if snr_values:
        summary['snr_mean'] = statistics.mean(snr_values)
        summary['snr_std'] = statistics.stdev(snr_values) if len(snr_values) > 1 else 0
        summary['snr_min'] = min(snr_values)
        summary['snr_max'] = max(snr_values)
    
    if sync_values:
        summary['sync_rate_mean'] = statistics.mean(sync_values)
        summary['sync_rate_std'] = statistics.stdev(sync_values) if len(sync_values) > 1 else 0
    
    return summary


# ============================================================
# ML TRAINING DATA
# ============================================================

def log_training_sample(
    # Features
    satellite: str,
    max_elevation_deg: float,
    duration_min: float,
    time_of_day_hour: float,
    day_of_week: int,
    cloud_cover_pct: Optional[float] = None,
    precipitation_prob: Optional[float] = None,
    temperature_c: Optional[float] = None,
    gain_db: float = 40.0,
    antenna_type: str = 'dipole',
    using_lna: bool = False,
    
    # Labels (outcomes)
    decode_success: bool = False,
    snr_db: Optional[float] = None,
    sync_rate: Optional[float] = None,
    image_quality: Optional[float] = None
) -> Dict:
    """
    Log a training sample for ML model.
    
    Features are inputs, labels are outcomes to predict.
    """
    ensure_data_dirs()
    
    sample = {
        'id': datetime.utcnow().strftime('%Y%m%d_%H%M%S'),
        'timestamp': datetime.utcnow().isoformat(),
        
        # Features
        'features': {
            'satellite': satellite,
            'max_elevation_deg': max_elevation_deg,
            'duration_min': duration_min,
            'time_of_day_hour': time_of_day_hour,
            'day_of_week': day_of_week,
            'cloud_cover_pct': cloud_cover_pct,
            'precipitation_prob': precipitation_prob,
            'temperature_c': temperature_c,
            'gain_db': gain_db,
            'antenna_type': antenna_type,
            'using_lna': using_lna
        },
        
        # Labels
        'labels': {
            'decode_success': decode_success,
            'snr_db': snr_db,
            'sync_rate': sync_rate,
            'image_quality': image_quality
        }
    }
    
    samples = _load_json(ML_FEATURES_FILE)
    samples.append(sample)
    _save_json(ML_FEATURES_FILE, samples)
    
    return sample


def get_training_data() -> List[Dict]:
    """Get all training samples for ML."""
    return _load_json(ML_FEATURES_FILE)


def get_training_dataframe():
    """
    Get training data as pandas DataFrame.
    
    Returns features (X) and labels (y) ready for sklearn.
    """
    try:
        import pandas as pd
    except ImportError:
        raise ImportError("pandas required: pip install pandas")
    
    samples = get_training_data()
    
    if not samples:
        return None, None
    
    # Flatten features and labels
    records = []
    for s in samples:
        record = {**s['features'], **s['labels']}
        records.append(record)
    
    df = pd.DataFrame(records)
    
    # Separate features and labels
    label_cols = ['decode_success', 'snr_db', 'sync_rate', 'image_quality']
    feature_cols = [c for c in df.columns if c not in label_cols]
    
    X = df[feature_cols]
    y = df[label_cols]
    
    return X, y


# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def get_recent_success_rate(n_missions: int = 10) -> float:
    """Get success rate of last N missions."""
    missions = get_missions(limit=n_missions)
    
    if not missions:
        return 0.0
    
    successes = sum(1 for m in missions if m['decode_success'])
    return successes / len(missions)


def get_satellite_stats() -> Dict[str, Dict]:
    """Get statistics by satellite."""
    missions = _load_json(MISSIONS_FILE)
    
    stats = {}
    for m in missions:
        sat = m['satellite']
        if sat not in stats:
            stats[sat] = {'attempts': 0, 'successes': 0, 'total_snr': 0, 'snr_count': 0}
        
        stats[sat]['attempts'] += 1
        if m['decode_success']:
            stats[sat]['successes'] += 1
        if m.get('snr_db'):
            stats[sat]['total_snr'] += m['snr_db']
            stats[sat]['snr_count'] += 1
    
    # Calculate rates and averages
    for sat in stats:
        s = stats[sat]
        s['success_rate'] = s['successes'] / s['attempts'] if s['attempts'] > 0 else 0
        s['avg_snr'] = s['total_snr'] / s['snr_count'] if s['snr_count'] > 0 else None
        del s['total_snr']
        del s['snr_count']
    
    return stats


def print_summary():
    """Print summary of all data."""
    counts = get_mission_count()
    metrics = get_metrics_summary()
    sat_stats = get_satellite_stats()
    training_count = len(get_training_data())
    
    print("\n" + "="*60)
    print("DATA STORE SUMMARY")
    print("="*60)
    
    print(f"\nMissions:")
    print(f"  Total attempts: {counts['total']}")
    print(f"  Capture success: {counts['capture_success']}")
    print(f"  Decode success: {counts['decode_success']}")
    
    if counts['total'] > 0:
        rate = counts['decode_success'] / counts['total'] * 100
        print(f"  Overall success rate: {rate:.1f}%")
    
    if metrics.get('count', 0) > 0:
        print(f"\nPerformance Metrics:")
        print(f"  Samples: {metrics['count']}")
        if 'snr_mean' in metrics:
            print(f"  SNR: {metrics['snr_mean']:.1f} ± {metrics['snr_std']:.1f} dB")
        if 'sync_rate_mean' in metrics:
            print(f"  Sync rate: {metrics['sync_rate_mean']:.2f} ± {metrics['sync_rate_std']:.2f}")
    
    if sat_stats:
        print(f"\nBy Satellite:")
        for sat, s in sat_stats.items():
            print(f"  {sat}: {s['successes']}/{s['attempts']} ({s['success_rate']*100:.0f}%)")
    
    print(f"\nML Training Samples: {training_count}")
    
    print("="*60)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'summary':
        print_summary()
    else:
        print("Usage: python data_store.py summary")
        print("\nThis module is primarily used as a library.")
        print("Import and use: log_mission(), get_missions(), log_training_sample(), etc.")
