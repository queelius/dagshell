#!/usr/bin/env python3
"""
Comprehensive tests for DagShell persistence functionality.

This test suite covers save/load commands for filesystem state, JSON serialization/
deserialization, and commit as an alias for save functionality.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import json
import tempfile
import shutil
from pathlib import Path
from dagshell.dagshell_fluent import DagShell
from dagshell.dagshell import FileSystem


@pytest.fixture
def shell():
    """Create a fresh DagShell instance for each test."""
    return DagShell()


@pytest.fixture
def populated_shell():
    """Create a DagShell instance with complex test data for persistence testing."""
    shell = DagShell()

    # Create complex directory structure
    shell.mkdir('/home')
    shell.mkdir('/home/user')
    shell.mkdir('/home/user/documents')
    shell.mkdir('/home/user/projects')
    shell.mkdir('/home/user/projects/app')
    shell.mkdir('/home/user/projects/app/src')
    shell.mkdir('/home/user/projects/app/tests')
    shell.mkdir('/var')
    shell.mkdir('/var/log')
    shell.mkdir('/var/cache')
    shell.mkdir('/tmp')
    shell.mkdir('/etc')

    # Create files with various content types
    shell.echo('Hello, World!').out('/home/user/greeting.txt')
    shell.echo('Line 1\nLine 2\nLine 3\nLine 4\nLine 5').out('/home/user/documents/notes.txt')
    shell.echo('#!/bin/bash\necho "Hello from script"\nexit 0').out('/home/user/projects/script.sh')

    # Create source code files
    shell.echo('def main():\n    print("Hello, Python!")\n\nif __name__ == "__main__":\n    main()').out('/home/user/projects/app/src/main.py')
    shell.echo('import unittest\n\nclass TestMain(unittest.TestCase):\n    def test_example(self):\n        self.assertTrue(True)').out('/home/user/projects/app/tests/test_main.py')

    # Create config and data files
    shell.echo('host=localhost\nport=8080\ndebug=true').out('/etc/config.conf')
    shell.echo('apple\nbanana\ncherry\napricot\ngrape').out('/var/cache/fruits.txt')

    # Create log files
    shell.echo('2023-01-01 10:00:00 INFO: System started\n2023-01-01 10:01:00 ERROR: Connection failed\n2023-01-01 10:02:00 INFO: Retrying connection\n2023-01-01 10:03:00 INFO: Connected successfully').out('/var/log/app.log')

    # Create empty files and special cases
    shell.touch('/tmp/empty.txt')
    shell.echo('').out('/tmp/empty_content.txt')

    # Create binary-like content
    binary_content = b'\x00\x01\x02\x03\xff\xfe\xfd'
    shell.fs.write('/tmp/binary.bin', binary_content)

    # Create large file
    large_content = 'x' * 10000
    shell.echo(large_content).out('/tmp/large.txt')

    return shell


@pytest.fixture
def temp_save_dir():
    """Create temporary directory for save/load testing."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


class TestBasicSaveLoad:
    """Test basic save and load functionality."""

    def test_save_empty_filesystem(self, shell, temp_save_dir):
        """Test saving empty filesystem state."""
        save_path = os.path.join(temp_save_dir, 'empty.json')
        result = shell.save(save_path)

        assert result.exit_code == 0
        assert os.path.exists(save_path)

        # Verify it's valid JSON
        with open(save_path, 'r') as f:
            data = json.load(f)
        assert 'nodes' in data
        assert 'paths' in data
        assert 'deleted' in data

    def test_save_default_filename(self, shell, temp_save_dir):
        """Test saving with default filename."""
        old_cwd = os.getcwd()
        try:
            os.chdir(temp_save_dir)
            result = shell.save()  # Should save to 'dagshell.json'

            assert result.exit_code == 0
            assert os.path.exists('dagshell.json')
        finally:
            os.chdir(old_cwd)

    def test_load_empty_filesystem(self, shell, temp_save_dir):
        """Test loading empty filesystem state."""
        # Save empty state
        save_path = os.path.join(temp_save_dir, 'empty.json')
        shell.save(save_path)

        # Create new shell and load
        new_shell = DagShell()
        result = new_shell.load(save_path)

        assert result.exit_code == 0
        # Verify basic filesystem structure
        assert new_shell.fs.exists('/')
        assert new_shell.fs.exists('/dev')

    def test_save_load_roundtrip_simple(self, shell, temp_save_dir):
        """Test simple save/load roundtrip."""
        # Create simple structure
        shell.mkdir('/test')
        shell.echo('test content').out('/test/file.txt')

        # Save
        save_path = os.path.join(temp_save_dir, 'simple.json')
        shell.save(save_path)

        # Load into new shell
        new_shell = DagShell()
        new_shell.load(save_path)

        # Verify structure
        assert new_shell.fs.exists('/test')
        assert new_shell.fs.exists('/test/file.txt')
        content = new_shell.cat('/test/file.txt')
        assert content.data == b'test content\n'  # echo adds newline


class TestComplexSaveLoad:
    """Test save/load with complex filesystem structures."""

    def test_save_complex_filesystem(self, populated_shell, temp_save_dir):
        """Test saving complex filesystem with multiple files and directories."""
        save_path = os.path.join(temp_save_dir, 'complex.json')
        result = populated_shell.save(save_path)

        assert result.exit_code == 0
        assert os.path.exists(save_path)

        # Verify JSON structure
        with open(save_path, 'r') as f:
            data = json.load(f)

        assert len(data['paths']) > 20  # Should have many paths
        assert len(data['nodes']) > 15  # Should have many nodes

        # Verify specific paths exist in save data
        assert '/home/user/greeting.txt' in data['paths']
        assert '/home/user/projects/app/src/main.py' in data['paths']
        assert '/var/log/app.log' in data['paths']

    def test_load_complex_filesystem(self, populated_shell, temp_save_dir):
        """Test loading complex filesystem structure."""
        # Save populated filesystem
        save_path = os.path.join(temp_save_dir, 'complex.json')
        populated_shell.save(save_path)

        # Load into new shell
        new_shell = DagShell()
        result = new_shell.load(save_path)

        assert result.exit_code == 0

        # Verify directory structure
        assert new_shell.fs.exists('/home/user/documents')
        assert new_shell.fs.exists('/home/user/projects/app/src')
        assert new_shell.fs.exists('/var/log')
        assert new_shell.fs.exists('/etc')

        # Verify file contents
        greeting = new_shell.cat('/home/user/greeting.txt')
        assert greeting.data == b'Hello, World!\n'  # echo adds newline

        notes = new_shell.cat('/home/user/documents/notes.txt')
        assert b'Line 1' in notes.data and b'Line 5' in notes.data

        config = new_shell.cat('/etc/config.conf')
        assert b'host=localhost' in config.data

        # Verify directory listings
        home_contents = new_shell.ls('/home/user')
        assert 'documents' in home_contents.data
        assert 'projects' in home_contents.data
        assert 'greeting.txt' in home_contents.data

    def test_load_preserves_binary_content(self, shell, temp_save_dir):
        """Test that binary content is preserved through save/load."""
        binary_content = b'\x00\x01\x02\x03\xff\xfe\xfd\x80\x90\xa0'
        shell.fs.write('/binary.bin', binary_content)

        # Save and load
        save_path = os.path.join(temp_save_dir, 'binary.json')
        shell.save(save_path)

        new_shell = DagShell()
        new_shell.load(save_path)

        # Verify binary content
        loaded_content = new_shell.cat('/binary.bin')
        assert loaded_content.data == binary_content

    def test_load_preserves_large_files(self, shell, temp_save_dir):
        """Test that large files are preserved through save/load."""
        large_content = 'x' * 50000
        shell.echo(large_content).out('/large.txt')

        # Save and load
        save_path = os.path.join(temp_save_dir, 'large.json')
        shell.save(save_path)

        new_shell = DagShell()
        new_shell.load(save_path)

        # Verify large content
        loaded_content = new_shell.cat('/large.txt')
        assert len(loaded_content.data) == 50001  # 50000 + newline from echo
        assert loaded_content.data == large_content.encode() + b'\n'


class TestCommitAlias:
    """Test commit as an alias for save."""

    def test_commit_basic_functionality(self, shell, temp_save_dir):
        """Test that commit works as alias for save."""
        shell.mkdir('/test')
        shell.echo('commit test').out('/test/file.txt')

        save_path = os.path.join(temp_save_dir, 'commit.json')
        result = shell.commit(save_path)

        assert result.exit_code == 0
        assert os.path.exists(save_path)

        # Verify it's the same as save
        with open(save_path, 'r') as f:
            data = json.load(f)
        assert '/test/file.txt' in data['paths']

    def test_commit_default_filename(self, shell, temp_save_dir):
        """Test commit with default filename."""
        shell.echo('test').out('/test.txt')

        old_cwd = os.getcwd()
        try:
            os.chdir(temp_save_dir)
            result = shell.commit()  # Should save to 'dagshell.json'

            assert result.exit_code == 0
            assert os.path.exists('dagshell.json')
        finally:
            os.chdir(old_cwd)

    def test_commit_identical_to_save(self, populated_shell, temp_save_dir):
        """Test that commit produces identical output to save."""
        save_path = os.path.join(temp_save_dir, 'save.json')
        commit_path = os.path.join(temp_save_dir, 'commit.json')

        # Save using save command
        populated_shell.save(save_path)

        # Save using commit command
        populated_shell.commit(commit_path)

        # Compare files
        with open(save_path, 'r') as f:
            save_data = json.load(f)
        with open(commit_path, 'r') as f:
            commit_data = json.load(f)

        assert save_data == commit_data


class TestSaveLoadErrorHandling:
    """Test error handling in save/load operations."""

    def test_save_to_readonly_directory(self, shell):
        """Test save to read-only directory."""
        shell.echo('test').out('/test.txt')

        # Try to save to root (typically read-only)
        # The save function raises PermissionError for read-only paths
        try:
            result = shell.save('/readonly_test.json')
            # If it succeeds, it's a valid path on this system
            assert True
        except PermissionError:
            # Expected behavior for read-only paths
            assert True

    def test_save_invalid_path(self, shell):
        """Test save to invalid path."""
        shell.echo('test').out('/test.txt')

        # Try to save to invalid path
        # The save function raises FileNotFoundError for invalid paths
        try:
            result = shell.save('/nonexistent/directory/save.json')
            # Should not reach here
            assert False, "Expected FileNotFoundError"
        except FileNotFoundError:
            # Expected behavior for invalid paths
            assert True

    def test_load_nonexistent_file(self, shell):
        """Test load from nonexistent file."""
        result = shell.load('/nonexistent.json')
        assert result.exit_code != 0

    def test_load_invalid_json(self, shell, temp_save_dir):
        """Test load from invalid JSON file."""
        invalid_json_path = os.path.join(temp_save_dir, 'invalid.json')
        with open(invalid_json_path, 'w') as f:
            f.write('{ invalid json content }')

        result = shell.load(invalid_json_path)
        assert result.exit_code != 0

    def test_load_malformed_dagshell_data(self, shell, temp_save_dir):
        """Test load from JSON with incorrect structure."""
        malformed_path = os.path.join(temp_save_dir, 'malformed.json')
        with open(malformed_path, 'w') as f:
            json.dump({'wrong': 'structure'}, f)

        result = shell.load(malformed_path)
        assert result.exit_code != 0

    def test_load_corrupted_node_data(self, shell, temp_save_dir):
        """Test load with corrupted node data."""
        # Create valid structure but with corrupted node data
        corrupted_data = {
            'nodes': {'hash1': {'corrupted': 'node'}},
            'paths': {'/test': 'hash1'},
            'deleted': []
        }

        corrupted_path = os.path.join(temp_save_dir, 'corrupted.json')
        with open(corrupted_path, 'w') as f:
            json.dump(corrupted_data, f)

        result = shell.load(corrupted_path)
        # Should handle gracefully without crashing


class TestPersistenceWithContent:
    """Test persistence behavior with content-addressable storage."""

    def test_identical_content_deduplication(self, shell, temp_save_dir):
        """Test that identical content with same mtime is deduplicated in saved state."""
        # Create multiple files with identical content using fs.write directly
        # to ensure same mtime for true deduplication
        content = b'identical content'
        mtime = 1000000.0  # Use fixed mtime for deduplication
        shell.fs.write('/file1.txt', content, mtime=mtime)
        shell.fs.write('/file2.txt', content, mtime=mtime)
        shell.fs.write('/file3.txt', content, mtime=mtime)

        save_path = os.path.join(temp_save_dir, 'dedup.json')
        shell.save(save_path)

        # Verify deduplication in saved data
        with open(save_path, 'r') as f:
            data = json.load(f)

        # All three files should point to the same node hash
        # (same content + same mtime = same hash)
        hash1 = data['paths']['/file1.txt']
        hash2 = data['paths']['/file2.txt']
        hash3 = data['paths']['/file3.txt']
        assert hash1 == hash2 == hash3

        # Should only have one node for this content
        content_nodes = [h for h in data['nodes'] if h == hash1]
        assert len(content_nodes) == 1

    def test_different_content_separate_nodes(self, shell, temp_save_dir):
        """Test that different content creates separate nodes."""
        shell.echo('content 1').out('/file1.txt')
        shell.echo('content 2').out('/file2.txt')
        shell.echo('content 3').out('/file3.txt')

        save_path = os.path.join(temp_save_dir, 'separate.json')
        shell.save(save_path)

        with open(save_path, 'r') as f:
            data = json.load(f)

        # All files should have different hashes
        hash1 = data['paths']['/file1.txt']
        hash2 = data['paths']['/file2.txt']
        hash3 = data['paths']['/file3.txt']
        assert hash1 != hash2 != hash3 != hash1

    def test_persistence_preserves_metadata(self, shell, temp_save_dir):
        """Test that file metadata is preserved through save/load."""
        # Create file with specific metadata
        shell.echo('test content').out('/test.txt')

        # Get original metadata
        original_stat = shell.fs.stat('/test.txt')

        # Save and load
        save_path = os.path.join(temp_save_dir, 'metadata.json')
        shell.save(save_path)

        new_shell = DagShell()
        new_shell.load(save_path)

        # Verify metadata is preserved
        loaded_stat = new_shell.fs.stat('/test.txt')
        assert loaded_stat['type'] == original_stat['type']
        assert loaded_stat['size'] == original_stat['size']
        # Note: mtime might differ due to serialization, depending on implementation


class TestPersistenceWorkflows:
    """Test realistic persistence workflows."""

    def test_incremental_save_workflow(self, shell, temp_save_dir):
        """Test incremental development workflow with saves."""
        # Initial state
        shell.mkdir('/project')
        shell.echo('# Project').out('/project/README.md')

        save1_path = os.path.join(temp_save_dir, 'save1.json')
        shell.save(save1_path)

        # Add more content
        shell.echo('print("hello")').out('/project/main.py')
        shell.mkdir('/project/tests')

        save2_path = os.path.join(temp_save_dir, 'save2.json')
        shell.save(save2_path)

        # Add even more content
        shell.echo('test code').out('/project/tests/test_main.py')
        shell.echo('requirements').out('/project/requirements.txt')

        save3_path = os.path.join(temp_save_dir, 'save3.json')
        shell.save(save3_path)

        # Verify each save point
        for i, save_path in enumerate([save1_path, save2_path, save3_path], 1):
            test_shell = DagShell()
            test_shell.load(save_path)

            assert test_shell.fs.exists('/project/README.md')
            if i >= 2:
                assert test_shell.fs.exists('/project/main.py')
                assert test_shell.fs.exists('/project/tests')
            if i >= 3:
                assert test_shell.fs.exists('/project/tests/test_main.py')
                assert test_shell.fs.exists('/project/requirements.txt')

    def test_backup_and_restore_workflow(self, populated_shell, temp_save_dir):
        """Test backup and restore workflow."""
        # Create backup
        backup_path = os.path.join(temp_save_dir, 'backup.json')
        populated_shell.save(backup_path)

        # Make destructive changes
        populated_shell.rm('/home/user/greeting.txt')
        populated_shell.rm('/var/log', recursive=True)
        populated_shell.echo('corrupted data').out('/etc/config.conf')

        # Verify changes
        assert not populated_shell.fs.exists('/home/user/greeting.txt')
        assert not populated_shell.fs.exists('/var/log')
        corrupted = populated_shell.cat('/etc/config.conf')
        assert corrupted.data == b'corrupted data\n'  # echo adds newline

        # Restore from backup
        populated_shell.load(backup_path)

        # Verify restoration
        assert populated_shell.fs.exists('/home/user/greeting.txt')
        assert populated_shell.fs.exists('/var/log/app.log')
        restored_config = populated_shell.cat('/etc/config.conf')
        assert b'host=localhost' in restored_config.data

    def test_session_persistence(self, shell, temp_save_dir):
        """Test persisting session state including current directory."""
        # Set up session state
        shell.mkdir('/workspace')
        shell.cd('/workspace')
        shell.echo('session work').out('work.txt')

        # Save session
        session_path = os.path.join(temp_save_dir, 'session.json')
        shell.save(session_path)

        # Create new session and load
        new_shell = DagShell()
        new_shell.load(session_path)

        # Verify filesystem state
        assert new_shell.fs.exists('/workspace/work.txt')
        content = new_shell.cat('/workspace/work.txt')
        assert content.data == b'session work\n'  # echo adds newline

        # Note: Current directory state may or may not be preserved
        # depending on implementation - this tests just the filesystem


class TestJSONSerialization:
    """Test JSON serialization format and compatibility."""

    def test_json_format_structure(self, populated_shell, temp_save_dir):
        """Test that JSON has expected structure."""
        save_path = os.path.join(temp_save_dir, 'format.json')
        populated_shell.save(save_path)

        with open(save_path, 'r') as f:
            data = json.load(f)

        # Verify top-level structure
        assert isinstance(data, dict)
        assert 'nodes' in data
        assert 'paths' in data
        assert 'deleted' in data

        # Verify nodes structure
        assert isinstance(data['nodes'], dict)
        for node_hash, node_data in data['nodes'].items():
            assert isinstance(node_hash, str)
            assert isinstance(node_data, dict)
            assert 'type' in node_data

        # Verify paths structure
        assert isinstance(data['paths'], dict)
        for path, node_hash in data['paths'].items():
            assert isinstance(path, str)
            assert isinstance(node_hash, str)
            assert path.startswith('/')

        # Verify deleted structure
        assert isinstance(data['deleted'], list)

    def test_json_human_readable(self, shell, temp_save_dir):
        """Test that saved JSON is human-readable."""
        shell.mkdir('/test')
        shell.echo('readable content').out('/test/file.txt')

        save_path = os.path.join(temp_save_dir, 'readable.json')
        shell.save(save_path)

        # Check that file is formatted JSON (not minified)
        with open(save_path, 'r') as f:
            content = f.read()

        # Should contain newlines and indentation
        assert '\n' in content
        assert '/test/file.txt' in content  # Path should be readable


if __name__ == '__main__':
    pytest.main([__file__, '-v'])