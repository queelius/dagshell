#!/usr/bin/env python3
"""
dagshell - A content-addressable virtual filesystem implemented as a DAG.

Core philosophy:
- Every filesystem object is immutable and content-addressed
- Changes create new nodes, preserving history
- Simple, composable operations following Unix philosophy
"""

import hashlib
import json
import time
import os
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Set, Union, Any
from enum import IntEnum
from collections import defaultdict
import random
import string


class Mode(IntEnum):
    """Unix-style file permissions."""
    # File types
    IFREG = 0o100000  # regular file
    IFDIR = 0o040000  # directory
    IFCHR = 0o020000  # character device

    # Permissions
    IRUSR = 0o400  # owner read
    IWUSR = 0o200  # owner write
    IXUSR = 0o100  # owner execute
    IRGRP = 0o040  # group read
    IWGRP = 0o020  # group write
    IXGRP = 0o010  # group execute
    IROTH = 0o004  # other read
    IWOTH = 0o002  # other write
    IXOTH = 0o001  # other execute

    # Common combinations
    FILE_DEFAULT = IFREG | IRUSR | IWUSR | IRGRP | IROTH  # 0o100644
    DIR_DEFAULT = IFDIR | IRUSR | IWUSR | IXUSR | IRGRP | IXGRP | IROTH | IXOTH  # 0o040755


@dataclass(frozen=True)
class Node:
    """Base class for all filesystem nodes."""
    mode: int
    uid: int = 1000
    gid: int = 1000
    mtime: float = field(default_factory=time.time)

    def compute_hash(self) -> str:
        """Compute SHA256 hash of this node including all metadata."""
        # Create a stable string representation
        data = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()

    def to_dict(self) -> dict:
        """Convert node to dictionary for serialization."""
        return asdict(self)

    def is_file(self) -> bool:
        """Check if this is a regular file."""
        return (self.mode & Mode.IFDIR) == 0 and (self.mode & Mode.IFCHR) == 0

    def is_dir(self) -> bool:
        """Check if this is a directory."""
        return (self.mode & Mode.IFDIR) != 0

    def is_device(self) -> bool:
        """Check if this is a device."""
        return (self.mode & Mode.IFCHR) != 0


@dataclass(frozen=True)
class FileNode(Node):
    """Regular file node."""
    content: bytes = b""

    def __init__(self, content: Union[str, bytes] = b"", mode: int = Mode.FILE_DEFAULT,
                 uid: int = 1000, gid: int = 1000, mtime: Optional[float] = None):
        if isinstance(content, str):
            content = content.encode('utf-8')
        object.__setattr__(self, 'content', content)
        object.__setattr__(self, 'mode', mode)
        object.__setattr__(self, 'uid', uid)
        object.__setattr__(self, 'gid', gid)
        object.__setattr__(self, 'mtime', mtime or time.time())

    def to_dict(self) -> dict:
        d = super().to_dict()
        # Store content as base64 for JSON serialization
        import base64
        d['content'] = base64.b64encode(self.content).decode('ascii')
        d['type'] = 'file'
        return d


@dataclass(frozen=True)
class DirNode(Node):
    """Directory node containing references to child nodes."""
    children: Dict[str, str] = field(default_factory=dict)  # name -> hash

    def __init__(self, children: Optional[Dict[str, str]] = None,
                 mode: int = Mode.DIR_DEFAULT, uid: int = 1000,
                 gid: int = 1000, mtime: Optional[float] = None):
        object.__setattr__(self, 'children', children or {})
        object.__setattr__(self, 'mode', mode)
        object.__setattr__(self, 'uid', uid)
        object.__setattr__(self, 'gid', gid)
        object.__setattr__(self, 'mtime', mtime or time.time())

    def to_dict(self) -> dict:
        d = super().to_dict()
        d['type'] = 'dir'
        return d

    def with_child(self, name: str, hash: str) -> 'DirNode':
        """Return a new DirNode with an additional child."""
        new_children = dict(self.children)
        new_children[name] = hash
        return DirNode(new_children, self.mode, self.uid, self.gid)

    def without_child(self, name: str) -> 'DirNode':
        """Return a new DirNode without the specified child."""
        new_children = dict(self.children)
        new_children.pop(name, None)
        return DirNode(new_children, self.mode, self.uid, self.gid)


@dataclass(frozen=True)
class DeviceNode(Node):
    """Virtual device node."""
    device_type: str = ""  # 'null', 'zero', 'random'

    def __init__(self, device_type: str, mode: int = Mode.IFCHR | 0o666,
                 uid: int = 0, gid: int = 0, mtime: Optional[float] = None):
        object.__setattr__(self, 'device_type', device_type)
        object.__setattr__(self, 'mode', mode)
        object.__setattr__(self, 'uid', uid)
        object.__setattr__(self, 'gid', gid)
        object.__setattr__(self, 'mtime', mtime or time.time())

    def read(self, size: int = 1024) -> bytes:
        """Read from the device."""
        if self.device_type == 'null':
            return b''
        elif self.device_type == 'zero':
            return b'\x00' * size
        elif self.device_type == 'random':
            return os.urandom(size)
        else:
            raise ValueError(f"Unknown device type: {self.device_type}")

    def write(self, data: bytes) -> int:
        """Write to the device (always succeeds for these devices)."""
        if self.device_type == 'null':
            return len(data)  # Black hole - accepts everything
        return 0

    def to_dict(self) -> dict:
        d = super().to_dict()
        d['type'] = 'device'
        return d


class FileSystem:
    """
    Content-addressable virtual filesystem.

    The filesystem is a DAG where each node is identified by its content hash.
    Path mappings are maintained separately from the DAG structure.
    """

    def __init__(self):
        # The DAG: hash -> Node
        self.nodes: Dict[str, Node] = {}

        # Path index: absolute path -> hash
        self.paths: Dict[str, str] = {}

        # Reference counting for garbage collection
        self.refs: Dict[str, int] = defaultdict(int)

        # Deleted paths (soft delete until purge)
        self.deleted: Set[str] = set()

        # Initialize root directory
        self._init_filesystem()

    def _init_filesystem(self):
        """Initialize the filesystem with root and basic structure."""
        # Create root directory
        root = DirNode()
        root_hash = self._add_node(root)
        self.paths['/'] = root_hash

        # Create /etc with user/group files
        etc = DirNode()

        # Create /etc/passwd
        passwd_content = b"""root:x:0:0:root:/root:/bin/sh
user:x:1000:1000:Default User:/home/user:/bin/sh
alice:x:1001:1001:Alice:/home/alice:/bin/sh
bob:x:1002:1002:Bob:/home/bob:/bin/sh"""
        passwd_node = FileNode(passwd_content, mode=Mode.FILE_DEFAULT)
        passwd_hash = self._add_node(passwd_node)
        etc = etc.with_child('passwd', passwd_hash)

        # Create /etc/group
        group_content = b"""root:x:0:
user:x:1000:
alice:x:1001:
bob:x:1002:
developers:x:2000:alice,bob"""
        group_node = FileNode(group_content, mode=Mode.FILE_DEFAULT)
        group_hash = self._add_node(group_node)
        etc = etc.with_child('group', group_hash)

        etc_hash = self._add_node(etc)
        root = root.with_child('etc', etc_hash)
        self.paths['/etc'] = etc_hash
        self.paths['/etc/passwd'] = passwd_hash
        self.paths['/etc/group'] = group_hash

        # Create /dev with devices
        dev = DirNode()
        dev_hash = self._add_node(dev)

        # Add virtual devices
        for device_type in ['null', 'zero', 'random']:
            device = DeviceNode(device_type)
            device_hash = self._add_node(device)
            dev = dev.with_child(device_type, device_hash)

        # Update dev directory with devices
        dev_hash = self._add_node(dev)

        # Update root with dev and etc
        root = root.with_child('dev', dev_hash)
        root_hash = self._add_node(root)
        self.paths['/'] = root_hash
        self.paths['/dev'] = dev_hash

        # Map device paths
        for device_type in ['null', 'zero', 'random']:
            device_hash = dev.children[device_type]
            self.paths[f'/dev/{device_type}'] = device_hash

    def _add_node(self, node: Node) -> str:
        """Add a node to the DAG and return its hash."""
        node_hash = node.compute_hash()
        if node_hash not in self.nodes:
            self.nodes[node_hash] = node
        return node_hash

    def _resolve_path(self, path: str) -> Optional[str]:
        """Resolve a path to a node hash."""
        path = os.path.normpath(path)
        if path in self.deleted:
            return None
        return self.paths.get(path)

    def _get_parent_path(self, path: str) -> tuple[str, str]:
        """Split path into parent directory and basename."""
        path = os.path.normpath(path)
        if path == '/':
            return None, '/'
        parent = os.path.dirname(path)
        name = os.path.basename(path)
        return parent, name

    # Core filesystem operations

    def open(self, path: str, mode: str = 'r') -> Optional['FileHandle']:
        """Open a file and return a handle."""
        node_hash = self._resolve_path(path)
        if not node_hash:
            if 'w' in mode or 'a' in mode:
                # Create new file
                return self._create_file(path, b'', mode)
            return None

        node = self.nodes[node_hash]
        if node.is_dir():
            raise IsADirectoryError(f"{path} is a directory")

        return FileHandle(self, path, node, mode)

    def read(self, path: str) -> Optional[bytes]:
        """Read entire file contents."""
        handle = self.open(path, 'r')
        if handle:
            return handle.read()
        return None

    def write(self, path: str, content: Union[str, bytes], mtime: Optional[float] = None) -> bool:
        """Write content to a file (creates if doesn't exist)."""
        if isinstance(content, str):
            content = content.encode('utf-8')

        parent_path, name = self._get_parent_path(path)
        if parent_path is None:
            return False

        parent_hash = self._resolve_path(parent_path)
        if not parent_hash:
            return False

        parent = self.nodes[parent_hash]
        if not parent.is_dir():
            return False

        # Create new file node
        file_node = FileNode(content, mtime=mtime)
        file_hash = self._add_node(file_node)

        # Update parent directory
        new_parent = parent.with_child(name, file_hash)
        new_parent_hash = self._add_node(new_parent)

        # Update paths
        self.paths[parent_path] = new_parent_hash
        self.paths[path] = file_hash
        self.deleted.discard(path)

        return True

    def mkdir(self, path: str, mode: int = Mode.DIR_DEFAULT) -> bool:
        """Create a directory."""
        if self._resolve_path(path):
            return False  # Already exists

        parent_path, name = self._get_parent_path(path)
        if parent_path is None:
            return False

        parent_hash = self._resolve_path(parent_path)
        if not parent_hash:
            return False

        parent = self.nodes[parent_hash]
        if not parent.is_dir():
            return False

        # Create new directory
        dir_node = DirNode(mode=mode)
        dir_hash = self._add_node(dir_node)

        # Update parent
        new_parent = parent.with_child(name, dir_hash)
        new_parent_hash = self._add_node(new_parent)

        # Update paths
        self.paths[parent_path] = new_parent_hash
        self.paths[path] = dir_hash
        self.deleted.discard(path)

        return True

    def ls(self, path: str = '/') -> Optional[List[str]]:
        """List directory contents."""
        node_hash = self._resolve_path(path)
        if not node_hash:
            return None

        node = self.nodes[node_hash]
        if not node.is_dir():
            return None

        return sorted(node.children.keys())

    def rm(self, path: str) -> bool:
        """Soft delete - removes path mapping but keeps data."""
        if path == '/':
            return False  # Cannot delete root

        if path not in self.paths:
            return False

        parent_path, name = self._get_parent_path(path)
        parent_hash = self._resolve_path(parent_path)
        if parent_hash:
            parent = self.nodes[parent_hash]
            if parent.is_dir() and name in parent.children:
                # Remove from parent directory
                new_parent = parent.without_child(name)
                new_parent_hash = self._add_node(new_parent)
                self.paths[parent_path] = new_parent_hash

        # Mark as deleted
        self.deleted.add(path)
        del self.paths[path]
        return True

    def purge(self) -> int:
        """Garbage collection - remove unreferenced nodes."""
        # Build reference graph
        referenced = set()

        def mark_referenced(hash: str):
            if hash in referenced:
                return
            referenced.add(hash)
            node = self.nodes.get(hash)
            if node and node.is_dir():
                for child_hash in node.children.values():
                    mark_referenced(child_hash)

        # Mark all nodes reachable from active paths
        for hash in self.paths.values():
            mark_referenced(hash)

        # Remove unreferenced nodes
        to_remove = set(self.nodes.keys()) - referenced
        for hash in to_remove:
            del self.nodes[hash]

        # Clear deleted set
        self.deleted.clear()

        return len(to_remove)

    def stat(self, path: str) -> Optional[dict]:
        """Get file/directory statistics."""
        node_hash = self._resolve_path(path)
        if not node_hash:
            return None

        node = self.nodes[node_hash]
        return {
            'type': 'file' if node.is_file() else 'dir' if node.is_dir() else 'device',
            'mode': node.mode,
            'uid': node.uid,
            'gid': node.gid,
            'mtime': node.mtime,
            'size': len(node.content) if node.is_file() else 0,
            'hash': node_hash
        }

    def exists(self, path: str) -> bool:
        """Check if a path exists."""
        return self._resolve_path(path) is not None

    def _create_file(self, path: str, content: bytes, mode: str, mtime: Optional[float] = None) -> Optional['FileHandle']:
        """Create a new file."""
        parent_path, name = self._get_parent_path(path)
        if parent_path is None:
            return None

        parent_hash = self._resolve_path(parent_path)
        if not parent_hash:
            return None

        parent = self.nodes[parent_hash]
        if not parent.is_dir():
            return None

        # Create file node
        file_node = FileNode(content, mtime=mtime)
        file_hash = self._add_node(file_node)

        # Update parent
        new_parent = parent.with_child(name, file_hash)
        new_parent_hash = self._add_node(new_parent)

        # Update paths
        self.paths[parent_path] = new_parent_hash
        self.paths[path] = file_hash
        self.deleted.discard(path)

        return FileHandle(self, path, file_node, mode)

    # User and permission management

    def lookup_user(self, username: str) -> tuple[int, int]:
        """Look up user ID and primary group ID from /etc/passwd."""
        passwd_hash = self._resolve_path('/etc/passwd')
        if not passwd_hash:
            # Default if no passwd file
            return (1000, 1000) if username == 'user' else (0, 0)

        passwd_node = self.nodes[passwd_hash]
        content = passwd_node.content.decode('utf-8')

        for line in content.strip().split('\n'):
            parts = line.split(':')
            if parts[0] == username:
                return (int(parts[2]), int(parts[3]))

        # Default for unknown users
        return (1000, 1000)

    def get_user_groups(self, username: str) -> Set[int]:
        """Get all group IDs for a user from /etc/group."""
        uid, primary_gid = self.lookup_user(username)
        groups = {primary_gid}

        group_hash = self._resolve_path('/etc/group')
        if not group_hash:
            return groups

        group_node = self.nodes[group_hash]
        content = group_node.content.decode('utf-8')

        for line in content.strip().split('\n'):
            parts = line.split(':')
            if len(parts) >= 4:
                gid = int(parts[2])
                members = parts[3].split(',') if parts[3] else []
                if username in members:
                    groups.add(gid)

        return groups

    def check_permission(self, path: str, uid: int, gids: Set[int], permission: int) -> bool:
        """
        Check if user has specific permission for a path.

        Args:
            path: File/directory path
            uid: User ID
            gids: Set of group IDs the user belongs to
            permission: Permission bit to check (e.g., Mode.IRUSR, Mode.IWUSR)

        Returns:
            True if permission granted, False otherwise
        """
        node_hash = self._resolve_path(path)
        if not node_hash:
            return False

        node = self.nodes[node_hash]
        mode = node.mode

        # Root user (uid 0) has all permissions
        if uid == 0:
            return True

        # Owner permissions
        if uid == node.uid:
            if permission in [Mode.IRUSR, Mode.IRGRP, Mode.IROTH]:
                return bool(mode & Mode.IRUSR)
            elif permission in [Mode.IWUSR, Mode.IWGRP, Mode.IWOTH]:
                return bool(mode & Mode.IWUSR)
            elif permission in [Mode.IXUSR, Mode.IXGRP, Mode.IXOTH]:
                return bool(mode & Mode.IXUSR)

        # Group permissions
        if node.gid in gids:
            if permission in [Mode.IRUSR, Mode.IRGRP, Mode.IROTH]:
                return bool(mode & Mode.IRGRP)
            elif permission in [Mode.IWUSR, Mode.IWGRP, Mode.IWOTH]:
                return bool(mode & Mode.IWGRP)
            elif permission in [Mode.IXUSR, Mode.IXGRP, Mode.IXOTH]:
                return bool(mode & Mode.IXGRP)

        # Other permissions
        if permission in [Mode.IRUSR, Mode.IRGRP, Mode.IROTH]:
            return bool(mode & Mode.IROTH)
        elif permission in [Mode.IWUSR, Mode.IWGRP, Mode.IWOTH]:
            return bool(mode & Mode.IWOTH)
        elif permission in [Mode.IXUSR, Mode.IXGRP, Mode.IXOTH]:
            return bool(mode & Mode.IXOTH)

        return False

    def export_to_real(self, target_path: str, preserve_permissions: bool = True,
                      uid_map: Optional[Dict[int, int]] = None,
                      gid_map: Optional[Dict[int, int]] = None) -> int:
        """
        Export the virtual filesystem to a real filesystem.

        Args:
            target_path: Target directory for export
            preserve_permissions: Whether to preserve file modes
            uid_map: Mapping from virtual UIDs to real UIDs
            gid_map: Mapping from virtual GIDs to real GIDs

        Returns:
            Number of files/directories exported
        """
        import shutil

        # Default mappings (virtual -> real)
        if uid_map is None:
            uid_map = {0: 0, 1000: os.getuid(), 1001: os.getuid(), 1002: os.getuid()}
        if gid_map is None:
            gid_map = {0: 0, 1000: os.getgid(), 1001: os.getgid(), 1002: os.getgid()}

        # Create target directory if needed
        os.makedirs(target_path, exist_ok=True)

        exported = 0

        # Export all paths
        for vpath in sorted(self.paths.keys()):
            if vpath in self.deleted:
                continue

            node_hash = self.paths[vpath]
            node = self.nodes[node_hash]

            # Skip root directory itself
            if vpath == '/':
                continue

            # Calculate real path
            real_path = os.path.join(target_path, vpath.lstrip('/'))

            if node.is_dir():
                # Create directory
                os.makedirs(real_path, exist_ok=True)
                exported += 1

                if preserve_permissions:
                    # Set directory permissions (remove file type bits)
                    mode = node.mode & 0o777
                    try:
                        os.chmod(real_path, mode)
                    except:
                        pass  # Ignore permission errors

            elif node.is_file():
                # Create parent directory if needed
                parent_dir = os.path.dirname(real_path)
                os.makedirs(parent_dir, exist_ok=True)

                # Write file content
                import builtins
                with builtins.open(real_path, 'wb') as f:
                    f.write(node.content)
                exported += 1

                if preserve_permissions:
                    # Set file permissions (remove file type bits)
                    mode = node.mode & 0o777
                    try:
                        os.chmod(real_path, mode)
                    except:
                        pass  # Ignore permission errors

                # Try to set ownership if running as root
                if os.geteuid() == 0:
                    real_uid = uid_map.get(node.uid, node.uid)
                    real_gid = gid_map.get(node.gid, node.gid)
                    try:
                        os.chown(real_path, real_uid, real_gid)
                    except:
                        pass  # Ignore if can't change ownership

        return exported

    # Serialization

    def to_json(self) -> str:
        """Serialize filesystem to JSON."""
        data = {
            'nodes': {hash: node.to_dict() for hash, node in self.nodes.items()},
            'paths': self.paths,
            'deleted': list(self.deleted)
        }
        return json.dumps(data, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> 'FileSystem':
        """Deserialize filesystem from JSON."""
        data = json.loads(json_str)
        fs = cls.__new__(cls)
        fs.nodes = {}
        fs.paths = data['paths']
        fs.deleted = set(data.get('deleted', []))
        fs.refs = defaultdict(int)

        # Reconstruct nodes
        import base64
        for hash, node_data in data['nodes'].items():
            node_type = node_data.pop('type', 'file')

            if node_type == 'file':
                content = base64.b64decode(node_data.pop('content', ''))
                node = FileNode(content=content, **{k: v for k, v in node_data.items() if k != 'content'})
            elif node_type == 'dir':
                node = DirNode(**{k: v for k, v in node_data.items() if k != 'type'})
            elif node_type == 'device':
                node = DeviceNode(**{k: v for k, v in node_data.items() if k != 'type'})
            else:
                continue

            fs.nodes[hash] = node

        return fs


class FileHandle:
    """Handle for reading/writing files."""

    def __init__(self, fs: FileSystem, path: str, node: Node, mode: str):
        self.fs = fs
        self.path = path
        self.node = node
        self.mode = mode
        self.position = 0
        self.buffer = bytearray(node.content if node.is_file() else b'')

        if 'a' in mode:
            self.position = len(self.buffer)

    def read(self, size: int = -1) -> bytes:
        """Read from file."""
        if 'r' not in self.mode and '+' not in self.mode:
            raise IOError("File not opened for reading")

        if self.node.is_device():
            return self.node.read(size if size > 0 else 1024)

        if size < 0:
            result = bytes(self.buffer[self.position:])
        else:
            result = bytes(self.buffer[self.position:self.position + size])

        self.position += len(result)
        return result

    def write(self, data: Union[str, bytes]) -> int:
        """Write to file."""
        if 'w' not in self.mode and 'a' not in self.mode and '+' not in self.mode:
            raise IOError("File not opened for writing")

        if isinstance(data, str):
            data = data.encode('utf-8')

        if self.node.is_device():
            return self.node.write(data)

        if 'w' in self.mode and self.position == 0:
            self.buffer = bytearray(data)
            self.position = len(data)
        else:
            # Extend buffer if necessary
            end_pos = self.position + len(data)
            if end_pos > len(self.buffer):
                self.buffer.extend(b'\x00' * (end_pos - len(self.buffer)))

            self.buffer[self.position:end_pos] = data
            self.position = end_pos

        return len(data)

    def close(self):
        """Close file and commit changes."""
        if 'w' in self.mode or 'a' in self.mode or ('+' in self.mode and self.buffer != self.node.content):
            # Save changes
            self.fs.write(self.path, bytes(self.buffer))

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# Convenience functions for a more Unix-like API

_default_fs = None

def get_fs() -> FileSystem:
    """Get the default filesystem instance."""
    global _default_fs
    if _default_fs is None:
        _default_fs = FileSystem()
    return _default_fs

def open(path: str, mode: str = 'r') -> Optional[FileHandle]:
    """Open a file."""
    return get_fs().open(path, mode)

def read(path: str) -> Optional[bytes]:
    """Read file contents."""
    return get_fs().read(path)

def write(path: str, content: Union[str, bytes], mtime: Optional[float] = None) -> bool:
    """Write content to file."""
    return get_fs().write(path, content, mtime)

def mkdir(path: str) -> bool:
    """Create directory."""
    return get_fs().mkdir(path)

def ls(path: str = '/') -> Optional[List[str]]:
    """List directory."""
    return get_fs().ls(path)

def rm(path: str) -> bool:
    """Remove file/directory."""
    return get_fs().rm(path)

def purge() -> int:
    """Run garbage collection."""
    return get_fs().purge()

def exists(path: str) -> bool:
    """Check if path exists."""
    return get_fs().exists(path)

def stat(path: str) -> Optional[dict]:
    """Get file statistics."""
    return get_fs().stat(path)