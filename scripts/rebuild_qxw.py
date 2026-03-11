#!/usr/bin/env python3
"""
Populate MyFirstLighting.qxw with complete scene DMX data, chaser steps,
and slider channel mappings for the YeeSite 200W 720LED RGBW Bar.

Channel layout (168-channel mode):
  Ch 0-143:   48 color zones × 3 (R, G, B)
  Ch 144-167: 24 white zones × 1

Physical layout:
  Bottom row: color zones 0-23 (L→R)
  Top row:    color zones 24-47, but physically R→L (counter-clockwise)
  Middle row: white zones 0-23 (L→R)

Usage:
  python3 rebuild_qxw.py
  # Updates: ../MyFirstLighting.qxw in place
"""

import os
import re
import random

random.seed(42)

NUM_COLOR_ZONES = 48
NUM_WHITE_ZONES = 24
COLUMNS = 24
FIXTURE_ID = 0
QXW_PATH = os.path.join(os.path.dirname(__file__), "..", "MyFirstLighting.qxw")


# ---- LAYOUT HELPERS ----

def col_to_bottom_zone(col):
    return col

def col_to_top_zone(col):
    return 47 - col

def hsv_to_rgb(h, s, v):
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


# ---- DMX HELPERS ----

def make_fixture_val(color_zones=None, white_zones=None):
    """Build FixtureVal CSV from zone data.
    color_zones: dict {zone_0idx: (r, g, b)}
    white_zones: dict {wzone_0idx: brightness}
    """
    pairs = []
    if color_zones:
        for z, (r, g, b) in sorted(color_zones.items()):
            base = z * 3
            if r > 0: pairs.append(f"{base},{r}")
            if g > 0: pairs.append(f"{base + 1},{g}")
            if b > 0: pairs.append(f"{base + 2},{b}")
    if white_zones:
        for w, val in sorted(white_zones.items()):
            if val > 0: pairs.append(f"{144 + w},{val}")
    return ",".join(pairs)


# ---- ZONE CONSTRUCTION HELPERS ----

def all_color(r, g, b):
    return {z: (r, g, b) for z in range(48)}

def all_white(val):
    return {w: val for w in range(24)}

def left_half_color(r, g, b):
    d = {col: (r, g, b) for col in range(12)}
    d.update({47 - col: (r, g, b) for col in range(12)})
    return d

def right_half_color(r, g, b):
    d = {col: (r, g, b) for col in range(12, 24)}
    d.update({47 - col: (r, g, b) for col in range(12, 24)})
    return d


# ---- SCENE DEFINITIONS ----

scenes = {}

scenes[1]  = ("Red",        all_color(255, 0, 0),     None)
scenes[2]  = ("Green",      all_color(0, 255, 0),     None)
scenes[3]  = ("Blue",       all_color(0, 0, 255),     None)
scenes[4]  = ("White",      None,                      all_white(255))
scenes[5]  = ("Cyan",       all_color(0, 255, 255),   None)
scenes[6]  = ("Yellow",     all_color(255, 255, 0),   None)
scenes[7]  = ("Purple",     all_color(180, 0, 255),   None)
scenes[8]  = ("Warm White", all_color(255, 160, 60),  all_white(200))
scenes[9]  = ("Orange",     all_color(255, 100, 0),   None)
scenes[10] = ("Pink",       all_color(255, 20, 147),  None)
scenes[11] = ("All Off",    None, None)
scenes[12] = ("Full White", all_color(255, 255, 255), all_white(255))
scenes[13] = ("Strobe On",  all_color(255, 255, 255), all_white(255))
scenes[14] = ("Strobe Off", None, None)

scenes[18] = ("Police A", left_half_color(255, 0, 0), None)
scenes[19] = ("Police B", right_half_color(0, 0, 255), None)

# Rainbow across 24 columns
rainbow_c = {}
for col in range(COLUMNS):
    hue = col / COLUMNS * 360
    r, g, b = hsv_to_rgb(hue, 1.0, 1.0)
    rainbow_c[col_to_bottom_zone(col)] = (r, g, b)
    rainbow_c[col_to_top_zone(col)] = (r, g, b)
scenes[21] = ("Rainbow", rainbow_c, None)

# Color Wipe (8 steps)
for step in range(8):
    fill_cols = int((step + 1) / 8 * COLUMNS)
    cz = {}
    for col in range(fill_cols):
        hue = col / COLUMNS * 360
        r, g, b = hsv_to_rgb(hue, 1.0, 1.0)
        cz[col_to_bottom_zone(col)] = (r, g, b)
        cz[col_to_top_zone(col)] = (r, g, b)
    scenes[22 + step] = (f"Wipe {step + 1}", cz, None)

# Knight Rider (8 positions)
kr_width = 3
for step in range(8):
    center_col = int((step + 0.5) / 8 * COLUMNS)
    cz = {}
    for col in range(COLUMNS):
        dist = abs(col - center_col)
        if dist <= kr_width:
            val = int(255 * (1.0 - dist / (kr_width + 1)) ** 1.5)
            cz[col_to_bottom_zone(col)] = (val, 0, 0)
            cz[col_to_top_zone(col)] = (val, 0, 0)
    scenes[31 + step] = (f"KR {step + 1}", cz, None)

# Alternating odd/even columns
odd_cz, even_cz = {}, {}
odd_wz, even_wz = {}, {}
for col in range(COLUMNS):
    if col % 2 == 0:
        odd_cz[col_to_bottom_zone(col)] = (255, 255, 255)
        odd_cz[col_to_top_zone(col)] = (255, 255, 255)
        odd_wz[col] = 255
    else:
        even_cz[col_to_bottom_zone(col)] = (255, 255, 255)
        even_cz[col_to_top_zone(col)] = (255, 255, 255)
        even_wz[col] = 255
scenes[40] = ("Alt Odd",  odd_cz,  odd_wz)
scenes[41] = ("Alt Even", even_cz, even_wz)

# White Chase (4 positions)
cw = COLUMNS // 4
for step in range(4):
    start = step * cw
    wz = {w: 255 for w in range(start, min(start + cw, COLUMNS))}
    scenes[43 + step] = (f"WChase {step + 1}", None, wz)

# Color Cycle steps
scenes[48] = ("Cycle Red",    all_color(255, 0, 0),   None)
scenes[49] = ("Cycle Yellow", all_color(255, 255, 0), None)
scenes[50] = ("Cycle Green",  all_color(0, 255, 0),   None)
scenes[51] = ("Cycle Cyan",   all_color(0, 255, 255), None)
scenes[52] = ("Cycle Blue",   all_color(0, 0, 255),   None)
scenes[53] = ("Cycle Purple", all_color(180, 0, 255), None)

# Fire (4 random frames)
for step in range(4):
    cz = {}
    for col in range(COLUMNS):
        r = random.randint(180, 255)
        g = random.randint(30, 120)
        cz[col_to_bottom_zone(col)] = (r, g, 0)
        cz[col_to_top_zone(col)] = (r, g, 0)
    wz = {w: random.randint(0, 40) for w in range(COLUMNS)}
    scenes[55 + step] = (f"Fire {step + 1}", cz, wz)

# Zone scenes
scenes[60] = ("Left Red",   left_half_color(255, 0, 0),   None)
scenes[61] = ("Right Red",  right_half_color(255, 0, 0),  None)
scenes[62] = ("Left Blue",  left_half_color(0, 0, 255),   None)
scenes[63] = ("Right Blue", right_half_color(0, 0, 255),  None)

center_cz, center_wz = {}, {}
for col in range(8, 16):
    center_cz[col_to_bottom_zone(col)] = (255, 255, 255)
    center_cz[col_to_top_zone(col)] = (255, 255, 255)
    center_wz[col] = 255
scenes[64] = ("Center On", center_cz, center_wz)

edge_cz, edge_wz = {}, {}
for col in list(range(0, 4)) + list(range(20, 24)):
    edge_cz[col_to_bottom_zone(col)] = (255, 255, 255)
    edge_cz[col_to_top_zone(col)] = (255, 255, 255)
    edge_wz[col] = 255
scenes[65] = ("Edges On", edge_cz, edge_wz)
scenes[66] = ("All White Only", None, all_white(255))


# ---- CHASER DEFINITIONS ----

chasers = {}
chasers[15] = ("Strobe Slow",      [(13, 400), (14, 400)],                     "Forward", "Loop")
chasers[16] = ("Strobe Medium",    [(13, 150), (14, 150)],                     "Forward", "Loop")
chasers[17] = ("Strobe Fast",      [(13, 60),  (14, 60)],                      "Forward", "Loop")
chasers[20] = ("Police Lights",    [(18, 120), (14, 40), (19, 120), (14, 40)], "Forward", "Loop")
chasers[30] = ("Color Wipe",       [(22+i, 180) for i in range(8)],            "Forward", "Loop")
chasers[39] = ("Knight Rider",     [(31+i, 80) for i in range(8)],             "Forward", "PingPong")
chasers[42] = ("Alternating Flash",[(40, 250), (41, 250)],                     "Forward", "Loop")
chasers[47] = ("White Chase",      [(43+i, 120) for i in range(4)],            "Forward", "Loop")
chasers[54] = ("Color Cycle",      [(48+i, 800) for i in range(6)],            "Forward", "Loop")
chasers[59] = ("Fire Effect",      [(55+i, 70) for i in range(4)],             "Forward", "Loop")


# ---- SLIDER CHANNEL MAPPINGS ----

def get_slider_channels(slider_id):
    all_red_ch   = [z * 3     for z in range(48)]
    all_green_ch = [z * 3 + 1 for z in range(48)]
    all_blue_ch  = [z * 3 + 2 for z in range(48)]
    all_white_ch = [144 + w   for w in range(24)]

    left_zones  = list(range(12)) + [47 - c for c in range(12)]
    right_zones = list(range(12, 24)) + [47 - c for c in range(12, 24)]

    mapping = {
        106: all_red_ch,
        107: all_green_ch,
        108: all_blue_ch,
        109: all_white_ch,
        302: sorted([z * 3     for z in left_zones]),
        304: sorted([z * 3 + 1 for z in left_zones]),
        306: sorted([z * 3 + 2 for z in left_zones]),
        308: [144 + w for w in range(12)],
        311: sorted([z * 3     for z in right_zones]),
        313: sorted([z * 3 + 1 for z in right_zones]),
        315: sorted([z * 3 + 2 for z in right_zones]),
        317: [144 + w for w in range(12, 24)],
    }
    return mapping.get(slider_id)


# ---- LINE-BY-LINE QXW PROCESSOR ----

def update_qxw():
    with open(QXW_PATH, "r") as f:
        lines = f.readlines()

    output = []
    i = 0
    stats = {"scenes": 0, "chasers": 0, "sliders": 0}

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        func_match = re.match(
            r'\s*<Function ID="(\d+)" Type="(Scene|Chaser)" Name="([^"]*)">', stripped)
        if func_match:
            func_id = int(func_match.group(1))
            func_type = func_match.group(2)

            j = i + 1
            depth = 1
            while j < len(lines) and depth > 0:
                if '</Function>' in lines[j]: depth -= 1
                if '<Function ' in lines[j] and '</Function>' not in lines[j]: depth += 1
                j += 1

            if func_type == "Scene" and func_id in scenes:
                name, cz, wz = scenes[func_id]
                fv = make_fixture_val(cz, wz)
                output.append(f'  <Function ID="{func_id}" Type="Scene" Name="{name}">\n')
                output.append(f'   <Speed FadeIn="0" FadeOut="0" Duration="0"/>\n')
                if fv:
                    output.append(f'   <FixtureVal ID="{FIXTURE_ID}">{fv}</FixtureVal>\n')
                else:
                    output.append(f'   <FixtureVal ID="{FIXTURE_ID}"/>\n')
                output.append(f'  </Function>\n')
                stats["scenes"] += 1
                i = j
                continue

            elif func_type == "Chaser" and func_id in chasers:
                name, steps, direction, run_order = chasers[func_id]
                output.append(f'  <Function ID="{func_id}" Type="Chaser" Name="{name}">\n')
                output.append(f'   <Speed FadeIn="0" FadeOut="0" Duration="0"/>\n')
                output.append(f'   <Direction>{direction}</Direction>\n')
                output.append(f'   <RunOrder>{run_order}</RunOrder>\n')
                output.append(f'   <SpeedModes FadeIn="Default" FadeOut="Default" Duration="Common"/>\n')
                for si, (scene_id, hold) in enumerate(steps):
                    output.append(f'   <Step Number="{si}" FadeIn="0" Hold="{hold}" FadeOut="0">{scene_id}</Step>\n')
                output.append(f'  </Function>\n')
                stats["chasers"] += 1
                i = j
                continue

        slider_match = re.match(r'\s*<Slider Caption="[^"]*" ID="(\d+)"', stripped)
        if slider_match:
            sid = int(slider_match.group(1))
            ch_map = get_slider_channels(sid)
            if ch_map is not None:
                output.append(line)
                i += 1
                while i < len(lines):
                    sline = lines[i].strip()
                    if sline.startswith('<Level '):
                        val_match = re.search(r'Value="(\d+)"', sline)
                        val = val_match.group(1) if val_match else "0"
                        if not sline.endswith('/>'):
                            while i < len(lines) and '</Level>' not in lines[i]:
                                i += 1
                        output.append(f'    <Level LowLimit="0" HighLimit="255" Value="{val}">\n')
                        for ch in ch_map:
                            output.append(f'     <Channel Fixture="{FIXTURE_ID}">{ch}</Channel>\n')
                        output.append(f'    </Level>\n')
                        stats["sliders"] += 1
                        i += 1
                        continue
                    elif sline == '</Slider>':
                        output.append(lines[i])
                        i += 1
                        break
                    else:
                        output.append(lines[i])
                        i += 1
                continue

        output.append(line)
        i += 1

    with open(QXW_PATH, "w") as f:
        f.writelines(output)
    return stats


if __name__ == "__main__":
    stats = update_qxw()
    print(f"Scenes:  {stats['scenes']}/{len(scenes)}")
    print(f"Chasers: {stats['chasers']}/{len(chasers)}")
    print(f"Sliders: {stats['sliders']}")
    print(f"Written: {QXW_PATH}")
