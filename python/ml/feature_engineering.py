#!/usr/bin/env python3
"""
feature_engineering.py
Satellite Ground Station - ML Feature Engineering

Extracts features from pass data, weather, and historical performance
for use in ML prediction models.

Features:
    - Orbital: max elevation, duration, time of day, azimuth range
    - Weather: cloud cover, precipitation, temperature
    - Historical: recent success rate, satellite-specific performance
    - Hardware: gain setting, LNA status, antenna config

Author: Luke Waszyn
Date: February 2026
"""

import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from python.data_store import get_missions, get_recent_success_rate, get_satellite_stats


# Feature definitions
FEATURE_SCHEMA = {
    # Orbital features
    'max_elevation_deg': 'float',      # 0-90
    'duration_min': 'float',           # typically 5-15
    'aos_hour_utc': 'float',           # 0-24
    'aos_day_of_week': 'int',          # 0-6 (Monday=0)
    'azimuth_range_deg': 'float',      # arc swept across sky
    'is_morning_pass': 'int',          # 0 or 1
    'is_evening_pass': 'int',          # 0 or 1
    
    # Weather features
    'cloud_cover_pct': 'float',        # 0-100 (nullable)
    'precipitation_prob': 'float',     # 0-1 (nullable)
    'temperature_c': 'float',          # (nullable)
    'humidity_pct': 'float',           # 0-100 (nullable)
    
    # Historical features
    'recent_success_rate': 'float',    # 0-1, last N missions
    'satellite_success_rate': 'float', # 0-1, for this satellite
    'total_attempts': 'int',           # experience level
    'days_since_last_success': 'float',# recency
    
    # Hardware features
    'gain_db': 'float',                # SDR gain setting
    'using_lna': 'int',                # 0 or 1
    'antenna_type': 'str',             # 'dipole', 'qfh', etc.
}


def extract_orbital_features(pass_info: Dict) -> Dict:
    """
    Extract orbital features from pass information.
    
    Args:
        pass_info: Dictionary with aos_time, los_time, max_elevation, etc.
    
    Returns:
        Dictionary of orbital features
    """
    aos = pass_info.get('aos_time')
    los = pass_info.get('los_time')
    
    # Handle string timestamps
    if isinstance(aos, str):
        aos = datetime.fromisoformat(aos.replace('Z', '+00:00'))
    if isinstance(los, str):
        los = datetime.fromisoformat(los.replace('Z', '+00:00'))
    
    # Strip timezone for calculations
    if aos and hasattr(aos, 'replace'):
        aos = aos.replace(tzinfo=None)
    if los and hasattr(los, 'replace'):
        los = los.replace(tzinfo=None)
    
    duration_sec = (los - aos).total_seconds() if aos and los else 0
    
    # Determine pass timing
    aos_hour = aos.hour + aos.minute / 60.0 if aos else 12
    is_morning = 1 if 4 <= aos_hour < 12 else 0
    is_evening = 1 if 17 <= aos_hour < 22 else 0
    
    # Azimuth range
    aos_az = pass_info.get('aos_az', 0)
    los_az = pass_info.get('los_az', 0)
    az_range = abs(los_az - aos_az)
    if az_range > 180:
        az_range = 360 - az_range
    
    return {
        'max_elevation_deg': pass_info.get('max_elevation', 0),
        'duration_min': duration_sec / 60.0,
        'aos_hour_utc': aos_hour,
        'aos_day_of_week': aos.weekday() if aos else 0,
        'azimuth_range_deg': az_range,
        'is_morning_pass': is_morning,
        'is_evening_pass': is_evening,
    }


def extract_weather_features(weather: Optional[Dict] = None) -> Dict:
    """
    Extract weather features.
    
    Args:
        weather: Dictionary with cloud_cover, precipitation, temp, etc.
                 None if weather data unavailable.
    
    Returns:
        Dictionary of weather features (with None for missing values)
    """
    if weather is None:
        weather = {}
    
    return {
        'cloud_cover_pct': weather.get('cloud_cover_pct'),
        'precipitation_prob': weather.get('precipitation_prob'),
        'temperature_c': weather.get('temperature_c'),
        'humidity_pct': weather.get('humidity_pct'),
    }


def extract_historical_features(satellite: str = None) -> Dict:
    """
    Extract features from historical mission data.
    
    Args:
        satellite: Satellite name for satellite-specific stats
    
    Returns:
        Dictionary of historical features
    """
    # Recent overall success rate
    recent_rate = get_recent_success_rate(n_missions=10)
    
    # Satellite-specific stats
    sat_stats = get_satellite_stats()
    sat_rate = 0.5  # Default prior
    if satellite:
        for sat_name, stats in sat_stats.items():
            if satellite.upper() in sat_name.upper():
                sat_rate = stats.get('success_rate', 0.5)
                break
    
    # Total attempts (experience)
    all_missions = get_missions()
    total_attempts = len(all_missions)
    
    # Days since last success
    successful = get_missions(success_only=True, limit=1)
    if successful:
        last_success = datetime.fromisoformat(successful[0]['timestamp'])
        days_since = (datetime.utcnow() - last_success).days
    else:
        days_since = 999  # No successes yet
    
    return {
        'recent_success_rate': recent_rate,
        'satellite_success_rate': sat_rate,
        'total_attempts': total_attempts,
        'days_since_last_success': days_since,
    }


def extract_hardware_features(config: Optional[Dict] = None) -> Dict:
    """
    Extract hardware configuration features.
    
    Args:
        config: Dictionary with gain, lna, antenna settings
    
    Returns:
        Dictionary of hardware features
    """
    if config is None:
        config = {}
    
    return {
        'gain_db': config.get('gain_db', 40.0),
        'using_lna': 1 if config.get('using_lna', False) else 0,
        'antenna_type': config.get('antenna_type', 'dipole'),
    }


def extract_all_features(
    pass_info: Dict,
    weather: Optional[Dict] = None,
    config: Optional[Dict] = None
) -> Dict:
    """
    Extract complete feature set for a pass.
    
    Args:
        pass_info: Pass data from scheduler
        weather: Weather data (optional)
        config: Hardware config (optional)
    
    Returns:
        Dictionary containing all features
    """
    features = {}
    
    # Orbital
    features.update(extract_orbital_features(pass_info))
    
    # Weather
    features.update(extract_weather_features(weather))
    
    # Historical
    satellite = pass_info.get('satellite', '')
    features.update(extract_historical_features(satellite))
    
    # Hardware
    features.update(extract_hardware_features(config))
    
    # Add satellite as categorical
    features['satellite'] = satellite
    
    return features


def features_to_dataframe(features_list: List[Dict]) -> pd.DataFrame:
    """
    Convert list of feature dictionaries to DataFrame.
    
    Args:
        features_list: List of feature dictionaries
    
    Returns:
        pandas DataFrame ready for ML
    """
    df = pd.DataFrame(features_list)
    
    # Handle categorical encoding
    if 'antenna_type' in df.columns:
        df['antenna_type_dipole'] = (df['antenna_type'] == 'dipole').astype(int)
        df['antenna_type_qfh'] = (df['antenna_type'] == 'qfh').astype(int)
        df = df.drop(columns=['antenna_type'])
    
    if 'satellite' in df.columns:
        # One-hot encode satellite
        sat_dummies = pd.get_dummies(df['satellite'], prefix='sat')
        df = pd.concat([df.drop(columns=['satellite']), sat_dummies], axis=1)
    
    return df


def get_feature_names(include_categorical: bool = True) -> List[str]:
    """Get list of numeric feature names for model training."""
    numeric_features = [
        'max_elevation_deg',
        'duration_min',
        'aos_hour_utc',
        'aos_day_of_week',
        'azimuth_range_deg',
        'is_morning_pass',
        'is_evening_pass',
        'cloud_cover_pct',
        'precipitation_prob',
        'temperature_c',
        'humidity_pct',
        'recent_success_rate',
        'satellite_success_rate',
        'total_attempts',
        'days_since_last_success',
        'gain_db',
        'using_lna',
    ]
    
    if include_categorical:
        numeric_features.extend([
            'antenna_type_dipole',
            'antenna_type_qfh',
        ])
    
    return numeric_features


def impute_missing(df: pd.DataFrame) -> pd.DataFrame:
    """
    Impute missing values for ML.
    
    Strategy:
        - Weather features: median or reasonable defaults
        - Other features: should not be missing
    """
    df = df.copy()
    
    # Weather defaults (conservative/neutral values)
    if 'cloud_cover_pct' in df.columns:
        df['cloud_cover_pct'] = df['cloud_cover_pct'].fillna(50.0)
    if 'precipitation_prob' in df.columns:
        df['precipitation_prob'] = df['precipitation_prob'].fillna(0.2)
    if 'temperature_c' in df.columns:
        df['temperature_c'] = df['temperature_c'].fillna(15.0)
    if 'humidity_pct' in df.columns:
        df['humidity_pct'] = df['humidity_pct'].fillna(50.0)
    
    # Fill any remaining NaN with 0
    df = df.fillna(0)
    
    return df


if __name__ == "__main__":
    # Example usage
    print("Feature Engineering Module")
    print("=" * 40)
    
    # Example pass
    example_pass = {
        'satellite': 'NOAA 18',
        'aos_time': datetime(2026, 2, 12, 14, 30, 0),
        'los_time': datetime(2026, 2, 12, 14, 42, 0),
        'max_elevation': 65.0,
        'aos_az': 180,
        'los_az': 45,
    }
    
    features = extract_all_features(example_pass)
    
    print("\nExtracted features:")
    for key, val in features.items():
        print(f"  {key}: {val}")
    
    print("\nFeature names for ML:")
    for name in get_feature_names():
        print(f"  - {name}")
