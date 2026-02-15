"""Tests for issues found during code review.

Each test targets a specific bug or issue identified in the comprehensive
code review. Tests are grouped by module and severity.
"""
import copy
import inspect
import json
import os
import re
import tempfile

import dagshell
from dagshell.dagshell import FileSystem, FileNode, DirNode, DeviceNode, SymlinkNode, Mode
from dagshell.dagshell_fluent import DagShell, CommandResult
from dagshell.terminal import TerminalSession, CommandExecutor


# =============================================================================
# CRITICAL #1: Duplicate method definitions in dagshell_fluent.py
# The second definition of save() lacks error handling (no try/except).
# =============================================================================

class TestDuplicateMethodDefinitions:
    """Verify save/load/commit have proper error handling."""

    def test_save_returns_error_on_write_failure(self):
        """save() should return exit_code=1 when the file cannot be written."""
        shell = DagShell()
        result = shell.save('/nonexistent_dir_xyz/impossible.json')
        assert result.exit_code == 1
        assert 'Failed to save' in result.text or 'save' in result.text.lower()

    def test_load_returns_error_on_missing_file(self):
        """load() should return exit_code=1 when file doesn't exist."""
        shell = DagShell()
        result = shell.load('/nonexistent_file_xyz.json')
        assert result.exit_code == 1

    def test_commit_delegates_to_save(self):
        """commit() should delegate to save() and return same result."""
        shell = DagShell()
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            tmpfile = f.name
        try:
            result = shell.commit(tmpfile)
            assert result.exit_code == 0
            with open(tmpfile) as f:
                data = json.loads(f.read())
            assert 'nodes' in data
        finally:
            os.unlink(tmpfile)


# =============================================================================
# CRITICAL #2: from_json() mutates input via .pop()
# Calling from_json twice on same parsed data should work.
# =============================================================================

class TestFromJsonIdempotent:
    """from_json() should not mutate its input data."""

    def test_from_json_can_be_called_twice_on_same_data(self):
        """Deserializing the same JSON string twice should produce
        equivalent filesystems."""
        fs = FileSystem()
        fs.write('/test.txt', b'hello')
        json_str = fs.to_json()

        fs1 = FileSystem.from_json(json_str)
        fs2 = FileSystem.from_json(json_str)

        assert fs1.paths == fs2.paths
        assert fs1.read('/test.txt') == b'hello'
        assert fs2.read('/test.txt') == b'hello'

    def test_from_json_does_not_mutate_parsed_dict(self):
        """The parsed dict should be unchanged after from_json."""
        fs = FileSystem()
        fs.write('/test.txt', b'hello world')
        json_str = fs.to_json()
        data = json.loads(json_str)
        original_data = copy.deepcopy(data)

        FileSystem.from_json(json_str)

        # Verify the original data was not mutated
        assert data == original_data, "from_json mutated the input data"


# =============================================================================
# CRITICAL #3: is_file() returns True for symlinks
# =============================================================================

class TestNodeTypeChecks:
    """Node type checks should use proper POSIX bitmask for all types."""

    def test_symlink_is_not_a_file(self):
        """A symlink node should not be considered a file."""
        symlink = SymlinkNode(target='/some/path', mode=Mode.IFLNK | 0o777)
        assert symlink.is_symlink() is True
        assert symlink.is_file() is False

    def test_symlink_is_not_a_device(self):
        """A symlink node should not be considered a device."""
        symlink = SymlinkNode(target='/some/path', mode=Mode.IFLNK | 0o777)
        assert symlink.is_device() is False

    def test_symlink_is_not_a_directory(self):
        """A symlink node should not be considered a directory."""
        symlink = SymlinkNode(target='/some/path', mode=Mode.IFLNK | 0o777)
        assert symlink.is_dir() is False

    def test_regular_file_is_a_file(self):
        """A regular FileNode should still be considered a file."""
        node = FileNode(content=b'hello', mode=Mode.IFREG | 0o644)
        assert node.is_file() is True

    def test_directory_is_not_a_file(self):
        """A directory should not be considered a file."""
        node = DirNode(children={}, mode=Mode.IFDIR | 0o755)
        assert node.is_file() is False

    def test_device_is_not_a_file(self):
        """A device should not be considered a file."""
        node = DeviceNode(device_type='null', mode=Mode.IFCHR | 0o666)
        assert node.is_file() is False


# =============================================================================
# CRITICAL #4: clear command should use ANSI escape instead of os.system
# =============================================================================

class TestClearCommand:
    """The clear command should not invoke external system commands."""

    def test_clear_does_not_use_system_call(self):
        """Verify clear command doesn't use external system call."""
        source = inspect.getsource(TerminalSession.execute_command)
        assert 'system(' not in source


# =============================================================================
# IMPORTANT #7: Bare except clauses
# =============================================================================

class TestNoBareExcepts:
    """Source code should not contain bare except: clauses."""

    def _find_bare_excepts(self, module) -> list:
        """Return list of (line_number, line) tuples for bare except: clauses."""
        source = inspect.getsource(module)
        return [
            (i, line)
            for i, line in enumerate(source.split('\n'), 1)
            if line.strip() == 'except:'
        ]

    def test_no_bare_except_in_dagshell(self):
        """dagshell.py should not have bare except: clauses."""
        import dagshell.dagshell as mod
        bare_excepts = self._find_bare_excepts(mod)
        assert bare_excepts == [], f"Found bare except clauses: {bare_excepts}"

    def test_no_bare_except_in_terminal(self):
        """terminal.py should not have bare except: clauses."""
        import dagshell.terminal as mod
        bare_excepts = self._find_bare_excepts(mod)
        assert bare_excepts == [], f"Found bare except clauses: {bare_excepts}"


# =============================================================================
# IMPORTANT #8: Python 3.8 incompatible type hints
# =============================================================================

class TestPython38Compatibility:
    """Type hints should be compatible with Python 3.8."""

    def test_no_builtin_generic_type_hints_in_dagshell(self):
        """dagshell.py should not use tuple[...] syntax (requires 3.9+)."""
        import dagshell.dagshell as mod
        source = inspect.getsource(mod)
        matches = re.findall(r'-> tuple\[|: tuple\[', source)
        assert matches == [], f"Found Python 3.9+ type hint syntax: {matches}"


# =============================================================================
# IMPORTANT #9-10: Version mismatch and placeholder metadata
# =============================================================================

class TestPackageMetadata:
    """Package metadata should be consistent and not placeholders."""

    def test_version_matches_pyproject(self):
        """__init__.py version should match pyproject.toml."""
        assert dagshell.__version__ == "0.2.1"

    def test_author_is_not_placeholder(self):
        """__init__.py author should not be a placeholder."""
        assert dagshell.__author__ != "Your Name"

    def test_email_is_not_placeholder(self):
        """__init__.py email should not be a placeholder."""
        assert dagshell.__email__ != "your.email@example.com"


# =============================================================================
# SUGGESTION #17: Dead code - duplicate head/tail in _prepare_arguments
# =============================================================================

class TestDeadCodeRemoved:
    """Verify dead code has been cleaned up."""

    def test_no_duplicate_head_tail_handler(self):
        """_prepare_arguments should only have one head/tail handler."""
        source = inspect.getsource(CommandExecutor._prepare_arguments)
        count = source.count("command.name in ['head', 'tail']")
        assert count == 1, f"Found {count} head/tail handlers, expected 1"


# =============================================================================
# SUGGESTION #18: ls -l shows hardcoded permissions
# =============================================================================

class TestLsLongPermissions:
    """ls -l should show actual file permissions, not hardcoded values."""

    def test_ls_long_shows_actual_permissions(self):
        """ls -l output should reflect the file's actual mode bits."""
        shell = DagShell()
        shell.mkdir('/testdir')
        shell.touch('/testdir/file.txt')
        shell.chmod('777', '/testdir/file.txt')

        result = shell.ls('/testdir', long=True)
        assert 'rwxrwxrwx' in result.text, (
            f"Expected rwxrwxrwx for mode 777, got: {result.text}"
        )


# =============================================================================
# SUGGESTION #21: Duplicate whoami() - second overrides first
# =============================================================================

class TestWhoamiUsesEnv:
    """whoami() should read from environment, not return hardcoded value."""

    def test_whoami_reads_user_env(self):
        """whoami should return the USER env var when set."""
        shell = DagShell()
        shell.setenv('USER', 'alice')
        result = shell.whoami()
        assert result.text == 'alice'

    def test_whoami_defaults_to_user(self):
        """whoami should default to 'user' when USER is not set."""
        shell = DagShell()
        del shell._env['USER']
        result = shell.whoami()
        assert result.text == 'user'


# =============================================================================
# SUGGESTION #19: Double history recording
# =============================================================================

class TestNoDoubleHistoryRecording:
    """Commands should only be recorded once in history."""

    def test_execute_command_does_not_duplicate_history(self):
        """Executing a command should not add it to history twice."""
        source = inspect.getsource(TerminalSession.execute_command)
        add_count = source.count('history_manager.add')
        assert add_count <= 1, (
            f"execute_command calls history_manager.add {add_count} times"
        )
