#!/bin/bash
set -e

echo "[entrypoint] Starting raveloxmidi (RTP-MIDI daemon for iOS Network MIDI)..."
raveloxmidi -c /etc/raveloxmidi/raveloxmidi.conf -d
sleep 2  # Wait for ALSA virtual port to register

echo "[entrypoint] Starting avahi-daemon (mDNS for iOS auto-discovery)..."
avahi-daemon --no-drop-root --daemonize || echo "[entrypoint] avahi-daemon unavailable (manual IP pairing still works)"

echo "[entrypoint] Starting YeeSite web controller..."
exec python server.py
