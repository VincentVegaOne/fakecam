#!/usr/bin/env python3
"""
Video manager module for FakeCam.

Handles video streaming to virtual camera device with support for
different sources, formats, and optimization modes.
"""

import logging
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, Callable

from ..utils.config import Config
from ..utils.process_manager import ManagedProcess, get_registry


logger = logging.getLogger(__name__)


class VideoManagerError(Exception):
    """Exception raised when video operations fail."""
    pass


class VideoDownloader:
    """
    Handles downloading of video files with progress tracking.

    Provides resumable downloads with progress callbacks and
    proper error handling.
    """

    def __init__(self):
        """Initialize video downloader."""
        self.current_download: Optional[str] = None

    def download(
        self,
        url: str,
        destination: Path,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> bool:
        """
        Download a video file.

        Args:
            url: URL to download from
            destination: Destination file path
            progress_callback: Optional callback(bytes_downloaded, total_bytes)

        Returns:
            bool: True if download successful

        Raises:
            VideoManagerError: If download fails
        """
        self.current_download = url
        logger.info(f"Downloading {url} to {destination}")

        try:
            # Ensure destination directory exists
            destination.parent.mkdir(parents=True, exist_ok=True)

            # Download with progress tracking
            def reporthook(block_num: int, block_size: int, total_size: int):
                """Progress hook for urllib."""
                if progress_callback:
                    bytes_downloaded = block_num * block_size
                    progress_callback(bytes_downloaded, total_size)

            urllib.request.urlretrieve(url, destination, reporthook=reporthook)

            if not destination.exists():
                raise VideoManagerError(f"Download completed but file not found: {destination}")

            logger.info(f"Download completed: {destination}")
            return True

        except urllib.error.HTTPError as e:
            error_msg = f"HTTP error {e.code}: {e.reason}"
            logger.error(error_msg)
            raise VideoManagerError(error_msg)
        except urllib.error.URLError as e:
            error_msg = f"URL error: {e.reason}"
            logger.error(error_msg)
            raise VideoManagerError(error_msg)
        except IOError as e:
            error_msg = f"I/O error during download: {e}"
            logger.error(error_msg)
            raise VideoManagerError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected download error: {e}"
            logger.error(error_msg)
            raise VideoManagerError(error_msg)
        finally:
            self.current_download = None


class VideoManager:
    """
    Manages video streaming to virtual camera.

    Handles different video sources (files, test patterns) and streaming
    with configurable quality settings and VM optimization.
    """

    def __init__(self, device_path: str = Config.VIDEO_DEVICE):
        """
        Initialize video manager.

        Args:
            device_path: Path to v4l2loopback device
        """
        self.device_path = device_path
        self.process = ManagedProcess("VideoStream")
        self.downloader = VideoDownloader()
        self.current_source: Optional[str] = None
        self.vm_mode = False

        # Register for cleanup
        get_registry().register(self.process)

    @property
    def is_running(self) -> bool:
        """Check if video is currently streaming."""
        return self.process.is_running

    def set_vm_mode(self, enabled: bool) -> None:
        """
        Enable or disable VM optimization mode.

        Args:
            enabled: True to enable VM optimization
        """
        self.vm_mode = enabled
        logger.info(f"VM optimization mode: {'enabled' if enabled else 'disabled'}")

    def _get_video_settings(self) -> dict:
        """
        Get current video settings based on VM mode.

        Returns:
            Dictionary with width, height, framerate
        """
        return Config.get_video_settings(self.vm_mode)

    def _build_test_pattern_command(self) -> list:
        """
        Build ffmpeg command for test pattern.

        Returns:
            Command as list of arguments
        """
        settings = self._get_video_settings()

        cmd = [
            "ffmpeg",
            "-re",  # Read input at native frame rate
            "-f", "lavfi",
            "-i", f"testsrc2=size={settings['width']}x{settings['height']}:"
                  f"rate={settings['framerate']}",
            "-pix_fmt", Config.DEFAULT_PIXEL_FORMAT,
            "-f", "v4l2",
            "-vcodec", "rawvideo"
        ]

        # Add VM optimizations if enabled
        if self.vm_mode:
            cmd.extend(Config.FFMPEG_VM_FLAGS)

        cmd.append(self.device_path)

        return cmd

    def _build_video_file_command(self, video_file: Path) -> list:
        """
        Build ffmpeg command for video file.

        Args:
            video_file: Path to video file

        Returns:
            Command as list of arguments
        """
        settings = self._get_video_settings()

        cmd = [
            "ffmpeg",
            "-re",  # Read input at native frame rate
            "-stream_loop", "-1",  # Loop indefinitely
            "-i", str(video_file),
            "-vf", f"scale={settings['width']}:{settings['height']}",
            "-pix_fmt", Config.DEFAULT_PIXEL_FORMAT,
            "-f", "v4l2",
            "-vcodec", "rawvideo"
        ]

        # Add VM optimizations if enabled
        if self.vm_mode:
            cmd.extend(Config.FFMPEG_VM_FLAGS)

        cmd.append(self.device_path)

        return cmd

    def _build_fallback_command(self) -> list:
        """
        Build fallback command (simple blue screen).

        Returns:
            Command as list of arguments
        """
        settings = self._get_video_settings()

        return [
            "ffmpeg",
            "-re",
            "-f", "lavfi",
            "-i", f"color=c=blue:s={settings['width']}x{settings['height']}:"
                  f"r={settings['framerate']}",
            "-pix_fmt", Config.DEFAULT_PIXEL_FORMAT,
            "-f", "v4l2",
            self.device_path
        ]

    def start(self, source: str) -> bool:
        """
        Start video streaming.

        Args:
            source: Video source name from Config.VIDEO_LIBRARY

        Returns:
            bool: True if started successfully

        Raises:
            VideoManagerError: If start fails
        """
        if self.is_running:
            raise VideoManagerError("Video is already running")

        if source not in Config.VIDEO_LIBRARY:
            raise VideoManagerError(f"Unknown video source: {source}")

        video_info = Config.VIDEO_LIBRARY[source]
        logger.info(f"Starting video: {source}")

        # Build appropriate command
        if video_info["type"] == "generated":
            cmd = self._build_test_pattern_command()
            logger.debug("Using test pattern")

        elif video_info["type"] == "download":
            video_file = Config.VIDEO_DIR / video_info["file"]

            # Download if needed
            if not video_file.exists():
                logger.info(f"Video file not found, downloading...")
                try:
                    self.downloader.download(video_info["url"], video_file)
                except VideoManagerError as e:
                    logger.warning(f"Download failed: {e}")
                    logger.info("Falling back to test pattern")
                    cmd = self._build_fallback_command()
                else:
                    cmd = self._build_video_file_command(video_file)
            else:
                cmd = self._build_video_file_command(video_file)
                logger.debug(f"Using video file: {video_file}")

        else:
            raise VideoManagerError(f"Unknown video type: {video_info['type']}")

        # Start the process
        try:
            success = self.process.start(cmd)

            if success:
                self.current_source = source
                logger.info(f"Video started: {source}")
                return True
            else:
                # Try fallback
                logger.warning("Video failed, trying fallback")
                fallback_cmd = self._build_fallback_command()
                success = self.process.start(fallback_cmd)

                if success:
                    self.current_source = "Fallback (Blue Screen)"
                    logger.info("Fallback video started")
                    return True
                else:
                    raise VideoManagerError("Both primary and fallback video failed")

        except Exception as e:
            logger.error(f"Failed to start video: {e}")
            raise VideoManagerError(f"Failed to start video: {e}")

    def stop(self) -> bool:
        """
        Stop video streaming.

        Returns:
            bool: True if stopped successfully
        """
        if not self.is_running:
            logger.debug("Video already stopped")
            return True

        logger.info("Stopping video")
        success = self.process.stop()

        if success:
            self.current_source = None
            logger.info("Video stopped")

        return success

    def restart(self, source: Optional[str] = None) -> bool:
        """
        Restart video streaming.

        Args:
            source: New video source (uses current if None)

        Returns:
            bool: True if restarted successfully
        """
        if source is None:
            source = self.current_source

        if source is None:
            raise VideoManagerError("No source specified for restart")

        logger.info(f"Restarting video with source: {source}")

        self.stop()
        return self.start(source)

    def download_video(
        self,
        source: str,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> bool:
        """
        Download a video without starting playback.

        Args:
            source: Video source name
            progress_callback: Optional progress callback

        Returns:
            bool: True if download successful

        Raises:
            VideoManagerError: If download fails
        """
        if source not in Config.VIDEO_LIBRARY:
            raise VideoManagerError(f"Unknown video source: {source}")

        video_info = Config.VIDEO_LIBRARY[source]

        if video_info["type"] != "download":
            logger.info(f"Source '{source}' doesn't need downloading")
            return True

        video_file = Config.VIDEO_DIR / video_info["file"]

        if video_file.exists():
            logger.info(f"Video already downloaded: {video_file}")
            return True

        return self.downloader.download(
            video_info["url"],
            video_file,
            progress_callback
        )

    def get_status(self) -> dict:
        """
        Get current video status.

        Returns:
            Dictionary with status information
        """
        return {
            "running": self.is_running,
            "source": self.current_source,
            "vm_mode": self.vm_mode,
            "settings": self._get_video_settings(),
            "pid": self.process.get_pid()
        }
