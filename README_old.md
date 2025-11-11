# FakeCam - Virtual Camera & Microphone Tool

**A simple, powerful tool for creating virtual webcam and microphone devices for testing video calls, especially useful in virtual machines.**

Perfect for testing Element Call, Zoom, Teams, or any video conferencing app!

## ✨ Features

- 🎥 **Virtual Webcam** - Stream video files as a webcam
- 🎤 **Virtual Microphone** - Generate realistic speech or tones
- 🌊 **Ocean/Surfing Videos** - Built-in library of beautiful HD videos
- 🎨 **Modern GUI** - Easy-to-use graphical interface
- 🚀 **VM Optimized** - Special low-resource mode for virtual machines
- 🔧 **One-Click Setup** - Automated installation and configuration

## 🚀 Quick Start

### Quick Start:
```bash
# Install dependencies (one-time setup)
./install_dependencies.sh

# Run FakeCam
python3 fakecam_final.py
```

## 📦 Main Application

**fakecam_final.py** - The consolidated version with all features:
- Modern GUI with video and audio selection
- Natural voice synthesis
- Auto-cleanup and device management
- VM optimization support

## 🎯 Key Features

### Video Options:
- 🏄 **Surfing HD** - 3 minutes of HD surfing footage
- 🌊 **Ocean Waves** - Beautiful ocean scenes
- 📹 **Test Pattern** - Quick technical test
- 🎬 **Sample Video** - Standard test footage

### Audio Options:
- 🎤 **Meeting Conversation** - Natural meeting speech
- 🗣️ **Presentation** - Professional presentation tone
- ☕ **Casual Chat** - Informal conversation
- 🔊 **Test Audio** - Clear test phrases
- 🎵 **Simple Tone** - 440Hz test tone
- 🔇 **Silence** - No audio output

## 🔧 Installation

### One-Time Setup (Installs Everything):
```bash
./install_dependencies.sh
```

This installs:
- ffmpeg (video/audio processing)
- v4l2loopback (virtual camera driver)
- espeak (basic text-to-speech)
- pico2wave (high quality text-to-speech)
- pulseaudio-utils (virtual microphone)
- python3-tk (GUI library)

## 💡 VM Optimization

If running in a virtual machine:
1. Check the **"🔋 VM Optimization Mode"** checkbox
2. Uses 360p resolution and 15fps for low CPU usage
3. Automatically detected if in VM environment

## 📱 Using in Video Apps

1. Start FakeCam (video/audio)
2. Open your video conferencing app
3. Select:
   - **Camera:** "FakeCam"
   - **Microphone:** "FakeMicrophone"

## 🛠️ Utilities

- **reset_fakecam.sh** - Reset if something goes wrong
- **cleanup_project.sh** - Clean up old test files

## 🆘 Troubleshooting

### Video not working?
```bash
./reset_fakecam.sh
```

### Need all dependencies?
```bash
./install_dependencies.sh
```

### Want zero password prompts?
Add module to boot:
```bash
echo "v4l2loopback" | sudo tee -a /etc/modules
echo "options v4l2loopback video_nr=10 card_label='FakeCam'" | sudo tee /etc/modprobe.d/fakecam.conf
sudo reboot
```

## 📂 Project Structure

```
fakecam/
├── fakecam_final.py         # Main application (GUI)
├── install_dependencies.sh  # One-time setup script
├── install_natural_voices.sh # Install better TTS (optional)
├── stop_all.sh             # Emergency stop
├── fix_v4l2ctl.sh          # Fix for VMs
├── clean_audio_cache.sh    # Clear audio cache
├── README.md               # This file
└── .gitignore              # Git ignore rules
```

## 🎉 Credits

Created for easy testing of video conferencing in virtual machines and Linux environments.

Perfect for:
- Testing Element Call
- VM development
- Privacy (use fake video instead of real camera)
- Fun virtual backgrounds

---

**Enjoy your virtual camera! 🎥🎤**