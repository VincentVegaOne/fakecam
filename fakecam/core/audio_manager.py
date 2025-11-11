#!/usr/bin/env python3
"""
Audio manager module for FakeCam.

Handles audio streaming to virtual microphone with support for
TTS, tones, and different audio sources.
"""

import subprocess
import logging
from pathlib import Path
from typing import Optional, Callable
from enum import Enum

from ..utils.config import Config
from ..utils.process_manager import ManagedProcess, get_registry
from ..utils.tts_engines import TTSManager


logger = logging.getLogger(__name__)


class AudioType(Enum):
    """Audio source types."""
    VOICE = "voice"
    TONE = "tone"
    SILENCE = "silence"


class AudioManagerError(Exception):
    """Exception raised when audio operations fail."""
    pass


class AudioGenerator:
    """
    Handles generation of audio files (TTS, tones, etc.).

    Provides audio synthesis with caching and progress tracking.
    """

    def __init__(self):
        """Initialize audio generator."""
        self.tts_manager = TTSManager()

    def generate_tone(self, output_file: Path) -> bool:
        """
        Generate a test tone.

        Args:
            output_file: Path to output file

        Returns:
            bool: True if generation successful
        """
        logger.info(f"Generating tone: {output_file}")

        try:
            # Ensure output directory exists
            output_file.parent.mkdir(parents=True, exist_ok=True)

            cmd = [
                "ffmpeg",
                "-f", "lavfi",
                "-i", f"sine=frequency={Config.TONE_FREQUENCY}:"
                      f"duration={Config.TONE_DURATION}:"
                      f"amplitude={Config.TONE_AMPLITUDE}",
                "-af", "volume=6dB",  # Boost volume
                "-y",  # Overwrite output
                str(output_file)
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=30
            )

            if result.returncode == 0 and output_file.exists():
                logger.info("Tone generated successfully")
                return True
            else:
                logger.error(f"Tone generation failed: {result.stderr.decode()[:100]}")
                return False

        except subprocess.TimeoutExpired:
            logger.error("Tone generation timed out")
            return False
        except Exception as e:
            logger.error(f"Tone generation error: {e}")
            return False

    def generate_speech(
        self,
        text: str,
        output_file: Path,
        audio_type: Optional[str] = None,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> bool:
        """
        Generate speech from text using TTS.

        Args:
            text: Text to synthesize
            output_file: Path to output file
            audio_type: Audio type hint for voice selection
            progress_callback: Optional callback(status_message)

        Returns:
            bool: True if generation successful
        """
        logger.info(f"Generating speech: {output_file}")

        try:
            # Ensure output directory exists
            output_file.parent.mkdir(parents=True, exist_ok=True)

            # Generate temporary file first
            temp_file = output_file.with_suffix('.temp.wav')

            if progress_callback:
                progress_callback("Synthesizing speech...")

            # Synthesize speech
            success = self.tts_manager.synthesize(text, temp_file, audio_type)

            if not success or not temp_file.exists():
                logger.error("TTS synthesis failed")
                return False

            if progress_callback:
                progress_callback("Enhancing audio quality...")

            # Apply enhancements
            success = self.tts_manager.apply_audio_enhancements(temp_file, output_file)

            # Clean up temp file
            temp_file.unlink(missing_ok=True)

            if success and output_file.exists():
                logger.info("Speech generated successfully")
                return True
            else:
                logger.error("Audio enhancement failed")
                return False

        except Exception as e:
            logger.error(f"Speech generation error: {e}")
            return False

    def get_audio_info(self, source: str) -> dict:
        """
        Get information about an audio source.

        Args:
            source: Audio source name

        Returns:
            Dictionary with audio info
        """
        if source not in Config.AUDIO_LIBRARY:
            raise AudioManagerError(f"Unknown audio source: {source}")

        return Config.AUDIO_LIBRARY[source].copy()


class AudioManager:
    """
    Manages audio streaming to virtual microphone.

    Handles different audio sources (TTS, tones, silence) and streaming
    with proper volume management.
    """

    def __init__(self, sink_name: str = Config.AUDIO_SINK_NAME):
        """
        Initialize audio manager.

        Args:
            sink_name: PulseAudio sink name
        """
        self.sink_name = sink_name
        self.process = ManagedProcess("AudioStream")
        self.generator = AudioGenerator()
        self.current_source: Optional[str] = None
        self._is_silence_mode = False

        # Register for cleanup
        get_registry().register(self.process)

    @property
    def is_running(self) -> bool:
        """Check if audio is currently streaming."""
        return self.process.is_running or self._is_silence_mode

    def _build_audio_stream_command(self, audio_file: Path) -> list:
        """
        Build ffmpeg command for audio streaming.

        Args:
            audio_file: Path to audio file

        Returns:
            Command as list of arguments
        """
        return [
            "ffmpeg",
            "-re",  # Read input at native frame rate
            "-stream_loop", "-1",  # Loop indefinitely
            "-i", str(audio_file),
            "-af", f"volume={Config.DEFAULT_VOLUME}",  # Amplify volume
            "-f", "pulse",
            self.sink_name
        ]

    def start(self, source: str) -> bool:
        """
        Start audio streaming.

        Args:
            source: Audio source name from Config.AUDIO_LIBRARY

        Returns:
            bool: True if started successfully

        Raises:
            AudioManagerError: If start fails
        """
        if self.is_running:
            raise AudioManagerError("Audio is already running")

        if source not in Config.AUDIO_LIBRARY:
            raise AudioManagerError(f"Unknown audio source: {source}")

        audio_info = Config.AUDIO_LIBRARY[source]
        logger.info(f"Starting audio: {source}")

        # Handle silence mode
        if audio_info.get("type") == "silence":
            logger.info("Silence mode activated")
            self._is_silence_mode = True
            self.current_source = source
            return True

        # Get audio file
        if audio_info["file"] is None:
            raise AudioManagerError(f"No file specified for source: {source}")

        audio_file = Config.AUDIO_DIR / audio_info["file"]

        # Generate if doesn't exist
        if not audio_file.exists():
            logger.info("Audio file not found, generating...")
            success = self.generate_audio(source)
            if not success or not audio_file.exists():
                raise AudioManagerError(f"Failed to generate audio: {source}")

        # Build and start command
        cmd = self._build_audio_stream_command(audio_file)

        try:
            success = self.process.start(cmd)

            if success:
                self.current_source = source
                logger.info(f"Audio started: {source}")
                return True
            else:
                raise AudioManagerError("Failed to start audio process")

        except Exception as e:
            logger.error(f"Failed to start audio: {e}")
            raise AudioManagerError(f"Failed to start audio: {e}")

    def stop(self) -> bool:
        """
        Stop audio streaming.

        Returns:
            bool: True if stopped successfully
        """
        if not self.is_running:
            logger.debug("Audio already stopped")
            return True

        logger.info("Stopping audio")

        # Handle silence mode
        if self._is_silence_mode:
            self._is_silence_mode = False
            self.current_source = None
            logger.info("Silence mode deactivated")
            return True

        # Stop normal audio process
        success = self.process.stop()

        if success:
            self.current_source = None
            logger.info("Audio stopped")

        return success

    def restart(self, source: Optional[str] = None) -> bool:
        """
        Restart audio streaming.

        Args:
            source: New audio source (uses current if None)

        Returns:
            bool: True if restarted successfully
        """
        if source is None:
            source = self.current_source

        if source is None:
            raise AudioManagerError("No source specified for restart")

        logger.info(f"Restarting audio with source: {source}")

        self.stop()
        return self.start(source)

    def generate_audio(
        self,
        source: str,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> bool:
        """
        Generate audio for a source.

        Args:
            source: Audio source name
            progress_callback: Optional progress callback

        Returns:
            bool: True if generation successful

        Raises:
            AudioManagerError: If generation fails
        """
        if source not in Config.AUDIO_LIBRARY:
            raise AudioManagerError(f"Unknown audio source: {source}")

        audio_info = Config.AUDIO_LIBRARY[source]

        # Skip silence
        if audio_info.get("type") == "silence":
            logger.info("Silence doesn't need generation")
            return True

        audio_file = Config.AUDIO_DIR / audio_info["file"]

        # Check if already exists
        if audio_file.exists():
            logger.info(f"Audio already exists: {audio_file}")
            return True

        # Generate based on type
        if audio_info.get("type") == "tone":
            return self.generator.generate_tone(audio_file)
        else:
            # Speech generation
            text = audio_info.get("text", "")
            if not text:
                raise AudioManagerError(f"No text specified for source: {source}")

            return self.generator.generate_speech(
                text,
                audio_file,
                source,
                progress_callback
            )

    def clear_audio_cache(self) -> int:
        """
        Clear all generated audio files.

        Returns:
            Number of files deleted
        """
        logger.info("Clearing audio cache")

        if not Config.AUDIO_DIR.exists():
            return 0

        count = 0
        for audio_file in Config.AUDIO_DIR.glob("*.wav"):
            try:
                audio_file.unlink()
                count += 1
                logger.debug(f"Deleted: {audio_file}")
            except Exception as e:
                logger.warning(f"Failed to delete {audio_file}: {e}")

        logger.info(f"Deleted {count} audio files")
        return count

    def get_status(self) -> dict:
        """
        Get current audio status.

        Returns:
            Dictionary with status information
        """
        return {
            "running": self.is_running,
            "source": self.current_source,
            "silence_mode": self._is_silence_mode,
            "pid": self.process.get_pid() if not self._is_silence_mode else None
        }

    def get_available_engines(self) -> list:
        """
        Get list of available TTS engines.

        Returns:
            List of engine names
        """
        engines = self.generator.tts_manager.get_available_engines()
        return list(engines.keys())
