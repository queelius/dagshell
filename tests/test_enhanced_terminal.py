#!/usr/bin/env python3
"""
Tests for the enhanced terminal module.

This module tests:
- History management with persistence
- History expansion (!!, !n, !-n)
- Tab completion for commands and paths
- Command aliases
- Keyboard shortcuts simulation
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
import tempfile
import json
from unittest.mock import Mock, patch, MagicMock
import readline

from dagshell.enhanced_terminal import (
    EnhancedTerminalSession,
    EnhancedTerminalConfig,
    HistoryManager,
    TabCompleter,
    AliasManager
)
from dagshell.dagshell_fluent import DagShell


class TestHistoryManager(unittest.TestCase):
    """Test the history manager."""

    def setUp(self):
        """Set up test fixtures."""
        # Create temporary history file
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.history')
        self.temp_file.close()

        # Clear readline history for clean test
        try:
            readline.clear_history()
        except AttributeError:
            pass  # Not available on all platforms

        self.history_manager = HistoryManager(self.temp_file.name, max_size=100)

    def tearDown(self):
        """Clean up test fixtures."""
        os.unlink(self.temp_file.name)

    def test_add_command(self):
        """Test adding commands to history."""
        self.history_manager.add("ls -la")
        self.history_manager.add("cd /home")
        self.history_manager.add("pwd")

        self.assertEqual(len(self.history_manager.history), 3)
        self.assertEqual(self.history_manager.history[0], "ls -la")
        self.assertEqual(self.history_manager.history[1], "cd /home")
        self.assertEqual(self.history_manager.history[2], "pwd")

    def test_no_duplicate_consecutive(self):
        """Test that consecutive duplicate commands are not added."""
        self.history_manager.add("ls")
        self.history_manager.add("ls")
        self.history_manager.add("pwd")
        self.history_manager.add("ls")

        self.assertEqual(len(self.history_manager.history), 3)
        self.assertEqual(self.history_manager.history, ["ls", "pwd", "ls"])

    def test_get_command(self):
        """Test getting command by index."""
        self.history_manager.add("first")
        self.history_manager.add("second")
        self.history_manager.add("third")

        self.assertEqual(self.history_manager.get(1), "first")
        self.assertEqual(self.history_manager.get(2), "second")
        self.assertEqual(self.history_manager.get(3), "third")
        self.assertIsNone(self.history_manager.get(0))
        self.assertIsNone(self.history_manager.get(4))

    def test_get_last(self):
        """Test getting last command."""
        self.assertIsNone(self.history_manager.get_last())

        self.history_manager.add("first")
        self.assertEqual(self.history_manager.get_last(), "first")

        self.history_manager.add("second")
        self.assertEqual(self.history_manager.get_last(), "second")

    def test_search_history(self):
        """Test searching history."""
        self.history_manager.add("ls -la")
        self.history_manager.add("cd /home")
        self.history_manager.add("ls /tmp")
        self.history_manager.add("pwd")

        results = self.history_manager.search("ls")
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0], (1, "ls -la"))
        self.assertEqual(results[1], (3, "ls /tmp"))

    def test_expand_double_bang(self):
        """Test !! expansion."""
        self.history_manager.add("echo hello")
        self.history_manager.add("ls -la")

        expanded = self.history_manager.expand("!! | grep txt")
        self.assertEqual(expanded, "ls -la | grep txt")

    def test_expand_number(self):
        """Test !n expansion."""
        self.history_manager.add("echo one")
        self.history_manager.add("echo two")
        self.history_manager.add("echo three")

        expanded = self.history_manager.expand("!2 && pwd")
        self.assertEqual(expanded, "echo two && pwd")

    def test_expand_negative_number(self):
        """Test !-n expansion."""
        self.history_manager.add("echo one")
        self.history_manager.add("echo two")
        self.history_manager.add("echo three")

        expanded = self.history_manager.expand("!-1")
        self.assertEqual(expanded, "echo three")

        expanded = self.history_manager.expand("!-2")
        self.assertEqual(expanded, "echo two")

    def test_expand_string(self):
        """Test !string expansion."""
        self.history_manager.add("echo hello")
        self.history_manager.add("ls -la")
        self.history_manager.add("echo world")

        expanded = self.history_manager.expand("!echo")
        self.assertEqual(expanded, "echo world")

        expanded = self.history_manager.expand("!ls")
        self.assertEqual(expanded, "ls -la")

    def test_expand_not_found(self):
        """Test expansion with non-existent reference."""
        self.history_manager.add("echo hello")

        with self.assertRaises(ValueError):
            self.history_manager.expand("!99")

        with self.assertRaises(ValueError):
            self.history_manager.expand("!nonexistent")

    def test_display_history(self):
        """Test history display formatting."""
        self.history_manager.add("first")
        self.history_manager.add("second")
        self.history_manager.add("third")

        output = self.history_manager.display()
        lines = output.split('\n')
        self.assertEqual(len(lines), 3)
        self.assertIn("first", lines[0])
        self.assertIn("second", lines[1])
        self.assertIn("third", lines[2])

        # Test with limit
        output = self.history_manager.display(2)
        lines = output.split('\n')
        self.assertEqual(len(lines), 2)
        self.assertIn("second", lines[0])
        self.assertIn("third", lines[1])


class TestAliasManager(unittest.TestCase):
    """Test the alias manager."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.aliases')
        self.temp_file.close()
        self.alias_manager = AliasManager(self.temp_file.name)

    def tearDown(self):
        """Clean up test fixtures."""
        os.unlink(self.temp_file.name)

    def test_add_alias(self):
        """Test adding aliases."""
        self.alias_manager.add("ll", "ls -la")
        self.alias_manager.add("la", "ls -A")

        self.assertEqual(self.alias_manager.aliases["ll"], "ls -la")
        self.assertEqual(self.alias_manager.aliases["la"], "ls -A")

    def test_remove_alias(self):
        """Test removing aliases."""
        self.alias_manager.add("ll", "ls -la")
        self.alias_manager.add("la", "ls -A")

        self.assertTrue(self.alias_manager.remove("ll"))
        self.assertNotIn("ll", self.alias_manager.aliases)
        self.assertIn("la", self.alias_manager.aliases)

        self.assertFalse(self.alias_manager.remove("nonexistent"))

    def test_expand_alias(self):
        """Test alias expansion."""
        self.alias_manager.add("ll", "ls -la")
        self.alias_manager.add("g", "grep")

        expanded = self.alias_manager.expand("ll")
        self.assertEqual(expanded, "ls -la")

        expanded = self.alias_manager.expand("ll /home")
        self.assertEqual(expanded, "ls -la /home")

        expanded = self.alias_manager.expand("g pattern file.txt")
        self.assertEqual(expanded, "grep pattern file.txt")

        # No expansion for non-aliases
        expanded = self.alias_manager.expand("cat file.txt")
        self.assertEqual(expanded, "cat file.txt")

    def test_list_aliases(self):
        """Test listing aliases."""
        output = self.alias_manager.list_aliases()
        self.assertEqual(output, "No aliases defined")

        self.alias_manager.add("ll", "ls -la")
        self.alias_manager.add("la", "ls -A")

        output = self.alias_manager.list_aliases()
        self.assertIn("alias la='ls -A'", output)
        self.assertIn("alias ll='ls -la'", output)

    def test_persistence(self):
        """Test alias persistence."""
        self.alias_manager.add("ll", "ls -la")
        self.alias_manager.save_aliases()

        # Create new manager with same file
        new_manager = AliasManager(self.temp_file.name)
        self.assertEqual(new_manager.aliases["ll"], "ls -la")


class TestTabCompleter(unittest.TestCase):
    """Test tab completion functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.shell = DagShell()
        # Create some test structure
        self.shell.mkdir("/home").mkdir("/tmp").mkdir("/usr")
        self.shell.cd("/home")
        self.shell.touch("file1.txt").touch("file2.txt")
        self.shell.mkdir("documents")

        self.aliases = {"ll": "ls -la", "la": "ls -A"}
        self.completer = TabCompleter(self.shell, self.aliases)

    def test_command_completion(self):
        """Test command name completion."""
        # Complete 'l' should give ls
        matches = self.completer._complete_command("l")
        self.assertIn("ls", matches)
        self.assertIn("ll", matches)  # alias
        self.assertIn("la", matches)  # alias
        self.assertIn("load", matches)

        # Complete 'ec' should give echo
        matches = self.completer._complete_command("ec")
        self.assertIn("echo", matches)

        # Complete 'ali' should give alias
        matches = self.completer._complete_command("ali")
        self.assertIn("alias", matches)

    def test_path_completion_relative(self):
        """Test relative path completion."""
        # In /home, complete 'doc'
        matches = self.completer._complete_path("doc", "ls doc")
        self.assertIn("documents/", matches)

        # Complete 'file'
        matches = self.completer._complete_path("file", "cat file")
        self.assertIn("file1.txt", matches)
        self.assertIn("file2.txt", matches)

    def test_path_completion_absolute(self):
        """Test absolute path completion."""
        # Complete '/h'
        matches = self.completer._complete_path("/h", "cd /h")
        self.assertIn("/home/", matches)

        # Complete '/t'
        matches = self.completer._complete_path("/t", "cd /t")
        self.assertIn("/tmp/", matches)


class TestEnhancedTerminalSession(unittest.TestCase):
    """Test the enhanced terminal session."""

    def setUp(self):
        """Set up test fixtures."""
        # Create temporary files
        self.history_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.history')
        self.history_file.close()

        self.alias_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.aliases')
        self.alias_file.close()

        # Create config
        self.config = EnhancedTerminalConfig(
            history_file=self.history_file.name,
            alias_file=self.alias_file.name,
            history_max_size=100
        )

        # Create session
        self.session = EnhancedTerminalSession(config=self.config)

    def tearDown(self):
        """Clean up test fixtures."""
        os.unlink(self.history_file.name)
        os.unlink(self.alias_file.name)

    def test_history_command(self):
        """Test history command."""
        # Add some history
        self.session.history_manager.add("echo one")
        self.session.history_manager.add("echo two")
        self.session.history_manager.add("echo three")

        # Test history command
        output = self.session.execute_command("history")
        self.assertIn("echo one", output)
        self.assertIn("echo two", output)
        self.assertIn("echo three", output)

        # Test history with count
        output = self.session.execute_command("history 2")
        self.assertNotIn("echo one", output)
        self.assertIn("echo two", output)
        self.assertIn("echo three", output)

    def test_alias_commands(self):
        """Test alias and unalias commands."""
        # Create alias
        output = self.session.execute_command("alias ll='ls -la'")
        self.assertIn("ll='ls -la'", output)

        # List aliases
        output = self.session.execute_command("alias")
        self.assertIn("ll='ls -la'", output)

        # Use alias
        output = self.session.execute_command("ll")
        # This should execute 'ls -la'

        # Remove alias
        output = self.session.execute_command("unalias ll")
        self.assertEqual(output, "")

        # Try to remove non-existent alias
        output = self.session.execute_command("unalias nonexistent")
        self.assertIn("not found", output)

    def test_history_expansion_in_execute(self):
        """Test history expansion in command execution."""
        # Add history
        self.session.history_manager.add("echo hello")

        # Test !! expansion
        with patch('builtins.print') as mock_print:
            output = self.session.execute_command("!!")
            # Should execute "echo hello"
            self.assertIn("hello", output)

    def test_clear_command(self):
        """Test clear command."""
        with patch('os.system') as mock_system:
            self.session.execute_command("clear")
            mock_system.assert_called_once()

    def test_combined_features(self):
        """Test combination of features."""
        # Create an alias
        self.session.execute_command("alias g='grep'")

        # Execute a command that will be in history
        output = self.session.execute_command("echo test")
        self.assertIn("test", output)

        # Now test history expansion
        output = self.session.execute_command("!!")
        self.assertIn("test", output)


class TestIntegration(unittest.TestCase):
    """Integration tests for enhanced terminal."""

    def test_full_workflow(self):
        """Test a complete workflow with all features."""
        # Create temporary files
        history_file = tempfile.NamedTemporaryFile(mode='w', delete=False)
        history_file.close()

        alias_file = tempfile.NamedTemporaryFile(mode='w', delete=False)
        alias_file.close()

        try:
            # Create session
            config = EnhancedTerminalConfig(
                history_file=history_file.name,
                alias_file=alias_file.name
            )
            session = EnhancedTerminalSession(config=config)

            # Create some structure
            session.execute_command("mkdir /workspace")
            session.execute_command("cd /workspace")
            session.execute_command("echo 'Hello World' > test.txt")

            # Create alias
            session.execute_command("alias ll='ls -la'")

            # Use the alias
            output = session.execute_command("ll")

            # Check that commands were executed and added to history
            # The history should have the commands we just ran
            self.assertTrue(len(session.history_manager.history) > 0)

            # Use history expansion
            session.execute_command("!echo")  # Should repeat the echo command

            # Clean up and check persistence
            session._cleanup()

            # Create new session with same files
            new_session = EnhancedTerminalSession(config=config)

            # Check alias persisted
            output = new_session.execute_command("alias")
            self.assertIn("ll='ls -la'", output)

        finally:
            os.unlink(history_file.name)
            os.unlink(alias_file.name)


if __name__ == '__main__':
    unittest.main()