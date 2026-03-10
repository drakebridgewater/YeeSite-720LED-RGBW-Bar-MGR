"""
Configuration for the YeeSite 720LED RGBW Bar web controller.

Physical layout (6 LEDs tall x 120 LEDs wide, zones are 2x5 LEDs):
  Top row:     24 color zones (RGB) — DMX zones 25-48, physically R→L (counter-clockwise)
  Middle row:  24 white zones (W)   — left to right
  Bottom row:  24 color zones (RGB) — DMX zones 1-24, physically L→R

168-channel DMX:
  Ch 0-143:   48 color zones × 3 (R, G, B)
  Ch 144-167: 24 white zones × 1

All values can be overridden via environment variables for Docker deployment.
"""

import os

OLA_HOST = os.environ.get("OLA_HOST", "10.0.0.10")
OLA_PORT = int(os.environ.get("OLA_PORT", "9090"))
OLA_URL = f"http://{OLA_HOST}:{OLA_PORT}"

DMX_UNIVERSE = int(os.environ.get("DMX_UNIVERSE", "1"))

COLUMNS = 24
NUM_COLOR_ZONES = 48
NUM_WHITE_ZONES = 24
CHANNELS_PER_COLOR_ZONE = 3  # R, G, B
CHANNELS_PER_WHITE_ZONE = 1
TOTAL_CHANNELS = NUM_COLOR_ZONES * CHANNELS_PER_COLOR_ZONE + NUM_WHITE_ZONES  # 168

FPS = int(os.environ.get("FPS", "60"))
FRAME_TIME = 1.0 / FPS

WEB_HOST = os.environ.get("WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.environ.get("WEB_PORT", "5003"))


def color_zone_channels(zone_idx):
    """Return (r_ch, g_ch, b_ch) for a 0-indexed color zone (0-47)."""
    base = zone_idx * 3
    return base, base + 1, base + 2


def white_zone_channel(wzone_idx):
    """Return the DMX channel for a 0-indexed white zone (0-23)."""
    return 144 + wzone_idx


def col_to_bottom_zone(col):
    """Physical column (0-23, L→R) → bottom color zone index."""
    return col


def col_to_top_zone(col):
    """Physical column (0-23, L→R) → top color zone index.
    Top row runs R→L in DMX order (counter-clockwise), so col 0 → zone 47."""
    return 47 - col
