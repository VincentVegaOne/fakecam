#!/usr/bin/env python3
"""
Unit tests for configuration module.

Tests configuration settings, validation, and VM detection.
"""

import unittest
from pathlib import Path

from ..utils.config import Config, ProcessState


class TestConfig(unittest.TestCase):
    """Test cases for Config class."""

    def test_video_settings_normal_mode(self):
        """Test video settings in normal mode."""
        settings = Config.get_video_settings(vm_mode=False)

        self.assertEqual(settings['width'], Config.DEFAULT_WIDTH)
        self.assertEqual(settings['height'], Config.DEFAULT_HEIGHT)
        self.assertEqual(settings['framerate'], Config.DEFAULT_FRAMERATE)

    def test_video_settings_vm_mode(self):
        """Test video settings in VM mode."""
        settings = Config.get_video_settings(vm_mode=True)

        self.assertEqual(settings['width'], Config.VM_WIDTH)
        self.assertEqual(settings['height'], Config.VM_HEIGHT)
        self.assertEqual(settings['framerate'], Config.VM_FRAMERATE)

    def test_ensure_directories(self):
        """Test directory creation."""
        Config.ensure_directories()

        self.assertTrue(Config.VIDEO_DIR.exists())
        self.assertTrue(Config.AUDIO_DIR.exists())

    def test_video_library_structure(self):
        """Test video library has correct structure."""
        self.assertIn("Test Pattern", Config.VIDEO_LIBRARY)
        self.assertIn("type", Config.VIDEO_LIBRARY["Test Pattern"])

    def test_audio_library_structure(self):
        """Test audio library has correct structure."""
        self.assertIn("🎤 Meeting Voice", Config.AUDIO_LIBRARY)
        self.assertIn("file", Config.AUDIO_LIBRARY["🎤 Meeting Voice"])

    def test_process_states(self):
        """Test ProcessState enum."""
        self.assertEqual(ProcessState.STOPPED.value, "stopped")
        self.assertEqual(ProcessState.RUNNING.value, "running")
        self.assertEqual(ProcessState.ERROR.value, "error")


if __name__ == '__main__':
    unittest.main()
