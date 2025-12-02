# Quick Start

## Terminal Emulator

Start the interactive terminal:

```bash
python -m dagshell.terminal
```

This gives you a familiar shell environment:

```
dagshell:/$ mkdir /project
dagshell:/$ cd /project
dagshell:/project$ echo "Hello World" > README.md
dagshell:/project$ cat README.md
Hello World
dagshell:/project$ ls -l
-rw-r--r--  1 user user  12 README.md
```

## Python API

Use the fluent API for scripting:

```python
from dagshell.dagshell_fluent import DagShell

# Create a shell instance
shell = DagShell()

# Method chaining
shell.mkdir("/project").cd("/project")
shell.echo("# My Project").out("README.md")

# Command results
result = shell.ls("-l")
print(result.text)

# Piping
shell.cat("README.md")
result = shell.grep("Project")
print(result.text)

# Save and load
shell.save("project.json")

# Later...
shell2 = DagShell()
shell2.load("project.json")
```

## Persistence

Everything is stored in a single JSON file:

```python
# Save current state
shell.save("myfs.json")

# Load into a new shell
new_shell = DagShell()
new_shell.load("myfs.json")

# All files and directories are restored
new_shell.ls("/")
```

## Next Steps

- [Terminal Usage](../guide/terminal.md) - Full terminal documentation
- [Python API](../guide/python-api.md) - Complete API reference
- [Commands Reference](../guide/commands.md) - All available commands
