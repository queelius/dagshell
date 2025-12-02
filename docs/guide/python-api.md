# Python API

The fluent API provides a Pythonic interface to DagShell with method chaining.

## Basic Usage

```python
from dagshell.dagshell_fluent import DagShell

# Create a shell instance
shell = DagShell()

# Method chaining
shell.mkdir("/project").cd("/project")

# Commands return CommandResult
result = shell.ls()
print(result.text)      # Human-readable output
print(result.data)      # Structured data
print(result.exit_code) # 0 for success
```

## CommandResult

Every command returns a `CommandResult` object:

```python
result = shell.cat("/etc/passwd")

# Access different representations
result.text       # String output
result.data       # Raw data (bytes, list, dict)
result.exit_code  # Exit status
bytes(result)     # Convert to bytes

# Chain with output redirection
shell.echo("content").out("/file.txt")      # Write
shell.echo("more").append("/file.txt")      # Append
```

## File Operations

```python
# Create and write
shell.touch("/file.txt")
shell.echo("Hello World").out("/file.txt")

# Read
content = shell.cat("/file.txt")
lines = shell.head(10, "/file.txt")
lines = shell.tail(10, "/file.txt")

# Copy, move, delete
shell.cp("/src.txt", "/dst.txt")
shell.mv("/old.txt", "/new.txt")
shell.rm("/file.txt")
shell.rm("/dir", recursive=True)

# Directories
shell.mkdir("/newdir")
shell.mkdir("/path/to/dir", parents=True)
```

## Text Processing

```python
# Grep
shell.cat("/file.txt")
matches = shell.grep("pattern")

# Or directly
matches = shell.grep("pattern", "/file.txt")

# Sort and unique
shell.cat("/file.txt")
sorted_result = shell.sort()
unique_result = shell.uniq()

# Chained processing
shell.cat("/data.txt")
shell.sort(numeric=True)
shell.uniq(count=True)
result = shell.head(10)
```

## Piping Pattern

```python
# Set up a pipeline by calling commands in sequence
shell.cat("/access.log")
shell.grep("ERROR")
shell.sort()
result = shell.uniq(count=True)

# Each command reads from _last_result
# Final result contains the processed output
```

## Links and Permissions

```python
# Symbolic links
shell.ln("/target", "/link", symbolic=True)
target = shell.readlink("/link")

# Permissions
shell.chmod("755", "/script.sh")
shell.chmod("u+x", "/script.sh")
shell.chown("root", "/file.txt")
shell.chown("root:wheel", "/file.txt")

# File info
info = shell.stat("/file.txt")
```

## Persistence

```python
# Save entire filesystem to JSON
shell.save("backup.json")

# Load from JSON
shell.load("backup.json")

# The JSON file is portable and human-readable
```

## Direct FileSystem Access

For low-level operations:

```python
# Access the underlying FileSystem
fs = shell.fs

# Read raw bytes
content = fs.read("/path/to/file")

# Write raw bytes
fs.write("/path/to/file", b"content")

# Check existence
exists = fs.exists("/path")

# Get node info
stat = fs.stat("/path")
```

## Environment

```python
# Set environment variables
shell.setenv("MY_VAR", "value")

# Get environment
shell.env()
shell.env("MY_VAR")

# Access in commands
shell.echo("$MY_VAR")
```
