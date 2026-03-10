#!/usr/bin/env python3
"""
YeeSite LED Bar Web Controller — Flask + SocketIO backend.

Drives 48 color zones (RGB, 3ch each) + 24 white zones (1ch each) = 168 channels
through OLA's REST API.
"""

import threading
import time
import requests
from flask import Flask, send_from_directory, jsonify, request
from flask_socketio import SocketIO

from config import (
    OLA_URL, DMX_UNIVERSE, NUM_COLOR_ZONES, NUM_WHITE_ZONES,
    TOTAL_CHANNELS, COLUMNS, FPS, FRAME_TIME, WEB_HOST, WEB_PORT,
    color_zone_channels, white_zone_channel, col_to_bottom_zone, col_to_top_zone,
)
from effects import EFFECTS, WHITE_EFFECTS

app = Flask(__name__, static_folder="static")
app.config["SECRET_KEY"] = "yeesite-ctrl"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")


# ---- LAMP REGISTRY ----
# Each lamp is a dict with an id, name, type, and a reference to its state/control.
# Extend this dict to add more fixtures in the future.

LAMPS = {}


class Lamp:
    """Base lamp abstraction. Subclass or extend for different fixture types."""

    def __init__(self, lamp_id, name, lamp_type="generic"):
        self.id = lamp_id
        self.name = name
        self.type = lamp_type
        LAMPS[lamp_id] = self

    def get_state(self):
        return {"id": self.id, "name": self.name, "type": self.type, "state": "off"}

    def turn_on(self, **kwargs):
        pass

    def turn_off(self):
        pass


# ---- DMX STATE ----
dmx = [0] * TOTAL_CHANNELS
brightness = 1.0
blackout = False
current_effect = None
effect_gen = None
effect_speed = 1.0
rgb_dimmer = 1.0
effect_lock = threading.Lock()

current_white_effect = None
white_effect_gen = None
white_effect_speed = 1.0
white_dimmer = 1.0
white_effect_lock = threading.Lock()

color_strobe_rate = 8.0   # Hz for color strobe effect
white_strobe_rate = 8.0   # Hz for white strobe effect

fade_from = None
fade_to = None
fade_start = 0.0
fade_duration = 0.0
fade_lock = threading.Lock()


def set_color_zone(zone_idx, r, g, b):
    rc, gc, bc = color_zone_channels(zone_idx)
    dmx[rc] = r
    dmx[gc] = g
    dmx[bc] = b


def set_white_zone(wzone_idx, val):
    dmx[white_zone_channel(wzone_idx)] = val


def set_column(col, r, g, b, w=0):
    set_color_zone(col_to_bottom_zone(col), r, g, b)
    set_color_zone(col_to_top_zone(col), r, g, b)
    set_white_zone(col, w)


def set_all(r, g, b, w=0):
    for col in range(COLUMNS):
        set_column(col, r, g, b, w)


def apply_frame(frame):
    """Apply effect frame to color zones, scaled by rgb_dimmer."""
    d = rgb_dimmer
    for z in range(NUM_COLOR_ZONES):
        r, g, b = frame["color"][z]
        set_color_zone(z, int(r * d), int(g * d), int(b * d))


def apply_white_frame(wframe):
    """Apply white effect frame to white zones, scaled by white_dimmer."""
    d = white_dimmer
    for i in range(NUM_WHITE_ZONES):
        set_white_zone(i, int(wframe[i] * d))


def get_display_state():
    bottom = []
    for col in range(COLUMNS):
        z = col_to_bottom_zone(col)
        rc, gc, bc = color_zone_channels(z)
        bottom.append({"r": dmx[rc], "g": dmx[gc], "b": dmx[bc]})

    top = []
    for col in range(COLUMNS):
        z = col_to_top_zone(col)
        rc, gc, bc = color_zone_channels(z)
        top.append({"r": dmx[rc], "g": dmx[gc], "b": dmx[bc]})

    white = []
    for w in range(NUM_WHITE_ZONES):
        white.append({"w": dmx[white_zone_channel(w)]})

    return {"top": top, "middle": white, "bottom": bottom}


def push_to_ola():
    if blackout:
        values = [0] * TOTAL_CHANNELS
    else:
        values = [max(0, min(255, int(v * brightness))) for v in dmx]

    csv = ",".join(str(v) for v in values)
    try:
        requests.post(f"{OLA_URL}/set_dmx", data={"u": DMX_UNIVERSE, "d": csv}, timeout=0.1)
    except requests.RequestException:
        pass


# ---- ANIMATION ENGINE ----

DISPLAY_FPS = 40
DISPLAY_INTERVAL = 1.0 / DISPLAY_FPS

def start_fade(target_dmx, duration):
    """Begin a crossfade from current DMX state to target over duration seconds."""
    global fade_from, fade_to, fade_start, fade_duration
    with fade_lock:
        fade_from = list(dmx)
        fade_to = list(target_dmx)
        fade_start = time.monotonic()
        fade_duration = max(0.0, duration)


def animation_loop():
    global fade_from, fade_to
    last_display = 0.0
    while True:
        with effect_lock:
            gen = effect_gen
            spd = effect_speed

        with white_effect_lock:
            wgen = white_effect_gen
            wspd = white_effect_speed

        # Fade interpolation
        with fade_lock:
            if fade_from is not None and fade_to is not None and fade_duration > 0:
                elapsed = time.monotonic() - fade_start
                t = min(1.0, elapsed / fade_duration)
                for i in range(TOTAL_CHANNELS):
                    dmx[i] = int(fade_from[i] + (fade_to[i] - fade_from[i]) * t)
                if t >= 1.0:
                    fade_from = None
                    fade_to = None

        if gen is not None:
            steps = max(1, int(spd))
            for _ in range(steps):
                try:
                    frame = next(gen)
                    apply_frame(frame)
                except StopIteration:
                    break

        if wgen is not None:
            wsteps = max(1, int(wspd))
            for _ in range(wsteps):
                try:
                    wframe = next(wgen)
                    apply_white_frame(wframe)
                except StopIteration:
                    break

        now = time.monotonic()
        if now - last_display >= DISPLAY_INTERVAL:
            push_to_ola()
            socketio.emit("frame", get_display_state())
            last_display = now

        fastest = max(spd if gen else 1.0, wspd if wgen else 1.0)
        time.sleep(FRAME_TIME / max(0.1, min(fastest, 3.0)))


# ---- ROUTES ----

@app.route("/")
def index():
    return send_from_directory("static", "index.html")

@app.route("/<path:path>")
def static_files(path):
    return send_from_directory("static", path)

def hex_to_rgb(h):
    h = h.lstrip("#")
    if len(h) != 6:
        return (0, 0, 0)
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def build_effect_kwargs(name, color_overrides):
    """Convert a dict of {param_key: "#hex"} into kwargs with RGB tuples."""
    meta = EFFECTS.get(name, {})
    kwargs = {}
    for slot in meta.get("colors", []):
        key = slot["key"]
        hex_val = color_overrides.get(key, slot["default"])
        kwargs[key] = hex_to_rgb(hex_val)
    return kwargs


# ---- YEESITE BAR LAMP ----

class YeeSiteBarLamp(Lamp):
    """The YeeSite 720-LED RGBW bar driven through OLA/DMX."""

    def __init__(self):
        super().__init__("yeesite-bar", "YeeSite LED Bar", lamp_type="dmx-rgbw-bar")

    def get_state(self):
        effect_list = list(EFFECTS.keys()) + list(WHITE_EFFECTS.keys())
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "state": "off" if blackout else "on",
            "brightness": round(brightness * 255),
            "color": {"r": dmx[0], "g": dmx[1], "b": dmx[2]},
            "white": dmx[white_zone_channel(0)] if NUM_WHITE_ZONES > 0 else 0,
            "effect": current_effect or current_white_effect,
            "effect_list": effect_list,
            "effect_speed": effect_speed,
            "rgb_dimmer": round(rgb_dimmer * 100),
            "white_dimmer": round(white_dimmer * 100),
            "color_strobe_rate": color_strobe_rate,
            "white_strobe_rate": white_strobe_rate,
            "display": get_display_state(),
        }

    def turn_on(self, **kwargs):
        global blackout, brightness, current_effect, effect_gen
        global current_white_effect, white_effect_gen, effect_speed

        blackout = False

        if "brightness" in kwargs:
            brightness = max(0.0, min(1.0, kwargs["brightness"] / 255))

        eff = kwargs.get("effect")
        if eff and eff in EFFECTS:
            colors = kwargs.get("colors", {})
            ek = build_effect_kwargs(eff, colors)
            with effect_lock:
                current_effect = eff
                effect_gen = EFFECTS[eff]["fn"](**ek)
            if "speed" in kwargs:
                self._set_speed(kwargs["speed"])
            return

        if eff and eff in WHITE_EFFECTS:
            with white_effect_lock:
                current_white_effect = eff
                white_effect_gen = WHITE_EFFECTS[eff]["fn"]()
            return

        color = kwargs.get("color", {}) if isinstance(kwargs.get("color"), dict) else {}
        r = int(kwargs.get("r", color.get("r", 0)))
        g = int(kwargs.get("g", color.get("g", 0)))
        b = int(kwargs.get("b", color.get("b", 0)))
        w = int(kwargs.get("w", color.get("w", 0)))

        if r or g or b or w:
            with effect_lock:
                current_effect = None
                effect_gen = None
            set_all(r, g, b, w)

    def turn_off(self):
        global blackout
        blackout = True

    def _set_speed(self, val):
        global effect_speed
        effect_speed = max(0.1, min(10.0, float(val)))


yeesite_bar = YeeSiteBarLamp()


# ---- LAMP API (Home Assistant compatible) ----

@app.route("/api/lamps")
def api_lamps():
    return jsonify({
        "lamps": [{"id": l.id, "name": l.name, "type": l.type} for l in LAMPS.values()]
    })


@app.route("/api/lamps/<lamp_id>")
def api_lamp_state(lamp_id):
    lamp = LAMPS.get(lamp_id)
    if not lamp:
        return jsonify({"error": "lamp not found"}), 404
    return jsonify(lamp.get_state())


@app.route("/api/lamps/<lamp_id>/turn_on", methods=["POST"])
def api_lamp_turn_on(lamp_id):
    lamp = LAMPS.get(lamp_id)
    if not lamp:
        return jsonify({"error": "lamp not found"}), 404
    data = request.json or {}
    lamp.turn_on(**data)
    return jsonify(lamp.get_state())


@app.route("/api/lamps/<lamp_id>/turn_off", methods=["POST"])
def api_lamp_turn_off(lamp_id):
    lamp = LAMPS.get(lamp_id)
    if not lamp:
        return jsonify({"error": "lamp not found"}), 404
    lamp.turn_off()
    return jsonify(lamp.get_state())


@app.route("/api/lamps/<lamp_id>/color", methods=["POST"])
def api_lamp_color(lamp_id):
    lamp = LAMPS.get(lamp_id)
    if not lamp:
        return jsonify({"error": "lamp not found"}), 404
    data = request.json or {}
    lamp.turn_on(color=data)
    return jsonify(lamp.get_state())


@app.route("/api/lamps/<lamp_id>/effect", methods=["POST"])
def api_lamp_effect(lamp_id):
    lamp = LAMPS.get(lamp_id)
    if not lamp:
        return jsonify({"error": "lamp not found"}), 404
    data = request.json or {}
    lamp.turn_on(effect=data.get("name"), colors=data.get("colors", {}), speed=data.get("speed", 1.0))
    return jsonify(lamp.get_state())


@app.route("/api/lamps/<lamp_id>/brightness", methods=["POST"])
def api_lamp_brightness(lamp_id):
    lamp = LAMPS.get(lamp_id)
    if not lamp:
        return jsonify({"error": "lamp not found"}), 404
    data = request.json or {}
    lamp.turn_on(brightness=int(data.get("value", 255)))
    return jsonify(lamp.get_state())


@app.route("/api/lamps/<lamp_id>/stop", methods=["POST"])
def api_lamp_stop(lamp_id):
    lamp = LAMPS.get(lamp_id)
    if not lamp:
        return jsonify({"error": "lamp not found"}), 404
    global current_effect, effect_gen, current_white_effect, white_effect_gen
    with effect_lock:
        current_effect = None
        effect_gen = None
    with white_effect_lock:
        current_white_effect = None
        white_effect_gen = None
    set_all(0, 0, 0, 0)
    lamp.turn_on()
    return jsonify(lamp.get_state())


# ---- LEGACY API (used by web UI) ----

@app.route("/api/state")
def api_state():
    effects_out = {}
    for k, v in EFFECTS.items():
        effects_out[k] = {
            "name": v["name"],
            "category": v["category"],
            "colors": v.get("colors", []),
        }
    white_effects_out = {}
    for k, v in WHITE_EFFECTS.items():
        white_effects_out[k] = {
            "name": v["name"],
            "category": v["category"],
        }
    return jsonify({
        "display": get_display_state(),
        "brightness": brightness,
        "blackout": blackout,
        "effect": current_effect,
        "effect_speed": effect_speed,
        "rgb_dimmer": rgb_dimmer,
        "effects": effects_out,
        "white_effect": current_white_effect,
        "white_effect_speed": white_effect_speed,
        "white_dimmer": white_dimmer,
        "white_effects": white_effects_out,
        "columns": COLUMNS,
        "color_strobe_rate": color_strobe_rate,
        "white_strobe_rate": white_strobe_rate,
    })


@app.route("/api/color", methods=["POST"])
def api_color():
    global current_effect, effect_gen, current_white_effect, white_effect_gen
    data = request.json
    with effect_lock:
        current_effect = None
        effect_gen = None
    with white_effect_lock:
        current_white_effect = None
        white_effect_gen = None
    set_all(int(data.get("r", 0)), int(data.get("g", 0)), int(data.get("b", 0)), int(data.get("w", 0)))
    return jsonify({"ok": True})


@app.route("/api/effect/<name>", methods=["POST"])
def api_effect(name):
    global current_effect, effect_gen
    if name not in EFFECTS:
        return jsonify({"error": "unknown effect"}), 400
    data = request.json or {}
    kwargs = build_effect_kwargs(name, data.get("colors", {}))
    with effect_lock:
        current_effect = name
        effect_gen = EFFECTS[name]["fn"](**kwargs)
    return jsonify({"ok": True, "effect": name})


@app.route("/api/stop", methods=["POST"])
def api_stop():
    global current_effect, effect_gen, current_white_effect, white_effect_gen
    with effect_lock:
        current_effect = None
        effect_gen = None
    with white_effect_lock:
        current_white_effect = None
        white_effect_gen = None
    set_all(0, 0, 0, 0)
    return jsonify({"ok": True})


@app.route("/api/brightness", methods=["POST"])
def api_brightness():
    global brightness
    data = request.json
    brightness = max(0.0, min(1.0, float(data.get("value", 1.0))))
    return jsonify({"ok": True, "brightness": brightness})


@app.route("/api/blackout", methods=["POST"])
def api_blackout():
    global blackout
    data = request.json
    blackout = bool(data.get("active", not blackout))
    return jsonify({"ok": True, "blackout": blackout})


# ---- SOCKETIO ----

@socketio.on("set_color")
def ws_set_color(data):
    global current_effect, effect_gen, current_white_effect, white_effect_gen
    with effect_lock:
        current_effect = None
        effect_gen = None
    with white_effect_lock:
        current_white_effect = None
        white_effect_gen = None
    fade_time = float(data.get("fade_time", 0))
    r, g, b, w = int(data.get("r", 0)), int(data.get("g", 0)), int(data.get("b", 0)), int(data.get("w", 0))
    if fade_time > 0:
        target = list(dmx)
        for col in range(COLUMNS):
            bz = col_to_bottom_zone(col)
            rc, gc, bc = color_zone_channels(bz)
            target[rc], target[gc], target[bc] = r, g, b
            tz = col_to_top_zone(col)
            rc2, gc2, bc2 = color_zone_channels(tz)
            target[rc2], target[gc2], target[bc2] = r, g, b
            target[white_zone_channel(col)] = w
        start_fade(target, fade_time)
    else:
        set_all(r, g, b, w)


@socketio.on("set_zones")
def ws_set_zones(data):
    """Set specific zones. data = {color_zones: [idx,...], white_zones: [idx,...], r, g, b, w}"""
    r = int(data.get("r", 0))
    g = int(data.get("g", 0))
    b = int(data.get("b", 0))
    w = int(data.get("w", 0))
    for cz in data.get("color_zones", []):
        if 0 <= cz < NUM_COLOR_ZONES:
            set_color_zone(cz, r, g, b)
    for wz in data.get("white_zones", []):
        if 0 <= wz < NUM_WHITE_ZONES:
            set_white_zone(wz, w)


_last_strobe_colors = {}

def _restart_strobe_effect_if_needed():
    """Restart strobe effects with current rates when they change."""
    global current_effect, effect_gen, current_white_effect, white_effect_gen
    if current_effect == "strobe":
        kwargs = build_effect_kwargs("strobe", _last_strobe_colors)
        kwargs["rate"] = color_strobe_rate
        with effect_lock:
            effect_gen = EFFECTS["strobe"]["fn"](**kwargs)
    if current_white_effect == "w_strobe":
        with white_effect_lock:
            white_effect_gen = WHITE_EFFECTS["w_strobe"]["fn"](peak=255, rate=white_strobe_rate)


@socketio.on("set_effect")
def ws_set_effect(data):
    global current_effect, effect_gen
    name = data.get("name", "")
    if not name or name not in EFFECTS:
        with effect_lock:
            current_effect = None
            effect_gen = None
    elif name == "strobe":
        _last_strobe_colors.clear()
        _last_strobe_colors.update(data.get("colors", {}))
        kwargs = build_effect_kwargs(name, _last_strobe_colors)
        kwargs["rate"] = color_strobe_rate
        with effect_lock:
            current_effect = name
            effect_gen = EFFECTS[name]["fn"](**kwargs)
    else:
        kwargs = build_effect_kwargs(name, data.get("colors", {}))
        with effect_lock:
            current_effect = name
            effect_gen = EFFECTS[name]["fn"](**kwargs)

@socketio.on("set_brightness")
def ws_set_brightness(data):
    global brightness
    brightness = max(0.0, min(1.0, float(data.get("value", 1.0))))

@socketio.on("set_blackout")
def ws_set_blackout(data):
    global blackout
    blackout = bool(data.get("active", not blackout))

@socketio.on("set_speed")
def ws_set_speed(data):
    global effect_speed
    effect_speed = max(0.1, min(10.0, float(data.get("value", 1.0))))

@socketio.on("set_white_effect")
def ws_set_white_effect(data):
    global current_white_effect, white_effect_gen
    name = data.get("name", "")
    if name in WHITE_EFFECTS:
        with white_effect_lock:
            current_white_effect = name
            if name == "w_strobe":
                white_effect_gen = WHITE_EFFECTS[name]["fn"](peak=255, rate=white_strobe_rate)
            else:
                white_effect_gen = WHITE_EFFECTS[name]["fn"]()

@socketio.on("stop_white_effect")
def ws_stop_white_effect(_data=None):
    global current_white_effect, white_effect_gen
    with white_effect_lock:
        current_white_effect = None
        white_effect_gen = None
    for w in range(NUM_WHITE_ZONES):
        set_white_zone(w, 0)

@socketio.on("set_rgb_dimmer")
def ws_set_rgb_dimmer(data):
    global rgb_dimmer
    rgb_dimmer = max(0.0, min(1.0, float(data.get("value", 1.0))))

@socketio.on("set_white_dimmer")
def ws_set_white_dimmer(data):
    global white_dimmer
    white_dimmer = max(0.0, min(1.0, float(data.get("value", 1.0))))

@socketio.on("set_white_speed")
def ws_set_white_speed(data):
    global white_effect_speed
    white_effect_speed = max(0.1, min(10.0, float(data.get("value", 1.0))))

@socketio.on("set_color_strobe_rate")
def ws_set_color_strobe_rate(data):
    global color_strobe_rate
    color_strobe_rate = max(1.0, min(30.0, float(data.get("value", 8))))
    _restart_strobe_effect_if_needed()


@socketio.on("set_white_strobe_rate")
def ws_set_white_strobe_rate(data):
    global white_strobe_rate
    white_strobe_rate = max(1.0, min(30.0, float(data.get("value", 8))))
    _restart_strobe_effect_if_needed()

@socketio.on("stop")
def ws_stop(_data=None):
    global current_effect, effect_gen, effect_speed, rgb_dimmer
    global current_white_effect, white_effect_gen, white_effect_speed, white_dimmer
    with effect_lock:
        current_effect = None
        effect_gen = None
    with white_effect_lock:
        current_white_effect = None
        white_effect_gen = None
    effect_speed = 1.0
    white_effect_speed = 1.0
    rgb_dimmer = 1.0
    white_dimmer = 1.0
    set_all(0, 0, 0, 0)


# ---- MAIN ----

if __name__ == "__main__":
    import subprocess
    import sys

    print(f"YeeSite Web Controller on http://{WEB_HOST}:{WEB_PORT}")
    print(f"OLA: {OLA_URL} universe {DMX_UNIVERSE}")
    print(f"Layout: {NUM_COLOR_ZONES} color zones (RGB) + {NUM_WHITE_ZONES} white zones")
    sys.exit(
        subprocess.call(
            [
                sys.executable,
                "-m",
                "gunicorn",
                "-c",
                "gunicorn_config.py",
                "server:app",
            ]
        )
    )
