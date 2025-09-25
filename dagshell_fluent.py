#!/usr/bin/env python3
"""
Fluent API for dagshell - A composable, chainable interface for terminal emulation.

This module provides a fluent, Unix-pipe-like API that serves as the foundation
for terminal emulation. It follows the principle of small, composable operations
that can be chained together.

Core Design Principles:
- Stateful operations that maintain context (pwd, env)
- Method chaining for pipe-like composition
- Dual nature: returns Python objects or redirects to virtual FS
- Clean separation between command execution and output handling
"""

import os
import re
import fnmatch
from typing import List, Dict, Optional, Union, Any, Callable, Iterator
from dataclasses import dataclass
from pathlib import PurePosixPath
import dagshell


@dataclass
class CommandResult:
    """
    Represents the result of a command execution.

    This class enables method chaining and provides both Python object
    access and virtual filesystem redirection capabilities.
    """
    data: Any  # The actual data (bytes, list, dict, etc.)
    text: Optional[str] = None  # Text representation for output
    exit_code: int = 0
    _shell: Optional['DagShell'] = None  # Reference to shell for context

    def __str__(self) -> str:
        """String representation of the result."""
        if self.text is not None:
            return self.text
        elif isinstance(self.data, bytes):
            return self.data.decode('utf-8', errors='replace')
        elif isinstance(self.data, list):
            return '\n'.join(str(item) for item in self.data)
        elif isinstance(self.data, dict):
            return '\n'.join(f"{k}: {v}" for k, v in self.data.items())
        else:
            return str(self.data)

    def __bytes__(self) -> bytes:
        """Bytes representation of the result."""
        if isinstance(self.data, bytes):
            return self.data
        else:
            return str(self).encode('utf-8')

    def __iter__(self) -> Iterator:
        """Allow iteration over list results."""
        if isinstance(self.data, (list, tuple)):
            return iter(self.data)
        elif isinstance(self.data, str):
            return iter(self.data.splitlines())
        elif isinstance(self.data, bytes):
            return iter(self.data.decode('utf-8', errors='replace').splitlines())
        else:
            return iter([self.data])

    def lines(self) -> List[str]:
        """Get result as list of lines."""
        return list(self)

    def out(self, path: str) -> 'CommandResult':
        """Redirect output to a file in the virtual filesystem."""
        # Resolve path relative to shell's current directory if available
        if self._shell and not path.startswith('/'):
            path = os.path.join(self._shell._cwd, path)

        # Ensure parent directory exists
        parent_path = os.path.dirname(path)
        if parent_path and parent_path != '/' and not dagshell.exists(parent_path):
            dagshell.mkdir(parent_path)

        content = bytes(self)
        dagshell.write(path, content)
        return self

    def append(self, path: str) -> 'CommandResult':
        """Append output to a file in the virtual filesystem."""
        # Resolve path relative to shell's current directory if available
        if self._shell and not path.startswith('/'):
            path = os.path.join(self._shell._cwd, path)

        # Read existing content
        existing = dagshell.read(path) if dagshell.exists(path) else b''
        content = existing + bytes(self)
        dagshell.write(path, content)
        return self


class DagShell:
    """
    Fluent, stateful shell-like interface for dagshell.

    This class provides a chainable API that mimics Unix shell commands
    while maintaining state like current directory and environment variables.
    """

    def __init__(self, fs: Optional[dagshell.FileSystem] = None):
        """Initialize the shell with optional filesystem."""
        self.fs = fs or dagshell.get_fs()
        self._cwd = '/'
        self._env = {
            'PATH': '/bin:/usr/bin:/usr/local/bin',
            'HOME': '/home/user',
            'USER': 'user',
            'SHELL': '/bin/dagshell',
            'PWD': '/'
        }
        self._last_result: Optional[CommandResult] = None

    def _make_result(self, data: Any, text: Optional[str] = None, exit_code: int = 0) -> CommandResult:
        """Create a CommandResult with shell context."""
        result = CommandResult(data=data, text=text, exit_code=exit_code, _shell=self)
        self._last_result = result
        return result

    def _resolve_path(self, path: str) -> str:
        """Resolve relative paths to absolute paths."""
        if not path.startswith('/'):
            # Handle relative paths
            if path == '.':
                return self._cwd
            elif path == '..':
                return str(PurePosixPath(self._cwd).parent)
            elif path.startswith('./'):
                path = path[2:]
            elif path.startswith('../'):
                parent = str(PurePosixPath(self._cwd).parent)
                return self._resolve_path(parent + '/' + path[3:])

            # Join with current directory
            return str(PurePosixPath(self._cwd) / path)
        return str(PurePosixPath(path))

    def _glob_match(self, pattern: str, path: str = None) -> List[str]:
        """Match files using glob patterns."""
        path = self._resolve_path(path or self._cwd)

        # Handle wildcards in the pattern
        if '*' in pattern or '?' in pattern or '[' in pattern:
            files = self.fs.ls(path) or []
            return [f for f in files if fnmatch.fnmatch(f, pattern)]
        else:
            # No wildcard, return as-is if exists
            full_path = self._resolve_path(os.path.join(path, pattern))
            if self.fs.exists(full_path):
                return [pattern]
            return []

    # State inspection methods

    def pwd(self) -> CommandResult:
        """Get current working directory."""
        return self._make_result(data=self._cwd, text=self._cwd)

    def env(self, var: Optional[str] = None) -> CommandResult:
        """Get environment variable(s)."""
        if var:
            value = self._env.get(var, '')
            result = CommandResult(data=value, text=value)
        else:
            result = CommandResult(data=dict(self._env))
        self._last_result = result
        return result

    def setenv(self, var: str, value: str) -> 'DagShell':
        """Set an environment variable."""
        self._env[var] = value
        if var == 'PWD':
            self._cwd = value
        return self

    # Navigation methods

    def cd(self, path: str = None) -> 'DagShell':
        """Change current directory."""
        if path is None:
            path = self._env.get('HOME', '/')

        new_path = self._resolve_path(path)

        # Check if directory exists
        if not self.fs.exists(new_path):
            # Should we raise an error or return self for chaining?
            # For fluent API, we'll set exit code but continue
            self._last_result = CommandResult(
                data=None,
                text=f"cd: {path}: No such file or directory",
                exit_code=1
            )
            return self

        # Check if it's a directory
        stat = self.fs.stat(new_path)
        if stat['type'] != 'dir':
            self._last_result = CommandResult(
                data=None,
                text=f"cd: {path}: Not a directory",
                exit_code=1
            )
            return self

        self._cwd = new_path
        self._env['PWD'] = new_path
        self._last_result = CommandResult(data=new_path, text='', exit_code=0)
        return self

    # File operations

    def ls(self, path: Optional[str] = None,
           all: bool = False, long: bool = False) -> CommandResult:
        """List directory contents."""
        target_path = self._resolve_path(path or self._cwd)

        if not self.fs.exists(target_path):
            result = CommandResult(
                data=[],
                text=f"ls: {path}: No such file or directory",
                exit_code=2
            )
            self._last_result = result
            return result

        stat = self.fs.stat(target_path)

        if stat['type'] == 'file':
            # If it's a file, just return the filename
            files = [os.path.basename(target_path)]
        else:
            # List directory contents
            files = self.fs.ls(target_path) or []

            # Filter hidden files unless -a flag
            if not all:
                files = [f for f in files if not f.startswith('.')]

        if long:
            # Detailed listing (simplified for now)
            detailed = []
            for f in files:
                full_path = os.path.join(target_path, f)
                fstat = self.fs.stat(full_path)
                if fstat:
                    type_char = 'd' if fstat['type'] == 'dir' else '-'
                    size = fstat.get('size', 0)
                    detailed.append(f"{type_char}rw-r--r--  1 user user {size:8} {f}")
            result = CommandResult(data=files, text='\n'.join(detailed))
        else:
            result = CommandResult(data=files, text='\n'.join(files))

        self._last_result = result
        return result

    def cat(self, *paths: str) -> CommandResult:
        """Concatenate and display files."""
        if not paths:
            # Read from stdin (last result)
            if self._last_result:
                return self._last_result
            else:
                result = CommandResult(data=b'', text='', exit_code=0)
                self._last_result = result
                return result

        contents = []
        for path in paths:
            resolved = self._resolve_path(path)
            content = self.fs.read(resolved)
            if content is None:
                result = CommandResult(
                    data=b'',
                    text=f"cat: {path}: No such file or directory",
                    exit_code=1
                )
                self._last_result = result
                return result
            contents.append(content)

        data = b''.join(contents)
        # Provide text representation for bytes data
        text = data.decode('utf-8', errors='replace')
        return self._make_result(data=data, text=text)

    def echo(self, *args: str, n: bool = False) -> CommandResult:
        """Echo arguments to output."""
        text = ' '.join(str(arg) for arg in args)
        if not n:
            text += '\n'
        return self._make_result(data=text.encode('utf-8'), text=text.rstrip())

    def touch(self, path: str) -> 'DagShell':
        """Create an empty file or update timestamp."""
        resolved = self._resolve_path(path)
        if not self.fs.exists(resolved):
            self.fs.write(resolved, b'')
        # TODO: Update mtime if exists
        return self

    def mkdir(self, path: str, parents: bool = False) -> 'DagShell':
        """Create a directory."""
        resolved = self._resolve_path(path)

        if parents:
            # Create parent directories as needed
            parts = PurePosixPath(resolved).parts
            current = '/'
            for part in parts[1:]:  # Skip root '/'
                current = os.path.join(current, part)
                if not self.fs.exists(current):
                    self.fs.mkdir(current)
        else:
            if not self.fs.mkdir(resolved):
                self._last_result = CommandResult(
                    data=None,
                    text=f"mkdir: cannot create directory '{path}': File exists or parent missing",
                    exit_code=1
                )
        return self

    def rm(self, path: str, recursive: bool = False, force: bool = False) -> 'DagShell':
        """Remove files or directories."""
        resolved = self._resolve_path(path)

        if not self.fs.exists(resolved) and not force:
            self._last_result = CommandResult(
                data=None,
                text=f"rm: cannot remove '{path}': No such file or directory",
                exit_code=1
            )
            return self

        # TODO: Implement recursive removal
        self.fs.rm(resolved)
        return self

    def cp(self, src: str, dst: str) -> 'DagShell':
        """Copy files or directories."""
        src_path = self._resolve_path(src)
        dst_path = self._resolve_path(dst)

        content = self.fs.read(src_path)
        if content is None:
            self._last_result = CommandResult(
                data=None,
                text=f"cp: cannot stat '{src}': No such file or directory",
                exit_code=1
            )
            return self

        self.fs.write(dst_path, content)
        return self

    def mv(self, src: str, dst: str) -> 'DagShell':
        """Move/rename files or directories."""
        self.cp(src, dst)
        self.rm(src)
        return self

    # Text processing methods

    def grep(self, pattern: str, *paths: str,
             ignore_case: bool = False, invert: bool = False) -> CommandResult:
        """Search for pattern in files or input."""
        import re

        # Prepare regex
        flags = re.IGNORECASE if ignore_case else 0
        try:
            regex = re.compile(pattern, flags)
        except re.error as e:
            result = CommandResult(
                data=[],
                text=f"grep: invalid regex: {e}",
                exit_code=2
            )
            self._last_result = result
            return result

        # Get input
        if paths:
            # Read from files
            lines = []
            for path in paths:
                resolved = self._resolve_path(path)
                content = self.fs.read(resolved)
                if content:
                    text = content.decode('utf-8', errors='replace')
                    for line in text.splitlines():
                        lines.append(line)
        else:
            # Read from last result
            if self._last_result:
                lines = self._last_result.lines()
            else:
                lines = []

        # Filter lines
        matches = []
        for line in lines:
            found = regex.search(line) is not None
            if (found and not invert) or (not found and invert):
                matches.append(line)

        result = CommandResult(data=matches, text='\n'.join(matches))
        self._last_result = result
        return result

    def head(self, n: int = 10, *paths: str) -> CommandResult:
        """Display first n lines of input."""
        # Get input
        if paths:
            lines = []
            for path in paths:
                resolved = self._resolve_path(path)
                content = self.fs.read(resolved)
                if content:
                    text = content.decode('utf-8', errors='replace')
                    lines.extend(text.splitlines())
        else:
            if self._last_result:
                lines = self._last_result.lines()
            else:
                lines = []

        # Take first n lines
        head_lines = lines[:n]
        result = CommandResult(data=head_lines, text='\n'.join(head_lines))
        self._last_result = result
        return result

    def tail(self, n: int = 10, *paths: str) -> CommandResult:
        """Display last n lines of input."""
        # Get input
        if paths:
            lines = []
            for path in paths:
                resolved = self._resolve_path(path)
                content = self.fs.read(resolved)
                if content:
                    text = content.decode('utf-8', errors='replace')
                    lines.extend(text.splitlines())
        else:
            if self._last_result:
                lines = self._last_result.lines()
            else:
                lines = []

        # Take last n lines
        tail_lines = lines[-n:] if lines else []
        result = CommandResult(data=tail_lines, text='\n'.join(tail_lines))
        self._last_result = result
        return result

    def wc(self, *paths: str, lines: bool = True,
           words: bool = False, chars: bool = False) -> CommandResult:
        """Word, line, and character count."""
        # Get input
        if paths:
            text_data = []
            for path in paths:
                resolved = self._resolve_path(path)
                content = self.fs.read(resolved)
                if content:
                    text_data.append(content.decode('utf-8', errors='replace'))
            text = '\n'.join(text_data)
        else:
            if self._last_result:
                text = str(self._last_result)
            else:
                text = ''

        # Count
        counts = {}
        if lines or (not words and not chars):  # Default to lines
            # Count lines properly - wc counts non-empty content as at least 1 line
            if text:
                counts['lines'] = text.count('\n') + (1 if not text.endswith('\n') else 0)
            else:
                counts['lines'] = 0
        if words:
            counts['words'] = len(text.split())
        if chars:
            counts['chars'] = len(text)

        # Format output
        if len(counts) == 1:
            # Single count
            value = list(counts.values())[0]
            result = CommandResult(data=value, text=str(value))
        else:
            # Multiple counts
            text_parts = []
            if 'lines' in counts:
                text_parts.append(str(counts['lines']))
            if 'words' in counts:
                text_parts.append(str(counts['words']))
            if 'chars' in counts:
                text_parts.append(str(counts['chars']))
            result = CommandResult(data=counts, text=' '.join(text_parts))

        self._last_result = result
        return result

    def sort(self, *paths: str, reverse: bool = False,
             numeric: bool = False, unique: bool = False) -> CommandResult:
        """Sort lines of text."""
        # Get input
        if paths:
            lines = []
            for path in paths:
                resolved = self._resolve_path(path)
                content = self.fs.read(resolved)
                if content:
                    text = content.decode('utf-8', errors='replace')
                    lines.extend(text.splitlines())
        else:
            if self._last_result:
                lines = self._last_result.lines()
            else:
                lines = []

        # Sort
        if numeric:
            def key_func(x):
                try:
                    return float(x)
                except ValueError:
                    return float('inf')
        else:
            key_func = str.lower

        sorted_lines = sorted(lines, key=key_func, reverse=reverse)

        # Remove duplicates if requested
        if unique:
            seen = set()
            unique_lines = []
            for line in sorted_lines:
                if line not in seen:
                    seen.add(line)
                    unique_lines.append(line)
            sorted_lines = unique_lines

        result = CommandResult(data=sorted_lines, text='\n'.join(sorted_lines))
        self._last_result = result
        return result

    def uniq(self, *paths: str, count: bool = False) -> CommandResult:
        """Remove duplicate lines."""
        # Get input
        if paths:
            lines = []
            for path in paths:
                resolved = self._resolve_path(path)
                content = self.fs.read(resolved)
                if content:
                    text = content.decode('utf-8', errors='replace')
                    lines.extend(text.splitlines())
        else:
            if self._last_result:
                lines = self._last_result.lines()
            else:
                lines = []

        # Remove consecutive duplicates
        unique_lines = []
        counts = []
        last_line = None
        current_count = 0

        for line in lines:
            if line != last_line:
                if last_line is not None:
                    unique_lines.append(last_line)
                    counts.append(current_count)
                last_line = line
                current_count = 1
            else:
                current_count += 1

        if last_line is not None:
            unique_lines.append(last_line)
            counts.append(current_count)

        # Format output
        if count:
            output_lines = [f"{c:7} {line}" for c, line in zip(counts, unique_lines)]
            result = CommandResult(
                data=list(zip(counts, unique_lines)),
                text='\n'.join(output_lines)
            )
        else:
            result = CommandResult(data=unique_lines, text='\n'.join(unique_lines))

        self._last_result = result
        return result

    # Piping and chaining support

    def pipe(self, func: Callable[['DagShell'], CommandResult]) -> CommandResult:
        """Pipe last result through a function."""
        return func(self)

    def tee(self, path: str) -> CommandResult:
        """Write to file and also return the data (like Unix tee)."""
        if self._last_result:
            self._last_result.out(path)
        return self._last_result or CommandResult(data=b'', text='')

    # Advanced features

    def find(self, path: Optional[str] = None, name: Optional[str] = None,
             type: Optional[str] = None, maxdepth: Optional[int] = None) -> CommandResult:
        """Find files and directories."""
        start_path = self._resolve_path(path or self._cwd)
        found = []

        def search(current_path: str, depth: int = 0):
            if maxdepth is not None and depth > maxdepth:
                return

            entries = self.fs.ls(current_path) or []
            for entry in entries:
                full_path = os.path.join(current_path, entry)
                stat = self.fs.stat(full_path)

                if stat:
                    # Check type filter
                    if type:
                        if type == 'f' and stat['type'] != 'file':
                            continue
                        elif type == 'd' and stat['type'] != 'dir':
                            continue

                    # Check name filter
                    if name and not fnmatch.fnmatch(entry, name):
                        if stat['type'] == 'dir':
                            # Still recurse into directories even if name doesn't match
                            search(full_path, depth + 1)
                        continue

                    found.append(full_path)

                    # Recurse into directories
                    if stat['type'] == 'dir':
                        search(full_path, depth + 1)

        # Start search
        if self.fs.exists(start_path):
            stat = self.fs.stat(start_path)

            # For directories, include it if no name filter or name matches
            if stat['type'] == 'dir':
                include_start = True

                # Check type filter
                if type and type == 'f':  # Looking for files only
                    include_start = False

                # Check name filter only if we have one and we're including dirs
                if include_start and name:
                    dir_name = os.path.basename(start_path) if start_path != '/' else '/'
                    if not fnmatch.fnmatch(dir_name, name):
                        include_start = False

                if include_start:
                    found.append(start_path)

                # Always search inside directories
                search(start_path, 1)
            else:
                # It's a file - include if criteria match
                if (not type or type == 'f'):
                    if not name or fnmatch.fnmatch(os.path.basename(start_path), name):
                        found.append(start_path)

        result = CommandResult(data=found, text='\n'.join(found))
        self._last_result = result
        return result

    def save(self, filename: str = 'dagshell.json') -> CommandResult:
        """Save filesystem to JSON file."""
        try:
            import json
            # Get JSON representation
            json_data = self.fs.to_json()

            # Write to real file (not virtual filesystem)
            with open(filename, 'w') as f:
                f.write(json_data)

            result = f"Filesystem saved to {filename}"
            return CommandResult(data=result, text=result, exit_code=0)
        except Exception as e:
            error = f"Failed to save: {e}"
            return CommandResult(data=error, text=error, exit_code=1)

    def load(self, filename: str = 'dagshell.json') -> CommandResult:
        """Load filesystem from JSON file."""
        try:
            import json
            # Read from real file
            with open(filename, 'r') as f:
                json_data = f.read()

            # Create new filesystem from JSON
            new_fs = dagshell.FileSystem.from_json(json_data)

            # Replace current filesystem
            self.fs = new_fs

            # Reset to root directory
            self._cwd = '/'

            result = f"Filesystem loaded from {filename}"
            return CommandResult(data=result, text=result, exit_code=0)
        except FileNotFoundError:
            error = f"File not found: {filename}"
            return CommandResult(data=error, text=error, exit_code=1)
        except Exception as e:
            error = f"Failed to load: {e}"
            return CommandResult(data=error, text=error, exit_code=1)

    def commit(self, filename: str = 'dagshell.json') -> CommandResult:
        """Alias for save - commit filesystem to JSON file."""
        return self.save(filename)

    def export(self, target_path: str, preserve_permissions: bool = True) -> CommandResult:
        """
        Export virtual filesystem to real filesystem.

        Args:
            target_path: Directory to export to
            preserve_permissions: Whether to preserve file modes

        Returns:
            CommandResult with export status
        """
        try:
            exported = self.fs.export_to_real(target_path, preserve_permissions)
            result = f"Exported {exported} files/directories to {target_path}"
            return CommandResult(data=exported, text=result, exit_code=0)
        except Exception as e:
            error = f"Export failed: {e}"
            return CommandResult(data=error, text=error, exit_code=1)

    def whoami(self) -> CommandResult:
        """Get current user name."""
        # For now, return a default user
        # This will be overridden by terminal session
        username = "user"
        return CommandResult(data=username, text=username, exit_code=0)

    def su(self, username: str = 'root') -> CommandResult:
        """Switch user (placeholder for terminal session)."""
        # This is mainly for terminal session use
        # The fluent API doesn't track user context by default
        result = f"Switched to user: {username}"
        return CommandResult(data=username, text=result, exit_code=0)

    def xargs(self, command: str, *args) -> CommandResult:
        """Build and execute command from input."""
        if not self._last_result:
            result = CommandResult(data=[], text='', exit_code=0)
            self._last_result = result
            return result

        # Get input lines
        lines = self._last_result.lines()

        # Map command to method
        method = getattr(self, command, None)
        if not method:
            result = CommandResult(
                data=None,
                text=f"xargs: {command}: command not found",
                exit_code=127
            )
            self._last_result = result
            return result

        # Execute command for each line
        results = []
        for line in lines:
            if callable(method):
                # Call with line as argument
                res = method(line, *args)
                if isinstance(res, CommandResult):
                    results.append(res.data)

        result = CommandResult(data=results)
        self._last_result = result
        return result


# Create a default global instance
_shell = DagShell()


# Module-level convenience functions that use the global instance
def cd(path: str = None) -> DagShell:
    """Change directory."""
    return _shell.cd(path)

def ls(path: str = None, **kwargs) -> CommandResult:
    """List directory."""
    return _shell.ls(path, **kwargs)

def pwd() -> CommandResult:
    """Get current directory."""
    return _shell.pwd()

def cat(*paths: str) -> CommandResult:
    """Concatenate files."""
    return _shell.cat(*paths)

def grep(pattern: str, *paths: str, **kwargs) -> CommandResult:
    """Search for pattern."""
    return _shell.grep(pattern, *paths, **kwargs)

def head(n: int = 10, *paths: str) -> CommandResult:
    """Show first n lines."""
    return _shell.head(n, *paths)

def tail(n: int = 10, *paths: str) -> CommandResult:
    """Show last n lines."""
    return _shell.tail(n, *paths)

def wc(*paths: str, **kwargs) -> CommandResult:
    """Count lines/words/chars."""
    return _shell.wc(*paths, **kwargs)

def echo(*args, **kwargs) -> CommandResult:
    """Echo arguments."""
    return _shell.echo(*args, **kwargs)

def env(var: str = None) -> CommandResult:
    """Get environment."""
    return _shell.env(var)

def find(path: str = None, **kwargs) -> CommandResult:
    """Find files."""
    return _shell.find(path, **kwargs)

def save(filename: str = 'dagshell.json') -> CommandResult:
    """Save filesystem to JSON file."""
    return _shell.save(filename)

def load(filename: str = 'dagshell.json') -> CommandResult:
    """Load filesystem from JSON file."""
    return _shell.load(filename)

def commit(filename: str = 'dagshell.json') -> CommandResult:
    """Alias for save - commit filesystem to JSON file."""
    return _shell.commit(filename)

def mkdir(path: str, **kwargs) -> DagShell:
    """Create directory."""
    return _shell.mkdir(path, **kwargs)

def touch(path: str) -> DagShell:
    """Create or update file."""
    return _shell.touch(path)

def rm(path: str, **kwargs) -> DagShell:
    """Remove file or directory."""
    return _shell.rm(path, **kwargs)

# Allow direct access to the shell instance for chaining
shell = _shell