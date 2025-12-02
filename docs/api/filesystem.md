# FileSystem API

The `FileSystem` class provides low-level access to the content-addressable DAG.

## Constructor

```python
from dagshell.dagshell import FileSystem

fs = FileSystem()
```

## Basic Operations

### read(path) -> Optional[bytes]

Read file contents.

```python
content = fs.read("/etc/passwd")
if content:
    text = content.decode('utf-8')
```

### write(path, content) -> bool

Write content to file.

```python
fs.write("/file.txt", b"Hello World")
fs.write("/file.txt", "Text content".encode())
```

### exists(path) -> bool

Check if path exists.

```python
if fs.exists("/path/to/file"):
    content = fs.read("/path/to/file")
```

### stat(path) -> Optional[Dict]

Get file information.

```python
info = fs.stat("/file.txt")
# Returns:
# {
#     'type': 'file',
#     'size': 1234,
#     'mode': 0o644,
#     'uid': 1000,
#     'gid': 1000,
#     'mtime': 1234567890.0
# }
```

### ls(path) -> Optional[List[str]]

List directory contents.

```python
entries = fs.ls("/home")
# Returns: ['user1', 'user2', ...]
```

## Directory Operations

### mkdir(path) -> bool

Create directory.

```python
fs.mkdir("/newdir")
```

### rmdir(path) -> bool

Remove empty directory.

```python
fs.rmdir("/emptydir")
```

## File Management

### unlink(path) -> bool

Remove file.

```python
fs.unlink("/file.txt")
```

### rename(old, new) -> bool

Rename/move file.

```python
fs.rename("/old.txt", "/new.txt")
```

## Links

### symlink(target, path) -> bool

Create symbolic link.

```python
fs.symlink("/target", "/link")
```

### readlink(path) -> Optional[str]

Read symbolic link target.

```python
target = fs.readlink("/link")
```

## Permissions

### chmod(path, mode) -> bool

Change file mode.

```python
fs.chmod("/file.txt", 0o755)
```

### chown(path, uid, gid) -> bool

Change ownership.

```python
fs.chown("/file.txt", 1000, 1000)
```

### can_read(path, uid, gid) -> bool
### can_write(path, uid, gid) -> bool
### can_execute(path, uid, gid) -> bool

Check permissions.

```python
if fs.can_write("/file.txt", 1000, 1000):
    fs.write("/file.txt", b"content")
```

## Serialization

### to_json() -> str

Serialize filesystem to JSON.

```python
json_data = fs.to_json()
with open("backup.json", "w") as f:
    f.write(json_data)
```

### from_json(json_str) -> FileSystem

Load filesystem from JSON.

```python
with open("backup.json") as f:
    json_data = f.read()
fs = FileSystem.from_json(json_data)
```

## Node Access

### get_node(hash) -> Optional[Node]

Get node by hash.

```python
node = fs.get_node("abc123...")
if isinstance(node, FileNode):
    print(node.content)
```

### Node Types

```python
from dagshell.dagshell import FileNode, DirNode, SymlinkNode, DeviceNode

# Check node type
node = fs.get_node(hash)
if node.is_file():
    print(node.content)
elif node.is_dir():
    print(node.entries)
elif node.is_symlink():
    print(node.target)
```

## Constants

```python
from dagshell.dagshell import Mode

Mode.IRWXU  # 0o700 - Owner rwx
Mode.IRWXG  # 0o070 - Group rwx
Mode.IRWXO  # 0o007 - Other rwx
Mode.IRUSR  # 0o400 - Owner read
Mode.IWUSR  # 0o200 - Owner write
Mode.IXUSR  # 0o100 - Owner execute
# ... etc
```
