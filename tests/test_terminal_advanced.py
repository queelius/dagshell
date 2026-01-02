#!/usr/bin/env python3
"""
Additional tests for terminal.py to improve coverage.

This module targets the uncovered lines identified by coverage analysis:
- HistoryManager exception handling
- TabCompleter completion methods
- AliasManager operations
- Execute command edge cases
"""

import sys
import os
import tempfile
import json
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from unittest.mock import Mock, patch, MagicMock
import readline

from dagshell.terminal import (
    TerminalSession, TerminalConfig,
    HistoryManager, TabCompleter, AliasManager
)
from dagshell.dagshell_fluent import DagShell


class TestHistoryManager(unittest.TestCase):
    """Test HistoryManager functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.history_file = os.path.join(self.temp_dir, 'test_history')

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        # Clear readline history to avoid test pollution
        readline.clear_history()

    def test_load_nonexistent_history_file(self):
        """Test loading when history file doesn't exist."""
        manager = HistoryManager(os.path.join(self.temp_dir, 'nonexistent'))
        self.assertEqual(manager.history, [])

    def test_add_command(self):
        """Test adding commands to history."""
        manager = HistoryManager(self.history_file)
        manager.add('ls')
        manager.add('pwd')
        self.assertIn('ls', manager.history)
        self.assertIn('pwd', manager.history)

    def test_add_empty_command(self):
        """Test that empty commands are not added."""
        manager = HistoryManager(self.history_file)
        manager.add('')
        manager.add('  ')
        self.assertEqual(len(manager.history), 0)

    def test_add_duplicate_consecutive(self):
        """Test that duplicate consecutive commands are not added."""
        manager = HistoryManager(self.history_file)
        manager.add('ls')
        manager.add('ls')
        self.assertEqual(manager.history.count('ls'), 1)

    def test_get_command(self):
        """Test getting command at specific index."""
        manager = HistoryManager(self.history_file)
        manager.add('first')
        manager.add('second')
        manager.add('third')
        self.assertEqual(manager.get(1), 'first')
        self.assertEqual(manager.get(2), 'second')
        self.assertEqual(manager.get(3), 'third')

    def test_get_invalid_index(self):
        """Test getting command at invalid index."""
        manager = HistoryManager(self.history_file)
        manager.add('test')
        self.assertIsNone(manager.get(0))  # 0 is invalid (1-based)
        self.assertIsNone(manager.get(5))  # Out of range

    def test_get_last(self):
        """Test getting last command."""
        manager = HistoryManager(self.history_file)
        manager.add('first')
        manager.add('last')
        self.assertEqual(manager.get_last(), 'last')

    def test_get_last_empty(self):
        """Test getting last command when history is empty."""
        manager = HistoryManager(self.history_file)
        self.assertIsNone(manager.get_last())

    def test_search(self):
        """Test searching history."""
        manager = HistoryManager(self.history_file)
        manager.add('ls -la')
        manager.add('pwd')
        manager.add('ls /home')
        results = manager.search('ls')
        self.assertEqual(len(results), 2)

    def test_expand_double_bang(self):
        """Test !! expansion."""
        manager = HistoryManager(self.history_file)
        manager.add('echo hello')
        expanded = manager.expand('!!')
        self.assertEqual(expanded, 'echo hello')

    def test_expand_double_bang_no_history(self):
        """Test !! expansion when history is empty."""
        manager = HistoryManager(self.history_file)
        with self.assertRaises(ValueError) as ctx:
            manager.expand('!!')
        self.assertIn('event not found', str(ctx.exception))

    def test_expand_number(self):
        """Test !n expansion."""
        manager = HistoryManager(self.history_file)
        manager.add('first')
        manager.add('second')
        manager.add('third')
        expanded = manager.expand('!2')
        self.assertEqual(expanded, 'second')

    def test_expand_negative_number(self):
        """Test !-n expansion."""
        manager = HistoryManager(self.history_file)
        manager.add('first')
        manager.add('second')
        manager.add('third')
        expanded = manager.expand('!-1')
        self.assertEqual(expanded, 'third')

    def test_expand_number_not_found(self):
        """Test !n expansion when number not found."""
        manager = HistoryManager(self.history_file)
        manager.add('test')
        with self.assertRaises(ValueError) as ctx:
            manager.expand('!99')
        self.assertIn('event not found', str(ctx.exception))

    def test_expand_string(self):
        """Test !string expansion."""
        manager = HistoryManager(self.history_file)
        manager.add('echo hello')
        manager.add('pwd')
        manager.add('echo world')
        expanded = manager.expand('!echo')
        self.assertEqual(expanded, 'echo world')

    def test_expand_string_not_found(self):
        """Test !string expansion when string not found."""
        manager = HistoryManager(self.history_file)
        manager.add('test')
        with self.assertRaises(ValueError) as ctx:
            manager.expand('!nonexistent')
        self.assertIn('event not found', str(ctx.exception))

    def test_expand_no_exclamation(self):
        """Test expansion with no ! in command."""
        manager = HistoryManager(self.history_file)
        result = manager.expand('ls -la')
        self.assertEqual(result, 'ls -la')

    def test_display(self):
        """Test history display."""
        manager = HistoryManager(self.history_file)
        manager.add('first')
        manager.add('second')
        manager.add('third')
        display = manager.display()
        self.assertIn('first', display)
        self.assertIn('second', display)
        self.assertIn('third', display)

    def test_display_with_limit(self):
        """Test history display with limit."""
        manager = HistoryManager(self.history_file)
        manager.add('first')
        manager.add('second')
        manager.add('third')
        display = manager.display(2)
        self.assertNotIn('first', display)
        self.assertIn('second', display)
        self.assertIn('third', display)

    def test_history_max_size(self):
        """Test that history is trimmed when exceeding max size."""
        manager = HistoryManager(self.history_file, max_size=5)
        for i in range(10):
            manager.add(f'command{i}')
        self.assertEqual(len(manager.history), 5)
        self.assertIn('command9', manager.history)
        self.assertNotIn('command0', manager.history)

    def test_save_and_load_history(self):
        """Test saving and loading history."""
        manager1 = HistoryManager(self.history_file)
        manager1.add('test command')
        manager1.save_history()

        # Create new manager and load
        manager2 = HistoryManager(self.history_file)
        self.assertIn('test command', manager2.history)


class TestAliasManager(unittest.TestCase):
    """Test AliasManager functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.alias_file = os.path.join(self.temp_dir, 'test_aliases.json')

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_add_alias(self):
        """Test adding an alias."""
        manager = AliasManager(self.alias_file)
        manager.add('ll', 'ls -la')
        self.assertEqual(manager.aliases['ll'], 'ls -la')

    def test_remove_alias(self):
        """Test removing an alias."""
        manager = AliasManager(self.alias_file)
        manager.add('ll', 'ls -la')
        result = manager.remove('ll')
        self.assertTrue(result)
        self.assertNotIn('ll', manager.aliases)

    def test_remove_nonexistent_alias(self):
        """Test removing nonexistent alias."""
        manager = AliasManager(self.alias_file)
        result = manager.remove('nonexistent')
        self.assertFalse(result)

    def test_expand_alias(self):
        """Test alias expansion."""
        manager = AliasManager(self.alias_file)
        manager.add('ll', 'ls -la')
        expanded = manager.expand('ll /home')
        self.assertEqual(expanded, 'ls -la /home')

    def test_expand_alias_no_args(self):
        """Test alias expansion without extra arguments."""
        manager = AliasManager(self.alias_file)
        manager.add('ll', 'ls -la')
        expanded = manager.expand('ll')
        self.assertEqual(expanded, 'ls -la')

    def test_expand_no_alias(self):
        """Test expansion with no matching alias."""
        manager = AliasManager(self.alias_file)
        expanded = manager.expand('ls -la')
        self.assertEqual(expanded, 'ls -la')

    def test_expand_empty(self):
        """Test expansion with empty command."""
        manager = AliasManager(self.alias_file)
        expanded = manager.expand('')
        self.assertEqual(expanded, '')

    def test_list_aliases(self):
        """Test listing aliases."""
        manager = AliasManager(self.alias_file)
        manager.add('ll', 'ls -la')
        manager.add('la', 'ls -a')
        listing = manager.list_aliases()
        self.assertIn("alias la='ls -a'", listing)
        self.assertIn("alias ll='ls -la'", listing)

    def test_list_aliases_empty(self):
        """Test listing aliases when empty."""
        manager = AliasManager(self.alias_file)
        listing = manager.list_aliases()
        self.assertEqual(listing, 'No aliases defined')

    def test_save_and_load_aliases(self):
        """Test saving and loading aliases."""
        manager1 = AliasManager(self.alias_file)
        manager1.add('ll', 'ls -la')

        # Create new manager and load
        manager2 = AliasManager(self.alias_file)
        self.assertEqual(manager2.aliases.get('ll'), 'ls -la')

    def test_load_invalid_json(self):
        """Test loading when alias file has invalid JSON."""
        with open(self.alias_file, 'w') as f:
            f.write('not valid json')
        manager = AliasManager(self.alias_file)
        self.assertEqual(manager.aliases, {})


class TestTabCompleter(unittest.TestCase):
    """Test TabCompleter functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.shell = DagShell()
        self.aliases = {'ll': 'ls -la'}
        self.completer = TabCompleter(self.shell, self.aliases)
        # Create some test files
        self.shell.fs.mkdir('/home')
        self.shell.fs.mkdir('/home/user')
        self.shell.fs.write('/home/user/file.txt', b'content')

    def test_command_cache_includes_shell_methods(self):
        """Test that command cache includes shell methods."""
        self.assertIn('ls', self.completer._command_cache)
        self.assertIn('cd', self.completer._command_cache)
        self.assertIn('cat', self.completer._command_cache)

    def test_command_cache_includes_special_commands(self):
        """Test that command cache includes special terminal commands."""
        self.assertIn('help', self.completer._command_cache)
        self.assertIn('clear', self.completer._command_cache)
        self.assertIn('exit', self.completer._command_cache)
        self.assertIn('history', self.completer._command_cache)

    def test_command_cache_includes_aliases(self):
        """Test that command cache includes aliases."""
        self.assertIn('ll', self.completer._command_cache)

    def test_complete_command_empty(self):
        """Test completing empty command text."""
        matches = self.completer._complete_command('')
        self.assertEqual(matches, self.completer._command_cache)

    def test_complete_command_partial(self):
        """Test completing partial command."""
        matches = self.completer._complete_command('ec')
        self.assertIn('echo', matches)

    def test_complete_path_absolute(self):
        """Test completing absolute path."""
        matches = self.completer._complete_path('/home/', 'ls /home/')
        self.assertIn('/home/user/', matches)

    def test_complete_path_relative(self):
        """Test completing relative path."""
        self.shell.cd('/home')
        matches = self.completer._complete_path('user', 'ls user')
        # Should have user or user/ in matches
        self.assertTrue(any('user' in m for m in matches))


class TestTerminalSession(unittest.TestCase):
    """Test TerminalSession functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = TerminalConfig(
            user='testuser',
            hostname='testhost',
            history_file=os.path.join(self.temp_dir, 'history'),
            alias_file=os.path.join(self.temp_dir, 'aliases.json')
        )
        self.session = TerminalSession(config=self.config)

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        readline.clear_history()

    def test_execute_empty_command(self):
        """Test executing empty command."""
        output = self.session.execute_command('')
        self.assertEqual(output, '')

    def test_execute_whitespace_command(self):
        """Test executing whitespace-only command."""
        output = self.session.execute_command('   ')
        self.assertEqual(output, '')

    def test_execute_history_command(self):
        """Test history command."""
        self.session.history_manager.add('test1')
        self.session.history_manager.add('test2')
        output = self.session.execute_command('history')
        self.assertIn('test1', output)
        self.assertIn('test2', output)

    def test_execute_history_with_count(self):
        """Test history command with count argument."""
        self.session.history_manager.add('test1')
        self.session.history_manager.add('test2')
        self.session.history_manager.add('test3')
        output = self.session.execute_command('history 2')
        self.assertNotIn('test1', output)
        self.assertIn('test2', output)
        self.assertIn('test3', output)

    def test_execute_alias_list(self):
        """Test alias command (list aliases)."""
        self.session.alias_manager.add('ll', 'ls -la')
        output = self.session.execute_command('alias')
        self.assertIn('ll', output)

    def test_execute_alias_create(self):
        """Test alias creation command."""
        output = self.session.execute_command("alias myls='ls -la'")
        self.assertIn('myls', output)
        self.assertEqual(self.session.alias_manager.aliases.get('myls'), 'ls -la')

    def test_execute_alias_create_double_quotes(self):
        """Test alias creation with double quotes."""
        output = self.session.execute_command('alias myls="ls -la"')
        self.assertIn('myls', output)
        self.assertEqual(self.session.alias_manager.aliases.get('myls'), 'ls -la')

    def test_execute_alias_no_equals(self):
        """Test alias command without equals sign."""
        output = self.session.execute_command('alias invalid')
        self.assertIn('usage', output.lower())

    def test_execute_alias_no_args(self):
        """Test alias command with no arguments after 'alias '."""
        output = self.session.execute_command('alias ')
        # Should show usage or list aliases
        self.assertIsNotNone(output)

    def test_execute_unalias(self):
        """Test unalias command."""
        self.session.alias_manager.add('ll', 'ls -la')
        output = self.session.execute_command('unalias ll')
        self.assertEqual(output, '')
        self.assertNotIn('ll', self.session.alias_manager.aliases)

    def test_execute_unalias_not_found(self):
        """Test unalias command for nonexistent alias."""
        output = self.session.execute_command('unalias nonexistent')
        self.assertIn('not found', output)

    def test_execute_unalias_no_args(self):
        """Test unalias command with no arguments (falls through to shell)."""
        # 'unalias ' with just trailing space stripped becomes 'unalias' which
        # doesn't match the 'unalias ' prefix, so it falls through to base shell
        output = self.session.execute_command('unalias')
        # The base shell doesn't have unalias, so it returns command not found
        self.assertIn('command not found', output)

    def test_execute_with_history_expansion(self):
        """Test command with history expansion."""
        self.session.history_manager.add('echo hello')
        # Execute !! which should expand to 'echo hello'
        output = self.session.execute_command('!!')
        self.assertEqual(output, 'hello')

    def test_execute_history_expansion_error(self):
        """Test history expansion error handling."""
        output = self.session.execute_command('!nonexistent')
        self.assertIn('event not found', output)

    def test_execute_with_alias_expansion(self):
        """Test command with alias expansion."""
        self.session.alias_manager.add('myecho', 'echo')
        output = self.session.execute_command('myecho hello')
        self.assertEqual(output, 'hello')

    def test_config_usage(self):
        """Test using TerminalConfig."""
        config = TerminalConfig(
            user='testuser',
            hostname='testhost'
        )
        session = TerminalSession(config=config)
        self.assertEqual(session.config.user, 'testuser')
        self.assertIsInstance(session.config, TerminalConfig)

    def test_default_config(self):
        """Test session with default config."""
        session = TerminalSession(config=None)
        self.assertIsInstance(session.config, TerminalConfig)


class TestTerminalClear(unittest.TestCase):
    """Test clear command handling."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = TerminalConfig(
            history_file=os.path.join(self.temp_dir, 'history'),
            alias_file=os.path.join(self.temp_dir, 'aliases.json')
        )
        self.session = TerminalSession(config=self.config)

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        readline.clear_history()

    @patch('os.system')
    def test_clear_command(self, mock_system):
        """Test clear command."""
        output = self.session.execute_command('clear')
        self.assertEqual(output, '')
        mock_system.assert_called()


class TestHistoryManagerExceptions(unittest.TestCase):
    """Test HistoryManager exception handling."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        readline.clear_history()

    def test_load_history_ioerror(self):
        """Test loading history with IOError."""
        # Create a directory instead of file to cause IOError
        history_path = os.path.join(self.temp_dir, 'history_dir')
        os.mkdir(history_path)
        manager = HistoryManager(history_path)
        self.assertEqual(manager.history, [])

    def test_save_history_ioerror(self):
        """Test saving history with IOError (to unwritable path)."""
        # Use a path that cannot be written
        manager = HistoryManager('/nonexistent/path/history')
        manager.add('test')
        # Should not raise, just ignore error
        manager.save_history()


class TestAliasManagerExceptions(unittest.TestCase):
    """Test AliasManager exception handling."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_save_aliases_ioerror(self):
        """Test saving aliases with IOError."""
        manager = AliasManager('/nonexistent/path/aliases.json')
        manager.add('test', 'echo test')
        # Should not raise, just ignore error
        manager.save_aliases()


if __name__ == '__main__':
    unittest.main()
