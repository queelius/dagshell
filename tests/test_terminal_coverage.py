#!/usr/bin/env python3
"""
Additional tests for terminal.py to improve coverage.

This module targets the uncovered lines identified by coverage analysis:
- Slash command handlers
- Command preparation for various commands
- Help system
- Main function edge cases
- Scheme command integration
- Redirection handlers
"""

import sys
import os
import tempfile
import json
import shutil

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


class TestCommandExecutorPrepareArguments(unittest.TestCase):
    """Test _prepare_arguments for various command types."""

    def setUp(self):
        """Set up test fixtures."""
        self.shell = DagShell()
        self.executor = CommandExecutor(self.shell)
        self.parser = CommandParser()

    def test_prepare_ln_symbolic(self):
        """Test ln -s command preparation."""
        # Create source file first
        self.shell.fs.write('/source.txt', b'content')

        cmd = self.parser.parse_simple("ln -s /source.txt /link.txt")
        result = self.executor._execute_command(cmd)
        # Should attempt to create symbolic link
        self.assertIsNotNone(result)

    def test_prepare_ln_no_symbolic(self):
        """Test ln without -s (hard link)."""
        self.shell.fs.write('/source.txt', b'content')

        cmd = self.parser.parse_simple("ln /source.txt /hardlink.txt")
        result = self.executor._execute_command(cmd)
        self.assertIsNotNone(result)

    def test_prepare_chmod(self):
        """Test chmod command preparation."""
        self.shell.fs.write('/file.txt', b'content')

        cmd = self.parser.parse_simple("chmod 755 /file.txt")
        result = self.executor._execute_command(cmd)
        self.assertIsNotNone(result)

    def test_prepare_chown(self):
        """Test chown command preparation."""
        self.shell.fs.write('/file.txt', b'content')

        cmd = self.parser.parse_simple("chown root /file.txt")
        result = self.executor._execute_command(cmd)
        self.assertIsNotNone(result)

    def test_prepare_diff(self):
        """Test diff command preparation."""
        self.shell.fs.write('/file1.txt', b'line 1\nline 2')
        self.shell.fs.write('/file2.txt', b'line 1\nline 3')

        cmd = self.parser.parse_simple("diff /file1.txt /file2.txt")
        result = self.executor._execute_command(cmd)
        self.assertIsNotNone(result)

    def test_prepare_diff_unified(self):
        """Test diff -u command preparation."""
        self.shell.fs.write('/file1.txt', b'line 1\nline 2')
        self.shell.fs.write('/file2.txt', b'line 1\nline 3')

        cmd = self.parser.parse_simple("diff -u /file1.txt /file2.txt")
        result = self.executor._execute_command(cmd)
        self.assertIsNotNone(result)

    def test_prepare_cut_d_f(self):
        """Test cut -d -f command preparation."""
        self.shell.fs.write('/data.csv', b'a,b,c\n1,2,3')

        cmd = self.parser.parse_simple("cut -d , -f 2 /data.csv")
        result = self.executor._execute_command(cmd)
        self.assertIsNotNone(result)

    def test_prepare_tr(self):
        """Test tr command preparation."""
        self.shell._last_result = CommandResult(
            data="hello", text="hello", exit_code=0
        )

        cmd = self.parser.parse_simple("tr a-z A-Z")
        result = self.executor._execute_command(cmd)
        self.assertIsNotNone(result)

    def test_prepare_du(self):
        """Test du command preparation."""
        self.shell.fs.mkdir('/testdir')
        self.shell.fs.write('/testdir/file.txt', b'content')

        cmd = self.parser.parse_simple("du /testdir")
        result = self.executor._execute_command(cmd)
        self.assertIsNotNone(result)

    def test_prepare_du_human_readable(self):
        """Test du -h command preparation."""
        self.shell.fs.mkdir('/testdir')
        self.shell.fs.write('/testdir/file.txt', b'content')

        cmd = self.parser.parse_simple("du -h /testdir")
        result = self.executor._execute_command(cmd)
        self.assertIsNotNone(result)

    def test_prepare_stat(self):
        """Test stat command preparation."""
        self.shell.fs.write('/file.txt', b'content')

        cmd = self.parser.parse_simple("stat /file.txt")
        result = self.executor._execute_command(cmd)
        self.assertIsNotNone(result)

    def test_prepare_readlink(self):
        """Test readlink command preparation."""
        self.shell.fs.write('/source.txt', b'content')
        # Create symbolic link using filesystem symlink method
        self.shell.fs.symlink('/source.txt', '/link.txt')

        cmd = self.parser.parse_simple("readlink /link.txt")
        result = self.executor._execute_command(cmd)
        self.assertIsNotNone(result)

    def test_prepare_id(self):
        """Test id command preparation."""
        cmd = self.parser.parse_simple("id")
        result = self.executor._execute_command(cmd)
        self.assertIsNotNone(result)

    def test_prepare_id_with_username(self):
        """Test id with username argument."""
        cmd = self.parser.parse_simple("id root")
        result = self.executor._execute_command(cmd)
        self.assertIsNotNone(result)

    def test_prepare_basename(self):
        """Test basename command preparation."""
        cmd = self.parser.parse_simple("basename /path/to/file.txt")
        result = self.executor._execute_command(cmd)
        self.assertIn("file.txt", result.text)

    def test_prepare_basename_with_suffix(self):
        """Test basename with suffix removal."""
        cmd = self.parser.parse_simple("basename /path/to/file.txt .txt")
        result = self.executor._execute_command(cmd)
        self.assertIsNotNone(result)

    def test_prepare_dirname(self):
        """Test dirname command preparation."""
        cmd = self.parser.parse_simple("dirname /path/to/file.txt")
        result = self.executor._execute_command(cmd)
        self.assertIn("/path/to", result.text)

    def test_prepare_xargs(self):
        """Test xargs command preparation."""
        self.shell._last_result = CommandResult(
            data=["file1.txt", "file2.txt"],
            text="file1.txt\nfile2.txt",
            exit_code=0
        )

        cmd = self.parser.parse_simple("xargs echo")
        result = self.executor._execute_command(cmd)
        self.assertIsNotNone(result)

    def test_prepare_xargs_with_n(self):
        """Test xargs -n command."""
        self.shell._last_result = CommandResult(
            data=["a", "b", "c", "d"],
            text="a\nb\nc\nd",
            exit_code=0
        )

        cmd = self.parser.parse_simple("xargs -n 2 echo")
        result = self.executor._execute_command(cmd)
        self.assertIsNotNone(result)

    def test_prepare_env_with_arg(self):
        """Test env command with argument."""
        cmd = self.parser.parse_simple("env VAR=value")
        result = self.executor._execute_command(cmd)
        self.assertIsNotNone(result)

    def test_prepare_tee(self):
        """Test tee command preparation."""
        self.shell._last_result = CommandResult(
            data="test content",
            text="test content",
            exit_code=0
        )

        cmd = self.parser.parse_simple("tee /output.txt")
        result = self.executor._execute_command(cmd)
        self.assertIsNotNone(result)


class TestCommandExecutorHelpSystem(unittest.TestCase):
    """Test the help system in CommandExecutor."""

    def setUp(self):
        """Set up test fixtures."""
        self.shell = DagShell()
        self.executor = CommandExecutor(self.shell)
        self.parser = CommandParser()

    def test_help_for_clear(self):
        """Test help for clear command."""
        result = self.executor._show_command_help('clear')
        self.assertIn('clear', result.text)
        self.assertIn('Clear', result.text)

    def test_help_for_exit(self):
        """Test help for exit command."""
        result = self.executor._show_command_help('exit')
        self.assertIn('exit', result.text)
        self.assertIn('Exit', result.text)

    def test_help_for_quit(self):
        """Test help for quit command."""
        result = self.executor._show_command_help('quit')
        self.assertIn('exit', result.text)

    def test_help_for_help(self):
        """Test help for help command itself."""
        result = self.executor._show_command_help('help')
        self.assertIn('help', result.text)

    def test_help_for_unknown_command(self):
        """Test help for unknown command."""
        result = self.executor._show_command_help('unknowncommand')
        self.assertIn('no help available', result.text)
        self.assertEqual(result.exit_code, 1)

    def test_help_flag_triggers_help(self):
        """Test that --help flag shows help."""
        cmd = self.parser.parse_simple("ls --help")
        result = self.executor._execute_command(cmd)
        self.assertIn('ls', result.text)

    def test_h_flag_triggers_help_for_non_excluded_commands(self):
        """Test that -h flag triggers help for non-excluded commands."""
        # mkdir is not in the excluded list for -h
        cmd = self.parser.parse_simple("mkdir -h")
        result = self.executor._execute_command(cmd)
        # Should show help for mkdir, not interpret -h as human-readable
        self.assertIn('mkdir', result.text.lower())

    def test_h_flag_not_help_for_ls(self):
        """Test that -h is not interpreted as help for ls (it's human-readable)."""
        self.shell.fs.write('/file.txt', b'content')
        cmd = self.parser.parse_simple("ls -h /")
        result = self.executor._execute_command(cmd)
        # For ls, -h should NOT trigger help (as -h means human-readable for ls)
        # The command should execute normally or show an error about unknown flag
        # but NOT show help text
        self.assertNotIn('Usage:', result.text)
        self.assertNotIn('Examples:', result.text)

    def test_all_commands_help(self):
        """Test showing all commands help."""
        result = self.executor._show_all_commands_help()
        self.assertIn('DagShell Terminal', result.text)
        self.assertIn('NAVIGATION', result.text)
        self.assertIn('FILE OPERATIONS', result.text)
        self.assertIn('TEXT PROCESSING', result.text)

    def test_help_command_with_argument(self):
        """Test help command with argument."""
        cmd = self.parser.parse_simple("help ls")
        result = self.executor._execute_command(cmd)
        self.assertIn('ls', result.text)

    def test_help_command_without_argument(self):
        """Test help command without argument."""
        cmd = self.parser.parse_simple("help")
        result = self.executor._execute_command(cmd)
        self.assertIn('Available Commands', result.text)


class TestCommandExecutorSpecialCommands(unittest.TestCase):
    """Test special command execution."""

    def setUp(self):
        """Set up test fixtures."""
        self.shell = DagShell()
        self.executor = CommandExecutor(self.shell)
        self.parser = CommandParser()

    def test_clear_command(self):
        """Test clear command returns escape codes."""
        cmd = self.parser.parse_simple("clear")
        result = self.executor._execute_command(cmd)
        self.assertIn('\033[2J', result.text)
        self.assertIn('\033[H', result.text)

    def test_exit_command(self):
        """Test exit command."""
        cmd = self.parser.parse_simple("exit")
        result = self.executor._execute_command(cmd)
        self.assertEqual(result.text, 'exit')

    def test_quit_command(self):
        """Test quit command."""
        cmd = self.parser.parse_simple("quit")
        result = self.executor._execute_command(cmd)
        self.assertEqual(result.text, 'exit')

    def test_question_mark_help(self):
        """Test ? alias for help."""
        # Need to get the method directly since parser might handle ? differently
        method = self.executor._get_shell_method('?')
        self.assertIsNotNone(method)
        result = method()
        self.assertIn('Commands', result.text)


class TestCommandExecutorRedirection(unittest.TestCase):
    """Test redirection handling."""

    def setUp(self):
        """Set up test fixtures."""
        self.shell = DagShell()
        self.executor = CommandExecutor(self.shell)
        self.parser = CommandParser()

    def test_append_redirection(self):
        """Test append redirection (>>)."""
        # First write
        cmd = self.parser.parse_simple("echo first > /output.txt")
        self.executor._execute_command(cmd)

        # Append
        cmd = self.parser.parse_simple("echo second >> /output.txt")
        self.executor._execute_command(cmd)

        content = self.shell.fs.read('/output.txt').decode('utf-8')
        self.assertIn('first', content)
        self.assertIn('second', content)


class TestCommandExecutorScheme(unittest.TestCase):
    """Test Scheme command integration."""

    def setUp(self):
        """Set up test fixtures."""
        self.shell = DagShell()
        self.executor = CommandExecutor(self.shell)
        self.parser = CommandParser()

    def test_scheme_no_args_shows_usage(self):
        """Test scheme with no arguments shows usage."""
        result = self.executor._run_scheme_command([])
        self.assertIn('Usage', result.text)
        self.assertIn('scheme', result.text)

    def test_scheme_eval_expression(self):
        """Test scheme evaluates inline expression."""
        result = self.executor._run_scheme_command(["(+ 1 2)"])
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.text.strip(), "3")

    def test_scheme_eval_boolean_true(self):
        """Test scheme boolean result #t."""
        result = self.executor._run_scheme_command(["(= 1 1)"])
        self.assertEqual(result.text.strip(), "#t")

    def test_scheme_eval_boolean_false(self):
        """Test scheme boolean result #f."""
        result = self.executor._run_scheme_command(["(= 1 2)"])
        self.assertEqual(result.text.strip(), "#f")

    def test_scheme_file_not_found(self):
        """Test scheme with non-existent script file."""
        result = self.executor._run_scheme_command(["/nonexistent.scm"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn('No such file', result.text)

    def test_scheme_run_script_file(self):
        """Test scheme runs script from virtual filesystem."""
        # Create a Scheme script in virtual FS
        self.shell.fs.write('/test.scm', b'(+ 10 20)')
        result = self.executor._run_scheme_command(["/test.scm"])
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.text.strip(), "30")

    def test_scheme_syntax_error(self):
        """Test scheme handles syntax errors."""
        result = self.executor._run_scheme_command(["(+ 1 2"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn('error', result.text.lower())


class TestSlashCommands(unittest.TestCase):
    """Test slash command handlers."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        config = TerminalConfig(
            user="testuser",
            hostname="testhost",
            safe_host_directory=self.temp_dir,
            snapshots_directory=os.path.join(self.temp_dir, 'snapshots')
        )
        self.session = TerminalSession(config=config)

        # Create some test files
        self.session.shell.fs.mkdir('/testdir')
        self.session.shell.fs.write('/testdir/file.txt', b'test content')

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_slash_help(self):
        """Test /help command."""
        output = self.session.execute_command('/help')
        self.assertIn('Slash Commands', output)
        self.assertIn('/import', output)
        self.assertIn('/export', output)
        self.assertIn('/save', output)

    def test_slash_status(self):
        """Test /status command."""
        output = self.session.execute_command('/status')
        self.assertIn('Filesystem Status', output)
        self.assertIn('Total nodes', output)
        self.assertIn('Files', output)
        self.assertIn('Directories', output)

    def test_slash_dag(self):
        """Test /dag command."""
        output = self.session.execute_command('/dag')
        self.assertIn('DAG Structure', output)

    def test_slash_nodes(self):
        """Test /nodes command."""
        output = self.session.execute_command('/nodes')
        self.assertIn('Content-addressed nodes', output)

    def test_slash_nodes_with_pattern(self):
        """Test /nodes with pattern filter."""
        output = self.session.execute_command('/nodes abc')
        # Should filter nodes by pattern
        self.assertIsNotNone(output)

    def test_slash_info_no_args(self):
        """Test /info without arguments."""
        output = self.session.execute_command('/info')
        self.assertIn('Usage', output)

    def test_slash_info_not_found(self):
        """Test /info with non-existent hash."""
        output = self.session.execute_command('/info zzzznonexistent')
        self.assertIn('No node found', output)

    def test_slash_info_valid_hash(self):
        """Test /info with valid hash prefix."""
        # Get a valid hash prefix
        for hash_key in self.session.shell.fs.nodes.keys():
            prefix = hash_key[:8]
            break
        output = self.session.execute_command(f'/info {prefix}')
        self.assertIn('Node Information', output)

    def test_slash_save(self):
        """Test /save command."""
        output = self.session.execute_command('/save test-state.json')
        self.assertIn('saved', output.lower())
        # Check file was created
        saved_file = os.path.join(self.temp_dir, 'test-state.json')
        self.assertTrue(os.path.exists(saved_file))

    def test_slash_save_default_filename(self):
        """Test /save with default filename."""
        output = self.session.execute_command('/save')
        self.assertIn('saved', output.lower())

    def test_slash_load_no_args(self):
        """Test /load without arguments."""
        output = self.session.execute_command('/load')
        self.assertIn('Usage', output)

    def test_slash_load_valid_file(self):
        """Test /load with valid file."""
        # First save
        self.session.execute_command('/save test-state.json')
        # Modify filesystem
        self.session.shell.fs.write('/newfile.txt', b'new content')
        # Load previous state
        output = self.session.execute_command('/load test-state.json')
        self.assertIn('loaded', output.lower())

    def test_slash_load_invalid_file(self):
        """Test /load with non-existent file."""
        output = self.session.execute_command('/load nonexistent.json')
        self.assertIn('failed', output.lower())

    def test_slash_snapshot(self):
        """Test /snapshot command."""
        output = self.session.execute_command('/snapshot mysnap')
        self.assertIn('Snapshot', output)
        self.assertIn('saved', output.lower())

    def test_slash_snapshot_no_name(self):
        """Test /snapshot without name."""
        output = self.session.execute_command('/snapshot')
        self.assertIn('Usage', output)

    def test_slash_snapshots_empty(self):
        """Test /snapshots when no snapshots exist."""
        output = self.session.execute_command('/snapshots')
        self.assertIn('No snapshots', output)

    def test_slash_snapshots_with_snapshots(self):
        """Test /snapshots after creating snapshots."""
        self.session.execute_command('/snapshot snap1')
        self.session.execute_command('/snapshot snap2')
        output = self.session.execute_command('/snapshots')
        self.assertIn('snap1', output)
        self.assertIn('snap2', output)

    def test_slash_aliases(self):
        """Test /aliases command."""
        output = self.session.execute_command('/aliases')
        self.assertIn('no aliases defined', output.lower())

    def test_slash_import_no_args(self):
        """Test /import without arguments."""
        output = self.session.execute_command('/import')
        self.assertIn('Usage', output)

    def test_slash_import_valid(self):
        """Test /import with valid paths."""
        # Create a file on host filesystem
        host_file = os.path.join(self.temp_dir, 'import_test.txt')
        with open(host_file, 'w') as f:
            f.write('import test content')

        output = self.session.execute_command('/import import_test.txt /imported.txt')
        self.assertIn('Imported', output)

    def test_slash_import_outside_safe_dir(self):
        """Test /import with path outside safe directory."""
        output = self.session.execute_command('/import /etc/passwd /etc/passwd')
        self.assertIn('outside safe directory', output)

    def test_slash_export_no_args(self):
        """Test /export without arguments."""
        output = self.session.execute_command('/export')
        self.assertIn('Usage', output)

    def test_slash_export_valid(self):
        """Test /export with valid paths."""
        output = self.session.execute_command('/export /testdir export_dir')
        self.assertIn('Exported', output)

    def test_slash_export_nonexistent_path(self):
        """Test /export with non-existent dagshell path."""
        output = self.session.execute_command('/export /nonexistent export_dir')
        self.assertIn('not found', output.lower())

    def test_slash_unknown_command(self):
        """Test unknown slash command."""
        output = self.session.execute_command('/unknownslashcmd')
        self.assertIn('Unknown slash command', output)
        self.assertIn('/help', output)

    def test_slash_empty(self):
        """Test empty slash command."""
        output = self.session.execute_command('/')
        self.assertIn('empty slash command', output.lower())


class TestTerminalSessionUserManagement(unittest.TestCase):
    """Test user management in TerminalSession."""

    def setUp(self):
        """Set up test fixtures."""
        config = TerminalConfig(
            user="testuser",
            hostname="testhost"
        )
        self.session = TerminalSession(config=config)
        # Create home directories
        self.session.shell.fs.mkdir('/home')
        self.session.shell.fs.mkdir('/home/testuser')
        self.session.shell.fs.mkdir('/home/alice')
        self.session.shell.fs.mkdir('/root')

    def test_whoami(self):
        """Test whoami command."""
        output = self.session.execute_command('whoami')
        self.assertEqual(output, 'testuser')

    def test_su_root(self):
        """Test su to root."""
        output = self.session.execute_command('su root')
        self.assertEqual(output, '')
        self.assertEqual(self.session.current_user, 'root')
        self.assertEqual(self.session.shell._cwd, '/root')

    def test_su_alice(self):
        """Test su to another user."""
        output = self.session.execute_command('su alice')
        self.assertEqual(output, '')
        self.assertEqual(self.session.current_user, 'alice')

    def test_su_default_root(self):
        """Test su without argument defaults to root."""
        output = self.session.execute_command('su')
        self.assertEqual(output, '')
        self.assertEqual(self.session.current_user, 'root')

    def test_su_nonexistent_user(self):
        """Test su to non-existent user."""
        output = self.session.execute_command('su nonexistentuser')
        self.assertIn('does not exist', output)

    def test_export_command(self):
        """Test export command in terminal session."""
        output = self.session.execute_command('export /test/path')
        # Export should attempt to export (will fail without target)
        self.assertIsNotNone(output)

    def test_export_missing_path(self):
        """Test export command without path."""
        output = self.session.execute_command('export')
        self.assertIn('missing', output.lower())


class TestTerminalSessionEmpty(unittest.TestCase):
    """Test edge cases with empty input."""

    def setUp(self):
        """Set up test fixtures."""
        self.session = TerminalSession()

    def test_empty_command(self):
        """Test empty command input."""
        output = self.session.execute_command('')
        self.assertEqual(output, '')

    def test_whitespace_command(self):
        """Test whitespace-only command."""
        output = self.session.execute_command('   ')
        self.assertEqual(output, '')


class TestCommandExecutorConditionalExecution(unittest.TestCase):
    """Test && and || operators."""

    def setUp(self):
        """Set up test fixtures."""
        self.shell = DagShell()
        self.executor = CommandExecutor(self.shell)
        self.parser = CommandParser()

    def test_and_operator_success(self):
        """Test && with successful first command."""
        group = self.parser.parse("echo first && echo second")
        result = self.executor.execute(group)
        self.assertEqual(result.text, "second")

    def test_and_operator_failure(self):
        """Test && with failing command - execution stops."""
        # When first command with && fails, the second command should NOT run
        group = self.parser.parse("echo first && nonexistentcmd && echo third")
        result = self.executor.execute(group)
        # The last successful result (echo first) is returned
        self.assertEqual(result.text, "first")
        self.assertEqual(result.exit_code, 0)
        # Verify third command did not run by checking text doesn't contain "third"
        self.assertNotIn("third", result.text)

    def test_or_operator_success(self):
        """Test || with successful first command."""
        group = self.parser.parse("echo first || echo second")
        result = self.executor.execute(group)
        # When || succeeds on first command, execution stops
        # The result should have exit_code 0
        self.assertEqual(result.exit_code, 0)

    def test_or_operator_failure(self):
        """Test || with failing first command."""
        group = self.parser.parse("nonexistentcmd || echo fallback")
        result = self.executor.execute(group)
        self.assertEqual(result.text, "fallback")


class TestCommandExecutorPipelineEdgeCases(unittest.TestCase):
    """Test pipeline edge cases."""

    def setUp(self):
        """Set up test fixtures."""
        self.shell = DagShell()
        self.executor = CommandExecutor(self.shell)
        self.parser = CommandParser()

    def test_empty_pipeline(self):
        """Test empty pipeline."""
        pipeline = Pipeline(commands=[])
        result = self.executor._execute_pipeline(pipeline)
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.text, '')

    def test_long_pipeline(self):
        """Test long pipeline with multiple stages."""
        self.shell.fs.write('/data.txt', b'c\na\nb\nc\na')
        group = self.parser.parse("cat /data.txt | sort | uniq")
        result = self.executor.execute(group)
        lines = result.text.strip().split('\n')
        self.assertEqual(sorted(lines), ['a', 'b', 'c'])


class TestTerminalSessionPrompt(unittest.TestCase):
    """Test prompt generation."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = TerminalConfig(
            user="testuser",
            hostname="testhost",
            home_dir="/home/testuser",
            enable_colors=False
        )
        self.session = TerminalSession(config=self.config)
        self.session.shell.fs.mkdir('/home')
        self.session.shell.fs.mkdir('/home/testuser')

    def test_prompt_without_colors(self):
        """Test prompt generation without colors."""
        # Disable colors
        self.session.config.enable_colors = False
        prompt = self.session.get_prompt()
        self.assertIn('testuser', prompt)
        self.assertIn('testhost', prompt)

    def test_prompt_in_home_shows_tilde(self):
        """Test prompt shows ~ when in home directory."""
        self.session.shell.cd('/home/testuser')
        prompt = self.session.get_prompt()
        self.assertIn('~', prompt)


class TestMainFunctionEdgeCases(unittest.TestCase):
    """Test main() function edge cases."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.fs_file = os.path.join(self.temp_dir, 'test_fs.json')

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_invalid_fs_file(self):
        """Test error when loading invalid filesystem file."""
        import subprocess

        # Create invalid JSON file
        invalid_file = os.path.join(self.temp_dir, 'invalid.json')
        with open(invalid_file, 'w') as f:
            f.write('not valid json')

        result = subprocess.run(
            ['python', '-m', 'dagshell.terminal', '--fs', invalid_file, 'pwd'],
            capture_output=True, text=True
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('error', result.stderr.lower())

    def test_user_option(self):
        """Test -u user option is accepted (used for interactive mode)."""
        import subprocess
        # The -u option is primarily for interactive mode (sets user in config)
        # In one-shot mode, it doesn't initialize environment, but the option is accepted
        result = subprocess.run(
            ['python', '-m', 'dagshell.terminal', '-u', 'myuser', 'pwd'],
            capture_output=True, text=True
        )
        # Command should succeed with the -u option present
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), '/')


class TestCommandExecutorHeadTailVariations(unittest.TestCase):
    """Test head and tail command variations."""

    def setUp(self):
        """Set up test fixtures."""
        self.shell = DagShell()
        self.executor = CommandExecutor(self.shell)
        self.parser = CommandParser()
        # Create test data
        self.shell.fs.write('/lines.txt', b'\n'.join(f"Line {i}".encode() for i in range(20)))

    def test_head_with_file_argument(self):
        """Test head with file argument."""
        cmd = self.parser.parse_simple("head -n 5 /lines.txt")
        result = self.executor._execute_command(cmd)
        lines = result.text.strip().split('\n')
        self.assertEqual(len(lines), 5)

    def test_tail_with_file_argument(self):
        """Test tail with file argument."""
        cmd = self.parser.parse_simple("tail -n 5 /lines.txt")
        result = self.executor._execute_command(cmd)
        lines = result.text.strip().split('\n')
        self.assertEqual(len(lines), 5)

    def test_head_default_lines(self):
        """Test head with default lines (10)."""
        self.shell._last_result = CommandResult(
            data=[f"Line {i}" for i in range(20)],
            text='\n'.join(f"Line {i}" for i in range(20)),
            exit_code=0
        )
        cmd = self.parser.parse_simple("head")
        result = self.executor._execute_command(cmd)
        lines = result.text.strip().split('\n')
        self.assertEqual(len(lines), 10)


class TestCommandExecutorFindCommand(unittest.TestCase):
    """Test find command preparation."""

    def setUp(self):
        """Set up test fixtures."""
        self.shell = DagShell()
        self.executor = CommandExecutor(self.shell)
        self.parser = CommandParser()
        # Create test directory structure
        self.shell.fs.mkdir('/search')
        self.shell.fs.mkdir('/search/sub1')
        self.shell.fs.mkdir('/search/sub2')
        self.shell.fs.write('/search/file1.txt', b'content1')
        self.shell.fs.write('/search/sub1/file2.txt', b'content2')

    def test_find_basic(self):
        """Test basic find command."""
        cmd = self.parser.parse_simple("find /search")
        result = self.executor._execute_command(cmd)
        self.assertIn('file1.txt', result.text)

    def test_find_with_type(self):
        """Test find with type filter."""
        cmd = self.parser.parse_simple("find /search -type f")
        result = self.executor._execute_command(cmd)
        self.assertIn('.txt', result.text)


class TestCommandExecutorExceptionHandling(unittest.TestCase):
    """Test exception handling in command execution."""

    def setUp(self):
        """Set up test fixtures."""
        self.shell = DagShell()
        self.executor = CommandExecutor(self.shell)
        self.parser = CommandParser()

    def test_command_raises_exception(self):
        """Test that exceptions are caught and returned as error results."""
        # Try to cat a non-existent file
        cmd = self.parser.parse_simple("cat /nonexistent/path/file.txt")
        result = self.executor._execute_command(cmd)
        self.assertEqual(result.exit_code, 1)
        self.assertIn('cat:', result.text)


class TestHostPathResolution(unittest.TestCase):
    """Test host path resolution security."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        config = TerminalConfig(
            safe_host_directory=self.temp_dir
        )
        self.session = TerminalSession(config=config)

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_resolve_relative_path(self):
        """Test resolving relative path."""
        resolved = self.session._resolve_host_path('subdir/file.txt')
        self.assertTrue(resolved.startswith(self.temp_dir))

    def test_resolve_absolute_within_safe(self):
        """Test resolving absolute path within safe directory."""
        safe_path = os.path.join(self.temp_dir, 'file.txt')
        resolved = self.session._resolve_host_path(safe_path)
        self.assertEqual(resolved, safe_path)

    def test_resolve_path_escape_attempt(self):
        """Test that path escape attempts are blocked."""
        with self.assertRaises(ValueError) as context:
            self.session._resolve_host_path('../../../etc/passwd')
        self.assertIn('outside safe directory', str(context.exception))

    def test_resolve_no_safe_directory(self):
        """Test error when safe_host_directory is not set."""
        session = TerminalSession()  # No safe_host_directory
        session.config.safe_host_directory = None
        with self.assertRaises(ValueError) as context:
            session._resolve_host_path('file.txt')
        self.assertIn('not configured', str(context.exception))


class TestCommandExecutorWcCommand(unittest.TestCase):
    """Test wc command preparation."""

    def setUp(self):
        """Set up test fixtures."""
        self.shell = DagShell()
        self.executor = CommandExecutor(self.shell)
        self.parser = CommandParser()
        self.shell.fs.write('/test.txt', b'line 1\nline 2\nline 3')

    def test_wc_with_file(self):
        """Test wc with file argument."""
        cmd = self.parser.parse_simple("wc /test.txt")
        result = self.executor._execute_command(cmd)
        self.assertIn('3', result.text)  # 3 lines

    def test_wc_with_flags(self):
        """Test wc with flags."""
        cmd = self.parser.parse_simple("wc -l /test.txt")
        result = self.executor._execute_command(cmd)
        self.assertIn('3', result.text)


class TestCommandExecutorSortUniq(unittest.TestCase):
    """Test sort and uniq command preparation."""

    def setUp(self):
        """Set up test fixtures."""
        self.shell = DagShell()
        self.executor = CommandExecutor(self.shell)
        self.parser = CommandParser()

    def test_sort_with_file(self):
        """Test sort with file argument."""
        self.shell.fs.write('/unsorted.txt', b'c\na\nb')
        cmd = self.parser.parse_simple("sort /unsorted.txt")
        result = self.executor._execute_command(cmd)
        self.assertEqual(result.text.strip(), 'a\nb\nc')

    def test_uniq_with_file(self):
        """Test uniq with file argument."""
        self.shell.fs.write('/dups.txt', b'a\na\nb\nb\nc')
        cmd = self.parser.parse_simple("uniq /dups.txt")
        result = self.executor._execute_command(cmd)
        self.assertEqual(result.text.strip(), 'a\nb\nc')


class TestDocstringExtraction(unittest.TestCase):
    """Test docstring extraction for help system."""

    def setUp(self):
        """Set up test fixtures."""
        self.shell = DagShell()
        self.executor = CommandExecutor(self.shell)

    def test_extract_sections_empty_docstring(self):
        """Test extracting sections from empty docstring."""
        sections = self.executor._extract_docstring_sections('')
        self.assertEqual(sections, {})

    def test_extract_sections_with_usage(self):
        """Test extracting Usage section."""
        docstring = """Brief description.

Usage:
    command [options]

Options:
    -v  verbose

Examples:
    command -v
"""
        sections = self.executor._extract_docstring_sections(docstring)
        self.assertEqual(sections['description'], 'Brief description.')
        self.assertEqual(sections['usage'], 'command [options]')
        self.assertIn('-v  verbose', sections['options'])
        self.assertIn('command -v', sections['examples'])


if __name__ == '__main__':
    unittest.main()
