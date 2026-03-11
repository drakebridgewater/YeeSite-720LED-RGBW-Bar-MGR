#!/usr/bin/env python3
"""
Regenerate the QXF fixture definition for the YeeSite 200W 720LED RGBW Bar.

Physical layout (6 LEDs tall x 120 LEDs wide, zones are 2x5 LEDs):
  Top row:     24 color zones (RGB) — DMX zones 25-48, physically R→L (counter-clockwise)
  Middle row:  24 white zones (W)   — left to right
  Bottom row:  24 color zones (RGB) — DMX zones 1-24, physically L→R

168-channel DMX:
  Ch 0-143:   48 color zones × 3 (R, G, B)
  Ch 144-167: 24 white zones × 1

Usage:
  python3 rebuild_qxf.py
  # Writes: ../YeeSite-720LED-RGBW-Bar-ALL-MODES.qxf
"""

import os

NUM_COLOR_ZONES = 48
NUM_WHITE_ZONES = 24
OUTPUT = os.path.join(os.path.dirname(__file__), "..", "YeeSite-720LED-RGBW-Bar-ALL-MODES.qxf")


def generate_qxf():
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<!DOCTYPE FixtureDefinition>',
        '<FixtureDefinition xmlns="http://www.qlcplus.org/FixtureDefinition">',
        ' <Creator>',
        '  <Name>Q Light Controller Plus</Name>',
        '  <Version>5.2.0</Version>',
        '  <Author>Drake</Author>',
        ' </Creator>',
        ' <Manufacturer>YeeSite</Manufacturer>',
        ' <Model>200W 720LED RGBW DJ Strobe Bar</Model>',
        ' <Type>LED Bar (Pixels)</Type>',
    ]

    # Global channels (6ch and 10ch modes)
    global_channels = [
        ('Dimmer',            'Intensity', None,    [('0', '255', 'Master Dimmer 0-100%')]),
        ('Red',               'Intensity', 'Red',   [('0', '255', 'Red 0-100%')]),
        ('Green',             'Intensity', 'Green', [('0', '255', 'Green 0-100%')]),
        ('Blue',              'Intensity', 'Blue',  [('0', '255', 'Blue 0-100%')]),
        ('White',             'Intensity', 'White', [('0', '255', 'White 0-100%')]),
        ('Strobe',            'Shutter',   None,    [('0', '10', 'Shutter Open'), ('11', '255', 'Strobe slow to fast')]),
        ('Auto Program',      'Effect',    None,    [('0', '0', 'Manual (DMX)'), ('1', '255', 'Auto programs 1-12')]),
        ('Program Speed',     'Speed',     None,    [('0', '255', 'Speed slow to fast')]),
        ('Sound Sensitivity', 'Effect',    None,    [('0', '10', 'Sound OFF'), ('11', '255', 'Sound sensitivity low-high')]),
        ('Dimmer Speed',      'Speed',     None,    [('0', '255', 'Dimmer fade speed')]),
    ]

    for name, group, colour, caps in global_channels:
        lines.append(f' <Channel Name="{name}">')
        lines.append(f'  <Group Byte="0">{group}</Group>')
        if colour:
            lines.append(f'  <Colour>{colour}</Colour>')
        for cmin, cmax, cdesc in caps:
            lines.append(f'  <Capability Min="{cmin}" Max="{cmax}">{cdesc}</Capability>')
        lines.append(' </Channel>')

    # 48 color zone channels (RGB)
    for z in range(1, NUM_COLOR_ZONES + 1):
        for color, cname in [('Red', 'Red'), ('Green', 'Green'), ('Blue', 'Blue')]:
            lines.append(f' <Channel Name="CZ{z} {color}">')
            lines.append(f'  <Group Byte="0">Intensity</Group>')
            lines.append(f'  <Colour>{cname}</Colour>')
            lines.append(f'  <Capability Min="0" Max="255">Color Zone {z} {color}</Capability>')
            lines.append(f' </Channel>')

    # 24 white zone channels
    for w in range(1, NUM_WHITE_ZONES + 1):
        lines.append(f' <Channel Name="WZ{w}">')
        lines.append(f'  <Group Byte="0">Intensity</Group>')
        lines.append(f'  <Colour>White</Colour>')
        lines.append(f'  <Capability Min="0" Max="255">White Zone {w}</Capability>')
        lines.append(f' </Channel>')

    # 6-Channel Mode
    lines.append(' <Mode Name="6-Channel">')
    for i, name in enumerate(['Red', 'Green', 'Blue', 'White', 'Dimmer', 'Strobe']):
        lines.append(f'  <Channel Number="{i}">{name}</Channel>')
    lines.append('  <Head>')
    for i in range(6):
        lines.append(f'   <Channel>{i}</Channel>')
    lines.append('  </Head>')
    lines.append(' </Mode>')

    # 10-Channel Mode
    lines.append(' <Mode Name="10-Channel">')
    for i, name in enumerate(['Dimmer', 'Red', 'Green', 'Blue', 'White', 'Strobe',
                               'Auto Program', 'Program Speed', 'Sound Sensitivity', 'Dimmer Speed']):
        lines.append(f'  <Channel Number="{i}">{name}</Channel>')
    lines.append('  <Head>')
    for i in range(10):
        lines.append(f'   <Channel>{i}</Channel>')
    lines.append('  </Head>')
    lines.append(' </Mode>')

    # 168-Channel Mode
    lines.append(' <Mode Name="168-Channel">')
    ch = 0
    for z in range(1, NUM_COLOR_ZONES + 1):
        for color in ['Red', 'Green', 'Blue']:
            lines.append(f'  <Channel Number="{ch}">CZ{z} {color}</Channel>')
            ch += 1
    for w in range(1, NUM_WHITE_ZONES + 1):
        lines.append(f'  <Channel Number="{ch}">WZ{w}</Channel>')
        ch += 1

    for z in range(NUM_COLOR_ZONES):
        base = z * 3
        lines.append('  <Head>')
        lines.append(f'   <Channel>{base}</Channel>')
        lines.append(f'   <Channel>{base + 1}</Channel>')
        lines.append(f'   <Channel>{base + 2}</Channel>')
        lines.append('  </Head>')
    for w in range(NUM_WHITE_ZONES):
        lines.append('  <Head>')
        lines.append(f'   <Channel>{144 + w}</Channel>')
        lines.append('  </Head>')
    lines.append(' </Mode>')

    lines.extend([
        ' <Physical>',
        '  <Bulb Type="" Lumens="0" ColourTemperature="0"/>',
        '  <Dimensions Weight="0" Width="970" Height="70" Depth="60"/>',
        '  <Lens Name="Other" DegreesMin="0" DegreesMax="0"/>',
        '  <Focus Type="Fixed" PanMax="0" TiltMax="0"/>',
        '  <Technical PowerConsumption="200" DmxConnector="3-pin"/>',
        ' </Physical>',
        '</FixtureDefinition>',
    ])
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    qxf = generate_qxf()
    with open(OUTPUT, "w") as f:
        f.write(qxf)
    print(f"Written: {OUTPUT}")
