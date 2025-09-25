#!/usr/bin/env python3
"""
Tests for the dagshell terminal emulator.

This module provides comprehensive tests for the command parser,
executor, and terminal session components.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from unittest.mock import Mock, patch, MagicMock

from dagshell.command_parser import (
    CommandParser, Command, Pipeline, CommandGroup,
    RedirectType, Redirect
)
from dagshell.terminal import (
    TerminalSession, CommandExecutor, CommandHistory,
    TerminalConfig
)
from dagshell.dagshell_fluent import DagShell, CommandResult
import dagshell.dagshell as dagshell


class TestCommandParser(unittest.TestCase):
    """Test the command parser."""

    def setUp(self):
        """Set up test fixtures."""
        self.parser = CommandParser()

    def test_parse_simple_command(self):
        """Test parsing a simple command."""
        cmd = self.parser.parse_simple("ls")
        self.assertEqual(cmd.name, "ls")
        self.assertEqual(cmd.args, [])
        self.assertEqual(cmd.flags, {})

    def test_parse_command_with_args(self):
        """Test parsing command with arguments."""
        cmd = self.parser.parse_simple("echo hello world")
        self.assertEqual(cmd.name, "echo")
        self.assertEqual(cmd.args, ["hello", "world"])

    def test_parse_command_with_flags(self):
        """Test parsing command with flags."""
        cmd = self.parser.parse_simple("ls -la")
        self.assertEqual(cmd.name, "ls")
        self.assertEqual(cmd.flags, {"all": True, "long": True})

        cmd = self.parser.parse_simple("ls -l -a")
        self.assertEqual(cmd.name, "ls")
        self.assertEqual(cmd.flags, {"long": True, "all": True})

    def test_parse_long_flags(self):
        """Test parsing long flags."""
        cmd = self.parser.parse_simple("grep --ignore-case pattern")
        self.assertEqual(cmd.name, "grep")
        self.assertEqual(cmd.args, ["pattern"])
        self.assertEqual(cmd.flags, {"ignore-case": True})

        cmd = self.parser.parse_simple("sort --reverse --numeric")
        self.assertEqual(cmd.name, "sort")
        self.assertEqual(cmd.flags, {"reverse": True, "numeric": True})

    def test_parse_flag_with_value(self):
        """Test parsing flags with values."""
        cmd = self.parser.parse_simple("head -n 20")
        self.assertEqual(cmd.name, "head")
        self.assertEqual(cmd.args, [])
        self.assertEqual(cmd.flags, {"lines": 20})

        cmd = self.parser.parse_simple("tail -n 5 file.txt")
        self.assertEqual(cmd.name, "tail")
        self.assertEqual(cmd.args, ["file.txt"])
        self.assertEqual(cmd.flags, {"lines": 5})

    def test_parse_quoted_arguments(self):
        """Test parsing quoted arguments."""
        cmd = self.parser.parse_simple('echo "hello world"')
        self.assertEqual(cmd.name, "echo")
        self.assertEqual(cmd.args, ["hello world"])

        cmd = self.parser.parse_simple("echo 'single quotes'")
        self.assertEqual(cmd.name, "echo")
        self.assertEqual(cmd.args, ["single quotes"])

    def test_parse_redirections(self):
        """Test parsing redirections."""
        cmd = self.parser.parse_simple("echo hello > output.txt")
        self.assertEqual(cmd.name, "echo")
        self.assertEqual(cmd.args, ["hello"])
        self.assertEqual(len(cmd.redirects), 1)
        self.assertEqual(cmd.redirects[0].type, RedirectType.WRITE)
        self.assertEqual(cmd.redirects[0].target, "output.txt")

        cmd = self.parser.parse_simple("echo world >> output.txt")
        self.assertEqual(cmd.name, "echo")
        self.assertEqual(cmd.args, ["world"])
        self.assertEqual(cmd.redirects[0].type, RedirectType.APPEND)

        cmd = self.parser.parse_simple("cat < input.txt")
        self.assertEqual(cmd.name, "cat")
        self.assertEqual(cmd.redirects[0].type, RedirectType.READ)
        self.assertEqual(cmd.redirects[0].target, "input.txt")

    def test_parse_pipeline(self):
        """Test parsing pipelines."""
        group = self.parser.parse("ls | grep test")
        self.assertEqual(len(group.pipelines), 1)
        pipeline = group.pipelines[0][0]
        self.assertEqual(len(pipeline.commands), 2)
        self.assertEqual(pipeline.commands[0].name, "ls")
        self.assertEqual(pipeline.commands[1].name, "grep")
        self.assertEqual(pipeline.commands[1].args, ["test"])

    def test_parse_complex_pipeline(self):
        """Test parsing complex pipelines."""
        group = self.parser.parse("cat file.txt | grep pattern | sort | uniq")
        pipeline = group.pipelines[0][0]
        self.assertEqual(len(pipeline.commands), 4)
        self.assertEqual(pipeline.commands[0].name, "cat")
        self.assertEqual(pipeline.commands[1].name, "grep")
        self.assertEqual(pipeline.commands[2].name, "sort")
        self.assertEqual(pipeline.commands[3].name, "uniq")

    def test_parse_command_sequence(self):
        """Test parsing command sequences."""
        group = self.parser.parse("cd /home ; ls")
        self.assertEqual(len(group.pipelines), 2)
        self.assertEqual(group.pipelines[0][0].commands[0].name, "cd")
        self.assertEqual(group.pipelines[0][1], ";")
        self.assertEqual(group.pipelines[1][0].commands[0].name, "ls")

    def test_parse_conditional_execution(self):
        """Test parsing && and || operators."""
        group = self.parser.parse("test -f file && echo exists")
        self.assertEqual(len(group.pipelines), 2)
        self.assertEqual(group.pipelines[0][1], "&&")

        group = self.parser.parse("test -f file || echo missing")
        self.assertEqual(len(group.pipelines), 2)
        self.assertEqual(group.pipelines[0][1], "||")

    def test_parse_pipeline_with_redirection(self):
        """Test parsing pipeline with redirection."""
        group = self.parser.parse("ls | grep test > results.txt")
        pipeline = group.pipelines[0][0]
        self.assertEqual(len(pipeline.commands), 2)
        self.assertEqual(pipeline.commands[1].name, "grep")
        self.assertEqual(len(pipeline.commands[1].redirects), 1)
        self.assertEqual(pipeline.commands[1].redirects[0].target, "results.txt")

    def test_parse_empty_command(self):
        """Test parsing empty command."""
        group = self.parser.parse("")
        self.assertEqual(len(group.pipelines), 0)

        group = self.parser.parse("   ")
        self.assertEqual(len(group.pipelines), 0)


class TestCommandExecutor(unittest.TestCase):
    """Test the command executor."""

    def setUp(self):
        """Set up test fixtures."""
        # Create virtual filesystem
        self.shell = DagShell()  # Creates its own filesystem
        self.executor = CommandExecutor(self.shell)
        self.parser = CommandParser()

        # Create some test files using the shell's filesystem
        self.shell.fs.write('/test.txt', b'Hello World\nTest Line\n')
        self.shell.fs.mkdir('/testdir')
        self.shell.fs.write('/testdir/file1.txt', b'File 1')
        self.shell.fs.write('/testdir/file2.txt', b'File 2')

    def test_execute_simple_command(self):
        """Test executing a simple command."""
        cmd = self.parser.parse_simple("pwd")
        result = self.executor._execute_command(cmd)
        self.assertEqual(result.text, "/")

    def test_execute_ls(self):
        """Test executing ls command."""
        cmd = self.parser.parse_simple("ls")
        result = self.executor._execute_command(cmd)
        self.assertIn("test.txt", result.text)
        self.assertIn("testdir", result.text)

        cmd = self.parser.parse_simple("ls -l")
        result = self.executor._execute_command(cmd)
        self.assertIn("test.txt", result.text)
        self.assertIn("rw-r--r--", result.text)

    def test_execute_cd(self):
        """Test executing cd command."""
        cmd = self.parser.parse_simple("cd /testdir")
        result = self.executor._execute_command(cmd)
        self.assertEqual(self.shell._cwd, "/testdir")

        cmd = self.parser.parse_simple("pwd")
        result = self.executor._execute_command(cmd)
        self.assertEqual(result.text, "/testdir")

    def test_execute_cat(self):
        """Test executing cat command."""
        cmd = self.parser.parse_simple("cat /test.txt")
        result = self.executor._execute_command(cmd)
        self.assertIn("Hello World", result.text)
        self.assertIn("Test Line", result.text)

    def test_execute_echo(self):
        """Test executing echo command."""
        cmd = self.parser.parse_simple("echo hello world")
        result = self.executor._execute_command(cmd)
        self.assertEqual(result.text, "hello world")

        cmd = self.parser.parse_simple("echo -n hello")
        result = self.executor._execute_command(cmd)
        self.assertEqual(result.text, "hello")

    def test_execute_grep(self):
        """Test executing grep command."""
        # Set up last result for piping
        self.shell._last_result = CommandResult(
            data=["Hello World", "Test Line", "Another Test"],
            text="Hello World\nTest Line\nAnother Test"
        )

        cmd = self.parser.parse_simple("grep Test")
        result = self.executor._execute_command(cmd)
        self.assertIn("Test Line", result.text)
        self.assertIn("Another Test", result.text)
        self.assertNotIn("Hello World", result.text)

    def test_execute_pipeline(self):
        """Test executing a pipeline."""
        group = self.parser.parse("cat /test.txt | grep Test")
        result = self.executor.execute(group)
        self.assertIn("Test Line", result.text)
        self.assertNotIn("Hello World", result.text)

    def test_execute_with_redirection(self):
        """Test executing command with redirection."""
        cmd = self.parser.parse_simple("echo hello > /output.txt")
        result = self.executor._execute_command(cmd)

        # Check file was created
        content = self.shell.fs.read('/output.txt')
        self.assertEqual(content.decode('utf-8').strip(), "hello")

    def test_execute_head(self):
        """Test executing head command."""
        # Create a file with multiple lines
        self.shell.fs.write('/lines.txt', b'\n'.join(f"Line {i}".encode() for i in range(20)))

        cmd = self.parser.parse_simple("cat /lines.txt")
        result = self.executor._execute_command(cmd)
        self.shell._last_result = result

        cmd = self.parser.parse_simple("head -n 5")
        result = self.executor._execute_command(cmd)
        lines = result.text.split('\n')
        self.assertEqual(len(lines), 5)
        self.assertEqual(lines[0], "Line 0")
        self.assertEqual(lines[4], "Line 4")

    def test_execute_tail(self):
        """Test executing tail command."""
        # Create a file with multiple lines
        self.shell.fs.write('/lines.txt', b'\n'.join(f"Line {i}".encode() for i in range(20)))

        cmd = self.parser.parse_simple("cat /lines.txt")
        result = self.executor._execute_command(cmd)
        self.shell._last_result = result

        cmd = self.parser.parse_simple("tail -n 3")
        result = self.executor._execute_command(cmd)
        lines = result.text.split('\n')
        self.assertEqual(len(lines), 3)
        self.assertEqual(lines[0], "Line 17")
        self.assertEqual(lines[2], "Line 19")

    def test_execute_sort(self):
        """Test executing sort command."""
        self.shell._last_result = CommandResult(
            data=["banana", "apple", "cherry"],
            text="banana\napple\ncherry"
        )

        cmd = self.parser.parse_simple("sort")
        result = self.executor._execute_command(cmd)
        lines = result.text.split('\n')
        self.assertEqual(lines, ["apple", "banana", "cherry"])

        # Test reverse sort
        self.shell._last_result = CommandResult(
            data=["banana", "apple", "cherry"],
            text="banana\napple\ncherry"
        )
        cmd = self.parser.parse_simple("sort -r")
        result = self.executor._execute_command(cmd)
        lines = result.text.split('\n')
        self.assertEqual(lines, ["cherry", "banana", "apple"])

    def test_execute_mkdir(self):
        """Test executing mkdir command."""
        cmd = self.parser.parse_simple("mkdir /newdir")
        result = self.executor._execute_command(cmd)

        # Check directory was created
        self.assertTrue(self.shell.fs.exists('/newdir'))
        stat = self.shell.fs.stat('/newdir')
        self.assertEqual(stat['type'], 'dir')

    def test_execute_touch(self):
        """Test executing touch command."""
        cmd = self.parser.parse_simple("touch /newfile.txt")
        result = self.executor._execute_command(cmd)

        # Check file was created
        self.assertTrue(self.shell.fs.exists('/newfile.txt'))
        content = self.shell.fs.read('/newfile.txt')
        self.assertEqual(content, b'')

    def test_execute_nonexistent_command(self):
        """Test executing nonexistent command."""
        cmd = self.parser.parse_simple("nonexistent")
        result = self.executor._execute_command(cmd)
        self.assertIn("command not found", result.text)
        self.assertEqual(result.exit_code, 127)


class TestCommandHistory(unittest.TestCase):
    """Test command history management."""

    def setUp(self):
        """Set up test fixtures."""
        self.history = CommandHistory(max_size=5)

    def test_add_command(self):
        """Test adding commands to history."""
        self.history.add("ls")
        self.history.add("cd /home")
        self.assertEqual(len(self.history.history), 2)
        self.assertEqual(self.history.history[0], "ls")
        self.assertEqual(self.history.history[1], "cd /home")

    def test_navigate_history(self):
        """Test navigating through history."""
        self.history.add("ls")
        self.history.add("cd /home")
        self.history.add("pwd")

        # Navigate backwards
        self.assertEqual(self.history.previous(), "pwd")
        self.assertEqual(self.history.previous(), "cd /home")
        self.assertEqual(self.history.previous(), "ls")
        self.assertIsNone(self.history.previous())  # At beginning

        # Navigate forward
        self.assertEqual(self.history.next(), "cd /home")
        self.assertEqual(self.history.next(), "pwd")
        self.assertEqual(self.history.next(), "")  # At end

    def test_max_size_limit(self):
        """Test history size limit."""
        for i in range(10):
            self.history.add(f"command {i}")

        self.assertEqual(len(self.history.history), 5)
        self.assertEqual(self.history.history[0], "command 5")
        self.assertEqual(self.history.history[-1], "command 9")

    def test_empty_command_not_added(self):
        """Test that empty commands are not added."""
        self.history.add("")
        self.history.add("   ")
        self.assertEqual(len(self.history.history), 0)


class TestTerminalSession(unittest.TestCase):
    """Test the terminal session."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = TerminalConfig(
            user="testuser",
            hostname="testhost",
            home_dir="/home/testuser",
            initial_dir="/"
        )
        self.session = TerminalSession(config=self.config)

        # Create some test files using the session's shell filesystem
        self.session.shell.fs.mkdir("/home")
        self.session.shell.fs.mkdir("/home/testuser")
        self.session.shell.fs.write("/test.txt", b"test content")

    def test_get_prompt(self):
        """Test prompt generation."""
        prompt = self.session.get_prompt()
        # With colors enabled, check for color codes
        self.assertIn("testuser", prompt)
        self.assertIn("testhost", prompt)
        self.assertIn("/", prompt)

        # Change directory and test again
        self.session.shell.cd("/home/testuser")
        prompt = self.session.get_prompt()
        self.assertIn("~", prompt)

    def test_execute_command(self):
        """Test executing commands."""
        output = self.session.execute_command("pwd")
        self.assertEqual(output, "/")

        output = self.session.execute_command("echo hello")
        self.assertEqual(output, "hello")

        output = self.session.execute_command("ls | grep test")
        self.assertIn("test.txt", output)

    def test_execute_exit_command(self):
        """Test exit command."""
        output = self.session.execute_command("exit")
        self.assertIsNone(output)

        output = self.session.execute_command("quit")
        self.assertIsNone(output)

    def test_run_script(self):
        """Test running a script."""
        script = [
            "cd /home",
            "pwd",
            "echo hello",
            "# This is a comment",
            "",  # Empty line
            "ls"
        ]

        outputs = self.session.run_script(script)
        self.assertEqual(outputs[0], "")  # cd produces no output
        self.assertEqual(outputs[1], "/home")
        self.assertEqual(outputs[2], "hello")
        self.assertIn("testuser", outputs[3])

    def test_environment_initialization(self):
        """Test environment initialization."""
        self.assertEqual(self.session.shell._env['USER'], "testuser")
        self.assertEqual(self.session.shell._env['HOSTNAME'], "testhost")
        self.assertEqual(self.session.shell._env['HOME'], "/home/testuser")


if __name__ == '__main__':
    unittest.main()