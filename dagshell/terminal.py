#!/usr/bin/env python3
"""
Terminal emulator for dagshell.

This module provides a complete terminal emulation layer that translates
shell commands into fluent API calls. It maintains session state, handles
command execution, and provides a familiar Unix-like interface.

Design Principles:
- All operations go through the fluent API
- Clean separation between parsing and execution
- Stateful session management
- Composable command execution
"""

import os
import sys
import getpass
import socket
import readline
import atexit
import signal
import json
import re
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime

from .command_parser import (
    CommandParser, Command, Pipeline, CommandGroup,
    RedirectType, Redirect
)
from .dagshell_fluent import DagShell, CommandResult


@dataclass
class TerminalConfig:
    """Configuration for terminal session."""
    user: str = field(default_factory=lambda: getpass.getuser())
    hostname: str = field(default_factory=lambda: socket.gethostname().split('.')[0])
    home_dir: str = '/home/user'
    initial_dir: str = '/'
    prompt_format: str = '{user}@{hostname}:{cwd}$ '
    enable_colors: bool = True
    history_size: int = 1000
    safe_host_directory: Optional[str] = None  # Safe directory for host file operations
    snapshots_directory: str = '.dagshell-snapshots'  # Directory for state snapshots
    # Enhanced terminal features
    history_file: str = field(default_factory=lambda: str(Path.home() / '.dagshell_history'))
    history_max_size: int = 10000
    enable_tab_completion: bool = True
    enable_history_expansion: bool = True
    aliases: Dict[str, str] = field(default_factory=dict)
    alias_file: str = field(default_factory=lambda: str(Path.home() / '.dagshell_aliases'))


class HistoryManager:
    """
    Manages command history with persistence and expansion.

    Provides:
    - History persistence to disk
    - History expansion (!!, !n, !-n, !string)
    - Integration with readline library
    """

    def __init__(self, history_file: str, max_size: int = 10000):
        """Initialize history manager with file persistence."""
        self.history_file = history_file
        self.max_size = max_size
        self.history: List[str] = []
        self._initial_history_length = readline.get_current_history_length()
        self._load_history()

    def _load_history(self):
        """Load history from file."""
        try:
            if os.path.exists(self.history_file):
                readline.clear_history()
                readline.read_history_file(self.history_file)
                history_length = readline.get_current_history_length()
                self.history = [
                    readline.get_history_item(i)
                    for i in range(1, history_length + 1)
                    if readline.get_history_item(i)
                ]
        except (IOError, OSError, AttributeError):
            self.history = []

    def save_history(self):
        """Save history to file."""
        try:
            readline.write_history_file(self.history_file)
        except (IOError, OSError):
            pass

    def add(self, command: str):
        """Add a command to history."""
        if command and command.strip():
            if not self.history or self.history[-1] != command:
                self.history.append(command)
                readline.add_history(command)
                if len(self.history) > self.max_size:
                    self.history = self.history[-self.max_size:]

    def get(self, index: int) -> Optional[str]:
        """Get command at specific index (1-based like bash)."""
        if 0 < index <= len(self.history):
            return self.history[index - 1]
        return None

    def get_last(self) -> Optional[str]:
        """Get the last command."""
        return self.history[-1] if self.history else None

    def search(self, pattern: str) -> List[Tuple[int, str]]:
        """Search history for commands containing pattern."""
        results = []
        for i, cmd in enumerate(self.history, 1):
            if pattern in cmd:
                results.append((i, cmd))
        return results

    def expand(self, command: str) -> str:
        """
        Expand history references in command.

        Supports: !! (last), !n (number), !-n (relative), !string (prefix)
        """
        if not command or '!' not in command:
            return command

        # Handle !! (last command)
        if '!!' in command:
            last_cmd = self.get_last()
            if last_cmd:
                command = command.replace('!!', last_cmd)
            else:
                raise ValueError("!!: event not found")

        # Handle !n and !-n
        pattern = r'!(-?\d+)'
        matches = re.findall(pattern, command)
        for match in matches:
            index = int(match)
            if index < 0:
                index = len(self.history) + index + 1
            expanded = self.get(index)
            if expanded:
                command = command.replace(f'!{match}', expanded)
            else:
                raise ValueError(f"!{match}: event not found")

        # Handle !string (most recent command starting with string)
        pattern = r'!([a-zA-Z]\w*)'
        matches = re.findall(pattern, command)
        for match in matches:
            for cmd in reversed(self.history):
                if cmd.startswith(match):
                    command = command.replace(f'!{match}', cmd)
                    break
            else:
                raise ValueError(f"!{match}: event not found")

        return command

    def display(self, max_entries: Optional[int] = None) -> str:
        """Format history for display."""
        entries = self.history if max_entries is None else self.history[-max_entries:]
        lines = []
        start_index = len(self.history) - len(entries) + 1
        for i, cmd in enumerate(entries, start_index):
            lines.append(f"{i:5d}  {cmd}")
        return '\n'.join(lines)


class AliasManager:
    """
    Manages command aliases with persistence.
    """

    def __init__(self, alias_file: str):
        """Initialize alias manager."""
        self.alias_file = alias_file
        self.aliases: Dict[str, str] = {}
        self._load_aliases()

    def _load_aliases(self):
        """Load aliases from file."""
        try:
            if os.path.exists(self.alias_file):
                with open(self.alias_file, 'r') as f:
                    self.aliases = json.load(f)
        except (IOError, json.JSONDecodeError):
            pass

    def save_aliases(self):
        """Save aliases to file."""
        try:
            with open(self.alias_file, 'w') as f:
                json.dump(self.aliases, f, indent=2)
        except IOError:
            pass

    def add(self, name: str, command: str):
        """Add an alias."""
        self.aliases[name] = command
        self.save_aliases()

    def remove(self, name: str) -> bool:
        """Remove an alias. Returns True if removed."""
        if name in self.aliases:
            del self.aliases[name]
            self.save_aliases()
            return True
        return False

    def expand(self, command_line: str) -> str:
        """Expand aliases in command line."""
        parts = command_line.split(None, 1)
        if not parts:
            return command_line
        first_word = parts[0]
        if first_word in self.aliases:
            expanded = self.aliases[first_word]
            if len(parts) > 1:
                return expanded + ' ' + parts[1]
            else:
                return expanded
        return command_line

    def list_aliases(self) -> str:
        """Format aliases for display."""
        if not self.aliases:
            return "No aliases defined"
        lines = []
        for name, command in sorted(self.aliases.items()):
            lines.append(f"alias {name}='{command}'")
        return '\n'.join(lines)


class TabCompleter:
    """
    Provides tab completion for commands and file paths.
    """

    def __init__(self, shell: DagShell, aliases: Dict[str, str]):
        """Initialize tab completer."""
        self.shell = shell
        self.aliases = aliases
        self._command_cache = self._build_command_cache()

    def _build_command_cache(self) -> List[str]:
        """Build cache of available commands."""
        commands = []
        for attr_name in dir(self.shell):
            if not attr_name.startswith('_'):
                attr = getattr(self.shell, attr_name)
                if callable(attr):
                    commands.append(attr_name)
        commands.extend(['help', 'clear', 'exit', 'quit', 'history', 'alias', 'unalias'])
        commands.extend(self.aliases.keys())
        return sorted(set(commands))

    def complete(self, text: str, state: int) -> Optional[str]:
        """Readline completion function."""
        line = readline.get_line_buffer()
        begin = readline.get_begidx()

        if begin == 0:
            matches = self._complete_command(text)
        else:
            matches = self._complete_path(text, line)

        try:
            return matches[state]
        except IndexError:
            return None

    def _complete_command(self, text: str) -> List[str]:
        """Complete command names."""
        if not text:
            return self._command_cache
        return [cmd for cmd in self._command_cache if cmd.startswith(text)]

    def _complete_path(self, text: str, line: str) -> List[str]:
        """Complete file paths in the virtual filesystem."""
        if text.startswith('/'):
            dir_path = os.path.dirname(text) or '/'
            prefix = os.path.basename(text)
        else:
            if '/' in text:
                dir_path = os.path.dirname(text)
                prefix = os.path.basename(text)
            else:
                dir_path = '.'
                prefix = text

        matches = []
        current_dir = self.shell._cwd
        if dir_path == '.':
            search_dir = current_dir
        elif dir_path.startswith('/'):
            search_dir = dir_path
        else:
            search_dir = os.path.join(current_dir, dir_path)

        try:
            result = self.shell.cd(search_dir).ls()
            if result and result.data:
                entries = result.data if isinstance(result.data, list) else result.text.strip().split('\n')
                for entry_name in entries:
                    if not entry_name or entry_name in ['.', '..']:
                        continue
                    if entry_name.startswith(prefix):
                        if text.startswith('/'):
                            full_path = os.path.join(dir_path, entry_name)
                        elif '/' in text:
                            full_path = os.path.join(dir_path, entry_name)
                        else:
                            full_path = entry_name
                        entry_full_path = os.path.join(search_dir, entry_name)
                        if self.shell.fs.stat(entry_full_path) and self.shell.fs.stat(entry_full_path).get('type') == 'dir':
                            full_path += '/'
                        matches.append(full_path)
            self.shell.cd(current_dir)
        except:
            pass

        return sorted(matches)


class CommandExecutor:
    """
    Executes parsed commands by translating them to fluent API calls.

    This class bridges the gap between parsed command structures
    and the fluent API, handling the translation of flags and
    arguments into appropriate method calls.
    """

    def __init__(self, shell: DagShell):
        """Initialize with a DagShell instance."""
        self.shell = shell

    def execute(self, command_group: CommandGroup) -> CommandResult:
        """Execute a CommandGroup and return the final result."""
        last_result = None
        last_exit_code = 0

        for pipeline, operator in command_group.pipelines:
            # Execute the pipeline
            result = self._execute_pipeline(pipeline)

            # Handle operators
            if operator == '&&':
                # Execute next only if this succeeded
                if result.exit_code != 0:
                    break
            elif operator == '||':
                # Execute next only if this failed
                if result.exit_code == 0:
                    break
            # For ';' and '&', always continue

            last_result = result
            last_exit_code = result.exit_code

        return last_result or CommandResult(data='', text='', exit_code=0)

    def _execute_pipeline(self, pipeline: Pipeline) -> CommandResult:
        """Execute a pipeline of commands."""
        if not pipeline.commands:
            return CommandResult(data='', text='', exit_code=0)

        # Execute first command
        result = self._execute_command(pipeline.commands[0])

        # Chain through remaining commands
        for cmd in pipeline.commands[1:]:
            # Store result in shell's last_result for piping
            self.shell._last_result = result
            result = self._execute_command(cmd)

        return result

    def _execute_command(self, command: Command) -> CommandResult:
        """Execute a single command by calling the appropriate shell method."""

        # Check for help flags first
        # Note: don't treat -h as help for commands that use -h for other purposes
        commands_with_h_flag = {'du', 'ls', 'df'}  # -h means human-readable
        is_help = '--help' in command.flags or 'help' in command.flags
        if not is_help and 'h' in command.flags and command.name not in commands_with_h_flag:
            is_help = True
        if is_help:
            return self._show_command_help(command.name)

        # Map command name to shell method
        method = self._get_shell_method(command.name)

        if method is None:
            return CommandResult(
                data='',
                text=f"-bash: {command.name}: command not found",
                exit_code=127
            )

        # Prepare arguments based on command type
        args, kwargs = self._prepare_arguments(command)

        # Execute the command
        try:
            result = method(*args, **kwargs)

            # Handle DagShell returns (for commands like cd, mkdir)
            if isinstance(result, DagShell):
                # These commands modify state but don't produce output
                result = CommandResult(data='', text='', exit_code=0)
            elif not isinstance(result, CommandResult):
                # Wrap non-CommandResult returns
                result = CommandResult(data=result, text=str(result), exit_code=0)

            # Handle redirections
            for redirect in command.redirects:
                result = self._apply_redirection(result, redirect)

            return result

        except Exception as e:
            return CommandResult(
                data='',
                text=f"{command.name}: {str(e)}",
                exit_code=1
            )


    def _show_help(self, command: Optional[str] = None) -> CommandResult:
        """Show help information for commands."""
        if command:
            # Show help for specific command
            return self._show_command_help(command)
        else:
            # Show general help with all commands
            return self._show_all_commands_help()

    def _extract_docstring_sections(self, docstring: str) -> dict:
        """Extract structured sections from a docstring."""
        if not docstring:
            return {}

        lines = docstring.strip().split('\n')
        sections = {
            'description': '',
            'usage': '',
            'options': [],
            'examples': []
        }

        # First line is always the description
        if lines:
            sections['description'] = lines[0].strip()

        current_section = None
        section_content = []

        for line in lines[1:]:
            line = line.strip()
            if line.startswith('Usage:'):
                current_section = 'usage'
                section_content = []
            elif line.startswith('Options:'):
                current_section = 'options'
                section_content = []
            elif line.startswith('Examples:'):
                current_section = 'examples'
                section_content = []
            elif line.startswith('Returns:'):
                current_section = 'returns'
                section_content = []
            elif line and current_section:
                section_content.append(line)
                if current_section == 'usage':
                    sections['usage'] = line
                elif current_section == 'options':
                    sections['options'].append(line)
                elif current_section == 'examples':
                    sections['examples'].append(line)

        return sections

    def _show_command_help(self, command: str) -> CommandResult:
        """Show detailed help for a specific command."""
        # Get the method from shell
        method = getattr(self.shell, command, None)

        if not method or not callable(method):
            # Check aliases
            if command in ['help', '?']:
                help_text = """help - Show this help system

Usage:
    help [COMMAND]

Options:
    COMMAND                Command to get help for

Examples:
    help                   # Show all commands
    help ls                # Show help for ls command
    help grep              # Show help for grep command"""
                return CommandResult(data=help_text, text=help_text, exit_code=0)
            elif command == 'clear':
                help_text = """clear - Clear the terminal screen

Usage:
    clear

Options:
    None

Examples:
    clear                  # Clear the screen"""
                return CommandResult(data=help_text, text=help_text, exit_code=0)
            elif command in ['exit', 'quit']:
                help_text = """exit/quit - Exit the shell

Usage:
    exit
    quit

Options:
    None

Examples:
    exit                   # Exit the shell
    quit                   # Exit the shell"""
                return CommandResult(data=help_text, text=help_text, exit_code=0)
            else:
                error_text = f"help: no help available for '{command}'"
                return CommandResult(data='', text=error_text, exit_code=1)

        # Get and format the docstring
        docstring = method.__doc__
        if docstring:
            sections = self._extract_docstring_sections(docstring)

            # Format the help text
            help_lines = []
            help_lines.append(f"{command} - {sections['description']}")
            help_lines.append("")

            if sections['usage']:
                help_lines.append("Usage:")
                help_lines.append(f"    {sections['usage']}")
                help_lines.append("")

            if sections['options']:
                help_lines.append("Options:")
                for opt in sections['options']:
                    help_lines.append(f"    {opt}")
                help_lines.append("")

            if sections['examples']:
                help_lines.append("Examples:")
                for ex in sections['examples']:
                    help_lines.append(f"    {ex}")
                help_lines.append("")

            help_text = '\n'.join(help_lines)
        else:
            help_text = f"{command} - No documentation available"

        return CommandResult(data=help_text, text=help_text, exit_code=0)

    def _show_all_commands_help(self) -> CommandResult:
        """Show a list of all available commands with brief descriptions."""
        # Get all command methods from shell
        commands = {}

        # Get methods from DagShell class
        for attr_name in dir(self.shell):
            if not attr_name.startswith('_'):
                attr = getattr(self.shell, attr_name)
                if callable(attr) and hasattr(attr, '__doc__'):
                    doc = attr.__doc__
                    if doc:
                        # Extract first line of docstring
                        first_line = doc.strip().split('\n')[0]
                        commands[attr_name] = first_line

        # Add special terminal commands
        special_commands = {
            'help': 'Show this help system',
            'clear': 'Clear the terminal screen',
            'exit': 'Exit the shell',
            'quit': 'Exit the shell (alias for exit)'
        }
        commands.update(special_commands)

        # Format the help text
        help_lines = []
        help_lines.append("DagShell Terminal - Available Commands")
        help_lines.append("="*40)
        help_lines.append("")
        help_lines.append("Type 'help COMMAND' for detailed help on a specific command.")
        help_lines.append("")

        # Group commands by category
        categories = {
            'NAVIGATION': ['cd', 'pwd', 'ls'],
            'FILE OPERATIONS': ['cat', 'touch', 'cp', 'mv', 'rm', 'mkdir'],
            'TEXT PROCESSING': ['echo', 'grep', 'head', 'tail', 'sort', 'uniq', 'wc'],
            'SEARCH': ['find'],
            'ENVIRONMENT': ['env', 'setenv', 'whoami', 'su'],
            'PERSISTENCE': ['save', 'load', 'commit', 'export'],
            'PIPING': ['tee', 'pipe'],
            'SYSTEM': ['clear', 'help', 'exit', 'quit']
        }

        for category, cmd_list in categories.items():
            category_commands = [(cmd, commands.get(cmd, '')) for cmd in cmd_list if cmd in commands]
            if category_commands:
                help_lines.append(f"{category}:")
                for cmd, desc in sorted(category_commands):
                    # Format with proper spacing
                    help_lines.append(f"  {cmd:<15} {desc}")
                help_lines.append("")

        # Add any commands not in categories
        uncategorized = []
        categorized_cmds = set()
        for cmd_list in categories.values():
            categorized_cmds.update(cmd_list)

        for cmd, desc in sorted(commands.items()):
            if cmd not in categorized_cmds and cmd not in ['xargs', 'pipe']:
                uncategorized.append((cmd, desc))

        if uncategorized:
            help_lines.append("OTHER:")
            for cmd, desc in uncategorized:
                help_lines.append(f"  {cmd:<15} {desc}")
            help_lines.append("")

        help_lines.append("REDIRECTION AND PIPING:")
        help_lines.append("  command > file     Redirect output to file")
        help_lines.append("  command >> file    Append output to file")
        help_lines.append("  cmd1 | cmd2        Pipe output of cmd1 to cmd2")
        help_lines.append("")
        help_lines.append("SLASH COMMANDS:")
        help_lines.append("  /help              Show slash command help")
        help_lines.append("  /status            Show filesystem statistics")
        help_lines.append("  /import            Import files from host")
        help_lines.append("  /export            Export files to host")
        help_lines.append("  /save              Save state to JSON")
        help_lines.append("  /load              Load state from JSON")
        help_lines.append("")
        help_lines.append("Note: The filesystem is virtual and in-memory.")
        help_lines.append("Use 'save' to persist to JSON, 'export' to write to real filesystem.")

        help_text = '\n'.join(help_lines)
        return CommandResult(data=help_text, text=help_text, exit_code=0)

    def _get_shell_method(self, command_name: str):
        """Get the shell method for a command name."""
        # Direct method mapping
        method = getattr(self.shell, command_name, None)
        if method and callable(method):
            return method

        # Handle special cases and aliases
        aliases = {
            'clear': lambda: CommandResult(data='', text='\033[2J\033[H', exit_code=0),
            'exit': lambda: CommandResult(data='', text='exit', exit_code=0),
            'quit': lambda: CommandResult(data='', text='exit', exit_code=0),
            'help': lambda *args: self._show_help(args[0] if args else None),
            '?': lambda *args: self._show_help(args[0] if args else None),
            'su': lambda *args: self._su(args[0] if args else 'root'),
            'export': lambda *args: self._export(args[0] if args else 'export'),
            'scheme': lambda *args: self._run_scheme_command(args),
        }

        return aliases.get(command_name)

    def _prepare_arguments(self, command: Command) -> Tuple[List, Dict]:
        """Prepare arguments and keyword arguments for method call."""
        args = []
        kwargs = {}

        # Special handling for different commands
        if command.name == 'help':
            # Handle help with optional command argument
            if command.args:
                args.append(command.args[0])
        elif command.name == 'ls':
            if command.args:
                args.append(command.args[0])
            kwargs.update(command.flags)
        elif command.name in ['head', 'tail']:
            # Handle head/tail arguments
            # head can be called as: head -n 5, head -5, or head 5
            n_value = 10  # default

            # Check for various flag names that might contain the line count
            if 'n' in command.flags:
                n_value = command.flags['n']
            elif 'lines' in command.flags:
                n_value = command.flags['lines']
            # Check for numeric flags like -5
            else:
                for flag_key in command.flags:
                    try:
                        n_value = int(flag_key)
                        break
                    except ValueError:
                        pass

            # First argument is the number of lines
            args.append(n_value)

            # Remaining arguments are file paths
            args.extend(command.args)

            # Don't pass flags as kwargs since we handled them
            return args, {}

        elif command.name == 'cd':
            if command.args:
                args.append(command.args[0])

        elif command.name == 'cat':
            args.extend(command.args)

        elif command.name == 'echo':
            args.extend(command.args)
            kwargs.update(command.flags)

        elif command.name == 'grep':
            if command.args:
                args.append(command.args[0])  # pattern
                args.extend(command.args[1:])  # files
            kwargs.update(command.flags)

        elif command.name in ['head', 'tail']:
            # Handle -n flag
            if 'lines' in command.flags:
                args.append(command.flags['lines'])
                del command.flags['lines']
            elif 'n' in command.flags:
                args.append(command.flags['n'])
                del command.flags['n']
            args.extend(command.args)
            kwargs.update(command.flags)

        elif command.name == 'wc':
            args.extend(command.args)
            kwargs.update(command.flags)

        elif command.name == 'sort':
            args.extend(command.args)
            kwargs.update(command.flags)

        elif command.name == 'uniq':
            args.extend(command.args)
            kwargs.update(command.flags)

        elif command.name == 'find':
            if command.args:
                args.append(command.args[0])  # path
            # Handle find-specific flags
            for key, value in command.flags.items():
                if key == 'type':
                    kwargs['type'] = value
                elif key == 'name' and len(command.args) > 1:
                    kwargs['name'] = command.args[1]

        elif command.name == 'mkdir':
            if command.args:
                args.append(command.args[0])
            kwargs.update(command.flags)

        elif command.name == 'touch':
            if command.args:
                args.append(command.args[0])

        elif command.name == 'rm':
            if command.args:
                args.append(command.args[0])
            kwargs.update(command.flags)

        elif command.name == 'cp':
            args.extend(command.args[:2])  # src, dst

        elif command.name == 'mv':
            args.extend(command.args[:2])  # src, dst

        elif command.name == 'ln':
            # ln [-s] source dest
            args.extend(command.args[:2])  # source, dest
            if 's' in command.flags or 'symbolic' in command.flags:
                kwargs['symbolic'] = True

        elif command.name == 'chmod':
            # chmod mode path
            if len(command.args) >= 2:
                args.append(command.args[0])  # mode
                args.append(command.args[1])  # path

        elif command.name == 'chown':
            # chown owner[:group] path
            if len(command.args) >= 2:
                args.append(command.args[0])  # owner
                args.append(command.args[1])  # path

        elif command.name == 'diff':
            # diff [-u] file1 file2
            args.extend(command.args[:2])  # file1, file2
            if 'u' in command.flags or 'unified' in command.flags:
                kwargs['unified'] = True
            if 'context' in command.flags:
                kwargs['context'] = command.flags['context']
            elif 'c' in command.flags:
                kwargs['context'] = command.flags['c']

        elif command.name == 'cut':
            # cut -d DELIM -f FIELDS [file...]
            if 'delimiter' in command.flags:
                kwargs['delimiter'] = command.flags['delimiter']
            elif 'd' in command.flags:
                kwargs['delimiter'] = command.flags['d']
            if 'fields' in command.flags:
                kwargs['fields'] = command.flags['fields']
            elif 'f' in command.flags:
                kwargs['fields'] = command.flags['f']
            args.extend(command.args)

        elif command.name == 'tr':
            # tr set1 set2
            args.extend(command.args[:2])

        elif command.name == 'du':
            # du [-h] [path...]
            if 'h' in command.flags or 'human_readable' in command.flags or 'human-readable' in command.flags:
                kwargs['human_readable'] = True
            args.extend(command.args)

        elif command.name == 'stat':
            # stat path
            if command.args:
                args.append(command.args[0])

        elif command.name == 'readlink':
            # readlink path
            if command.args:
                args.append(command.args[0])

        elif command.name == 'id':
            # id [username]
            if command.args:
                args.append(command.args[0])

        elif command.name == 'basename':
            # basename path [suffix]
            if command.args:
                args.append(command.args[0])
                if len(command.args) > 1:
                    args.append(command.args[1])

        elif command.name == 'dirname':
            # dirname path
            if command.args:
                args.append(command.args[0])

        elif command.name == 'xargs':
            # xargs command [args...]
            if command.args:
                args.append(command.args[0])  # command
                args.extend(command.args[1:])  # additional args
            if 'n' in command.flags:
                kwargs['max_args'] = command.flags['n']

        elif command.name == 'pwd':
            pass  # No arguments

        elif command.name == 'env':
            if command.args:
                args.append(command.args[0])

        elif command.name == 'tee':
            if command.args:
                args.append(command.args[0])

        else:
            # Default: pass all arguments
            args.extend(command.args)
            kwargs.update(command.flags)

        return args, kwargs

    def _apply_redirection(self, result: CommandResult, redirect: Redirect) -> CommandResult:
        """Apply a redirection to a command result."""
        if redirect.type == RedirectType.WRITE:
            # Overwrite file
            result.out(redirect.target)
            # Clear the text output since it's been redirected
            result.text = ''
        elif redirect.type == RedirectType.APPEND:
            # Append to file
            result.append(redirect.target)
            # Clear the text output since it's been redirected
            result.text = ''
        # TODO: Handle other redirection types (INPUT, etc.)

        return result

    def _run_scheme_command(self, args) -> CommandResult:
        """Run a Scheme script or expression."""
        from .scheme_interpreter import SchemeREPL

        try:
            repl = SchemeREPL()

            if args and args[0]:
                script_path = args[0]
                # Run script from virtual filesystem
                if script_path.endswith('.scm'):
                    # Resolve relative paths using the shell's resolver
                    resolved_path = self.shell._resolve_path(script_path)
                    # Read script from virtual FS
                    content = self.shell.fs.read(resolved_path)
                    if content is None:
                        return CommandResult(
                            data='',
                            text=f"scheme: {script_path}: No such file",
                            exit_code=1
                        )

                    code = content.decode('utf-8')
                else:
                    # Treat argument as inline code
                    code = script_path

                # Execute the Scheme code
                result = repl.eval_string(code)

                # Format result for display
                if result is not None:
                    if isinstance(result, bool):
                        text = "#t" if result else "#f"
                    elif isinstance(result, list):
                        text = repl._list_to_string(result)
                    else:
                        text = str(result)
                else:
                    text = ""

                return CommandResult(data=result, text=text, exit_code=0)
            else:
                # No script provided, show usage
                help_text = """scheme - Run Scheme code or scripts

Usage:
    scheme SCRIPT.scm          Run a Scheme script file
    scheme "(expression)"      Evaluate a Scheme expression

Examples:
    scheme /project/build.scm
    scheme "(ls)"
    scheme "(mkdir '/test')"

For interactive REPL, run: python scheme"""
                return CommandResult(data=help_text, text=help_text, exit_code=0)

        except Exception as e:
            error = f"Scheme error: {e}"
            return CommandResult(data=error, text=error, exit_code=1)


class CommandHistory:
    """Manages command history for the terminal session."""

    def __init__(self, max_size: int = 1000):
        """Initialize with maximum history size."""
        self.max_size = max_size
        self.history: List[str] = []
        self.position = 0

    def add(self, command: str):
        """Add a command to history."""
        if command and command.strip():
            self.history.append(command)
            if len(self.history) > self.max_size:
                self.history.pop(0)
        self.position = len(self.history)

    def previous(self) -> Optional[str]:
        """Get previous command in history."""
        if self.position > 0:
            self.position -= 1
            return self.history[self.position]
        return None

    def next(self) -> Optional[str]:
        """Get next command in history."""
        if self.position < len(self.history) - 1:
            self.position += 1
            return self.history[self.position]
        elif self.position == len(self.history) - 1:
            self.position += 1
            return ''
        return ''


class TerminalSession:
    """
    Main terminal session manager.

    This class provides the REPL loop and manages the terminal session,
    including prompt display, command execution, and session state.
    Features include readline integration, history expansion, tab completion,
    and command aliases.
    """

    def __init__(self, config: Optional[TerminalConfig] = None,
                 shell: Optional[DagShell] = None,
                 fs: Optional['FileSystem'] = None):
        """Initialize terminal session."""
        self.config = config or TerminalConfig()
        if shell:
            self.shell = shell
        elif fs:
            self.shell = DagShell(fs=fs)
        else:
            self.shell = DagShell()
        self.parser = CommandParser()
        self.executor = CommandExecutor(self.shell)
        self.history = CommandHistory(self.config.history_size)
        self.running = False

        # User context
        self.current_user = self.config.user
        self.uid, self.gid = self.shell.fs.lookup_user(self.current_user)
        self.groups = self.shell.fs.get_user_groups(self.current_user)
        self.strict_permissions = False  # Can be enabled for permission checking

        # Enhanced terminal components
        self.history_manager = HistoryManager(
            self.config.history_file,
            self.config.history_max_size
        )
        self.alias_manager = AliasManager(self.config.alias_file)

        # Setup readline and register cleanup
        self._setup_readline()
        atexit.register(self._cleanup)

        # Initialize shell environment
        self._init_environment()

    def _setup_readline(self):
        """Configure readline for terminal."""
        if self.config.enable_tab_completion:
            self.tab_completer = TabCompleter(self.shell, self.alias_manager.aliases)
            readline.set_completer(self.tab_completer.complete)
            readline.parse_and_bind('tab: complete')
        readline.parse_and_bind('set editing-mode emacs')
        readline.set_history_length(self.config.history_max_size)

    def _cleanup(self):
        """Clean up on exit."""
        self.history_manager.save_history()
        self.alias_manager.save_aliases()

    def _init_environment(self):
        """Initialize the shell environment."""
        self.shell.setenv('USER', self.config.user)
        self.shell.setenv('HOME', self.config.home_dir)
        self.shell.setenv('HOSTNAME', self.config.hostname)

        # Set initial directory
        if self.config.initial_dir:
            self.shell.cd(self.config.initial_dir)

    def _whoami(self) -> CommandResult:
        """Return current username."""
        return CommandResult(data=self.current_user, text=self.current_user, exit_code=0)

    def _su(self, username: str) -> CommandResult:
        """Switch user."""
        # Check if user exists
        uid, gid = self.shell.fs.lookup_user(username)
        if uid == 1000 and username not in ['user', 'alice', 'bob', 'root']:
            return CommandResult(
                data='',
                text=f"su: user '{username}' does not exist",
                exit_code=1
            )

        # Switch user
        self.current_user = username
        self.uid, self.gid = uid, gid
        self.groups = self.shell.fs.get_user_groups(username)
        self.shell.setenv('USER', username)

        # Change to user's home directory
        home = f"/home/{username}" if username != 'root' else "/root"
        if self.shell.fs.exists(home):
            self.shell.cd(home)
            self.shell.setenv('HOME', home)

        return CommandResult(data='', text='', exit_code=0)

    def _export(self, target_path: str) -> CommandResult:
        """Export virtual filesystem to real filesystem."""
        try:
            exported = self.shell.fs.export_to_real(target_path)
            result = f"Exported {exported} files/directories to {target_path}"
            return CommandResult(data=exported, text=result, exit_code=0)
        except Exception as e:
            error = f"Export failed: {e}"
            return CommandResult(data='', text=error, exit_code=1)

    # Slash command handlers

    def _execute_slash_command(self, command_line: str) -> str:
        """Execute a slash command."""
        parts = command_line[1:].split(None, 2)  # Remove leading / and split
        if not parts:
            return "Error: empty slash command"

        cmd = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []

        # Dispatch to appropriate handler
        handlers = {
            'import': self._slash_import,
            'export': self._slash_export,
            'save': self._slash_save,
            'load': self._slash_load,
            'snapshot': self._slash_snapshot,
            'snapshots': self._slash_snapshots,
            'status': self._slash_status,
            'dag': self._slash_dag,
            'nodes': self._slash_nodes,
            'info': self._slash_info,
            'help': self._slash_help,
            'aliases': self._slash_aliases,
        }

        handler = handlers.get(cmd)
        if handler:
            try:
                return handler(args)
            except Exception as e:
                return f"Error in /{cmd}: {e}"
        else:
            return f"Unknown slash command: /{cmd}\nType /help for available commands"

    def _resolve_host_path(self, path: str) -> str:
        """Resolve and validate a host path against safe_host_directory."""
        if self.config.safe_host_directory is None:
            raise ValueError("Host file operations not configured. Set safe_host_directory in config.")

        # Make safe directory absolute
        safe_dir = os.path.abspath(self.config.safe_host_directory)

        # If path is relative, join with safe directory
        if not os.path.isabs(path):
            resolved = os.path.abspath(os.path.join(safe_dir, path))
        else:
            resolved = os.path.abspath(path)

        # Check if resolved path is within safe directory
        if not resolved.startswith(safe_dir):
            raise ValueError(f"Path '{path}' is outside safe directory '{safe_dir}'")

        return resolved

    def _slash_import(self, args: List[str]) -> str:
        """Import file/directory from host filesystem."""
        if len(args) < 2:
            return "Usage: /import <host-path> <dagshell-path>"

        host_path = args[0]
        dagshell_path = args[1]

        try:
            # Resolve host path
            resolved_host = self._resolve_host_path(host_path)

            # Import into virtual filesystem
            imported = self.shell.fs.import_from_real(
                resolved_host,
                dagshell_path,
                preserve_permissions=True,
                uid=self.uid,
                gid=self.gid
            )

            return f"Imported {imported} items from {resolved_host} to {dagshell_path}"
        except Exception as e:
            return f"Import failed: {e}"

    def _slash_export(self, args: List[str]) -> str:
        """Export file/directory to host filesystem."""
        if len(args) < 2:
            return "Usage: /export <dagshell-path> <host-path>"

        dagshell_path = args[0]
        host_path = args[1]

        try:
            # Check if dagshell path exists
            if not self.shell.fs.exists(dagshell_path):
                return f"Error: Path not found in dagshell: {dagshell_path}"

            # Resolve host path
            resolved_host = self._resolve_host_path(host_path)

            # For now, we'll export the entire filesystem to the host path
            # TODO: Implement selective export for specific paths
            exported = self.shell.fs.export_to_real(resolved_host)

            return f"Exported {exported} items to {resolved_host}"
        except Exception as e:
            return f"Export failed: {e}"

    def _slash_save(self, args: List[str]) -> str:
        """Save state to JSON file."""
        filename = args[0] if args else 'dagshell-state.json'

        try:
            # Resolve path
            if self.config.safe_host_directory:
                filepath = self._resolve_host_path(filename)
            else:
                filepath = filename

            # Save state
            import builtins
            with builtins.open(filepath, 'w') as f:
                f.write(self.shell.fs.to_json())

            return f"State saved to {filepath}"
        except Exception as e:
            return f"Save failed: {e}"

    def _slash_load(self, args: List[str]) -> str:
        """Load state from JSON file."""
        if not args:
            return "Usage: /load <filename>"

        filename = args[0]

        try:
            # Resolve path
            if self.config.safe_host_directory:
                filepath = self._resolve_host_path(filename)
            else:
                filepath = filename

            # Load state
            import builtins
            with builtins.open(filepath, 'r') as f:
                json_str = f.read()

            from .dagshell import FileSystem
            self.shell.fs = FileSystem.from_json(json_str)

            return f"State loaded from {filepath}"
        except Exception as e:
            return f"Load failed: {e}"

    def _slash_snapshot(self, args: List[str]) -> str:
        """Create named snapshot of current state."""
        if not args:
            return "Usage: /snapshot <name>"

        name = args[0]

        try:
            # Create snapshots directory if needed
            snapshots_dir = self.config.snapshots_directory
            os.makedirs(snapshots_dir, exist_ok=True)

            # Create snapshot filename with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{name}_{timestamp}.json"
            filepath = os.path.join(snapshots_dir, filename)

            # Save snapshot
            import builtins
            with builtins.open(filepath, 'w') as f:
                f.write(self.shell.fs.to_json())

            return f"Snapshot '{name}' saved to {filepath}"
        except Exception as e:
            return f"Snapshot failed: {e}"

    def _slash_snapshots(self, args: List[str]) -> str:
        """List available snapshots."""
        try:
            snapshots_dir = self.config.snapshots_directory

            if not os.path.exists(snapshots_dir):
                return "No snapshots found"

            # List snapshot files
            import builtins
            snapshots = []
            for filename in os.listdir(snapshots_dir):
                if filename.endswith('.json'):
                    filepath = os.path.join(snapshots_dir, filename)
                    stat = os.stat(filepath)
                    size = stat.st_size
                    mtime = datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                    snapshots.append(f"{filename:50s} {size:>10d} bytes  {mtime}")

            if not snapshots:
                return "No snapshots found"

            return "Available snapshots:\n" + "\n".join(snapshots)
        except Exception as e:
            return f"Error listing snapshots: {e}"

    def _slash_status(self, args: List[str]) -> str:
        """Show filesystem status."""
        fs = self.shell.fs

        # Count different types
        file_count = 0
        dir_count = 0
        total_size = 0

        for path in fs.paths:
            if path in fs.deleted:
                continue
            node_hash = fs.paths[path]
            node = fs.nodes[node_hash]

            if node.is_file():
                file_count += 1
                total_size += len(node.content)
            elif node.is_dir():
                dir_count += 1

        # Format size
        if total_size < 1024:
            size_str = f"{total_size} bytes"
        elif total_size < 1024 * 1024:
            size_str = f"{total_size / 1024:.1f} KB"
        else:
            size_str = f"{total_size / (1024 * 1024):.1f} MB"

        return f"""Filesystem Status:
  Total nodes:     {len(fs.nodes)}
  Files:           {file_count}
  Directories:     {dir_count}
  Total paths:     {len(fs.paths)}
  Deleted paths:   {len(fs.deleted)}
  Total size:      {size_str}
  Current dir:     {self.shell._cwd}
  Current user:    {self.current_user} (uid={self.uid}, gid={self.gid})"""

    def _slash_dag(self, args: List[str]) -> str:
        """Visualize DAG structure."""
        # Simple ASCII visualization
        fs = self.shell.fs

        lines = ["DAG Structure (content-addressed nodes):", ""]

        # Show a sample of nodes
        node_sample = list(fs.nodes.items())[:20]
        for node_hash, node in node_sample:
            node_type = "FILE" if node.is_file() else "DIR"
            paths = [p for p, h in fs.paths.items() if h == node_hash and p not in fs.deleted]
            paths_str = ", ".join(paths[:3])
            if len(paths) > 3:
                paths_str += f" ... ({len(paths)} total)"

            lines.append(f"  {node_hash[:12]}... [{node_type}] -> {paths_str}")

        if len(fs.nodes) > 20:
            lines.append(f"\n  ... and {len(fs.nodes) - 20} more nodes")

        return "\n".join(lines)

    def _slash_nodes(self, args: List[str]) -> str:
        """List nodes with optional pattern filter."""
        fs = self.shell.fs
        pattern = args[0] if args else None

        lines = ["Content-addressed nodes:", ""]

        for node_hash, node in fs.nodes.items():
            # Filter by pattern if provided
            if pattern and pattern.lower() not in node_hash.lower():
                continue

            node_type = "FILE" if node.is_file() else "DIR "
            size = len(node.content) if node.is_file() else 0
            mode = oct(node.mode & 0o777)

            paths = [p for p, h in fs.paths.items() if h == node_hash and p not in fs.deleted]
            if paths:
                paths_str = ", ".join(paths[:2])
                if len(paths) > 2:
                    paths_str += "..."
            else:
                paths_str = "(unreferenced)"

            lines.append(f"  {node_hash[:12]}  [{node_type}]  {mode:>6s}  {size:>8d}  {paths_str}")

        return "\n".join(lines)

    def _slash_info(self, args: List[str]) -> str:
        """Show detailed node information."""
        if not args:
            return "Usage: /info <node-hash-prefix>"

        prefix = args[0]
        fs = self.shell.fs

        # Find matching nodes
        matches = [h for h in fs.nodes.keys() if h.startswith(prefix)]

        if not matches:
            return f"No node found matching: {prefix}"

        if len(matches) > 1:
            return f"Ambiguous prefix. Matches: {', '.join([m[:12] for m in matches])}"

        # Show node details
        node_hash = matches[0]
        node = fs.nodes[node_hash]

        lines = [
            f"Node Information:",
            f"  Hash:        {node_hash}",
            f"  Type:        {'FILE' if node.is_file() else 'DIRECTORY'}",
            f"  Mode:        {oct(node.mode)} ({oct(node.mode & 0o777)} permissions)",
            f"  Owner:       uid={node.uid}, gid={node.gid}",
            f"  Modified:    {datetime.fromtimestamp(node.mtime).strftime('%Y-%m-%d %H:%M:%S')}",
        ]

        if node.is_file():
            lines.append(f"  Size:        {len(node.content)} bytes")
            # Show first few bytes as preview
            preview = node.content[:100]
            try:
                preview_str = preview.decode('utf-8', errors='replace')
                lines.append(f"  Preview:     {repr(preview_str)}")
            except:
                lines.append(f"  Preview:     (binary data)")

        # Show paths
        paths = [p for p, h in fs.paths.items() if h == node_hash]
        lines.append(f"  Paths ({len(paths)}):")
        for path in paths[:10]:
            deleted = " (deleted)" if path in fs.deleted else ""
            lines.append(f"    {path}{deleted}")
        if len(paths) > 10:
            lines.append(f"    ... and {len(paths) - 10} more")

        return "\n".join(lines)

    def _slash_help(self, args: List[str]) -> str:
        """Show slash command help."""
        return """Slash Commands:

Host File Operations:
  /import <host-path> <dagshell-path>  Import file/directory from host
  /export <dagshell-path> <host-path>  Export file/directory to host

State Management:
  /save [filename]                     Save state to JSON (default: dagshell-state.json)
  /load <filename>                     Load state from JSON file
  /snapshot <name>                     Create named snapshot with timestamp
  /snapshots                           List available snapshots

DAG/Filesystem Inspection:
  /status                              Show filesystem statistics
  /dag                                 Visualize DAG structure
  /nodes [pattern]                     List nodes (optionally filtered by pattern)
  /info <node-hash>                    Show detailed node information

Meta Commands:
  /help                                Show this help
  /aliases                             List command aliases

Note: Host file operations require safe_host_directory to be configured."""

    def _slash_aliases(self, args: List[str]) -> str:
        """List command aliases."""
        return self.alias_manager.list_aliases()

    def _handle_alias_command(self, command_line: str) -> str:
        """Handle alias creation command."""
        parts = command_line.split(None, 1)
        if len(parts) < 2:
            return "alias: usage: alias name=command"
        alias_def = parts[1]
        if '=' not in alias_def:
            return "alias: usage: alias name=command"
        name, command = alias_def.split('=', 1)
        name = name.strip()
        command = command.strip()
        # Remove quotes if present
        if command.startswith('"') and command.endswith('"'):
            command = command[1:-1]
        elif command.startswith("'") and command.endswith("'"):
            command = command[1:-1]
        self.alias_manager.add(name, command)
        # Update tab completer
        if hasattr(self, 'tab_completer'):
            self.tab_completer.aliases = self.alias_manager.aliases
            self.tab_completer._command_cache = self.tab_completer._build_command_cache()
        return f"alias {name}='{command}'"

    def _handle_unalias_command(self, command_line: str) -> str:
        """Handle alias removal command."""
        parts = command_line.split()
        if len(parts) < 2:
            return "unalias: usage: unalias name"
        name = parts[1]
        if self.alias_manager.remove(name):
            if hasattr(self, 'tab_completer'):
                self.tab_completer.aliases = self.alias_manager.aliases
                self.tab_completer._command_cache = self.tab_completer._build_command_cache()
            return ''
        else:
            return f"unalias: {name}: not found"

    def get_prompt(self) -> str:
        """Generate the command prompt."""
        # Get current directory
        cwd = self.shell._cwd

        # Replace home directory with ~
        home = self.shell._env.get('HOME', '/home/user')
        if cwd.startswith(home):
            display_cwd = '~' + cwd[len(home):]
        else:
            display_cwd = cwd

        # Format prompt
        prompt = self.config.prompt_format.format(
            user=self.current_user,
            hostname=self.config.hostname,
            cwd=display_cwd,
            time=datetime.now().strftime('%H:%M:%S')
        )

        # Add colors if enabled
        if self.config.enable_colors:
            # Green for user@host, blue for path
            prompt = f'\033[32m{self.config.user}@{self.config.hostname}\033[0m:\033[34m{display_cwd}\033[0m$ '

        return prompt

    def execute_command(self, command_line: str) -> Optional[str]:
        """
        Execute a command line and return the output.

        Returns None for exit commands.
        Includes history expansion and alias support.
        """
        # Handle empty input
        if not command_line or command_line.strip() == '':
            return ''

        # Handle clear command
        if command_line.strip() == 'clear':
            os.system('clear' if os.name != 'nt' else 'cls')
            return ''

        # Handle history command
        if command_line.strip() == 'history':
            return self.history_manager.display()
        elif command_line.strip().startswith('history '):
            parts = command_line.split()
            if len(parts) > 1 and parts[1].isdigit():
                return self.history_manager.display(int(parts[1]))
            return self.history_manager.display()

        # Handle alias commands
        if command_line.strip() == 'alias':
            return self.alias_manager.list_aliases()
        elif command_line.strip().startswith('alias '):
            return self._handle_alias_command(command_line)
        elif command_line.strip().startswith('unalias '):
            return self._handle_unalias_command(command_line)

        # Store original for history
        original_command = command_line

        # Expand history references
        if self.config.enable_history_expansion:
            try:
                expanded = self.history_manager.expand(command_line)
                if expanded != command_line:
                    print(expanded)
                    command_line = expanded
            except ValueError as e:
                return str(e)

        # Expand aliases
        command_line = self.alias_manager.expand(command_line)

        # Check for slash commands first
        if command_line.strip().startswith('/'):
            return self._execute_slash_command(command_line.strip())

        # Parse the command
        command_group = self.parser.parse(command_line)

        # Check for special commands
        if command_group.pipelines and command_group.pipelines[0][0].commands:
            first_cmd = command_group.pipelines[0][0].commands[0]

            # Handle exit
            if first_cmd.name in ['exit', 'quit']:
                return None

            # Handle user management commands specially
            if first_cmd.name == 'whoami':
                return self.current_user
            elif first_cmd.name == 'su':
                username = first_cmd.args[0] if first_cmd.args else 'root'
                result = self._su(username)
                return result.text if result.text else ''
            elif first_cmd.name == 'export':
                if not first_cmd.args:
                    return 'export: missing target path'
                result = self._export(first_cmd.args[0])
                return result.text

        # Execute the command normally
        result = self.executor.execute(command_group)

        # Add to history after successful execution (but not history expansion commands)
        if result is not None and not original_command.startswith('!'):
            self.history_manager.add(original_command)

        # Return the text output
        return result.text if result.text else str(result)

    def run_interactive(self):
        """Run the interactive REPL loop with readline support."""
        self.running = True

        # Print welcome message
        print("Welcome to DagShell Terminal")
        print("Features: History (↑/↓), Tab completion, Aliases, History expansion (!!, !n)")
        print("Type 'help' for commands, '/help' for slash commands, 'exit' to quit")
        print()

        while self.running:
            try:
                # Display prompt and get input (readline handles history navigation)
                prompt = self.get_prompt()
                command_line = input(prompt)

                # Add to history manager
                self.history_manager.add(command_line)
                self.history.add(command_line)  # Keep legacy history too

                # Execute command
                output = self.execute_command(command_line)

                # Check for exit
                if output is None:
                    break

                # Display output
                if output:
                    print(output)

            except KeyboardInterrupt:
                print("^C")
                continue
            except EOFError:
                print()
                break
            except Exception as e:
                print(f"Error: {e}")

        # Clean up
        self._cleanup()
        print("Goodbye!")

    def run_command(self, command_line: str) -> str:
        """
        Run a single command and return output.

        This method is useful for non-interactive use.
        """
        output = self.execute_command(command_line)
        return output if output is not None else ''

    def run_script(self, script_lines: List[str]) -> List[str]:
        """
        Run a script (list of command lines) and return outputs.
        """
        outputs = []
        for line in script_lines:
            # Skip comments and empty lines
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            output = self.execute_command(line)
            if output is None:  # Exit command
                break
            outputs.append(output)

        return outputs


def main():
    """Main entry point for terminal emulator.

    Supports three modes:
    1. Interactive mode (default): Full shell session
    2. Command mode (-c): Execute a single command string
    3. One-shot mode: Execute command from positional arguments

    Examples:
        dagshell                           # Interactive mode
        dagshell -i                        # Explicit interactive mode
        dagshell -c "ls -la /home"         # Command mode
        dagshell ls -la /home              # One-shot mode
        dagshell --fs project.json ls /    # With filesystem file
        dagshell --fs project.json --save mkdir /new  # Save after write
    """
    import argparse

    parser = argparse.ArgumentParser(
        description='DagShell - Virtual POSIX filesystem with content-addressable DAG structure',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  dagshell                              Start interactive shell
  dagshell ls -la /home                 One-shot command
  dagshell --fs project.json ls /       Use filesystem from file
  dagshell --fs project.json --save mkdir /new
                                        Save changes back to file
  dagshell -c "mkdir /a && touch /a/b"  Execute command string

Environment:
  DAGSHELL_FS    Default filesystem file (overridden by --fs)
'''
    )

    # Filesystem options
    parser.add_argument('--fs', metavar='FILE',
                        help='Load filesystem from JSON file (default: $DAGSHELL_FS or empty)')
    parser.add_argument('--save', '-s', action='store_true',
                        help='Save filesystem back to source file after execution')
    parser.add_argument('-o', '--output', metavar='FILE',
                        help='Save filesystem to FILE after execution')
    parser.add_argument('--json', action='store_true',
                        help='Output filesystem as JSON to stdout (for pipelines)')

    # Execution mode
    parser.add_argument('-c', '--command', metavar='CMD',
                        help='Execute command string and exit')
    parser.add_argument('-i', '--interactive', action='store_true',
                        help='Force interactive mode even with --fs')

    # Session options
    parser.add_argument('-u', '--user', help='Set username', default=getpass.getuser())
    parser.add_argument('-d', '--directory', help='Set initial directory', default='/')
    parser.add_argument('--no-history', action='store_true',
                        help='Disable history expansion')
    parser.add_argument('--no-completion', action='store_true',
                        help='Disable tab completion')

    # Positional arguments for one-shot mode
    parser.add_argument('args', nargs='*', help='Command and arguments for one-shot mode')

    args = parser.parse_args()

    # Determine filesystem source
    fs_file = args.fs or os.environ.get('DAGSHELL_FS')

    # Determine execution mode
    has_oneshot_cmd = len(args.args) > 0
    has_command_str = args.command is not None
    force_interactive = args.interactive

    # Create filesystem
    from .dagshell import FileSystem
    if fs_file and os.path.exists(fs_file):
        try:
            with open(fs_file, 'r') as f:
                fs = FileSystem.from_json(f.read())
        except Exception as e:
            print(f"dagshell: error loading {fs_file}: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        fs = FileSystem()

    # Create shell with loaded filesystem
    from .dagshell_fluent import DagShell
    shell = DagShell(fs=fs)
    shell.cd(args.directory)

    # One-shot or command mode
    if has_oneshot_cmd or has_command_str:
        # Build command string
        if has_command_str:
            cmd_str = args.command
        else:
            # Join positional args, preserving quotes for args with spaces
            cmd_str = ' '.join(args.args)

        # Execute command
        executor = CommandExecutor(shell)
        parser_obj = CommandParser()

        try:
            parsed = parser_obj.parse(cmd_str)
            result = executor.execute(parsed)

            # Output result
            if args.json:
                # Output filesystem as JSON
                print(shell.fs.to_json())
            elif result and result.text:
                print(result.text)

            # Handle save options
            if args.save and fs_file:
                with open(fs_file, 'w') as f:
                    f.write(shell.fs.to_json())
            if args.output:
                with open(args.output, 'w') as f:
                    f.write(shell.fs.to_json())

            sys.exit(result.exit_code if result else 0)

        except Exception as e:
            print(f"dagshell: {e}", file=sys.stderr)
            sys.exit(1)

    # Interactive mode
    else:
        config = TerminalConfig(
            user=args.user,
            initial_dir=args.directory,
            enable_tab_completion=not args.no_completion,
            enable_history_expansion=not args.no_history
        )
        session = TerminalSession(config=config, fs=fs)
        session.run_interactive()

        # Save after interactive session if requested
        if args.save and fs_file:
            with open(fs_file, 'w') as f:
                f.write(session.shell.fs.to_json())
        if args.output:
            with open(args.output, 'w') as f:
                f.write(session.shell.fs.to_json())


if __name__ == '__main__':
    main()