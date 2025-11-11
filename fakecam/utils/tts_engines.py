#!/usr/bin/env python3
"""
Text-to-Speech (TTS) engine abstraction layer for FakeCam.

This module provides a secure, extensible interface for multiple TTS engines,
with proper error handling and no shell injection vulnerabilities.

Security Note:
    All TTS engines use subprocess with argument lists (no shell=True)
    to prevent command injection vulnerabilities.
"""

import subprocess
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod

from .config import Config


logger = logging.getLogger(__name__)


class TTSEngine(ABC):
    """Abstract base class for TTS engines."""

    def __init__(self, name: str):
        """
        Initialize TTS engine.

        Args:
            name: Human-readable name of the engine
        """
        self.name = name

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if this TTS engine is available on the system.

        Returns:
            bool: True if engine is available
        """
        pass

    @abstractmethod
    def synthesize(self, text: str, output_file: Path, **kwargs) -> bool:
        """
        Synthesize speech from text.

        Args:
            text: Text to synthesize
            output_file: Path where audio file should be saved
            **kwargs: Engine-specific parameters

        Returns:
            bool: True if synthesis succeeded
        """
        pass

    def _check_command(self, command: str) -> bool:
        """
        Check if a command is available.

        Args:
            command: Command name to check

        Returns:
            bool: True if command exists
        """
        try:
            result = subprocess.run(
                ["which", command],
                capture_output=True,
                timeout=1
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False


class FliteTTS(TTSEngine):
    """
    Flite TTS engine - lightweight but natural sounding.

    Provides multiple voice options and good quality.
    """

    VOICES = {
        "Meeting Voice": "slt",     # Female
        "Professional Talk": "awb",  # Male
        "Casual Chat": "awb",
        "Quick Update": "slt",
        "Test Audio": "kal"          # Male
    }

    def __init__(self):
        """Initialize Flite TTS engine."""
        super().__init__("Flite")

    def is_available(self) -> bool:
        """Check if flite is installed."""
        return self._check_command("flite")

    def synthesize(self, text: str, output_file: Path, voice: str = "slt") -> bool:
        """
        Synthesize speech using Flite.

        Args:
            text: Text to synthesize
            output_file: Output WAV file path
            voice: Voice name (slt, awb, kal, etc.)

        Returns:
            bool: True if successful
        """
        try:
            # Note: Using list arguments prevents shell injection
            cmd = ["flite", "-voice", voice, "-t", text, "-o", str(output_file)]
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=30
            )

            if result.returncode == 0 and output_file.exists():
                logger.info(f"Flite synthesis successful with voice '{voice}'")
                return True
            else:
                logger.warning(f"Flite synthesis failed: {result.stderr.decode()[:100]}")
                return False

        except subprocess.TimeoutExpired:
            logger.error("Flite synthesis timed out")
            return False
        except Exception as e:
            logger.error(f"Flite synthesis error: {e}")
            return False


class PicoTTS(TTSEngine):
    """
    Pico TTS engine - very natural sounding, if available.

    Typically available on Debian-based systems.
    """

    def __init__(self):
        """Initialize Pico TTS engine."""
        super().__init__("Pico2Wave")

    def is_available(self) -> bool:
        """Check if pico2wave is installed."""
        return self._check_command("pico2wave")

    def synthesize(self, text: str, output_file: Path, language: str = "en-US") -> bool:
        """
        Synthesize speech using Pico TTS.

        Args:
            text: Text to synthesize
            output_file: Output WAV file path
            language: Language code (e.g., 'en-US', 'en-GB')

        Returns:
            bool: True if successful
        """
        try:
            cmd = ["pico2wave", "-l", language, "-w", str(output_file), text]
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=30
            )

            if result.returncode == 0 and output_file.exists():
                logger.info("Pico TTS synthesis successful")
                return True
            else:
                logger.warning(f"Pico TTS synthesis failed: {result.stderr.decode()[:100]}")
                return False

        except subprocess.TimeoutExpired:
            logger.error("Pico TTS synthesis timed out")
            return False
        except Exception as e:
            logger.error(f"Pico TTS synthesis error: {e}")
            return False


class ESpeakNGTTS(TTSEngine):
    """
    eSpeak-NG TTS engine - improved version of eSpeak.

    Offers multiple voices and better quality than original eSpeak.
    """

    def __init__(self):
        """Initialize eSpeak-NG TTS engine."""
        super().__init__("eSpeak-NG")

    def is_available(self) -> bool:
        """Check if espeak-ng is installed."""
        return self._check_command("espeak-ng")

    def synthesize(
        self,
        text: str,
        output_file: Path,
        voice: str = "en+m3",
        speed: int = Config.ESPEAK_SPEED,
        pitch: int = Config.ESPEAK_PITCH,
        amplitude: int = Config.ESPEAK_AMPLITUDE
    ) -> bool:
        """
        Synthesize speech using eSpeak-NG.

        Args:
            text: Text to synthesize
            output_file: Output WAV file path
            voice: Voice variant (e.g., 'en+f3', 'en+m3')
            speed: Speaking speed in words per minute
            pitch: Pitch adjustment (0-99)
            amplitude: Volume amplitude (0-200)

        Returns:
            bool: True if successful
        """
        try:
            cmd = [
                "espeak-ng",
                "-v", voice,
                "-s", str(speed),
                "-p", str(pitch),
                "-a", str(amplitude),
                "-w", str(output_file),
                text
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=30
            )

            if result.returncode == 0 and output_file.exists():
                logger.info(f"eSpeak-NG synthesis successful with voice '{voice}'")
                return True
            else:
                logger.warning(f"eSpeak-NG synthesis failed: {result.stderr.decode()[:100]}")
                return False

        except subprocess.TimeoutExpired:
            logger.error("eSpeak-NG synthesis timed out")
            return False
        except Exception as e:
            logger.error(f"eSpeak-NG synthesis error: {e}")
            return False


class ESpeakTTS(TTSEngine):
    """
    eSpeak TTS engine - fallback option, always available.

    Original eSpeak engine, widely available but lower quality.
    """

    def __init__(self):
        """Initialize eSpeak TTS engine."""
        super().__init__("eSpeak")

    def is_available(self) -> bool:
        """Check if espeak is installed."""
        return self._check_command("espeak")

    def synthesize(
        self,
        text: str,
        output_file: Path,
        voice: str = "en+f3",
        speed: int = Config.ESPEAK_SPEED,
        pitch: int = Config.ESPEAK_PITCH,
        amplitude: int = Config.ESPEAK_AMPLITUDE
    ) -> bool:
        """
        Synthesize speech using eSpeak.

        Args:
            text: Text to synthesize
            output_file: Output WAV file path
            voice: Voice variant
            speed: Speaking speed in words per minute
            pitch: Pitch adjustment (0-99)
            amplitude: Volume amplitude (0-200)

        Returns:
            bool: True if successful
        """
        try:
            cmd = [
                "espeak",
                "-v", voice,
                "-s", str(speed),
                "-p", str(pitch),
                "-a", str(amplitude),
                "-w", str(output_file),
                text
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=30
            )

            if result.returncode == 0 and output_file.exists():
                logger.info(f"eSpeak synthesis successful with voice '{voice}'")
                return True
            else:
                logger.warning(f"eSpeak synthesis failed: {result.stderr.decode()[:100]}")
                return False

        except subprocess.TimeoutExpired:
            logger.error("eSpeak synthesis timed out")
            return False
        except Exception as e:
            logger.error(f"eSpeak synthesis error: {e}")
            return False


class FestivalTTS(TTSEngine):
    """
    Festival TTS engine - good quality but slower.

    Provides natural voices but synthesis is slower than other engines.
    """

    def __init__(self):
        """Initialize Festival TTS engine."""
        super().__init__("Festival")

    def is_available(self) -> bool:
        """Check if festival and text2wave are installed."""
        return self._check_command("text2wave")

    def synthesize(
        self,
        text: str,
        output_file: Path,
        voice: str = "cmu_us_slt_arctic_hts"
    ) -> bool:
        """
        Synthesize speech using Festival.

        Args:
            text: Text to synthesize
            output_file: Output WAV file path
            voice: Voice name

        Returns:
            bool: True if successful
        """
        try:
            # Festival uses stdin for text input - SAFE, no shell injection
            cmd = [
                "text2wave",
                "-eval", f"(voice_{voice})",
                "-o", str(output_file)
            ]
            result = subprocess.run(
                cmd,
                input=text.encode(),
                capture_output=True,
                timeout=30
            )

            if result.returncode == 0 and output_file.exists():
                logger.info(f"Festival synthesis successful with voice '{voice}'")
                return True
            else:
                logger.warning(f"Festival synthesis failed: {result.stderr.decode()[:100]}")
                return False

        except subprocess.TimeoutExpired:
            logger.error("Festival synthesis timed out")
            return False
        except Exception as e:
            logger.error(f"Festival synthesis error: {e}")
            return False


class TTSManager:
    """
    TTS Manager - selects best available engine and handles synthesis.

    Tries engines in order of preference and falls back to alternatives
    if the preferred engine is not available.
    """

    def __init__(self):
        """Initialize TTS manager with all available engines."""
        self.engines: Dict[str, TTSEngine] = {
            "flite": FliteTTS(),
            "pico2wave": PicoTTS(),
            "espeak-ng": ESpeakNGTTS(),
            "festival": FestivalTTS(),
            "espeak": ESpeakTTS()
        }

        # Cache available engines
        self._available_engines: Optional[Dict[str, TTSEngine]] = None

    def get_available_engines(self) -> Dict[str, TTSEngine]:
        """
        Get all available TTS engines.

        Returns:
            Dict mapping engine name to engine instance
        """
        if self._available_engines is None:
            self._available_engines = {
                name: engine
                for name, engine in self.engines.items()
                if engine.is_available()
            }
            logger.info(f"Available TTS engines: {list(self._available_engines.keys())}")

        return self._available_engines

    def get_best_engine(self) -> Optional[TTSEngine]:
        """
        Get the best available TTS engine.

        Returns:
            TTSEngine instance or None if no engine available
        """
        available = self.get_available_engines()

        # Try engines in order of preference
        for engine_name in Config.TTS_ENGINE_PRIORITY:
            if engine_name in available:
                logger.info(f"Selected TTS engine: {engine_name}")
                return available[engine_name]

        logger.error("No TTS engines available!")
        return None

    def synthesize(
        self,
        text: str,
        output_file: Path,
        audio_type: Optional[str] = None
    ) -> bool:
        """
        Synthesize speech using the best available engine.

        Args:
            text: Text to synthesize
            output_file: Output file path
            audio_type: Audio type hint for voice selection (optional)

        Returns:
            bool: True if synthesis succeeded
        """
        engine = self.get_best_engine()
        if engine is None:
            logger.error("No TTS engine available for synthesis")
            return False

        # Select appropriate voice based on audio type
        kwargs = {}
        if isinstance(engine, FliteTTS) and audio_type:
            voice = FliteTTS.VOICES.get(audio_type, "slt")
            kwargs["voice"] = voice
        elif isinstance(engine, (ESpeakNGTTS, ESpeakTTS)) and audio_type:
            # Clean up audio type name
            clean_type = audio_type.replace("🎤 ", "").replace("💼 ", "").replace(
                "☕ ", "").replace("🎯 ", "").replace("🔊 ", "")
            voice = Config.ESPEAK_VOICE_MAP.get(clean_type, "en+m3")
            kwargs["voice"] = voice

        logger.info(f"Synthesizing with {engine.name}: {text[:50]}...")
        return engine.synthesize(text, output_file, **kwargs)

    def apply_audio_enhancements(
        self,
        input_file: Path,
        output_file: Path
    ) -> bool:
        """
        Apply audio enhancements to make TTS sound more natural.

        Uses ffmpeg to apply filters that improve TTS quality:
        - Volume normalization
        - Frequency filtering
        - Dynamic compression
        - Subtle stereo widening

        Args:
            input_file: Input audio file
            output_file: Enhanced output file

        Returns:
            bool: True if successful
        """
        try:
            # Complex filter chain for natural sound
            audio_filter = (
                "volume=10dB,"                                    # Increase volume
                "highpass=f=80,"                                  # Remove low rumble
                "lowpass=f=12000,"                                # Soften harsh highs
                "equalizer=f=2000:t=h:w=200:g=2,"                # Boost speech frequencies
                "equalizer=f=300:t=h:w=100:g=-2,"                # Reduce robotic mids
                "acompressor=threshold=0.3:ratio=3:attack=5:release=100,"  # Compress dynamics
                "adelay=0.002|0.002"                              # Subtle stereo effect
            )

            cmd = [
                "ffmpeg",
                "-i", str(input_file),
                "-af", audio_filter,
                "-y",  # Overwrite output
                str(output_file)
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=30
            )

            if result.returncode == 0 and output_file.exists():
                logger.info("Audio enhancements applied successfully")
                return True
            else:
                logger.warning(f"Audio enhancement failed: {result.stderr.decode()[:100]}")
                # If enhancement fails, copy original
                if input_file.exists():
                    import shutil
                    shutil.copy(input_file, output_file)
                return False

        except subprocess.TimeoutExpired:
            logger.error("Audio enhancement timed out")
            return False
        except Exception as e:
            logger.error(f"Audio enhancement error: {e}")
            return False
