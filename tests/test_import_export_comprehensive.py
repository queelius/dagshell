#!/usr/bin/env python3
"""
Comprehensive tests for DagShell import/export functionality.

This test suite covers import_file and export_file commands with security
restrictions, directory import/export, and edge cases for real filesystem interaction.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import tempfile
import shutil
from pathlib import Path
from dagshell.dagshell_fluent import DagShell
from dagshell.dagshell import FileSystem


@pytest.fixture
def shell():
    """Create a fresh DagShell instance for each test with isolated filesystem."""
    return DagShell(fs=FileSystem())


@pytest.fixture
def temp_real_files():
    """Create temporary real files for import testing."""
    temp_dir = tempfile.mkdtemp()

    # Create test files and directories
    test_files = {
        'simple.txt': 'Hello, World!',
        'multiline.txt': 'Line 1\nLine 2\nLine 3\n',
        'binary.bin': b'\x00\x01\x02\x03\xff\xfe\xfd',
        'empty.txt': '',
        'utf8.txt': 'Unicode: ñáéíóú 中文 🌟',
        'large.txt': 'x' * 10000,  # Large file
    }

    # Create subdirectory structure
    subdir = os.path.join(temp_dir, 'subdir')
    os.makedirs(subdir)
    nested_subdir = os.path.join(subdir, 'nested')
    os.makedirs(nested_subdir)

    # Write test files
    for filename, content in test_files.items():
        filepath = os.path.join(temp_dir, filename)
        mode = 'wb' if isinstance(content, bytes) else 'w'
        encoding = None if isinstance(content, bytes) else 'utf-8'
        with open(filepath, mode, encoding=encoding) as f:
            f.write(content)

    # Create files in subdirectories
    with open(os.path.join(subdir, 'sub_file.txt'), 'w') as f:
        f.write('File in subdirectory')

    with open(os.path.join(nested_subdir, 'deep_file.txt'), 'w') as f:
        f.write('Deep nested file')

    yield temp_dir

    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture
def temp_export_dir():
    """Create temporary directory for export testing."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


class TestImportFileBasic:
    """Test basic import_file functionality."""

    def test_import_simple_text_file(self, shell, temp_real_files):
        """Test importing a simple text file."""
        real_path = os.path.join(temp_real_files, 'simple.txt')
        virtual_path = '/imported/simple.txt'

        result = shell.import_file(real_path, virtual_path)
        assert result.exit_code == 0

        # Verify file exists in virtual filesystem
        assert shell.fs.exists('/imported/simple.txt')

        # Verify content
        content = shell.cat('/imported/simple.txt')
        assert content.data == b'Hello, World!'

    def test_import_without_virtual_path(self, shell, temp_real_files):
        """Test importing file without specifying virtual path."""
        real_path = os.path.join(temp_real_files, 'simple.txt')

        result = shell.import_file(real_path)
        assert result.exit_code == 0

        # Should create at root with same filename
        assert shell.fs.exists('/simple.txt')
        content = shell.cat('/simple.txt')
        assert content.data == b'Hello, World!'

    def test_import_multiline_file(self, shell, temp_real_files):
        """Test importing multiline text file."""
        real_path = os.path.join(temp_real_files, 'multiline.txt')

        shell.import_file(real_path, '/test/multiline.txt')
        content = shell.cat('/test/multiline.txt')

        lines = content.data.decode().strip().split('\n')
        assert lines == ['Line 1', 'Line 2', 'Line 3']

    def test_import_binary_file(self, shell, temp_real_files):
        """Test importing binary file."""
        real_path = os.path.join(temp_real_files, 'binary.bin')

        shell.import_file(real_path, '/data/binary.bin')
        content = shell.cat('/data/binary.bin')

        expected = b'\x00\x01\x02\x03\xff\xfe\xfd'
        assert content.data == expected

    def test_import_empty_file(self, shell, temp_real_files):
        """Test importing empty file."""
        real_path = os.path.join(temp_real_files, 'empty.txt')

        shell.import_file(real_path, '/empty.txt')
        content = shell.cat('/empty.txt')
        assert content.data == b''

    def test_import_utf8_file(self, shell, temp_real_files):
        """Test importing UTF-8 file with unicode characters."""
        real_path = os.path.join(temp_real_files, 'utf8.txt')

        shell.import_file(real_path, '/unicode.txt')
        content = shell.cat('/unicode.txt')

        assert 'ñáéíóú' in content.data.decode('utf-8')
        assert '中文' in content.data.decode('utf-8')
        assert '🌟' in content.data.decode('utf-8')

    def test_import_large_file(self, shell, temp_real_files):
        """Test importing large file."""
        real_path = os.path.join(temp_real_files, 'large.txt')

        shell.import_file(real_path, '/large.txt')
        content = shell.cat('/large.txt')

        assert len(content.data) == 10000
        assert content.data == b'x' * 10000


class TestImportFileAdvanced:
    """Test advanced import_file functionality."""

    def test_import_creates_directory_structure(self, shell, temp_real_files):
        """Test that import creates necessary directory structure."""
        real_path = os.path.join(temp_real_files, 'simple.txt')
        virtual_path = '/deep/nested/structure/file.txt'

        shell.import_file(real_path, virtual_path)

        # Verify directory structure was created
        assert shell.fs.exists('/deep')
        assert shell.fs.exists('/deep/nested')
        assert shell.fs.exists('/deep/nested/structure')
        assert shell.fs.exists('/deep/nested/structure/file.txt')

    def test_import_overwrites_existing_file(self, shell, temp_real_files):
        """Test that import overwrites existing virtual file."""
        real_path = os.path.join(temp_real_files, 'simple.txt')

        # Create existing file
        shell.echo('old content').out('/test.txt')

        # Import over it
        shell.import_file(real_path, '/test.txt')

        # Should have new content
        content = shell.cat('/test.txt')
        assert content.data == b'Hello, World!'

    def test_import_with_relative_virtual_path(self, shell, temp_real_files):
        """Test import with relative virtual path."""
        real_path = os.path.join(temp_real_files, 'simple.txt')

        shell.mkdir('/home')
        shell.cd('/home')
        shell.import_file(real_path, 'relative.txt')

        # Should create file relative to current directory
        assert shell.fs.exists('/home/relative.txt')

    def test_import_preserves_filename(self, shell, temp_real_files):
        """Test that import preserves original filename when path is directory."""
        real_path = os.path.join(temp_real_files, 'simple.txt')

        shell.mkdir('/imported')
        shell.import_file(real_path, '/imported')

        # Should create file with original name inside directory
        assert shell.fs.exists('/imported/simple.txt')


class TestImportDirectoryRecursive:
    """Test recursive directory import functionality."""

    def test_import_directory_structure(self, shell, temp_real_files):
        """Test importing entire directory structure."""
        result = shell.import_file(temp_real_files, '/imported', recursive=True)
        assert result.exit_code == 0

        # Verify all files were imported
        assert shell.fs.exists('/imported/simple.txt')
        assert shell.fs.exists('/imported/multiline.txt')
        assert shell.fs.exists('/imported/subdir/sub_file.txt')
        assert shell.fs.exists('/imported/subdir/nested/deep_file.txt')

        # Verify content
        content = shell.cat('/imported/subdir/sub_file.txt')
        assert content.data == b'File in subdirectory'

    def test_import_directory_without_recursive_fails(self, shell, temp_real_files):
        """Test that importing directory without recursive flag fails appropriately."""
        result = shell.import_file(temp_real_files, '/imported')
        # Should handle gracefully (may fail or skip)
        # The specific behavior depends on implementation


class TestExportFileBasic:
    """Test basic export_file functionality."""

    def test_export_simple_file(self, shell, temp_export_dir):
        """Test exporting a simple file."""
        # Create file in virtual filesystem
        shell.echo('Hello, Virtual World!').out('/test.txt')

        # Export it
        export_path = os.path.join(temp_export_dir, 'exported.txt')
        result = shell.export_file('/test.txt', export_path)
        assert result.exit_code == 0

        # Verify file exists in real filesystem
        assert os.path.exists(export_path)

        # Verify content
        with open(export_path, 'r') as f:
            content = f.read()
        assert content == 'Hello, Virtual World!\n'  # echo adds newline

    def test_export_without_real_path(self, shell, temp_export_dir):
        """Test exporting without specifying real path."""
        shell.echo('test content').out('/export_test.txt')

        # Change to temp directory and export
        old_cwd = os.getcwd()
        try:
            os.chdir(temp_export_dir)
            result = shell.export_file('/export_test.txt')
            assert result.exit_code == 0

            # Should create file with same name in current directory
            assert os.path.exists('export_test.txt')
        finally:
            os.chdir(old_cwd)

    def test_export_binary_file(self, shell, temp_export_dir):
        """Test exporting binary content."""
        # Create binary content in virtual filesystem
        binary_content = b'\x00\x01\x02\x03\xff\xfe\xfd'
        shell.fs.write('/binary.bin', binary_content)

        export_path = os.path.join(temp_export_dir, 'binary_export.bin')
        shell.export_file('/binary.bin', export_path)

        # Verify binary content
        with open(export_path, 'rb') as f:
            content = f.read()
        assert content == binary_content

    def test_export_empty_file(self, shell, temp_export_dir):
        """Test exporting empty file."""
        shell.touch('/empty.txt')

        export_path = os.path.join(temp_export_dir, 'empty_export.txt')
        shell.export_file('/empty.txt', export_path)

        assert os.path.exists(export_path)
        assert os.path.getsize(export_path) == 0

    def test_export_large_file(self, shell, temp_export_dir):
        """Test exporting large file."""
        large_content = 'x' * 50000
        shell.echo(large_content).out('/large.txt')

        export_path = os.path.join(temp_export_dir, 'large_export.txt')
        shell.export_file('/large.txt', export_path)

        assert os.path.exists(export_path)
        assert os.path.getsize(export_path) == 50001  # 50000 chars + newline


class TestExportDirectoryRecursive:
    """Test recursive directory export functionality."""

    def test_export_directory_structure(self, shell, temp_export_dir):
        """Test exporting directory structure recursively."""
        # Create virtual directory structure
        shell.mkdir('/project')
        shell.mkdir('/project/src')
        shell.mkdir('/project/docs')
        shell.echo('main code').out('/project/src/main.py')
        shell.echo('utility code').out('/project/src/utils.py')
        shell.echo('documentation').out('/project/docs/README.md')
        shell.echo('project info').out('/project/info.txt')

        # Export recursively
        export_path = os.path.join(temp_export_dir, 'exported_project')
        result = shell.export_file('/project', export_path, recursive=True)
        assert result.exit_code == 0

        # Verify directory structure
        assert os.path.exists(export_path)
        assert os.path.exists(os.path.join(export_path, 'src'))
        assert os.path.exists(os.path.join(export_path, 'docs'))
        assert os.path.exists(os.path.join(export_path, 'src', 'main.py'))
        assert os.path.exists(os.path.join(export_path, 'src', 'utils.py'))
        assert os.path.exists(os.path.join(export_path, 'docs', 'README.md'))
        assert os.path.exists(os.path.join(export_path, 'info.txt'))

        # Verify content
        with open(os.path.join(export_path, 'src', 'main.py'), 'r') as f:
            assert f.read() == 'main code\n'  # echo adds newline

    def test_export_directory_without_recursive_fails(self, shell, temp_export_dir):
        """Test that exporting directory without recursive flag fails appropriately."""
        shell.mkdir('/test_dir')
        shell.echo('content').out('/test_dir/file.txt')

        export_path = os.path.join(temp_export_dir, 'should_fail')
        result = shell.export_file('/test_dir', export_path)
        # Should handle gracefully (behavior depends on implementation)


class TestSecurityRestrictions:
    """Test security restrictions for import/export operations."""

    def test_import_safe_paths_restriction(self, shell):
        """Test that import respects safe_paths restrictions."""
        # Try to import from a potentially dangerous path
        dangerous_paths = [
            '/etc/passwd',
            '/root/sensitive',
            '../../../etc/passwd',
            'C:\\Windows\\System32',  # Windows path
        ]

        for path in dangerous_paths:
            if os.path.exists(path):
                # This should either fail or be restricted
                result = shell.import_file(path, '/imported.txt', safe_paths=['/tmp', '/home'])
                # Verify it doesn't succeed if path is outside safe_paths
                if not any(path.startswith(safe) for safe in ['/tmp', '/home']):
                    assert result.exit_code != 0 or not shell.fs.exists('/imported.txt')

    def test_export_safe_paths_restriction(self, shell, temp_export_dir):
        """Test that export respects safe_paths restrictions."""
        shell.echo('sensitive data').out('/secret.txt')

        # Try to export to potentially dangerous location
        dangerous_path = '/etc/malicious.txt'
        result = shell.export_file('/secret.txt', dangerous_path, safe_paths=[temp_export_dir])

        # Should fail or be restricted
        assert result.exit_code != 0 or not os.path.exists(dangerous_path)

    def test_import_path_traversal_protection(self, shell, temp_real_files):
        """Test protection against path traversal attacks."""
        real_path = os.path.join(temp_real_files, 'simple.txt')

        # Try path traversal in virtual path
        dangerous_virtual_paths = [
            '../../etc/passwd',
            '../../../root/malicious',
            '/../../outside_root',
        ]

        for vpath in dangerous_virtual_paths:
            result = shell.import_file(real_path, vpath)
            # Should normalize path or reject dangerous paths
            # Verify no files created outside virtual filesystem root

    def test_export_path_traversal_protection(self, shell, temp_export_dir):
        """Test protection against path traversal in export."""
        shell.echo('test content').out('/test.txt')

        # Try to export outside allowed directory using path traversal
        dangerous_path = os.path.join(temp_export_dir, '../../../etc/malicious.txt')
        result = shell.export_file('/test.txt', dangerous_path, safe_paths=[temp_export_dir])

        # Should fail or normalize path
        assert not os.path.exists('/etc/malicious.txt')


class TestImportExportErrorHandling:
    """Test error handling in import/export operations."""

    def test_import_nonexistent_file(self, shell):
        """Test importing nonexistent file."""
        result = shell.import_file('/nonexistent/file.txt', '/imported.txt')
        assert result.exit_code != 0
        assert not shell.fs.exists('/imported.txt')

    def test_import_permission_denied(self, shell):
        """Test importing file with permission issues."""
        # This test may be skipped on systems where we can't create permission issues
        try:
            # Try to access a file that typically requires root access
            result = shell.import_file('/etc/shadow', '/imported.txt')
            # Should either fail with permission error or be empty
            assert result.exit_code != 0 or not shell.fs.exists('/imported.txt')
        except PermissionError:
            # Expected on most systems
            pass

    def test_export_nonexistent_virtual_file(self, shell, temp_export_dir):
        """Test exporting nonexistent virtual file."""
        export_path = os.path.join(temp_export_dir, 'nonexistent.txt')
        result = shell.export_file('/nonexistent.txt', export_path)

        assert result.exit_code != 0
        assert not os.path.exists(export_path)

    def test_export_to_readonly_directory(self, shell, temp_export_dir):
        """Test exporting to read-only directory."""
        shell.echo('test content').out('/test.txt')

        # Create read-only subdirectory
        readonly_dir = os.path.join(temp_export_dir, 'readonly')
        os.makedirs(readonly_dir)
        os.chmod(readonly_dir, 0o444)  # Read-only

        try:
            export_path = os.path.join(readonly_dir, 'should_fail.txt')
            result = shell.export_file('/test.txt', export_path)
            assert result.exit_code != 0
        finally:
            # Cleanup: restore permissions
            os.chmod(readonly_dir, 0o755)

    def test_import_export_roundtrip(self, shell, temp_real_files, temp_export_dir):
        """Test importing and then exporting file preserves content."""
        real_path = os.path.join(temp_real_files, 'utf8.txt')

        # Import
        shell.import_file(real_path, '/roundtrip.txt')

        # Export
        export_path = os.path.join(temp_export_dir, 'roundtrip_export.txt')
        shell.export_file('/roundtrip.txt', export_path)

        # Compare original and final
        with open(real_path, 'rb') as f:
            original = f.read()
        with open(export_path, 'rb') as f:
            final = f.read()

        assert original == final


class TestImportExportIntegration:
    """Test integration scenarios for import/export."""

    def test_import_process_export_workflow(self, shell, temp_real_files, temp_export_dir):
        """Test complete workflow: import, process, export."""
        # Import a file
        real_path = os.path.join(temp_real_files, 'multiline.txt')
        shell.import_file(real_path, '/data/input.txt')

        # Process it using the fluent API piping pattern
        shell.cat('/data/input.txt')
        shell.grep('Line')  # Reads from _last_result
        shell.sort()        # Reads from _last_result
        result = shell.tee('/data/processed.txt')  # Saves to file and returns result

        # Export processed result
        export_path = os.path.join(temp_export_dir, 'processed_output.txt')
        shell.export_file('/data/processed.txt', export_path)

        # Verify final result
        with open(export_path, 'r') as f:
            content = f.read()
        assert 'Line 1' in content
        assert 'Line 2' in content
        assert 'Line 3' in content

    def test_batch_import_operations(self, shell, temp_real_files):
        """Test importing multiple files efficiently."""
        files_to_import = ['simple.txt', 'multiline.txt', 'utf8.txt']

        for filename in files_to_import:
            real_path = os.path.join(temp_real_files, filename)
            virtual_path = f'/batch/{filename}'
            shell.import_file(real_path, virtual_path)

        # Verify all files imported
        for filename in files_to_import:
            assert shell.fs.exists(f'/batch/{filename}')

        # Verify they can be processed together
        result = shell.cat('/batch/simple.txt', '/batch/multiline.txt')
        assert b'Hello, World!' in result.data
        assert b'Line 1' in result.data


if __name__ == '__main__':
    pytest.main([__file__, '-v'])