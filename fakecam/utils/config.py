#!/usr/bin/env python3
"""
Configuration module for FakeCam.
Contains all constants and configuration settings.
"""

from pathlib import Path
from enum import Enum


class ProcessState(Enum):
    """Process state enumeration."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


class Config:
    """Main configuration class with all settings."""

    # Application info
    APP_NAME = "FakeCam"
    APP_VERSION = "2.0.0"
    APP_DESCRIPTION = "Virtual Camera & Microphone for Testing"

    # Device settings
    VIDEO_DEVICE = "/dev/video10"
    VIDEO_DEVICE_NUMBER = 10
    AUDIO_SINK_NAME = "fakemic"
    AUDIO_SINK_DESCRIPTION = "FakeMicrophone"

    # Video settings - Normal mode
    DEFAULT_WIDTH = 640
    DEFAULT_HEIGHT = 480
    DEFAULT_FRAMERATE = 30
    DEFAULT_PIXEL_FORMAT = "yuyv422"

    # Video settings - VM Optimization mode
    VM_WIDTH = 360
    VM_HEIGHT = 240
    VM_FRAMERATE = 15

    # Audio settings
    DEFAULT_VOLUME = 2.5
    TONE_FREQUENCY = 440  # Hz
    TONE_DURATION = 5  # seconds
    TONE_AMPLITUDE = 0.8

    # TTS settings
    ESPEAK_SPEED = 160  # Words per minute
    ESPEAK_PITCH = 50  # Pitch value (0-99)
    ESPEAK_AMPLITUDE = 200  # Amplitude (max volume)

    # Timing constants (in seconds)
    PROCESS_START_DELAY = 2.0  # Wait for process to fully start
    PROCESS_STOP_TIMEOUT = 2.0  # Timeout for graceful termination
    CLEANUP_DELAY = 0.5  # Delay between cleanup operations
    MODULE_RELOAD_DELAY = 0.5  # Delay before reloading v4l2loopback
    DEVICE_INIT_DELAY = 1.0  # Delay after device initialization

    # Retry settings
    MAX_CLEANUP_RETRIES = 3
    MAX_MODULE_LOAD_RETRIES = 3

    # File paths
    HOME_DIR = Path.home()
    VIDEO_DIR = HOME_DIR / "fakecam_videos"
    AUDIO_DIR = HOME_DIR / "fakecam_audio"
    PREFS_FILE = HOME_DIR / ".fakecam_prefs.json"

    # v4l2loopback module parameters
    V4L2_MODULE_PARAMS = {
        "devices": "1",
        "video_nr": str(VIDEO_DEVICE_NUMBER),
        "card_label": "FakeCam",
        "exclusive_caps": "1",
        "max_buffers": "2"
    }

    # ffmpeg optimization flags
    FFMPEG_VM_FLAGS = ["-preset", "ultrafast", "-bufsize", "1M"]

    # Video library
    VIDEO_LIBRARY = {
        "Test Pattern": {
            "type": "generated",
            "description": "Color test pattern"
        },
        "🏄 Surfing HD": {
            "type": "download",
            "file": "surfing.mp4",
            "url": "https://filesamples.com/samples/video/mp4/sample_1280x720_surfing_with_audio.mp4",
            "size": "~10 MB",
            "description": "HD surfing footage"
        },
        "🌊 Ocean Waves": {
            "type": "download",
            "file": "ocean.mp4",
            "url": "https://filesamples.com/samples/video/mp4/sample_960x540_ocean_with_audio.mp4",
            "size": "~5 MB",
            "description": "Ocean wave scenes"
        }
    }

    # Audio content library
    AUDIO_LIBRARY = {
        "🎤 Meeting Voice": {
            "file": "meeting_voice.wav",
            "text": "Hello everyone... Thanks for joining the meeting today. Um, let me just share my screen here... Can everyone see this clearly? ... Great! So, let's begin with our agenda. First up, we need to discuss the project timeline. Uh, the development is going really well actually. We're definitely on track for the deadline. Any questions so far? ... No? Excellent. Let's move on to the next topic then.",
            "description": "Natural meeting conversation"
        },
        "💼 Professional Talk": {
            "file": "professional.wav",
            "text": "Good morning everyone. I'll be presenting our quarterly results today. So, as you can see on this slide here, our performance has really exceeded expectations. Revenue is up by, uh, fifteen percent, which is fantastic. Customer satisfaction scores have improved significantly as well. Now, let's look at the detailed breakdown... These numbers really reflect the hard work of the entire team. Really great job everyone.",
            "description": "Professional presentation"
        },
        "☕ Casual Chat": {
            "file": "casual_chat.wav",
            "text": "Hey! How's it going? ... Yeah, yeah, I saw that email too. Oh man, did you catch the game last night? It was pretty amazing, right? ... Oh, by the way, we should probably sync up about next week's presentation. I can share my screen if you want to take a look at the draft... Just let me know what works for you, okay?",
            "description": "Casual conversation"
        },
        "🎯 Quick Update": {
            "file": "quick_update.wav",
            "text": "Hi folks, just a quick update here... So the project is on track. We completed the first milestone yesterday, which is great. Um, no blockers at the moment, everything's running smoothly. I'll have the full report ready by end of day. Thanks everyone!",
            "description": "Brief status update"
        },
        "🔊 Test Audio": {
            "file": "test_audio.wav",
            "text": "Testing, testing, one two three... Can you hear me clearly? Hello? ... This is a microphone test. Audio check... audio check... Is this coming through okay?",
            "description": "Microphone test"
        },
        "🎵 Simple Tone": {
            "file": "tone.wav",
            "type": "tone",
            "description": "440Hz test tone"
        },
        "🔇 Silence": {
            "file": None,
            "type": "silence",
            "description": "No audio output"
        }
    }

    # TTS engine preferences (in order of preference)
    TTS_ENGINE_PRIORITY = [
        "flite",      # Most natural
        "pico2wave",  # Very natural but not always available
        "espeak-ng",  # Better than espeak
        "festival",   # Good but slower
        "espeak"      # Fallback
    ]

    # TTS voice mappings for espeak-ng
    ESPEAK_VOICE_MAP = {
        "Meeting Voice": "en+f3",      # Female voice 3
        "Professional Talk": "en+m3",  # Male voice 3
        "Casual Chat": "en+m7",        # Male voice 7
        "Quick Update": "en+f2",       # Female voice 2
        "Test Audio": "en+m4"          # Male voice 4
    }

    @classmethod
    def ensure_directories(cls):
        """Ensure all required directories exist."""
        cls.VIDEO_DIR.mkdir(exist_ok=True)
        cls.AUDIO_DIR.mkdir(exist_ok=True)

    @classmethod
    def get_video_settings(cls, vm_mode=False):
        """
        Get video settings based on mode.

        Args:
            vm_mode: Whether VM optimization is enabled

        Returns:
            dict: Video settings (width, height, framerate)
        """
        if vm_mode:
            return {
                "width": cls.VM_WIDTH,
                "height": cls.VM_HEIGHT,
                "framerate": cls.VM_FRAMERATE
            }
        return {
            "width": cls.DEFAULT_WIDTH,
            "height": cls.DEFAULT_HEIGHT,
            "framerate": cls.DEFAULT_FRAMERATE
        }

    @classmethod
    def detect_vm(cls):
        """
        Detect if running in a virtual machine.

        Returns:
            bool: True if running in VM
        """
        import subprocess

        # Check common VM indicators
        vm_indicators = [
            ("systemd-detect-virt", []),
            ("dmidecode", ["-s", "system-product-name"]),
        ]

        for cmd, args in vm_indicators:
            try:
                result = subprocess.run(
                    [cmd] + args,
                    capture_output=True,
                    text=True,
                    timeout=1
                )
                output = result.stdout.lower()
                if any(vm in output for vm in ["qemu", "kvm", "virtualbox", "vmware", "xen"]):
                    return True
            except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError):
                continue

        return False
