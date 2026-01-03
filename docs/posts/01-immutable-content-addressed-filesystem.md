# Building an Immutable, Content-Addressed Filesystem in Python

*How Git-style content addressing creates elegant, functional data structures*

---

When you run `git commit`, something interesting happens: Git doesn't store your files by name. Instead, it computes a SHA-1 hash of each file's content and stores the file under that hash. The filename is just a pointer to the hash. This is **content addressing**—identifying data by what it contains rather than where it lives.

This seemingly simple idea has profound implications. In this post, I'll show how to build a content-addressed virtual filesystem in Python, exploring how immutability and content addressing work together to create elegant, functional data structures.

## Why Content Addressing?

Consider a traditional filesystem. When you modify a file, the system overwrites the old content. The file's identity (its path) stays the same, but its content changes. This mutable approach has problems:

1. **No automatic history**: Once you overwrite, the old data is gone
2. **No deduplication**: Two identical files take up twice the space
3. **No integrity verification**: Corruption can go undetected

Content addressing solves all three. If a file's identity *is* its content (via a hash), then:

1. **History is preserved**: Changing content creates a new hash, so the old version still exists
2. **Deduplication is automatic**: Identical content has identical hashes—stored once
3. **Integrity is built-in**: If the content doesn't match the hash, you know something's wrong

## The Node Hierarchy

Let's build this. First, we define our filesystem nodes using Python's frozen dataclasses:

```python
from dataclasses import dataclass, field
import hashlib
import json

@dataclass(frozen=True)
class Node:
    """Base class for all filesystem nodes."""
    mode: int
    uid: int = 1000
    gid: int = 1000
    mtime: float = field(default_factory=time.time)

    def compute_hash(self) -> str:
        """Compute SHA256 hash of this node including all metadata."""
        data = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()
```

The `frozen=True` parameter is crucial. It makes instances immutable—you cannot modify a Node after creation. Any "change" requires creating a new Node.

We then specialize for different node types:

```python
@dataclass(frozen=True)
class FileNode(Node):
    """Regular file node."""
    content: bytes = b""

@dataclass(frozen=True)
class DirNode(Node):
    """Directory node containing references to child nodes."""
    children: Dict[str, str] = field(default_factory=dict)  # name -> hash
```

Notice that `DirNode.children` maps names to *hashes*, not to Node objects directly. This is the key insight: directories don't contain files; they contain *references* to file hashes. The actual nodes live in a separate store.

## The DAG Structure

This reference-based approach creates a Directed Acyclic Graph (DAG):

```python
class FileSystem:
    """Content-addressable virtual filesystem."""

    def __init__(self):
        # The DAG: hash -> Node
        self.nodes: Dict[str, Node] = {}

        # Path index: absolute path -> hash
        self.paths: Dict[str, str] = {}

    def _add_node(self, node: Node) -> str:
        """Add a node to the DAG, returning its hash."""
        node_hash = node.compute_hash()
        if node_hash not in self.nodes:
            self.nodes[node_hash] = node
        return node_hash
```

When we add a node, we compute its hash and store the mapping `hash → node`. If an identical node already exists (same hash), we don't duplicate it—we just return the existing hash. **Deduplication is automatic.**

## Immutable Updates

Here's where immutability shines. When we write to a file, we don't modify anything. Instead, we:

1. Create a new FileNode with the new content
2. Create a new DirNode for the parent, pointing to the new file hash
3. Update the path index

```python
def write(self, path: str, content: bytes) -> bool:
    """Write content to a file."""
    parent_path, name = self._get_parent_path(path)
    parent_hash = self.paths[parent_path]
    parent = self.nodes[parent_hash]

    # Create new file node
    file_node = FileNode(content)
    file_hash = self._add_node(file_node)

    # Create new parent directory with updated child reference
    new_children = dict(parent.children)
    new_children[name] = file_hash
    new_parent = DirNode(children=new_children)
    new_parent_hash = self._add_node(new_parent)

    # Update path index
    self.paths[parent_path] = new_parent_hash
    self.paths[path] = file_hash

    return True
```

The old FileNode still exists in `self.nodes`. The old DirNode still exists too. We've just created new versions and updated where the path points. This is **structural sharing**—unchanged parts of the tree are shared between versions.

## Visualizing the DAG

Let's trace through an example:

```python
fs = FileSystem()
fs.mkdir("/project")
fs.write("/project/main.py", b"print('hello')")
fs.write("/project/main.py", b"print('world')")
```

After these operations, our DAG contains:

```
Hash: a1b2c3... → DirNode(children={})           # original /project
Hash: d4e5f6... → FileNode("print('hello')")     # first version
Hash: g7h8i9... → DirNode(children={"main.py": "d4e5f6..."})
Hash: j0k1l2... → FileNode("print('world')")     # second version
Hash: m3n4o5... → DirNode(children={"main.py": "j0k1l2..."})
```

Both versions of `main.py` exist. The path `/project/main.py` points to the latest hash (`j0k1l2...`), but we could easily restore the old version if we tracked which hashes corresponded to which versions.

## Benefits in Practice

This design enables powerful features almost for free:

**Snapshots**: Save the current `paths` dictionary. Restore it later to go back in time.

```python
def snapshot(self) -> Dict[str, str]:
    """Create a snapshot of the current filesystem state."""
    return dict(self.paths)

def restore(self, snapshot: Dict[str, str]):
    """Restore filesystem to a previous snapshot."""
    self.paths = dict(snapshot)
```

**Deduplication**: Multiple paths can point to the same hash.

```python
# These might share the same underlying node if content is identical
fs.write("/file1.txt", b"hello")
fs.write("/file2.txt", b"hello")  # Same hash, no new storage
```

**Integrity checking**: If someone asks for a file, we can verify it.

```python
def verify(self, path: str) -> bool:
    """Verify a file's integrity."""
    node_hash = self.paths[path]
    node = self.nodes[node_hash]
    return node.compute_hash() == node_hash
```

## The Functional Programming Connection

This approach is deeply connected to functional programming. In FP:

- Data is immutable
- "Changes" create new values
- Sharing is safe because nothing mutates

Our filesystem follows these principles exactly. Nodes are frozen. "Writing" creates new nodes. Multiple paths can safely share nodes because nodes never change.

This is why Clojure's persistent data structures, Haskell's pure values, and Git's object store all use similar ideas. **Content addressing + immutability = safe, efficient, verifiable data.**

## Trade-offs

Nothing is free. This approach has costs:

1. **Memory**: Old versions accumulate. You need garbage collection to reclaim space from unreachable nodes.

2. **Performance**: Creating new nodes for every change can be slower than in-place mutation for write-heavy workloads.

3. **Complexity**: Path resolution requires extra indirection through the hash table.

For many use cases—especially those valuing history, integrity, and safe concurrency—these trade-offs are worthwhile.

## Conclusion

Content addressing transforms how we think about data. Instead of "where is this file?" we ask "what is this content's identity?" Instead of destructive updates, we create new versions while sharing unchanged structure.

This pattern appears everywhere: Git, IPFS, Nix, Docker layers, and many database internals. Understanding it opens doors to building robust, elegant systems.

The full implementation in [DagShell](https://github.com/queelius/dagshell) extends these ideas with a complete POSIX-like interface, demonstrating how content addressing can underpin a full virtual filesystem.

---

*Next in this series: [Unix Philosophy in Python](#) — building composable commands with method chaining.*
