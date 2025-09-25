# DagShell Terminal Emulator - Usage Guide

## Quick Start

```bash
# Start interactive terminal
python terminal.py

# Execute single command
python terminal.py -c "ls -la"

# Start as different user
python terminal.py -u alice

# Start in specific directory
python terminal.py -d /home/user
```

## Key Features

### 1. **Help System**
```bash
$ help
# or
$ ?
```
Shows all available commands and usage examples.

### 2. **Filesystem Persistence**

The virtual filesystem is **in-memory by default** and will be lost when you exit. To persist your work:

```bash
# Save current filesystem to JSON
$ save my_workspace.json

# Or use the commit alias
$ commit my_workspace.json

# Load a previously saved filesystem
$ load my_workspace.json
```

The filesystem is saved as a content-addressable JSON file where:
- Each file/directory has a unique SHA256 hash
- File contents are preserved
- Directory structure is maintained
- Metadata (permissions, timestamps) is saved

### 3. **Basic Commands**

```bash
# Navigation
$ cd /home/user
$ pwd
$ ls -la

# File operations
$ touch file.txt
$ echo "Hello" > greeting.txt
$ cat greeting.txt
$ cp source.txt dest.txt
$ mv oldname.txt newname.txt
$ rm file.txt

# Directory operations
$ mkdir newdir
$ rmdir emptydir
$ rm -r directory

# Text processing
$ cat file.txt | grep pattern
$ ls | head -5
$ sort numbers.txt -n
$ echo "test" | wc -l
```

### 4. **Piping and Redirection**

```bash
# Pipes
$ ls | grep ".txt" | wc -l

# Output redirection
$ echo "Hello" > output.txt
$ echo "World" >> output.txt

# Multiple commands
$ mkdir test; cd test; touch file.txt
$ mkdir test && cd test
$ cd nonexistent || echo "Failed"
```

## Example Session

```bash
$ python terminal.py
Welcome to dagshell terminal emulator
Type 'help' for help, 'exit' to quit

user@host:/$ mkdir /project
user@host:/$ cd /project
user@host:/project$ echo "# My Project" > README.md
user@host:/project$ touch main.py
user@host:/project$ ls
README.md
main.py
user@host:/project$ save project.json
Filesystem saved to project.json
user@host:/project$ exit
Goodbye!

# Later, restore your work:
$ python terminal.py
user@host:/$ load project.json
Filesystem loaded from project.json
user@host:/$ cd /project
user@host:/project$ ls
README.md
main.py
```

## Virtual Devices

The filesystem includes virtual devices:
- `/dev/null` - Discards all input
- `/dev/zero` - Produces null bytes
- `/dev/random` - Produces random bytes (deterministic with seed)

```bash
$ cat /dev/random | head -c 100 > random.bin
$ echo "discard this" > /dev/null
$ dd if=/dev/zero bs=1024 count=1 > zeros.bin
```

## Important Notes

1. **Virtual Filesystem**: All operations happen in memory on a virtual filesystem. Nothing affects your real filesystem unless you explicitly save/load JSON files.

2. **Content-Addressable**: Files are stored by their content hash, so identical files are automatically deduplicated.

3. **History**: The terminal maintains command history (up/down arrows work in interactive mode).

4. **Python API**: Every terminal command is backed by the fluent Python API, so you can also use:
   ```python
   from dagshell_fluent import shell
   shell.cd('/home').mkdir('user').touch('file.txt')
   shell.save('workspace.json')
   ```

## Tips

- Use `save` frequently to persist your work
- JSON files can be version-controlled with Git
- Load different "workspaces" for different projects
- The filesystem supports hard links naturally through content-addressing
- Use `help` to see all available commands