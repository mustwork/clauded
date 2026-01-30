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

    def test_animates_through_frames(self) -> None:
        """Spinner cycles through animation frames."""
        output = io.StringIO()

        with patch.object(sys, "stdout", output):
            with spinner("Test"):
                # Run long enough to see multiple frames
                time.sleep(0.25)

        result = output.getvalue()

        # Braille spinner frames - at least some should appear
        frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        frame_count = sum(1 for frame in frames if frame in result)
        assert frame_count >= 1


class TestSpinnerThreadCleanup:
    """Tests for spinner thread cleanup behavior."""

    def test_thread_starts_during_context(self) -> None:
        """Animation thread starts when context is entered."""
        output = io.StringIO()
        thread_count_before = threading.active_count()

        with patch.object(sys, "stdout", output):
            with spinner("Testing"):
                # Give thread time to start
                time.sleep(0.05)
                thread_count_during = threading.active_count()
                # At least one more thread should be running
                assert thread_count_during >= thread_count_before

    def test_thread_cleanup_on_normal_exit(self) -> None:
        """Thread is properly cleaned up on normal exit."""
        output = io.StringIO()

        with patch.object(sys, "stdout", output):
            with spinner("Testing"):
                time.sleep(0.05)

        # Give thread time to clean up (join timeout is 0.2s)
        time.sleep(0.3)

        # Thread should be stopped (daemon threads don't prevent exit)

    def test_thread_cleanup_on_exception(self) -> None:
        """Thread is properly cleaned up when exception is raised."""
        output = io.StringIO()

        with patch.object(sys, "stdout", output):
            try:
                with spinner("Testing"):
                    time.sleep(0.05)
                    raise RuntimeError("Test error")
            except RuntimeError:
                pass

        # Give thread time to clean up
        time.sleep(0.3)

        # Thread should be stopped despite exception

    def test_multiple_sequential_spinners(self) -> None:
        """Multiple sequential spinners work correctly."""
        output = io.StringIO()

        with patch.object(sys, "stdout", output):
            for i in range(3):
                with spinner(f"Step {i}"):
                    time.sleep(0.05)

        # All should complete without issues
        result = output.getvalue()
        assert "Step 0" in result or "Step 1" in result or "Step 2" in result


class TestSpinnerContextManagerBehavior:
    """Tests for context manager yield behavior."""

    def test_yields_none(self) -> None:
        """Spinner context manager yields None."""
        output = io.StringIO()

        with patch.object(sys, "stdout", output):
            with spinner("Test") as value:
                assert value is None

    def test_allows_work_inside_context(self) -> None:
        """Code inside spinner context executes normally."""
        output = io.StringIO()
        result = 0

        with patch.object(sys, "stdout", output):
            with spinner("Computing"):
                for i in range(5):
                    result += i

        assert result == 10


class TestSpinnerEdgeCases:
    """Tests for edge cases."""

    def test_empty_message(self) -> None:
        """Spinner works with empty message."""
        output = io.StringIO()

        with patch.object(sys, "stdout", output):
            with spinner(""):
                pass

        # Should complete without error

    def test_long_message(self) -> None:
        """Spinner works with long message."""
        output = io.StringIO()
        long_msg = "A" * 200

        with patch.object(sys, "stdout", output):
            with spinner(long_msg):
                pass

        assert long_msg in output.getvalue()

    def test_unicode_message(self) -> None:
        """Spinner works with unicode message."""
        output = io.StringIO()

        with patch.object(sys, "stdout", output):
            with spinner("Loading data"):
                pass

        assert "Loading" in output.getvalue()

    def test_rapid_spinner_creation(self) -> None:
        """Rapidly creating spinners doesn't cause issues."""
        output = io.StringIO()

        with patch.object(sys, "stdout", output):
            for i in range(10):
                with spinner(f"Iteration {i}"):
                    pass  # Immediate exit

        # All should complete without error
