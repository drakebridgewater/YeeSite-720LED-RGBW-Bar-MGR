#!/bin/bash
set -e

echo "[entrypoint] Starting avahi-daemon (mDNS for iOS auto-discovery)..."
avahi-daemon --no-drop-root --daemonize || echo "[entrypoint] avahi-daemon unavailable (manual IP pairing still works)"

echo "[entrypoint] Starting YeeSite web controller..."
exec python server.py
