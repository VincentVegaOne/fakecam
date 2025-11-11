#!/usr/bin/env python3
"""
Unit tests for preferences module.

Tests preference loading, saving, and validation.
"""

import unittest
import tempfile
from pathlib import Path

from ..utils.preferences import Preferences


class TestPreferences(unittest.TestCase):
    """Test cases for Preferences class."""

    def setUp(self):
        """Set up test fixtures."""
        # Use temporary file for testing
        self.temp_file = Path(tempfile.mktemp(suffix='.json'))
        self.prefs = Preferences(self.temp_file)

    def tearDown(self):
        """Clean up after tests."""
        if self.temp_file.exists():
            self.temp_file.unlink()

    def test_get_default_value(self):
        """Test getting default values."""
        value = self.prefs.get("video_selection")
        self.assertEqual(value, "Test Pattern")

    def test_set_and_get(self):
        """Test setting and getting values."""
        self.prefs.set("video_selection", "🏄 Surfing HD")
        value = self.prefs.get("video_selection")
        self.assertEqual(value, "🏄 Surfing HD")

    def test_save_and_load(self):
        """Test saving and loading preferences."""
        self.prefs.set("video_selection", "🌊 Ocean Waves")
        self.prefs.set("vm_mode", True)
        self.prefs.save()

        # Load in new instance
        new_prefs = Preferences(self.temp_file)
        self.assertEqual(new_prefs.get("video_selection"), "🌊 Ocean Waves")
        self.assertEqual(new_prefs.get("vm_mode"), True)

    def test_invalid_key(self):
        """Test setting invalid key raises error."""
        with self.assertRaises(ValueError):
            self.prefs.set("invalid_key", "value")

    def test_invalid_type(self):
        """Test setting invalid type raises error."""
        with self.assertRaises(TypeError):
            self.prefs.set("vm_mode", "not_a_bool")

    def test_update_multiple(self):
        """Test updating multiple preferences."""
        updates = {
            "video_selection": "🏄 Surfing HD",
            "audio_selection": "💼 Professional Talk"
        }
        self.prefs.update(updates)

        self.assertEqual(self.prefs.get("video_selection"), "🏄 Surfing HD")
        self.assertEqual(self.prefs.get("audio_selection"), "💼 Professional Talk")

    def test_reset_to_defaults(self):
        """Test resetting to default values."""
        self.prefs.set("video_selection", "🏄 Surfing HD")
        self.prefs.reset()

        self.assertEqual(self.prefs.get("video_selection"), "Test Pattern")

    def test_dictionary_access(self):
        """Test dictionary-style access."""
        self.prefs["video_selection"] = "🌊 Ocean Waves"
        self.assertEqual(self.prefs["video_selection"], "🌊 Ocean Waves")

    def test_contains(self):
        """Test __contains__ method."""
        self.assertIn("video_selection", self.prefs)
        self.assertNotIn("nonexistent", self.prefs)


if __name__ == '__main__':
    unittest.main()
