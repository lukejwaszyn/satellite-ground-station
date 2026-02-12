#!/usr/bin/env python3
"""
scheduler_optimizer.py
Satellite Ground Station - ML-Optimized Schedule Generator

Generates optimal capture schedules based on predictions.

Optimization objectives:
    - Maximize total expected success
    - Balance satellite diversity
    - Respect constraints (min gap between captures, max per day)
    - Prioritize high-confidence predictions

Author: Luke Waszyn
Date: February 2026
"""

import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from python.ml.ml_predictor import get_predictor, predict_success
from python.ml.pass_scorer import score_pass
from python.schedule_captures import get_upcoming_passes


# Schedule constraints
CONSTRAINTS = {
    'min_gap_minutes': 30,          # Minimum time between captures
    'max_captures_per_day': 8,      # Don't exhaust resources
    'min_success_probability': 0.3, # Skip low-probability passes
    'prefer_diversity': True,       # Try different satellites
    'max_consecutive_same_sat': 3,  # Max same satellite in a row
}


class ScheduleOptimizer:
    """
    Generates optimized capture schedules.
    """
    
    def __init__(self, constraints: Optional[Dict] = None):
        self.constraints = {**CONSTRAINTS, **(constraints or {})}
        self.predictor = get_predictor()
    
    def generate_schedule(self,
                          hours_ahead: int = 48,
                          weather: Optional[Dict] = None,
                          config: Optional[Dict] = None) -> List[Dict]:
        """
        Generate optimized capture schedule.
        
        Args:
            hours_ahead: How far ahead to schedule
            weather: Weather data (optional)
            config: Hardware config (optional)
        
        Returns:
            List of scheduled captures with predictions
        """
        # Get upcoming passes
        passes = get_upcoming_passes(hours_ahead=hours_ahead, min_elevation=15)
        
        if not passes:
            return []
        
        # Score all passes
        scored_passes = []
        for p in passes:
            pred = self.predictor.predict(p, weather, config)
            scored_passes.append({
                'pass': p,
                'prediction': pred,
                'score': pred['success_probability'],
            })
        
        # Sort by score descending
        scored_passes.sort(key=lambda x: x['score'], reverse=True)
        
        # Apply constraints to build schedule
        schedule = self._apply_constraints(scored_passes)
        
        return schedule
    
    def _apply_constraints(self, scored_passes: List[Dict]) -> List[Dict]:
        """
        Apply scheduling constraints.
        
        Greedy algorithm: take highest-scoring passes that satisfy constraints.
        """
        schedule = []
        captures_by_day = {}
        consecutive_same_sat = 0
        last_satellite = None
        last_end_time = None
        
        for item in scored_passes:
            p = item['pass']
            pred = item['prediction']
            
            # Skip low probability
            if pred['success_probability'] < self.constraints['min_success_probability']:
                continue
            
            # Parse times
            aos = p['aos_time']
            los = p['los_time']
            
            if isinstance(aos, str):
                aos = datetime.fromisoformat(aos.replace('Z', '+00:00')).replace(tzinfo=None)
            if isinstance(los, str):
                los = datetime.fromisoformat(los.replace('Z', '+00:00')).replace(tzinfo=None)
            if hasattr(aos, 'tzinfo') and aos.tzinfo:
                aos = aos.replace(tzinfo=None)
            if hasattr(los, 'tzinfo') and los.tzinfo:
                los = los.replace(tzinfo=None)
            
            # Check minimum gap
            if last_end_time is not None:
                gap = (aos - last_end_time).total_seconds() / 60
                if gap < self.constraints['min_gap_minutes']:
                    continue
            
            # Check max captures per day
            day_key = aos.strftime('%Y-%m-%d')
            day_count = captures_by_day.get(day_key, 0)
            if day_count >= self.constraints['max_captures_per_day']:
                continue
            
            # Check satellite diversity
            satellite = p.get('satellite', '')
            if satellite == last_satellite:
                consecutive_same_sat += 1
                if consecutive_same_sat >= self.constraints['max_consecutive_same_sat']:
                    continue
            else:
                consecutive_same_sat = 0
            
            # Pass all constraints - add to schedule
            schedule.append({
                'pass': p,
                'prediction': pred,
                'scheduled_aos': aos.isoformat(),
                'scheduled_los': los.isoformat(),
            })
            
            # Update state
            last_end_time = los
            last_satellite = satellite
            captures_by_day[day_key] = day_count + 1
        
        # Sort schedule by time
        schedule.sort(key=lambda x: x['scheduled_aos'])
        
        return schedule
    
    def get_schedule_summary(self, schedule: List[Dict]) -> Dict:
        """
        Generate summary statistics for a schedule.
        """
        if not schedule:
            return {'total': 0}
        
        total = len(schedule)
        expected_successes = sum(s['prediction']['success_probability'] for s in schedule)
        
        satellites = set(s['pass'].get('satellite', 'unknown') for s in schedule)
        
        by_recommendation = {'capture': 0, 'marginal': 0, 'skip': 0}
        for s in schedule:
            rec = s['prediction'].get('recommendation', 'unknown')
            if rec in by_recommendation:
                by_recommendation[rec] += 1
        
        avg_elevation = sum(s['pass'].get('max_elevation', 0) for s in schedule) / total
        
        return {
            'total_passes': total,
            'expected_successes': round(expected_successes, 1),
            'expected_success_rate': round(expected_successes / total, 2),
            'unique_satellites': len(satellites),
            'satellites': list(satellites),
            'by_recommendation': by_recommendation,
            'avg_elevation': round(avg_elevation, 1),
        }
    
    def print_schedule(self, schedule: List[Dict]):
        """Print formatted schedule."""
        print("\n" + "=" * 70)
        print("OPTIMIZED CAPTURE SCHEDULE")
        print("=" * 70)
        
        if not schedule:
            print("No passes scheduled")
            return
        
        summary = self.get_schedule_summary(schedule)
        
        print(f"\nSummary:")
        print(f"  Total passes: {summary['total_passes']}")
        print(f"  Expected successes: {summary['expected_successes']}")
        print(f"  Expected success rate: {summary['expected_success_rate']:.0%}")
        print(f"  Satellites: {', '.join(summary['satellites'])}")
        
        print(f"\nSchedule:")
        print("-" * 70)
        
        current_day = None
        
        for i, item in enumerate(schedule, 1):
            p = item['pass']
            pred = item['prediction']
            
            aos = item['scheduled_aos']
            if isinstance(aos, str):
                aos_dt = datetime.fromisoformat(aos)
            else:
                aos_dt = aos
            
            day = aos_dt.strftime('%Y-%m-%d')
            if day != current_day:
                print(f"\n  {day}")
                print(f"  {'-' * 40}")
                current_day = day
            
            time_str = aos_dt.strftime('%H:%M:%S')
            sat = p.get('satellite', 'Unknown')
            el = p.get('max_elevation', 0)
            prob = pred['success_probability']
            rec = pred['recommendation']
            
            rec_symbol = {'capture': '+', 'marginal': '~', 'skip': '-'}.get(rec, '?')
            
            print(f"  [{rec_symbol}] {time_str} UTC | {sat:20} | "
                  f"El: {el:4.1f}° | P(success): {prob:5.1%}")
        
        print("\n" + "=" * 70)


def generate_schedule(hours_ahead: int = 48,
                      weather: Optional[Dict] = None,
                      constraints: Optional[Dict] = None) -> List[Dict]:
    """
    Convenience function to generate schedule.
    
    Args:
        hours_ahead: Planning horizon in hours
        weather: Weather data (optional)
        constraints: Override default constraints (optional)
    
    Returns:
        List of scheduled captures
    """
    optimizer = ScheduleOptimizer(constraints)
    return optimizer.generate_schedule(hours_ahead, weather)


def optimize_next_n(n: int = 5,
                    weather: Optional[Dict] = None) -> List[Dict]:
    """
    Get the next N best passes to capture.
    
    Args:
        n: Number of passes to return
        weather: Weather data (optional)
    
    Returns:
        Top N passes by predicted success
    """
    optimizer = ScheduleOptimizer()
    schedule = optimizer.generate_schedule(hours_ahead=72, weather=weather)
    return schedule[:n]


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate optimized capture schedule')
    parser.add_argument('--hours', type=int, default=48,
                        help='Hours ahead to schedule (default: 48)')
    parser.add_argument('--json', action='store_true',
                        help='Output as JSON')
    
    args = parser.parse_args()
    
    optimizer = ScheduleOptimizer()
    schedule = optimizer.generate_schedule(hours_ahead=args.hours)
    
    if args.json:
        import json
        # Clean for JSON serialization
        output = []
        for item in schedule:
            output.append({
                'satellite': item['pass'].get('satellite'),
                'aos': item['scheduled_aos'],
                'los': item['scheduled_los'],
                'max_elevation': item['pass'].get('max_elevation'),
                'success_probability': item['prediction']['success_probability'],
                'recommendation': item['prediction']['recommendation'],
            })
        print(json.dumps(output, indent=2))
    else:
        optimizer.print_schedule(schedule)
        
        summary = optimizer.get_schedule_summary(schedule)
        print(f"\nNext recommended capture:")
        if schedule:
            next_pass = schedule[0]
            print(f"  {next_pass['pass'].get('satellite')} at {next_pass['scheduled_aos']}")
            print(f"  Success probability: {next_pass['prediction']['success_probability']:.1%}")
