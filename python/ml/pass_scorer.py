#!/usr/bin/env python3
"""
pass_scorer.py
Satellite Ground Station - Rule-Based Pass Scoring

Scores satellite passes using deterministic rules.
This serves as the baseline before ML models are trained.

Scoring Algorithm:
    - Elevation: 50% weight (higher = better signal)
    - Duration: 20% weight (longer = more data)
    - Weather: 20% weight (clear = better)
    - Time diversity: 10% weight (prefer variety)

Score range: 0.0 to 1.0

Author: Luke Waszyn
Date: February 2026
"""

import sys
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from python.ml.feature_engineering import extract_all_features


# Scoring weights
WEIGHTS = {
    'elevation': 0.50,
    'duration': 0.20,
    'weather': 0.20,
    'time_diversity': 0.10,
}

# Thresholds
MIN_ELEVATION_DEG = 15      # Below this, don't attempt
MAX_ELEVATION_DEG = 90      # Perfect elevation
MIN_DURATION_MIN = 5        # Below this, probably not worth it
MAX_DURATION_MIN = 15       # Typical max for good pass
CLOUD_THRESHOLD_PCT = 80    # Above this, significant degradation


def score_elevation(max_elevation_deg: float) -> float:
    """
    Score based on maximum elevation.
    
    Higher elevation = stronger signal = better score.
    
    Returns: 0.0 to 1.0
    """
    if max_elevation_deg < MIN_ELEVATION_DEG:
        return 0.0
    
    if max_elevation_deg >= MAX_ELEVATION_DEG:
        return 1.0
    
    # Linear scaling between min and max
    return (max_elevation_deg - MIN_ELEVATION_DEG) / (MAX_ELEVATION_DEG - MIN_ELEVATION_DEG)


def score_duration(duration_min: float) -> float:
    """
    Score based on pass duration.
    
    Longer passes capture more image data.
    
    Returns: 0.0 to 1.0
    """
    if duration_min < MIN_DURATION_MIN:
        return 0.2  # Short but not zero
    
    if duration_min >= MAX_DURATION_MIN:
        return 1.0
    
    # Linear scaling
    return (duration_min - MIN_DURATION_MIN) / (MAX_DURATION_MIN - MIN_DURATION_MIN)


def score_weather(cloud_cover_pct: Optional[float] = None,
                  precipitation_prob: Optional[float] = None) -> float:
    """
    Score based on weather conditions.
    
    Note: Weather affects RF propagation minimally at VHF,
    but heavy rain can cause issues. This is more about
    operational conditions (can you be outside with equipment).
    
    Returns: 0.0 to 1.0
    """
    # If no weather data, assume moderate conditions
    if cloud_cover_pct is None and precipitation_prob is None:
        return 0.6
    
    score = 1.0
    
    # Cloud cover penalty (minor effect on RF)
    if cloud_cover_pct is not None:
        if cloud_cover_pct > CLOUD_THRESHOLD_PCT:
            score -= 0.2
        elif cloud_cover_pct > 50:
            score -= 0.1
    
    # Precipitation penalty (more significant)
    if precipitation_prob is not None:
        if precipitation_prob > 0.7:
            score -= 0.4  # Likely rain, hard to operate
        elif precipitation_prob > 0.4:
            score -= 0.2
        elif precipitation_prob > 0.2:
            score -= 0.1
    
    return max(0.0, score)


def score_time_diversity(aos_hour_utc: float, 
                         recent_passes: Optional[List[Dict]] = None) -> float:
    """
    Score based on time diversity.
    
    Prefer passes at different times than recent captures
    to get variety in training data.
    
    Returns: 0.0 to 1.0
    """
    if recent_passes is None or len(recent_passes) == 0:
        return 0.8  # No history, neutral score
    
    # Check if we've captured at similar times recently
    for recent in recent_passes[-5:]:  # Last 5 passes
        recent_hour = None
        if 'aos_time' in recent:
            aos = recent['aos_time']
            if isinstance(aos, str):
                aos = datetime.fromisoformat(aos.replace('Z', '+00:00'))
            if hasattr(aos, 'hour'):
                recent_hour = aos.hour
        
        if recent_hour is not None:
            hour_diff = abs(aos_hour_utc - recent_hour)
            if hour_diff > 12:
                hour_diff = 24 - hour_diff
            
            # If very similar time, reduce score
            if hour_diff < 2:
                return 0.4
            elif hour_diff < 4:
                return 0.7
    
    return 1.0


def score_pass(pass_info: Dict,
               weather: Optional[Dict] = None,
               recent_passes: Optional[List[Dict]] = None) -> Tuple[float, Dict]:
    """
    Calculate overall score for a satellite pass.
    
    Args:
        pass_info: Pass data with elevation, duration, times
        weather: Weather data (optional)
        recent_passes: Recent capture history (optional)
    
    Returns:
        Tuple of (score, breakdown)
        - score: 0.0 to 1.0
        - breakdown: Dict with component scores
    """
    # Extract features
    features = extract_all_features(pass_info, weather)
    
    # Component scores
    el_score = score_elevation(features['max_elevation_deg'])
    dur_score = score_duration(features['duration_min'])
    wx_score = score_weather(
        features.get('cloud_cover_pct'),
        features.get('precipitation_prob')
    )
    div_score = score_time_diversity(
        features['aos_hour_utc'],
        recent_passes
    )
    
    # Weighted combination
    total_score = (
        WEIGHTS['elevation'] * el_score +
        WEIGHTS['duration'] * dur_score +
        WEIGHTS['weather'] * wx_score +
        WEIGHTS['time_diversity'] * div_score
    )
    
    breakdown = {
        'elevation_score': el_score,
        'duration_score': dur_score,
        'weather_score': wx_score,
        'time_diversity_score': div_score,
        'weights': WEIGHTS,
        'total_score': total_score,
    }
    
    return total_score, breakdown


def rank_passes(passes: List[Dict],
                weather: Optional[Dict] = None,
                recent_passes: Optional[List[Dict]] = None) -> List[Tuple[Dict, float, Dict]]:
    """
    Rank a list of passes by score.
    
    Args:
        passes: List of pass dictionaries
        weather: Weather data (applied to all)
        recent_passes: Recent capture history
    
    Returns:
        List of (pass_info, score, breakdown) tuples, sorted by score descending
    """
    scored = []
    
    for p in passes:
        score, breakdown = score_pass(p, weather, recent_passes)
        scored.append((p, score, breakdown))
    
    # Sort by score descending
    scored.sort(key=lambda x: x[1], reverse=True)
    
    return scored


def filter_passes(passes: List[Dict],
                  min_score: float = 0.3,
                  min_elevation: float = 15.0) -> List[Dict]:
    """
    Filter passes by minimum criteria.
    
    Args:
        passes: List of pass dictionaries
        min_score: Minimum score threshold
        min_elevation: Minimum max elevation
    
    Returns:
        Filtered list of passes
    """
    filtered = []
    
    for p in passes:
        # Elevation filter
        if p.get('max_elevation', 0) < min_elevation:
            continue
        
        # Score filter
        score, _ = score_pass(p)
        if score < min_score:
            continue
        
        filtered.append(p)
    
    return filtered


def recommend_pass(passes: List[Dict],
                   weather: Optional[Dict] = None,
                   recent_passes: Optional[List[Dict]] = None) -> Optional[Dict]:
    """
    Recommend the best pass to capture.
    
    Args:
        passes: List of upcoming passes
        weather: Current weather data
        recent_passes: Recent capture history
    
    Returns:
        Best pass dictionary, or None if no suitable passes
    """
    ranked = rank_passes(passes, weather, recent_passes)
    
    if not ranked:
        return None
    
    best_pass, best_score, breakdown = ranked[0]
    
    # Reject if score too low
    if best_score < 0.3:
        return None
    
    return best_pass


if __name__ == "__main__":
    print("Pass Scorer - Rule-Based Baseline")
    print("=" * 50)
    
    # Example passes
    passes = [
        {
            'satellite': 'NOAA 18',
            'aos_time': datetime(2026, 2, 12, 14, 30, 0),
            'los_time': datetime(2026, 2, 12, 14, 42, 0),
            'max_elevation': 75.0,
            'aos_az': 180,
            'los_az': 45,
        },
        {
            'satellite': 'NOAA 19',
            'aos_time': datetime(2026, 2, 12, 16, 15, 0),
            'los_time': datetime(2026, 2, 12, 16, 23, 0),
            'max_elevation': 35.0,
            'aos_az': 200,
            'los_az': 30,
        },
        {
            'satellite': 'NOAA 20',
            'aos_time': datetime(2026, 2, 12, 18, 45, 0),
            'los_time': datetime(2026, 2, 12, 18, 56, 0),
            'max_elevation': 55.0,
            'aos_az': 170,
            'los_az': 60,
        },
    ]
    
    print("\nScoring passes:\n")
    
    ranked = rank_passes(passes)
    
    for i, (p, score, breakdown) in enumerate(ranked, 1):
        print(f"{i}. {p['satellite']} - Score: {score:.3f}")
        print(f"   Max El: {p['max_elevation']}°")
        print(f"   Breakdown: El={breakdown['elevation_score']:.2f}, "
              f"Dur={breakdown['duration_score']:.2f}, "
              f"Wx={breakdown['weather_score']:.2f}, "
              f"Div={breakdown['time_diversity_score']:.2f}")
        print()
    
    best = recommend_pass(passes)
    if best:
        print(f"Recommended: {best['satellite']} at {best['aos_time']}")
