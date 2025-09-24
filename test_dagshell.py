#!/usr/bin/env python3
"""
Unit tests for dagshell - content-addressable virtual filesystem.
"""

import pytest
import json
import dagshell
from dagshell import FileSystem, FileNode, DirNode, DeviceNode, Mode


class TestNodes:
    """Test node classes and content addressing."""

    def test_file_node_hashing(self):
        """Test that identical files have the same hash."""
        # Use fixed mtime for deterministic hashing
        fixed_time = 1000000.0
        file1 = FileNode(b"hello world", mtime=fixed_time)
        file2 = FileNode(b"hello world", mtime=fixed_time)
        assert file1.compute_hash() == file2.compute_hash()

        # Different content should have different hash
        file3 = FileNode(b"goodbye world", mtime=fixed_time)
        assert file1.compute_hash() != file3.compute_hash()

        # Different metadata should have different hash
        file4 = FileNode(b"hello world", uid=2000, mtime=fixed_time)
        assert file1.compute_hash() != file4.compute_hash()

    def test_dir_node_immutability(self):
        """Test that directory nodes are immutable."""
        dir1 = DirNode()
        dir2 = dir1.with_child("test", "hash123")
        assert dir1.children == {}
        assert dir2.children == {"test": "hash123"}
        assert dir1.compute_hash() != dir2.compute_hash()

    def test_device_node_operations(self):
        """Test virtual device operations."""
        null_dev = DeviceNode("null")
        zero_dev = DeviceNode("zero")
        random_dev = DeviceNode("random")

        # Test /dev/null
        assert null_dev.read(10) == b''
        assert null_dev.write(b"test") == 4

        # Test /dev/zero
        assert zero_dev.read(5) == b'\x00' * 5

        # Test /dev/random
        random_data = random_dev.read(10)
        assert len(random_data) == 10
        assert random_data != b'\x00' * 10  # Should not be all zeros


class TestFileSystem:
    """Test filesystem operations."""

    def test_initialization(self):
        """Test filesystem initialization."""
        fs = FileSystem()
        assert fs.exists('/')
        assert fs.exists('/dev')
        assert fs.exists('/dev/null')
        assert fs.exists('/dev/zero')
        assert fs.exists('/dev/random')

    def test_create_and_read_file(self):
        """Test file creation and reading."""
        fs = FileSystem()

        # Create directory
        assert fs.mkdir('/home')
        assert fs.mkdir('/home/user')

        # Write file
        assert fs.write('/home/user/test.txt', 'Hello, World!')

        # Read file
        content = fs.read('/home/user/test.txt')
        assert content == b'Hello, World!'

        # Check file exists
        assert fs.exists('/home/user/test.txt')

    def test_directory_operations(self):
        """Test directory creation and listing."""
        fs = FileSystem()

        # Create nested directories
        assert fs.mkdir('/usr')
        assert fs.mkdir('/usr/local')
        assert fs.mkdir('/usr/local/bin')

        # List directories
        assert 'usr' in fs.ls('/')
        assert 'local' in fs.ls('/usr')
        assert fs.ls('/usr/local') == ['bin']  # Should contain 'bin' directory

        # Create files in directory
        fs.write('/usr/local/file1.txt', 'content1')
        fs.write('/usr/local/file2.txt', 'content2')
        assert sorted(fs.ls('/usr/local')) == ['bin', 'file1.txt', 'file2.txt']

    def test_file_handle_operations(self):
        """Test file handle read/write operations."""
        fs = FileSystem()
        fs.mkdir('/tmp')

        # Write using file handle
        with fs.open('/tmp/test.txt', 'w') as f:
            f.write('Line 1\n')
            f.write('Line 2\n')

        # Read using file handle
        with fs.open('/tmp/test.txt', 'r') as f:
            content = f.read()
            assert content == b'Line 1\nLine 2\n'

        # Append mode
        with fs.open('/tmp/test.txt', 'a') as f:
            f.write('Line 3\n')

        assert fs.read('/tmp/test.txt') == b'Line 1\nLine 2\nLine 3\n'

    def test_soft_delete_and_purge(self):
        """Test soft delete and garbage collection."""
        fs = FileSystem()

        # Create structure
        fs.mkdir('/data')
        fs.write('/data/file1.txt', 'important data')
        fs.write('/data/file2.txt', 'temporary data')

        initial_nodes = len(fs.nodes)

        # Soft delete
        assert fs.rm('/data/file2.txt')
        assert not fs.exists('/data/file2.txt')
        assert fs.exists('/data/file1.txt')

        # Nodes still exist before purge
        assert len(fs.nodes) >= initial_nodes

        # Purge removes unreferenced nodes
        removed = fs.purge()
        assert removed > 0
        assert len(fs.nodes) < initial_nodes

    def test_content_addressing(self):
        """Test that identical content results in same hash."""
        fs = FileSystem()

        fs.mkdir('/test1')
        fs.mkdir('/test2')

        # Write identical content to different paths with same mtime
        fixed_time = 1000000.0
        fs.write('/test1/file.txt', 'identical content', mtime=fixed_time)
        fs.write('/test2/file.txt', 'identical content', mtime=fixed_time)

        # Both files should reference the same node
        hash1 = fs.paths['/test1/file.txt']
        hash2 = fs.paths['/test2/file.txt']
        assert hash1 == hash2

    def test_stat_operation(self):
        """Test file statistics."""
        fs = FileSystem()

        fs.mkdir('/test')
        fs.write('/test/file.txt', 'test content')

        # Check directory stats
        dir_stat = fs.stat('/test')
        assert dir_stat['type'] == 'dir'
        assert dir_stat['mode'] & Mode.IFDIR

        # Check file stats
        file_stat = fs.stat('/test/file.txt')
        assert file_stat['type'] == 'file'
        assert file_stat['size'] == 12  # len('test content')
        assert file_stat['mode'] & Mode.IFREG

    def test_device_files(self):
        """Test virtual device files."""
        fs = FileSystem()

        # Test /dev/null
        with fs.open('/dev/null', 'w') as f:
            written = f.write('This disappears')
            assert written == 15

        with fs.open('/dev/null', 'r') as f:
            assert f.read() == b''

        # Test /dev/zero
        with fs.open('/dev/zero', 'r') as f:
            zeros = f.read(100)
            assert zeros == b'\x00' * 100

        # Test /dev/random
        with fs.open('/dev/random', 'r') as f:
            random_bytes = f.read(16)
            assert len(random_bytes) == 16


class TestSerialization:
    """Test JSON serialization/deserialization."""

    def test_round_trip_serialization(self):
        """Test that filesystem survives serialization."""
        fs1 = FileSystem()

        # Create complex structure
        fs1.mkdir('/home')
        fs1.mkdir('/home/user')
        fs1.mkdir('/home/user/documents')
        fs1.write('/home/user/documents/file1.txt', 'Document 1')
        fs1.write('/home/user/documents/file2.txt', 'Document 2')
        fs1.mkdir('/var')
        fs1.mkdir('/var/log')
        fs1.write('/var/log/system.log', 'System log entries')

        # Serialize
        json_str = fs1.to_json()

        # Deserialize
        fs2 = FileSystem.from_json(json_str)

        # Verify structure
        assert fs2.ls('/') == fs1.ls('/')
        assert fs2.ls('/home/user/documents') == fs1.ls('/home/user/documents')
        assert fs2.read('/home/user/documents/file1.txt') == b'Document 1'
        assert fs2.read('/var/log/system.log') == b'System log entries'

        # Verify hashes match
        assert fs2.paths == fs1.paths
        assert len(fs2.nodes) == len(fs1.nodes)

    def test_json_format(self):
        """Test JSON format structure."""
        fs = FileSystem()
        fs.mkdir('/test')
        fs.write('/test/file.txt', 'content')

        json_str = fs.to_json()
        data = json.loads(json_str)

        # Check structure
        assert 'nodes' in data
        assert 'paths' in data
        assert 'deleted' in data

        # Check that paths map to hashes
        assert '/test' in data['paths']
        assert '/test/file.txt' in data['paths']

        # Check that nodes exist
        test_hash = data['paths']['/test']
        assert test_hash in data['nodes']
        assert data['nodes'][test_hash]['type'] == 'dir'


class TestConvenienceFunctions:
    """Test module-level convenience functions."""

    def test_global_filesystem(self):
        """Test global filesystem instance."""
        # Reset global state
        dagshell._default_fs = None

        # Use convenience functions
        assert dagshell.mkdir('/test')
        assert dagshell.write('/test/file.txt', 'hello')
        assert dagshell.read('/test/file.txt') == b'hello'
        assert dagshell.exists('/test/file.txt')
        assert 'file.txt' in dagshell.ls('/test')
        assert dagshell.rm('/test/file.txt')
        assert not dagshell.exists('/test/file.txt')

        # Verify stat
        stat = dagshell.stat('/test')
        assert stat['type'] == 'dir'

    def test_open_convenience(self):
        """Test open convenience function."""
        dagshell._default_fs = None

        dagshell.mkdir('/tmp')

        with dagshell.open('/tmp/test.txt', 'w') as f:
            f.write('test content')

        with dagshell.open('/tmp/test.txt', 'r') as f:
            assert f.read() == b'test content'


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_cannot_delete_root(self):
        """Test that root directory cannot be deleted."""
        fs = FileSystem()
        assert not fs.rm('/')
        assert fs.exists('/')

    def test_cannot_create_duplicate(self):
        """Test that duplicate paths cannot be created."""
        fs = FileSystem()
        assert fs.mkdir('/test')
        assert not fs.mkdir('/test')  # Should fail

    def test_cannot_write_to_directory(self):
        """Test that writing to directory path fails."""
        fs = FileSystem()
        fs.mkdir('/test')
        # Cannot open directory for writing
        with pytest.raises(IsADirectoryError):
            fs.open('/test', 'w')

    def test_parent_must_be_directory(self):
        """Test that parent must be a directory."""
        fs = FileSystem()
        fs.write('/file.txt', 'content')
        # Cannot create file under a file
        assert not fs.write('/file.txt/nested.txt', 'content')
        assert not fs.mkdir('/file.txt/subdir')

    def test_nonexistent_parent(self):
        """Test operations with nonexistent parent."""
        fs = FileSystem()
        # Cannot create file in nonexistent directory
        assert not fs.write('/nonexistent/file.txt', 'content')
        assert not fs.mkdir('/nonexistent/subdir')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])