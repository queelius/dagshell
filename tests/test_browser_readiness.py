"""Tests for browser-readiness issues found during code review.

These tests target bugs and missing features that would break
the interactive Linux terminal tutorial running in Pyodide.
"""
import os
import inspect

from dagshell.dagshell_fluent import DagShell, CommandResult
from dagshell.command_parser import CommandParser
from dagshell.terminal import CommandExecutor, TerminalSession


def make_executor():
    """Create a fresh shell + executor pair for testing."""
    shell = DagShell()
    executor = CommandExecutor(shell)
    parser = CommandParser()
    return shell, executor, parser


def run(cmd, shell=None, executor=None, parser=None):
    """Execute a command string and return the CommandResult."""
    if shell is None:
        shell, executor, parser = make_executor()
    parsed = parser.parse(cmd)
    return executor.execute(parsed), shell


# =============================================================================
# C1: rm -r must recursively delete children
# =============================================================================

class TestRmRecursive:
    """rm -r should delete the directory AND all its children."""

    def test_rm_recursive_deletes_children(self):
        shell = DagShell()
        shell.mkdir('/rmtest')
        shell.mkdir('/rmtest/sub')
        shell.echo('hello').out('/rmtest/sub/file.txt')
        assert shell.fs.exists('/rmtest/sub/file.txt')

        shell.rm('/rmtest', recursive=True)
        assert not shell.fs.exists('/rmtest')
        assert not shell.fs.exists('/rmtest/sub')
        assert not shell.fs.exists('/rmtest/sub/file.txt')

    def test_rm_recursive_via_executor(self):
        shell, executor, parser = make_executor()
        run('mkdir /a', shell, executor, parser)
        run('mkdir /a/b', shell, executor, parser)
        run('echo content', shell, executor, parser)
        # Write a file into /a/b
        shell.echo('content').out('/a/b/file.txt')

        result, _ = run('rm -r /a', shell, executor, parser)
        assert not shell.fs.exists('/a')
        assert not shell.fs.exists('/a/b')
        assert not shell.fs.exists('/a/b/file.txt')


# =============================================================================
# C2: Failed commands must propagate exit codes
# =============================================================================

class TestExitCodePropagation:
    """Commands that fail should return non-zero exit codes."""

    def test_cd_nonexistent_returns_error(self):
        shell, executor, parser = make_executor()
        result, _ = run('cd /nonexistent_path_xyz', shell, executor, parser)
        assert result.exit_code != 0, (
            f"cd to nonexistent path should fail, got exit_code={result.exit_code}"
        )

    def test_failed_cd_blocks_and_chain(self):
        shell, executor, parser = make_executor()
        result, _ = run('cd /nonexistent_xyz && echo should_not_appear',
                        shell, executor, parser)
        assert 'should_not_appear' not in (result.text or '')


# =============================================================================
# I7: Semicolons should show all output
# =============================================================================

class TestSemicolonOutput:
    """Semicolon-separated commands should produce concatenated output."""

    def test_semicolons_show_all_output(self):
        shell, executor, parser = make_executor()
        result, _ = run('echo alpha; echo beta; echo gamma',
                        shell, executor, parser)
        assert 'alpha' in result.text
        assert 'beta' in result.text
        assert 'gamma' in result.text


# =============================================================================
# C3: readline import must be Pyodide-safe
# =============================================================================

class TestPyodideSafety:
    """Imports must not crash when readline is unavailable."""

    def test_terminal_module_does_not_require_readline(self):
        """The terminal module should gracefully handle missing readline."""
        source = inspect.getsource(inspect.getmodule(TerminalSession))
        # readline import should be wrapped in try/except
        assert 'try:' in source and 'readline' in source, (
            "readline import should be wrapped in try/except for Pyodide"
        )


# =============================================================================
# I1: Unknown flags must not crash commands
# =============================================================================

class TestUnknownFlags:
    """Commands should handle unrecognized flags gracefully."""

    def test_ls_with_unknown_flag(self):
        """ls -h should not crash."""
        shell, executor, parser = make_executor()
        try:
            result, _ = run('ls -h /', shell, executor, parser)
            # Should succeed (ignoring the flag) or return an error,
            # but NOT raise an exception
            assert isinstance(result, CommandResult)
        except TypeError:
            raise AssertionError("ls -h crashed with TypeError")

    def test_echo_with_unknown_flag(self):
        """echo -e should not crash."""
        shell, executor, parser = make_executor()
        try:
            result, _ = run('echo -e hello', shell, executor, parser)
            assert isinstance(result, CommandResult)
        except TypeError:
            raise AssertionError("echo -e crashed with TypeError")


# =============================================================================
# I5: Tilde and $VAR expansion
# =============================================================================

class TestVariableExpansion:
    """Shell should expand ~ and $VARIABLE references."""

    def test_cd_tilde_goes_home(self):
        shell, executor, parser = make_executor()
        run('cd /', shell, executor, parser)
        result, _ = run('cd ~', shell, executor, parser)
        # Should go to HOME, not /~
        assert shell._cwd != '/~'
        home = shell._env.get('HOME', '/home/user')
        assert shell._cwd == home

    def test_echo_expands_variable(self):
        shell, executor, parser = make_executor()
        shell.setenv('GREETING', 'hello_world')
        result, _ = run('echo $GREETING', shell, executor, parser)
        assert 'hello_world' in result.text


# =============================================================================
# I2: tree command
# =============================================================================

class TestTreeCommand:
    """tree should display directory structure with ASCII art."""

    def test_tree_shows_directory_contents(self):
        shell = DagShell()
        shell.mkdir('/project')
        shell.mkdir('/project/src')
        shell.touch('/project/src/main.py')
        shell.touch('/project/README.md')

        result = shell.tree('/project')
        assert isinstance(result, CommandResult)
        assert 'src' in result.text
        assert 'main.py' in result.text
        assert 'README.md' in result.text

    def test_tree_via_executor(self):
        shell, executor, parser = make_executor()
        run('mkdir /proj', shell, executor, parser)
        run('mkdir /proj/lib', shell, executor, parser)
        shell.touch('/proj/lib/util.py')

        result, _ = run('tree /proj', shell, executor, parser)
        assert 'lib' in result.text
        assert 'util.py' in result.text


# =============================================================================
# C4: find -name must work
# =============================================================================

class TestFindCommand:
    """find -name pattern should find matching files."""

    def test_find_name_pattern(self):
        shell, executor, parser = make_executor()
        shell.touch('/a.txt')
        shell.mkdir('/sub')
        shell.touch('/sub/b.txt')
        shell.touch('/sub/c.py')

        result, _ = run('find / -name "*.txt"', shell, executor, parser)
        assert 'a.txt' in result.text
        assert 'b.txt' in result.text
        assert 'c.py' not in result.text

    def test_find_type_directory(self):
        shell, executor, parser = make_executor()
        shell.mkdir('/mydir')
        shell.touch('/myfile')

        result, _ = run('find / -type d', shell, executor, parser)
        assert 'mydir' in result.text


# =============================================================================
# I3: export should set env vars
# =============================================================================

class TestExportCommand:
    """export VAR=value should set environment variables."""

    def test_export_sets_env_var(self):
        shell, executor, parser = make_executor()
        result, _ = run('export FOO=bar', shell, executor, parser)
        assert shell._env.get('FOO') == 'bar'

    def test_export_var_usable_in_echo(self):
        shell, executor, parser = make_executor()
        run('export GREETING=hello', shell, executor, parser)
        result, _ = run('echo $GREETING', shell, executor, parser)
        assert 'hello' in result.text


# =============================================================================
# I8: wc should show lines/words/bytes by default
# =============================================================================

class TestWcDefaults:
    """wc with no flags should show lines, words, and bytes."""

    def test_wc_default_shows_all_counts(self):
        shell = DagShell()
        shell.echo('hello world\nfoo bar baz').out('/test.txt')
        result = shell.wc('/test.txt')
        text = result.text
        # Should contain line count, word count, and byte/char count
        # Real wc: "  2  5  25 test.txt"
        parts = text.split()
        # At minimum should have 3 numeric values
        nums = [p for p in parts if p.isdigit()]
        assert len(nums) >= 3, (
            f"wc should show lines/words/bytes, got: {text}"
        )


# =============================================================================
# S1: cd - (previous directory)
# =============================================================================

class TestCdPrevious:
    """cd - should return to the previous directory."""

    def test_cd_dash_returns_to_previous(self):
        shell = DagShell()
        shell.mkdir('/aaa')
        shell.mkdir('/bbb')
        shell.cd('/aaa')
        shell.cd('/bbb')
        assert shell._cwd == '/bbb'

        shell.cd('-')
        assert shell._cwd == '/aaa'
