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
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime

from command_parser import (
    CommandParser, Command, Pipeline, CommandGroup,
    RedirectType, Redirect
)
from dagshell_fluent import DagShell, CommandResult


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
                result = self.shell._last_result or CommandResult(data='', text='', exit_code=0)
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


    def _show_help(self) -> CommandResult:
        """Show help information."""
        help_text = """DagShell Terminal Emulator - Help

BASIC COMMANDS:
  cd <path>         Change directory
  pwd               Print working directory
  ls [-la]          List directory contents
  mkdir <name>      Create directory
  rm <path>         Remove file or directory
  cp <src> <dst>    Copy file or directory
  mv <src> <dst>    Move/rename file or directory

FILE OPERATIONS:
  cat <file>        Display file contents
  touch <file>      Create empty file
  echo <text>       Print text to stdout
  head [-n N] file  Show first N lines (default 10)
  tail [-n N] file  Show last N lines (default 10)

TEXT PROCESSING:
  grep <pattern>    Search for pattern in input
  sort [-r] [-n]    Sort lines (-r reverse, -n numeric)
  uniq              Remove duplicate lines
  wc [-l]           Count words/lines

REDIRECTION:
  command > file    Redirect output to file (overwrite)
  command >> file   Append output to file
  cmd1 | cmd2       Pipe output of cmd1 to cmd2

PERSISTENCE:
  save [file]       Save filesystem to JSON (default: dagshell.json)
  load [file]       Load filesystem from JSON
  commit            Alias for save
  export <path>     Export virtual filesystem to real filesystem

USER MANAGEMENT:
  whoami            Show current username
  su [user]         Switch to another user (default: root)
  cat /etc/passwd   View user accounts
  cat /etc/group    View groups

SYSTEM:
  env [var]         Show environment variable(s)
  setenv VAR val    Set environment variable
  clear             Clear screen
  help or ?         Show this help
  exit or quit      Exit the shell

EXAMPLES:
  echo "hello" > greeting.txt     Create file with content
  cat file.txt | grep pattern     Search in file
  ls -la | head -5                 List first 5 items

Note: The filesystem is virtual and in-memory only.
Use 'save' to persist changes to disk as JSON."""

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
            'help': lambda: self._show_help(),
            '?': lambda: self._show_help(),
            'whoami': lambda: self._whoami(),
            'su': lambda *args: self._su(args[0] if args else 'root'),
            'export': lambda *args: self._export(args[0] if args else 'export'),
        }

        return aliases.get(command_name)

    def _prepare_arguments(self, command: Command) -> Tuple[List, Dict]:
        """Prepare arguments and keyword arguments for method call."""
        args = []
        kwargs = {}

        # Special handling for different commands
        if command.name == 'ls':
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
    """

    def __init__(self, config: Optional[TerminalConfig] = None,
                 shell: Optional[DagShell] = None):
        """Initialize terminal session."""
        self.config = config or TerminalConfig()
        self.shell = shell or DagShell()
        self.parser = CommandParser()
        self.executor = CommandExecutor(self.shell)
        self.history = CommandHistory(self.config.history_size)
        self.running = False

        # User context
        self.current_user = self.config.user
        self.uid, self.gid = self.shell.fs.lookup_user(self.current_user)
        self.groups = self.shell.fs.get_user_groups(self.current_user)
        self.strict_permissions = False  # Can be enabled for permission checking

        # Initialize shell environment
        self._init_environment()

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
        """
        # Handle empty input
        if not command_line or command_line.strip() == '':
            return ''

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

        # Return the text output
        return result.text if result.text else str(result)

    def run_interactive(self):
        """Run the interactive REPL loop."""
        self.running = True

        # Print welcome message
        print("Welcome to dagshell terminal emulator")
        print("Type 'help' for help, 'exit' to quit")
        print()

        while self.running:
            try:
                # Display prompt and get input
                prompt = self.get_prompt()
                command_line = input(prompt)

                # Add to history
                self.history.add(command_line)

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
    """Main entry point for terminal emulator."""
    import argparse

    parser = argparse.ArgumentParser(description='DagShell Terminal Emulator')
    parser.add_argument('-c', '--command', help='Execute command and exit')
    parser.add_argument('-u', '--user', help='Set username', default=getpass.getuser())
    parser.add_argument('-d', '--directory', help='Set initial directory', default='/')
    args = parser.parse_args()

    # Create configuration
    config = TerminalConfig(
        user=args.user,
        initial_dir=args.directory
    )

    # Create terminal session
    session = TerminalSession(config=config)

    # Run command or interactive session
    if args.command:
        output = session.run_command(args.command)
        if output:
            print(output)
    else:
        session.run_interactive()


if __name__ == '__main__':
    main()