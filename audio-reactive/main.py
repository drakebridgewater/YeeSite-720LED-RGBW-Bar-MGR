"""
Audio-reactive lighting controller for YeeSite 720LED RGBW Bar.

Usage:
    python main.py                                  # artnet mode, freq_color mapping
    python main.py --mode controller                # use web controller SocketIO
    python main.py --mapping spectrum               # spectrum analyzer visualization
    python main.py --mapping beat_reactive          # hue-shifting beat pulses
    python main.py --device "BlackHole 2ch"         # capture system audio (requires BlackHole)
    python main.py --list-devices                   # show available input devices
"""
import argparse
import time

import numpy as np
import sounddevice as sd

import config
from analyzer import AudioAnalyzer
from artnet import ArtNetSender
from controller import ControllerClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hue_to_rgb(h: float) -> tuple[float, float, float]:
    """Hue 0.0–1.0 → (r, g, b) floats at full saturation."""
    h6 = (h % 1.0) * 6.0
    i  = int(h6) % 6
    f  = h6 - int(h6)
    sectors = [
        (1, f,   0),
        (1-f, 1, 0),
        (0, 1,   f),
        (0, 1-f, 1),
        (f, 0,   1),
        (1, 0,   1-f),
    ]
    return sectors[i]


def _clamp255(v: float) -> int:
    return max(0, min(255, int(v)))


# ---------------------------------------------------------------------------
# Audio → DMX mappings (return a 168-element list of ints 0–255)
# ---------------------------------------------------------------------------

def freq_color_dmx(analysis: dict, floor: float = 0.05) -> list[int]:
    """
    Frequency bands → hue:
      bass=red, mid=green, high=blue.
    RMS drives overall brightness.
    Beats flash the entire fixture white.
    """
    bass = analysis["bass"]
    mid  = analysis["mid"]
    high = analysis["high"]
    rms  = max(floor, analysis["rms"])

    total = bass + mid + high
    if total < 0.01:
        r, g, b = 0.33, 0.33, 0.33  # neutral when quiet
    else:
        r = bass / total
        g = mid  / total
        b = high / total

    if analysis["beat"]:
        # Bright white flash on beat
        val = 255
        dmx = [0] * 168
        for z in range(48):
            base = z * 3
            dmx[base] = dmx[base+1] = dmx[base+2] = val
        for w in range(24):
            dmx[144 + w] = val
        return dmx

    scale = rms * 255
    ri, gi, bi = _clamp255(r * scale), _clamp255(g * scale), _clamp255(b * scale)

    dmx = [0] * 168
    for z in range(48):
        base = z * 3
        dmx[base], dmx[base+1], dmx[base+2] = ri, gi, bi
    return dmx


def spectrum_dmx(analysis: dict, floor: float = 0.05) -> list[int]:
    """
    Spectrum analyzer: each of the 48 color zones gets brightness from its
    frequency bucket.  Bottom row (zones 0–23): low→high left to right.
    Top row (zones 24–47): high→low (mirrored, matches physical layout).
    Hue cycles through the rainbow per zone.
    White zones pulse with overall RMS.
    """
    spectrum = analysis["spectrum"]   # 48 floats, 0–1
    rms      = max(floor, analysis["rms"])

    dmx = [0] * 168
    for z in range(48):
        level = spectrum[z]
        h = z / 48.0
        r, g, b = _hue_to_rgb(h)
        base = z * 3
        dmx[base]   = _clamp255(r * level * 255)
        dmx[base+1] = _clamp255(g * level * 255)
        dmx[base+2] = _clamp255(b * level * 255)

    w_level = _clamp255(rms * 160)
    for w in range(24):
        dmx[144 + w] = w_level

    if analysis["beat"]:
        for w in range(24):
            dmx[144 + w] = 255

    return dmx


def beat_reactive_dmx(analysis: dict, state: dict, floor: float = 0.05) -> list[int]:
    """
    Ambient hue-shifting color that pulses white on each beat.
    Hue advances a step on every beat so the color slowly cycles.
    """
    rms  = max(floor, analysis["rms"])

    if analysis["beat"]:
        state["flash"]  = 1.0
        state["hue"]    = (state.get("hue", 0.0) + 0.13) % 1.0

    # Exponential flash decay
    flash = state.get("flash", 0.0)
    state["flash"] = flash * 0.75

    hue = state.get("hue", 0.0)
    r, g, b = _hue_to_rgb(hue)

    level = min(1.0, rms + flash)
    ri = _clamp255(r * level * 255)
    gi = _clamp255(g * level * 255)
    bi = _clamp255(b * level * 255)

    dmx = [0] * 168
    for z in range(48):
        base = z * 3
        dmx[base], dmx[base+1], dmx[base+2] = ri, gi, bi

    w_level = _clamp255(flash * 220)
    for w in range(24):
        dmx[144 + w] = w_level

    return dmx


# ---------------------------------------------------------------------------
# Run loops
# ---------------------------------------------------------------------------

def _status_line(analysis: dict):
    beat_tag = "[BEAT]" if analysis["beat"] else "      "
    print(
        f"\r{beat_tag} bass={analysis['bass']:.2f}  "
        f"mid={analysis['mid']:.2f}  high={analysis['high']:.2f}  "
        f"rms={analysis['rms']:.2f}   ",
        end="", flush=True,
    )


def run_artnet(analyzer: AudioAnalyzer, mapping: str):
    state = {"hue": 0.0, "flash": 0.0}

    with ArtNetSender(config.ARTNET_HOST, config.ARTNET_PORT, config.ARTNET_UNIVERSE) as sender:
        print(f"[artnet] → {config.ARTNET_HOST}:{config.ARTNET_PORT}  universe={config.ARTNET_UNIVERSE}")
        print(f"[artnet] mapping={mapping}   Ctrl+C to stop\n")

        try:
            while True:
                analysis = analyzer.process()
                if analysis:
                    if mapping == "spectrum":
                        dmx = spectrum_dmx(analysis, config.BRIGHTNESS_FLOOR)
                    elif mapping == "beat_reactive":
                        dmx = beat_reactive_dmx(analysis, state, config.BRIGHTNESS_FLOOR)
                    else:
                        dmx = freq_color_dmx(analysis, config.BRIGHTNESS_FLOOR)

                    sender.send(dmx)
                    _status_line(analysis)

                time.sleep(1 / 60)

        except KeyboardInterrupt:
            # Blackout on exit
            sender.send([0] * 168)
            print("\n[artnet] Stopped.")


def run_controller(analyzer: AudioAnalyzer, mapping: str):
    state        = {"hue": 0.0, "flash": 0.0}
    last_beat_t  = 0.0

    client = ControllerClient(config.CONTROLLER_URL)
    client.connect()

    print(f"[controller] mapping={mapping}   Ctrl+C to stop\n")

    try:
        while True:
            analysis = analyzer.process()
            if analysis:
                bass = analysis["bass"]
                mid  = analysis["mid"]
                high = analysis["high"]
                rms  = analysis["rms"]

                total = bass + mid + high
                if total < 0.01:
                    r, g, b = 128, 128, 128
                else:
                    r = _clamp255(bass / total * 255)
                    g = _clamp255(mid  / total * 255)
                    b = _clamp255(high / total * 255)

                client.set_color(r, g, b)
                client.set_brightness(max(config.BRIGHTNESS_FLOOR, rms))

                # Tie effect speed to BPM-ish signal: faster music = faster effects
                speed = 0.5 + rms * 3.0
                client.set_speed(speed)

                now = time.time()
                if analysis["beat"] and now - last_beat_t > 0.5:
                    client.beat_effect("beat_flash")
                    last_beat_t = now

                _status_line(analysis)

            time.sleep(1 / 30)

    except KeyboardInterrupt:
        client.stop()
        client.disconnect()
        print("\n[controller] Stopped.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def list_devices():
    print("\nAvailable audio INPUT devices:")
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0:
            marker = " *" if i == sd.default.device[0] else "  "
            print(f"{marker}[{i:2d}] {d['name']}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Audio-reactive lighting — YeeSite 720LED RGBW Bar",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--mode", choices=["artnet", "controller"], default=config.OUTPUT_MODE,
        help="artnet: direct UDP to fixture | controller: SocketIO to web controller",
    )
    parser.add_argument(
        "--mapping", choices=["freq_color", "spectrum", "beat_reactive"], default=config.MAPPING,
        help="Audio→light mapping algorithm",
    )
    parser.add_argument(
        "--device", default=None,
        help='Audio input device name or index (e.g. "BlackHole 2ch")',
    )
    parser.add_argument(
        "--list-devices", action="store_true",
        help="List available audio input devices and exit",
    )
    args = parser.parse_args()

    if args.list_devices:
        list_devices()
        return

    raw_device = args.device or config.AUDIO_DEVICE
    # sounddevice requires an int for index-based selection
    if raw_device is not None:
        try:
            device = int(raw_device)
        except (ValueError, TypeError):
            device = raw_device
    else:
        device = None
    print(f"Audio device : {device or 'system default'}")
    print("Starting analyzer...")

    analyzer = AudioAnalyzer(
        device=device,
        sample_rate=config.SAMPLE_RATE,
        chunk_size=config.CHUNK_SIZE,
        bass_range=config.BASS_RANGE,
        mid_range=config.MID_RANGE,
        high_range=config.HIGH_RANGE,
        beat_threshold=config.BEAT_THRESHOLD,
        beat_cooldown=config.BEAT_COOLDOWN,
        peak_decay=config.PEAK_DECAY,
    )
    analyzer.start()
    time.sleep(0.3)  # let the stream warm up

    try:
        if args.mode == "artnet":
            run_artnet(analyzer, args.mapping)
        else:
            run_controller(analyzer, args.mapping)
    finally:
        analyzer.stop()


if __name__ == "__main__":
    main()
