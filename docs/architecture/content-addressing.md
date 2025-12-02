# Content Addressing

DagShell uses content-addressable storage, where every piece of data is identified by its cryptographic hash.

## How It Works

```
┌─────────────────┐
│  File Content   │
│  "Hello World"  │
└────────┬────────┘
         │
         ▼ SHA256
┌─────────────────────────────────────────────────────┐
│ a591a6d40bf420404a011733cfb7b190d62c65bf0bcda32b57 │
└─────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────┐
│   Node Store    │
│  hash → node    │
└─────────────────┘
```

## Benefits

### Automatic Deduplication

Identical files are stored only once:

```python
shell.echo("Hello World").out("/file1.txt")
shell.echo("Hello World").out("/file2.txt")

# Both files point to the same content hash
# Only one copy stored in the DAG
```

### Integrity Verification

Content can be verified against its hash:

```python
node = fs.get_node(hash)
computed_hash = sha256(node.content).hexdigest()
assert computed_hash == hash  # Always true
```

### Efficient Storage

The DAG structure means:

- Duplicate files share storage
- Similar directories share common subtrees
- History/snapshots share unchanged content

## Hash Calculation

Node hashes include all metadata:

```python
def _compute_hash(self) -> str:
    h = hashlib.sha256()
    h.update(self.content)
    h.update(str(self.mode).encode())
    h.update(str(self.uid).encode())
    h.update(str(self.gid).encode())
    h.update(str(self.mtime).encode())
    return h.hexdigest()
```

This means:

- Same content, different permissions = different hash
- Same content, different owner = different hash
- Metadata changes create new nodes

## DAG Structure

```
                    ┌─────────┐
                    │  root   │
                    │  dir    │
                    └────┬────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
    ┌────▼────┐    ┌────▼────┐    ┌────▼────┐
    │  home   │    │  etc    │    │  tmp    │
    │  dir    │    │  dir    │    │  dir    │
    └────┬────┘    └────┬────┘    └─────────┘
         │               │
    ┌────▼────┐    ┌────▼────┐
    │  user   │    │ passwd  │
    │  dir    │    │  file   │
    └────┬────┘    └─────────┘
         │
    ┌────▼────┐
    │ .bashrc │
    │  file   │
    └─────────┘
```

Each box is a node identified by its hash. Directories contain mappings of names to child hashes.

## Immutability

Nodes are immutable (frozen dataclasses). Any modification creates a new node:

```python
# Original file
original = fs.read("/file.txt")  # Returns content

# "Modify" creates new node
fs.write("/file.txt", b"new content")

# New hash, new node
# Old node still exists in DAG (orphaned)
```

## JSON Serialization

The entire filesystem serializes to JSON:

```json
{
  "nodes": {
    "abc123...": {
      "type": "file",
      "content": "SGVsbG8gV29ybGQ=",
      "mode": 420,
      "uid": 1000,
      "gid": 1000
    },
    "def456...": {
      "type": "dir",
      "entries": {
        "file.txt": "abc123..."
      }
    }
  },
  "root": "def456..."
}
```
