#!/bin/bash

# FakeCam Dependencies Installer
# Installs everything in one go to minimize password prompts

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}╔════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║       FakeCam Complete Installation Script         ║${NC}"
echo -e "${CYAN}║         One Password - All Dependencies            ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════╝${NC}\n"

# Detect distribution
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
    VERSION=$VERSION_ID
else
    echo -e "${RED}Cannot detect OS${NC}"
    exit 1
fi

echo -e "${YELLOW}Detected OS:${NC} $NAME $VERSION\n"

# Check what's missing
MISSING_PACKAGES=""
MISSING_PYTHON=""

echo -e "${CYAN}Checking dependencies...${NC}\n"

# Core dependencies
DEPS=(
    "ffmpeg:ffmpeg"
    "v4l2loopback:v4l2loopback-dkms v4l2loopback-utils"
    "espeak:espeak"
    "v4l2-ctl:v4l-utils"
    "pactl:pulseaudio-utils"
)

for dep in "${DEPS[@]}"; do
    IFS=':' read -r cmd packages <<< "$dep"
    if command -v $cmd &> /dev/null; then
        echo -e "  ${GREEN}✓${NC} $cmd is installed"
    else
        echo -e "  ${RED}✗${NC} $cmd is missing"
        MISSING_PACKAGES="$MISSING_PACKAGES $packages"
    fi
done

# Check Python tkinter
echo -e "\n${CYAN}Checking Python modules...${NC}\n"
if python3 -c "import tkinter" 2>/dev/null; then
    echo -e "  ${GREEN}✓${NC} python3-tk is installed"
else
    echo -e "  ${RED}✗${NC} python3-tk is missing"
    MISSING_PYTHON="python3-tk"
fi

# Check if anything needs installation
ALL_MISSING="$MISSING_PACKAGES $MISSING_PYTHON"

if [ -z "$ALL_MISSING" ]; then
    echo -e "\n${GREEN}All dependencies are already installed!${NC}"

    # Check if module needs loading
    if ! lsmod | grep -q v4l2loopback; then
        echo -e "\n${YELLOW}v4l2loopback module is not loaded.${NC}"
        read -p "Load it now? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo -e "\n${CYAN}Loading v4l2loopback module...${NC}"
            sudo modprobe v4l2loopback video_nr=10 card_label='FakeCam' exclusive_caps=1
            if [ $? -eq 0 ]; then
                echo -e "${GREEN}✓ Module loaded successfully${NC}"
            fi
        fi
    else
        echo -e "\n${GREEN}v4l2loopback module is already loaded${NC}"
    fi

    echo -e "\n${GREEN}You're ready to run FakeCam!${NC}"
    echo -e "${CYAN}Run: python3 fakecam_gui_v2.py${NC}\n"
    exit 0
fi

# Installation needed
echo -e "\n${YELLOW}Missing packages:${NC} $ALL_MISSING"
echo -e "\n${CYAN}This script will install all missing dependencies with ONE password prompt.${NC}"
echo -e "${YELLOW}You will only need to enter your password ONCE.${NC}\n"

read -p "Install all missing dependencies now? (y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "\n${YELLOW}Installation cancelled${NC}"
    exit 1
fi

# Prepare installation command based on distro
echo -e "\n${CYAN}Installing all dependencies (one password prompt)...${NC}\n"

if [[ "$OS" == "ubuntu" ]] || [[ "$OS" == "debian" ]] || [[ "$OS" == "linuxmint" ]]; then
    # Update package list and install everything at once
    INSTALL_CMD="apt-get update && apt-get install -y $ALL_MISSING"

    echo -e "${YELLOW}Running: sudo $INSTALL_CMD${NC}\n"
    sudo bash -c "$INSTALL_CMD"

elif [[ "$OS" == "fedora" ]]; then
    # Fedora packages
    FEDORA_PACKAGES=$(echo $ALL_MISSING | sed 's/python3-tk/python3-tkinter/g' | sed 's/v4l2loopback-dkms/v4l2loopback/g')
    INSTALL_CMD="dnf install -y $FEDORA_PACKAGES"

    echo -e "${YELLOW}Running: sudo $INSTALL_CMD${NC}\n"
    sudo bash -c "$INSTALL_CMD"

elif [[ "$OS" == "arch" ]]; then
    # Arch packages
    ARCH_PACKAGES=$(echo $ALL_MISSING | sed 's/python3-tk/tk/g' | sed 's/v4l2loopback-dkms/v4l2loopback-dkms/g')
    INSTALL_CMD="pacman -S --noconfirm $ARCH_PACKAGES"

    echo -e "${YELLOW}Running: sudo $INSTALL_CMD${NC}\n"
    sudo bash -c "$INSTALL_CMD"

else
    echo -e "${RED}Unsupported distribution: $OS${NC}"
    echo -e "${YELLOW}Please install manually:${NC}"
    echo -e "  $ALL_MISSING"
    exit 1
fi

# Check if installation succeeded
if [ $? -eq 0 ]; then
    echo -e "\n${GREEN}✓ All dependencies installed successfully!${NC}"

    # Try to install optional Pico TTS (better voice quality)
    echo -e "\n${YELLOW}Checking for optional TTS engines...${NC}"
    if ! command -v pico2wave &> /dev/null; then
        if [[ "$OS" == "ubuntu" ]] || [[ "$OS" == "debian" ]] || [[ "$OS" == "linuxmint" ]]; then
            echo -e "${CYAN}Attempting to install Pico TTS...${NC}"
            if sudo apt-get install -y libttspico-utils 2>/dev/null; then
                echo -e "${GREEN}✓ Pico TTS installed (better voice quality!)${NC}"
            else
                echo -e "${YELLOW}ℹ Pico TTS not available on your system${NC}"
                echo -e "${GREEN}  No problem - espeak will work great!${NC}"
            fi
        fi
    else
        echo -e "${GREEN}✓ Pico TTS already installed${NC}"
    fi

    # Load v4l2loopback module
    echo -e "\n${CYAN}Loading v4l2loopback module...${NC}"
    sudo modprobe v4l2loopback video_nr=10 card_label='FakeCam' exclusive_caps=1

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Module loaded${NC}"

        # Verify device creation
        if [ -e /dev/video10 ]; then
            echo -e "${GREEN}✓ Device /dev/video10 created${NC}"
        fi
    else
        echo -e "${YELLOW}Module loading failed - will retry when running GUI${NC}"
    fi

    # Add user to video group if needed
    if ! groups | grep -q video; then
        echo -e "\n${CYAN}Adding user to video group...${NC}"
        sudo usermod -a -G video $USER
        echo -e "${YELLOW}Note: You may need to logout/login for group change to take effect${NC}"
    fi

    echo -e "\n${GREEN}╔════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║           Installation Complete!                   ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════╝${NC}"
    echo -e "\n${CYAN}You can now run FakeCam:${NC}"
    echo -e "  ${GREEN}python3 fakecam_gui_v2.py${NC}\n"
    echo -e "${YELLOW}No more password prompts needed!${NC}\n"

else
    echo -e "\n${RED}Installation failed!${NC}"
    echo -e "${YELLOW}Please check the error messages above${NC}"
    exit 1
fi