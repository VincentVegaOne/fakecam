#!/usr/bin/env python3
"""
Main entry point for FakeCam application.

This module provides the command-line interface and application startup.
"""

import sys
import logging
import signal
import atexit
import argparse

try:
    import tkinter as tk
except ImportError:
    print("Error: tkinter not installed")
    print("Run: sudo apt-get install python3-tk")
    sys.exit(1)

from .gui.main_window import FakeCamGUI
from .utils.config import Config
from .utils.process_manager import get_registry


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


def parse_args():
    """
    Parse command-line arguments.

    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description=f"{Config.APP_NAME} - {Config.APP_DESCRIPTION}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  fakecam                    # Start GUI
  fakecam --debug            # Start with debug logging
  fakecam --version          # Show version

For more information, visit: https://github.com/yourusername/fakecam
        """
    )

    parser.add_argument(
        '--version',
        action='version',
        version=f"{Config.APP_NAME} v{Config.APP_VERSION}"
    )

    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )

    parser.add_argument(
        '--log-file',
        type=str,
        metavar='FILE',
        help='Write logs to file'
    )

    return parser.parse_args()


def setup_logging(args):
    """
    Configure logging based on arguments.

    Args:
        args: Parsed command-line arguments
    """
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")

    if args.log_file:
        file_handler = logging.FileHandler(args.log_file)
        file_handler.setFormatter(
            logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        )
        logging.getLogger().addHandler(file_handler)
        logger.info(f"Logging to file: {args.log_file}")


def ensure_directories():
    """Ensure all required directories exist."""
    try:
        Config.ensure_directories()
        logger.debug("Directories created/verified")
    except Exception as e:
        logger.error(f"Failed to create directories: {e}")
        sys.exit(1)


def main():
    """Main application entry point."""
    # Parse arguments
    args = parse_args()

    # Setup logging
    setup_logging(args)

    logger.info(f"Starting {Config.APP_NAME} v{Config.APP_VERSION}")

    # Ensure directories exist
    ensure_directories()

    # Create Tkinter root
    root = tk.Tk()

    # Create GUI
    app = FakeCamGUI(root)

    # Global cleanup handler
    def cleanup_handler():
        """Global cleanup on exit."""
        try:
            logger.info("Performing cleanup...")
            app.cleanup()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    # Register cleanup handlers
    atexit.register(cleanup_handler)

    # Handle window close
    root.protocol("WM_DELETE_WINDOW", app.on_closing)

    # Handle signals
    def signal_handler(signum, frame):
        """Handle interrupt signals."""
        logger.info(f"Received signal {signum}, shutting down...")
        cleanup_handler()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start main loop
    try:
        logger.info("Starting GUI main loop")
        root.mainloop()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("Application terminated")


if __name__ == "__main__":
    main()
