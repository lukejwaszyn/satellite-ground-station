#!/usr/bin/env python3
"""
capture_daemon.py
Satellite Ground Station - Autonomous Capture Daemon

Background thread that continuously monitors the pass schedule and
automatically captures, decodes, and grades every capturable satellite pass.

Designed to run inside satcom_server.py as a daemon thread, but can also
run standalone for testing.

Behavior:
  - Scans pass schedule every 30 seconds
  - When a capturable pass (APT or LRPT) AOS is within the pre-AOS margin:
    - Selects the highest-elevation pass if multiple are imminent
    - Waits until AOS
    - Triggers capture via the existing pipeline
    - Routes to correct decoder (APT or LRPT)
    - Runs quality estimator on decoded image
    - Logs everything to mission log
  - Skips passes already captured (tracks by satellite + AOS time)
  - Respects cooldown between captures (configurable)
  - Can be enabled/disabled via config or API

Integration:
  - Import and start from satcom_server.py main()
  - Uses shared SystemState for coordination with manual captures
  - Writes to same mission log as manual captures

Author: Luke Waszyn
Date: March 2026
"""

import os
import sys
import time
import json
import threading
import traceback
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Resolve paths relative to project root
BASE_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(BASE_DIR))

# Default daemon configuration
DAEMON_DEFAULTS = {
    'enabled': True,
    'scan_interval_sec': 30,          # How often to check for upcoming passes
    'pre_aos_margin_sec': 120,        # Start preparing this many seconds before AOS
    'post_capture_cooldown_sec': 60,  # Minimum time between captures
    'min_elevation_deg': 15,          # Minimum max elevation to attempt
    'max_concurrent_captures': 1,     # Only one capture at a time
    'auto_decode': True,              # Automatically decode after capture
    'auto_quality_check': True,       # Automatically grade decoded images
    'capturable_roles': ['primary', 'weather'],  # Which satellite roles to capture
}

# Satellites that actually transmit decodable signals
CAPTURABLE_SATS = {
    'NOAA 15', 'NOAA 18', 'NOAA 19',          # APT
    'METEOR-M2 3', 'METEOR-M2 4',              # LRPT
}


class CaptureDaemon:
    """
    Autonomous capture daemon that runs as a background thread.
    
    Monitors the pass schedule and automatically captures every
    capturable satellite pass without operator intervention.
    """
    
    def __init__(self, state, config_func, orbital_data_func, 
                 capture_func, log_func, decoded_dir):
        """
        Args:
            state: SystemState instance (shared with server)
            config_func: callable that returns current config dict
            orbital_data_func: callable that returns cached orbital data
            capture_func: callable(pass_info, config) to execute capture
            log_func: callable(entry) to append to mission log  
            decoded_dir: Path to decoded images directory
        """
        self.state = state
        self.get_config = config_func
        self.get_orbital_data = orbital_data_func
        self.run_capture = capture_func
        self.append_log = log_func
        self.decoded_dir = Path(decoded_dir)
        
        self._thread = None
        self._running = False
        self._lock = threading.Lock()
        
        # Track which passes we've already captured (satellite + aos_unix)
        self._captured_passes = set()
        
        # Stats
        self.stats = {
            'started_at': None,
            'total_scans': 0,
            'total_captures': 0,
            'total_decodes': 0,
            'total_good': 0,
            'total_marginal': 0,
            'total_noise': 0,
            'last_scan': None,
            'last_capture': None,
            'last_capture_satellite': None,
            'last_capture_result': None,
            'next_scheduled': None,
            'next_scheduled_satellite': None,
            'errors': 0,
        }
        
        # Load daemon config
        self.daemon_config = DAEMON_DEFAULTS.copy()
        config = self.get_config()
        if 'daemon' in config:
            self.daemon_config.update(config['daemon'])
    
    def start(self):
        """Start the daemon thread."""
        if self._running:
            return
        
        self._running = True
        self.stats['started_at'] = datetime.now(timezone.utc).isoformat()
        
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.name = 'capture-daemon'
        self._thread.start()
        
        print("[DAEMON] Autonomous capture daemon started")
        print(f"[DAEMON]   Scan interval: {self.daemon_config['scan_interval_sec']}s")
        print(f"[DAEMON]   Pre-AOS margin: {self.daemon_config['pre_aos_margin_sec']}s")
        print(f"[DAEMON]   Min elevation: {self.daemon_config['min_elevation_deg']}°")
        print(f"[DAEMON]   Auto decode: {self.daemon_config['auto_decode']}")
        print(f"[DAEMON]   Auto quality check: {self.daemon_config['auto_quality_check']}")
    
    def stop(self):
        """Stop the daemon thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        print("[DAEMON] Stopped")
    
    def is_running(self):
        return self._running
    
    def get_status(self):
        """Return daemon status for API."""
        return {
            'enabled': self.daemon_config.get('enabled', True),
            'running': self._running,
            'config': self.daemon_config,
            'stats': self.stats,
            'captured_passes': len(self._captured_passes),
        }
    
    def _run_loop(self):
        """Main daemon loop."""
        print("[DAEMON] Entering main loop...")
        
        while self._running:
            try:
                self._scan_and_capture()
            except Exception as e:
                print(f"[DAEMON] Error in scan loop: {e}")
                traceback.print_exc()
                self.stats['errors'] += 1
            
            # Sleep in small increments so we can stop quickly
            for _ in range(self.daemon_config['scan_interval_sec']):
                if not self._running:
                    break
                time.sleep(1)
    
    def _scan_and_capture(self):
        """Check for upcoming passes and trigger capture if needed."""
        self.stats['total_scans'] += 1
        self.stats['last_scan'] = datetime.now(timezone.utc).isoformat()
        
        # Don't interfere with manual captures
        if self.state.capturing:
            return
        
        # Check if daemon is enabled
        if not self.daemon_config.get('enabled', True):
            return
        
        # Check if SDR is connected
        if not self.state.sdr_connected:
            return
        
        # Get current orbital data
        orbital_data = self.get_orbital_data()
        if not orbital_data:
            return
        
        now_unix = time.time()
        pre_margin = self.daemon_config['pre_aos_margin_sec']
        min_el = self.daemon_config['min_elevation_deg']
        
        # Find all imminent capturable passes
        candidates = []
        
        for sat_name, sat_data in orbital_data.get('satellites', {}).items():
            # Check if this satellite is capturable
            role = sat_data.get('role', 'display')
            if role not in self.daemon_config['capturable_roles']:
                continue
            
            # Additional check: is this actually a satellite we can decode?
            if sat_name not in CAPTURABLE_SATS:
                continue
            
            for p in sat_data.get('passes', []):
                # Skip passes we've already captured
                pass_key = f"{sat_name}_{p['aos_unix']}"
                if pass_key in self._captured_passes:
                    continue
                
                # Skip passes that have already ended
                if p.get('los_unix', 0) < now_unix:
                    continue
                
                # Skip low-elevation passes
                if p.get('max_el', 0) < min_el:
                    continue
                
                # Check if pass is imminent (within pre-AOS margin) or active
                time_to_aos = p['aos_unix'] - now_unix
                is_active = p['aos_unix'] <= now_unix and p.get('los_unix', 0) > now_unix
                is_imminent = 0 < time_to_aos <= pre_margin
                
                if is_active or is_imminent:
                    candidates.append({
                        'satellite': sat_name,
                        'pass': p,
                        'freq_hz': sat_data.get('freq_hz'),
                        'signal_type': 'LRPT' if 'METEOR' in sat_name.upper() else 'APT',
                        'time_to_aos': time_to_aos,
                        'is_active': is_active,
                    })
        
        if not candidates:
            # Update next scheduled info for status display
            self._update_next_scheduled(orbital_data, now_unix, min_el)
            return
        
        # Select the best candidate (highest elevation, prefer active passes)
        candidates.sort(key=lambda c: (c['is_active'], c['pass']['max_el']), reverse=True)
        best = candidates[0]
        
        sat_name = best['satellite']
        pass_data = best['pass']
        
        status_str = 'In progress' if best['is_active'] else f"AOS in {best['time_to_aos']:.0f}s"
        print(f"\n[DAEMON] {'ACTIVE' if best['is_active'] else 'IMMINENT'} pass detected: "
              f"{sat_name} | Max El: {pass_data['max_el']}° | {status_str}")
        
        # Wait for AOS if not yet active
        if not best['is_active'] and best['time_to_aos'] > 5:
            wait_sec = best['time_to_aos'] - 5  # Start 5 seconds before AOS
            print(f"[DAEMON] Waiting {wait_sec:.0f}s for AOS...")
            
            # Wait in small increments
            waited = 0
            while waited < wait_sec and self._running and not self.state.capturing:
                time.sleep(min(5, wait_sec - waited))
                waited += 5
            
            if not self._running or self.state.capturing:
                print("[DAEMON] Aborted wait (shutdown or manual capture started)")
                return
        
        # Execute capture
        self._execute_autonomous_capture(best)
    
    def _execute_autonomous_capture(self, candidate):
        """Execute a full autonomous capture cycle."""
        sat_name = candidate['satellite']
        pass_data = candidate['pass']
        signal_type = candidate['signal_type']
        pass_key = f"{sat_name}_{pass_data['aos_unix']}"
        
        # Mark this pass as captured (even if it fails, don't retry)
        self._captured_passes.add(pass_key)
        
        print(f"[DAEMON] Starting autonomous capture: {sat_name} ({signal_type})")
        print(f"[DAEMON]   Max elevation: {pass_data['max_el']}°")
        print(f"[DAEMON]   Duration: {pass_data.get('duration_sec', 0)/60:.1f} min")
        
        # Build pass_info in the format the capture pipeline expects
        pass_info = {
            **pass_data,
            'satellite': sat_name,
            'freq_hz': candidate.get('freq_hz'),
        }
        
        config = self.get_config()
        
        self.stats['total_captures'] += 1
        self.stats['last_capture'] = datetime.now(timezone.utc).isoformat()
        self.stats['last_capture_satellite'] = sat_name
        
        try:
            # Use the same capture function as the manual path
            self.run_capture(pass_info, config)
            
            self.stats['last_capture_result'] = 'complete'
            print(f"[DAEMON] Capture complete: {sat_name}")
            
            # Quality check on the most recent decoded image
            if self.daemon_config.get('auto_quality_check', True):
                self._run_quality_check(sat_name)
            
        except Exception as e:
            print(f"[DAEMON] Capture failed: {e}")
            traceback.print_exc()
            self.stats['last_capture_result'] = f'error: {str(e)[:100]}'
            self.stats['errors'] += 1
        
        # Cooldown before next capture
        cooldown = self.daemon_config.get('post_capture_cooldown_sec', 60)
        if cooldown > 0:
            print(f"[DAEMON] Cooldown: {cooldown}s")
            time.sleep(cooldown)
    
    def _run_quality_check(self, sat_name):
        """Run quality estimator on the most recently decoded image."""
        try:
            # Find the most recent decoded image
            decoded_files = sorted(
                self.decoded_dir.glob('*.png'),
                key=lambda f: f.stat().st_mtime,
                reverse=True
            )
            
            if not decoded_files:
                return
            
            latest = decoded_files[0]
            
            # Only check if it was modified in the last 5 minutes
            age = time.time() - latest.stat().st_mtime
            if age > 300:
                return
            
            from python.quality_estimator import estimate_quality
            result = estimate_quality(str(latest))
            
            grade = result.get('grade', 'UNKNOWN')
            confidence = result.get('confidence', 0)
            snr = result.get('metrics', {}).get('snr_db', '?')
            
            print(f"[DAEMON] Quality: {grade} (confidence: {confidence}, SNR: {snr} dB)")
            
            # Update stats
            if grade == 'GOOD':
                self.stats['total_good'] += 1
            elif grade == 'MARGINAL':
                self.stats['total_marginal'] += 1
            elif grade == 'NOISE':
                self.stats['total_noise'] += 1
            
            self.stats['total_decodes'] += 1
            
            # Save quality report alongside the image
            quality_path = latest.with_suffix('.quality.json')
            with open(quality_path, 'w') as f:
                json.dump(result, f, indent=2)
            
        except ImportError:
            print("[DAEMON] quality_estimator not available, skipping quality check")
        except Exception as e:
            print(f"[DAEMON] Quality check failed: {e}")
    
    def _update_next_scheduled(self, orbital_data, now_unix, min_el):
        """Find and cache the next upcoming capturable pass for status display."""
        next_pass = None
        next_sat = None
        
        for sat_name, sat_data in orbital_data.get('satellites', {}).items():
            role = sat_data.get('role', 'display')
            if role not in self.daemon_config['capturable_roles']:
                continue
            if sat_name not in CAPTURABLE_SATS:
                continue
            
            for p in sat_data.get('passes', []):
                if p['aos_unix'] <= now_unix:
                    continue
                if p.get('max_el', 0) < min_el:
                    continue
                
                pass_key = f"{sat_name}_{p['aos_unix']}"
                if pass_key in self._captured_passes:
                    continue
                
                if not next_pass or p['aos_unix'] < next_pass['aos_unix']:
                    next_pass = p
                    next_sat = sat_name
        
        if next_pass:
            time_until = next_pass['aos_unix'] - now_unix
            mins = int(time_until / 60)
            self.stats['next_scheduled'] = next_pass.get('aos_utc', '')
            self.stats['next_scheduled_satellite'] = next_sat
            
            # Log periodically (every ~5 minutes worth of scans)
            if self.stats['total_scans'] % 10 == 1:
                print(f"[DAEMON] Next capture: {next_sat} in {mins}m "
                      f"(El: {next_pass['max_el']}°)")
        else:
            self.stats['next_scheduled'] = None
            self.stats['next_scheduled_satellite'] = None


def create_daemon(state, config_func, orbital_data_func, 
                  capture_func, log_func, decoded_dir):
    """
    Factory function to create a CaptureDaemon instance.
    Called from satcom_server.py main().
    
    Returns: CaptureDaemon instance (call .start() to begin)
    """
    return CaptureDaemon(
        state=state,
        config_func=config_func,
        orbital_data_func=orbital_data_func,
        capture_func=capture_func,
        log_func=log_func,
        decoded_dir=decoded_dir,
    )


# ================================================================
# Standalone mode (for testing without the full server)
# ================================================================

if __name__ == '__main__':
    print("="*60)
    print("  AUTONOMOUS CAPTURE DAEMON — Standalone Test Mode")
    print("="*60)
    print()
    print("In production, this runs inside satcom_server.py.")
    print("Standalone mode simulates the daemon loop for testing.")
    print()
    
    # Minimal standalone test
    class MockState:
        sdr_connected = False
        capturing = False
    
    mock_state = MockState()
    
    def mock_config():
        return {'daemon': {'enabled': True, 'scan_interval_sec': 10}}
    
    def mock_orbital():
        return None
    
    def mock_capture(pass_info, config):
        print(f"[MOCK] Would capture: {pass_info.get('satellite')}")
    
    def mock_log(entry):
        print(f"[MOCK] Would log: {entry.get('satellite')}")
    
    daemon = create_daemon(
        mock_state, mock_config, mock_orbital,
        mock_capture, mock_log, '/tmp/decoded'
    )
    
    print("Starting daemon (Ctrl+C to stop)...")
    daemon.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        daemon.stop()
        print("\nDaemon stopped.")
