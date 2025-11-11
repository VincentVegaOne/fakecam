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

        # State
        self.devices_setup = False

        # Build UI
        self._build_ui()

        # Apply preferences
        self._apply_preferences()

        # Set up logging handler
        self._setup_logging()

        # Welcome message
        self.log("Welcome to FakeCam v{Config.APP_VERSION}!")
        self.log("Click 'SETUP DEVICES' to begin")

        # Check if running in VM
        if Config.detect_vm():
            self.log("⚙ VM detected - VM optimization recommended")

    def _build_ui(self):
        """Build the user interface."""
        # Main container with padding
        main = tk.Frame(self.root, padx=15, pady=10)
        main.pack(fill=tk.BOTH, expand=True)

        # Header
        self._build_header(main)

        # Setup button
        self._build_setup_section(main)

        # Video section
        self._build_video_section(main)

        # Audio section
        self._build_audio_section(main)

        # Quick actions
        self._build_quick_actions(main)

        # Log area
        self._build_log_section(main)

        # Status bar
        self._build_status_bar()

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

    def _setup_devices_thread(self):
        """Setup devices in background thread."""
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
                        self.setup_btn.config(bg="#28a745", text="✓ DEVICES READY"),
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
                        self.setup_btn.config(state="normal", text="⚙ SETUP DEVICES (Try Again)")
                    ])

            except Exception as e:
                self.root.after(0, lambda: [
                    self.log(f"✗ Setup error: {e}"),
                    messagebox.showerror("Setup Error", str(e)),
                    self.setup_btn.config(state="normal", text="⚙ SETUP DEVICES (Try Again)")
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

        except VideoManagerError as e:
            self.log(f"✗ Video error: {e}")
            messagebox.showerror("Video Error", str(e))
            self.video_btn.config(state="normal")

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

        except Exception as e:
            self.log(f"✗ Error stopping video: {e}")
            self.video_btn.config(state="normal")

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

        except AudioManagerError as e:
            self.log(f"✗ Audio error: {e}")
            messagebox.showerror("Audio Error", str(e))
            self.audio_btn.config(state="normal")

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

        except Exception as e:
            self.log(f"✗ Error stopping audio: {e}")
            self.audio_btn.config(state="normal")

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

    def cleanup(self):
        """Cleanup on exit."""
        self.log("Cleaning up...")

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
