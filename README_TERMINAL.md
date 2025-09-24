# DagShell Terminal Emulator - Phase 1

A Unix-like terminal emulator built on top of the DagShell fluent API, providing a familiar command-line interface that translates shell commands into Python API calls.

## Architecture

The terminal emulator consists of three main components:

### 1. Command Parser (`command_parser.py`)
- Parses shell command syntax into structured representations
- Handles pipes (`|`), redirections (`>`, `>>`, `<`), and operators (`&&`, `||`, `;`)
- Maps command flags to API parameters
- Pure parsing logic with no execution

### 2. Terminal Session (`terminal.py`)
- Manages the REPL (Read-Eval-Print Loop)
- Maintains session state (user, hostname, environment)
- Handles prompt generation and command history
- Bridges parsing and execution

### 3. Fluent API (`dagshell_fluent.py`)
- Provides chainable, Unix-like operations
- All filesystem operations go through the virtual DAG filesystem
- Stateful shell maintaining current directory and environment

## Features Implemented

### Basic Commands
- Navigation: `cd`, `pwd`, `ls`
- File operations: `cat`, `echo`, `touch`, `mkdir`, `rm`, `cp`, `mv`
- Text processing: `grep`, `head`, `tail`, `sort`, `uniq`, `wc`
- System: `env`, `find`

### Shell Features
- **Pipes**: `ls | grep test | head -n 5`
- **Redirections**: `echo hello > file.txt`, `cat data >> output.txt`
- **Command sequences**: `cd /home ; ls ; pwd`
- **Conditional execution**: `test -f file && echo exists || echo missing`
- **Flag parsing**: Short (`-la`) and long (`--all`) flags
- **Quoted arguments**: `echo "hello world"`
- **Environment variables**: Maintained per session
- **Command history**: Navigate with up/down arrows (when run interactively)

## Command Translation Examples

Terminal commands are translated directly to fluent API calls:

```bash
# Terminal command → Python API
ls -la              → shell.ls(all=True, long=True)
cd /home            → shell.cd('/home')
cat file.txt        → shell.cat('file.txt')
echo hello > out    → shell.echo('hello').out('out')
ls | grep test      → shell.ls().grep('test')
find . -name "*.py" → shell.find('.', name='*.py')
```

## Usage

### Interactive Mode
```python
from terminal import TerminalSession, TerminalConfig

config = TerminalConfig(
    user='myuser',
    hostname='myhost',
    home_dir='/home/myuser'
)
session = TerminalSession(config=config)
session.run_interactive()
```

### Programmatic Usage
```python
session = TerminalSession()
output = session.execute_command("ls -la | grep txt")
print(output)
```

### Running Scripts
```python
script_lines = [
    "cd /home",
    "mkdir projects",
    "echo 'Hello' > projects/test.txt",
    "cat projects/test.txt"
]
outputs = session.run_script(script_lines)
```

## Testing

Run the comprehensive test suite:
```bash
python -m pytest test_terminal.py -v
```

Run the demo:
```bash
# Show command demonstrations
python demo_terminal.py commands

# Interactive mode
python demo_terminal.py interactive

# Show command translation
python demo_terminal.py translation
```

## Design Principles

1. **Everything Through the API**: No direct filesystem access; all operations use the fluent API
2. **Composable**: Commands can be chained and piped naturally
3. **Stateful**: Maintains session state (pwd, env) between commands
4. **Elegant**: Clean separation between parsing, execution, and presentation
5. **Testable**: Pure functions for parsing, clear interfaces for execution

## Phase 1 Limitations

Current implementation focuses on core functionality. Future phases could add:
- Job control (`&`, `fg`, `bg`, `jobs`)
- Command substitution (`$(...)`, backticks)
- Shell scripting constructs (`if`, `for`, `while`)
- Aliases and functions
- Tab completion
- More complex redirections (`2>&1`, here documents)
- Signal handling (`Ctrl+C`, `Ctrl+Z`)

## Files Structure

```
terminal.py           - Main terminal emulator and REPL
command_parser.py     - Shell command parser
dagshell_fluent.py    - Fluent API (extended for terminal support)
test_terminal.py      - Comprehensive test suite
demo_terminal.py      - Demonstration script
```

## Example Session

```bash
user@dagshell:/$ ls
dev  home  tmp  var

user@dagshell:/$ cd home
user@dagshell:/home$ mkdir myproject
user@dagshell:/home$ cd myproject
user@dagshell:/home/myproject$ echo "# My Project" > README.md
user@dagshell:/home/myproject$ cat README.md
# My Project

user@dagshell:/home/myproject$ ls -la
-rw-r--r--  1 user user      12 README.md

user@dagshell:/home/myproject$ echo "print('hello')" > hello.py
user@dagshell:/home/myproject$ cat hello.py | grep print
print('hello')
```

The terminal emulator provides a familiar Unix-like interface while leveraging the power of the DagShell virtual filesystem and its composable, functional design.