# DagShell

A virtual POSIX-compliant filesystem implementation with content-addressable DAG structure.

## Quick Start

```bash
# Install the package
pip install -e .

# Start the terminal emulator
python -m dagshell.terminal

# Or use the Python API directly
python
>>> from dagshell.dagshell_fluent import DagShell
>>> shell = DagShell()
>>> shell.mkdir("/project").cd("/project")
>>> shell.echo("Hello, DagShell!").out("README.md")
>>> shell.save("my_project.json")
```

## Features

- **Content-Addressable Filesystem**: SHA256-based deduplication
- **Virtual POSIX Environment**: Complete filesystem in JSON
- **Multiple Interfaces**: Python API, Scheme DSL, Terminal emulator
- **Persistence**: Save/load filesystem state as JSON
- **Virtual Devices**: /dev/null, /dev/random, /dev/zero
- **Directory Navigation**: cd, pushd, popd, dirs
- **Import/Export**: Transfer files between real and virtual filesystems
- **Command History**: Track and recall previous commands
- **Comprehensive Testing**: 583 tests with 77% code coverage

## Development

```bash
# Run tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=dagshell --cov-report=term
```

## License

MIT
