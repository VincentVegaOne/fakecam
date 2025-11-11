#!/usr/bin/env python3
"""
FakeCam Final - The ONE working version
Simple, reliable virtual webcam and microphone
"""

import os
import sys
import time
import subprocess
import threading
import signal
import atexit
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import ttk, scrolledtext
except ImportError:
    print("Error: tkinter not installed")
    print("Run: sudo apt-get install python3-tk")
    sys.exit(1)

class FakeCam:
    def __init__(self, root):
        self.root = root
        self.root.title("FakeCam - Virtual Devices")
        self.root.geometry("500x650")

        # State
        self.video_proc = None
        self.audio_proc = None

        # Main UI
        main = tk.Frame(root, padx=15, pady=10)
        main.pack(fill=tk.BOTH, expand=True)

        # Title
        tk.Label(main, text="FakeCam", font=("Arial", 16, "bold")).pack()
        tk.Label(main, text="Simple Virtual Camera & Microphone", font=("Arial", 10)).pack(pady=(0,10))

        # Quick Setup Button
        tk.Button(
            main, text="⚙️ SETUP DEVICES (Run First!)",
            command=self.setup_devices,
            bg="orange", fg="white", font=("Arial", 11, "bold")
        ).pack(fill=tk.X, pady=5)

        # Video Section
        video_frame = tk.LabelFrame(main, text="VIDEO", font=("Arial", 11, "bold"))
        video_frame.pack(fill=tk.X, pady=10)

        # Video selection dropdown
        tk.Label(video_frame, text="Select video:").pack(pady=(5,0))

        self.video_var = tk.StringVar(value="Test Pattern")
        self.video_options = [
            "Test Pattern",
            "🏄 Surfing HD",
            "🌊 Ocean Waves"
        ]

        self.video_combo = ttk.Combobox(
            video_frame,
            textvariable=self.video_var,
            values=self.video_options,
            state="readonly",
            width=25
        )
        self.video_combo.pack(pady=5)

        # Download button for videos
        self.download_btn = tk.Button(
            video_frame,
            text="📥 Download Selected",
            command=self.download_video,
            bg="purple", fg="white",
            font=("Arial", 9)
        )
        self.download_btn.pack(pady=2)

        self.video_btn = tk.Button(
            video_frame,
            text="▶ START VIDEO",
            command=self.toggle_video,
            bg="green", fg="white",
            font=("Arial", 10, "bold")
        )
        self.video_btn.pack(pady=5)

        # Audio Section
        audio_frame = tk.LabelFrame(main, text="AUDIO", font=("Arial", 11, "bold"))
        audio_frame.pack(fill=tk.X, pady=10)

        # Audio selection dropdown
        tk.Label(audio_frame, text="Select audio:").pack(pady=(5,0))

        self.audio_var = tk.StringVar(value="🎤 Meeting Voice")
        self.audio_options = [
            "🎤 Meeting Voice",
            "💼 Professional Talk",
            "☕ Casual Chat",
            "🎯 Quick Update",
            "🔊 Test Audio",
            "🎵 Simple Tone",
            "🔇 Silence"
        ]

        self.audio_combo = ttk.Combobox(
            audio_frame,
            textvariable=self.audio_var,
            values=self.audio_options,
            state="readonly",
            width=25
        )
        self.audio_combo.pack(pady=5)

        # Generate button for audio
        self.generate_btn = tk.Button(
            audio_frame,
            text="🔄 Generate Audio",
            command=self.generate_audio,
            bg="purple", fg="white",
            font=("Arial", 9)
        )
        self.generate_btn.pack(pady=2)

        self.audio_btn = tk.Button(
            audio_frame,
            text="▶ START AUDIO",
            command=self.toggle_audio,
            bg="green", fg="white",
            font=("Arial", 10, "bold")
        )
        self.audio_btn.pack(pady=5)

        # Start All Button
        tk.Button(
            main, text="🚀 START BOTH",
            command=self.start_both,
            bg="blue", fg="white", font=("Arial", 12, "bold"),
            height=2
        ).pack(fill=tk.X, pady=10)

        # Log Area
        log_frame = tk.LabelFrame(main, text="LOG", font=("Arial", 10))
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = scrolledtext.ScrolledText(
            log_frame, height=10, wrap=tk.WORD,
            font=("Courier", 9)
        )
        self.log_text.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)

        # Initial message
        self.log("Welcome to FakeCam!")
        self.log("Click SETUP DEVICES first, then START")

        # Initial cleanup on start
        self.initial_cleanup()

    def log(self, msg):
        """Simple logging"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {msg}\n")
        self.log_text.see(tk.END)
        self.root.update()

    def initial_cleanup(self):
        """Initial cleanup when app starts"""
        self.log("Performing initial cleanup...")
        # Kill any leftover ffmpeg processes
        result = subprocess.run(["pgrep", "-f", "ffmpeg"], capture_output=True, text=True)
        if result.stdout:
            self.log("  Found old ffmpeg processes, cleaning...")
            subprocess.run(["pkill", "-f", "ffmpeg"], capture_output=True)
            time.sleep(1)

    def cleanup_old_devices(self):
        """Thorough cleanup of old devices and processes"""
        # Kill all related processes
        processes_to_kill = [
            "ffmpeg.*video10",
            "ffmpeg.*fakemic",
            "ffmpeg.*fakecam",
            "v4l2.*video10"
        ]

        for pattern in processes_to_kill:
            subprocess.run(["pkill", "-f", pattern], capture_output=True)

        # Kill by exact name too
        subprocess.run(["pkill", "ffmpeg"], capture_output=True)

        # Clean up audio sinks
        result = subprocess.run(["pactl", "list", "short", "sinks"],
                              capture_output=True, text=True)
        if "fakemic" in result.stdout or "FakeMicrophone" in result.stdout:
            self.log("  Removing old audio sinks...")
            # Get module IDs for fakemic
            result = subprocess.run(["pactl", "list", "short", "modules"],
                                  capture_output=True, text=True)
            for line in result.stdout.split('\n'):
                if "module-null-sink" in line and ("fakemic" in line or "FakeMicrophone" in line):
                    module_id = line.split()[0]
                    subprocess.run(["pactl", "unload-module", module_id],
                                 capture_output=True)

        # Clean v4l2loopback if loaded
        result = subprocess.run(["lsmod"], capture_output=True, text=True)
        if "v4l2loopback" in result.stdout:
            self.log("  Removing old video module...")
            # First try to unload normally
            subprocess.run(["sudo", "modprobe", "-r", "v4l2loopback"],
                         capture_output=True)

        # Force kill any stubborn processes
        subprocess.run(["sudo", "pkill", "-9", "-f", "ffmpeg"], capture_output=True)

        self.log("  Cleanup complete")

    def setup_devices(self):
        """Setup video and audio devices with thorough cleanup"""
        self.log("Setting up devices...")

        # 1. Complete cleanup of old processes and devices
        self.log("Cleaning up old devices...")
        self.cleanup_old_devices()
        time.sleep(1)

        # 2. Setup video device
        self.log("Setting up video device...")

        # Remove and reload module with multiple attempts
        for attempt in range(3):
            result = subprocess.run(["sudo", "modprobe", "-r", "v4l2loopback"],
                                  capture_output=True, text=True)
            if "in use" not in result.stderr:
                break
            self.log(f"  Retry {attempt + 1}: Module in use, killing processes...")
            subprocess.run(["sudo", "pkill", "-9", "-f", "video10"], capture_output=True)
            time.sleep(1)

        time.sleep(0.5)

        result = subprocess.run([
            "sudo", "modprobe", "v4l2loopback",
            "devices=1",
            "video_nr=10",
            "card_label=FakeCam",
            "exclusive_caps=1",
            "max_buffers=2"
        ], capture_output=True)

        if Path("/dev/video10").exists():
            # Set permissions
            subprocess.run(["sudo", "chmod", "666", "/dev/video10"])

            # CRITICAL: Initialize the device format (if v4l2-ctl is available)
            try:
                subprocess.run([
                    "v4l2-ctl", "-d", "/dev/video10",
                    "--set-fmt-video=width=640,height=480,pixelformat=YUYV"
                ], capture_output=True, check=False)
                self.log("  Device format initialized")
            except FileNotFoundError:
                self.log("  ⚠ v4l2-ctl not found - using default format")
                self.log("  Install with: sudo apt-get install v4l-utils")

            self.log("✓ Video device ready at /dev/video10")
        else:
            self.log("✗ Failed to create video device")
            self.log("Try running as: sudo python3 fakecam_final.py")
            return

        # 3. Setup audio device
        self.log("Setting up audio device...")

        # Clean old sinks
        subprocess.run(["pactl", "unload-module", "module-null-sink"],
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(0.5)

        # Create new sink
        result = subprocess.run([
            "pactl", "load-module", "module-null-sink",
            "sink_name=fakemic",
            "sink_properties=device.description=FakeMicrophone"
        ], capture_output=True, text=True)

        if result.returncode == 0:
            self.log("✓ Audio device ready")
            self.log("  Use 'Monitor of FakeMicrophone' as mic")
        else:
            self.log("✗ Failed to create audio device")

        self.log("Setup complete!")

    def download_video(self):
        """Download selected video"""
        selected = self.video_var.get()

        if selected == "Test Pattern":
            self.log("Test pattern doesn't need download")
            return

        # Video library
        video_files = {
            "🏄 Surfing HD": {
                "file": "surfing.mp4",
                "url": "https://filesamples.com/samples/video/mp4/sample_1280x720_surfing_with_audio.mp4",
                "size": "~10 MB"
            },
            "🌊 Ocean Waves": {
                "file": "ocean.mp4",
                "url": "https://filesamples.com/samples/video/mp4/sample_960x540_ocean_with_audio.mp4",
                "size": "~5 MB"
            }
        }

        video_info = video_files.get(selected)
        if not video_info:
            return

        video_dir = Path.home() / "fakecam_videos"
        video_dir.mkdir(exist_ok=True)
        video_file = video_dir / video_info["file"]

        if video_file.exists():
            self.log(f"✓ {selected} already downloaded")
            return

        self.log(f"Downloading {selected} ({video_info['size']})...")
        self.download_btn.config(text="⏳ Downloading...", state="disabled")

        def download_thread():
            try:
                import urllib.request
                urllib.request.urlretrieve(video_info["url"], video_file)
                self.log(f"✓ Downloaded {video_info['file']}")
            except Exception as e:
                self.log(f"✗ Download failed: {str(e)[:50]}")
            finally:
                self.download_btn.config(text="📥 Download Selected", state="normal")

        thread = threading.Thread(target=download_thread, daemon=True)
        thread.start()

    def toggle_video(self):
        """Toggle video on/off"""
        if self.video_proc and self.video_proc.poll() is None:
            self.stop_video()
        else:
            self.start_video()

    def start_video(self):
        """Start video - with video selection"""
        selected = self.video_var.get()
        self.log(f"Starting video: {selected}...")

        # Clean up any existing video process
        if self.video_proc:
            self.stop_video()
            time.sleep(0.5)

        # Kill any orphaned video processes
        subprocess.run(["pkill", "-f", "ffmpeg.*video10"], capture_output=True)
        time.sleep(0.5)

        # First, ensure device is ready
        if not Path("/dev/video10").exists():
            self.log("✗ Video device not found - click SETUP first")
            return

        # Reinitialize device format (if v4l2-ctl is available)
        try:
            subprocess.run([
                "v4l2-ctl", "-d", "/dev/video10",
                "--set-fmt-video=width=640,height=480,pixelformat=YUYV"
            ], capture_output=True, check=False)
        except FileNotFoundError:
            # v4l2-ctl not installed, but ffmpeg can still work without it
            self.log("ℹ v4l2-ctl not found - using default format")

        # Setup video directory
        video_dir = Path.home() / "fakecam_videos"
        video_dir.mkdir(exist_ok=True)

        # Video library with URLs
        video_files = {
            "Test Pattern": None,  # Generated
            "🏄 Surfing HD": {
                "file": "surfing.mp4",
                "url": "https://filesamples.com/samples/video/mp4/sample_1280x720_surfing_with_audio.mp4"
            },
            "🌊 Ocean Waves": {
                "file": "ocean.mp4",
                "url": "https://filesamples.com/samples/video/mp4/sample_960x540_ocean_with_audio.mp4"
            }
        }

        # Handle video file
        if selected == "Test Pattern":
            # Use test pattern
            cmd = [
                "ffmpeg",
                "-re",
                "-f", "lavfi",
                "-i", "testsrc2=size=640x480:rate=30",
                "-pix_fmt", "yuyv422",
                "-f", "v4l2",
                "-vcodec", "rawvideo",
                "/dev/video10"
            ]
        else:
            # Use video file
            video_info = video_files.get(selected)
            if not video_info:
                self.log("✗ Unknown video selection")
                return

            video_file = video_dir / video_info["file"]

            # Download if needed
            if not video_file.exists():
                self.log(f"Downloading {selected}...")
                try:
                    import urllib.request
                    urllib.request.urlretrieve(video_info["url"], video_file)
                    self.log(f"✓ Downloaded {video_info['file']}")
                except Exception as e:
                    self.log(f"✗ Download failed: {str(e)[:50]}")
                    # Fallback to test pattern
                    self.log("Using test pattern instead...")
                    cmd = [
                        "ffmpeg", "-re", "-f", "lavfi",
                        "-i", "testsrc2=size=640x480:rate=30",
                        "-pix_fmt", "yuyv422", "-f", "v4l2",
                        "-vcodec", "rawvideo", "/dev/video10"
                    ]

            if video_file.exists():
                # Stream the video file
                cmd = [
                    "ffmpeg",
                    "-re",
                    "-stream_loop", "-1",  # Loop forever
                    "-i", str(video_file),
                    "-vf", "scale=640:480",  # Resize to standard
                    "-pix_fmt", "yuyv422",
                    "-f", "v4l2",
                    "-vcodec", "rawvideo",
                    "/dev/video10"
                ]
            else:
                self.log("✗ Video file not found")
                return

        try:
            self.video_proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL
            )

            # Check if it started
            time.sleep(2)
            if self.video_proc.poll() is None:
                self.log("✓ Video started")
                self.video_btn.config(text="⏹ STOP VIDEO", bg="red")
            else:
                self.log("✗ Video failed to start")
                self.video_proc = None

                # Try alternative method
                self.log("Trying alternative video method...")
                cmd = [
                    "ffmpeg",
                    "-re",
                    "-f", "lavfi",
                    "-i", "color=c=blue:s=640x480:r=30",  # Simple blue screen
                    "-pix_fmt", "yuyv422",
                    "-f", "v4l2",
                    "/dev/video10"
                ]

                self.video_proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL
                )

                time.sleep(1)
                if self.video_proc.poll() is None:
                    self.log("✓ Video started (blue screen)")
                    self.video_btn.config(text="⏹ STOP VIDEO", bg="red")
                else:
                    self.log("✗ Video failed completely")
                    self.log("Device may be in use - try: pkill ffmpeg")
                    self.video_proc = None

        except Exception as e:
            self.log(f"✗ Error: {str(e)[:50]}")
            self.video_proc = None

    def stop_video(self):
        """Stop video"""
        if self.video_proc:
            self.log("Stopping video...")
            self.video_proc.terminate()
            try:
                self.video_proc.wait(timeout=2)
            except:
                self.video_proc.kill()
            self.video_proc = None
            self.log("✓ Video stopped")
            self.video_btn.config(text="▶ START VIDEO", bg="green")

    def generate_audio(self):
        """Generate audio for selected type"""
        selected = self.audio_var.get()
        self.log(f"Generating {selected}...")

        audio_dir = Path.home() / "fakecam_audio"
        audio_dir.mkdir(exist_ok=True)

        # Audio content library with more natural speech patterns
        audio_content = {
            "🎤 Meeting Voice": {
                "file": "meeting_voice.wav",
                "text": "Hello everyone... Thanks for joining the meeting today. Um, let me just share my screen here... Can everyone see this clearly? ... Great! So, let's begin with our agenda. First up, we need to discuss the project timeline. Uh, the development is going really well actually. We're definitely on track for the deadline. Any questions so far? ... No? Excellent. Let's move on to the next topic then."
            },
            "💼 Professional Talk": {
                "file": "professional.wav",
                "text": "Good morning everyone. I'll be presenting our quarterly results today. So, as you can see on this slide here, our performance has really exceeded expectations. Revenue is up by, uh, fifteen percent, which is fantastic. Customer satisfaction scores have improved significantly as well. Now, let's look at the detailed breakdown... These numbers really reflect the hard work of the entire team. Really great job everyone."
            },
            "☕ Casual Chat": {
                "file": "casual_chat.wav",
                "text": "Hey! How's it going? ... Yeah, yeah, I saw that email too. Oh man, did you catch the game last night? It was pretty amazing, right? ... Oh, by the way, we should probably sync up about next week's presentation. I can share my screen if you want to take a look at the draft... Just let me know what works for you, okay?"
            },
            "🎯 Quick Update": {
                "file": "quick_update.wav",
                "text": "Hi folks, just a quick update here... So the project is on track. We completed the first milestone yesterday, which is great. Um, no blockers at the moment, everything's running smoothly. I'll have the full report ready by end of day. Thanks everyone!"
            },
            "🔊 Test Audio": {
                "file": "test_audio.wav",
                "text": "Testing, testing, one two three... Can you hear me clearly? Hello? ... This is a microphone test. Audio check... audio check... Is this coming through okay?"
            },
            "🎵 Simple Tone": {
                "file": "tone.wav",
                "type": "tone"
            },
            "🔇 Silence": {
                "file": None,
                "type": "silence"
            }
        }

        info = audio_content.get(selected)
        if not info:
            self.log("✗ Unknown audio type")
            return

        if info.get("type") == "silence":
            self.log("Silence selected - no file needed")
            return

        audio_file = audio_dir / info["file"]

        # Check if already exists
        if audio_file.exists():
            self.log(f"✓ Audio already exists: {info['file']}")
            return

        self.generate_btn.config(text="⏳ Generating...", state="disabled")

        try:
            if info.get("type") == "tone":
                # Generate loud 440Hz tone with increased amplitude
                cmd = [
                    "ffmpeg", "-f", "lavfi",
                    "-i", "sine=frequency=440:duration=5:amplitude=0.8",
                    "-filter:a", "volume=6dB",
                    "-y", str(audio_file)
                ]
                subprocess.run(cmd, capture_output=True)
                self.log(f"✓ Generated loud tone: {info['file']}")
            else:
                # Generate natural-sounding speech
                text = info.get("text", "Test")
                temp_file = audio_file.with_suffix('.temp.wav')
                generated = False

                # Try different TTS engines for more natural sound
                # 1. Try Festival (most natural)
                if not generated and subprocess.run(["which", "festival"], capture_output=True).returncode == 0:
                    try:
                        # Use Festival with a natural voice
                        festival_cmd = f'echo "{text}" | text2wave -eval "(voice_cmu_us_slt_arctic_hts)" -o {temp_file}'
                        result = subprocess.run(festival_cmd, shell=True, capture_output=True)
                        if result.returncode == 0 and temp_file.exists():
                            self.log("  Using Festival (natural voice)")
                            generated = True
                    except:
                        pass

                # 2. Try Flite (lightweight but natural)
                if not generated and subprocess.run(["which", "flite"], capture_output=True).returncode == 0:
                    try:
                        # Use Flite with slt voice (female) or awb (male)
                        voice = "slt" if "Meeting" in selected or "Professional" in selected else "awb"
                        flite_cmd = ["flite", "-voice", voice, "-t", text, "-o", str(temp_file)]
                        result = subprocess.run(flite_cmd, capture_output=True)
                        if result.returncode == 0:
                            self.log(f"  Using Flite ({voice} voice)")
                            generated = True
                    except:
                        pass

                # 3. Try Pico TTS (very natural if available)
                if not generated and subprocess.run(["which", "pico2wave"], capture_output=True).returncode == 0:
                    try:
                        pico_cmd = ["pico2wave", "-l", "en-US", "-w", str(temp_file), text]
                        result = subprocess.run(pico_cmd, capture_output=True)
                        if result.returncode == 0:
                            self.log("  Using Pico TTS (very natural)")
                            generated = True
                    except:
                        pass

                # 4. Try eSpeak-NG (better than espeak)
                if not generated and subprocess.run(["which", "espeak-ng"], capture_output=True).returncode == 0:
                    try:
                        # Use different voices for variety
                        voices = {
                            "Meeting Voice": "en+f3",  # Female voice 3
                            "Professional Talk": "en+m3",  # Male voice 3
                            "Casual Chat": "en+m7",  # Male voice 7
                            "Quick Update": "en+f2",  # Female voice 2
                            "Test Audio": "en+m4"  # Male voice 4
                        }
                        voice = voices.get(selected.replace("🎤 ", "").replace("💼 ", "").replace("☕ ", "").replace("🎯 ", "").replace("🔊 ", ""), "en+m3")

                        espeak_ng_cmd = [
                            "espeak-ng", "-v", voice,
                            "-s", "160",  # Slightly faster for more natural rhythm
                            "-p", "50",  # Pitch variation
                            "-a", "200",  # Max amplitude
                            "-w", str(temp_file),
                            text
                        ]
                        result = subprocess.run(espeak_ng_cmd, capture_output=True)
                        if result.returncode == 0:
                            self.log(f"  Using eSpeak-NG ({voice})")
                            generated = True
                    except:
                        pass

                # 5. Fallback to regular espeak with better settings
                if not generated:
                    # Use espeak with MBROLA voice if available
                    espeak_cmd = [
                        "espeak",
                        "-v", "en+f3",  # Try female voice for variety
                        "-s", "160",  # Natural speaking speed
                        "-p", "45",  # Add pitch variation
                        "-a", "200",  # Max volume
                        "-w", str(temp_file),
                        text
                    ]
                    result = subprocess.run(espeak_cmd, capture_output=True)
                    if result.returncode == 0:
                        self.log("  Using eSpeak (enhanced)")
                        generated = True

                # Post-process: Add effects for more natural sound
                if generated and temp_file.exists():
                    # Apply audio filters to make it sound more natural
                    natural_cmd = [
                        "ffmpeg", "-i", str(temp_file),
                        "-af", (
                            "volume=10dB,"  # Increase volume
                            "highpass=f=80,"  # Remove low frequency rumble
                            "lowpass=f=12000,"  # Soften harsh highs
                            "equalizer=f=2000:t=h:w=200:g=2,"  # Boost speech frequencies
                            "equalizer=f=300:t=h:w=100:g=-2,"  # Reduce robotic low mids
                            "acompressor=threshold=0.3:ratio=3:attack=5:release=100,"  # Compress dynamics
                            "adelay=0.002|0.002"  # Tiny stereo delay for warmth
                        ),
                        "-y", str(audio_file)
                    ]
                    subprocess.run(natural_cmd, capture_output=True)
                    temp_file.unlink(missing_ok=True)  # Remove temp file
                    self.log(f"✓ Generated natural speech: {info['file']}")
                else:
                    self.log("✗ Failed to generate speech")
        except Exception as e:
            self.log(f"✗ Error: {str(e)[:50]}")
        finally:
            self.generate_btn.config(text="🔄 Generate Audio", state="normal")

    def toggle_audio(self):
        """Toggle audio on/off"""
        if self.audio_proc:
            # Check if it's running
            if self.audio_proc == "silence" or self.audio_proc.poll() is None:
                self.stop_audio()
            else:
                self.start_audio()
        else:
            self.start_audio()

    def start_audio(self):
        """Start audio with selection"""
        selected = self.audio_var.get()
        self.log(f"Starting audio: {selected}...")

        # Clean up any existing audio process
        if self.audio_proc:
            self.stop_audio()
            time.sleep(0.5)

        # Kill any orphaned audio processes
        subprocess.run(["pkill", "-f", "ffmpeg.*fakemic"], capture_output=True)
        time.sleep(0.5)

        # Clean and recreate sink
        self.log("  Setting up audio sink...")

        # Remove ALL old null-sink modules
        result = subprocess.run(["pactl", "list", "short", "modules"],
                              capture_output=True, text=True)
        for line in result.stdout.split('\n'):
            if "module-null-sink" in line:
                module_id = line.split()[0]
                subprocess.run(["pactl", "unload-module", module_id],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        time.sleep(0.5)

        # Create fresh sink
        result = subprocess.run([
            "pactl", "load-module", "module-null-sink",
            "sink_name=fakemic",
            "sink_properties=device.description=FakeMicrophone"
        ], capture_output=True, text=True)

        if result.returncode != 0:
            self.log("✗ Failed to create audio sink")
            return

        # Handle different audio types
        if selected == "🔇 Silence":
            # Just create sink, no audio
            self.log("✓ Silent microphone active")
            self.log("  Select 'Monitor of FakeMicrophone' in your app")
            self.audio_btn.config(text="⏹ STOP AUDIO", bg="red")
            self.audio_proc = "silence"  # Mark as running
            return

        # Get audio file
        audio_dir = Path.home() / "fakecam_audio"
        audio_dir.mkdir(exist_ok=True)

        audio_files = {
            "🎤 Meeting Voice": "meeting_voice.wav",
            "💼 Professional Talk": "professional.wav",
            "☕ Casual Chat": "casual_chat.wav",
            "🎯 Quick Update": "quick_update.wav",
            "🔊 Test Audio": "test_audio.wav",
            "🎵 Simple Tone": "tone.wav"
        }

        audio_filename = audio_files.get(selected)
        if not audio_filename:
            self.log("✗ Unknown audio selection")
            return

        audio_file = audio_dir / audio_filename

        # Generate if doesn't exist
        if not audio_file.exists():
            self.log(f"Audio file not found, generating...")
            self.generate_audio()

            # Check again
            if not audio_file.exists():
                self.log("✗ Failed to generate audio file")
                return

        # Play audio in loop with increased volume
        cmd = [
            "ffmpeg",
            "-re",
            "-stream_loop", "-1",  # Loop forever
            "-i", str(audio_file),
            "-filter:a", "volume=2.5",  # Amplify volume by 2.5x (about 8dB)
            "-f", "pulse",
            "fakemic"
        ]

        self.audio_proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL
        )

        time.sleep(1)
        if self.audio_proc.poll() is None:
            self.log("✓ Audio started")
            self.log("  Select 'Monitor of FakeMicrophone' in your app")
            self.audio_btn.config(text="⏹ STOP AUDIO", bg="red")
        else:
            self.log("✗ Audio failed")
            self.audio_proc = None

    def stop_audio(self):
        """Stop audio"""
        if self.audio_proc:
            self.log("Stopping audio...")

            # Handle special case for silence
            if self.audio_proc == "silence":
                self.audio_proc = None
            else:
                # Stop actual process
                self.audio_proc.terminate()
                try:
                    self.audio_proc.wait(timeout=2)
                except:
                    self.audio_proc.kill()
                self.audio_proc = None

            self.log("✓ Audio stopped")
            self.audio_btn.config(text="▶ START AUDIO", bg="green")

    def start_both(self):
        """Start both video and audio"""
        if not self.video_proc or self.video_proc.poll() is not None:
            self.start_video()
            time.sleep(1)

        if not self.audio_proc or self.audio_proc.poll() is not None:
            self.start_audio()

    def cleanup(self):
        """Cleanup on exit - ensure everything is stopped"""
        self.log("Cleaning up...")

        # Stop our processes gracefully first
        try:
            self.stop_video()
            self.stop_audio()
        except:
            pass

        # Comprehensive cleanup
        self.log("  Stopping all processes...")

        # Kill ffmpeg processes with increasing force
        patterns = [
            "ffmpeg.*fakecam",
            "ffmpeg.*video10",
            "ffmpeg.*fakemic",
            "ffmpeg.*FakeMicrophone"
        ]

        for pattern in patterns:
            subprocess.run(["pkill", "-f", pattern], capture_output=True)

        time.sleep(0.5)

        # Force kill if still running
        subprocess.run(["pkill", "-9", "-f", "ffmpeg"], capture_output=True)

        # Clean up audio modules
        self.log("  Removing audio devices...")
        result = subprocess.run(["pactl", "list", "short", "modules"],
                              capture_output=True, text=True)
        for line in result.stdout.split('\n'):
            if "module-null-sink" in line:
                module_id = line.split()[0]
                subprocess.run(["pactl", "unload-module", module_id],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Clean up video device
        self.log("  Removing video device...")
        # Try multiple times as it might be in use
        for attempt in range(3):
            result = subprocess.run(["sudo", "modprobe", "-r", "v4l2loopback"],
                                  capture_output=True, text=True)
            if "in use" not in result.stderr:
                break
            time.sleep(0.5)
            subprocess.run(["sudo", "pkill", "-9", "-f", "video10"], capture_output=True)

        self.log("Cleanup complete")

def main():
    root = tk.Tk()
    app = FakeCam(root)

    # Register cleanup for any exit
    def exit_handler():
        try:
            app.cleanup()
        except:
            pass
        # Extra safety - kill any ffmpeg
        subprocess.run(["pkill", "-f", "ffmpeg"], capture_output=True)

    # Register cleanup handlers
    atexit.register(exit_handler)

    # Handle window close
    def on_close():
        app.cleanup()
        root.quit()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)

    # Handle Ctrl+C
    def signal_handler(sig, frame):
        print("\nReceived interrupt signal, cleaning up...")
        app.cleanup()
        root.quit()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        root.mainloop()
    except KeyboardInterrupt:
        app.cleanup()
    except Exception as e:
        print(f"Error: {e}")
        app.cleanup()
    finally:
        # Final cleanup just in case
        subprocess.run(["pkill", "-f", "ffmpeg"], capture_output=True)

if __name__ == "__main__":
    main()