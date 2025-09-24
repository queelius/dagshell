#!/usr/bin/env python3
"""
Command parser for the dagshell terminal emulator.

This module provides a clean, composable parser that translates shell command
strings into structured representations that can be executed via the fluent API.

Design Principles:
- Single responsibility: Parse commands, don't execute them
- Composable: Each parsing step is independent
- Elegant: Clean data structures for representing commands
- Testable: Pure functions with predictable outputs
"""

import re
import shlex
from typing import List, Dict, Optional, Tuple, Union, Any
from dataclasses import dataclass
from enum import Enum


class RedirectType(Enum):
    """Types of IO redirection."""
    WRITE = '>'      # Overwrite file
    APPEND = '>>'    # Append to file
    READ = '<'       # Read from file
    HERE_DOC = '<<'  # Here document
    HERE_STR = '<<<' # Here string


@dataclass
class Redirect:
    """Represents an IO redirection."""
    type: RedirectType
    target: str
    fd: int = 1  # File descriptor (1=stdout, 2=stderr, 0=stdin)


@dataclass
class Command:
    """
    Represents a single command with its arguments and redirections.

    This is the fundamental unit of execution. Each command maps to
    a method call on the fluent API.
    """
    name: str
    args: List[str]
    flags: Dict[str, Union[bool, str, int]]  # Parsed flags
    redirects: List[Redirect]
    raw_args: List[str]  # Original arguments before flag parsing

    def __str__(self) -> str:
        parts = [self.name]
        if self.flags:
            for key, value in self.flags.items():
                if value is True:
                    parts.append(f"-{key}")
                else:
                    parts.append(f"--{key}={value}")
        parts.extend(self.args)
        return ' '.join(parts)


@dataclass
class Pipeline:
    """
    Represents a pipeline of commands connected by pipes.

    Commands are executed left to right, with output flowing
    through the pipeline.
    """
    commands: List[Command]
    background: bool = False

    def __str__(self) -> str:
        return ' | '.join(str(cmd) for cmd in self.commands)


@dataclass
class CommandGroup:
    """
    Represents a group of pipelines connected by operators.

    Supports && (and), || (or), ; (sequence), & (background).
    """
    pipelines: List[Tuple[Pipeline, Optional[str]]]  # (pipeline, operator)

    def __str__(self) -> str:
        parts = []
        for pipeline, op in self.pipelines:
            parts.append(str(pipeline))
            if op:
                parts.append(op)
        return ' '.join(parts)


class CommandParser:
    """
    Parser for shell command syntax.

    This parser handles:
    - Basic commands with arguments
    - Flags (short: -a, -abc; long: --flag, --flag=value)
    - Pipes (|)
    - Redirections (>, >>, <)
    - Command sequences (;, &&, ||)
    - Quoting and escaping
    """

    # Common flag mappings for Unix commands
    FLAG_MAPPINGS = {
        'ls': {
            'a': 'all',
            'l': 'long',
            'h': 'human',
            'r': 'reverse',
            't': 'time',
            'S': 'size',
            '1': 'one',
        },
        'grep': {
            'i': 'ignore_case',
            'v': 'invert',
            'E': 'extended',
            'F': 'fixed',
            'n': 'line_number',
            'c': 'count',
            'l': 'files_with_matches',
        },
        'rm': {
            'r': 'recursive',
            'f': 'force',
            'i': 'interactive',
            'v': 'verbose',
        },
        'cp': {
            'r': 'recursive',
            'f': 'force',
            'v': 'verbose',
            'n': 'no_clobber',
        },
        'mkdir': {
            'p': 'parents',
            'v': 'verbose',
        },
        'sort': {
            'r': 'reverse',
            'n': 'numeric',
            'u': 'unique',
        },
        'uniq': {
            'c': 'count',
            'd': 'repeated',
        },
        'wc': {
            'l': 'lines',
            'w': 'words',
            'c': 'chars',
        },
        'echo': {
            'n': 'n',  # no newline
            'e': 'escape',
        },
        'head': {
            'n': 'lines',
        },
        'tail': {
            'n': 'lines',
            'f': 'follow',
        },
        'find': {
            'd': 'type',
            'f': 'type',
        }
    }

    def __init__(self):
        """Initialize the parser."""
        # Regex patterns for parsing
        self.redirect_pattern = re.compile(r'(\d*)([><]+)\s*(\S+)')
        self.operator_pattern = re.compile(r'(&&|\|\||;|&)')

    def parse(self, command_line: str) -> CommandGroup:
        """
        Parse a complete command line into a CommandGroup.

        This is the main entry point for parsing shell commands.
        """
        # Handle empty input
        if not command_line or command_line.strip() == '':
            return CommandGroup(pipelines=[])

        # Split by command operators (&&, ||, ;, &)
        pipelines = []
        parts = self.operator_pattern.split(command_line)

        i = 0
        while i < len(parts):
            part = parts[i].strip()
            if not part:
                i += 1
                continue

            # Check if this is an operator
            if self.operator_pattern.match(part):
                i += 1
                continue

            # Parse this part as a pipeline
            pipeline = self._parse_pipeline(part)

            # Check for following operator
            operator = None
            if i + 1 < len(parts):
                next_part = parts[i + 1].strip()
                if self.operator_pattern.match(next_part):
                    operator = next_part
                    i += 1

            pipelines.append((pipeline, operator))
            i += 1

        return CommandGroup(pipelines=pipelines)

    def _parse_pipeline(self, pipeline_str: str) -> Pipeline:
        """Parse a pipeline of commands connected by pipes."""
        # Check for background execution
        background = False
        if pipeline_str.endswith('&'):
            background = True
            pipeline_str = pipeline_str[:-1].strip()

        # Split by pipes
        pipe_parts = self._split_by_pipe(pipeline_str)

        # Parse each command
        commands = []
        for part in pipe_parts:
            part = part.strip()
            if part:
                cmd = self._parse_command(part)
                if cmd:
                    commands.append(cmd)

        return Pipeline(commands=commands, background=background)

    def _split_by_pipe(self, text: str) -> List[str]:
        """Split text by pipe character, respecting quotes."""
        parts = []
        current = []
        in_single_quote = False
        in_double_quote = False
        escaped = False

        for char in text:
            if escaped:
                current.append(char)
                escaped = False
            elif char == '\\':
                escaped = True
                current.append(char)
            elif char == "'" and not in_double_quote:
                in_single_quote = not in_single_quote
                current.append(char)
            elif char == '"' and not in_single_quote:
                in_double_quote = not in_double_quote
                current.append(char)
            elif char == '|' and not in_single_quote and not in_double_quote:
                # Found a pipe separator
                parts.append(''.join(current))
                current = []
            else:
                current.append(char)

        # Add the last part
        if current:
            parts.append(''.join(current))

        return parts

    def _parse_command(self, command_str: str) -> Optional[Command]:
        """Parse a single command with its arguments and redirections."""
        # Extract redirections first
        redirects, clean_str = self._extract_redirections(command_str)

        # Parse the command and arguments
        try:
            tokens = shlex.split(clean_str)
        except ValueError:
            # Handle unclosed quotes gracefully
            tokens = clean_str.split()

        if not tokens:
            return None

        cmd_name = tokens[0]
        raw_args = tokens[1:] if len(tokens) > 1 else []

        # Parse flags and arguments
        flags, args = self._parse_flags(cmd_name, raw_args)

        return Command(
            name=cmd_name,
            args=args,
            flags=flags,
            redirects=redirects,
            raw_args=raw_args
        )

    def _extract_redirections(self, command_str: str) -> Tuple[List[Redirect], str]:
        """Extract redirections from a command string."""
        redirects = []
        clean_str = command_str

        # Find all redirections
        for match in self.redirect_pattern.finditer(command_str):
            fd_str, op, target = match.groups()
            fd = int(fd_str) if fd_str else (1 if op.startswith('>') else 0)

            # Determine redirection type
            if op == '>':
                redirect_type = RedirectType.WRITE
            elif op == '>>':
                redirect_type = RedirectType.APPEND
            elif op == '<':
                redirect_type = RedirectType.READ
            elif op == '<<':
                redirect_type = RedirectType.HERE_DOC
            elif op == '<<<':
                redirect_type = RedirectType.HERE_STR
            else:
                continue

            redirects.append(Redirect(type=redirect_type, target=target, fd=fd))

        # Remove redirections from command string
        clean_str = self.redirect_pattern.sub('', clean_str)

        return redirects, clean_str.strip()

    def _parse_flags(self, cmd_name: str, args: List[str]) -> Tuple[Dict[str, Union[bool, str, int]], List[str]]:
        """
        Parse flags from arguments.

        Returns (flags_dict, remaining_args)
        """
        flags = {}
        remaining = []
        flag_mappings = self.FLAG_MAPPINGS.get(cmd_name, {})

        i = 0
        while i < len(args):
            arg = args[i]

            if arg == '--':
                # End of flags marker
                remaining.extend(args[i + 1:])
                break
            elif arg.startswith('--'):
                # Long flag
                if '=' in arg:
                    key, value = arg[2:].split('=', 1)
                    flags[key] = value
                else:
                    flags[arg[2:]] = True
                i += 1
            elif arg.startswith('-') and len(arg) > 1 and arg[1] != '-':
                # Short flag(s)
                # Special case for head/tail: -N where N is a number
                if cmd_name in ['head', 'tail'] and arg[1:].isdigit():
                    flags['n'] = int(arg[1:])
                    i += 1
                else:
                    for char in arg[1:]:
                        # Map short flag to long name if available
                        long_name = flag_mappings.get(char, char)

                        # Check if this flag takes a value
                        if cmd_name in ['head', 'tail'] and char == 'n':
                            # Special case: -n takes a value
                            if i + 1 < len(args) and not args[i + 1].startswith('-'):
                                try:
                                    flags[long_name] = int(args[i + 1])
                                    i += 1
                                except ValueError:
                                    flags[long_name] = True
                            else:
                                flags[long_name] = True
                        else:
                            flags[long_name] = True
                    i += 1
            else:
                # Regular argument
                remaining.append(arg)
                i += 1

        return flags, remaining

    def parse_simple(self, command_str: str) -> Command:
        """
        Parse a simple command without pipes or operators.

        Convenience method for testing and simple cases.
        """
        cmd = self._parse_command(command_str)
        return cmd if cmd else Command(name='', args=[], flags={}, redirects=[], raw_args=[])