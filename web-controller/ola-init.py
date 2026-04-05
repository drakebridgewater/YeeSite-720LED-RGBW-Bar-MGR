#!/usr/bin/env python3
"""
One-shot OLA configurator.
Waits for OLA to be ready, then patches the ArtNet output port to DMX_UNIVERSE.
OLA discovers the eDMX1-PRO via ArtPoll once network reachable — this script
just wires the discovered port to the right universe automatically.
"""
import os, sys, time
import requests

OLA_URL    = f"http://{os.environ.get('OLA_HOST', 'localhost')}:{os.environ.get('OLA_PORT', '9090')}"
UNIVERSE   = int(os.environ.get('DMX_UNIVERSE', '1'))
ARTNET_IP  = os.environ.get('ARTNET_IP', '')

print(f"[ola-init] target={ARTNET_IP}  universe={UNIVERSE}  ola={OLA_URL}")

# ── Wait for OLA HTTP API ────────────────────────────────────────────────────
for attempt in range(30):
    try:
        requests.get(f"{OLA_URL}/json/server_stats", timeout=2).raise_for_status()
        print("[ola-init] OLA is up.")
        break
    except Exception:
        print(f"[ola-init] waiting for OLA... ({attempt + 1}/30)")
        time.sleep(2)
else:
    print("[ola-init] ERROR: OLA did not become ready in time.")
    sys.exit(1)

# ── Get available ports ──────────────────────────────────────────────────────
# Give OLA a moment to finish loading plugins and run its ArtPoll discovery
time.sleep(3)

ports = requests.get(f"{OLA_URL}/json/get_ports").json()

for device in ports:
    if 'ArtNet' not in device.get('device_name', ''):
        continue
    for port in device.get('output_ports', []):
        alias = device['device_alias']
        pid   = port['port_id']

        if port.get('patched'):
            print(f"[ola-init] ArtNet {alias}:{pid} already patched to universe {port.get('universe')} — skipping.")
            sys.exit(0)

        r = requests.post(f"{OLA_URL}/json/patch", data={
            'action':    'patch',
            'device':    alias,
            'port':      pid,
            'is_output': 1,
            'universe':  UNIVERSE,
        })
        print(f"[ola-init] Patched ArtNet {alias}:{pid} → universe {UNIVERSE}  HTTP {r.status_code}")
        sys.exit(0)

# No ArtNet port found — OLA may need more time for ArtPoll to reach the device
print("[ola-init] No ArtNet output port found yet.")
print(f"[ola-init] Verify {ARTNET_IP} is reachable and check the OLA UI at {OLA_URL}")
sys.exit(1)
