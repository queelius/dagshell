#!/usr/bin/env python3
"""
Enhanced terminal module for DagShell with readline support and advanced features.

This module provides a complete terminal emulation layer with:
- Readline integration for proper history navigation
- Command history with persistence
- Tab completion for commands and paths
- History expansion (!!, !n)
- Command aliases
- Keyboard shortcuts (Ctrl+C, Ctrl+D, Ctrl+L)

Design Principles:
- Clean separation of concerns
- Composable history management
- Elegant readline integration
- First-class history support
"""

import os
import sys
import readline
import atexit
import signal
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import json

from .terminal import (
    TerminalSession, TerminalConfig, CommandExecutor,
    CommandHistory as BaseCommandHistory
)
from .dagshell_fluent import DagShell, CommandResult
from .command_parser import CommandParser


@dataclass
class EnhancedTerminalConfig(TerminalConfig):
    """Extended configuration for enhanced terminal session."""
    history_file: str = field(default_factory=lambda: str(Path.home() / '.dagshell_history'))
    history_max_size: int = 10000
    enable_tab_completion: bool = True
    enable_history_expansion: bool = True
    aliases: Dict[str, str] = field(default_factory=dict)
    alias_file: str = field(default_factory=lambda: str(Path.home() / '.dagshell_aliases'))


class HistoryManager:
    """
    Manages command history with persistence and expansion.

    This class provides:
    - History persistence to disk
    - History expansion (!!, !n, !-n, !string)
    - Integration with readline library
    - Clean API for history operations
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
                # Clear any existing readline history first
                readline.clear_history()
                # Load from file
                readline.read_history_file(self.history_file)
                # Also load into our internal list
                history_length = readline.get_current_history_length()
                self.history = [
                    readline.get_history_item(i)
                    for i in range(1, history_length + 1)
                    if readline.get_history_item(i)
                ]
        except (IOError, OSError):
            # Start with empty history
            self.history = []
        except AttributeError:
            # readline might not have clear_history on some platforms
            self.history = []

    def save_history(self):
        """Save history to file."""
        try:
            readline.write_history_file(self.history_file)
        except (IOError, OSError):
            pass  # Ignore save errors

    def add(self, command: str):
        """Add a command to history."""
        if command and command.strip():
            # Don't add duplicate consecutive commands
            if not self.history or self.history[-1] != command:
                self.history.append(command)
                readline.add_history(command)

                # Trim history if too long
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

        Supports:
        - !! : last command
        - !n : command number n
        - !-n : n commands ago
        - !string : most recent command starting with string
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
        import re

        # Match !n or !-n
        pattern = r'!(-?\d+)'
        matches = re.findall(pattern, command)
        for match in matches:
            index = int(match)
            if index < 0:
                # Negative index: count from end
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
            # Search backwards for command starting with match
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


class TabCompleter:
    """
    Provides tab completion for commands and file paths.

    This class integrates with readline to provide:
    - Command name completion
    - File path completion
    - Flag completion for known commands
    - Alias expansion
    """

    def __init__(self, shell: DagShell, aliases: Dict[str, str]):
        """Initialize tab completer."""
        self.shell = shell
        self.aliases = aliases
        self._command_cache = self._build_command_cache()

    def _build_command_cache(self) -> List[str]:
        """Build cache of available commands."""
        commands = []

        # Get methods from DagShell
        for attr_name in dir(self.shell):
            if not attr_name.startswith('_'):
                attr = getattr(self.shell, attr_name)
                if callable(attr):
                    commands.append(attr_name)

        # Add special terminal commands
        commands.extend(['help', 'clear', 'exit', 'quit', 'history', 'alias', 'unalias'])

        # Add aliases
        commands.extend(self.aliases.keys())

        return sorted(set(commands))

    def complete(self, text: str, state: int) -> Optional[str]:
        """
        Readline completion function.

        Called by readline to get completions.
        """
        # Get the full line buffer
        line = readline.get_line_buffer()
        begin = readline.get_begidx()

        # Determine what we're completing
        if begin == 0:
            # Completing command name
            matches = self._complete_command(text)
        else:
            # Completing arguments - check if it's a path
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
        # Parse the current directory and partial path
        if text.startswith('/'):
            # Absolute path
            dir_path = os.path.dirname(text) or '/'
            prefix = os.path.basename(text)
        else:
            # Relative path
            if '/' in text:
                dir_path = os.path.dirname(text)
                prefix = os.path.basename(text)
            else:
                dir_path = '.'
                prefix = text

        # Get completions from the virtual filesystem
        matches = []

        # Resolve the directory path
        current_dir = self.shell._cwd
        if dir_path == '.':
            search_dir = current_dir
        elif dir_path.startswith('/'):
            search_dir = dir_path
        else:
            search_dir = os.path.join(current_dir, dir_path)

        # List entries in the directory
        try:
            # Use the shell's ls method to get entries
            result = self.shell.cd(search_dir).ls()

            # Parse the ls output - use data attribute which is a list of names
            if result and result.data:
                entries = result.data if isinstance(result.data, list) else result.text.strip().split('\n')
                for entry_name in entries:
                    # Skip empty entries and . and ..
                    if not entry_name or entry_name in ['.', '..']:
                        continue

                    if entry_name.startswith(prefix):
                        # Construct the full path for the completion
                        if text.startswith('/'):
                            # Absolute path
                            full_path = os.path.join(dir_path, entry_name)
                        elif '/' in text:
                            # Relative path with directory
                            full_path = os.path.join(dir_path, entry_name)
                        else:
                            # Just the name
                            full_path = entry_name

                        # Add trailing slash for directories
                        entry_full_path = os.path.join(search_dir, entry_name)
                        if self.shell.fs.stat(entry_full_path) and self.shell.fs.stat(entry_full_path).get('type') == 'dir':
                            full_path += '/'

                        matches.append(full_path)

            # Restore original directory
            self.shell.cd(current_dir)

        except:
            pass  # Ignore errors in path completion

        return sorted(matches)


class AliasManager:
    """
    Manages command aliases.

    Provides a clean API for:
    - Creating and removing aliases
    - Expanding aliases in commands
    - Persistence to disk
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
            pass  # Start with empty aliases

    def save_aliases(self):
        """Save aliases to file."""
        try:
            with open(self.alias_file, 'w') as f:
                json.dump(self.aliases, f, indent=2)
        except IOError:
            pass  # Ignore save errors

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
        # Split command line to get first word
        parts = command_line.split(None, 1)
        if not parts:
            return command_line

        first_word = parts[0]

        # Check if it's an alias
        if first_word in self.aliases:
            expanded = self.aliases[first_word]
            # Replace first word with expansion
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


class EnhancedTerminalSession(TerminalSession):
    """
    Enhanced terminal session with readline support and advanced features.

    This class extends the base TerminalSession with:
    - Readline integration for proper input handling
    - Advanced history management with persistence
    - Tab completion
    - History expansion
    - Command aliases
    - Signal handling for Ctrl+C, Ctrl+D, Ctrl+L
    """

    def __init__(self, config: Optional[EnhancedTerminalConfig] = None,
                 shell: Optional[DagShell] = None):
        """Initialize enhanced terminal session."""
        # Use enhanced config
        if config is None:
            config = EnhancedTerminalConfig()
        elif not isinstance(config, EnhancedTerminalConfig):
            # Convert regular config to enhanced
            enhanced_config = EnhancedTerminalConfig(**config.__dict__)
            config = enhanced_config

        # Initialize base class
        super().__init__(config, shell)

        # Store enhanced config
        self.enhanced_config = config

        # Initialize enhanced components
        self.history_manager = HistoryManager(
            config.history_file,
            config.history_max_size
        )

        self.alias_manager = AliasManager(config.alias_file)

        # Setup readline
        self._setup_readline()

        # Setup signal handlers
        self._setup_signal_handlers()

        # Register cleanup
        atexit.register(self._cleanup)

    def _setup_readline(self):
        """Configure readline for our terminal."""
        # Set up tab completion
        if self.enhanced_config.enable_tab_completion:
            self.tab_completer = TabCompleter(self.shell, self.alias_manager.aliases)
            readline.set_completer(self.tab_completer.complete)
            readline.parse_and_bind('tab: complete')

        # Configure readline behavior
        readline.parse_and_bind('set editing-mode emacs')

        # Set history size
        readline.set_history_length(self.enhanced_config.history_max_size)

    def _setup_signal_handlers(self):
        """Set up signal handlers for keyboard shortcuts."""
        # Ctrl+C is handled by Python's default KeyboardInterrupt

        # Ctrl+L for clear screen
        def clear_screen(signum, frame):
            os.system('clear' if os.name != 'nt' else 'cls')
            # Redraw the current line
            print(self.get_prompt(), end='')
            print(readline.get_line_buffer(), end='')
            sys.stdout.flush()

        # Note: Ctrl+L typically sends SIGWINCH, but we'll handle it in the main loop

    def _cleanup(self):
        """Clean up on exit."""
        self.history_manager.save_history()
        self.alias_manager.save_aliases()

    def execute_command(self, command_line: str) -> Optional[str]:
        """
        Execute a command line with history expansion and alias support.
        """
        # Skip empty commands
        if not command_line or command_line.strip() == '':
            return ''

        # Handle clear command specially
        if command_line.strip() == 'clear':
            os.system('clear' if os.name != 'nt' else 'cls')
            return ''

        # Handle special history command
        if command_line.strip() == 'history':
            return self._show_history(None)
        elif command_line.strip().startswith('history '):
            # history with argument
            parts = command_line.split()
            if len(parts) > 1 and parts[1].isdigit():
                return self._show_history(int(parts[1]))
            return self._show_history(None)

        # Handle alias commands
        if command_line.strip() == 'alias':
            return self.alias_manager.list_aliases()
        elif command_line.strip().startswith('alias '):
            return self._handle_alias_command(command_line)
        elif command_line.strip().startswith('unalias '):
            return self._handle_unalias_command(command_line)

        # Store original for history (before expansion)
        original_command = command_line

        # Expand history references
        if self.enhanced_config.enable_history_expansion:
            try:
                expanded = self.history_manager.expand(command_line)
                if expanded != command_line:
                    # Show the expanded command
                    print(expanded)
                    command_line = expanded
            except ValueError as e:
                return str(e)

        # Expand aliases
        command_line = self.alias_manager.expand(command_line)

        # Execute using parent class
        result = super().execute_command(command_line)

        # Add original command to history (after successful execution)
        if result is not None and not original_command.startswith('!'):
            # Don't add history expansion commands themselves
            self.history_manager.add(original_command)

        return result

    def _show_history(self, count: Optional[int]) -> str:
        """Show command history."""
        return self.history_manager.display(count)

    def _handle_alias_command(self, command_line: str) -> str:
        """Handle alias creation command."""
        # Parse: alias name=command
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
            # Update tab completer
            if hasattr(self, 'tab_completer'):
                self.tab_completer.aliases = self.alias_manager.aliases
                self.tab_completer._command_cache = self.tab_completer._build_command_cache()
            return ''
        else:
            return f"unalias: {name}: not found"

    def run_interactive(self):
        """
        Run the enhanced interactive REPL loop.

        Uses readline for input with proper history navigation
        and tab completion.
        """
        self.running = True

        # Print welcome message
        print("Welcome to DagShell Enhanced Terminal")
        print("Features: History (↑/↓), Tab completion, Aliases, History expansion (!!, !n)")
        print("Type 'help' for commands, 'exit' to quit")
        print()

        while self.running:
            try:
                # Get prompt
                prompt = self.get_prompt()

                # Get input using readline (automatically handles history navigation)
                command_line = input(prompt)

                # Add to history
                self.history_manager.add(command_line)

                # Execute command
                output = self.execute_command(command_line)

                # Check for exit
                if output is None:
                    break

                # Handle special clear command
                if command_line.strip() == 'clear':
                    os.system('clear' if os.name != 'nt' else 'cls')
                    continue

                # Display output
                if output:
                    print(output)

            except KeyboardInterrupt:
                # Ctrl+C - cancel current input
                print("^C")
                continue

            except EOFError:
                # Ctrl+D - exit
                print()
                break

            except Exception as e:
                print(f"Error: {e}")

        # Clean up
        self._cleanup()
        print("Goodbye!")


def main():
    """Main entry point for enhanced terminal."""
    import argparse
    import getpass

    parser = argparse.ArgumentParser(description='DagShell Enhanced Terminal')
    parser.add_argument('-c', '--command', help='Execute command and exit')
    parser.add_argument('-u', '--user', help='Set username', default=getpass.getuser())
    parser.add_argument('-d', '--directory', help='Set initial directory', default='/')
    parser.add_argument('--no-history', action='store_true', help='Disable history')
    parser.add_argument('--no-completion', action='store_true', help='Disable tab completion')
    parser.add_argument('--history-file', help='History file location')

    args = parser.parse_args()

    # Create configuration
    config = EnhancedTerminalConfig(
        user=args.user,
        initial_dir=args.directory,
        enable_tab_completion=not args.no_completion,
        enable_history_expansion=not args.no_history
    )

    if args.history_file:
        config.history_file = args.history_file

    # Create terminal session
    session = EnhancedTerminalSession(config=config)

    # Run command or interactive session
    if args.command:
        output = session.run_command(args.command)
        if output:
            print(output)
    else:
        session.run_interactive()


if __name__ == '__main__':
    main()