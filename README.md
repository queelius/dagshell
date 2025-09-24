# DagShell

A virtual POSIX-compliant filesystem implementation with content-addressable DAG structure.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Start the terminal emulator
python terminal.py

# Or use the Python API directly
python
>>> from dagshell_fluent import shell
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
- **Comprehensive Testing**: 99% code coverage

## Documentation

- [Terminal Usage Guide](TERMINAL_USAGE.md)
- [Terminal Implementation](README_TERMINAL.md)
- [Test Coverage Report](TEST_COVERAGE_REPORT.md)

## License

MIT
