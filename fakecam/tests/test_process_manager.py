#!/usr/bin/env python3
"""
Unit tests for process manager module.

Tests process lifecycle, state management, and thread safety.
"""

import unittest
import time

from ..utils.process_manager import ManagedProcess, ProcessRegistry
from ..utils.config import ProcessState


class TestManagedProcess(unittest.TestCase):
    """Test cases for ManagedProcess class."""

    def setUp(self):
        """Set up test fixtures."""
        self.process = ManagedProcess("test_process")

    def tearDown(self):
        """Clean up after tests."""
        if self.process.is_running:
            self.process.stop()

    def test_initial_state(self):
        """Test process initial state."""
        self.assertEqual(self.process.state, ProcessState.STOPPED)
        self.assertFalse(self.process.is_running)
        self.assertIsNone(self.process.get_pid())

    def test_start_simple_command(self):
        """Test starting a simple command."""
        # Use 'sleep' command as a test
        success = self.process.start(["sleep", "10"])

        self.assertTrue(success)
        self.assertEqual(self.process.state, ProcessState.RUNNING)
        self.assertTrue(self.process.is_running)
        self.assertIsNotNone(self.process.get_pid())

    def test_start_nonexistent_command(self):
        """Test starting a nonexistent command."""
        success = self.process.start(["nonexistent_command_12345"])

        self.assertFalse(success)
        self.assertEqual(self.process.state, ProcessState.ERROR)
        self.assertFalse(self.process.is_running)

    def test_stop_process(self):
        """Test stopping a running process."""
        self.process.start(["sleep", "10"])
        self.assertTrue(self.process.is_running)

        success = self.process.stop()

        self.assertTrue(success)
        self.assertEqual(self.process.state, ProcessState.STOPPED)
        self.assertFalse(self.process.is_running)

    def test_stop_already_stopped(self):
        """Test stopping an already stopped process."""
        success = self.process.stop()
        self.assertTrue(success)

    def test_cannot_start_running_process(self):
        """Test that starting a running process raises error."""
        self.process.start(["sleep", "10"])

        with self.assertRaises(RuntimeError):
            self.process.start(["sleep", "5"])


class TestProcessRegistry(unittest.TestCase):
    """Test cases for ProcessRegistry class."""

    def setUp(self):
        """Set up test fixtures."""
        self.registry = ProcessRegistry()

    def tearDown(self):
        """Clean up after tests."""
        self.registry.stop_all()

    def test_register_process(self):
        """Test registering a process."""
        process = ManagedProcess("test")
        self.registry.register(process)

        self.assertIn(process, self.registry.processes)

    def test_unregister_process(self):
        """Test unregistering a process."""
        process = ManagedProcess("test")
        self.registry.register(process)
        self.registry.unregister(process)

        self.assertNotIn(process, self.registry.processes)

    def test_stop_all_processes(self):
        """Test stopping all registered processes."""
        process1 = ManagedProcess("test1")
        process2 = ManagedProcess("test2")

        self.registry.register(process1)
        self.registry.register(process2)

        process1.start(["sleep", "10"])
        process2.start(["sleep", "10"])

        self.assertEqual(self.registry.get_running_count(), 2)

        self.registry.stop_all()

        self.assertEqual(self.registry.get_running_count(), 0)

    def test_get_running_count(self):
        """Test getting count of running processes."""
        self.assertEqual(self.registry.get_running_count(), 0)

        process1 = ManagedProcess("test1")
        process2 = ManagedProcess("test2")

        self.registry.register(process1)
        self.registry.register(process2)

        process1.start(["sleep", "10"])

        self.assertEqual(self.registry.get_running_count(), 1)


if __name__ == '__main__':
    unittest.main()
