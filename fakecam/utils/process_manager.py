#!/usr/bin/env python3
"""
Process manager module for FakeCam.
Handles process lifecycle with proper state management and thread safety.
"""

import subprocess
import threading
import logging
import time
from typing import Optional, List
from .config import ProcessState, Config


logger = logging.getLogger(__name__)


class ManagedProcess:
    """
    A managed process with proper state tracking and lifecycle management.

    Provides thread-safe process management with state tracking,
    graceful shutdown, and proper cleanup.
    """

    def __init__(self, name: str):
        """
        Initialize a managed process.

        Args:
            name: Human-readable name for this process
        """
        self.name = name
        self.state = ProcessState.STOPPED
        self.proc: Optional[subprocess.Popen] = None
        self.lock = threading.Lock()
        self._pid: Optional[int] = None

    @property
    def is_running(self) -> bool:
        """Check if process is currently running."""
        with self.lock:
            return self.state == ProcessState.RUNNING and self._is_alive()

    def _is_alive(self) -> bool:
        """Check if the underlying process is alive."""
        return self.proc is not None and self.proc.poll() is None

    def start(self, cmd: List[str]) -> bool:
        """
        Start the process with the given command.

        Args:
            cmd: Command and arguments as list

        Returns:
            bool: True if started successfully

        Raises:
            RuntimeError: If process is already running
        """
        with self.lock:
            if self.state == ProcessState.RUNNING:
                raise RuntimeError(f"Process {self.name} is already running")

            logger.info(f"Starting process: {self.name}")
            self.state = ProcessState.STARTING

            try:
                self.proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL
                )
                self._pid = self.proc.pid
                logger.debug(f"Process {self.name} started with PID {self._pid}")

            except FileNotFoundError as e:
                logger.error(f"Command not found for {self.name}: {e}")
                self.state = ProcessState.ERROR
                return False
            except PermissionError as e:
                logger.error(f"Permission denied for {self.name}: {e}")
                self.state = ProcessState.ERROR
                return False
            except Exception as e:
                logger.error(f"Failed to start {self.name}: {e}")
                self.state = ProcessState.ERROR
                return False

        # Wait a bit and verify it's still running
        time.sleep(Config.PROCESS_START_DELAY)

        with self.lock:
            if self._is_alive():
                self.state = ProcessState.RUNNING
                logger.info(f"Process {self.name} started successfully")
                return True
            else:
                logger.error(f"Process {self.name} died immediately after start")
                self.state = ProcessState.ERROR
                self.proc = None
                return False

    def stop(self) -> bool:
        """
        Stop the process gracefully.

        Returns:
            bool: True if stopped successfully
        """
        with self.lock:
            if self.state == ProcessState.STOPPED:
                logger.debug(f"Process {self.name} already stopped")
                return True

            if self.proc is None:
                self.state = ProcessState.STOPPED
                return True

            logger.info(f"Stopping process: {self.name}")
            self.state = ProcessState.STOPPING

            try:
                # Try graceful termination first
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=Config.PROCESS_STOP_TIMEOUT)
                    logger.debug(f"Process {self.name} terminated gracefully")
                except subprocess.TimeoutExpired:
                    # Force kill if graceful termination fails
                    logger.warning(f"Process {self.name} didn't terminate, forcing kill")
                    self.proc.kill()
                    try:
                        self.proc.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        logger.error(f"Failed to kill process {self.name}")
                        return False

            except Exception as e:
                logger.error(f"Error stopping {self.name}: {e}")
                return False
            finally:
                self.proc = None
                self._pid = None
                self.state = ProcessState.STOPPED
                logger.info(f"Process {self.name} stopped")

        return True

    def get_pid(self) -> Optional[int]:
        """Get the process ID if running."""
        with self.lock:
            return self._pid if self._is_alive() else None


class ProcessRegistry:
    """
    Registry to track all managed processes.

    Ensures all processes can be cleaned up properly on exit.
    """

    def __init__(self):
        """Initialize the process registry."""
        self.processes: List[ManagedProcess] = []
        self.lock = threading.Lock()

    def register(self, process: ManagedProcess):
        """
        Register a managed process.

        Args:
            process: Process to register
        """
        with self.lock:
            if process not in self.processes:
                self.processes.append(process)
                logger.debug(f"Registered process: {process.name}")

    def unregister(self, process: ManagedProcess):
        """
        Unregister a managed process.

        Args:
            process: Process to unregister
        """
        with self.lock:
            if process in self.processes:
                self.processes.remove(process)
                logger.debug(f"Unregistered process: {process.name}")

    def stop_all(self):
        """Stop all registered processes."""
        with self.lock:
            logger.info("Stopping all registered processes")
            for proc in self.processes[:]:  # Copy to avoid modification during iteration
                try:
                    proc.stop()
                except Exception as e:
                    logger.error(f"Error stopping {proc.name}: {e}")

    def get_running_count(self) -> int:
        """Get count of currently running processes."""
        with self.lock:
            return sum(1 for p in self.processes if p.is_running)


# Global registry instance
_registry = ProcessRegistry()


def get_registry() -> ProcessRegistry:
    """Get the global process registry."""
    return _registry


def kill_processes_by_pattern(pattern: str) -> bool:
    """
    Kill processes matching a pattern.

    Args:
        pattern: Pattern to match (used with pkill -f)

    Returns:
        bool: True if successful
    """
    try:
        # First check if any processes match
        result = subprocess.run(
            ["pgrep", "-f", pattern],
            capture_output=True,
            text=True
        )

        if not result.stdout.strip():
            logger.debug(f"No processes matching pattern: {pattern}")
            return True

        pids = result.stdout.strip().split('\n')
        logger.info(f"Killing {len(pids)} processes matching: {pattern}")

        # Try graceful termination first
        subprocess.run(["pkill", "-f", pattern], capture_output=True)
        time.sleep(Config.CLEANUP_DELAY)

        # Check if any are still running
        result = subprocess.run(
            ["pgrep", "-f", pattern],
            capture_output=True,
            text=True
        )

        if result.stdout.strip():
            # Force kill remaining processes
            logger.warning(f"Force killing stubborn processes: {pattern}")
            subprocess.run(["pkill", "-9", "-f", pattern], capture_output=True)
            time.sleep(Config.CLEANUP_DELAY)

        return True

    except FileNotFoundError:
        logger.warning("pkill/pgrep not found, cannot kill processes by pattern")
        return False
    except Exception as e:
        logger.error(f"Error killing processes by pattern {pattern}: {e}")
        return False


def kill_process_by_name(name: str) -> bool:
    """
    Kill all processes with exact name match.

    Args:
        name: Exact process name

    Returns:
        bool: True if successful
    """
    try:
        subprocess.run(["pkill", name], capture_output=True)
        time.sleep(Config.CLEANUP_DELAY)
        subprocess.run(["pkill", "-9", name], capture_output=True)
        return True
    except Exception as e:
        logger.error(f"Error killing process {name}: {e}")
        return False
