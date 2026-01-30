"""Simple terminal spinner for long-running operations."""

import sys
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager

# ANSI escape sequences for cursor control
_HIDE_CURSOR = "\033[?25l"
_SHOW_CURSOR = "\033[?25h"


@contextmanager
def spinner(message: str) -> Iterator[None]:
    """Display a spinner with a message while code executes.

    Hides the cursor during animation and restores it on completion or
    interruption. The spinner line is cleared on exit.

    Usage:
        with spinner("Detecting frameworks"):
            # long running operation
            detect_frameworks()
    """
    frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    stop_event = threading.Event()
    current_frame = [0]

    def animate() -> None:
        while not stop_event.is_set():
            frame = frames[current_frame[0] % len(frames)]
            sys.stdout.write(f"\r  {frame} {message}")
            sys.stdout.flush()
            current_frame[0] += 1
            time.sleep(0.08)

    # Hide cursor during animation
    sys.stdout.write(_HIDE_CURSOR)
    sys.stdout.flush()

    thread = threading.Thread(target=animate, daemon=True)
    thread.start()

    try:
        yield
    finally:
        stop_event.set()
        thread.join(timeout=0.2)
        # Clear the spinner line and restore cursor visibility
        sys.stdout.write("\r" + " " * (len(message) + 6) + "\r")
        sys.stdout.write(_SHOW_CURSOR)
        sys.stdout.flush()
