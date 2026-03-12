"""
Effect generators for the YeeSite 720LED RGBW Bar.

Each effect is a generator yielding frames. A frame is a dict:
  {"color": [(r,g,b)] * 48, "white": [w] * 24}

Color zones 0-23 = bottom row (L→R), 24-47 = top row (R→L physically).
White zones 0-23 = middle row (L→R).

Effects only drive the RGB color zones. White zones are reserved for
strobe mode and direct manual control (sliders, groups, zone selection).
"""

import math
import random
from config import COLUMNS, NUM_COLOR_ZONES, NUM_WHITE_ZONES, col_to_bottom_zone, col_to_top_zone, FRAME_TIME


def _hsv_to_rgb(h, s, v):
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


def _blank():
    return {"color": [(0, 0, 0)] * NUM_COLOR_ZONES, "white": [0] * NUM_WHITE_ZONES}


def _set_column(frame, col, r, g, b):
    """Set both top and bottom color zones at a physical column. Never touches white."""
    bz = col_to_bottom_zone(col)
    tz = col_to_top_zone(col)
    frame["color"][bz] = (r, g, b)
    frame["color"][tz] = (r, g, b)


def _set_all_columns(frame, r, g, b):
    for col in range(COLUMNS):
        _set_column(frame, col, r, g, b)


def solid_color(color=(255, 255, 255)):
    r, g, b = color
    frame = _blank()
    _set_all_columns(frame, r, g, b)
    while True:
        yield frame


def rainbow_chase(speed=2.0):
    offset = 0.0
    while True:
        frame = _blank()
        for col in range(COLUMNS):
            hue = (col / COLUMNS * 360 + offset) % 360
            r, g, b = _hsv_to_rgb(hue, 1.0, 1.0)
            _set_column(frame, col, r, g, b)
        yield frame
        offset = (offset + speed) % 360


def rainbow_breathe(speed=1.0):
    hue = 0.0
    t = 0.0
    while True:
        brightness = (math.sin(t) + 1) / 2
        r, g, b = _hsv_to_rgb(hue, 1.0, brightness)
        frame = _blank()
        _set_all_columns(frame, r, g, b)
        yield frame
        hue = (hue + speed * 0.5) % 360
        t += speed * 0.05


def _fire_color(h):
    """Map heat 0.0-1.0 to a fire color: black → deep red → orange → yellow → white-hot."""
    if h < 0.25:
        t = h / 0.25
        return int(t * 180), 0, 0
    elif h < 0.55:
        t = (h - 0.25) / 0.3
        return int(180 + t * 75), int(t * 130), 0
    elif h < 0.8:
        t = (h - 0.55) / 0.25
        return 255, int(130 + t * 125), int(t * 30)
    else:
        t = (h - 0.8) / 0.2
        return 255, 255, int(30 + t * 180)


def fire(intensity=1.0):
    bot_heat = [0.0] * COLUMNS
    top_heat = [0.0] * COLUMNS

    while True:
        # Ignite random sparks along the bottom
        for _ in range(random.randint(2, 5)):
            c = random.randint(0, COLUMNS - 1)
            bot_heat[c] = min(1.0, bot_heat[c] + random.uniform(0.4, 0.9) * intensity)

        # Diffuse bottom heat horizontally
        new_bot = list(bot_heat)
        for c in range(COLUMNS):
            left = bot_heat[max(0, c - 1)]
            right = bot_heat[min(COLUMNS - 1, c + 1)]
            new_bot[c] = bot_heat[c] * 0.55 + left * 0.18 + right * 0.18 + random.uniform(-0.02, 0.04)
            new_bot[c] = max(0.0, min(1.0, new_bot[c]))
        bot_heat = new_bot

        # Heat rises: top gets a fraction of bottom, with cooling
        for c in range(COLUMNS):
            rise = bot_heat[c] * random.uniform(0.3, 0.65)
            top_heat[c] = top_heat[c] * 0.4 + rise * 0.6
            top_heat[c] *= random.uniform(0.82, 0.96)
            top_heat[c] = max(0.0, min(1.0, top_heat[c]))

        # Cool bottom slightly each frame
        for c in range(COLUMNS):
            bot_heat[c] *= random.uniform(0.85, 0.95)

        # Occasional flare on a random column
        if random.random() < 0.08:
            c = random.randint(0, COLUMNS - 1)
            bot_heat[c] = min(1.0, bot_heat[c] + 0.5)
            top_heat[c] = min(1.0, top_heat[c] + 0.3)

        frame = _blank()
        for col in range(COLUMNS):
            br, bg, bb = _fire_color(bot_heat[col])
            tr, tg, tb = _fire_color(top_heat[col])
            bz = col_to_bottom_zone(col)
            tz = col_to_top_zone(col)
            frame["color"][bz] = (br, bg, bb)
            frame["color"][tz] = (tr, tg, tb)
        yield frame


def knight_rider(color=(255, 0, 0), width=4, speed=1.5):
    pos = 0.0
    direction = 1
    while True:
        frame = _blank()
        center = pos
        for col in range(COLUMNS):
            dist = abs(col - center)
            if dist <= width:
                factor = (1.0 - dist / (width + 1)) ** 1.5
                _set_column(frame, col, int(color[0] * factor), int(color[1] * factor), int(color[2] * factor))
        yield frame
        pos += direction * speed
        if pos >= COLUMNS - 1:
            pos = COLUMNS - 1
            direction = -1
        elif pos <= 0:
            pos = 0
            direction = 1


def police(color_a=(255, 0, 0), color_b=(0, 0, 255), speed=4.0):
    t = 0.0
    half = COLUMNS // 2
    while True:
        frame = _blank()
        phase = int(t) % 2
        if phase == 0:
            for col in range(half):
                _set_column(frame, col, *color_a)
        else:
            for col in range(half, COLUMNS):
                _set_column(frame, col, *color_b)
        yield frame
        t += speed * 0.025


def police_tb(color_a=(255, 0, 0), color_b=(0, 0, 255), speed=4.0):
    t = 0.0
    while True:
        frame = _blank()
        phase = int(t) % 2
        if phase == 0:
            for col in range(COLUMNS):
                bz = col_to_bottom_zone(col)
                frame["color"][bz] = color_a
        else:
            for col in range(COLUMNS):
                tz = col_to_top_zone(col)
                frame["color"][tz] = color_b
        yield frame
        t += speed * 0.025


def color_wipe(speed=1.0):
    hue_offset = 0.0
    while True:
        # Fill left to right
        pos = 0.0
        while pos < COLUMNS:
            frame = _blank()
            fill_to = min(int(pos) + 1, COLUMNS)
            for col in range(fill_to):
                hue = (col / COLUMNS * 360 + hue_offset) % 360
                _set_column(frame, col, *_hsv_to_rgb(hue, 1.0, 1.0))
            yield frame
            pos += speed * 0.5

        # Hold fully lit briefly
        frame = _blank()
        for col in range(COLUMNS):
            hue = (col / COLUMNS * 360 + hue_offset) % 360
            _set_column(frame, col, *_hsv_to_rgb(hue, 1.0, 1.0))
        for _ in range(3):
            yield frame

        # Erase left to right
        pos = 0.0
        while pos < COLUMNS:
            frame = _blank()
            erase_to = min(int(pos) + 1, COLUMNS)
            for col in range(erase_to, COLUMNS):
                hue = (col / COLUMNS * 360 + hue_offset) % 360
                _set_column(frame, col, *_hsv_to_rgb(hue, 1.0, 1.0))
            yield frame
            pos += speed * 0.5

        hue_offset = (hue_offset + 60) % 360


def breathe(color=(0, 100, 255), speed=1.0):
    t = 0.0
    while True:
        factor = (math.sin(t) + 1) / 2
        frame = _blank()
        _set_all_columns(frame, int(color[0] * factor), int(color[1] * factor), int(color[2] * factor))
        yield frame
        t += speed * 0.05


def sparkle(base_color=(0, 0, 0), spark_color=(255, 255, 255), density=0.1):
    while True:
        frame = _blank()
        for col in range(COLUMNS):
            if random.random() < density:
                _set_column(frame, col, *spark_color)
            else:
                _set_column(frame, col, *base_color)
        yield frame


def wave(color=(0, 100, 255), speed=2.0, wavelength=10.0):
    offset = 0.0
    while True:
        frame = _blank()
        for col in range(COLUMNS):
            factor = (math.sin(2 * math.pi * (col / wavelength) + offset) + 1) / 2
            _set_column(frame, col, int(color[0] * factor), int(color[1] * factor), int(color[2] * factor))
        yield frame
        offset += speed * 0.05


def color_cycle(speed=0.5):
    hue = 0.0
    while True:
        r, g, b = _hsv_to_rgb(hue, 1.0, 1.0)
        frame = _blank()
        _set_all_columns(frame, r, g, b)
        yield frame
        hue = (hue + speed) % 360


def meteor(color=(255, 255, 255), tail_length=8, speed=1.5):
    pos = -tail_length
    while True:
        frame = _blank()
        head = int(pos)
        for col in range(COLUMNS):
            dist = head - col
            if 0 <= dist <= tail_length:
                factor = (1.0 - dist / tail_length) ** 2
                _set_column(frame, col, int(color[0] * factor), int(color[1] * factor), int(color[2] * factor))
        yield frame
        pos += speed
        if pos > COLUMNS + tail_length:
            pos = -tail_length


def strobe(color=(255, 255, 255), rate=5.0):
    t = 0.0
    period = 1.0 / rate if rate > 0 else 1.0
    while True:
        on = (t % period) < (period / 2)
        frame = _blank()
        if on:
            _set_all_columns(frame, *color)
        yield frame
        t += FRAME_TIME


def alternating(color_a=(255, 0, 0), color_b=(0, 0, 255), speed=2.0):
    t = 0.0
    while True:
        swap = int(t) % 2 == 0
        frame = _blank()
        for col in range(COLUMNS):
            if (col % 2 == 0) == swap:
                _set_column(frame, col, *color_a)
            else:
                _set_column(frame, col, *color_b)
        yield frame
        t += speed * 0.025


def gradient(color_left=(255, 0, 0), color_right=(0, 0, 255)):
    frame = _blank()
    for col in range(COLUMNS):
        t = col / (COLUMNS - 1)
        r = int(color_left[0] * (1 - t) + color_right[0] * t)
        g = int(color_left[1] * (1 - t) + color_right[1] * t)
        b = int(color_left[2] * (1 - t) + color_right[2] * t)
        _set_column(frame, col, r, g, b)
    while True:
        yield frame


def theater_chase(color=(255, 255, 0), speed=3.0, group_size=3):
    offset = 0
    t = 0.0
    while True:
        frame = _blank()
        for col in range(COLUMNS):
            if (col + offset) % group_size == 0:
                _set_column(frame, col, *color)
        yield frame
        t += speed * 0.025
        if t >= 1.0:
            offset = (offset + 1) % group_size
            t = 0.0


def twinkle(color=(255, 200, 100), speed=1.0):
    phases = [random.uniform(0, 2 * math.pi) for _ in range(COLUMNS)]
    speeds = [random.uniform(0.5, 2.0) * speed for _ in range(COLUMNS)]
    while True:
        frame = _blank()
        for col in range(COLUMNS):
            v = (math.sin(phases[col]) + 1) / 2
            _set_column(frame, col, int(color[0] * v), int(color[1] * v), int(color[2] * v))
            phases[col] += speeds[col] * 0.08
        yield frame


def bounce(color_a=(255, 0, 0), color_b=(0, 100, 255), width=3, speed=1.5):
    pos_a = 0.0
    pos_b = float(COLUMNS - 1)
    dir_a = 1
    dir_b = -1
    while True:
        frame = _blank()
        for col in range(COLUMNS):
            da = abs(col - pos_a)
            db = abs(col - pos_b)
            ra, ga, ba = 0, 0, 0
            rb, gb, bb = 0, 0, 0
            if da <= width:
                f = (1.0 - da / (width + 1)) ** 1.5
                ra, ga, ba = int(color_a[0] * f), int(color_a[1] * f), int(color_a[2] * f)
            if db <= width:
                f = (1.0 - db / (width + 1)) ** 1.5
                rb, gb, bb = int(color_b[0] * f), int(color_b[1] * f), int(color_b[2] * f)
            _set_column(frame, col,
                        min(255, ra + rb), min(255, ga + gb), min(255, ba + bb))
        yield frame
        pos_a += dir_a * speed
        pos_b += dir_b * speed
        if pos_a >= COLUMNS - 1:
            pos_a = COLUMNS - 1; dir_a = -1
        elif pos_a <= 0:
            pos_a = 0; dir_a = 1
        if pos_b >= COLUMNS - 1:
            pos_b = COLUMNS - 1; dir_b = -1
        elif pos_b <= 0:
            pos_b = 0; dir_b = 1


def plasma(color_a=(255, 0, 128), color_b=(0, 128, 255), speed=1.0):
    t = 0.0
    while True:
        frame = _blank()
        for col in range(COLUMNS):
            v1 = math.sin(col * 0.3 + t)
            v2 = math.sin(col * 0.15 + t * 1.3)
            v3 = math.sin((col * 0.2 + t * 0.7))
            v = (v1 + v2 + v3 + 3) / 6
            r = int(color_a[0] * (1 - v) + color_b[0] * v)
            g = int(color_a[1] * (1 - v) + color_b[1] * v)
            b = int(color_a[2] * (1 - v) + color_b[2] * v)
            _set_column(frame, col, r, g, b)
        yield frame
        t += speed * 0.04


def rain(color=(0, 100, 255), decay=0.88):
    brightness = [0.0] * COLUMNS
    while True:
        if random.random() < 0.25:
            c = random.randint(0, COLUMNS - 1)
            brightness[c] = 1.0
        frame = _blank()
        for col in range(COLUMNS):
            v = brightness[col]
            if v > 0.01:
                _set_column(frame, col, int(color[0] * v), int(color[1] * v), int(color[2] * v))
            brightness[col] *= decay
        yield frame


def pulse(color=(0, 255, 128), speed=2.0):
    center = (COLUMNS - 1) / 2.0
    radius = 0.0
    while True:
        frame = _blank()
        for col in range(COLUMNS):
            dist = abs(col - center)
            diff = abs(dist - radius)
            if diff < 2.5:
                f = max(0.0, 1.0 - diff / 2.5)
                _set_column(frame, col, int(color[0] * f), int(color[1] * f), int(color[2] * f))
        yield frame
        radius += speed * 0.3
        if radius > COLUMNS:
            radius = 0.0


def heartbeat(color=(255, 0, 60), speed=1.0):
    PATTERN = [1.0, 0.0, 0.7, 0.0, 0.0, 0.0, 0.0, 0.0]
    idx = 0.0
    while True:
        i = int(idx) % len(PATTERN)
        frac = idx - int(idx)
        nxt = (i + 1) % len(PATTERN)
        v = PATTERN[i] * (1 - frac) + PATTERN[nxt] * frac
        frame = _blank()
        _set_all_columns(frame, int(color[0] * v), int(color[1] * v), int(color[2] * v))
        yield frame
        idx += speed * 0.08
        if idx >= len(PATTERN):
            idx -= len(PATTERN)


def lightning(color=(200, 200, 255)):
    cooldown = 0
    flash_frames = 0
    flash_brightness = 0.0
    while True:
        frame = _blank()
        if cooldown <= 0 and random.random() < 0.06:
            flash_frames = random.randint(1, 3)
            flash_brightness = random.uniform(0.6, 1.0)
            cooldown = random.randint(8, 25)
        if flash_frames > 0:
            v = flash_brightness * (0.5 + random.uniform(0, 0.5))
            spread = random.randint(4, COLUMNS)
            start = random.randint(0, COLUMNS - spread)
            for col in range(start, start + spread):
                _set_column(frame, col, int(color[0] * v), int(color[1] * v), int(color[2] * v))
            flash_frames -= 1
        cooldown -= 1
        yield frame


def running_lights(color=(0, 200, 255), speed=2.0):
    offset = 0.0
    while True:
        frame = _blank()
        for col in range(COLUMNS):
            v = (math.sin(col * 0.5 + offset) + 1) / 2
            v = v ** 1.5
            _set_column(frame, col, int(color[0] * v), int(color[1] * v), int(color[2] * v))
        yield frame
        offset += speed * 0.06


def lava(color_a=(255, 40, 0), color_b=(255, 160, 0), speed=0.5):
    phases = [random.uniform(0, 2 * math.pi) for _ in range(COLUMNS)]
    freqs = [random.uniform(0.3, 1.2) for _ in range(COLUMNS)]
    while True:
        frame = _blank()
        for col in range(COLUMNS):
            v = (math.sin(phases[col]) + 1) / 2
            r = int(color_a[0] * (1 - v) + color_b[0] * v)
            g = int(color_a[1] * (1 - v) + color_b[1] * v)
            b = int(color_a[2] * (1 - v) + color_b[2] * v)
            _set_column(frame, col, r, g, b)
            phases[col] += freqs[col] * speed * 0.03
        yield frame


def comet(color=(100, 180, 255), tail_length=10, speed=1.5):
    pos = -tail_length
    while True:
        frame = _blank()
        head = int(pos)
        for col in range(COLUMNS):
            dist = head - col
            if dist == 0:
                _set_column(frame, col, *color)
            elif 0 < dist <= tail_length:
                t = dist / tail_length
                hue = (t * 270) % 360
                factor = (1.0 - t) ** 1.5
                r, g, b = _hsv_to_rgb(hue, 1.0, factor)
                _set_column(frame, col, r, g, b)
        yield frame
        pos += speed
        if pos > COLUMNS + tail_length:
            pos = -tail_length


def color_bounce(color=(255, 100, 0), width=2):
    pos = 0.0
    vel = 0.0
    gravity = 0.15
    damping = 0.85
    floor = COLUMNS - 1
    while True:
        frame = _blank()
        for col in range(COLUMNS):
            dist = abs(col - pos)
            if dist <= width:
                f = (1.0 - dist / (width + 1)) ** 1.5
                _set_column(frame, col, int(color[0] * f), int(color[1] * f), int(color[2] * f))
        yield frame
        vel += gravity
        pos += vel
        if pos >= floor:
            pos = floor
            vel = -abs(vel) * damping
            if abs(vel) < 0.3:
                vel = -4.0


def midi_reactive(midi_state_ref):
    """
    Music-reactive effect driven by midi_handler.midi_state.

    Reads zone colors and brightness values set by the MIDI callback thread
    and renders them each frame, applying per-frame brightness decay so notes
    fade out naturally after being released.

    midi_state_ref is the shared dict from midi_handler.midi_state.
    Instantiated by server.py when the first Note On arrives.
    """
    DECAY = 0.93        # brightness decay per frame (~1 s fade at 60 FPS)
    FLASH_DECAY = 0.80  # faster flash decay (velocity impact)

    while True:
        frame = _blank()
        zones = midi_state_ref.get("zones", [])
        z_brightness = midi_state_ref.get("zone_brightness", [])
        flash = midi_state_ref.get("flash_brightness", 0.0)

        for col in range(COLUMNS):
            bz = col_to_bottom_zone(col)
            tz = col_to_top_zone(col)

            bv = z_brightness[col] if col < len(z_brightness) else 0.0
            effective = min(1.0, bv + flash * 0.25)

            if col < len(zones):
                base_r, base_g, base_b = zones[col]
                r = int(base_r * effective)
                g = int(base_g * effective)
                b = int(base_b * effective)
            else:
                r = g = b = 0

            frame["color"][bz] = (r, g, b)
            frame["color"][tz] = (r, g, b)
            # White middle row: spatially matched brightness, capped at 80% to
            # avoid washing out the RGB colour visible underneath
            frame["white"][col] = int(effective * 200)

            # Decay zone brightness (note-off fade)
            if col < len(z_brightness):
                midi_state_ref["zone_brightness"][col] = bv * DECAY

        # Decay global flash
        midi_state_ref["flash_brightness"] = flash * FLASH_DECAY

        yield frame


def beat_flash(midi_state_ref):
    """
    Full-bar flash on every beat. Hue advances 90° each beat.
    Reads beat_phase and beat_count from midi_state_ref.
    """
    hue = 0.0
    last_beat = -1
    while True:
        frame = _blank()
        beat_count = midi_state_ref.get("beat_count", 0)
        beat_phase = midi_state_ref.get("beat_phase", 0.0)
        clock_running = midi_state_ref.get("clock_running", False)

        if beat_count != last_beat:
            hue = (hue + 90) % 360
            last_beat = beat_count

        if clock_running:
            # Bright flash at phase 0, decays over first third of the beat
            brightness = max(0.0, 1.0 - beat_phase * 3.5)
            if brightness > 0:
                r, g, b = _hsv_to_rgb(hue, 1.0, brightness)
                _set_all_columns(frame, r, g, b)
                for i in range(NUM_WHITE_ZONES):
                    frame["white"][i] = int(brightness * 200)
        yield frame


def beat_chase(midi_state_ref):
    """
    A bright dot sweeps from left to right within each beat, hue advances each beat.
    """
    hue = 0.0
    last_beat = -1
    while True:
        frame = _blank()
        beat_count = midi_state_ref.get("beat_count", 0)
        beat_phase = midi_state_ref.get("beat_phase", 0.0)
        clock_running = midi_state_ref.get("clock_running", False)

        if beat_count != last_beat:
            hue = (hue + 30) % 360
            last_beat = beat_count

        if clock_running:
            center = beat_phase * (COLUMNS - 1)
            r, g, b = _hsv_to_rgb(hue, 1.0, 1.0)
            width = 3
            for col in range(COLUMNS):
                dist = abs(col - center)
                if dist <= width:
                    f = (1.0 - dist / (width + 1)) ** 1.5
                    _set_column(frame, col, int(r * f), int(g * f), int(b * f))
        yield frame


def beat_color_cycle(midi_state_ref):
    """
    Whole bar pulses, advancing hue by 60° on each beat. Brightness peaks at downbeat.
    """
    hue = 0.0
    last_beat = -1
    while True:
        frame = _blank()
        beat_count = midi_state_ref.get("beat_count", 0)
        beat_phase = midi_state_ref.get("beat_phase", 0.0)
        clock_running = midi_state_ref.get("clock_running", False)

        if beat_count != last_beat:
            hue = (hue + 60) % 360
            last_beat = beat_count

        if clock_running:
            # Cosine pulse: peaks at phase 0, troughs at phase 0.5
            brightness = (math.cos(beat_phase * 2 * math.pi) + 1) / 2
            brightness = 0.2 + brightness * 0.8   # floor at 20%
            r, g, b = _hsv_to_rgb(hue, 1.0, brightness)
            _set_all_columns(frame, r, g, b)
        yield frame


def _rgb_to_hex(r, g, b):
    return f"#{r:02x}{g:02x}{b:02x}"


# =========================================================================
# WHITE-ONLY EFFECTS
# Each generator yields a list of 24 int values (0-255), one per white zone.
# =========================================================================

def _w_blank():
    return [0] * NUM_WHITE_ZONES


def w_solid(peak=255):
    """Static white - all zones at same level."""
    out = [int(peak)] * NUM_WHITE_ZONES
    while True:
        yield list(out)


def w_breathe(peak=255, speed=1.0):
    t = 0.0
    while True:
        v = int(((math.sin(t) + 1) / 2) * peak)
        yield [v] * NUM_WHITE_ZONES
        t += speed * 0.05


def w_strobe(peak=255, rate=5.0):
    t = 0.0
    period = 1.0 / max(0.5, rate)
    while True:
        on = (t % period) < (period / 2)
        yield [peak if on else 0] * NUM_WHITE_ZONES
        t += FRAME_TIME


def w_chase(peak=255, speed=2.0):
    pos = 0.0
    width = 3
    while True:
        out = _w_blank()
        center = int(pos) % NUM_WHITE_ZONES
        for i in range(NUM_WHITE_ZONES):
            dist = min(abs(i - center), NUM_WHITE_ZONES - abs(i - center))
            if dist <= width:
                out[i] = int(peak * ((1.0 - dist / (width + 1)) ** 1.5))
        yield out
        pos += speed * 0.5


def w_twinkle(peak=255, speed=1.0):
    phases = [random.uniform(0, 2 * math.pi) for _ in range(NUM_WHITE_ZONES)]
    speeds = [random.uniform(0.5, 2.0) * speed for _ in range(NUM_WHITE_ZONES)]
    while True:
        out = _w_blank()
        for i in range(NUM_WHITE_ZONES):
            out[i] = int(((math.sin(phases[i]) + 1) / 2) * peak)
            phases[i] += speeds[i] * 0.08
        yield out


def w_sparkle(peak=255, density=0.12):
    while True:
        out = _w_blank()
        for i in range(NUM_WHITE_ZONES):
            if random.random() < density:
                out[i] = random.randint(int(peak * 0.6), peak)
        yield out


def w_pulse(peak=255, speed=2.0):
    center = (NUM_WHITE_ZONES - 1) / 2.0
    radius = 0.0
    while True:
        out = _w_blank()
        for i in range(NUM_WHITE_ZONES):
            diff = abs(abs(i - center) - radius)
            if diff < 2.0:
                out[i] = int(peak * max(0.0, 1.0 - diff / 2.0))
        yield out
        radius += speed * 0.3
        if radius > NUM_WHITE_ZONES:
            radius = 0.0


def w_wave(peak=255, speed=2.0, wavelength=8.0):
    offset = 0.0
    while True:
        out = _w_blank()
        for i in range(NUM_WHITE_ZONES):
            v = (math.sin(2 * math.pi * (i / wavelength) + offset) + 1) / 2
            out[i] = int(v * peak)
        yield out
        offset += speed * 0.05


def w_alternating(peak=255, speed=2.0):
    t = 0.0
    while True:
        swap = int(t) % 2 == 0
        out = _w_blank()
        for i in range(NUM_WHITE_ZONES):
            if (i % 2 == 0) == swap:
                out[i] = peak
        yield out
        t += speed * 0.025


def w_gradient(peak=255):
    out = _w_blank()
    for i in range(NUM_WHITE_ZONES):
        out[i] = int(peak * i / (NUM_WHITE_ZONES - 1))
    while True:
        yield list(out)


def w_rain(peak=255, decay=0.88):
    brightness = [0.0] * NUM_WHITE_ZONES
    while True:
        if random.random() < 0.25:
            c = random.randint(0, NUM_WHITE_ZONES - 1)
            brightness[c] = 1.0
        out = _w_blank()
        for i in range(NUM_WHITE_ZONES):
            out[i] = int(brightness[i] * peak) if brightness[i] > 0.01 else 0
            brightness[i] *= decay
        yield out


def w_bounce(peak=255, speed=1.5, width=2):
    pos = 0.0
    direction = 1
    while True:
        out = _w_blank()
        for i in range(NUM_WHITE_ZONES):
            dist = abs(i - pos)
            if dist <= width:
                out[i] = int(peak * ((1.0 - dist / (width + 1)) ** 1.5))
        yield out
        pos += direction * speed
        if pos >= NUM_WHITE_ZONES - 1:
            pos = NUM_WHITE_ZONES - 1; direction = -1
        elif pos <= 0:
            pos = 0; direction = 1


WHITE_EFFECTS = {
    "w_solid": {"name": "Solid", "fn": w_solid, "category": "ambient"},
    "w_breathe": {"name": "Breathe", "fn": w_breathe, "category": "ambient"},
    "w_strobe": {"name": "Strobe", "fn": w_strobe, "category": "flash"},
    "w_chase": {"name": "Chase", "fn": w_chase, "category": "chase"},
    "w_twinkle": {"name": "Twinkle", "fn": w_twinkle, "category": "ambient"},
    "w_sparkle": {"name": "Sparkle", "fn": w_sparkle, "category": "ambient"},
    "w_pulse": {"name": "Pulse", "fn": w_pulse, "category": "chase"},
    "w_wave": {"name": "Wave", "fn": w_wave, "category": "chase"},
    "w_alternating": {"name": "Alternating", "fn": w_alternating, "category": "flash"},
    "w_gradient": {"name": "Gradient", "fn": w_gradient, "category": "ambient"},
    "w_rain": {"name": "Rain", "fn": w_rain, "category": "ambient"},
    "w_bounce": {"name": "Bounce", "fn": w_bounce, "category": "chase"},
}


EFFECTS = {
    "solid": {
        "name": "Solid", "fn": solid_color, "category": "ambient",
        "colors": [
            {"key": "color", "label": "Color", "default": "#ffffff"},
        ],
    },
    "rainbow_chase": {
        "name": "Rainbow Chase", "fn": rainbow_chase, "category": "color",
        "colors": [],
    },
    "rainbow_breathe": {
        "name": "Rainbow Breathe", "fn": rainbow_breathe, "category": "color",
        "colors": [],
    },
    "fire": {
        "name": "Fire", "fn": fire, "category": "warm",
        "colors": [],
    },
    "knight_rider": {
        "name": "Knight Rider", "fn": knight_rider, "category": "chase",
        "colors": [
            {"key": "color", "label": "Color", "default": "#ff0000"},
        ],
    },
    "police": {
        "name": "Police L/R", "fn": police, "category": "flash",
        "colors": [
            {"key": "color_a", "label": "Left", "default": "#ff0000"},
            {"key": "color_b", "label": "Right", "default": "#0000ff"},
        ],
    },
    "police_tb": {
        "name": "Police T/B", "fn": police_tb, "category": "flash",
        "colors": [
            {"key": "color_a", "label": "Bottom", "default": "#ff0000"},
            {"key": "color_b", "label": "Top", "default": "#0000ff"},
        ],
    },
    "color_wipe": {
        "name": "Color Wipe", "fn": color_wipe, "category": "chase",
        "colors": [],
    },
    "breathe": {
        "name": "Breathe", "fn": breathe, "category": "ambient",
        "colors": [
            {"key": "color", "label": "Color", "default": "#0064ff"},
        ],
    },
    "sparkle": {
        "name": "Sparkle", "fn": sparkle, "category": "ambient",
        "colors": [
            {"key": "base_color", "label": "Base", "default": "#000000"},
            {"key": "spark_color", "label": "Spark", "default": "#ffffff"},
        ],
    },
    "wave": {
        "name": "Wave", "fn": wave, "category": "chase",
        "colors": [
            {"key": "color", "label": "Color", "default": "#0064ff"},
        ],
    },
    "color_cycle": {
        "name": "Color Cycle", "fn": color_cycle, "category": "color",
        "colors": [],
    },
    "meteor": {
        "name": "Meteor", "fn": meteor, "category": "chase",
        "colors": [
            {"key": "color", "label": "Color", "default": "#ffffff"},
        ],
    },
    "strobe": {
        "name": "Strobe", "fn": strobe, "category": "flash",
        "colors": [
            {"key": "color", "label": "Color", "default": "#ffffff"},
        ],
    },
    "alternating": {
        "name": "Alternating", "fn": alternating, "category": "flash",
        "colors": [
            {"key": "color_a", "label": "Color A", "default": "#ff0000"},
            {"key": "color_b", "label": "Color B", "default": "#0000ff"},
        ],
    },
    "gradient": {
        "name": "Gradient", "fn": gradient, "category": "color",
        "colors": [
            {"key": "color_left", "label": "Left", "default": "#ff0000"},
            {"key": "color_right", "label": "Right", "default": "#0000ff"},
        ],
    },
    "theater_chase": {
        "name": "Theater Chase", "fn": theater_chase, "category": "chase",
        "colors": [
            {"key": "color", "label": "Color", "default": "#ffff00"},
        ],
    },
    "twinkle": {
        "name": "Twinkle", "fn": twinkle, "category": "ambient",
        "colors": [
            {"key": "color", "label": "Color", "default": "#ffc864"},
        ],
    },
    "bounce": {
        "name": "Bounce", "fn": bounce, "category": "chase",
        "colors": [
            {"key": "color_a", "label": "Left", "default": "#ff0000"},
            {"key": "color_b", "label": "Right", "default": "#0064ff"},
        ],
    },
    "plasma": {
        "name": "Plasma", "fn": plasma, "category": "color",
        "colors": [
            {"key": "color_a", "label": "Color A", "default": "#ff0080"},
            {"key": "color_b", "label": "Color B", "default": "#0080ff"},
        ],
    },
    "rain": {
        "name": "Rain", "fn": rain, "category": "ambient",
        "colors": [
            {"key": "color", "label": "Color", "default": "#0064ff"},
        ],
    },
    "pulse": {
        "name": "Pulse", "fn": pulse, "category": "chase",
        "colors": [
            {"key": "color", "label": "Color", "default": "#00ff80"},
        ],
    },
    "heartbeat": {
        "name": "Heartbeat", "fn": heartbeat, "category": "ambient",
        "colors": [
            {"key": "color", "label": "Color", "default": "#ff003c"},
        ],
    },
    "lightning": {
        "name": "Lightning", "fn": lightning, "category": "flash",
        "colors": [
            {"key": "color", "label": "Color", "default": "#c8c8ff"},
        ],
    },
    "running_lights": {
        "name": "Running Lights", "fn": running_lights, "category": "chase",
        "colors": [
            {"key": "color", "label": "Color", "default": "#00c8ff"},
        ],
    },
    "lava": {
        "name": "Lava", "fn": lava, "category": "warm",
        "colors": [
            {"key": "color_a", "label": "Color A", "default": "#ff2800"},
            {"key": "color_b", "label": "Color B", "default": "#ffa000"},
        ],
    },
    "comet": {
        "name": "Comet", "fn": comet, "category": "chase",
        "colors": [
            {"key": "color", "label": "Head", "default": "#64b4ff"},
        ],
    },
    "color_bounce": {
        "name": "Color Bounce", "fn": color_bounce, "category": "chase",
        "colors": [
            {"key": "color", "label": "Color", "default": "#ff6400"},
        ],
    },
}
