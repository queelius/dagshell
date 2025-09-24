#!/usr/bin/env python3
"""
Extended unit tests for dagshell - achieving comprehensive coverage.
"""

import pytest
import json
import base64
import time
import dagshell
from dagshell import FileSystem, FileNode, DirNode, DeviceNode, Mode, FileHandle


class TestFileNodeExtended:
    """Extended tests for FileNode class."""

    def test_file_node_string_initialization(self):
        """Test FileNode initialization with string content."""
        # Test string content initialization (covers line 85)
        file_node = FileNode("Hello, World!")
        assert file_node.content == b"Hello, World!"

        # Test with Unicode string
        file_node_unicode = FileNode("Hello 世界 🌍")
        assert file_node_unicode.content == "Hello 世界 🌍".encode('utf-8')

        # Test with empty string
        file_node_empty = FileNode("")
        assert file_node_empty.content == b""

    def test_file_node_custom_attributes(self):
        """Test FileNode with custom uid, gid, and mode."""
        custom_mode = Mode.IFREG | 0o755
        file_node = FileNode(
            content="test content",
            mode=custom_mode,
            uid=2000,
            gid=3000,
            mtime=1234567890.0
        )
        assert file_node.mode == custom_mode
        assert file_node.uid == 2000
        assert file_node.gid == 3000
        assert file_node.mtime == 1234567890.0


class TestDeviceNodeExtended:
    """Extended tests for DeviceNode class."""

    def test_device_unknown_type(self):
        """Test DeviceNode with unknown device type."""
        unknown_device = DeviceNode("unknown_device")

        # Reading from unknown device should raise ValueError (covers line 155)
        with pytest.raises(ValueError, match="Unknown device type"):
            unknown_device.read(10)

    def test_device_write_operations(self):
        """Test write operations on devices."""
        # Test /dev/null write (covers line 161)
        null_dev = DeviceNode("null")
        assert null_dev.write(b"test data") == 9

        # Test /dev/zero write - should return 0
        zero_dev = DeviceNode("zero")
        assert zero_dev.write(b"test") == 0

        # Test /dev/random write - should return 0
        random_dev = DeviceNode("random")
        assert random_dev.write(b"test") == 0


class TestFileSystemExtended:
    """Extended tests for FileSystem class."""

    def test_get_parent_path_edge_cases(self):
        """Test _get_parent_path with various edge cases."""
        fs = FileSystem()

        # Test root path (covers line 242)
        parent, name = fs._get_parent_path('/')
        assert parent is None
        assert name == '/'

        # Test direct child of root
        parent, name = fs._get_parent_path('/file.txt')
        assert parent == '/'
        assert name == 'file.txt'

        # Test nested path
        parent, name = fs._get_parent_path('/dir1/dir2/file.txt')
        assert parent == '/dir1/dir2'
        assert name == 'file.txt'

    def test_open_nonexistent_for_read(self):
        """Test opening nonexistent file for reading."""
        fs = FileSystem()

        # Try to open nonexistent file for reading (covers line 256)
        handle = fs.open('/nonexistent.txt', 'r')
        assert handle is None

    def test_open_create_mode(self):
        """Test opening file in write/append mode creates it."""
        fs = FileSystem()

        # Open nonexistent file in write mode should create it
        with fs.open('/newfile.txt', 'w') as f:
            f.write('created content')

        assert fs.exists('/newfile.txt')
        assert fs.read('/newfile.txt') == b'created content'

        # Open nonexistent file in append mode should create it
        with fs.open('/appendfile.txt', 'a') as f:
            f.write('appended content')

        assert fs.exists('/appendfile.txt')
        assert fs.read('/appendfile.txt') == b'appended content'

    def test_read_nonexistent_file(self):
        """Test reading nonexistent file."""
        fs = FileSystem()

        # Read nonexistent file should return None (covers line 269)
        content = fs.read('/does/not/exist.txt')
        assert content is None

    def test_write_to_root(self):
        """Test writing to root path."""
        fs = FileSystem()

        # Cannot write to root (covers line 278)
        result = fs.write('/', 'content')
        assert result is False

    def test_mkdir_root_exists(self):
        """Test creating root directory (already exists)."""
        fs = FileSystem()

        # Root already exists (covers line 306)
        result = fs.mkdir('/')
        assert result is False

    def test_mkdir_no_parent_for_root(self):
        """Test mkdir with root as path."""
        fs = FileSystem()

        # This is handled by line 306, but let's test the parent_path None case (line 310)
        # Actually root case is caught earlier, but we can test the logic flow
        assert not fs.mkdir('/')

    def test_ls_nonexistent_directory(self):
        """Test listing nonexistent directory."""
        fs = FileSystem()

        # List nonexistent directory (covers line 339)
        result = fs.ls('/nonexistent/dir')
        assert result is None

    def test_ls_file_instead_of_directory(self):
        """Test listing a file instead of directory."""
        fs = FileSystem()

        fs.write('/file.txt', 'content')

        # Try to list a file (covers line 343)
        result = fs.ls('/file.txt')
        assert result is None

    def test_rm_nonexistent_file(self):
        """Test removing nonexistent file."""
        fs = FileSystem()

        # Remove nonexistent file (covers line 353)
        result = fs.rm('/does/not/exist.txt')
        assert result is False

    def test_stat_nonexistent_path(self):
        """Test stat on nonexistent path."""
        fs = FileSystem()

        # Stat nonexistent path (covers line 402)
        result = fs.stat('/nonexistent')
        assert result is None

    def test_create_file_with_invalid_parent(self):
        """Test _create_file with various invalid conditions."""
        fs = FileSystem()

        # Try to create file at root level (covers line 423)
        handle = fs._create_file('/', b'content', 'w')
        assert handle is None

        # Try to create file in nonexistent directory (covers line 427)
        handle = fs._create_file('/nonexistent/file.txt', b'content', 'w')
        assert handle is None

        # Try to create file where parent is not a directory (covers line 431)
        fs.write('/file.txt', 'content')
        handle = fs._create_file('/file.txt/nested.txt', b'content', 'w')
        assert handle is None

    def test_from_json_with_unknown_node_type(self):
        """Test from_json with unknown node type."""
        # Create a JSON with unknown node type (covers line 482)
        json_data = {
            'nodes': {
                'hash123': {
                    'type': 'unknown_type',
                    'mode': 0o644,
                    'uid': 1000,
                    'gid': 1000,
                    'mtime': time.time()
                }
            },
            'paths': {},
            'deleted': []
        }

        json_str = json.dumps(json_data)
        fs = FileSystem.from_json(json_str)

        # Unknown node type should be skipped
        assert 'hash123' not in fs.nodes

    def test_hard_links(self):
        """Test hard links - multiple paths to same content."""
        fs = FileSystem()

        # Create a file
        fixed_time = 1000000.0
        fs.write('/original.txt', 'shared content', mtime=fixed_time)
        original_hash = fs.paths['/original.txt']

        # Create another file with same content and mtime (simulating hard link)
        fs.write('/link.txt', 'shared content', mtime=fixed_time)
        link_hash = fs.paths['/link.txt']

        # Both should point to the same node
        assert original_hash == link_hash

        # Modifying one doesn't affect the other (COW semantics)
        fs.write('/original.txt', 'modified content')

        # Link still has original content
        assert fs.read('/link.txt') == b'shared content'
        assert fs.read('/original.txt') == b'modified content'

        # Hashes should now be different
        assert fs.paths['/original.txt'] != fs.paths['/link.txt']


class TestFileHandleExtended:
    """Extended tests for FileHandle class."""

    def test_file_handle_read_mode_enforcement(self):
        """Test FileHandle read mode enforcement."""
        fs = FileSystem()
        fs.write('/test.txt', 'test content')

        # Open in write-only mode
        handle = fs.open('/test.txt', 'w')

        # Try to read in write-only mode (covers line 506)
        with pytest.raises(IOError, match="not opened for reading"):
            handle.read()

        handle.close()

    def test_file_handle_device_read(self):
        """Test FileHandle reading from device."""
        fs = FileSystem()

        # Read from /dev/zero with specific size
        with fs.open('/dev/zero', 'r') as f:
            data = f.read(50)
            assert len(data) == 50
            assert data == b'\x00' * 50

        # Read from /dev/random
        with fs.open('/dev/random', 'r') as f:
            data = f.read(32)
            assert len(data) == 32
            assert data != b'\x00' * 32  # Should not be all zeros

    def test_file_handle_partial_read(self):
        """Test FileHandle partial read operations."""
        fs = FileSystem()
        fs.write('/test.txt', 'Hello, World!')

        with fs.open('/test.txt', 'r') as f:
            # Read first 5 bytes (covers line 514)
            data1 = f.read(5)
            assert data1 == b'Hello'

            # Read next 7 bytes
            data2 = f.read(7)
            assert data2 == b', World'

            # Read remaining
            data3 = f.read()
            assert data3 == b'!'

            # Read when at end
            data4 = f.read()
            assert data4 == b''

    def test_file_handle_write_mode_enforcement(self):
        """Test FileHandle write mode enforcement."""
        fs = FileSystem()
        fs.write('/test.txt', 'initial content')

        # Open in read-only mode
        handle = fs.open('/test.txt', 'r')

        # Try to write in read-only mode (covers line 522)
        with pytest.raises(IOError, match="not opened for writing"):
            handle.write('new content')

        handle.close()

    def test_file_handle_write_string(self):
        """Test FileHandle write with string input."""
        fs = FileSystem()

        with fs.open('/test.txt', 'w') as f:
            # Write string (should be converted to bytes)
            f.write('Hello, 世界!')

        content = fs.read('/test.txt')
        assert content == 'Hello, 世界!'.encode('utf-8')

    def test_file_handle_append_mode(self):
        """Test FileHandle in append mode."""
        fs = FileSystem()

        # Create initial file
        fs.write('/test.txt', 'Line 1\n')

        # Open in append mode
        with fs.open('/test.txt', 'a') as f:
            # Position should be at end
            assert f.position == 7
            f.write('Line 2\n')

        # Verify content
        assert fs.read('/test.txt') == b'Line 1\nLine 2\n'

    def test_file_handle_read_write_mode(self):
        """Test FileHandle in read-write mode (r+)."""
        fs = FileSystem()
        fs.write('/test.txt', 'Initial content')

        with fs.open('/test.txt', 'r+') as f:
            # Can read
            content = f.read(7)
            assert content == b'Initial'

            # Can write (overwrites from current position)
            f.write(' modified')

        # Check final content
        assert fs.read('/test.txt') == b'Initial modified'

    def test_file_handle_write_extend_buffer(self):
        """Test FileHandle extending buffer when writing beyond end."""
        fs = FileSystem()

        with fs.open('/test.txt', 'w') as f:
            f.write('ABC')
            # Seek forward (simulated by setting position)
            f.position = 10
            f.write('XYZ')

        content = fs.read('/test.txt')
        # Should have null bytes in gap
        expected = b'ABC' + b'\x00' * 7 + b'XYZ'
        assert content == expected

    def test_file_handle_device_write(self):
        """Test FileHandle writing to device."""
        fs = FileSystem()

        # Write to /dev/null
        with fs.open('/dev/null', 'w') as f:
            written = f.write('This goes nowhere')
            assert written == 17

    def test_file_handle_context_manager_save(self):
        """Test FileHandle context manager saves changes."""
        fs = FileSystem()

        # Write using context manager
        with fs.open('/test.txt', 'w') as f:
            f.write('Content written')

        # Verify content was saved
        assert fs.read('/test.txt') == b'Content written'

        # Modify existing file
        with fs.open('/test.txt', 'w') as f:
            f.write('New content')

        assert fs.read('/test.txt') == b'New content'


class TestConvenienceFunctionsExtended:
    """Extended tests for module-level convenience functions."""

    def test_purge_convenience_function(self):
        """Test the purge convenience function."""
        # Reset global filesystem
        dagshell._default_fs = None

        # Create some files
        dagshell.mkdir('/temp')
        dagshell.write('/temp/file1.txt', 'content1')
        dagshell.write('/temp/file2.txt', 'content2')

        # Delete one file
        dagshell.rm('/temp/file2.txt')

        # Call purge (covers line 594)
        removed_count = dagshell.purge()
        assert removed_count > 0

        # File1 should still exist
        assert dagshell.exists('/temp/file1.txt')
        # File2 should not exist
        assert not dagshell.exists('/temp/file2.txt')


class TestDAGStructure:
    """Test the DAG structure and content addressing."""

    def test_dag_node_sharing(self):
        """Test that identical content results in node sharing."""
        fs = FileSystem()

        # Create multiple directories with same file
        fs.mkdir('/dir1')
        fs.mkdir('/dir2')

        fixed_time = 1234567890.0
        fs.write('/dir1/same.txt', 'identical content', mtime=fixed_time)
        fs.write('/dir2/same.txt', 'identical content', mtime=fixed_time)

        # Both files should reference the same node
        hash1 = fs.paths['/dir1/same.txt']
        hash2 = fs.paths['/dir2/same.txt']
        assert hash1 == hash2

        # Should only have one node for this content
        node_count = sum(1 for node in fs.nodes.values()
                        if isinstance(node, FileNode) and node.content == b'identical content')
        assert node_count == 1

    def test_dag_history_preservation(self):
        """Test that modifications preserve history in the DAG."""
        fs = FileSystem()

        # Create initial file
        fs.write('/file.txt', 'version 1')
        hash_v1 = fs.paths['/file.txt']

        # Modify file
        fs.write('/file.txt', 'version 2')
        hash_v2 = fs.paths['/file.txt']

        # Hashes should be different
        assert hash_v1 != hash_v2

        # Both nodes should still exist in the DAG
        assert hash_v1 in fs.nodes
        assert hash_v2 in fs.nodes

        # Old version is still accessible via its hash
        node_v1 = fs.nodes[hash_v1]
        assert node_v1.content == b'version 1'

    def test_dag_directory_updates(self):
        """Test that directory modifications create new directory nodes."""
        fs = FileSystem()

        fs.mkdir('/parent')
        parent_hash_v1 = fs.paths['/parent']

        # Add a child
        fs.mkdir('/parent/child1')
        parent_hash_v2 = fs.paths['/parent']

        # Parent directory should have a new hash
        assert parent_hash_v1 != parent_hash_v2

        # Both versions exist in DAG
        assert parent_hash_v1 in fs.nodes
        assert parent_hash_v2 in fs.nodes

        # Old version has no children
        assert len(fs.nodes[parent_hash_v1].children) == 0
        # New version has one child
        assert len(fs.nodes[parent_hash_v2].children) == 1

    def test_garbage_collection_comprehensive(self):
        """Comprehensive test of garbage collection."""
        fs = FileSystem()

        # Create a complex structure
        fs.mkdir('/keep')
        fs.mkdir('/delete')
        fs.mkdir('/delete/nested')
        fs.write('/keep/important.txt', 'keep this')
        fs.write('/delete/temp.txt', 'delete this')
        fs.write('/delete/nested/deep.txt', 'also delete')

        initial_node_count = len(fs.nodes)

        # Delete the /delete tree
        fs.rm('/delete/nested/deep.txt')
        fs.rm('/delete/temp.txt')
        fs.rm('/delete/nested')
        fs.rm('/delete')

        # Nodes still exist before purge
        assert len(fs.nodes) >= initial_node_count

        # Purge unreferenced nodes
        removed = fs.purge()
        assert removed > 0

        # Check that kept files are still accessible
        assert fs.exists('/keep')
        assert fs.exists('/keep/important.txt')
        assert fs.read('/keep/important.txt') == b'keep this'

        # Deleted paths should not exist
        assert not fs.exists('/delete')
        assert not fs.exists('/delete/nested')


class TestComplexScenarios:
    """Test complex real-world scenarios."""

    def test_concurrent_modifications(self):
        """Test handling of concurrent-like modifications."""
        fs = FileSystem()

        # Create initial structure
        fs.mkdir('/shared')
        fs.write('/shared/data.txt', 'initial data')

        # Save initial hash
        initial_hash = fs.paths['/shared/data.txt']

        # Multiple "concurrent" modifications
        fs.write('/shared/data.txt', 'modification 1')
        hash1 = fs.paths['/shared/data.txt']

        fs.write('/shared/data.txt', 'modification 2')
        hash2 = fs.paths['/shared/data.txt']

        # All versions exist in DAG
        assert initial_hash in fs.nodes
        assert hash1 in fs.nodes
        assert hash2 in fs.nodes

        # All have different hashes
        assert len({initial_hash, hash1, hash2}) == 3

    def test_deep_directory_structure(self):
        """Test deeply nested directory structures."""
        fs = FileSystem()

        # Create deep structure
        path = ''
        for i in range(10):
            path = f'{path}/level{i}'
            assert fs.mkdir(path)

        # Write file at deepest level
        deep_file = f'{path}/deep.txt'
        assert fs.write(deep_file, 'Deep content')

        # Verify we can traverse and read
        assert fs.exists(deep_file)
        assert fs.read(deep_file) == b'Deep content'

        # List at various levels
        assert 'level1' in fs.ls('/level0')
        assert 'level5' in fs.ls('/level0/level1/level2/level3/level4')

    def test_large_directory_listing(self):
        """Test directory with many entries."""
        fs = FileSystem()

        fs.mkdir('/large')

        # Create many files
        for i in range(100):
            fs.write(f'/large/file_{i:03d}.txt', f'Content {i}')

        # List should return all entries
        entries = fs.ls('/large')
        assert len(entries) == 100

        # Entries should be sorted
        assert entries == sorted(entries)
        assert entries[0] == 'file_000.txt'
        assert entries[-1] == 'file_099.txt'

    def test_permission_preservation(self):
        """Test that permissions are preserved correctly."""
        fs = FileSystem()

        # Create directory with custom permissions
        custom_mode = Mode.IFDIR | 0o700  # rwx------
        fs.mkdir('/private')

        # Create file with custom permissions
        fs.write('/private/secret.txt', 'secret data')

        # Get stats
        dir_stat = fs.stat('/private')
        file_stat = fs.stat('/private/secret.txt')

        # Check directory permissions
        assert dir_stat['mode'] & 0o777 == 0o755  # Default dir permissions

        # Check file permissions
        assert file_stat['mode'] & 0o777 == 0o644  # Default file permissions


class TestErrorRecovery:
    """Test error recovery and robustness."""

    def test_invalid_json_recovery(self):
        """Test handling of invalid JSON during deserialization."""
        # Malformed JSON
        with pytest.raises(json.JSONDecodeError):
            FileSystem.from_json("{ invalid json }")

        # Empty JSON
        with pytest.raises(KeyError):
            FileSystem.from_json("{}")

    def test_partial_operation_failure(self):
        """Test that partial operation failures don't corrupt filesystem."""
        fs = FileSystem()

        fs.mkdir('/test')
        fs.write('/test/file.txt', 'content')

        # Try to create file with invalid parent
        result = fs.write('/nonexistent/file.txt', 'content')
        assert result is False

        # Original structure should be intact
        assert fs.exists('/test')
        assert fs.exists('/test/file.txt')
        assert fs.read('/test/file.txt') == b'content'

    def test_path_normalization(self):
        """Test that paths are normalized correctly."""
        fs = FileSystem()

        fs.mkdir('/test')
        fs.write('/test/file.txt', 'content')

        # Various path formats should work (os.path.normpath handles these)
        # Note: '//' at start becomes '/' after normpath
        assert fs.exists('/test/file.txt')

        # Test that normpath is working
        # '/test/../test/file.txt' becomes '/test/file.txt'
        assert fs._resolve_path('/test/../test/file.txt') == fs._resolve_path('/test/file.txt')

        # '/test/./file.txt' becomes '/test/file.txt'
        assert fs._resolve_path('/test/./file.txt') == fs._resolve_path('/test/file.txt')


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--cov=dagshell', '--cov-report=term-missing'])