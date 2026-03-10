# YeeSite LED Controller

Web-based DMX controller for the YeeSite 720-LED RGBW bar, with a real-time UI, 26+ RGB effects, 11 white effects, zone-level control, and a REST API for Home Assistant integration.

## Hardware

- **Fixture:** YeeSite 720-LED RGBW Bar (168 DMX channels)
- **DMX Interface:** [Open Lighting Architecture (OLA)](https://www.openlighting.org/ola/) running on the network
- **Layout:** 48 RGB color zones (24 top + 24 bottom) + 24 white zones (middle row)

## Quick Start

### Run Locally

```bash
cd web-controller
pip install -r requirements.txt
python server.py
```

Open `http://localhost:5003` in a browser. The server runs under [Gunicorn](https://gunicorn.org/) with threaded workers and [simple-websocket](https://github.com/miguelgrinberg/simple-websocket) for production-ready WebSocket support.

By default the controller talks to OLA at `10.0.0.10:9090` on universe 1. Edit `config.py` or set environment variables to change this (see [Configuration](#configuration)).

### Run with Docker

```bash
cd web-controller
docker compose up -d --build
```

### Run on Unraid

1. Install the **Docker Compose** plugin from Community Applications.
2. Create a new compose stack pointing at `web-controller/docker-compose.yml`.
3. Edit the environment variables to match your OLA host, then start the stack.

Alternatively, build and push the image to a registry, then add it through the Unraid Docker UI:

| Setting | Value |
|---------|-------|
| Port | `5003` -> `5003` |
| `OLA_HOST` | IP of your OLA server |
| `OLA_PORT` | `9090` |
| `DMX_UNIVERSE` | `1` |

## Configuration

All settings can be overridden with environment variables, making Docker deployment straightforward.

| Variable | Default | Description |
|----------|---------|-------------|
| `OLA_HOST` | `10.0.0.10` | OLA server IP address |
| `OLA_PORT` | `9090` | OLA HTTP API port |
| `DMX_UNIVERSE` | `1` | DMX universe number |
| `WEB_PORT` | `5003` | Web UI / API port |
| `FPS` | `60` | Animation frame rate |

## Web UI

The controller runs at `http://<host>:5003` and provides:

- **RGBW sliders** and color picker for direct color control
- **Color presets** (keyboard shortcuts `1`-`0`)
- **26 RGB effects** — rainbow chase, fire, plasma, meteor, police, and more
- **11 white effects** — breathe, chase, twinkle, rain, etc.
- **Per-effect color customization** with live preview
- **Speed and dimmer controls** for RGB and white independently
- **Zone selection** — click, Ctrl+click, or Shift+click zones on the LED bar visualizer
- **Zone groups** — save selections with per-group color/white/dimmer controls
- **Strobe overlay** with white-only mode
- **Master brightness** and blackout toggle
- **Keyboard shortcuts** — press `?` in the UI to see all shortcuts

## REST API

### Lamp API (Home Assistant)

All endpoints are scoped by lamp ID. The built-in fixture is `yeesite-bar`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/lamps` | List all registered lamps |
| `GET` | `/api/lamps/<id>` | Full lamp state |
| `POST` | `/api/lamps/<id>/turn_on` | Turn on (accepts `brightness`, `color`, `effect`) |
| `POST` | `/api/lamps/<id>/turn_off` | Turn off (blackout) |
| `POST` | `/api/lamps/<id>/color` | Set color `{"r", "g", "b", "w"}` |
| `POST` | `/api/lamps/<id>/effect` | Set effect `{"name", "colors", "speed"}` |
| `POST` | `/api/lamps/<id>/brightness` | Set brightness `{"value": 0-255}` |
| `POST` | `/api/lamps/<id>/stop` | Stop effects, go dark |

#### Examples

```bash
# Get lamp state
curl http://localhost:5003/api/lamps/yeesite-bar

# Turn on with a color
curl -X POST http://localhost:5003/api/lamps/yeesite-bar/turn_on \
  -H "Content-Type: application/json" \
  -d '{"color": {"r": 255, "g": 0, "b": 100, "w": 0}, "brightness": 200}'

# Start an effect
curl -X POST http://localhost:5003/api/lamps/yeesite-bar/effect \
  -H "Content-Type: application/json" \
  -d '{"name": "rainbow_chase", "speed": 1.5}'

# Turn off
curl -X POST http://localhost:5003/api/lamps/yeesite-bar/turn_off
```

## Home Assistant Integration

Add a [RESTful Command](https://www.home-assistant.io/integrations/rest_command/) and [REST sensor](https://www.home-assistant.io/integrations/rest/) to your HA configuration. Replace `CONTROLLER_IP` with the IP of the machine running the controller.

### `configuration.yaml`

```yaml
rest_command:
  yeesite_turn_on:
    url: "http://CONTROLLER_IP:5003/api/lamps/yeesite-bar/turn_on"
    method: POST
    content_type: "application/json"
    payload: '{"brightness": {{ brightness | default(255) }}}'

  yeesite_turn_off:
    url: "http://CONTROLLER_IP:5003/api/lamps/yeesite-bar/turn_off"
    method: POST

  yeesite_color:
    url: "http://CONTROLLER_IP:5003/api/lamps/yeesite-bar/color"
    method: POST
    content_type: "application/json"
    payload: '{"r": {{ r }}, "g": {{ g }}, "b": {{ b }}, "w": {{ w | default(0) }}}'

  yeesite_effect:
    url: "http://CONTROLLER_IP:5003/api/lamps/yeesite-bar/effect"
    method: POST
    content_type: "application/json"
    payload: '{"name": "{{ effect }}"}'

sensor:
  - platform: rest
    name: YeeSite Bar State
    resource: "http://CONTROLLER_IP:5003/api/lamps/yeesite-bar"
    value_template: "{{ value_json.state }}"
    json_attributes:
      - brightness
      - color
      - effect
      - effect_list
      - strobe
    scan_interval: 5
```

### Template Light (optional)

Wrap the above into a [Template Light](https://www.home-assistant.io/integrations/light.template/) for a full light entity:

```yaml
light:
  - platform: template
    lights:
      yeesite_bar:
        friendly_name: "YeeSite LED Bar"
        value_template: "{{ states('sensor.yeesite_bar_state') }}"
        turn_on:
          service: rest_command.yeesite_turn_on
          data:
            brightness: "{{ brightness | default(255) }}"
        turn_off:
          service: rest_command.yeesite_turn_off
```

## Project Structure

```
web-controller/
  server.py          Flask + SocketIO backend
  config.py          DMX/OLA/network configuration (env-var overridable)
  effects.py         RGB and white effect generators
  static/
    index.html       Web UI
    app.js           Frontend logic
    style.css        Styles
  Dockerfile
  docker-compose.yml
  requirements.txt
```
