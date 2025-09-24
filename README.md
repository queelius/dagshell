# DagShell - Content-Addressable Virtual Filesystem

A virtualized POSIX-like filesystem implementation where the entire filesystem exists as a DAG (Directed Acyclic Graph) with content-addressable hashing and immutable nodes.

## Core Design Principles

1. **Everything is immutable** - Changes create new nodes, preserving history
2. **Content-addressable** - Every node has a SHA256 hash of its content + metadata
3. **Soft deletes** - `rm()` just removes path mappings, `purge()` does garbage collection
4. **Simple and composable** - Following Unix philosophy of doing one thing well

## Features

- **Python API** - Clean, composable filesystem operations
- **Scheme DSL** - Elegant Lisp dialect for filesystem manipulation
- **Virtual devices** - `/dev/null`, `/dev/zero`, `/dev/random`
- **JSON serialization** - Save/load entire filesystem state
- **History preservation** - All versions kept until explicitly purged

## Quick Start

### Python API

```python
import dagshell

# Create filesystem
fs = dagshell.FileSystem()

# Basic operations
fs.mkdir("/home/user")
fs.write("/home/user/hello.txt", "Hello, World!")
content = fs.read("/home/user/hello.txt")
fs.ls("/home/user")

# Content addressing
stat = fs.stat("/home/user/hello.txt")
print(f"Content hash: {stat['hash']}")

# Soft delete and garbage collection
fs.rm("/home/user/hello.txt")  # Soft delete
fs.purge()  # Remove unreferenced nodes
```

### Scheme DSL

```scheme
;; Start REPL
$ python scheme_interpreter.py

;; Create structure
(mkdir "/project")
(write-file "/project/README.md" "# My Project")
(ls "/project")

;; Define functions
(define count-files
  (lambda (dir)
    (length (ls dir))))

;; Higher-order operations
(define with-temp-file
  (lambda (path content proc)
    (begin
      (write-file path content)
      (let ((result (proc path)))
        (rm path)
        result))))
```

## Installation

```bash
# Clone repository
git clone <repository-url>
cd dagshell

# Run tests
python -m pytest

# Run demo
python demo.py

# Start Scheme REPL
python scheme_interpreter.py
```

## Architecture

The filesystem is implemented as a DAG where:
- Each node is identified by its content hash
- Directories contain mappings from names to hashes
- Path resolution is separate from the DAG structure
- Hard links naturally emerge from the content-addressing

```
/
├── home/
│   └── user/
│       ├── document.txt → hash_abc123...
│       └── backup.txt → hash_abc123... (same content, same hash)
└── dev/
    ├── null → DeviceNode("null")
    ├── zero → DeviceNode("zero")
    └── random → DeviceNode("random")
```

## Testing

```bash
# Run all tests
python -m pytest

# Run with coverage
python -m pytest --cov=dagshell --cov=scheme_interpreter

# Run specific test suite
python -m pytest test_dagshell.py -v
python -m pytest test_scheme_interpreter.py -v
```

## Files

- `dagshell.py` - Core filesystem implementation
- `scheme_interpreter.py` - Scheme DSL interpreter
- `demo.py` - Demonstration of capabilities
- `test_dagshell.py` - Filesystem tests
- `test_scheme_interpreter.py` - Scheme interpreter tests

## Future Enhancements

The design allows for future additions such as:
- POSIX terminal emulation with full login experience
- Branching and merging (git-like operations)
- Network transparency
- FUSE mounting for OS integration
- Capability-based security

## Philosophy

DagShell embodies the Unix philosophy:
- Do one thing well (content-addressable filesystem)
- Everything is a file (including devices)
- Composable operations
- Simple, elegant design over premature optimization