# DagShell API

The `DagShell` class provides the main interface for interacting with the virtual filesystem.

## Constructor

```python
from dagshell.dagshell_fluent import DagShell

shell = DagShell(fs=None)
```

**Parameters:**

- `fs` - Optional FileSystem instance. Creates new one if not provided.

## Navigation

### cd(path)

Change current directory.

```python
shell.cd("/home/user")
shell.cd("..")
shell.cd("-")  # Previous directory
```

### pwd()

Return current working directory.

```python
result = shell.pwd()
print(result.text)  # /home/user
```

### pushd(path), popd(), dirs()

Directory stack operations.

```python
shell.pushd("/tmp")
shell.popd()
result = shell.dirs()
```

## File Operations

### cat(*paths)

Display file contents.

```python
result = shell.cat("/etc/passwd")
result = shell.cat("file1.txt", "file2.txt")
```

### head(n, *paths), tail(n, *paths)

Display first/last n lines.

```python
result = shell.head(10, "/var/log/messages")
result = shell.tail(20, "/var/log/messages")
```

### touch(path)

Create empty file or update timestamp.

```python
shell.touch("/newfile.txt")
```

### cp(src, dst), mv(src, dst), rm(path, recursive=False)

Copy, move, remove files.

```python
shell.cp("/src.txt", "/dst.txt")
shell.mv("/old.txt", "/new.txt")
shell.rm("/file.txt")
shell.rm("/dir", recursive=True)
```

### mkdir(path, parents=False)

Create directory.

```python
shell.mkdir("/newdir")
shell.mkdir("/path/to/dir", parents=True)
```

### ls(path=None, all=False, long=False)

List directory contents.

```python
result = shell.ls()
result = shell.ls("/home", all=True, long=True)
```

## Text Processing

### echo(*args, n=False)

Display text.

```python
result = shell.echo("Hello", "World")
shell.echo("no newline", n=True)
```

### grep(pattern, *files, ignore_case=False, invert=False)

Search for patterns.

```python
shell.cat("/file.txt")
result = shell.grep("pattern")

# Or directly
result = shell.grep("pattern", "/file.txt", ignore_case=True)
```

### sort(*files, reverse=False, numeric=False, unique=False)

Sort lines.

```python
result = shell.sort("/data.txt", numeric=True)
```

### uniq(*files, count=False)

Remove duplicate lines.

```python
result = shell.uniq("/data.txt", count=True)
```

### wc(*files, lines=False, words=False, chars=False)

Count lines, words, characters.

```python
result = shell.wc("/file.txt")
result = shell.wc("/file.txt", lines=True)
```

### cut(*files, delimiter='\t', fields=None)

Extract fields.

```python
result = shell.cut("/data.csv", delimiter=",", fields="1,3")
```

### tr(set1, set2='', delete=False)

Translate characters.

```python
shell.cat("/file.txt")
result = shell.tr("a-z", "A-Z")
result = shell.tr("0-9", "", delete=True)
```

### diff(file1, file2, unified=False)

Compare files.

```python
result = shell.diff("/file1.txt", "/file2.txt")
result = shell.diff("/old.py", "/new.py", unified=True)
```

## Links

### ln(target, link, symbolic=False)

Create links.

```python
shell.ln("/target.txt", "/hardlink.txt")
shell.ln("/target.txt", "/symlink.txt", symbolic=True)
```

### readlink(path)

Read symbolic link target.

```python
result = shell.readlink("/symlink.txt")
```

## Permissions

### chmod(mode, path)

Change file mode.

```python
shell.chmod("755", "/script.sh")
shell.chmod("u+x", "/script.sh")
shell.chmod("go-w", "/file.txt")
```

### chown(owner, path)

Change ownership.

```python
shell.chown("user", "/file.txt")
shell.chown("user:group", "/file.txt")
```

### stat(path)

Get file information.

```python
result = shell.stat("/file.txt")
```

## Persistence

### save(filename)

Save filesystem to JSON.

```python
shell.save("backup.json")
```

### load(filename)

Load filesystem from JSON.

```python
shell.load("backup.json")
```

## Output Redirection

CommandResult supports output redirection:

```python
# Write to file
shell.echo("content").out("/file.txt")

# Append to file
shell.echo("more").append("/file.txt")
```
