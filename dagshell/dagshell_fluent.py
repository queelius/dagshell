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
from . import dagshell


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

        # Use shell's filesystem if available, otherwise fall back to global
        if self._shell:
            # Ensure parent directories exist (create nested if necessary)
            parent_path = os.path.dirname(path)
            if parent_path and parent_path != '/' and not self._shell.fs.exists(parent_path):
                # Create parent directories recursively
                self._shell.mkdir(parent_path, parents=True)

            content = bytes(self)
            self._shell.fs.write(path, content)
        else:
            # Fall back to global filesystem
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

        # Use shell's filesystem if available, otherwise fall back to global
        if self._shell:
            # Ensure parent directories exist (create nested if necessary)
            parent_path = os.path.dirname(path)
            if parent_path and parent_path != '/' and not self._shell.fs.exists(parent_path):
                # Create parent directories recursively
                self._shell.mkdir(parent_path, parents=True)

            # Read existing content from shell's filesystem
            existing = self._shell.fs.read(path) if self._shell.fs.exists(path) else b''
            content = existing + bytes(self)
            self._shell.fs.write(path, content)
        else:
            # Fall back to global filesystem
            parent_path = os.path.dirname(path)
            if parent_path and parent_path != '/' and not dagshell.exists(parent_path):
                dagshell.mkdir(parent_path)

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
        self._dir_stack: List[str] = []  # Stack for pushd/popd
        self._history: List[str] = []  # Command history
        self._history_max: int = 1000  # Maximum history size

    def _add_to_history(self, command: str) -> None:
        """Add a command to history."""
        if command and command.strip():
            self._history.append(command.strip())
            # Trim history if too long
            if len(self._history) > self._history_max:
                self._history = self._history[-self._history_max:]

    def history(self, n: Optional[int] = None) -> CommandResult:
        """Display command history.

        Usage:
            history [N]

        Options:
            N                      Number of recent commands to show

        Returns:
            Command history list.
        """
        if n is None:
            hist = self._history.copy()
        else:
            hist = self._history[-n:] if n > 0 else []

        # Format like bash history with line numbers
        lines = [f"{i+1}  {cmd}" for i, cmd in enumerate(hist)]
        return self._make_result(hist, '\n'.join(lines))

    def _make_result(self, data: Any, text: Optional[str] = None, exit_code: int = 0) -> CommandResult:
        """Create a CommandResult with shell context."""
        result = CommandResult(data=data, text=text, exit_code=exit_code, _shell=self)
        self._last_result = result
        return result

    def _resolve_path(self, path: str) -> str:
        """Resolve relative paths to absolute paths and normalize them."""
        # Construct the full path
        if not path.startswith('/'):
            # Relative path - join with current directory
            full_path = str(PurePosixPath(self._cwd) / path)
        else:
            # Absolute path
            full_path = path

        # Normalize the path (resolve . and .. components)
        # Split into parts and manually resolve . and ..
        parts = full_path.split('/')
        normalized = []

        for part in parts:
            if part == '' or part == '.':
                # Skip empty parts and current directory references
                continue
            elif part == '..':
                # Go up one level if possible
                if normalized:
                    normalized.pop()
            else:
                # Regular directory/file name
                normalized.append(part)

        # Reconstruct the path
        result = '/' + '/'.join(normalized) if normalized else '/'
        return result

    def _ensure_parent_dirs(self, path: str) -> None:
        """Ensure all parent directories exist, creating them if needed.

        Args:
            path: The directory path to ensure exists.
        """
        # Split the path into components
        parts = path.strip('/').split('/')
        current = ''
        for part in parts:
            current = f'{current}/{part}'
            if not self.fs.exists(current):
                self.fs.mkdir(current)

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
        """Print working directory.

        Usage:
            pwd

        Options:
            None

        Examples:
            pwd                    # Show current directory

        Returns:
            The absolute path of the current working directory.
        """
        return self._make_result(data=self._cwd, text=self._cwd)

    def env(self, var: Optional[str] = None) -> CommandResult:
        """Display environment variables.

        Usage:
            env [VARIABLE]

        Options:
            VARIABLE               Name of specific variable to display

        Examples:
            env                    # Show all environment variables
            env USER               # Show value of USER variable
            env PATH               # Show value of PATH variable

        Returns:
            Environment variable value(s).
        """
        if var:
            value = self._env.get(var, '')
            result = CommandResult(data=value, text=value)
        else:
            result = CommandResult(data=dict(self._env))
        self._last_result = result
        return result

    def setenv(self, var: str, value: str) -> 'DagShell':
        """Set environment variable.

        Usage:
            setenv VARIABLE VALUE

        Options:
            VARIABLE               Variable name
            VALUE                  Variable value

        Examples:
            setenv PATH /usr/bin   # Set PATH variable
            setenv EDITOR vim      # Set default editor
            setenv DEBUG true      # Set debug flag

        Returns:
            Self for method chaining.
        """
        self._env[var] = value
        if var == 'PWD':
            self._cwd = value
        return self

    # Navigation methods

    def cd(self, path: str = None) -> 'DagShell':
        """Change the current directory.

        Usage:
            cd [PATH]

        Options:
            PATH                   Directory to change to (default: HOME)

        Examples:
            cd                     # Go to home directory
            cd /usr/bin            # Go to /usr/bin
            cd ..                  # Go to parent directory
            cd ~/documents         # Go to documents in home

        Returns:
            Self for method chaining.
        """
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

    def pushd(self, path: str) -> 'DagShell':
        """Push current directory onto stack and change to new directory.

        Usage:
            pushd PATH

        Options:
            PATH                   Directory to change to

        Examples:
            pushd /tmp             # Push cwd, go to /tmp
            pushd ~/projects       # Push cwd, go to projects

        Returns:
            Self for method chaining.
        """
        # Save current directory on stack
        self._dir_stack.append(self._cwd)

        # Change to new directory
        new_path = self._resolve_path(path)

        if not self.fs.exists(new_path):
            # Pop the directory we just pushed since cd failed
            self._dir_stack.pop()
            self._last_result = CommandResult(
                data=None,
                text=f"pushd: {path}: No such file or directory",
                exit_code=1
            )
            return self

        stat = self.fs.stat(new_path)
        if stat['type'] != 'dir':
            self._dir_stack.pop()
            self._last_result = CommandResult(
                data=None,
                text=f"pushd: {path}: Not a directory",
                exit_code=1
            )
            return self

        self._cwd = new_path
        self._env['PWD'] = new_path

        # Return stack info like bash does
        stack_display = ' '.join([new_path] + list(reversed(self._dir_stack)))
        self._last_result = CommandResult(data=self._dir_stack.copy(), text=stack_display, exit_code=0)
        return self

    def popd(self) -> 'DagShell':
        """Pop directory from stack and change to it.

        Usage:
            popd

        Examples:
            popd                   # Return to previously pushed directory

        Returns:
            Self for method chaining.
        """
        if not self._dir_stack:
            self._last_result = CommandResult(
                data=None,
                text="popd: directory stack empty",
                exit_code=1
            )
            return self

        # Pop directory from stack
        prev_dir = self._dir_stack.pop()

        # Change to it
        self._cwd = prev_dir
        self._env['PWD'] = prev_dir

        # Return stack info
        stack_display = ' '.join([prev_dir] + list(reversed(self._dir_stack)))
        self._last_result = CommandResult(data=self._dir_stack.copy(), text=stack_display, exit_code=0)
        return self

    def dirs(self) -> CommandResult:
        """Display directory stack.

        Usage:
            dirs

        Returns:
            Current directory stack.
        """
        stack = [self._cwd] + list(reversed(self._dir_stack))
        return self._make_result(stack, ' '.join(stack))

    # File operations

    def ls(self, path: Optional[str] = None,
           all: bool = False, long: bool = False) -> CommandResult:
        """List directory contents.

        Usage:
            ls [OPTIONS] [PATH]

        Options:
            -a, --all              Show hidden files (starting with .)
            -l, --long             Use long listing format
            PATH                   Directory to list (default: current)

        Examples:
            ls                     # List current directory
            ls /usr                # List /usr directory
            ls -a                  # Show all files including hidden
            ls -la /tmp            # Long format with hidden files

        Returns:
            List of files and directories.
        """
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
        """Concatenate and display files.

        Usage:
            cat [FILE...]

        Options:
            FILE                   File(s) to display

        Examples:
            cat file.txt           # Display contents of file.txt
            cat f1.txt f2.txt      # Concatenate multiple files
            echo "text" | cat      # Display piped input

        Returns:
            File contents as text.
        """
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
        """Display a line of text.

        Usage:
            echo [OPTIONS] [STRING...]

        Options:
            -n                     Do not output trailing newline
            STRING                 Text to display

        Examples:
            echo "Hello World"     # Print Hello World
            echo -n "No newline"   # Print without newline
            echo $USER             # Print environment variable

        Returns:
            The echoed text.
        """
        text = ' '.join(str(arg) for arg in args)
        if not n:
            text += '\n'
        return self._make_result(data=text.encode('utf-8'), text=text.rstrip())

    def touch(self, path: str) -> 'DagShell':
        """Create empty file or update timestamp.

        Usage:
            touch FILE

        Options:
            FILE                   File to create or update

        Examples:
            touch newfile.txt      # Create empty file
            touch existing.txt     # Update timestamp
            touch /tmp/marker      # Create file with absolute path

        Returns:
            Self for method chaining.
        """
        resolved = self._resolve_path(path)
        if not self.fs.exists(resolved):
            self.fs.write(resolved, b'')
        # TODO: Update mtime if exists
        return self

    def mkdir(self, path: str, parents: bool = False) -> 'DagShell':
        """Create directories.

        Usage:
            mkdir [OPTIONS] DIRECTORY

        Options:
            -p, --parents          Create parent directories as needed
            DIRECTORY              Directory name to create

        Examples:
            mkdir mydir            # Create directory
            mkdir -p a/b/c         # Create nested directories
            mkdir /tmp/test        # Create with absolute path

        Returns:
            Self for method chaining.
        """
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
        """Remove files or directories.

        Usage:
            rm [OPTIONS] FILE

        Options:
            -r, --recursive        Remove directories recursively
            -f, --force            Ignore nonexistent files
            FILE                   File or directory to remove

        Examples:
            rm file.txt            # Remove a file
            rm -r mydir            # Remove directory recursively
            rm -rf /tmp/cache      # Force remove directory

        Returns:
            Self for method chaining.
        """
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
        """Copy files or directories.

        Usage:
            cp SOURCE DEST

        Options:
            SOURCE                 Source file/directory
            DEST                   Destination path

        Examples:
            cp file1.txt file2.txt # Copy file
            cp doc.txt /tmp/       # Copy to directory
            cp -r dir1 dir2        # Copy directory (when implemented)

        Returns:
            Self for method chaining.
        """
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

        # Check if destination is a directory
        dst_stat = self.fs.stat(dst_path)
        if dst_stat and dst_stat['type'] == 'dir':
            # If dst is a directory, copy src into it with the same name
            src_name = os.path.basename(src_path)
            dst_path = os.path.join(dst_path, src_name)

        self.fs.write(dst_path, content)
        return self

    def mv(self, src: str, dst: str) -> 'DagShell':
        """Move or rename files and directories.

        Usage:
            mv SOURCE DEST

        Options:
            SOURCE                 Source file/directory
            DEST                   Destination path

        Examples:
            mv old.txt new.txt     # Rename file
            mv file.txt /tmp/      # Move to directory
            mv dir1 dir2           # Rename directory

        Returns:
            Self for method chaining.
        """
        src_path = self._resolve_path(src)
        dst_path = self._resolve_path(dst)

        if not self.fs.exists(src_path):
            self._last_result = CommandResult(
                data=None,
                text=f"mv: cannot stat '{src}': No such file or directory",
                exit_code=1
            )
            return self

        src_stat = self.fs.stat(src_path)

        # Check if destination is an existing directory
        dst_stat = self.fs.stat(dst_path)
        if dst_stat and dst_stat['type'] == 'dir':
            # Move source into the directory
            src_name = os.path.basename(src_path)
            dst_path = os.path.join(dst_path, src_name)

        if src_stat and src_stat['type'] == 'dir':
            # Moving a directory - need to recursively copy then delete
            self._copy_dir_recursive(src_path, dst_path)
            self._rm_recursive(src_path)
        else:
            # Moving a file - simple copy and delete
            content = self.fs.read(src_path)
            if content is not None:
                self.fs.write(dst_path, content)
                self.fs.rm(src_path)

        return self

    def _copy_dir_recursive(self, src: str, dst: str) -> None:
        """Recursively copy a directory."""
        # Create destination directory
        self.fs.mkdir(dst)

        # Copy all children
        children = self.fs.ls(src)
        if children:
            for child in children:
                src_child = os.path.join(src, child)
                dst_child = os.path.join(dst, child)
                child_stat = self.fs.stat(src_child)

                if child_stat and child_stat['type'] == 'dir':
                    self._copy_dir_recursive(src_child, dst_child)
                else:
                    content = self.fs.read(src_child)
                    if content is not None:
                        self.fs.write(dst_child, content)

    def _rm_recursive(self, path: str) -> None:
        """Recursively remove a directory and its contents."""
        stat = self.fs.stat(path)
        if stat and stat['type'] == 'dir':
            children = self.fs.ls(path)
            if children:
                for child in children:
                    child_path = os.path.join(path, child)
                    self._rm_recursive(child_path)
        self.fs.rm(path)

    # Text processing methods

    def grep(self, pattern: str, *paths: str,
             ignore_case: bool = False, invert: bool = False) -> CommandResult:
        """Search for patterns in files or input.

        Usage:
            grep [OPTIONS] PATTERN [FILE...]

        Options:
            -i, --ignore-case      Ignore case distinctions
            -v, --invert           Select non-matching lines
            PATTERN                Regular expression pattern
            FILE                   File(s) to search (default: stdin)

        Examples:
            grep "error" log.txt   # Find lines with "error"
            grep -i "ERROR" *.log  # Case-insensitive search
            ls | grep ".txt"       # Filter ls output
            grep -v "#" config     # Show non-comment lines

        Returns:
            Lines matching the pattern.
        """
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
        """Display first lines of a file.

        Usage:
            head [OPTIONS] [FILE...]

        Options:
            -n NUM                 Number of lines to display (default: 10)
            FILE                   File(s) to read (default: stdin)

        Examples:
            head file.txt          # Show first 10 lines
            head -n 5 file.txt     # Show first 5 lines
            cat log | head -20     # Show first 20 lines of piped input

        Returns:
            The first n lines of input.
        """
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
        """Display last lines of a file.

        Usage:
            tail [OPTIONS] [FILE...]

        Options:
            -n NUM                 Number of lines to display (default: 10)
            FILE                   File(s) to read (default: stdin)

        Examples:
            tail file.txt          # Show last 10 lines
            tail -n 20 error.log   # Show last 20 lines
            dmesg | tail -5        # Show last 5 lines of piped input

        Returns:
            The last n lines of input.
        """
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

        # Take last n lines (handle n=0 case explicitly since -0 == 0 in Python)
        tail_lines = lines[-n:] if lines and n > 0 else []
        result = CommandResult(data=tail_lines, text='\n'.join(tail_lines))
        self._last_result = result
        return result

    def wc(self, *paths: str, lines: bool = True,
           words: bool = False, chars: bool = False) -> CommandResult:
        """Print line, word, and character counts.

        Usage:
            wc [OPTIONS] [FILE...]

        Options:
            -l, --lines            Print line count
            -w, --words            Print word count
            -c, --chars            Print character count
            FILE                   File(s) to count (default: stdin)

        Examples:
            wc file.txt            # Count lines in file
            wc -l *.py             # Count lines in Python files
            wc -w document.txt     # Count words
            echo "test" | wc -c    # Count characters in piped input

        Returns:
            Count statistics.
        """
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
        """Sort lines of text files.

        Usage:
            sort [OPTIONS] [FILE...]

        Options:
            -r, --reverse          Sort in reverse order
            -n, --numeric          Sort numerically
            -u, --unique           Remove duplicate lines
            FILE                   File(s) to sort (default: stdin)

        Examples:
            sort names.txt         # Sort alphabetically
            sort -r file.txt       # Sort in reverse
            sort -n numbers.txt    # Sort numerically
            ls | sort -r           # Sort ls output in reverse

        Returns:
            Sorted lines.
        """
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
        """Report or omit repeated lines.

        Usage:
            uniq [OPTIONS] [FILE...]

        Options:
            -c, --count            Prefix lines with occurrence count
            FILE                   File(s) to process (default: stdin)

        Examples:
            uniq file.txt          # Remove consecutive duplicates
            sort file | uniq       # Remove all duplicates (after sort)
            uniq -c data.txt       # Count occurrences

        Returns:
            Unique lines.
        """
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
        """Read from stdin and write to file and stdout.

        Usage:
            command | tee FILE

        Options:
            FILE                   Output file

        Examples:
            ls | tee list.txt      # Save ls output and display
            echo "log" | tee -a log.txt  # Append and display

        Returns:
            The input data (passes through).
        """
        if self._last_result:
            # Resolve path relative to current directory
            resolved = self._resolve_path(path)
            # Write directly to filesystem
            content = bytes(self._last_result)
            self.fs.write(resolved, content)
        return self._last_result or CommandResult(data=b'', text='')

    # Advanced features

    def find(self, path: Optional[str] = None, name: Optional[str] = None,
             type: Optional[str] = None, maxdepth: Optional[int] = None) -> CommandResult:
        """Search for files and directories.

        Usage:
            find [PATH] [OPTIONS]

        Options:
            PATH                   Starting directory (default: current)
            -name PATTERN          Find by name pattern (supports wildcards)
            -type TYPE             Find by type (f=file, d=directory)
            -maxdepth N            Maximum search depth

        Examples:
            find                   # List all files/dirs from current
            find /usr -name "*.so" # Find .so files in /usr
            find . -type f         # Find only files
            find -maxdepth 2       # Search only 2 levels deep

        Returns:
            List of matching paths.
        """
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
        """Save virtual filesystem to JSON file.

        Usage:
            save [FILENAME]

        Options:
            FILENAME               Output file (default: dagshell.json)

        Examples:
            save                   # Save to dagshell.json
            save backup.json       # Save to specific file
            save /tmp/fs.json      # Save with absolute path

        Returns:
            Status message.
        """
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
        """Load virtual filesystem from JSON file.

        Usage:
            load [FILENAME]

        Options:
            FILENAME               Input file (default: dagshell.json)

        Examples:
            load                   # Load from dagshell.json
            load backup.json       # Load from specific file
            load /tmp/fs.json      # Load from absolute path

        Returns:
            Status message.
        """
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
        """Commit filesystem to JSON file (alias for save).

        Usage:
            commit [FILENAME]

        Options:
            FILENAME               Output file (default: dagshell.json)

        Examples:
            commit                 # Save to dagshell.json
            commit state.json      # Save to specific file

        Returns:
            Status message.
        """
        return self.save(filename)

    def export(self, target_path: str, preserve_permissions: bool = True) -> CommandResult:
        """Export virtual filesystem to real filesystem.

        Usage:
            export TARGET_PATH [OPTIONS]

        Options:
            TARGET_PATH            Real directory to export to
            --no-preserve-perms    Don't preserve file permissions

        Examples:
            export /tmp/export     # Export to /tmp/export
            export ~/backup        # Export to home directory

        Returns:
            Export status with file count.
        """
        try:
            exported = self.fs.export_to_real(target_path, preserve_permissions)
            result = f"Exported {exported} files/directories to {target_path}"
            return CommandResult(data=exported, text=result, exit_code=0)
        except Exception as e:
            error = f"Export failed: {e}"
            return CommandResult(data=error, text=error, exit_code=1)

    def whoami(self) -> CommandResult:
        """Print effective username.

        Usage:
            whoami

        Options:
            None

        Examples:
            whoami                 # Show current username

        Returns:
            Current username.
        """
        # For now, return a default user
        # This will be overridden by terminal session
        username = "user"
        return CommandResult(data=username, text=username, exit_code=0)

    def su(self, username: str = 'root') -> CommandResult:
        """Switch user account.

        Usage:
            su [USERNAME]

        Options:
            USERNAME               User to switch to (default: root)

        Examples:
            su                     # Switch to root
            su alice               # Switch to user alice
            su bob                 # Switch to user bob

        Returns:
            Status message.
        """
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

    def save(self, filename: str = 'dagshell.json') -> CommandResult:
        """Save virtual filesystem to JSON file.

        Usage:
            save [FILENAME]

        Options:
            FILENAME               File to save to (default: dagshell.json)

        Examples:
            save                   # Save to dagshell.json
            save backup.json       # Save to backup.json

        Returns:
            Status message.
        """
        # Get filesystem state as JSON
        json_data = self.fs.to_json()

        # Write to real filesystem
        with open(filename, 'w') as f:
            f.write(json_data)

        result = f"Filesystem saved to {filename}"
        return CommandResult(data=json_data, text=result, exit_code=0)

    def load(self, filename: str = 'dagshell.json') -> CommandResult:
        """Load virtual filesystem from JSON file.

        Usage:
            load [FILENAME]

        Options:
            FILENAME               File to load from (default: dagshell.json)

        Examples:
            load                   # Load from dagshell.json
            load backup.json       # Load from backup.json

        Returns:
            Status message.
        """
        try:
            # Read from real filesystem
            with open(filename, 'r') as f:
                json_data = f.read()

            # Create new filesystem from JSON
            self.fs = dagshell.FileSystem.from_json(json_data)

            # Reset working directory
            self._cwd = '/'

            result = f"Filesystem loaded from {filename}"
            return CommandResult(data=json_data, text=result, exit_code=0)
        except FileNotFoundError:
            result = f"load: {filename}: No such file"
            return CommandResult(data=None, text=result, exit_code=1)
        except Exception as e:
            result = f"load: {filename}: Error: {e}"
            return CommandResult(data=None, text=result, exit_code=1)

    def commit(self, filename: str = 'dagshell.json') -> CommandResult:
        """Alias for save - commit virtual filesystem to JSON file.

        Usage:
            commit [FILENAME]

        Options:
            FILENAME               File to save to (default: dagshell.json)

        Examples:
            commit                 # Save to dagshell.json
            commit state.json      # Save to state.json

        Returns:
            Status message.
        """
        return self.save(filename)

    def import_file(self, real_path: str, virtual_path: Optional[str] = None,
                    safe_paths: Optional[List[str]] = None, recursive: bool = True) -> CommandResult:
        """Import a file from the real filesystem into the virtual filesystem.

        Usage:
            import_file REAL_PATH [VIRTUAL_PATH]

        Options:
            REAL_PATH              Path to file on real filesystem
            VIRTUAL_PATH           Path in virtual filesystem (default: same as filename)
            --safe-paths          List of allowed directory prefixes
            --recursive           Import directories recursively (default: True)

        Examples:
            import_file /etc/hosts               # Import to /hosts
            import_file ~/code/script.py /scripts/script.py
            import_file ./data.csv /data/input.csv
            import_file ~/project /proj --recursive=True  # Import entire directory tree

        Security:
            By default, imports are restricted to current directory and below.
            Use safe_paths to specify allowed directories.

        Returns:
            Status message or error.
        """
        import os
        import pathlib

        # Default safe paths if not specified
        if safe_paths is None:
            safe_paths = [
                os.getcwd(),  # Current directory
                os.path.expanduser('~/'),  # Home directory
                '/tmp',  # Temp directory
            ]

        # Resolve real path
        real_path = os.path.abspath(os.path.expanduser(real_path))

        # Security check - ensure path is within safe paths
        is_safe = any(
            real_path.startswith(os.path.abspath(safe))
            for safe in safe_paths
        )

        if not is_safe:
            result = (f"import_file: {real_path}: Permission denied. "
                     f"Path not in safe paths: {safe_paths}")
            return CommandResult(data=None, text=result, exit_code=1)

        # Check if file exists
        if not os.path.exists(real_path):
            result = f"import_file: {real_path}: No such file or directory"
            return CommandResult(data=None, text=result, exit_code=1)

        # Determine virtual path
        if virtual_path is None:
            virtual_path = '/' + os.path.basename(real_path)
        else:
            virtual_path = self._resolve_path(virtual_path)
            # If importing a file and virtual_path is an existing directory,
            # append the original filename (like cp behavior)
            if os.path.isfile(real_path) and self.fs.exists(virtual_path):
                stat_info = self.fs.stat(virtual_path)
                if stat_info and stat_info.get('type') == 'dir':
                    virtual_path = os.path.join(virtual_path, os.path.basename(real_path))

        try:
            if os.path.isfile(real_path):
                # Import single file
                # Ensure parent directory exists (create recursively)
                parent_dir = os.path.dirname(virtual_path)
                if parent_dir and parent_dir != '/':
                    # Create parent directories recursively
                    self._ensure_parent_dirs(parent_dir)

                with open(real_path, 'rb') as f:
                    content = f.read()
                self.fs.write(virtual_path, content)
                result = f"Imported file: {real_path} -> {virtual_path}"

            elif os.path.isdir(real_path):
                # Import directory
                imported = []
                if recursive:
                    # Import recursively using os.walk
                    for root, dirs, files in os.walk(real_path):
                        # Calculate relative path
                        rel_root = os.path.relpath(root, real_path)
                        if rel_root == '.':
                            virt_root = virtual_path
                        else:
                            virt_root = os.path.join(virtual_path, rel_root)

                        # Create directory
                        self.fs.mkdir(virt_root)

                        # Import files
                        for file in files:
                            real_file = os.path.join(root, file)
                            virt_file = os.path.join(virt_root, file)

                            with open(real_file, 'rb') as f:
                                content = f.read()
                            self.fs.write(virt_file, content)
                            imported.append(virt_file)
                else:
                    # Import only top-level files (non-recursive)
                    self.fs.mkdir(virtual_path)
                    for item in os.listdir(real_path):
                        item_path = os.path.join(real_path, item)
                        if os.path.isfile(item_path):
                            virt_file = os.path.join(virtual_path, item)
                            with open(item_path, 'rb') as f:
                                content = f.read()
                            self.fs.write(virt_file, content)
                            imported.append(virt_file)

                result = (f"Imported directory: {real_path} -> {virtual_path}\n"
                         f"Files imported: {len(imported)}")
            else:
                result = f"import_file: {real_path}: Not a regular file or directory"
                return CommandResult(data=None, text=result, exit_code=1)

            return CommandResult(data={'imported': real_path, 'to': virtual_path},
                               text=result, exit_code=0)

        except Exception as e:
            result = f"import_file: {real_path}: Error: {e}"
            return CommandResult(data=None, text=result, exit_code=1)

    def export_file(self, virtual_path: str, real_path: Optional[str] = None,
                    safe_paths: Optional[List[str]] = None, recursive: bool = True) -> CommandResult:
        """Export a file from the virtual filesystem to the real filesystem.

        Usage:
            export_file VIRTUAL_PATH [REAL_PATH]

        Options:
            VIRTUAL_PATH           Path in virtual filesystem
            REAL_PATH             Path on real filesystem (default: current dir)
            --safe-paths          List of allowed directory prefixes
            --recursive           Export directories recursively (default: True)

        Examples:
            export_file /data/results.csv       # Export to ./results.csv
            export_file /config.json ~/config.json
            export_file /project ./exported_project --recursive=True

        Security:
            By default, exports are restricted to current directory and below.
            Use safe_paths to specify allowed directories.

        Returns:
            Status message or error.
        """
        import os

        # Default safe paths if not specified
        if safe_paths is None:
            safe_paths = [
                os.getcwd(),  # Current directory
                os.path.expanduser('~/'),  # Home directory
                '/tmp',  # Temp directory
            ]

        # Resolve virtual path
        virtual_path = self._resolve_path(virtual_path)

        # Check if virtual file exists
        if not self.fs.exists(virtual_path):
            result = f"export_file: {virtual_path}: No such file or directory"
            return CommandResult(data=None, text=result, exit_code=1)

        # Determine real path
        if real_path is None:
            real_path = os.path.join(os.getcwd(), os.path.basename(virtual_path))
        else:
            real_path = os.path.abspath(os.path.expanduser(real_path))

        # Security check
        is_safe = any(
            real_path.startswith(os.path.abspath(safe))
            for safe in safe_paths
        )

        if not is_safe:
            result = (f"export_file: {real_path}: Permission denied. "
                     f"Path not in safe paths: {safe_paths}")
            return CommandResult(data=None, text=result, exit_code=1)

        try:
            # Get stat info to determine file type
            stat_info = self.fs.stat(virtual_path)
            if not stat_info:
                result = f"export_file: {virtual_path}: No such file or directory"
                return CommandResult(data=None, text=result, exit_code=1)

            if stat_info['type'] == 'file':
                # Export single file
                content = self.fs.read(virtual_path)
                os.makedirs(os.path.dirname(real_path), exist_ok=True)
                with open(real_path, 'wb') as f:
                    f.write(content)
                result = f"Exported file: {virtual_path} -> {real_path}"

            elif stat_info['type'] == 'dir':
                # Export directory
                exported = []
                os.makedirs(real_path, exist_ok=True)

                if recursive:
                    # Export recursively
                    def export_recursive_helper(vpath, rpath):
                        os.makedirs(rpath, exist_ok=True)
                        for item in self.fs.ls(vpath) or []:
                            vitem = os.path.join(vpath, item)
                            ritem = os.path.join(rpath, item)

                            item_stat = self.fs.stat(vitem)
                            if item_stat and item_stat['type'] == 'file':
                                content = self.fs.read(vitem)
                                with open(ritem, 'wb') as f:
                                    f.write(content)
                                exported.append(ritem)
                            elif item_stat and item_stat['type'] == 'dir':
                                export_recursive_helper(vitem, ritem)

                    export_recursive_helper(virtual_path, real_path)
                else:
                    # Export only top-level files (non-recursive)
                    for item in self.fs.ls(virtual_path) or []:
                        vitem = os.path.join(virtual_path, item)
                        ritem = os.path.join(real_path, item)

                        item_stat = self.fs.stat(vitem)
                        if item_stat and item_stat['type'] == 'file':
                            content = self.fs.read(vitem)
                            with open(ritem, 'wb') as f:
                                f.write(content)
                            exported.append(ritem)

                result = (f"Exported directory: {virtual_path} -> {real_path}\n"
                         f"Files exported: {len(exported)}")
            else:
                result = f"export_file: {virtual_path}: Not a regular file or directory"
                return CommandResult(data=None, text=result, exit_code=1)

            return CommandResult(data={'exported': virtual_path, 'to': real_path},
                               text=result, exit_code=0)

        except Exception as e:
            result = f"export_file: {virtual_path}: Error: {e}"
            return CommandResult(data=None, text=result, exit_code=1)


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