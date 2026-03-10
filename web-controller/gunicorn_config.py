"""
Gunicorn config for YeeSite web controller.

Starts the animation loop in the worker process after fork, avoiding
macOS fork+threads issues (objc_initializeAfterForkError).
"""
import threading

from config import WEB_HOST, WEB_PORT

bind = f"{WEB_HOST}:{WEB_PORT}"
workers = 1
threads = 100
worker_class = "gthread"


def post_fork(server, worker):
    """Start animation loop in worker process only (after fork)."""
    from server import animation_loop

    t = threading.Thread(target=animation_loop, daemon=True)
    t.start()
