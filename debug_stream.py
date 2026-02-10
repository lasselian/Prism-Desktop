
import sys
import json
import keyring
from pathlib import Path
import requests
import time

# Mock utils - we can just hardcode or read config
# Assuming config is in AppData/PrismDesktop or similar
# But let's check utils later if needed.
# Let's import utils and keyring as main.py does.

from core.utils import get_config_path

KEY_TOKEN = "ha_token"
SERVICE_NAME = "PrismDesktop"

def load_token():
    try:
        token = keyring.get_password(SERVICE_NAME, KEY_TOKEN)
        return token
    except Exception as e:
        print(f"Error loading token: {e}")
        return None

def load_config():
    path = get_config_path()
    if path.exists():
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def test_stream(entity_id):
    config = load_config()
    token = load_token()
    
    if not token:
        print("No token found in keyring.")
        return
        
    ha_config = config.get('home_assistant', {})
    url = ha_config.get('url', '').rstrip('/')
    
    if not url:
        print("No HA URL found in config.")
        return

    print(f"Connecting to {url} for entity {entity_id}...")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # 1. Test Snapshot first
    print("\n--- Testing Snapshot API (/api/camera_proxy) ---")
    try:
        snap_resp = requests.get(f"{url}/api/camera_proxy/{entity_id}", headers=headers, timeout=10)
        print(f"Snapshot Status: {snap_resp.status_code}")
        print(f"Snapshot Content-Type: {snap_resp.headers.get('Content-Type')}")
        print(f"Snapshot Size: {len(snap_resp.content)} bytes")
        
        if snap_resp.status_code != 200:
            print("Snapshot failed! Camera might be unavailable or auth error.")
            # Proceed anyway to test stream
    except Exception as e:
        print(f"Snapshot Error: {e}")

    # 2. Test Stream with http.client (low level)
    print("\n--- Testing Stream API (/api/camera_proxy_stream) via http.client ---")
    import http.client
    from urllib.parse import urlparse
    
    parsed = urlparse(url)
    conn_cls = http.client.HTTPSConnection if parsed.scheme == 'https' else http.client.HTTPConnection
    port = parsed.port or (443 if parsed.scheme == 'https' else 80)
    
    # 3. Test Stream with HTTP/1.0 (No Chunked)
    print("\n--- Testing Stream API with HTTP/1.0 (No Chunked) ---")
    path = f"/api/camera_proxy_stream/{entity_id}"
    try:
        conn = conn_cls(parsed.hostname, port, timeout=10)
        conn._http_vsn = 10
        conn._http_vsn_str = 'HTTP/1.0'
        
        # Define headers again
        h = {
            "Authorization": f"Bearer {token}",
            "User-Agent": "PrismDesktop/Debug",
            "Accept": "*/*"
        }
        
        print(f"Requesting {path} (HTTP/1.0)...")
        conn.request("GET", path, headers=h)
        resp = conn.getresponse()
        print(f"Response Status: {resp.status} {resp.reason}")
        print(f"Response Headers: {resp.getheaders()}")
        
        if resp.status == 200:
            print("Reading stream (HTTP/1.0)...")
            chunks = 0
            total_bytes = 0
            start_t = time.time()
            while True:
                chunk = resp.read(1024)
                if not chunk:
                    print("Stream ended (0 bytes)")
                    break
                chunks += 1
                total_bytes += len(chunk)
                if chunks % 100 == 0:
                    print(f"Read {total_bytes/1024:.1f} KB")
                if chunks >= 500:
                    print("Test successful")
                    break
        else:
            print("Failed.")
        conn.close()
    except Exception as e:
        print(f"HTTP/1.0 Error: {e}")

    # 4. Test Rapid Snapshots (Fallback viability)
    print("\n--- Testing Rapid Snapshots (Fallback) ---")
    try:
        count = 0
        start_t = time.time()
        for i in range(5):
            r = requests.get(f"{url}/api/camera_proxy/{entity_id}", headers=headers)
            if r.status_code == 200:
                print(f"Snapshot {i+1}: {len(r.content)} bytes, {time.time()-start_t:.2f}s elapsed")
            else:
                print(f"Snapshot {i+1} failed")
        end_t = time.time()
        fps = 5 / (end_t - start_t)
        print(f"Rapid Snapshot FPS: {fps:.2f}")
    except Exception as e:
        print(f"Rapid Snapshot Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_stream.py <camera_entity_id>")
        # Try to find a camera in config automatically
        config = load_config()
        first_camera = None
        for btn in config.get('buttons', []):
            if btn.get('type') == 'camera':
                first_camera = btn.get('entity_id')
                break
        
        if first_camera:
            print(f"Auto-detected camera: {first_camera}")
            test_stream(first_camera)
        else:
            print("No camera found in config.")
    else:
        test_stream(sys.argv[1])
