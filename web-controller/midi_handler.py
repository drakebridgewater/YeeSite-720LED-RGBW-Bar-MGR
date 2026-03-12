"""
MIDI handler for YeeSite lighting controller.

Connects to raveloxmidi's ALSA virtual port and translates MIDI events
into lighting state changes.

MIDI layout (MPK Mini defaults):
  Ch1  (0-indexed: 0) — piano keys + knobs
  Ch10 (0-indexed: 9) — drum pads

Designed for graceful degradation: if python-rtmidi or ALSA is unavailable,
the module loads and all methods are no-ops so the web controller still runs.
"""

import collections
import logging
import threading
import time

log = logging.getLogger(__name__)

try:
    import rtmidi
    RTMIDI_AVAILABLE = True
except ImportError:
    RTMIDI_AVAILABLE = False
    log.warning("python-rtmidi not installed; MIDI disabled")

# MIDI channel constants (0-indexed)
MIDI_CH_KEYS = 0   # Ch1 in 1-indexed notation
MIDI_CH_PADS = 9   # Ch10 in 1-indexed notation

# Shared state dict — written by MIDI callback thread, read by animation_loop.
# All individual key assignments are atomic at the GIL level.
midi_state = {
    "mode": "idle",             # "idle" | "reactive" | "effect"
    "active_notes": {},         # {note_int: velocity_int} currently held keys
    "zones": [(0, 0, 0)] * 48, # per-zone RGB target (bottom 0-23, top 24-47)
    "zone_brightness": [0.0] * 48,
    "flash_brightness": 0.0,    # decays each frame in the midi_reactive generator
    "manual_hue": 0.0,
    "manual_sat": 1.0,
    "midi_connected": False,
    "last_event": None,         # human-readable string for UI display
    # Clock sync
    "bpm": 0.0,
    "beat_phase": 0.0,          # 0.0–1.0 position within current beat
    "beat_count": 0,            # total beats received since last Start
    "clock_running": False,
}

COLUMNS = 24  # number of physical columns on the bar


def _hsv_to_rgb(h, s, v):
    """HSV (h=0-360, s/v=0-1) → (r, g, b) 0-255 each."""
    h = h % 360
    c = v * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = v - c
    if h < 60:    r, g, b = c, x, 0
    elif h < 120: r, g, b = x, c, 0
    elif h < 180: r, g, b = 0, c, x
    elif h < 240: r, g, b = 0, x, c
    elif h < 300: r, g, b = x, 0, c
    else:         r, g, b = c, 0, x
    return int((r + m) * 255), int((g + m) * 255), int((b + m) * 255)


class MidiHandler:
    """
    Listens for MIDI messages via python-rtmidi (ALSA backend on Linux).

    Callbacks wired by server.py after import to avoid circular imports:
      on_pad_trigger(effect_name: str)
      on_color_preset(r, g, b, w)
      on_cc_brightness(value: float)
      on_cc_speed(value: float)
      on_cc_rgb_dimmer(value: float)
      on_cc_white_dimmer(value: float)
      on_cc_color_strobe_rate(hz: float)   # 1–30 Hz
      on_cc_white_strobe_rate(hz: float)   # 1–30 Hz
      on_cc_manual_color(r, g, b)          # hue/sat knobs → solid color (non-reactive mode only)
      on_stop()
    """

    # Bank A pads → effect names (None = stop)
    PAD_EFFECTS = {
        36: "rainbow_chase",
        37: "police",
        38: "fire",
        39: "breathe",
        40: "sparkle",
        41: "knight_rider",
        42: "strobe",
        43: None,  # Stop all
    }

    # Bank B pads → (r, g, b, w) color presets
    PAD_COLORS = {
        44: (255, 0, 0, 0),        # Red
        45: (0, 255, 0, 0),        # Green
        46: (0, 0, 255, 0),        # Blue
        47: (255, 255, 255, 255),  # White
        48: (0, 255, 255, 0),      # Cyan
        49: (255, 255, 0, 0),      # Yellow
        50: (128, 0, 255, 0),      # Purple
        51: (0, 0, 0, 0),          # All Off
    }

    def __init__(self, port_name_substring="raveloxmidi"):
        self.available = False
        self.port_name = port_name_substring
        self._midi_in = None

        # Callbacks set by server.py
        self.on_pad_trigger = None
        self.on_color_preset = None
        self.on_cc_brightness = None
        self.on_cc_speed = None
        self.on_cc_rgb_dimmer = None
        self.on_cc_white_dimmer = None
        self.on_cc_color_strobe_rate = None
        self.on_cc_white_strobe_rate = None
        self.on_cc_manual_color = None
        self.on_stop = None
        self.on_beat = None   # called each quarter-note downbeat with {"bpm": float, "beat_count": int}

        # Clock sync state
        self._clock_times = collections.deque(maxlen=24)
        self._clock_pulse_count = 0

        if not RTMIDI_AVAILABLE:
            return

        try:
            self._midi_in = rtmidi.MidiIn()
            self.available = True
        except Exception as e:
            log.warning(f"Could not initialise rtmidi: {e}")

    def find_port(self, retries=12, delay=1.0):
        """Find the raveloxmidi ALSA port by name substring, retrying up to retries×delay seconds."""
        if not self.available:
            return None
        for attempt in range(retries):
            ports = self._midi_in.get_ports()
            for i, name in enumerate(ports):
                if self.port_name.lower() in name.lower():
                    log.info(f"MIDI: found port {i}: '{name}'")
                    return i
            log.debug(f"MIDI: port not found (attempt {attempt + 1}/{retries}), retrying in {delay}s…")
            time.sleep(delay)
        log.error(f"MIDI: could not find port matching '{self.port_name}' after {retries} attempts")
        return None

    def start(self, port_index=None):
        """Open the MIDI port and start listening. Launches watchdog for auto-reconnect."""
        if not self.available:
            log.warning("MIDI: not available, skipping start")
            return

        # Initial connection (blocks up to ~12 s while raveloxmidi starts up)
        if port_index is None:
            port_index = self.find_port()
        if port_index is not None:
            self._open_port(port_index)

        # Watchdog runs forever — reconnects if port disappears (e.g. raveloxmidi restart)
        t = threading.Thread(target=self._reconnect_loop, daemon=True)
        t.start()

    def _open_port(self, port_index):
        """Open (or re-open) a port by index. Returns True on success."""
        try:
            try:
                self._midi_in.close_port()
            except Exception:
                pass
            self._midi_in.open_port(port_index)
            self._midi_in.ignore_types(sysex=True, timing=False, active_sense=True)
            self._midi_in.set_callback(self._on_midi_message)
            midi_state["midi_connected"] = True
            log.info("MIDI: port opened — waiting for iPad")
            return True
        except Exception as e:
            log.error(f"MIDI: failed to open port: {e}")
            return False

    def _reconnect_loop(self):
        """Poll every 10 s; reconnect if the named port disappears or was never opened."""
        POLL = 10.0
        while self.available:
            time.sleep(POLL)
            try:
                ports = self._midi_in.get_ports()
                port_alive = any(self.port_name.lower() in p.lower() for p in ports)
            except Exception:
                port_alive = False

            if not port_alive:
                if midi_state["midi_connected"]:
                    log.warning("MIDI: port lost — will reconnect when available")
                    midi_state["midi_connected"] = False
                continue  # port not there yet; try again next cycle

            # Port exists but we're not connected (lost session or initial failure)
            if not midi_state["midi_connected"]:
                idx = self.find_port(retries=1, delay=0.0)
                if idx is not None:
                    log.info("MIDI: reconnecting…")
                    self._open_port(idx)

    def stop(self):
        self.available = False   # signals _reconnect_loop to exit
        if self._midi_in:
            try:
                self._midi_in.close_port()
            except Exception:
                pass
        midi_state["midi_connected"] = False

    # ------------------------------------------------------------------
    # Internal MIDI callback (runs in rtmidi's own thread)
    # ------------------------------------------------------------------

    def _on_midi_message(self, event, data=None):
        message, _delta = event
        if not message:
            return

        status = message[0]

        # System Real-Time messages are single bytes (0xF8–0xFF), no channel
        if status == 0xF8:   # Clock pulse
            self._handle_clock()
            return
        if status == 0xFA or status == 0xFB:   # Start / Continue
            self._handle_clock_start()
            return
        if status == 0xFC:   # Stop
            self._handle_clock_stop()
            return

        msg_type = status & 0xF0
        channel = status & 0x0F

        if msg_type == 0x90 and len(message) >= 3:
            note, velocity = message[1], message[2]
            if velocity == 0:
                self._handle_note_off(channel, note)
            else:
                self._handle_note_on(channel, note, velocity)
        elif msg_type == 0x80 and len(message) >= 3:
            self._handle_note_off(channel, message[1])
        elif msg_type == 0xB0 and len(message) >= 3:
            self._handle_cc(channel, message[1], message[2])

    # ------------------------------------------------------------------
    # MIDI Clock handlers
    # ------------------------------------------------------------------

    def _handle_clock_start(self):
        """0xFA (Start) or 0xFB (Continue): reset and begin counting pulses."""
        self._clock_pulse_count = 0
        self._clock_times.clear()
        midi_state["clock_running"] = True
        midi_state["beat_count"] = 0
        midi_state["bpm"] = 0.0
        midi_state["beat_phase"] = 0.0

    def _handle_clock_stop(self):
        """0xFC (Stop): mark clock as not running."""
        midi_state["clock_running"] = False
        midi_state["beat_phase"] = 0.0

    def _handle_clock(self):
        """0xF8 (Clock): 24 pulses per quarter note — compute BPM and beat phase."""
        if not midi_state["clock_running"]:
            return

        now = time.monotonic()
        self._clock_pulse_count += 1
        self._clock_times.append(now)

        # Compute BPM from rolling window of timestamps
        if len(self._clock_times) >= 2:
            total_time = self._clock_times[-1] - self._clock_times[0]
            num_intervals = len(self._clock_times) - 1
            if num_intervals > 0 and total_time > 0:
                avg_interval = total_time / num_intervals
                midi_state["bpm"] = round(60.0 / (avg_interval * 24), 1)

        # Beat phase: position 0.0–1.0 within the current quarter note
        pulse_in_beat = self._clock_pulse_count % 24
        midi_state["beat_phase"] = pulse_in_beat / 24.0

        # Fire on_beat at the downbeat of each quarter note
        if pulse_in_beat == 0:
            midi_state["beat_count"] += 1
            if self.on_beat:
                self.on_beat({
                    "bpm": midi_state["bpm"],
                    "beat_count": midi_state["beat_count"],
                })

    def _handle_note_on(self, channel, note, velocity):
        if channel == MIDI_CH_PADS:
            self._handle_pad(note, velocity)
        elif channel == MIDI_CH_KEYS:
            self._handle_key_on(note, velocity)

    def _handle_note_off(self, channel, note):
        if channel == MIDI_CH_KEYS:
            midi_state["active_notes"].pop(note, None)
            # zone_brightness decays naturally each frame in midi_reactive

    def _handle_pad(self, note, velocity):
        """MPK Mini pad hit → effect trigger or color preset."""
        if note in self.PAD_EFFECTS:
            effect = self.PAD_EFFECTS[note]
            midi_state["last_event"] = f"Pad {note - 35}: {'stop' if effect is None else effect}"
            if effect is None:
                if self.on_stop:
                    self.on_stop()
            else:
                midi_state["mode"] = "effect"
                if self.on_pad_trigger:
                    self.on_pad_trigger(effect)

        elif note in self.PAD_COLORS:
            r, g, b, w = self.PAD_COLORS[note]
            midi_state["last_event"] = f"Pad {note - 35}: color ({r},{g},{b},{w})"
            midi_state["mode"] = "color"
            if self.on_color_preset:
                self.on_color_preset(r, g, b, w)

    def _handle_key_on(self, note, velocity):
        """Piano key down → music-reactive zone coloring."""
        midi_state["mode"] = "reactive"
        midi_state["active_notes"][note] = velocity
        midi_state["last_event"] = f"Note {note} vel {velocity}"

        # Recompute all zones from every currently-held note so chords blend.
        new_zones = [(0, 0, 0)] * 48
        new_brightness = [0.0] * 48

        for held_note, held_vel in midi_state["active_notes"].items():
            pitch_class = held_note % 12
            hue = pitch_class * 30.0  # 12 pitch classes × 30° = full 360°

            # Octave → horizontal position (MIDI oct 2-8 → col 0-23)
            octave = held_note // 12
            col_center = max(0, min(COLUMNS - 1, int(((octave - 2) / 6.0) * (COLUMNS - 1))))

            vel_n = held_vel / 127.0
            r, g, b = _hsv_to_rgb(hue, midi_state["manual_sat"], 1.0)

            spread = 4  # columns affected around col_center
            for col in range(COLUMNS):
                dist = abs(col - col_center)
                if dist <= spread:
                    factor = (1.0 - dist / (spread + 1)) ** 1.5 * vel_n
                    nr, ng, nb = new_zones[col]
                    # Bottom zones (0-23) and top zones (24-47) both get the color
                    new_zones[col] = (
                        min(255, nr + int(r * factor)),
                        min(255, ng + int(g * factor)),
                        min(255, nb + int(b * factor)),
                    )
                    new_zones[col + 24] = new_zones[col]  # mirror top row
                    new_brightness[col] = min(1.0, new_brightness[col] + factor)
                    new_brightness[col + 24] = new_brightness[col]

        midi_state["zones"] = new_zones
        midi_state["zone_brightness"] = new_brightness
        midi_state["flash_brightness"] = velocity / 127.0

    def _handle_cc(self, channel, cc, value):
        """Knob CC → parameter change."""
        if channel != MIDI_CH_KEYS:
            return
        normalized = value / 127.0
        midi_state["last_event"] = f"CC{cc}={value}"

        cc_actions = {
            70: lambda v: self.on_cc_brightness(v) if self.on_cc_brightness else None,
            71: lambda v: self.on_cc_speed(0.1 + v * 4.9) if self.on_cc_speed else None,
            72: lambda v: self.on_cc_rgb_dimmer(v) if self.on_cc_rgb_dimmer else None,
            73: lambda v: self.on_cc_white_dimmer(v) if self.on_cc_white_dimmer else None,
            76: lambda v: self.on_cc_color_strobe_rate(1.0 + v * 29.0) if self.on_cc_color_strobe_rate else None,
            77: lambda v: self.on_cc_white_strobe_rate(1.0 + v * 29.0) if self.on_cc_white_strobe_rate else None,
        }

        if cc in cc_actions:
            cc_actions[cc](normalized)
        elif cc == 74:
            midi_state["manual_hue"] = normalized * 360.0
            if self.on_cc_manual_color and midi_state["mode"] != "reactive":
                r, g, b = _hsv_to_rgb(midi_state["manual_hue"], midi_state["manual_sat"], 1.0)
                self.on_cc_manual_color(r, g, b)
        elif cc == 75:
            midi_state["manual_sat"] = max(0.0, min(1.0, normalized))
            if self.on_cc_manual_color and midi_state["mode"] != "reactive":
                r, g, b = _hsv_to_rgb(midi_state["manual_hue"], midi_state["manual_sat"], 1.0)
                self.on_cc_manual_color(r, g, b)
