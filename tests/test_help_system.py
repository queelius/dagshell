#!/usr/bin/env python3
"""
Test the help system functionality.
"""

import pytest
from dagshell.terminal import TerminalSession, CommandExecutor
from dagshell.dagshell_fluent import DagShell


class TestHelpSystem:
    """Test the integrated help system."""

    def setup_method(self):
        """Set up test fixtures."""
        self.session = TerminalSession()
        self.shell = DagShell()
        self.executor = CommandExecutor(self.shell)

    def test_general_help(self):
        """Test general help command shows all commands."""
        output = self.session.execute_command('help')
        assert 'DagShell Terminal - Available Commands' in output
        assert 'NAVIGATION:' in output
        assert 'FILE OPERATIONS:' in output
        assert 'TEXT PROCESSING:' in output
        assert 'cd' in output
        assert 'ls' in output
        assert 'grep' in output

    def test_specific_command_help(self):
        """Test help for specific commands."""
        # Test ls help
        output = self.session.execute_command('help ls')
        assert 'ls - List directory contents' in output
        assert 'Usage:' in output
        assert 'Options:' in output
        assert 'Examples:' in output
        assert '-a, --all' in output
        assert '-l, --long' in output

        # Test grep help
        output = self.session.execute_command('help grep')
        assert 'grep - Search for patterns' in output
        assert '-i, --ignore-case' in output
        assert 'PATTERN' in output

        # Test cd help
        output = self.session.execute_command('help cd')
        assert 'cd - Change the current directory' in output
        assert 'PATH' in output
        assert 'cd ..' in output

    def test_help_flag_on_commands(self):
        """Test --help flag on commands."""
        # Test cat --help
        output = self.session.execute_command('cat --help')
        assert 'cat - Concatenate and display files' in output
        assert 'Usage:' in output

        # Test ls --help
        output = self.session.execute_command('ls --help')
        assert 'ls - List directory contents' in output
        assert 'Options:' in output

        # Test -h flag variant
        output = self.session.execute_command('grep -h')
        assert 'grep - Search for patterns' in output

    def test_help_for_special_commands(self):
        """Test help for special terminal commands."""
        # Test help help
        output = self.session.execute_command('help help')
        assert 'help - Show this help system' in output
        assert 'help ls' in output

        # Test clear help
        output = self.session.execute_command('help clear')
        assert 'clear - Clear the terminal screen' in output

        # Test exit help
        output = self.session.execute_command('help exit')
        assert 'exit/quit - Exit the shell' in output

    def test_help_for_nonexistent_command(self):
        """Test help for a command that doesn't exist."""
        output = self.session.execute_command('help nonexistent')
        assert "no help available for 'nonexistent'" in output

    def test_docstring_extraction(self):
        """Test that docstrings are properly extracted and formatted."""
        # Direct test of extraction
        docstring = self.shell.ls.__doc__
        sections = self.executor._extract_docstring_sections(docstring)

        assert sections['description'] == 'List directory contents.'
        assert 'ls [OPTIONS] [PATH]' in sections['usage']
        assert any('-a, --all' in opt for opt in sections['options'])
        assert any('ls /usr' in ex for ex in sections['examples'])

    def test_all_commands_have_help(self):
        """Test that all major commands have proper docstrings."""
        commands_to_test = [
            'pwd', 'cd', 'ls', 'cat', 'echo', 'grep', 'head', 'tail',
            'wc', 'sort', 'uniq', 'mkdir', 'rm', 'cp', 'mv', 'touch',
            'find', 'save', 'load', 'env', 'setenv', 'whoami', 'su'
        ]

        for cmd in commands_to_test:
            method = getattr(self.shell, cmd, None)
            assert method is not None, f"Command {cmd} not found"
            assert method.__doc__ is not None, f"Command {cmd} has no docstring"

            # Check docstring structure
            doc = method.__doc__
            assert 'Usage:' in doc, f"Command {cmd} missing Usage section"
            assert 'Examples:' in doc, f"Command {cmd} missing Examples section"

    def test_help_command_categories(self):
        """Test that commands are properly categorized in help output."""
        output = self.session.execute_command('help')

        categories = [
            'NAVIGATION:', 'FILE OPERATIONS:', 'TEXT PROCESSING:',
            'SEARCH:', 'ENVIRONMENT:', 'PERSISTENCE:', 'SYSTEM:'
        ]

        for category in categories:
            assert category in output, f"Category {category} not in help output"

    def test_help_shows_redirection_info(self):
        """Test that help includes information about redirection and piping."""
        output = self.session.execute_command('help')
        assert 'REDIRECTION AND PIPING:' in output
        assert 'command > file' in output
        assert 'command >> file' in output
        assert 'cmd1 | cmd2' in output


if __name__ == '__main__':
    pytest.main([__file__, '-v'])