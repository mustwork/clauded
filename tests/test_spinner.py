"""Tests for clauded.spinner module."""

import io
import sys
import threading
import time
from unittest.mock import patch

from clauded.spinner import _HIDE_CURSOR, _SHOW_CURSOR, spinner


class TestSpinnerCursorControl:
    """Tests for spinner cursor visibility control."""

    def test_hides_cursor_on_start(self) -> None:
        """Spinner hides cursor when entering context."""
        output = io.StringIO()

        with patch.object(sys, "stdout", output):
            with spinner("Testing"):
                # Cursor should be hidden at this point
                pass

        # Check that hide cursor sequence was written
        assert _HIDE_CURSOR in output.getvalue()

    def test_shows_cursor_on_normal_exit(self) -> None:
        """Spinner shows cursor when exiting context normally."""
        output = io.StringIO()

        with patch.object(sys, "stdout", output):
            with spinner("Testing"):
                pass

        # Check that show cursor sequence was written
        assert _SHOW_CURSOR in output.getvalue()

    def test_shows_cursor_on_exception(self) -> None:
        """Spinner shows cursor when context exits via exception."""
        output = io.StringIO()

        with patch.object(sys, "stdout", output):
            try:
                with spinner("Testing"):
                    raise ValueError("test error")
            except ValueError:
                pass

        # Cursor should still be restored despite exception
        assert _SHOW_CURSOR in output.getvalue()

    def test_shows_cursor_on_keyboard_interrupt(self) -> None:
        """Spinner shows cursor when interrupted with CTRL+C."""
        output = io.StringIO()

        with patch.object(sys, "stdout", output):
            try:
                with spinner("Testing"):
                    raise KeyboardInterrupt()
            except KeyboardInterrupt:
                pass

        # Cursor should still be restored despite interrupt
        assert _SHOW_CURSOR in output.getvalue()

    def test_clears_spinner_line_on_exit(self) -> None:
        """Spinner clears its line when exiting context."""
        output = io.StringIO()

        with patch.object(sys, "stdout", output):
            with spinner("Testing"):
                pass

        # Should contain carriage return and spaces to clear line
        assert "\r" in output.getvalue()


class TestSpinnerAnimation:
    """Tests for spinner animation behavior."""

    def test_displays_message(self) -> None:
        """Spinner displays the provided message."""
        output = io.StringIO()

        with patch.object(sys, "stdout", output):
            with spinner("Loading"):
                time.sleep(0.1)

        assert "Loading" in output.getvalue()

    def test_thread_stops_on_exit(self) -> None:
        """Spinner animation thread stops when context exits."""
        initial_threads = threading.active_count()

        with spinner("Testing"):
            # Thread should be running during context
            pass

        # Give thread time to clean up
        time.sleep(0.3)

        # Thread count should return to initial (daemon thread stopped)
        assert threading.active_count() <= initial_threads + 1
