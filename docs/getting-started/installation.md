# Installation

## Requirements

- Python 3.8 or higher
- No external dependencies for core functionality

## Install from PyPI

```bash
pip install dagshell
```

## Install from Source

```bash
git clone https://github.com/queelius/dagshell.git
cd dagshell
pip install -e .
```

## Verify Installation

```bash
# Start the terminal emulator
python -m dagshell.terminal

# Or test in Python
python -c "from dagshell import DagShell; print('DagShell installed successfully!')"
```

## Development Installation

For contributing or development:

```bash
git clone https://github.com/queelius/dagshell.git
cd dagshell
pip install -e ".[dev]"

# Run tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=dagshell --cov-report=term
```
