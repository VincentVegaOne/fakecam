#!/usr/bin/env python3
"""
Main GUI window for FakeCam.

Provides an intuitive interface for controlling virtual camera and microphone
with proper status indicators, progress tracking, and error handling.
"""

import sys
import logging
import threading
import time
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import ttk, scrolledtext, messagebox
except ImportError:
    print("Error: tkinter not installed")
    print("Run: sudo apt-get install python3-tk")
    sys.exit(1)

from ..core.device_setup import DeviceManager, DeviceSetupError
from ..core.video_manager import VideoManager, VideoManagerError
from ..core.audio_manager import AudioManager, AudioManagerError
from ..core.monitor import SystemMonitor
from ..utils.config import Config
from ..utils.preferences import Preferences
from ..utils.process_manager import get_registry


logger = logging.getLogger(__name__)


class ProgressDialog:
    """
    Modal progress dialog for long-running operations.

    Provides user feedback during downloads, generation, etc.
    """

    def __init__(self, parent, title: str, message: str):
        """
        Initialize progress dialog.

        Args:
            parent: Parent window
            title: Dialog title
            message: Initial message
        """
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("400x150")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # Center on parent
        self.dialog.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.dialog.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")

        # Message label
        self.label = tk.Label(
            self.dialog,
            text=message,
            font=("Arial", 10),
            wraplength=350
        )
        self.label.pack(pady=20)

        # Progress bar
        self.progress = ttk.Progressbar(
            self.dialog,
            mode='indeterminate',
            length=350
        )
        self.progress.pack(pady=10)
        self.progress.start()

        # Status label
        self.status_label = tk.Label(
            self.dialog,
            text="",
            font=("Arial", 9),
            fg="gray"
        )
        self.status_label.pack()

    def update_message(self, message: str):
        """Update the main message."""
        self.label.config(text=message)
        self.dialog.update()

    def update_status(self, status: str):
        """Update the status label."""
        self.status_label.config(text=status)
        self.dialog.update()

    def close(self):
        """Close the dialog."""
        self.progress.stop()
        self.dialog.grab_release()
        self.dialog.destroy()


class StatusIndicator(tk.Canvas):
    """
    LED-style status indicator widget.

    Shows green/red/gray status with optional label.
    """

    def __init__(self, parent, label: str = "", **kwargs):
        """
        Initialize status indicator.

        Args:
            parent: Parent widget
            label: Optional label text
        """
        super().__init__(parent, width=20, height=20, highlightthickness=0, **kwargs)
        self.label = label

        # Draw circle
        self.circle = self.create_oval(4, 4, 16, 16, fill="gray", outline="darkgray")

    def set_status(self, status: str):
        """
        Set indicator status.

        Args:
            status: 'running' (green), 'stopped' (gray), 'error' (red)
        """
        colors = {
            'running': ('green', 'darkgreen'),
            'stopped': ('gray', 'darkgray'),
            'error': ('red', 'darkred')
        }
        fill, outline = colors.get(status, ('gray', 'darkgray'))
        self.itemconfig(self.circle, fill=fill, outline=outline)


class FakeCamGUI:
    """
    Main FakeCam GUI application.

    Provides comprehensive interface for controlling virtual camera and microphone
    with proper error handling, progress tracking, and user preferences.
    """

    def __init__(self, root):
        """
        Initialize GUI.

        Args:
            root: Tkinter root window
        """
        self.root = root
        self.root.title(f"{Config.APP_NAME} v{Config.APP_VERSION}")

        # Load preferences
        self.preferences = Preferences()
        geometry = self.preferences.get("window_geometry", "550x850")
        self.root.geometry(geometry)

        # Initialize managers
        self.device_manager = DeviceManager()
        self.video_manager = VideoManager()
        self.audio_manager = AudioManager()
        self.system_monitor = SystemMonitor()

        # State
        self.devices_setup = False
        self.monitoring_active = False
        self.monitor_update_interval = 1000  # ms

        # Build UI
        self._build_ui()

        # Apply preferences
        self._apply_preferences()

        # Set up logging handler
        self._setup_logging()

        # Welcome message
        self.log(f"Welcome to FakeCam v{Config.APP_VERSION}!")
        self.log("Setting up devices...")

        # Check if running in VM
        if Config.detect_vm():
            self.log("⚙ VM detected - VM optimization recommended")

        # Auto-setup devices on startup
        self.root.after(500, self._auto_setup_devices)

    def _build_ui(self):
        """Build the user interface."""
        # Main container with padding
        main = tk.Frame(self.root, padx=15, pady=10)
        main.pack(fill=tk.BOTH, expand=True)

        # Header
        self._build_header(main)

        # Setup button
        self._build_setup_section(main)

        # Create notebook (tabs)
        self.notebook = ttk.Notebook(main)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=10)

        # Tab 1: Controls
        controls_frame = tk.Frame(self.notebook)
        self.notebook.add(controls_frame, text="Controls")

        # Tab 2: Monitor
        monitor_frame = tk.Frame(self.notebook)
        self.notebook.add(monitor_frame, text="Monitor")

        # Build controls tab content
        self._build_controls_tab(controls_frame)

        # Build monitor tab content
        self._build_monitor_tab(monitor_frame)

        # Log area (shared, below tabs)
        self._build_log_section(main)

        # Status bar
        self._build_status_bar()

    def _build_controls_tab(self, parent):
        """Build the controls tab content."""
        # Video section
        self._build_video_section(parent)

        # Audio section
        self._build_audio_section(parent)

        # Quick actions
        self._build_quick_actions(parent)

    def _build_header(self, parent):
        """Build header section."""
        header_frame = tk.Frame(parent)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        tk.Label(
            header_frame,
            text=Config.APP_NAME,
            font=("Arial", 18, "bold")
        ).pack()

        tk.Label(
            header_frame,
            text=Config.APP_DESCRIPTION,
            font=("Arial", 10)
        ).pack()

        tk.Label(
            header_frame,
            text=f"v{Config.APP_VERSION}",
            font=("Arial", 8),
            fg="gray"
        ).pack()

    def _build_setup_section(self, parent):
        """Build device setup section."""
        setup_frame = tk.Frame(parent)
        setup_frame.pack(fill=tk.X, pady=5)

        self.setup_btn = tk.Button(
            setup_frame,
            text="⚙ SETUP DEVICES (Run First!)",
            command=self._setup_devices_thread,
            bg="#FF8C00",
            fg="white",
            font=("Arial", 11, "bold"),
            height=2
        )
        self.setup_btn.pack(fill=tk.X)

    def _build_video_section(self, parent):
        """Build video control section."""
        video_frame = tk.LabelFrame(
            parent,
            text="VIDEO",
            font=("Arial", 11, "bold"),
            padx=10,
            pady=10
        )
        video_frame.pack(fill=tk.X, pady=10)

        # Video selection
        selection_frame = tk.Frame(video_frame)
        selection_frame.pack(fill=tk.X, pady=5)

        tk.Label(
            selection_frame,
            text="Select video:",
            font=("Arial", 10)
        ).pack(side=tk.LEFT, padx=(0, 10))

        self.video_var = tk.StringVar(value="Test Pattern")
        self.video_combo = ttk.Combobox(
            selection_frame,
            textvariable=self.video_var,
            values=list(Config.VIDEO_LIBRARY.keys()),
            state="readonly",
            width=25
        )
        self.video_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # VM optimization checkbox
        self.vm_var = tk.BooleanVar(value=Config.detect_vm())
        self.vm_check = tk.Checkbutton(
            video_frame,
            text="🔋 VM Optimization Mode (lower resolution, better performance)",
            variable=self.vm_var,
            command=self._on_vm_mode_changed,
            font=("Arial", 9)
        )
        self.vm_check.pack(fill=tk.X, pady=5)

        # Buttons
        button_frame = tk.Frame(video_frame)
        button_frame.pack(fill=tk.X, pady=5)

        self.video_download_btn = tk.Button(
            button_frame,
            text="📥 Download",
            command=self._download_video_thread,
            bg="#8B008B",
            fg="white",
            width=12
        )
        self.video_download_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.video_btn = tk.Button(
            button_frame,
            text="▶ START VIDEO",
            command=self._toggle_video,
            bg="#28a745",
            fg="white",
            font=("Arial", 10, "bold")
        )
        self.video_btn.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Status indicator
        status_frame = tk.Frame(video_frame)
        status_frame.pack(fill=tk.X, pady=5)

        tk.Label(status_frame, text="Status:", font=("Arial", 9)).pack(side=tk.LEFT)
        self.video_status = StatusIndicator(status_frame)
        self.video_status.pack(side=tk.LEFT, padx=5)
        self.video_status_label = tk.Label(
            status_frame,
            text="Stopped",
            font=("Arial", 9),
            fg="gray"
        )
        self.video_status_label.pack(side=tk.LEFT)

    def _build_audio_section(self, parent):
        """Build audio control section."""
        audio_frame = tk.LabelFrame(
            parent,
            text="AUDIO",
            font=("Arial", 11, "bold"),
            padx=10,
            pady=10
        )
        audio_frame.pack(fill=tk.X, pady=10)

        # Audio selection
        selection_frame = tk.Frame(audio_frame)
        selection_frame.pack(fill=tk.X, pady=5)

        tk.Label(
            selection_frame,
            text="Select audio:",
            font=("Arial", 10)
        ).pack(side=tk.LEFT, padx=(0, 10))

        self.audio_var = tk.StringVar(value="🎤 Meeting Voice")
        self.audio_combo = ttk.Combobox(
            selection_frame,
            textvariable=self.audio_var,
            values=list(Config.AUDIO_LIBRARY.keys()),
            state="readonly",
            width=25
        )
        self.audio_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Buttons
        button_frame = tk.Frame(audio_frame)
        button_frame.pack(fill=tk.X, pady=5)

        self.audio_generate_btn = tk.Button(
            button_frame,
            text="🔄 Generate",
            command=self._generate_audio_thread,
            bg="#8B008B",
            fg="white",
            width=12
        )
        self.audio_generate_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.audio_btn = tk.Button(
            button_frame,
            text="▶ START AUDIO",
            command=self._toggle_audio,
            bg="#28a745",
            fg="white",
            font=("Arial", 10, "bold")
        )
        self.audio_btn.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Status indicator
        status_frame = tk.Frame(audio_frame)
        status_frame.pack(fill=tk.X, pady=5)

        tk.Label(status_frame, text="Status:", font=("Arial", 9)).pack(side=tk.LEFT)
        self.audio_status = StatusIndicator(status_frame)
        self.audio_status.pack(side=tk.LEFT, padx=5)
        self.audio_status_label = tk.Label(
            status_frame,
            text="Stopped",
            font=("Arial", 9),
            fg="gray"
        )
        self.audio_status_label.pack(side=tk.LEFT)

        # Instruction label
        tk.Label(
            audio_frame,
            text="→ In your app, select 'Monitor of FakeMicrophone' as microphone",
            font=("Arial", 8),
            fg="blue"
        ).pack(fill=tk.X, pady=(5, 0))

    def _build_quick_actions(self, parent):
        """Build quick actions section."""
        actions_frame = tk.Frame(parent)
        actions_frame.pack(fill=tk.X, pady=10)

        self.start_both_btn = tk.Button(
            actions_frame,
            text="🚀 START BOTH",
            command=self._start_both,
            bg="#007bff",
            fg="white",
            font=("Arial", 12, "bold"),
            height=2
        )
        self.start_both_btn.pack(fill=tk.X)

    def _build_log_section(self, parent):
        """Build log display section."""
        log_frame = tk.LabelFrame(
            parent,
            text="LOG",
            font=("Arial", 10),
            padx=5,
            pady=5
        )
        log_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            height=18,
            wrap=tk.WORD,
            font=("Courier", 9)
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def _build_status_bar(self):
        """Build status bar at bottom."""
        self.status_bar = tk.Label(
            self.root,
            text="Ready",
            relief=tk.SUNKEN,
            anchor=tk.W,
            font=("Arial", 8)
        )
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def _build_monitor_tab(self, parent):
        """Build the monitor tab content."""
        # Main container
        monitor_container = tk.Frame(parent, padx=10, pady=10)
        monitor_container.pack(fill=tk.BOTH, expand=True)

        # Monitor control
        control_frame = tk.Frame(monitor_container)
        control_frame.pack(fill=tk.X, pady=(0, 10))

        self.monitor_toggle_btn = tk.Button(
            control_frame,
            text="▶ START MONITORING",
            command=self._toggle_monitoring,
            bg="#28a745",
            fg="white",
            font=("Arial", 10, "bold")
        )
        self.monitor_toggle_btn.pack(side=tk.LEFT, padx=5)

        tk.Label(
            control_frame,
            text="Updates every 1 second",
            font=("Arial", 9),
            fg="gray"
        ).pack(side=tk.LEFT, padx=10)

        # Create two columns
        left_column = tk.Frame(monitor_container)
        left_column.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        right_column = tk.Frame(monitor_container)
        right_column.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))

        # === LEFT COLUMN: Video Stats ===
        video_frame = tk.LabelFrame(
            left_column,
            text="📹 VIDEO OUTPUT",
            font=("Arial", 11, "bold"),
            padx=10,
            pady=10
        )
        video_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Video stats labels
        self.monitor_video_resolution = self._create_stat_label(video_frame, "Resolution:")
        self.monitor_video_framerate = self._create_stat_label(video_frame, "Framerate:")
        self.monitor_video_format = self._create_stat_label(video_frame, "Format:")
        self.monitor_video_status = self._create_stat_label(video_frame, "Status:")

        # === LEFT COLUMN: Stream Stats ===
        stream_frame = tk.LabelFrame(
            left_column,
            text="📊 STREAM STATS",
            font=("Arial", 11, "bold"),
            padx=10,
            pady=10
        )
        stream_frame.pack(fill=tk.BOTH, expand=True)

        self.monitor_video_bitrate = self._create_stat_label(stream_frame, "Video Bitrate:")
        self.monitor_audio_bitrate = self._create_stat_label(stream_frame, "Audio Bitrate:")
        self.monitor_video_uptime = self._create_stat_label(stream_frame, "Video Uptime:")
        self.monitor_audio_uptime = self._create_stat_label(stream_frame, "Audio Uptime:")

        # === RIGHT COLUMN: Audio Stats ===
        audio_frame = tk.LabelFrame(
            right_column,
            text="🎤 AUDIO OUTPUT",
            font=("Arial", 11, "bold"),
            padx=10,
            pady=10
        )
        audio_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Audio stats labels
        self.monitor_audio_rate = self._create_stat_label(audio_frame, "Sample Rate:")
        self.monitor_audio_channels = self._create_stat_label(audio_frame, "Channels:")
        self.monitor_audio_format = self._create_stat_label(audio_frame, "Format:")
        self.monitor_audio_status = self._create_stat_label(audio_frame, "Status:")

        # Audio level meter
        tk.Label(
            audio_frame,
            text="Audio Level:",
            font=("Arial", 10, "bold")
        ).pack(anchor=tk.W, pady=(10, 5))

        # Create audio level meter canvas
        meter_frame = tk.Frame(audio_frame)
        meter_frame.pack(fill=tk.X, pady=5)

        self.audio_meter_canvas = tk.Canvas(
            meter_frame,
            height=30,
            bg="black",
            highlightthickness=1,
            highlightbackground="gray"
        )
        self.audio_meter_canvas.pack(fill=tk.X)

        # Level percentage label
        self.monitor_audio_level_label = tk.Label(
            audio_frame,
            text="0%",
            font=("Arial", 9),
            fg="gray"
        )
        self.monitor_audio_level_label.pack(anchor=tk.E)

        # === RIGHT COLUMN: System Info ===
        system_frame = tk.LabelFrame(
            right_column,
            text="💻 SYSTEM",
            font=("Arial", 11, "bold"),
            padx=10,
            pady=10
        )
        system_frame.pack(fill=tk.BOTH, expand=True)

        self.monitor_device_status = self._create_stat_label(
            system_frame,
            "Device Status:"
        )
        self.monitor_vm_mode = self._create_stat_label(
            system_frame,
            "VM Optimization:"
        )

        # Refresh button
        tk.Button(
            system_frame,
            text="🔄 Refresh Now",
            command=self._update_monitor_display,
            font=("Arial", 9)
        ).pack(pady=(10, 0))

    def _create_stat_label(self, parent, label_text):
        """
        Create a statistics label pair.

        Args:
            parent: Parent widget
            label_text: Label text

        Returns:
            Value label widget
        """
        row = tk.Frame(parent)
        row.pack(fill=tk.X, pady=2)

        tk.Label(
            row,
            text=label_text,
            font=("Arial", 9, "bold"),
            width=15,
            anchor=tk.W
        ).pack(side=tk.LEFT)

        value_label = tk.Label(
            row,
            text="--",
            font=("Arial", 9),
            fg="gray",
            anchor=tk.W
        )
        value_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        return value_label

    def _toggle_monitoring(self):
        """Toggle monitoring on/off."""
        if self.monitoring_active:
            self._stop_monitoring()
        else:
            self._start_monitoring()

    def _start_monitoring(self):
        """Start real-time monitoring."""
        self.monitoring_active = True
        self.system_monitor.start_monitoring()

        self.monitor_toggle_btn.config(
            text="⏹ STOP MONITORING",
            bg="#dc3545"
        )

        self.log("Monitoring started")
        self._schedule_monitor_update()

    def _stop_monitoring(self):
        """Stop real-time monitoring."""
        self.monitoring_active = False

        self.monitor_toggle_btn.config(
            text="▶ START MONITORING",
            bg="#28a745"
        )

        self.log("Monitoring stopped")

    def _schedule_monitor_update(self):
        """Schedule next monitor update."""
        if self.monitoring_active:
            self._update_monitor_display()
            self.root.after(self.monitor_update_interval, self._schedule_monitor_update)

    def _update_monitor_display(self):
        """Update monitor display with current stats."""
        try:
            stats = self.system_monitor.get_all_stats()
            video_stats = stats["video"]
            audio_stats = stats["audio"]
            stream_stats = stats["stream"]

            # Update video stats
            self.monitor_video_resolution.config(
                text=video_stats.resolution,
                fg="green" if video_stats.is_streaming else "gray"
            )
            self.monitor_video_framerate.config(
                text=f"{video_stats.framerate:.1f} fps",
                fg="green" if video_stats.framerate > 0 else "gray"
            )
            self.monitor_video_format.config(
                text=video_stats.pixel_format,
                fg="green" if video_stats.is_streaming else "gray"
            )
            self.monitor_video_status.config(
                text="● Streaming" if video_stats.is_streaming else "○ Idle",
                fg="green" if video_stats.is_streaming else "gray"
            )

            # Update audio stats
            sample_rate_text = f"{audio_stats.sample_rate} Hz" if audio_stats.sample_rate > 0 else "--"
            self.monitor_audio_rate.config(
                text=sample_rate_text,
                fg="green" if audio_stats.sink_exists else "gray"
            )
            self.monitor_audio_channels.config(
                text=audio_stats.channels,
                fg="green" if audio_stats.sink_exists else "gray"
            )
            self.monitor_audio_format.config(
                text=audio_stats.format,
                fg="green" if audio_stats.sink_exists else "gray"
            )
            self.monitor_audio_status.config(
                text="● Streaming" if audio_stats.is_streaming else "○ Idle",
                fg="green" if audio_stats.is_streaming else "gray"
            )

            # Update audio level meter
            self._draw_audio_meter(audio_stats.level)
            self.monitor_audio_level_label.config(
                text=f"{int(audio_stats.level * 100)}%",
                fg="green" if audio_stats.level > 0.1 else "gray"
            )

            # Update stream stats
            self.monitor_video_bitrate.config(
                text=f"{stream_stats.estimated_video_bitrate:.2f} Mbps" if stream_stats.estimated_video_bitrate > 0 else "--",
                fg="green" if stream_stats.estimated_video_bitrate > 0 else "gray"
            )
            self.monitor_audio_bitrate.config(
                text=f"{stream_stats.estimated_audio_bitrate:.1f} Kbps" if stream_stats.estimated_audio_bitrate > 0 else "--",
                fg="green" if stream_stats.estimated_audio_bitrate > 0 else "gray"
            )

            # Format uptime
            video_uptime = self._format_uptime(stream_stats.video_uptime)
            audio_uptime = self._format_uptime(stream_stats.audio_uptime)

            self.monitor_video_uptime.config(
                text=video_uptime,
                fg="green" if video_stats.is_streaming else "gray"
            )
            self.monitor_audio_uptime.config(
                text=audio_uptime,
                fg="green" if audio_stats.is_streaming else "gray"
            )

            # Update system info
            device_ok = video_stats.device_exists and audio_stats.sink_exists
            self.monitor_device_status.config(
                text="✓ Ready" if device_ok else "✗ Not Ready",
                fg="green" if device_ok else "red"
            )
            self.monitor_vm_mode.config(
                text="Enabled" if self.vm_var.get() else "Disabled",
                fg="blue" if self.vm_var.get() else "gray"
            )

        except Exception as e:
            logger.error(f"Error updating monitor display: {e}")

    def _draw_audio_meter(self, level: float):
        """
        Draw audio level meter.

        Args:
            level: Audio level from 0.0 to 1.0
        """
        try:
            canvas = self.audio_meter_canvas
            width = canvas.winfo_width()
            height = canvas.winfo_height()

            if width < 10:  # Not yet rendered
                width = 400
                height = 30

            # Clear canvas
            canvas.delete("all")

            # Draw background grid
            for i in range(0, 11):
                x = (i / 10) * width
                canvas.create_line(
                    x, 0, x, height,
                    fill="#333",
                    width=1
                )

            # Calculate meter width
            meter_width = int(level * width)

            # Determine color based on level
            if level < 0.5:
                color = "#00ff00"  # Green
            elif level < 0.8:
                color = "#ffff00"  # Yellow
            else:
                color = "#ff0000"  # Red

            # Draw meter
            if meter_width > 0:
                canvas.create_rectangle(
                    0, 0, meter_width, height,
                    fill=color,
                    outline=""
                )

            # Draw peak indicator
            if meter_width > 0:
                canvas.create_line(
                    meter_width, 0, meter_width, height,
                    fill="white",
                    width=2
                )

        except Exception as e:
            logger.debug(f"Error drawing audio meter: {e}")

    def _format_uptime(self, uptime) -> str:
        """
        Format uptime timedelta as string.

        Args:
            uptime: timedelta object

        Returns:
            Formatted uptime string
        """
        if uptime.total_seconds() == 0:
            return "--"

        total_seconds = int(uptime.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"

    def _setup_logging(self):
        """Set up logging to GUI."""
        class GUILogHandler(logging.Handler):
            """Custom logging handler that writes to GUI."""

            def __init__(self, gui_callback):
                super().__init__()
                self.gui_callback = gui_callback

            def emit(self, record):
                try:
                    msg = self.format(record)
                    self.gui_callback(msg)
                except Exception:
                    pass

        handler = GUILogHandler(self.log)
        handler.setLevel(logging.INFO)
        handler.setFormatter(
            logging.Formatter('[%(levelname)s] %(message)s')
        )
        logging.getLogger().addHandler(handler)

    def _apply_preferences(self):
        """Apply saved preferences."""
        self.video_var.set(self.preferences.get("video_selection", "Test Pattern"))
        self.audio_var.set(self.preferences.get("audio_selection", "🎤 Meeting Voice"))
        self.vm_var.set(self.preferences.get("vm_mode", Config.detect_vm()))
        self.video_manager.set_vm_mode(self.vm_var.get())

    def _save_preferences(self):
        """Save current preferences."""
        self.preferences.update({
            "video_selection": self.video_var.get(),
            "audio_selection": self.audio_var.get(),
            "vm_mode": self.vm_var.get(),
            "window_geometry": self.root.geometry()
        })
        self.preferences.save()

    def log(self, message: str):
        """
        Add message to log.

        Args:
            message: Message to log
        """
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()

    def set_status(self, message: str):
        """
        Update status bar.

        Args:
            message: Status message
        """
        self.status_bar.config(text=message)
        self.root.update_idletasks()

    def _on_vm_mode_changed(self):
        """Handle VM mode checkbox change."""
        self.video_manager.set_vm_mode(self.vm_var.get())
        mode = "enabled" if self.vm_var.get() else "disabled"
        self.log(f"VM optimization {mode}")

    def _update_start_both_button(self):
        """Update START BOTH button based on current state."""
        video_running = self.video_manager.is_running
        audio_running = self.audio_manager.is_running

        if video_running and audio_running:
            # Both running
            self.start_both_btn.config(
                text="⏹ STOP BOTH",
                bg="#dc3545",
                command=self._stop_both
            )
        elif video_running or audio_running:
            # One running
            self.start_both_btn.config(
                text="⏹ STOP ALL",
                bg="#dc3545",
                command=self._stop_both
            )
        else:
            # Both stopped
            self.start_both_btn.config(
                text="🚀 START BOTH",
                bg="#007bff",
                command=self._start_both
            )

    def _auto_setup_devices(self):
        """Auto-setup devices on startup."""
        def task():
            self.root.after(0, lambda: self.setup_btn.config(state="disabled", text="⏳ Setting up..."))

            try:
                video_ok, audio_ok = self.device_manager.setup_all()

                if video_ok and audio_ok:
                    self.devices_setup = True
                    self.root.after(0, lambda: [
                        self.log("✓ All devices setup successfully!"),
                        self.log(f"  Video device: {Config.VIDEO_DEVICE}"),
                        self.log(f"  Audio sink: Monitor of {Config.AUDIO_SINK_DESCRIPTION}"),
                        self.log("Ready to start! Select sources and click START BOTH"),
                        self.setup_btn.config(bg="#28a745", text="✓ DEVICES READY", state="disabled"),
                        self.set_status("Ready - Devices configured")
                    ])
                else:
                    error_msg = []
                    if not video_ok:
                        error_msg.append("video")
                    if not audio_ok:
                        error_msg.append("audio")

                    self.root.after(0, lambda: [
                        self.log(f"✗ Setup errors: {', '.join(error_msg)} failed"),
                        self.log("  You can retry setup or continue with available devices"),
                        self.setup_btn.config(state="normal", text="⚙ RETRY SETUP", bg="#ffc107")
                    ])

            except Exception as e:
                self.root.after(0, lambda: [
                    self.log(f"✗ Setup error: {e}"),
                    self.log("  Click RETRY SETUP to try again"),
                    self.setup_btn.config(state="normal", text="⚙ RETRY SETUP", bg="#ffc107")
                ])

        thread = threading.Thread(target=task, daemon=True)
        thread.start()

    def _setup_devices_thread(self):
        """Setup devices in background thread (manual retry)."""
        def task():
            self.root.after(0, lambda: self.setup_btn.config(state="disabled", text="⏳ Setting up..."))

            try:
                video_ok, audio_ok = self.device_manager.setup_all()

                if video_ok and audio_ok:
                    self.devices_setup = True
                    self.root.after(0, lambda: [
                        self.log("✓ All devices setup successfully!"),
                        self.log(f"  Video device: {Config.VIDEO_DEVICE}"),
                        self.log(f"  Audio sink: Monitor of {Config.AUDIO_SINK_DESCRIPTION}"),
                        self.setup_btn.config(bg="#28a745", text="✓ DEVICES READY", state="disabled"),
                        self.set_status("Devices ready")
                    ])
                else:
                    error_msg = []
                    if not video_ok:
                        error_msg.append("video setup failed")
                    if not audio_ok:
                        error_msg.append("audio setup failed")

                    self.root.after(0, lambda: [
                        self.log(f"✗ Setup errors: {', '.join(error_msg)}"),
                        self.log("  Check logs above for details"),
                        messagebox.showerror("Setup Error", f"Setup failed: {', '.join(error_msg)}"),
                        self.setup_btn.config(state="normal", text="⚙ RETRY SETUP", bg="#ffc107")
                    ])

            except Exception as e:
                self.root.after(0, lambda: [
                    self.log(f"✗ Setup error: {e}"),
                    messagebox.showerror("Setup Error", str(e)),
                    self.setup_btn.config(state="normal", text="⚙ RETRY SETUP", bg="#ffc107")
                ])

        thread = threading.Thread(target=task, daemon=True)
        thread.start()

    def _toggle_video(self):
        """Toggle video on/off."""
        if self.video_manager.is_running:
            self._stop_video()
        else:
            self._start_video()

    def _start_video(self):
        """Start video streaming."""
        if not self.devices_setup:
            messagebox.showwarning("Not Ready", "Please setup devices first!")
            return

        source = self.video_var.get()

        try:
            self.video_btn.config(state="disabled")
            self.log(f"Starting video: {source}")

            self.video_manager.start(source)

            self.video_btn.config(
                text="⏹ STOP VIDEO",
                bg="#dc3545",
                state="normal"
            )
            self.video_status.set_status('running')
            self.video_status_label.config(text=f"Running: {source}", fg="green")
            self.log("✓ Video started")
            self.set_status(f"Video: {source}")

            # Update START BOTH button
            self._update_start_both_button()

        except VideoManagerError as e:
            self.log(f"✗ Video error: {e}")
            messagebox.showerror("Video Error", str(e))
            self.video_btn.config(state="normal")
            self._update_start_both_button()

    def _stop_video(self):
        """Stop video streaming."""
        try:
            self.video_btn.config(state="disabled")
            self.log("Stopping video...")

            self.video_manager.stop()

            self.video_btn.config(
                text="▶ START VIDEO",
                bg="#28a745",
                state="normal"
            )
            self.video_status.set_status('stopped')
            self.video_status_label.config(text="Stopped", fg="gray")
            self.log("✓ Video stopped")
            self.set_status("Video stopped")

            # Update START BOTH button
            self._update_start_both_button()

        except Exception as e:
            self.log(f"✗ Error stopping video: {e}")
            self.video_btn.config(state="normal")
            self._update_start_both_button()

    def _download_video_thread(self):
        """Download video in background thread."""
        source = self.video_var.get()

        if source == "Test Pattern":
            self.log("Test pattern doesn't need downloading")
            return

        def task():
            progress_dialog = None

            try:
                # Show progress dialog
                self.root.after(0, lambda: self.video_download_btn.config(state="disabled"))

                def show_progress():
                    nonlocal progress_dialog
                    progress_dialog = ProgressDialog(
                        self.root,
                        "Downloading Video",
                        f"Downloading {source}..."
                    )

                self.root.after(0, show_progress)

                # Download
                self.video_manager.download_video(source)

                self.root.after(0, lambda: [
                    progress_dialog.close() if progress_dialog else None,
                    self.log(f"✓ Downloaded: {source}"),
                    self.video_download_btn.config(state="normal")
                ])

            except VideoManagerError as e:
                self.root.after(0, lambda: [
                    progress_dialog.close() if progress_dialog else None,
                    self.log(f"✗ Download failed: {e}"),
                    messagebox.showerror("Download Error", str(e)),
                    self.video_download_btn.config(state="normal")
                ])

        thread = threading.Thread(target=task, daemon=True)
        thread.start()

    def _toggle_audio(self):
        """Toggle audio on/off."""
        if self.audio_manager.is_running:
            self._stop_audio()
        else:
            self._start_audio()

    def _start_audio(self):
        """Start audio streaming."""
        if not self.devices_setup:
            messagebox.showwarning("Not Ready", "Please setup devices first!")
            return

        source = self.audio_var.get()

        try:
            self.audio_btn.config(state="disabled")
            self.log(f"Starting audio: {source}")

            self.audio_manager.start(source)

            self.audio_btn.config(
                text="⏹ STOP AUDIO",
                bg="#dc3545",
                state="normal"
            )
            self.audio_status.set_status('running')
            self.audio_status_label.config(text=f"Running: {source}", fg="green")
            self.log("✓ Audio started")
            self.set_status(f"Audio: {source}")

            # Update START BOTH button
            self._update_start_both_button()

        except AudioManagerError as e:
            self.log(f"✗ Audio error: {e}")
            messagebox.showerror("Audio Error", str(e))
            self.audio_btn.config(state="normal")
            self._update_start_both_button()

    def _stop_audio(self):
        """Stop audio streaming."""
        try:
            self.audio_btn.config(state="disabled")
            self.log("Stopping audio...")

            self.audio_manager.stop()

            self.audio_btn.config(
                text="▶ START AUDIO",
                bg="#28a745",
                state="normal"
            )
            self.audio_status.set_status('stopped')
            self.audio_status_label.config(text="Stopped", fg="gray")
            self.log("✓ Audio stopped")
            self.set_status("Audio stopped")

            # Update START BOTH button
            self._update_start_both_button()

        except Exception as e:
            self.log(f"✗ Error stopping audio: {e}")
            self.audio_btn.config(state="normal")
            self._update_start_both_button()

    def _generate_audio_thread(self):
        """Generate audio in background thread."""
        source = self.audio_var.get()

        def task():
            progress_dialog = None

            try:
                self.root.after(0, lambda: self.audio_generate_btn.config(state="disabled"))

                def show_progress():
                    nonlocal progress_dialog
                    progress_dialog = ProgressDialog(
                        self.root,
                        "Generating Audio",
                        f"Generating {source}..."
                    )

                self.root.after(0, show_progress)

                # Generate with progress callback
                def progress_callback(status):
                    if progress_dialog:
                        self.root.after(0, lambda: progress_dialog.update_status(status))

                self.audio_manager.generate_audio(source, progress_callback)

                self.root.after(0, lambda: [
                    progress_dialog.close() if progress_dialog else None,
                    self.log(f"✓ Generated: {source}"),
                    self.audio_generate_btn.config(state="normal")
                ])

            except AudioManagerError as e:
                self.root.after(0, lambda: [
                    progress_dialog.close() if progress_dialog else None,
                    self.log(f"✗ Generation failed: {e}"),
                    messagebox.showerror("Generation Error", str(e)),
                    self.audio_generate_btn.config(state="normal")
                ])

        thread = threading.Thread(target=task, daemon=True)
        thread.start()

    def _start_both(self):
        """Start both video and audio."""
        if not self.devices_setup:
            messagebox.showwarning("Not Ready", "Please setup devices first!")
            return

        if not self.video_manager.is_running:
            self._start_video()
            time.sleep(0.5)

        if not self.audio_manager.is_running:
            self._start_audio()

        # Update button state
        self._update_start_both_button()

    def _stop_both(self):
        """Stop both video and audio."""
        if self.video_manager.is_running:
            self._stop_video()

        if self.audio_manager.is_running:
            self._stop_audio()

        # Update button state
        self._update_start_both_button()

    def cleanup(self):
        """Cleanup on exit."""
        self.log("Cleaning up...")

        # Stop monitoring
        if self.monitoring_active:
            self._stop_monitoring()

        # Save preferences
        self._save_preferences()

        # Stop streams
        try:
            self.video_manager.stop()
            self.audio_manager.stop()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

        # Stop all processes
        get_registry().stop_all()

        # Teardown devices
        try:
            self.device_manager.teardown_all()
        except Exception as e:
            logger.error(f"Error tearing down devices: {e}")

        self.log("Cleanup complete")

    def on_closing(self):
        """Handle window closing."""
        if messagebox.askokcancel("Quit", "Close FakeCam?"):
            self.cleanup()
            self.root.quit()
            self.root.destroy()
