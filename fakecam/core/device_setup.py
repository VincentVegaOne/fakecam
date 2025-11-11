#!/usr/bin/env python3
"""
Device setup module for FakeCam.

Handles creation and management of virtual video and audio devices
with proper error handling and cleanup.
"""

import subprocess
import time
import logging
from pathlib import Path
from typing import Optional, List, Tuple, Dict

from ..utils.config import Config
from ..utils.process_manager import kill_processes_by_pattern


logger = logging.getLogger(__name__)


class DeviceSetupError(Exception):
    """Exception raised when device setup fails."""
    pass


class VideoDeviceManager:
    """
    Manages v4l2loopback virtual video device.

    Handles module loading/unloading, device initialization,
    and cleanup with proper error handling.
    """

    def __init__(self):
        """Initialize video device manager."""
        self.device_path = Path(Config.VIDEO_DEVICE)
        self.is_setup = False

    def is_device_available(self) -> bool:
        """
        Check if video device exists and is accessible.

        Returns:
            bool: True if device is available
        """
        return self.device_path.exists() and self.device_path.is_char_device()

    def is_module_loaded(self) -> bool:
        """
        Check if v4l2loopback module is loaded.

        Returns:
            bool: True if module is loaded
        """
        try:
            result = subprocess.run(
                ["lsmod"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return "v4l2loopback" in result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def cleanup_existing_devices(self) -> bool:
        """
        Clean up any existing video devices and processes.

        Returns:
            bool: True if cleanup successful
        """
        logger.info("Cleaning up existing video devices")

        # Kill processes using the video device
        patterns = [
            f"ffmpeg.*{Config.VIDEO_DEVICE}",
            "ffmpeg.*video10",
            "ffmpeg.*FakeCam"
        ]

        for pattern in patterns:
            kill_processes_by_pattern(pattern)

        time.sleep(Config.CLEANUP_DELAY)

        # Unload module if loaded
        if self.is_module_loaded():
            logger.info("Unloading v4l2loopback module")

            for attempt in range(Config.MAX_CLEANUP_RETRIES):
                result = subprocess.run(
                    ["sudo", "modprobe", "-r", "v4l2loopback"],
                    capture_output=True,
                    text=True
                )

                if result.returncode == 0:
                    logger.debug("Module unloaded successfully")
                    return True

                if "in use" in result.stderr.lower():
                    logger.warning(
                        f"Module in use (attempt {attempt + 1}/{Config.MAX_CLEANUP_RETRIES})"
                    )
                    # Force kill any remaining processes
                    subprocess.run(
                        ["sudo", "pkill", "-9", "-f", "video10"],
                        capture_output=True
                    )
                    time.sleep(Config.CLEANUP_DELAY)
                else:
                    logger.error(f"Failed to unload module: {result.stderr}")
                    break

        return True

    def load_module(self) -> bool:
        """
        Load v4l2loopback kernel module.

        Returns:
            bool: True if module loaded successfully

        Raises:
            DeviceSetupError: If module fails to load
        """
        logger.info("Loading v4l2loopback module")

        # Build module parameters
        params = [f"{key}={value}" for key, value in Config.V4L2_MODULE_PARAMS.items()]

        cmd = ["sudo", "modprobe", "v4l2loopback"] + params

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                error_msg = f"Failed to load module: {result.stderr}"
                logger.error(error_msg)
                raise DeviceSetupError(error_msg)

            time.sleep(Config.MODULE_RELOAD_DELAY)

            if not self.is_device_available():
                error_msg = f"Module loaded but device {Config.VIDEO_DEVICE} not created"
                logger.error(error_msg)
                raise DeviceSetupError(error_msg)

            logger.info(f"Module loaded successfully, device at {Config.VIDEO_DEVICE}")
            return True

        except subprocess.TimeoutExpired:
            error_msg = "Module load timed out"
            logger.error(error_msg)
            raise DeviceSetupError(error_msg)
        except FileNotFoundError:
            error_msg = "modprobe command not found"
            logger.error(error_msg)
            raise DeviceSetupError(error_msg)

    def set_device_permissions(self) -> bool:
        """
        Set appropriate permissions on video device.

        Returns:
            bool: True if permissions set successfully
        """
        try:
            result = subprocess.run(
                ["sudo", "chmod", "666", str(self.device_path)],
                capture_output=True,
                timeout=5
            )

            if result.returncode == 0:
                logger.debug(f"Set permissions on {self.device_path}")
                return True
            else:
                logger.warning(f"Failed to set permissions: {result.stderr.decode()}")
                return False

        except (subprocess.TimeoutExpired, FileNotFoundError):
            logger.warning("Failed to set device permissions")
            return False

    def initialize_device_format(self) -> bool:
        """
        Initialize video device format using v4l2-ctl.

        Returns:
            bool: True if initialization successful (or v4l2-ctl not available)
        """
        try:
            cmd = [
                "v4l2-ctl",
                "-d", str(self.device_path),
                f"--set-fmt-video=width={Config.DEFAULT_WIDTH},"
                f"height={Config.DEFAULT_HEIGHT},"
                f"pixelformat={Config.DEFAULT_PIXEL_FORMAT.upper()}"
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=5
            )

            if result.returncode == 0:
                logger.info("Video device format initialized")
                return True
            else:
                logger.debug("Format initialization skipped (non-critical)")
                return True  # Non-critical failure

        except FileNotFoundError:
            logger.info("v4l2-ctl not found, skipping format initialization (non-critical)")
            return True  # v4l2-ctl is optional
        except subprocess.TimeoutExpired:
            logger.warning("Format initialization timed out")
            return True  # Non-critical

    def setup(self) -> bool:
        """
        Complete video device setup process.

        Returns:
            bool: True if setup successful

        Raises:
            DeviceSetupError: If setup fails critically
        """
        logger.info("Setting up video device")

        # Step 1: Cleanup
        self.cleanup_existing_devices()

        # Step 2: Load module
        self.load_module()

        # Step 3: Set permissions
        self.set_device_permissions()

        # Step 4: Initialize format (optional)
        self.initialize_device_format()

        self.is_setup = True
        logger.info("Video device setup complete")
        return True

    def teardown(self) -> bool:
        """
        Tear down video device.

        Returns:
            bool: True if teardown successful
        """
        logger.info("Tearing down video device")
        success = self.cleanup_existing_devices()
        self.is_setup = False
        return success


class AudioDeviceManager:
    """
    Manages PulseAudio null sink for virtual microphone.

    Handles sink creation, management, and cleanup with proper
    error handling.
    """

    def __init__(self):
        """Initialize audio device manager."""
        self.sink_name = Config.AUDIO_SINK_NAME
        self.sink_description = Config.AUDIO_SINK_DESCRIPTION
        self.module_id: Optional[int] = None
        self.is_setup = False

    def is_sink_loaded(self) -> bool:
        """
        Check if audio sink is loaded.

        Returns:
            bool: True if sink exists
        """
        try:
            result = subprocess.run(
                ["pactl", "list", "short", "sinks"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return self.sink_name in result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def get_sink_module_ids(self) -> List[int]:
        """
        Get module IDs for fakecam audio sinks.

        Returns:
            List of module IDs
        """
        module_ids = []

        try:
            result = subprocess.run(
                ["pactl", "list", "short", "modules"],
                capture_output=True,
                text=True,
                timeout=5
            )

            for line in result.stdout.split('\n'):
                if "module-null-sink" in line and self.sink_name in line:
                    try:
                        module_id = int(line.split()[0])
                        module_ids.append(module_id)
                    except (ValueError, IndexError):
                        continue

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return module_ids

    def cleanup_existing_sinks(self) -> bool:
        """
        Clean up any existing audio sinks and processes.

        Returns:
            bool: True if cleanup successful
        """
        logger.info("Cleaning up existing audio sinks")

        # Kill processes using the sink
        patterns = [
            f"ffmpeg.*{self.sink_name}",
            "ffmpeg.*fakemic",
            f"ffmpeg.*{self.sink_description}"
        ]

        for pattern in patterns:
            kill_processes_by_pattern(pattern)

        time.sleep(Config.CLEANUP_DELAY)

        # Unload all fakecam null-sink modules
        module_ids = self.get_sink_module_ids()

        for module_id in module_ids:
            try:
                logger.debug(f"Unloading module {module_id}")
                subprocess.run(
                    ["pactl", "unload-module", str(module_id)],
                    capture_output=True,
                    timeout=5
                )
            except (subprocess.TimeoutExpired, FileNotFoundError):
                logger.warning(f"Failed to unload module {module_id}")

        time.sleep(Config.CLEANUP_DELAY)
        return True

    def create_sink(self) -> bool:
        """
        Create PulseAudio null sink.

        Returns:
            bool: True if sink created successfully

        Raises:
            DeviceSetupError: If sink creation fails
        """
        logger.info("Creating audio sink")

        try:
            result = subprocess.run(
                [
                    "pactl", "load-module", "module-null-sink",
                    f"sink_name={self.sink_name}",
                    f"sink_properties=device.description={self.sink_description}"
                ],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                error_msg = f"Failed to create audio sink: {result.stderr}"
                logger.error(error_msg)
                raise DeviceSetupError(error_msg)

            # Get module ID
            try:
                self.module_id = int(result.stdout.strip())
                logger.debug(f"Audio sink created with module ID {self.module_id}")
            except ValueError:
                logger.warning("Could not parse module ID")

            time.sleep(Config.CLEANUP_DELAY)

            if not self.is_sink_loaded():
                error_msg = "Sink created but not visible in pactl list"
                logger.error(error_msg)
                raise DeviceSetupError(error_msg)

            logger.info(f"Audio sink '{self.sink_name}' created successfully")
            return True

        except subprocess.TimeoutExpired:
            error_msg = "Sink creation timed out"
            logger.error(error_msg)
            raise DeviceSetupError(error_msg)
        except FileNotFoundError:
            error_msg = "pactl command not found - is PulseAudio installed?"
            logger.error(error_msg)
            raise DeviceSetupError(error_msg)

    def setup(self) -> bool:
        """
        Complete audio device setup process.

        Returns:
            bool: True if setup successful

        Raises:
            DeviceSetupError: If setup fails critically
        """
        logger.info("Setting up audio device")

        # Step 1: Cleanup
        self.cleanup_existing_sinks()

        # Step 2: Create sink
        self.create_sink()

        self.is_setup = True
        logger.info("Audio device setup complete")
        logger.info(f"Use 'Monitor of {self.sink_description}' as microphone input")
        return True

    def teardown(self) -> bool:
        """
        Tear down audio device.

        Returns:
            bool: True if teardown successful
        """
        logger.info("Tearing down audio device")
        success = self.cleanup_existing_sinks()
        self.is_setup = False
        self.module_id = None
        return success


class DeviceManager:
    """
    Unified device manager for both video and audio.

    Provides high-level interface for device setup and teardown.
    """

    def __init__(self):
        """Initialize device manager."""
        self.video = VideoDeviceManager()
        self.audio = AudioDeviceManager()

    def setup_all(self) -> Tuple[bool, bool]:
        """
        Setup both video and audio devices.

        Returns:
            Tuple of (video_success, audio_success)
        """
        video_ok = False
        audio_ok = False

        try:
            video_ok = self.video.setup()
        except DeviceSetupError as e:
            logger.error(f"Video setup failed: {e}")

        try:
            audio_ok = self.audio.setup()
        except DeviceSetupError as e:
            logger.error(f"Audio setup failed: {e}")

        return video_ok, audio_ok

    def teardown_all(self) -> bool:
        """
        Tear down both video and audio devices.

        Returns:
            bool: True if both teardowns successful
        """
        video_ok = self.video.teardown()
        audio_ok = self.audio.teardown()
        return video_ok and audio_ok

    def get_status(self) -> Dict[str, bool]:
        """
        Get status of all devices.

        Returns:
            Dictionary with device statuses
        """
        return {
            "video_device_exists": self.video.is_device_available(),
            "video_module_loaded": self.video.is_module_loaded(),
            "video_setup": self.video.is_setup,
            "audio_sink_loaded": self.audio.is_sink_loaded(),
            "audio_setup": self.audio.is_setup
        }
