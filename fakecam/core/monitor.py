#!/usr/bin/env python3
"""
System monitoring module for FakeCam.

Provides real-time monitoring of video and audio output devices with
stats collection, analysis, and visualization support.
"""

import subprocess
import time
import re
import logging
from typing import Optional, Dict, Any, List
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime, timedelta

from ..utils.config import Config


logger = logging.getLogger(__name__)


@dataclass
class VideoStats:
    """Video device statistics."""
    resolution: str = "Unknown"
    width: int = 0
    height: int = 0
    pixel_format: str = "Unknown"
    framerate: float = 0.0
    is_streaming: bool = False
    device_exists: bool = False


@dataclass
class AudioStats:
    """Audio device statistics."""
    sample_rate: int = 0
    channels: str = "Unknown"
    format: str = "Unknown"
    volume: float = 0.0
    level: float = 0.0  # Current audio level (0.0-1.0)
    is_streaming: bool = False
    sink_exists: bool = False


@dataclass
class StreamStats:
    """Overall stream statistics."""
    video_uptime: timedelta = timedelta(0)
    audio_uptime: timedelta = timedelta(0)
    estimated_video_bitrate: float = 0.0  # Mbps
    estimated_audio_bitrate: float = 0.0  # Kbps
    video_drops: int = 0
    audio_underruns: int = 0


class VideoMonitor:
    """
    Monitors v4l2 video device statistics.

    Provides real-time monitoring of video output including resolution,
    framerate, format, and streaming status.
    """

    def __init__(self, device_path: str = Config.VIDEO_DEVICE):
        """
        Initialize video monitor.

        Args:
            device_path: Path to v4l2 device
        """
        self.device_path = device_path
        self.start_time: Optional[datetime] = None

    def get_stats(self) -> VideoStats:
        """
        Get current video device statistics.

        Returns:
            VideoStats object with current stats
        """
        stats = VideoStats()

        # Check if device exists
        device = Path(self.device_path)
        stats.device_exists = device.exists()

        if not stats.device_exists:
            return stats

        try:
            # Get device info using v4l2-ctl
            result = subprocess.run(
                ["v4l2-ctl", "-d", self.device_path, "--all"],
                capture_output=True,
                text=True,
                timeout=2
            )

            if result.returncode == 0:
                output = result.stdout
                stats.is_streaming = self._parse_streaming_status(output)
                stats.width, stats.height = self._parse_resolution(output)
                stats.resolution = f"{stats.width}x{stats.height}"
                stats.pixel_format = self._parse_pixel_format(output)
                stats.framerate = self._parse_framerate(output)

        except FileNotFoundError:
            logger.debug("v4l2-ctl not available, using basic detection")
            # Fallback: just check if device exists
            stats.is_streaming = self._check_device_in_use()

        except subprocess.TimeoutExpired:
            logger.warning("v4l2-ctl timed out")

        except Exception as e:
            logger.error(f"Error getting video stats: {e}")

        return stats

    def _parse_streaming_status(self, output: str) -> bool:
        """Parse streaming status from v4l2-ctl output."""
        # Check for "Streaming: on" or similar
        if re.search(r"Stream.*[Oo]n", output):
            return True
        # Also check buffer usage
        if re.search(r"Frames.*[1-9]", output):
            return True
        return False

    def _parse_resolution(self, output: str) -> tuple:
        """Parse resolution from v4l2-ctl output."""
        match = re.search(r"Width/Height\s*:\s*(\d+)/(\d+)", output)
        if match:
            return int(match.group(1)), int(match.group(2))
        return 0, 0

    def _parse_pixel_format(self, output: str) -> str:
        """Parse pixel format from v4l2-ctl output."""
        match = re.search(r"Pixel Format\s*:\s*'(\w+)'", output)
        if match:
            return match.group(1)
        return "Unknown"

    def _parse_framerate(self, output: str) -> float:
        """Parse framerate from v4l2-ctl output."""
        match = re.search(r"(\d+\.?\d*)\s*fps", output)
        if match:
            return float(match.group(1))

        # Alternative format
        match = re.search(r"Frames per second:\s*(\d+\.?\d*)", output)
        if match:
            return float(match.group(1))

        return 0.0

    def _check_device_in_use(self) -> bool:
        """Check if device is in use by checking for processes."""
        try:
            result = subprocess.run(
                ["lsof", self.device_path],
                capture_output=True,
                timeout=1
            )
            return result.returncode == 0
        except:
            return False

    def start_tracking(self):
        """Start tracking uptime."""
        self.start_time = datetime.now()

    def get_uptime(self) -> timedelta:
        """Get streaming uptime."""
        if self.start_time:
            return datetime.now() - self.start_time
        return timedelta(0)


class AudioMonitor:
    """
    Monitors PulseAudio sink statistics.

    Provides real-time monitoring of audio output including sample rate,
    channels, volume, and audio levels.
    """

    def __init__(self, sink_name: str = Config.AUDIO_SINK_NAME):
        """
        Initialize audio monitor.

        Args:
            sink_name: PulseAudio sink name
        """
        self.sink_name = sink_name
        self.start_time: Optional[datetime] = None
        self.peak_history: List[float] = []
        self.max_history_size = 10

    def get_stats(self) -> AudioStats:
        """
        Get current audio device statistics.

        Returns:
            AudioStats object with current stats
        """
        stats = AudioStats()

        try:
            # Get sink info
            result = subprocess.run(
                ["pactl", "list", "sinks"],
                capture_output=True,
                text=True,
                timeout=2
            )

            if result.returncode == 0:
                output = result.stdout
                sink_info = self._find_sink_info(output)

                if sink_info:
                    stats.sink_exists = True
                    stats.sample_rate = self._parse_sample_rate(sink_info)
                    stats.channels = self._parse_channels(sink_info)
                    stats.format = self._parse_format(sink_info)
                    stats.volume = self._parse_volume(sink_info)
                    stats.is_streaming = self._parse_streaming_status(sink_info)

                    # Get current audio level
                    stats.level = self.get_audio_level()

        except FileNotFoundError:
            logger.warning("pactl not available")

        except subprocess.TimeoutExpired:
            logger.warning("pactl timed out")

        except Exception as e:
            logger.error(f"Error getting audio stats: {e}")

        return stats

    def _find_sink_info(self, output: str) -> Optional[str]:
        """Extract sink info section for our sink."""
        # Find section for our sink
        pattern = rf"Sink #\d+.*?Name: {self.sink_name}.*?(?=Sink #|\Z)"
        match = re.search(pattern, output, re.DOTALL)
        if match:
            return match.group(0)
        return None

    def _parse_sample_rate(self, sink_info: str) -> int:
        """Parse sample rate from sink info."""
        match = re.search(r"Sample Specification:.*?(\d+)Hz", sink_info, re.DOTALL)
        if match:
            return int(match.group(1))
        return 0

    def _parse_channels(self, sink_info: str) -> str:
        """Parse channel configuration from sink info."""
        match = re.search(r"Sample Specification:.*?(\d+)ch", sink_info, re.DOTALL)
        if match:
            channels = int(match.group(1))
            return "Stereo" if channels == 2 else f"{channels}ch"
        return "Unknown"

    def _parse_format(self, sink_info: str) -> str:
        """Parse audio format from sink info."""
        match = re.search(r"Sample Specification: ([\w\d]+)", sink_info)
        if match:
            return match.group(1)
        return "Unknown"

    def _parse_volume(self, sink_info: str) -> float:
        """Parse volume level from sink info."""
        match = re.search(r"Volume:.*?(\d+)%", sink_info)
        if match:
            return float(match.group(1)) / 100.0
        return 0.0

    def _parse_streaming_status(self, sink_info: str) -> bool:
        """Parse streaming status from sink info."""
        # Check if sink state is RUNNING
        if re.search(r"State: RUNNING", sink_info):
            return True
        return False

    def get_audio_level(self) -> float:
        """
        Get current audio level (peak).

        Returns:
            Audio level from 0.0 to 1.0
        """
        try:
            # Use pactl to get monitor source info
            monitor_source = f"{self.sink_name}.monitor"

            result = subprocess.run(
                ["pactl", "list", "sources"],
                capture_output=True,
                text=True,
                timeout=1
            )

            if result.returncode == 0:
                # Find our monitor source section
                pattern = rf"Source #\d+.*?Name: {monitor_source}.*?(?=Source #|\Z)"
                match = re.search(pattern, result.stdout, re.DOTALL)

                if match:
                    source_info = match.group(0)
                    # Look for volume/level indicators
                    # PulseAudio shows volume as percentage
                    vol_match = re.search(r"Volume:.*?(\d+)%", source_info)
                    if vol_match:
                        level = float(vol_match.group(1)) / 100.0
                        self.peak_history.append(level)
                        if len(self.peak_history) > self.max_history_size:
                            self.peak_history.pop(0)
                        return level

            # Return average from history if available
            if self.peak_history:
                return sum(self.peak_history) / len(self.peak_history)

        except Exception as e:
            logger.debug(f"Error getting audio level: {e}")

        return 0.0

    def start_tracking(self):
        """Start tracking uptime."""
        self.start_time = datetime.now()

    def get_uptime(self) -> timedelta:
        """Get streaming uptime."""
        if self.start_time:
            return datetime.now() - self.start_time
        return timedelta(0)


class SystemMonitor:
    """
    Unified system monitor for video and audio.

    Provides comprehensive monitoring of both video and audio streams
    with combined statistics and analysis.
    """

    def __init__(self):
        """Initialize system monitor."""
        self.video_monitor = VideoMonitor()
        self.audio_monitor = AudioMonitor()

    def get_all_stats(self) -> Dict[str, Any]:
        """
        Get all monitoring statistics.

        Returns:
            Dictionary with video, audio, and stream stats
        """
        video_stats = self.video_monitor.get_stats()
        audio_stats = self.audio_monitor.get_stats()

        # Calculate stream stats
        stream_stats = StreamStats()
        stream_stats.video_uptime = self.video_monitor.get_uptime()
        stream_stats.audio_uptime = self.audio_monitor.get_uptime()

        # Estimate bitrates
        if video_stats.is_streaming:
            stream_stats.estimated_video_bitrate = self._estimate_video_bitrate(
                video_stats.width, video_stats.height, video_stats.framerate
            )

        if audio_stats.is_streaming:
            stream_stats.estimated_audio_bitrate = self._estimate_audio_bitrate(
                audio_stats.sample_rate, audio_stats.channels
            )

        return {
            "video": video_stats,
            "audio": audio_stats,
            "stream": stream_stats
        }

    def _estimate_video_bitrate(self, width: int, height: int, fps: float) -> float:
        """
        Estimate video bitrate in Mbps.

        Args:
            width: Video width
            height: Video height
            fps: Frames per second

        Returns:
            Estimated bitrate in Mbps
        """
        if width == 0 or height == 0 or fps == 0:
            return 0.0

        # Raw bitrate for YUYV422 is: width * height * 2 bytes * fps
        # Convert to Mbps
        raw_bitrate = (width * height * 2 * fps * 8) / 1_000_000
        return round(raw_bitrate, 2)

    def _estimate_audio_bitrate(self, sample_rate: int, channels: str) -> float:
        """
        Estimate audio bitrate in Kbps.

        Args:
            sample_rate: Sample rate in Hz
            channels: Channel configuration

        Returns:
            Estimated bitrate in Kbps
        """
        if sample_rate == 0:
            return 0.0

        # Assume 16-bit samples
        num_channels = 2 if "Stereo" in channels or "2ch" in channels else 1

        # Bitrate = sample_rate * bit_depth * channels
        bitrate = (sample_rate * 16 * num_channels) / 1000
        return round(bitrate, 1)

    def start_monitoring(self):
        """Start monitoring both streams."""
        self.video_monitor.start_tracking()
        self.audio_monitor.start_tracking()
