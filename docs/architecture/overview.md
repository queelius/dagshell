# Architecture Overview

DagShell consists of several layers, each providing different levels of abstraction.

## Layer Diagram

```
┌─────────────────────────────────────────────┐
│           Terminal Emulator                  │
│         (terminal.py)                        │
├─────────────────────────────────────────────┤
│           Fluent API                         │
│         (dagshell_fluent.py)                 │
├─────────────────────────────────────────────┤
│           Core FileSystem                    │
│         (dagshell.py)                        │
├─────────────────────────────────────────────┤
│           Content-Addressable DAG            │
│         (SHA256 hashing)                     │
└─────────────────────────────────────────────┘
```

## Core FileSystem (dagshell.py)

The foundation layer providing:

- **Immutable Nodes**: All filesystem nodes are immutable dataclasses
- **Content Addressing**: Every node is identified by its SHA256 hash
- **DAG Structure**: Directories reference nodes by hash, creating a DAG

### Node Types

```python
@dataclass(frozen=True)
class FileNode(Node):
    """Regular file with byte content."""
    content: bytes

@dataclass(frozen=True)
class DirNode(Node):
    """Directory with entries mapping names to hashes."""
    entries: Dict[str, str]  # name -> hash

@dataclass(frozen=True)
class SymlinkNode(Node):
    """Symbolic link pointing to another path."""
    target: str

@dataclass(frozen=True)
class DeviceNode(Node):
    """Virtual device (/dev/null, /dev/random, etc.)."""
    device_type: str
```

### FileSystem Class

Manages the DAG with two key structures:

- `_nodes: Dict[str, Node]` - Hash to node mapping
- `_root: str` - Hash of root directory

## Fluent API (dagshell_fluent.py)

Provides a chainable Python interface:

```python
shell.mkdir("/project").cd("/project").echo("Hello").out("file.txt")
```

### Key Components

- **DagShell**: Main shell class with state (cwd, env, history)
- **CommandResult**: Wrapper enabling chaining with `.out()`, `.append()`
- **Method Chaining**: Commands return self or CommandResult

### Design Principles

1. Commands return `CommandResult` for data access
2. State-modifying commands (cd, mkdir) return `DagShell` for chaining
3. `_last_result` enables pipe-like composition

## Terminal Emulator (terminal.py)

Full shell experience with:

- **CommandParser**: Parses shell syntax (pipes, redirects, quotes)
- **CommandExecutor**: Translates parsed commands to fluent API calls
- **TerminalSession**: Manages shell state and history

### Command Flow

```
"ls -la | grep txt"
    → CommandParser
    → Pipeline(Command("ls"), Command("grep"))
    → CommandExecutor
    → shell.ls(all=True, long=True)
    → shell.grep("txt")
    → CommandResult
```

## Scheme Interpreter

Optional Scheme DSL for scripting:

```scheme
(define files (ls "/home"))
(for-each display files)
(mkdir "/new-dir")
```
