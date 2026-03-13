"""
Gunicorn config for YeeSite web controller.

Starts the animation loop in the worker process after fork, avoiding
macOS fork+threads issues (objc_initializeAfterForkError).
"""
import logging
import threading

from config import WEB_HOST, WEB_PORT

bind = f"{WEB_HOST}:{WEB_PORT}"
workers = 1
threads = 100
worker_class = "gthread"

# Route all gunicorn and app logs to stdout/stderr so docker logs works
accesslog = "-"
errorlog = "-"
loglevel = "info"


def post_fork(_server, _worker):
    """Start animation loop and MIDI handler in worker process only (after fork)."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    from server import animation_loop, midi_handler

    def _animation_loop_safe():
        try:
            animation_loop()
        except Exception:
            logging.exception("animation_loop crashed")

    t = threading.Thread(target=_animation_loop_safe, daemon=True)
    t.start()

    # Start MIDI in a thread so it doesn't block gunicorn startup
    mt = threading.Thread(target=midi_handler.start, daemon=True)
    mt.start()
