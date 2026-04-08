"""
Configuration for audio-reactive lighting.
Edit these values, or pass overrides via CLI flags.
"""

# --- Output mode ---
# "artnet"     : send ArtNet UDP directly to the fixture (lowest latency, full per-zone control)
# "controller" : SocketIO to the web controller (uses its effects engine)
OUTPUT_MODE = "artnet"

# --- ArtNet (direct to fixture) ---
ARTNET_HOST     = "10.0.15.109"
ARTNET_PORT     = 6454
# ArtNet universes are 0-indexed; OLA "Universe 1" = ArtNet universe 0
ARTNET_UNIVERSE = 0

# --- Web controller SocketIO ---
CONTROLLER_URL = "http://10.0.15.1:5003"  # update to your Unraid IP

# --- Fixture layout ---
NUM_COLOR_ZONES  = 48
NUM_WHITE_ZONES  = 24
TOTAL_CHANNELS   = 168  # 48*3 + 24

# --- Audio capture ---
SAMPLE_RATE  = 44100
CHUNK_SIZE   = 2048    # larger = better freq resolution, more latency (~23ms at 44100)
AUDIO_DEVICE = None    # None = system default; "BlackHole 2ch" for loopback capture

# Frequency bands (Hz)
BASS_RANGE  = (60,   250)
MID_RANGE   = (250,  2000)
HIGH_RANGE  = (2000, 8000)

# --- Beat detection ---
BEAT_THRESHOLD = 1.6   # multiplier above rolling average to trigger beat
BEAT_COOLDOWN  = 0.25  # minimum seconds between beats

# --- Normalization ---
# Running peak decays slowly; lower = adapts faster to quiet passages
PEAK_DECAY = 0.995

# --- Mapping ---
# "freq_color"    : bass→red, mid→green, high→blue; beat flashes white
# "spectrum"      : spectrum analyzer across all 48 zones, rainbow hue
# "beat_reactive" : hue-shifting color that pulses on beats
MAPPING = "freq_color"

# Minimum brightness so it's never completely dark (0.0–1.0)
BRIGHTNESS_FLOOR = 0.05
