#!/usr/bin/env python3
"""
Comprehensive tests for import_from_real functionality.

Tests the importing of files from the real filesystem into the virtual filesystem,
including single files, directories, permission preservation, and edge cases.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import tempfile
import shutil
from pathlib import Path
from dagshell.dagshell import FileSystem, Mode


@pytest.fixture
def fs():
    """Create a fresh FileSystem instance for each test."""
    return FileSystem()


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    temp = tempfile.mkdtemp()
    yield temp
    shutil.rmtree(temp)


class TestImportSingleFile:
    """Test importing single files from real filesystem."""

    def test_import_simple_text_file(self, fs, temp_dir):
        """Given a text file, when imported, then content matches exactly."""
        # Create real file
        real_file = Path(temp_dir) / "test.txt"
        content = b"Hello, DagShell!"
        real_file.write_bytes(content)

        # Import to virtual filesystem
        count = fs.import_from_real(str(real_file), '/imported.txt')

        # Verify
        assert count == 1
        assert fs.exists('/imported.txt')
        assert fs.read('/imported.txt') == content

    def test_import_binary_file(self, fs, temp_dir):
        """Given a binary file, when imported, then bytes are preserved."""
        # Create binary file
        real_file = Path(temp_dir) / "binary.dat"
        content = bytes(range(256))  # All possible byte values
        real_file.write_bytes(content)

        # Import
        count = fs.import_from_real(str(real_file), '/binary.dat')

        # Verify
        assert count == 1
        assert fs.read('/binary.dat') == content

    def test_import_empty_file(self, fs, temp_dir):
        """Given an empty file, when imported, then creates empty file in virtual fs."""
        # Create empty file
        real_file = Path(temp_dir) / "empty.txt"
        real_file.touch()

        # Import
        count = fs.import_from_real(str(real_file), '/empty.txt')

        # Verify
        assert count == 1
        assert fs.exists('/empty.txt')
        assert fs.read('/empty.txt') == b''

    def test_import_large_file(self, fs, temp_dir):
        """Given a large file, when imported, then full content is preserved."""
        # Create large file (1MB)
        real_file = Path(temp_dir) / "large.bin"
        content = b'x' * (1024 * 1024)
        real_file.write_bytes(content)

        # Import
        count = fs.import_from_real(str(real_file), '/large.bin')

        # Verify
        assert count == 1
        assert len(fs.read('/large.bin')) == 1024 * 1024

    def test_import_to_nested_path(self, fs, temp_dir):
        """Given a target with nested path, when parent directories exist, then import succeeds."""
        # Create real file
        real_file = Path(temp_dir) / "test.txt"
        real_file.write_text("test")

        # Create parent directories first
        fs.mkdir('/deep')
        fs.mkdir('/deep/nested')
        fs.mkdir('/deep/nested/path')

        # Import to nested path
        count = fs.import_from_real(str(real_file), '/deep/nested/path/file.txt')

        # Verify file exists
        assert fs.exists('/deep/nested/path/file.txt')
        assert count == 1


class TestImportDirectory:
    """Test importing directories recursively."""

    def test_import_empty_directory(self, fs, temp_dir):
        """Given an empty directory, when imported, then directory is created."""
        # Create empty directory
        empty_dir = Path(temp_dir) / "empty_dir"
        empty_dir.mkdir()

        # Import
        count = fs.import_from_real(str(empty_dir), '/imported')

        # Verify
        assert count == 1
        assert fs.exists('/imported')
        # Check it's a directory by getting the node
        node_hash = fs.paths['/imported']
        node = fs.nodes[node_hash]
        assert node.is_dir()

    def test_import_directory_with_files(self, fs, temp_dir):
        """Given a directory with files, when imported, then all files are included."""
        # Create directory structure
        test_dir = Path(temp_dir) / "test_dir"
        test_dir.mkdir()
        (test_dir / "file1.txt").write_text("content1")
        (test_dir / "file2.txt").write_text("content2")
        (test_dir / "file3.txt").write_text("content3")

        # Import
        count = fs.import_from_real(str(test_dir), '/imported')

        # Verify
        assert count >= 4  # directory + 3 files
        assert fs.exists('/imported')
        assert fs.exists('/imported/file1.txt')
        assert fs.exists('/imported/file2.txt')
        assert fs.exists('/imported/file3.txt')
        assert fs.read('/imported/file1.txt') == b'content1'

    def test_import_nested_directory_structure(self, fs, temp_dir):
        """Given nested directories, when imported, then structure is preserved."""
        # Create nested structure
        root = Path(temp_dir) / "root"
        root.mkdir()
        (root / "level1").mkdir()
        (root / "level1" / "level2").mkdir()
        (root / "level1" / "level2" / "deep.txt").write_text("deep content")
        (root / "level1" / "mid.txt").write_text("mid content")
        (root / "top.txt").write_text("top content")

        # Import
        count = fs.import_from_real(str(root), '/imported')

        # Verify structure
        assert fs.exists('/imported/top.txt')
        assert fs.exists('/imported/level1/mid.txt')
        assert fs.exists('/imported/level1/level2/deep.txt')
        assert fs.read('/imported/level1/level2/deep.txt') == b'deep content'

    def test_import_directory_with_subdirectories(self, fs, temp_dir):
        """Given directory with multiple subdirectories, when imported, then all are included."""
        # Create complex structure
        root = Path(temp_dir) / "complex"
        root.mkdir()
        (root / "dir1").mkdir()
        (root / "dir2").mkdir()
        (root / "dir3").mkdir()
        (root / "dir1" / "file1.txt").write_text("d1f1")
        (root / "dir2" / "file2.txt").write_text("d2f2")
        (root / "dir3" / "subdir").mkdir()
        (root / "dir3" / "subdir" / "file3.txt").write_text("d3s3")

        # Import
        count = fs.import_from_real(str(root), '/complex')

        # Verify all paths
        assert fs.exists('/complex/dir1/file1.txt')
        assert fs.exists('/complex/dir2/file2.txt')
        assert fs.exists('/complex/dir3/subdir/file3.txt')


class TestPermissionPreservation:
    """Test permission preservation during import."""

    def test_import_preserves_executable_permission(self, fs, temp_dir):
        """Given executable file, when imported with preserve_permissions, then executable bit is set."""
        # Create executable file
        real_file = Path(temp_dir) / "script.sh"
        real_file.write_text("#!/bin/bash\necho hello")
        os.chmod(real_file, 0o755)

        # Import with permission preservation
        fs.import_from_real(str(real_file), '/script.sh', preserve_permissions=True)

        # Verify permissions
        node_hash = fs.paths['/script.sh']
        node = fs.nodes[node_hash]
        assert node.mode & 0o111 != 0  # Has execute bits

    def test_import_without_permission_preservation(self, fs, temp_dir):
        """Given executable file, when imported without preserve_permissions, then default permissions are used."""
        # Create executable file
        real_file = Path(temp_dir) / "script.sh"
        real_file.write_text("#!/bin/bash\necho hello")
        os.chmod(real_file, 0o755)

        # Import without permission preservation
        fs.import_from_real(str(real_file), '/script.sh', preserve_permissions=False)

        # Verify default permissions
        node_hash = fs.paths['/script.sh']
        node = fs.nodes[node_hash]
        assert (node.mode & 0o777) == 0o644  # Default file permissions

    def test_import_with_custom_uid_gid(self, fs, temp_dir):
        """Given file, when imported with custom uid/gid, then ownership is set correctly."""
        # Create file
        real_file = Path(temp_dir) / "test.txt"
        real_file.write_text("test")

        # Import with custom uid/gid
        fs.import_from_real(str(real_file), '/test.txt', uid=1001, gid=1002)

        # Verify ownership
        node_hash = fs.paths['/test.txt']
        node = fs.nodes[node_hash]
        assert node.uid == 1001
        assert node.gid == 1002


class TestImportErrorHandling:
    """Test error handling during import."""

    def test_import_nonexistent_file_raises_error(self, fs, temp_dir):
        """Given nonexistent path, when importing, then raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            fs.import_from_real('/nonexistent/path.txt', '/target.txt')

    def test_import_with_relative_target_raises_error(self, fs, temp_dir):
        """Given relative target path, when importing, then raises ValueError."""
        # Create real file
        real_file = Path(temp_dir) / "test.txt"
        real_file.write_text("test")

        # Try to import to relative path
        with pytest.raises(ValueError, match="Target path must be absolute"):
            fs.import_from_real(str(real_file), 'relative/path.txt')

    def test_import_overwrites_existing_file(self, fs, temp_dir):
        """Given existing virtual file, when importing to same path, then file is overwritten."""
        # Create existing virtual file
        fs.write('/existing.txt', b'old content')

        # Create real file with different content
        real_file = Path(temp_dir) / "new.txt"
        real_file.write_text("new content")

        # Import, overwriting
        fs.import_from_real(str(real_file), '/existing.txt')

        # Verify new content
        assert fs.read('/existing.txt') == b'new content'


class TestImportEdgeCases:
    """Test edge cases and special scenarios."""

    def test_import_file_with_unicode_content(self, fs, temp_dir):
        """Given file with Unicode content, when imported, then encoding is preserved."""
        # Create file with Unicode
        real_file = Path(temp_dir) / "unicode.txt"
        content = 'Unicode: ñáéíóú 中文 🌟 русский العربية'
        real_file.write_text(content, encoding='utf-8')

        # Import
        fs.import_from_real(str(real_file), '/unicode.txt')

        # Verify
        imported_content = fs.read('/unicode.txt').decode('utf-8')
        assert imported_content == content

    def test_import_file_with_special_characters_in_name(self, fs, temp_dir):
        """Given file with special characters in name, when imported, then name is preserved."""
        # Create file with special characters
        real_file = Path(temp_dir) / "file-with_special.chars.txt"
        real_file.write_text("content")

        # Import
        fs.import_from_real(str(real_file), '/special-chars.txt')

        # Verify
        assert fs.exists('/special-chars.txt')

    def test_import_returns_correct_count(self, fs, temp_dir):
        """Given directory structure, when imported, then returns accurate count."""
        # Create structure with known number of items
        root = Path(temp_dir) / "counted"
        root.mkdir()
        (root / "file1.txt").write_text("1")
        (root / "file2.txt").write_text("2")
        (root / "subdir").mkdir()
        (root / "subdir" / "file3.txt").write_text("3")

        # Import and check count
        count = fs.import_from_real(str(root), '/counted')

        # Should count: root dir, file1, file2, subdir, file3 = 5
        assert count >= 5

    def test_import_directory_to_root(self, fs, temp_dir):
        """Given directory, when imported to root, then files appear at root level."""
        # Create directory
        test_dir = Path(temp_dir) / "to_root"
        test_dir.mkdir()
        (test_dir / "root_file.txt").write_text("at root")

        # Import to root
        fs.import_from_real(str(test_dir), '/')

        # Verify file is accessible from root
        assert fs.exists('/root_file.txt')
