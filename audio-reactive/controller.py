"""
SocketIO client wrapper for the web controller.

Supported events (mirrors server.py):
    set_color(r, g, b)          – set all RGB zones to one color
    set_brightness(value)       – master brightness 0.0–1.0
    set_speed(value)            – effect speed 0.01–10.0
    set_effect(name, **kwargs)  – start a named effect
    beat_effect(name)           – trigger beat_flash / beat_chase / beat_color_cycle
    stop()                      – stop current effect
"""
import socketio as sio_lib


class ControllerClient:
    BEAT_EFFECTS = {"beat_flash", "beat_chase", "beat_color_cycle"}

    def __init__(self, url: str):
        self.url  = url
        self._sio = sio_lib.Client(reconnection=True, reconnection_attempts=0, logger=False, engineio_logger=False)
        self._connected = False

        @self._sio.event
        def connect():
            self._connected = True
            print(f"[controller] Connected to {url}")

        @self._sio.event
        def disconnect():
            self._connected = False
            print("[controller] Disconnected")

        @self._sio.event
        def connect_error(data):
            print(f"[controller] Connection error: {data}")

    def connect(self):
        try:
            self._sio.connect(self.url, transports=["websocket"])
        except Exception as e:
            print(f"[controller] Could not connect to {self.url}: {e}")

    def disconnect(self):
        if self._connected:
            self._sio.disconnect()

    def _emit(self, event, data):
        if self._connected:
            self._sio.emit(event, data)

    def set_color(self, r: int, g: int, b: int):
        self._emit("set_color", {"r": r, "g": g, "b": b})

    def set_brightness(self, value: float):
        self._emit("set_brightness", {"value": float(value)})

    def set_speed(self, value: float):
        self._emit("set_speed", {"value": float(value)})

    def set_effect(self, name: str, **kwargs):
        self._emit("set_effect", {"name": name, **kwargs})

    def beat_effect(self, name: str = "beat_flash"):
        if name not in self.BEAT_EFFECTS:
            raise ValueError(f"Unknown beat effect: {name}. Choose from {self.BEAT_EFFECTS}")
        self._emit("set_beat_effect", {"name": name})

    def stop(self):
        self._emit("stop", {})
