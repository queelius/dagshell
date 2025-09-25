"""
DagShell - A virtual POSIX filesystem with content-addressable DAG structure

This package provides a virtual filesystem implementation based on a directed acyclic
graph (DAG) structure with content-addressable storage, along with a fluent API
interface and an embedded Scheme interpreter.
"""

__version__ = "0.1.0"
__author__ = "Your Name"
__email__ = "your.email@example.com"

from .dagshell import (
    FileSystem,
    FileNode,
    DirNode,
    DeviceNode,
    Mode,
    FileHandle,
    Node,
)

from .dagshell_fluent import (
    DagShell,
    CommandResult,
    shell,
    _shell,
)

from .scheme_interpreter import (
    SchemeREPL,
    Symbol,
    Procedure,
    Environment,
)

from .terminal import (
    TerminalSession,
    TerminalConfig,
    CommandExecutor,
    CommandHistory,
)

from .command_parser import (
    Command,
    CommandParser,
    Pipeline,
    CommandGroup,
    Redirect,
    RedirectType,
)

__all__ = [
    # Core filesystem classes
    "FileSystem",
    "FileNode",
    "DirNode",
    "DeviceNode",
    "Node",
    "Mode",
    "FileHandle",

    # Fluent API
    "DagShell",
    "CommandResult",
    "shell",
    "_shell",

    # Scheme interpreter
    "SchemeREPL",
    "Symbol",
    "Procedure",
    "Environment",

    # Terminal
    "TerminalSession",
    "TerminalConfig",
    "CommandExecutor",
    "CommandHistory",

    # Command parser
    "Command",
    "CommandParser",
    "Pipeline",
    "CommandGroup",
    "Redirect",
    "RedirectType",

    # Version info
    "__version__",
    "__author__",
    "__email__",
]