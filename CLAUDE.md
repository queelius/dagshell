# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

DagShell is a virtual POSIX filesystem with content-addressable DAG structure. It provides three primary interfaces:
1. **Core Filesystem** (`dagshell.py`) - Immutable, content-addressed nodes (FileNode, DirNode, DeviceNode)
2. **Fluent API** (`dagshell_fluent.py`) - Chainable Python interface with method chaining and piping
3. **Terminal Emulator** (`terminal.py`) - Full shell interface translating commands to fluent API calls
4. **Scheme Interpreter** (`scheme_interpreter.py`) - Embedded Scheme DSL for filesystem operations

## Development Commands

### Testing
```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_dagshell.py -v

# Run specific test class or method
python -m pytest tests/test_terminal.py::TestCommandParser -v
python -m pytest tests/test_terminal.py::TestCommandExecutor::test_execute_simple_command -xvs

# Run with coverage
python -m pytest tests/ --cov=dagshell --cov-report=html --cov-report=term

# Run without traceback for clean output
python -m pytest tests/test_terminal.py -v --tb=no
```

### Code Quality
```bash
# Format code
black dagshell/ tests/

# Check formatting
black --check dagshell/ tests/

# Sort imports
isort dagshell/ tests/

# Lint
flake8 dagshell/ tests/

# Type checking
mypy dagshell/
```

### Running the Terminal
```bash
# Start interactive terminal
python -m dagshell.terminal
# or
dagshell  # if installed via pip

# Run demo scripts
python examples/demo.py
python examples/demo_terminal.py
python examples/demo_fluent.py
```

## Architecture

### Core Filesystem (dagshell.py)
- **Immutability**: All nodes are frozen dataclasses. Changes create new nodes.
- **Content Addressing**: SHA256 hashing for deduplication. Hash includes all metadata (mode, uid, gid, mtime).
- **DAG Structure**: Directories reference nodes by hash, creating a directed acyclic graph.
- **Node Types**:
  - `FileNode`: Regular files with byte content
  - `DirNode`: Directories with entries dict mapping names to hashes
  - `DeviceNode`: Virtual devices (/dev/null, /dev/random, /dev/zero)
- **FileSystem Class**: Manages the DAG with `_nodes` (hash→node) and `_root` (root directory hash).

### Fluent API (dagshell_fluent.py)
- **CommandResult**: Wrapper enabling method chaining. Has `.data`, `.text`, `.exit_code`.
- **DagShell Class**: Stateful shell with `_cwd`, `_env`, `fs` (FileSystem instance).
- **Dual Nature**: Methods return CommandResult (Python object) OR redirect to virtual filesystem via `.out()`.
- **Method Chaining**: `shell.mkdir("/project").cd("/project").echo("text").out("file.txt")`
- **Piping**: Store last result in `_last_result`, accessible via `_()` method for pipe-like composition.
- **Directory Stack**: `pushd`/`popd` for directory navigation with `_dir_stack`.
- **Command History**: `_history` list tracks executed commands, accessible via `history()` method.
- **Import/Export**: `import_file()` and `export_file()` for real filesystem interaction.

### Terminal Emulator (terminal.py)
- **TerminalSession**: Main session manager with shell instance and command history.
- **CommandExecutor**: Translates parsed Command objects to fluent API method calls.
- **CommandParser** (command_parser.py): Parses shell syntax into structured Command/Pipeline/CommandGroup objects.
- **Data Flow**: Raw command string → CommandParser → Command objects → CommandExecutor → Fluent API calls → CommandResult

### Scheme Interpreter (scheme_interpreter.py)
- **Purpose**: Provides Scheme DSL for filesystem operations as an alternative interface.
- **Core Components**: Tokenizer, parser, evaluator with Environment for lexical scoping.
- **Integration**: SchemeREPL has FileSystem reference, exposes filesystem operations as Scheme primitives.

## Key Design Principles

1. **Separation of Concerns**:
   - Command parsing is separate from execution
   - Fluent API is separate from terminal emulation
   - Each layer can be used independently

2. **Composability**:
   - Small, focused methods that chain together
   - Unix philosophy: do one thing well
   - CommandResult enables both Python object access and filesystem redirection

3. **Immutability**:
   - Filesystem nodes are immutable
   - Operations return new filesystem states
   - History preserved in DAG structure

4. **Testability**:
   - Pure functions where possible
   - Clear interfaces between components
   - Comprehensive test suite with 77% coverage (583 tests)

## Testing Strategy

- **Comprehensive Test Coverage**: Target is 99%+ coverage
- **Test Organization**:
  - Core filesystem: `test_dagshell.py`, `test_core_filesystem_comprehensive.py`
  - Fluent API: `test_fluent.py`
  - Terminal: `test_terminal.py`, `test_terminal_features_comprehensive.py`
  - Scheme: `test_scheme_interpreter.py`, `test_scheme_integration_comprehensive.py`
  - Integration: `test_integration.py`
  - Edge cases: `test_edge_cases_comprehensive.py`
- **When adding features**: Write tests first or alongside implementation
- **After changes**: Run relevant test suite and verify coverage hasn't dropped

## Common Patterns

### Adding a New Command
1. Add method to `DagShell` class in `dagshell_fluent.py`
2. Add execution logic in `CommandExecutor._execute_command()` in `terminal.py`
3. Add tests in appropriate test file
4. Update help system if user-facing

### Working with the Filesystem
```python
# Access the FileSystem instance
fs = shell.fs

# Nodes are immutable - operations return new filesystem
new_fs = fs.write("/path/file.txt", b"content")

# Resolve paths
abs_path = shell._resolve_path("relative/path")

# Check permissions
if not fs.can_read(path, uid, gid):
    raise PermissionError(...)
```

### Method Chaining Pattern
```python
def new_command(self, arg1, arg2):
    # Do filesystem operation
    result_data = ...

    # Return CommandResult for chaining
    return CommandResult(
        data=result_data,
        text=str(result_data),
        exit_code=0,
        _shell=self
    )
```

## Important Notes

- **No External Dependencies**: Core package has zero dependencies (only dev dependencies)
- **Python 3.8+**: Minimum supported version
- **Virtual Devices**: /dev/null, /dev/random, /dev/zero are implemented as DeviceNode with special behavior
- **Permissions**: Unix-style permissions (mode bits) are enforced via `can_read()`, `can_write()`, `can_execute()`
- **Path Resolution**: Always use `_resolve_path()` to handle relative paths correctly
- **Content Encoding**: Files store bytes, conversion to/from str handled at API boundaries
