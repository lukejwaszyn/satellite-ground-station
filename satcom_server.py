#!/usr/bin/env python3
"""
satcom_server.py
SATCOM Ground Station - Mission Operations Server

Unified backend that:
  1. Serves the 3D Mission Operations HMI (satellite-viz.html)
  2. Generates live orbital data via Skyfield SGP4
  3. Exposes REST API for mission control (capture, decode, status)
  4. Serves decoded images for globe overlay
  5. Manages station configuration

Replaces the manual workflow of:
  python generate_orbital_data.py → python -m http.server → open browser

With a single command:
  python satcom_server.py

API Endpoints:
  GET  /                     → HMI frontend
  GET  /api/orbital-data     → Live orbital data (replaces orbital_data.json)
  GET  /api/passes           → Upcoming passes with capture recommendations
  GET  /api/status           → System status (SDR, capture state, etc.)
  GET  /api/missions         → Mission history log
  GET  /api/config           → Current station configuration
  PUT  /api/config           → Update station configuration
  POST /api/capture          → Schedule/trigger a satellite capture
  GET  /api/decoded/<file>   → Serve decoded APT images

Author: Luke Waszyn
Date: February 2026
"""

import json
import os
import sys
import time
import threading
import mimetypes
import subprocess
import traceback
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timezone

# =============================================================
# Paths — resolve relative to this script's location
# =============================================================
BASE_DIR = Path(__file__).parent.resolve()
HMI_DIR = BASE_DIR / 'hmi'
DATA_DIR = BASE_DIR / 'data'
DECODED_DIR = DATA_DIR / 'decoded'
CAPTURES_DIR = DATA_DIR / 'captures'
CONFIG_PATH = BASE_DIR / 'config.json'
MISSION_LOG_PATH = DATA_DIR / 'mission_log.json'

# Add project root to path for imports
sys.path.insert(0, str(BASE_DIR))


# =============================================================
# Default Configuration
# =============================================================
DEFAULT_CONFIG = {
    'station': {
        'name': 'My Ground Station',
        'lat': 40.7934,
        'lon': -77.8600,
        'elevation_m': 376.0,
        'min_elevation_deg': 10.0,
    },
    'capture': {
        'sample_rate': 2.4e6,
        'gain_db': 40,
        'pre_aos_margin_sec': 30,
        'post_los_margin_sec': 30,
        'primary_freq_hz': 137.1e6,
    },
    'hmi': {
        'propagation_hours': 24,
        'position_step_sec': 30,
        'doppler_step_sec': 5,
        'http_port': 8080,
    },
}


def load_config():
    """Load config from file, falling back to defaults."""
    config = DEFAULT_CONFIG.copy()
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, 'r') as f:
                user_config = json.load(f)
            # Deep merge user config over defaults
            for section in user_config:
                if section in config and isinstance(config[section], dict):
                    config[section].update(user_config[section])
                else:
                    config[section] = user_config[section]
        except Exception as e:
            print(f"[WARN] Could not load config.json: {e}, using defaults")
    return config


def save_config(config):
    """Save config to file."""
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=2)


# =============================================================
# System State (thread-safe)
# =============================================================
class SystemState:
    """Tracks current system state across threads."""
    def __init__(self):
        self._lock = threading.Lock()
        self.sdr_connected = False
        self.capturing = False
        self.current_capture = None       # Pass info if capturing
        self.last_orbital_update = None
        self.cached_orbital_data = None
        self.capture_history = []
        self.start_time = datetime.now(timezone.utc)
    
    def to_dict(self):
        with self._lock:
            uptime = (datetime.now(timezone.utc) - self.start_time).total_seconds()
            return {
                'server_uptime_sec': round(uptime),
                'sdr_connected': self.sdr_connected,
                'capturing': self.capturing,
                'current_capture': self.current_capture,
                'last_orbital_update': self.last_orbital_update,
                'orbital_data_cached': self.cached_orbital_data is not None,
                'total_missions': len(self.capture_history),
                'server_time_utc': datetime.now(timezone.utc).isoformat(),
            }
    
    def set_capturing(self, pass_info):
        with self._lock:
            self.capturing = True
            self.current_capture = pass_info
    
    def clear_capturing(self):
        with self._lock:
            self.capturing = False
            self.current_capture = None

state = SystemState()


# =============================================================
# Orbital Data Generation (wraps generate_orbital_data.py)
# =============================================================
def generate_orbital_data(config):
    """
    Generate orbital data using the existing generate_orbital_data module.
    Returns the data dict directly instead of writing to file.
    """
    try:
        # Import the generator - it lives in hmi/
        sys.path.insert(0, str(HMI_DIR))
        
        # We need to patch the ground station location from config
        import importlib
        if 'generate_orbital_data' in sys.modules:
            mod = importlib.reload(sys.modules['generate_orbital_data'])
        else:
            mod = importlib.import_module('generate_orbital_data')
        
        # Patch ground station from config
        mod.GS_LAT = config['station']['lat']
        mod.GS_LON = config['station']['lon']
        mod.GS_ELEV = config['station']['elevation_m']
        mod.MIN_ELEVATION = config['station']['min_elevation_deg']
        
        # Generate data
        data = mod.generate_data(
            duration_hours=config['hmi']['propagation_hours'],
            position_step_sec=config['hmi']['position_step_sec'],
            output_path=str(DATA_DIR / 'orbital_data.json'),
        )
        
        state.last_orbital_update = datetime.now(timezone.utc).isoformat()
        state.cached_orbital_data = data
        
        return data
        
    except Exception as e:
        print(f"[ERROR] Orbital data generation failed: {e}")
        traceback.print_exc()
        return None


# =============================================================
# Mission Log
# =============================================================
def load_mission_log():
    """Load mission history from disk."""
    if MISSION_LOG_PATH.exists():
        try:
            with open(MISSION_LOG_PATH, 'r') as f:
                return json.load(f)
        except Exception:
            return []
    return []


def append_mission_log(entry):
    """Append a mission result to the log."""
    log = load_mission_log()
    log.append(entry)
    MISSION_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MISSION_LOG_PATH, 'w') as f:
        json.dump(log, f, indent=2)
    return log


# =============================================================
# SDR Detection
# =============================================================
def check_sdr():
    """Check if RTL-SDR is connected."""
    try:
        result = subprocess.run(
            ['rtl_test', '-t'],
            capture_output=True, text=True, timeout=5
        )
        connected = 'Found' in result.stdout or 'Found' in result.stderr
        state.sdr_connected = connected
        return connected
    except (FileNotFoundError, subprocess.TimeoutExpired):
        state.sdr_connected = False
        return False


# =============================================================
# Capture Execution (runs in background thread)
# =============================================================
def run_capture_async(pass_info, config):
    """
    Execute a capture in a background thread.
    Converts frontend pass data format to what the capture pipeline expects.
    """
    try:
        state.set_capturing(pass_info)
        
        mission_entry = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'satellite': pass_info.get('satellite', 'Unknown'),
            'max_elevation_deg': pass_info.get('max_el', 0),
            'status': 'capturing',
            'capture_file': None,
            'decoded_image': None,
        }
        
        print(f"\n[CAPTURE] Starting capture for {pass_info.get('satellite', 'Unknown')}")
        print(f"  Max elevation: {pass_info.get('max_el', '?')}°")
        
        # Convert frontend pass format to pipeline format
        # Frontend sends: aos_unix, los_unix, aos_utc, los_utc, duration_sec
        # Pipeline expects: aos_time (datetime), los_time (datetime), satellite, duration_sec
        pipeline_pass = dict(pass_info)
        
        try:
            if 'aos_utc' in pass_info and 'aos_time' not in pass_info:
                pipeline_pass['aos_time'] = datetime.fromisoformat(
                    pass_info['aos_utc'].replace('Z', '+00:00'))
            if 'los_utc' in pass_info and 'los_time' not in pass_info:
                pipeline_pass['los_time'] = datetime.fromisoformat(
                    pass_info['los_utc'].replace('Z', '+00:00'))
            if 'max_el' in pass_info and 'max_elevation' not in pass_info:
                pipeline_pass['max_elevation'] = pass_info['max_el']
        except Exception as e:
            print(f"[CAPTURE] Warning: time conversion issue: {e}")
        
        # Try to use the existing capture pipeline
        try:
            from python.schedule_captures import execute_capture
            from python.doppler_calc import calculate_doppler_profile, save_doppler_profile
            
            # Generate Doppler profile for this pass
            freq_hz = pass_info.get('freq_hz') or config['capture'].get('primary_freq_hz', 137.1e6)
            print(f"  Frequency: {freq_hz/1e6:.4f} MHz (from {'pass data' if pass_info.get('freq_hz') else 'config default'})")
            
            doppler_profile = None
            try:
                doppler_profile = calculate_doppler_profile(
                    pipeline_pass.get('satellite', 'Unknown'),
                    pipeline_pass.get('aos_time'),
                    pipeline_pass.get('los_time'),
                    freq_hz
                )
            except Exception as e:
                print(f"[CAPTURE] Doppler calc failed, capturing without: {e}")
            
            # If no Doppler profile, build a minimal one so execute_capture doesn't crash
            if doppler_profile is None:
                doppler_profile = {
                    'satellite': pipeline_pass.get('satellite', 'Unknown'),
                    'center_freq_hz': freq_hz,
                    'aos_utc': pass_info.get('aos_utc', ''),
                    'los_utc': pass_info.get('los_utc', ''),
                    'points': []
                }
            
            capture_file = execute_capture(pipeline_pass, doppler_profile)
            mission_entry['capture_file'] = str(capture_file) if capture_file else None
            mission_entry['capture_success'] = capture_file is not None
        except Exception as e:
            print(f"[CAPTURE] Capture failed: {e}")
            traceback.print_exc()
            mission_entry['capture_success'] = False
            mission_entry['error'] = str(e)
        
        # Try to decode if capture succeeded
        if mission_entry.get('capture_success') and mission_entry.get('capture_file'):
            try:
                from python.demod.decode_apt import decode_apt
                result = decode_apt(mission_entry['capture_file'], str(DECODED_DIR))
                if result and result.get('png_path'):
                    mission_entry['decoded_image'] = os.path.basename(result['png_path'])
                    mission_entry['decode_success'] = True
                    print(f"[CAPTURE] Decoded: {mission_entry['decoded_image']}")
            except Exception as e:
                print(f"[CAPTURE] Decode failed: {e}")
                mission_entry['decode_success'] = False
        
        mission_entry['status'] = 'complete'
        mission_entry['completed'] = datetime.now(timezone.utc).isoformat()
        
        append_mission_log(mission_entry)
        state.capture_history.append(mission_entry)
        
        print(f"[CAPTURE] Mission complete for {pass_info.get('satellite', 'Unknown')}")
        
    except Exception as e:
        print(f"[CAPTURE] Error: {e}")
        traceback.print_exc()
    finally:
        state.clear_capturing()


# =============================================================
# HTTP Request Handler
# =============================================================
class SATCOMHandler(SimpleHTTPRequestHandler):
    """
    Handles both static file serving (HMI) and REST API requests.
    """
    
    # Suppress default logging for clean output
    def log_message(self, format, *args):
        path = args[0].split()[1] if args else ''
        # Only log API calls and errors, not static file requests
        if '/api/' in str(path) or '40' in str(args[-1:]):
            print(f"[HTTP] {args[0]}")
    
    def send_json(self, data, status=200):
        """Send a JSON response."""
        body = json.dumps(data, separators=(',', ':'))
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(body.encode()))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body.encode())
    
    def send_error_json(self, status, message):
        """Send a JSON error response."""
        self.send_json({'error': message, 'status': status}, status)
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        # ---- API Routes ----
        if path == '/api/orbital-data':
            self.handle_orbital_data()
        elif path == '/api/passes':
            self.handle_passes(parse_qs(parsed.query))
        elif path == '/api/status':
            self.handle_status()
        elif path == '/api/missions':
            self.handle_missions()
        elif path == '/api/config':
            self.handle_get_config()
        elif path.startswith('/api/decoded/'):
            self.handle_decoded_image(path)
        
        # ---- Static Files (HMI) ----
        elif path == '/' or path == '/index.html':
            self.serve_file(HMI_DIR / 'satellite-viz.html', 'text/html')
        elif path == '/orbital_data.json':
            # Backwards compatibility — redirect to API
            self.handle_orbital_data()
        else:
            # Try to serve from hmi/ directory
            file_path = HMI_DIR / path.lstrip('/')
            if file_path.exists() and file_path.is_file():
                self.serve_file(file_path)
            else:
                # Try from project root (for any other static assets)
                file_path = BASE_DIR / path.lstrip('/')
                if file_path.exists() and file_path.is_file():
                    self.serve_file(file_path)
                else:
                    self.send_error_json(404, f'Not found: {path}')
    
    def do_PUT(self):
        parsed = urlparse(self.path)
        if parsed.path == '/api/config':
            self.handle_put_config()
        else:
            self.send_error_json(404, 'Not found')
    
    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == '/api/capture':
            self.handle_capture()
        elif parsed.path == '/api/refresh':
            self.handle_refresh()
        else:
            self.send_error_json(404, 'Not found')
    
    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    # ---- Handlers ----
    
    def handle_orbital_data(self):
        """Generate and return orbital data."""
        config = load_config()
        
        # Use cache if fresh (< 10 min old)
        if state.cached_orbital_data and state.last_orbital_update:
            try:
                last = datetime.fromisoformat(state.last_orbital_update)
                age = (datetime.now(timezone.utc) - last).total_seconds()
                if age < 600:  # 10 minutes
                    self.send_json(state.cached_orbital_data)
                    return
            except Exception:
                pass
        
        print("[API] Generating fresh orbital data...")
        data = generate_orbital_data(config)
        
        if data:
            self.send_json(data)
        else:
            self.send_error_json(500, 'Failed to generate orbital data')
    
    def handle_passes(self, query):
        """Return upcoming passes, optionally filtered."""
        config = load_config()
        
        # Use cached data if available
        if not state.cached_orbital_data:
            generate_orbital_data(config)
        
        if not state.cached_orbital_data:
            self.send_error_json(500, 'No orbital data available')
            return
        
        # Extract passes from all satellites
        min_el = float(query.get('min_elevation', [0])[0])
        role_filter = query.get('role', [None])[0]
        
        passes = []
        for sat_name, sat_data in state.cached_orbital_data.get('satellites', {}).items():
            for p in sat_data.get('passes', []):
                if p['max_el'] >= min_el:
                    if role_filter and sat_data.get('role') != role_filter:
                        continue
                    pass_entry = {**p, 'satellite': sat_name, 'role': sat_data.get('role')}
                    passes.append(pass_entry)
        
        # Sort by AOS time
        passes.sort(key=lambda p: p.get('aos_unix', 0))
        
        self.send_json({
            'count': len(passes),
            'min_elevation_filter': min_el,
            'passes': passes,
        })
    
    def handle_status(self):
        """Return current system status (non-blocking, uses cached SDR state)."""
        status = state.to_dict()
        status['decoded_images'] = len(list(DECODED_DIR.glob('*.png'))) if DECODED_DIR.exists() else 0
        status['config_loaded'] = CONFIG_PATH.exists()
        
        self.send_json(status)
    
    def handle_missions(self):
        """Return mission history."""
        log = load_mission_log()
        self.send_json({
            'count': len(log),
            'missions': log,
        })
    
    def handle_get_config(self):
        """Return current configuration."""
        config = load_config()
        self.send_json(config)
    
    def handle_put_config(self):
        """Update configuration."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            new_config = json.loads(body)
            
            # Merge with existing config
            config = load_config()
            for section in new_config:
                if section in config and isinstance(config[section], dict):
                    config[section].update(new_config[section])
                else:
                    config[section] = new_config[section]
            
            save_config(config)
            
            # Invalidate orbital cache since config changed
            state.cached_orbital_data = None
            
            self.send_json({'status': 'ok', 'config': config})
        except Exception as e:
            self.send_error_json(400, f'Invalid config: {e}')
    
    def handle_capture(self):
        """Trigger a satellite capture."""
        if state.capturing:
            self.send_error_json(409, 'Capture already in progress')
            return
        
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            pass_info = json.loads(body) if body else {}
            
            # Check AOS time — don't capture if more than 2 minutes away
            aos_unix = pass_info.get('aos_unix', 0)
            los_unix = pass_info.get('los_unix', 0)
            now_unix = time.time()
            secs_until_aos = aos_unix - now_unix
            
            # Allow if: pass is active (AOS past, LOS future) OR within 2 min of AOS
            pass_is_active = aos_unix <= now_unix and los_unix > now_unix
            
            if not pass_is_active and secs_until_aos > 120:
                mins = int(secs_until_aos / 60)
                self.send_error_json(400, f'Too early — AOS in {mins} minutes. Wait until 2 min before AOS.')
                return
            
            config = load_config()
            
            # Launch capture in background thread
            thread = threading.Thread(
                target=run_capture_async,
                args=(pass_info, config),
                daemon=True
            )
            thread.start()
            
            self.send_json({
                'status': 'capture_started',
                'satellite': pass_info.get('satellite', 'Unknown'),
                'message': 'Capture running in background',
            })
        except Exception as e:
            self.send_error_json(400, f'Invalid request: {e}')
    
    def handle_refresh(self):
        """Force regeneration of orbital data."""
        state.cached_orbital_data = None
        config = load_config()
        print("[API] Forcing orbital data refresh...")
        data = generate_orbital_data(config)
        if data:
            self.send_json({'status': 'ok', 'satellites': len(data.get('satellites', {}))})
        else:
            self.send_error_json(500, 'Refresh failed')
    
    def handle_decoded_image(self, path):
        """Serve a decoded APT image."""
        filename = path.replace('/api/decoded/', '')
        file_path = DECODED_DIR / filename
        if file_path.exists():
            self.serve_file(file_path)
        else:
            self.send_error_json(404, f'Image not found: {filename}')
    
    def serve_file(self, file_path, content_type=None):
        """Serve a static file."""
        file_path = Path(file_path)
        if not file_path.exists():
            self.send_error_json(404, 'Not found')
            return
        
        if content_type is None:
            content_type, _ = mimetypes.guess_type(str(file_path))
            content_type = content_type or 'application/octet-stream'
        
        with open(file_path, 'rb') as f:
            data = f.read()
        
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', len(data))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        self.wfile.write(data)


# =============================================================
# Server Startup
# =============================================================
def print_banner(config):
    """Print startup banner."""
    port = config['hmi']['http_port']
    station = config['station']
    
    print()
    print("=" * 60)
    print("  ███████  █████  ████████  ██████  ██████  ███    ███ ")
    print("  ██      ██   ██    ██    ██      ██    ██ ████  ████ ")
    print("  ███████ ███████    ██    ██      ██    ██ ██ ████ ██ ")
    print("       ██ ██   ██    ██    ██      ██    ██ ██  ██  ██ ")
    print("  ███████ ██   ██    ██     ██████  ██████  ██      ██ ")
    print()
    print("  Ground Station Mission Operations Server")
    print("=" * 60)
    print(f"  Station:   {station['name']}")
    print(f"  Location:  {station['lat']}°N, {abs(station['lon'])}°W")
    print(f"  Elevation: {station['elevation_m']}m")
    print(f"  Server:    http://localhost:{port}")
    print()
    print("  Endpoints:")
    print(f"    HMI:     http://localhost:{port}/")
    print(f"    API:     http://localhost:{port}/api/status")
    print(f"    Passes:  http://localhost:{port}/api/passes")
    print(f"    Config:  http://localhost:{port}/api/config")
    print("=" * 60)
    print()


def main():
    """Start the SATCOM server."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='SATCOM Ground Station - Mission Operations Server',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python satcom_server.py                    # Start on default port 8080
  python satcom_server.py --port 3000        # Custom port
  python satcom_server.py --no-generate      # Skip initial orbital data generation
"""
    )
    parser.add_argument('--port', type=int, default=None,
                        help='HTTP port (default: from config or 8080)')
    parser.add_argument('--no-generate', action='store_true',
                        help='Skip initial orbital data generation')
    
    args = parser.parse_args()
    
    # Load config
    config = load_config()
    port = args.port or config['hmi']['http_port']
    
    # Ensure data directories exist
    for d in [DATA_DIR, DECODED_DIR, CAPTURES_DIR]:
        d.mkdir(parents=True, exist_ok=True)
    
    # Print banner
    print_banner(config)
    
    # Check SDR
    print("[INIT] Checking for RTL-SDR...", end=' ')
    if check_sdr():
        print("FOUND ✓")
    else:
        print("NOT FOUND (capture disabled, HMI will work in tracking mode)")
    
    # Start background SDR polling (every 15 seconds)
    def sdr_poll_loop():
        while True:
            time.sleep(15)
            try:
                check_sdr()
            except Exception:
                pass
    
    sdr_thread = threading.Thread(target=sdr_poll_loop, daemon=True)
    sdr_thread.start()
    
    # Generate initial orbital data
    if not args.no_generate:
        print("[INIT] Generating orbital data (this takes ~30-60s)...")
        try:
            generate_orbital_data(config)
            print("[INIT] Orbital data ready ✓")
        except Exception as e:
            print(f"[INIT] Orbital data generation failed: {e}")
            print("[INIT] HMI will start in demo mode")
    else:
        print("[INIT] Skipping orbital data generation (--no-generate)")
    
    # Start server
    server = HTTPServer(('0.0.0.0', port), SATCOMHandler)
    
    print(f"\n[SERVER] Listening on http://localhost:{port}")
    print("[SERVER] Press Ctrl+C to stop\n")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[SERVER] Shutting down...")
        server.shutdown()


if __name__ == '__main__':
    main()
