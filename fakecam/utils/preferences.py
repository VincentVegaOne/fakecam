#!/usr/bin/env python3
"""
User preferences management for FakeCam.

Handles saving and loading user preferences with proper error handling
and validation.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from .config import Config


logger = logging.getLogger(__name__)


class Preferences:
    """
    User preferences manager.

    Handles loading, saving, and validating user preferences with
    sensible defaults and error recovery.
    """

    # Default preferences
    DEFAULTS = {
        "video_selection": "Test Pattern",
        "audio_selection": "🎤 Meeting Voice",
        "vm_mode": Config.detect_vm(),
        "window_geometry": "550x850",
        "last_video_dir": str(Config.VIDEO_DIR),
        "last_audio_dir": str(Config.AUDIO_DIR),
    }

    def __init__(self, prefs_file: Optional[Path] = None):
        """
        Initialize preferences manager.

        Args:
            prefs_file: Path to preferences file (uses default if None)
        """
        self.prefs_file = prefs_file or Config.PREFS_FILE
        self._prefs: Dict[str, Any] = {}
        self.load()

    def load(self) -> bool:
        """
        Load preferences from file.

        Returns:
            bool: True if loaded successfully
        """
        if not self.prefs_file.exists():
            logger.info(f"No preferences file found, using defaults")
            self._prefs = self.DEFAULTS.copy()
            return False

        try:
            with open(self.prefs_file, 'r', encoding='utf-8') as f:
                loaded_prefs = json.load(f)

            # Validate and merge with defaults
            self._prefs = self.DEFAULTS.copy()
            for key, value in loaded_prefs.items():
                if key in self.DEFAULTS:
                    # Type validation
                    if type(value) == type(self.DEFAULTS[key]):
                        self._prefs[key] = value
                    else:
                        logger.warning(
                            f"Invalid type for preference '{key}': "
                            f"expected {type(self.DEFAULTS[key])}, got {type(value)}"
                        )

            logger.info(f"Loaded preferences from {self.prefs_file}")
            return True

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in preferences file: {e}")
            self._prefs = self.DEFAULTS.copy()
            return False
        except PermissionError as e:
            logger.error(f"Permission denied reading preferences: {e}")
            self._prefs = self.DEFAULTS.copy()
            return False
        except Exception as e:
            logger.error(f"Error loading preferences: {e}")
            self._prefs = self.DEFAULTS.copy()
            return False

    def save(self) -> bool:
        """
        Save preferences to file.

        Returns:
            bool: True if saved successfully
        """
        try:
            # Ensure parent directory exists
            self.prefs_file.parent.mkdir(parents=True, exist_ok=True)

            # Write atomically using a temporary file
            temp_file = self.prefs_file.with_suffix('.tmp')

            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self._prefs, f, indent=2, sort_keys=True)

            # Atomic rename
            temp_file.replace(self.prefs_file)

            logger.info(f"Saved preferences to {self.prefs_file}")
            return True

        except PermissionError as e:
            logger.error(f"Permission denied writing preferences: {e}")
            return False
        except IOError as e:
            logger.error(f"I/O error writing preferences: {e}")
            return False
        except Exception as e:
            logger.error(f"Error saving preferences: {e}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a preference value.

        Args:
            key: Preference key
            default: Default value if key not found

        Returns:
            Preference value or default
        """
        return self._prefs.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """
        Set a preference value.

        Args:
            key: Preference key
            value: New value

        Raises:
            ValueError: If key is not in valid preferences
        """
        if key not in self.DEFAULTS:
            raise ValueError(f"Unknown preference key: {key}")

        # Type validation
        expected_type = type(self.DEFAULTS[key])
        if not isinstance(value, expected_type):
            raise TypeError(
                f"Invalid type for '{key}': expected {expected_type}, got {type(value)}"
            )

        self._prefs[key] = value
        logger.debug(f"Set preference '{key}' = {value}")

    def update(self, prefs_dict: Dict[str, Any]) -> None:
        """
        Update multiple preferences at once.

        Args:
            prefs_dict: Dictionary of preferences to update
        """
        for key, value in prefs_dict.items():
            try:
                self.set(key, value)
            except (ValueError, TypeError) as e:
                logger.warning(f"Skipping invalid preference update: {e}")

    def reset(self) -> None:
        """Reset all preferences to defaults."""
        self._prefs = self.DEFAULTS.copy()
        logger.info("Reset preferences to defaults")

    def get_all(self) -> Dict[str, Any]:
        """
        Get all preferences.

        Returns:
            Dictionary of all preferences
        """
        return self._prefs.copy()

    def __getitem__(self, key: str) -> Any:
        """Allow dictionary-style access."""
        return self.get(key)

    def __setitem__(self, key: str, value: Any) -> None:
        """Allow dictionary-style setting."""
        self.set(key, value)

    def __contains__(self, key: str) -> bool:
        """Check if preference key exists."""
        return key in self._prefs
