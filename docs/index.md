# DagShell

A virtual POSIX-compliant filesystem implementation with content-addressable DAG structure.

## Overview

DagShell provides a complete virtual filesystem that:

- **Stores everything in JSON** - Your entire filesystem is a single portable file
- **Uses content addressing** - SHA256 hashing for automatic deduplication
- **Implements POSIX semantics** - Familiar commands like ls, cat, grep, chmod
- **Supports multiple interfaces** - Python API, terminal emulator, Scheme DSL

## Key Features

| Feature | Description |
|---------|-------------|
| Content-Addressable | SHA256-based deduplication - identical files stored once |
| Virtual POSIX | Complete filesystem in a JSON file |
| Multiple Interfaces | Python API, Scheme DSL, Terminal emulator |
| Persistence | Save/load filesystem state as JSON |
| Virtual Devices | /dev/null, /dev/random, /dev/zero |
| Symbolic Links | Full symlink support with loop detection |
| Permissions | Unix-style mode bits and ownership |

## Quick Example

```python
from dagshell.dagshell_fluent import DagShell

# Create a shell instance
shell = DagShell()

# Create directories and files
shell.mkdir("/project").cd("/project")
shell.echo("Hello, DagShell!").out("README.md")

# Use familiar commands
shell.ls("-l")
shell.cat("README.md")

# Save everything to a JSON file
shell.save("my_project.json")
```

## Installation

```bash
pip install dagshell
```

Or install from source:

```bash
git clone https://github.com/queelius/dagshell.git
cd dagshell
pip install -e .
```

## License

MIT License
