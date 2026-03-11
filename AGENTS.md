# AI Agent Instructions

Instructions for AI assistants working on the YeeSite LED Controller codebase.

## Project Overview

Web-based DMX controller for a 720-LED RGBW bar. Stack: Python (Flask + Socket.IO) backend, vanilla JS/CSS frontend, OLA for DMX output.

## Architecture

- **`web-controller/server.py`** — Flask app, Socket.IO handlers, animation loop, REST API
- **`web-controller/effects.py`** — Effect generators (yield frame dicts). Add new effects here.
- **`web-controller/config.py`** — DMX layout, OLA URL, env vars. Use helpers like `color_zone_channels()`, `col_to_bottom_zone()`.
- **`web-controller/static/`** — `index.html`, `app.js`, `style.css` — no build step

## Key Conventions

1. **Effects** — Generators yielding `{"color": [(r,g,b)*48], "white": [w]*24}`. Color zones 0–23 = bottom row, 24–47 = top row. White zones 0–23 = middle row.
2. **Solid is default** — Clicking colors sets `solid` (color) and `w_solid` (white). An effect is always active when showing colors.
3. **Touch support** — Knobs use `touchstart`/`touchmove`/`touchend`. Hover-only UI (effect star, scene delete) should use `@media (hover: none)` for touch devices.
4. **Socket.IO events** — Client emits: `set_color`, `set_zones`, `set_effect`, `set_white_effect`, `stop`, etc. Server emits `frame` with display state.

## Effect Authoring

### Timing
- **Always use `FRAME_TIME` from config** for time increments — do NOT hardcode `1.0/40`. `FPS=60` in config, so `FRAME_TIME = 1/60`.
- The animation loop calls each generator once per `FRAME_TIME` at speed=1. At higher `effect_speed`, more steps are taken per loop tick.
- Example: `t += FRAME_TIME` advances 1 second of t per second at speed=1.

### Flash/Strobe Effects
- **Do not produce ALL-OFF frames** unless the effect is explicitly a strobe (category `"flash"`). Even `police`/`police_tb` should alternate directly between the two colors with no dark phase — blank frames cause harsh, epilepsy-risk strobing.
- `strobe` and `w_strobe` are the only intentional full-dark-cycle effects. Their `rate` parameter is set independently via the strobe-rate slider in the UI (not via `effect_speed`).

### Categories
| Category | Behavior |
|----------|----------|
| `ambient` | Smooth, low-energy (breathe, twinkle, lava, rain) |
| `color`   | Hue-shifting, always fully lit (rainbow_chase, color_cycle, plasma) |
| `chase`   | Moving spot or pattern — rest of bar may be dark (knight_rider, meteor, comet, wave) |
| `warm`    | Fire/lava palette effects |
| `flash`   | Intentional strobing or alternating (police, strobe, alternating, lightning) |

### White Effects (w_*)
- Yield a `list[int]` of 24 values (0–255), one per white zone.
- Color effects and white effects run independently; switching one does not stop the other.
- `w_solid` is the default white mode when a color is set via the sliders.

### Adding a New Effect
1. Write a generator in `effects.py` following the frame format above.
2. Add an entry to `EFFECTS` (color) or `WHITE_EFFECTS` (white) dict with `name`, `fn`, `category`, and `colors` list.
3. The UI picks it up automatically — no JS changes needed for basic effects.

## Running

```bash
cd web-controller && pip install -r requirements.txt && python server.py
```

Open http://localhost:5003. OLA defaults to `10.0.0.10:9090`; override via `OLA_HOST`, `OLA_PORT`.

## Common Tasks

| Task | Where |
|------|-------|
| Add RGB effect | `effects.py` — add generator, add to `EFFECTS` dict |
| Add white effect | `effects.py` — add generator, add to `WHITE_EFFECTS` dict |
| Add REST endpoint | `server.py` — `@app.route` or `@socketio.on` |
| Change UI layout | `static/index.html`, `style.css` |
| Add client logic | `static/app.js` — IIFE, no framework |

## Configuration

All config in `config.py`; env vars override (e.g. `OLA_HOST`, `WEB_PORT`, `DMX_UNIVERSE`).
