# audio-reactive

Real-time audio → lighting controller for the YeeSite 720LED RGBW Bar.

## Setup

### 1. Install dependencies

```bash
cd audio-reactive
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Capture system audio (optional but recommended)

Install [BlackHole](https://existential.audio/blackhole/) (free virtual audio device):

```bash
brew install blackhole-2ch
```

Then in **Audio MIDI Setup** (macOS):
1. Create a **Multi-Output Device** containing both your speakers and BlackHole 2ch
2. Set your system audio output to that Multi-Output Device
3. Run with `--device "BlackHole 2ch"` to capture whatever's playing

Without BlackHole, the script captures from the system default input (usually your mic).

### 3. Configure

Edit `config.py`:
- `ARTNET_HOST` — fixture IP (default `10.0.15.109`)
- `ARTNET_UNIVERSE` — ArtNet universe (default `0`; OLA "Universe 1" = ArtNet 0)
- `CONTROLLER_URL` — web controller URL for `--mode controller`

## Usage

```bash
# List available audio input devices
python main.py --list-devices

# Direct ArtNet, default mapping (freq → color)
python main.py

# Capture system audio via BlackHole
python main.py --device "BlackHole 2ch"

# Spectrum analyzer across all 48 zones
python main.py --mapping spectrum

# Hue-shifting beats
python main.py --mapping beat_reactive

# Use web controller instead of direct ArtNet
python main.py --mode controller
```

## Mappings

| Mapping | Description |
|---|---|
| `freq_color` | bass=red, mid=green, high=blue; brightness from RMS; beats flash white |
| `spectrum` | 48-zone spectrum analyzer with rainbow hue; white zones pulse on beat |
| `beat_reactive` | Solid hue-shifting color; hue advances and brightness spikes on each beat |

## TouchDesigner

If you're also using TouchDesigner, you can have both running simultaneously — just point them at different ArtNet universes, or let TouchDesigner take over by stopping this script. Direct ArtNet means no coordination needed.

## Tuning tips

- **Sensitivity**: lower `BEAT_THRESHOLD` in `config.py` (try `1.3`) if beats aren't detecting
- **Too many false beats**: raise `BEAT_THRESHOLD` or increase `BEAT_COOLDOWN`
- **Adapts too slowly to quiet/loud songs**: lower `PEAK_DECAY` (e.g. `0.99`)
- **Feels laggy**: decrease `CHUNK_SIZE` to `1024` (less freq resolution, lower latency)
