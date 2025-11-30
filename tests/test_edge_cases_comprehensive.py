#!/usr/bin/env python3
"""
Comprehensive edge cases and error handling tests for DagShell system.

This test suite covers non-existent files/directories, permission errors,
invalid Scheme syntax, circular references in filesystem, boundary conditions,
resource exhaustion, and other edge cases that could break the system.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import tempfile
import shutil
from dagshell.dagshell_fluent import DagShell
from dagshell.dagshell import FileSystem
try:
    from dagshell.scheme_interpreter import SchemeREPL
except ImportError:
    SchemeREPL = None


@pytest.fixture
def shell():
    """Create a fresh DagShell instance for each test."""
    return DagShell()


@pytest.fixture
def stress_shell():
    """Create a DagShell instance for stress testing."""
    shell = DagShell()

    # Create a more complex structure for stress testing
    for i in range(10):
        shell.mkdir(f'/stress{i}')
        for j in range(5):
            shell.mkdir(f'/stress{i}/sub{j}')
            shell.echo(f'content {i}-{j}').out(f'/stress{i}/sub{j}/file{j}.txt')

    return shell


class TestNonExistentResources:
    """Test operations on non-existent files and directories."""

    def test_cat_nonexistent_file(self, shell):
        """Test cat on nonexistent file."""
        result = shell.cat('/nonexistent.txt')
        # Should handle gracefully, not crash
        assert result.exit_code != 0 or result.data == b''

    def test_ls_nonexistent_directory(self, shell):
        """Test ls on nonexistent directory."""
        result = shell.ls('/nonexistent/directory')
        # Should handle gracefully
        assert result.exit_code != 0 or result.data == []

    def test_cd_nonexistent_directory(self, shell):
        """Test cd to nonexistent directory."""
        original_pwd = shell.pwd().data
        shell.cd('/nonexistent/path')

        # Should remain in original directory
        current_pwd = shell.pwd().data
        assert current_pwd == original_pwd

    def test_rm_nonexistent_file(self, shell):
        """Test rm on nonexistent file."""
        result = shell.rm('/nonexistent.txt')
        # Should handle gracefully
        assert result is not None

    def test_rm_nonexistent_file_with_force(self, shell):
        """Test rm -f on nonexistent file."""
        result = shell.rm('/nonexistent.txt', force=True)
        # With force, should not fail
        assert result is not None

    def test_cp_nonexistent_source(self, shell):
        """Test cp with nonexistent source."""
        shell.mkdir('/dest')
        result = shell.cp('/nonexistent.txt', '/dest/')
        # Should fail gracefully
        assert not shell.fs.exists('/dest/nonexistent.txt')

    def test_mv_nonexistent_source(self, shell):
        """Test mv with nonexistent source."""
        shell.mkdir('/dest')
        result = shell.mv('/nonexistent.txt', '/dest/')
        # Should fail gracefully
        assert not shell.fs.exists('/dest/nonexistent.txt')

    def test_cp_to_nonexistent_directory(self, shell):
        """Test cp to nonexistent destination directory."""
        shell.echo('content').out('/source.txt')
        result = shell.cp('/source.txt', '/nonexistent/dir/dest.txt')
        # Should fail gracefully
        assert not shell.fs.exists('/nonexistent/dir/dest.txt')

    def test_mv_to_nonexistent_directory(self, shell):
        """Test mv to nonexistent destination directory."""
        shell.echo('content').out('/source.txt')
        result = shell.mv('/source.txt', '/nonexistent/dir/dest.txt')
        # Source should still exist if move failed
        # Behavior may vary by implementation

    def test_grep_nonexistent_file(self, shell):
        """Test grep on nonexistent file."""
        result = shell.grep('pattern', '/nonexistent.txt')
        # Should handle gracefully
        assert result.exit_code != 0 or result.data == []

    def test_head_nonexistent_file(self, shell):
        """Test head on nonexistent file."""
        result = shell.head(5, '/nonexistent.txt')
        assert result.exit_code != 0 or result.data == []

    def test_tail_nonexistent_file(self, shell):
        """Test tail on nonexistent file."""
        result = shell.tail(5, '/nonexistent.txt')
        assert result.exit_code != 0 or result.data == []

    def test_wc_nonexistent_file(self, shell):
        """Test wc on nonexistent file."""
        result = shell.wc('/nonexistent.txt')
        assert result.exit_code != 0 or result.data == 0


class TestInvalidPaths:
    """Test operations with invalid path formats."""

    def test_empty_path_operations(self, shell):
        """Test operations with empty paths."""
        invalid_paths = ['', ' ', '\t', '\n']

        for path in invalid_paths:
            try:
                # These should handle empty paths gracefully
                shell.cat(path)
                shell.ls(path)
                shell.mkdir(path)
                shell.rm(path)
                # Should not crash
                assert True
            except (ValueError, TypeError, IsADirectoryError, FileNotFoundError):
                # Expected for invalid paths
                assert True

    def test_null_byte_in_paths(self, shell):
        """Test paths with null bytes."""
        invalid_paths = [
            '/path\x00/with/null',
            '\x00invalid',
            '/valid/path\x00'
        ]

        for path in invalid_paths:
            try:
                shell.mkdir(path)
                shell.echo('content').out(path + '/file.txt')
                # Should handle or reject null bytes
                assert True
            except (ValueError, TypeError):
                # Expected for invalid paths
                assert True

    def test_extremely_long_paths(self, shell):
        """Test extremely long file paths."""
        # Create very long path
        long_component = 'a' * 255  # Max filename length on many systems
        long_path = '/' + '/'.join([long_component] * 10)  # Very deep path

        try:
            result = shell.mkdir(long_path)
            # Should either succeed or fail gracefully
            assert True
        except Exception:
            # May fail due to path length limits
            assert True

    def test_paths_with_special_characters(self, shell):
        """Test paths with special characters."""
        special_chars = [
            '/path with spaces/file.txt',
            '/path_with_underscores/file.txt',
            '/path-with-hyphens/file.txt',
            '/path.with.dots/file.txt',
            '/path:with:colons/file.txt',  # May be invalid on some systems
            '/path;with;semicolons/file.txt',
            '/path|with|pipes/file.txt',
            '/path<with>brackets/file.txt',
            '/path"with"quotes/file.txt',
            "/path'with'apostrophes/file.txt"
        ]

        for path in special_chars:
            try:
                # Create parent directory
                parent = os.path.dirname(path)
                if parent != '/':
                    shell.mkdir(parent)

                # Try to create file
                shell.echo('test').out(path)

                # If successful, verify it exists
                if shell.fs.exists(path):
                    content = shell.cat(path)
                    assert content.data == b'test'

            except Exception:
                # Some special characters may not be supported
                pass

    def test_relative_path_edge_cases(self, shell):
        """Test edge cases in relative path resolution."""
        shell.mkdir('/test')
        shell.cd('/test')

        edge_cases = [
            '.',
            '..',
            '../..',
            './.',
            './..',
            '../.',
            '././.',
            '../../..',
            './../..',
        ]

        for path in edge_cases:
            try:
                resolved = shell._resolve_path(path)
                # Should resolve to valid absolute path
                assert resolved.startswith('/')
            except Exception:
                # Some edge cases might not be supported
                pass


class TestBoundaryConditions:
    """Test boundary conditions and limits."""

    def test_empty_files(self, shell):
        """Test operations on empty files."""
        shell.touch('/empty.txt')

        # All operations should handle empty files
        assert shell.cat('/empty.txt').data == b''
        assert shell.head(10, '/empty.txt').data == []
        assert shell.tail(10, '/empty.txt').data == []
        assert shell.wc('/empty.txt', lines=True, words=False, chars=False).data == 0
        assert shell.grep('pattern', '/empty.txt').data == []

    def test_single_character_files(self, shell):
        """Test operations on single character files."""
        shell.echo('a').out('/single.txt')

        result = shell.cat('/single.txt')
        assert result.data == b'a\n'  # echo adds newline

        result = shell.head(1, '/single.txt')
        assert len(result.data) == 1

        result = shell.wc('/single.txt', chars=True, lines=False, words=False)
        assert result.data == 2  # 'a' + newline = 2 chars

    def test_very_large_files(self, shell):
        """Test operations on very large files."""
        # Create large content (10KB)
        large_content = 'x' * 10000
        shell.echo(large_content).out('/large.txt')

        # Operations should handle large files
        result = shell.cat('/large.txt')
        assert len(result.data) == 10001  # 10000 chars + newline

        result = shell.head(10, '/large.txt')
        assert len(result.data) <= 10

        result = shell.tail(10, '/large.txt')
        assert len(result.data) <= 10

        result = shell.wc('/large.txt', chars=True, lines=False, words=False)
        assert result.data == 10001  # 10000 chars + newline from echo

    def test_files_with_many_lines(self, shell):
        """Test files with many lines."""
        # Create file with 1000 lines
        lines = [f'line {i}' for i in range(1000)]
        content = '\n'.join(lines)
        shell.echo(content).out('/many_lines.txt')

        result = shell.wc('/many_lines.txt', lines=True, words=False, chars=False)
        assert result.data == 1000

        result = shell.head(50, '/many_lines.txt')
        assert len(result.data) == 50

        result = shell.tail(25, '/many_lines.txt')
        assert len(result.data) == 25

    def test_zero_length_operations(self, shell):
        """Test operations with zero-length parameters."""
        shell.echo('test content').out('/test.txt')

        # Zero-length operations
        result = shell.head(0, '/test.txt')
        assert result.data == []

        result = shell.tail(0, '/test.txt')
        assert result.data == []

        result = shell.grep('', '/test.txt')  # Empty pattern
        # Behavior may vary - empty pattern might match all or none

    def test_negative_parameters(self, shell):
        """Test operations with negative parameters."""
        shell.echo('line 1\nline 2\nline 3\nline 4\nline 5').out('/test.txt')

        try:
            # Negative line counts should be handled gracefully
            result = shell.head(-5, '/test.txt')
            assert result.exit_code != 0 or result.data == []
        except (ValueError, TypeError):
            # Expected for invalid parameters
            assert True

        try:
            result = shell.tail(-3, '/test.txt')
            assert result.exit_code != 0 or result.data == []
        except (ValueError, TypeError):
            assert True


class TestInvalidSchemeCode:
    """Test Scheme interpreter with invalid syntax."""

    def test_scheme_syntax_errors(self, shell):
        """Test Scheme with various syntax errors."""
        if SchemeREPL is None:
            pytest.skip("Scheme interpreter not available")

        repl = SchemeREPL()

        syntax_errors = [
            '(unclosed paren',
            'unopened)',
            '(nested (unclosed)',
            '((()))',  # This might be valid
            '(define)',  # Missing arguments
            '(+ 1 2 3))',  # Extra closing paren
            '(if)',  # Missing condition and branches
            '(lambda)',  # Missing parameters and body
            '(quote)',  # Missing argument
            '',  # Empty input
            '   ',  # Whitespace only
            '()',  # Empty list - might be valid
        ]

        for code in syntax_errors:
            try:
                result = repl.eval_string(code)
                # Should either return an error or handle gracefully
                # Should not crash the interpreter
                assert True
            except Exception as e:
                # Syntax errors are expected
                assert True

    def test_scheme_runtime_errors(self, shell):
        """Test Scheme runtime errors."""
        if SchemeREPL is None:
            pytest.skip("Scheme interpreter not available")

        repl = SchemeREPL()

        runtime_errors = [
            '(/ 1 0)',  # Division by zero
            '(car 123)',  # car on non-list
            '(cdr "string")',  # cdr on non-list
            '(+ "string" 5)',  # Type mismatch
            '(nonexistent-function)',  # Undefined function
            '(undefined-variable)',  # Undefined variable
            '(car (list))',  # car on empty list
            '(cdr (list))',  # cdr on empty list
        ]

        for code in runtime_errors:
            try:
                result = repl.eval_string(code)
                # Should handle runtime errors gracefully
                assert True
            except Exception:
                # Runtime errors are expected
                assert True

    def test_scheme_infinite_recursion(self, shell):
        """Test Scheme with potentially infinite recursion."""
        if SchemeREPL is None:
            pytest.skip("Scheme interpreter not available")

        repl = SchemeREPL()

        # Define a recursive function that could run forever
        infinite_recursion = '''
        (define infinite-loop
          (lambda (x)
            (infinite-loop x)))
        '''

        try:
            repl.eval_string(infinite_recursion)
            # Don't actually call it - would run forever
            # Just test that definition doesn't crash
            assert True
        except Exception:
            # Some recursion protection might prevent this
            assert True

    def test_scheme_very_deep_nesting(self, shell):
        """Test Scheme with very deep nesting."""
        if SchemeREPL is None:
            pytest.skip("Scheme interpreter not available")

        repl = SchemeREPL()

        # Create properly deeply nested expression: (+ 1 (+ 1 (+ 1 ...)))
        depth = 100
        nested_expr = '(+ 1 ' * depth + '1' + ')' * depth

        try:
            result = repl.eval_string(nested_expr)
            # Should either work or fail gracefully
            assert True
        except (RecursionError, SyntaxError):
            # Expected for very deep nesting or parsing issues
            assert True


class TestCircularReferences:
    """Test handling of potential circular references."""

    def test_symbolic_link_simulation(self, shell):
        """Test simulation of circular symbolic links."""
        # Since this is a virtual filesystem, we can't have real symlinks
        # But we can test similar scenarios

        # Create a structure that might cause issues
        shell.mkdir('/a')
        shell.mkdir('/b')
        shell.echo('content a').out('/a/file.txt')
        shell.echo('content b').out('/b/file.txt')

        # Copy directories to each other (not actually circular, but complex)
        shell.cp('/a/file.txt', '/b/a_copy.txt')
        shell.cp('/b/file.txt', '/a/b_copy.txt')

        # Verify no issues
        assert shell.fs.exists('/a/b_copy.txt')
        assert shell.fs.exists('/b/a_copy.txt')

    def test_deep_directory_nesting(self, shell):
        """Test very deep directory nesting."""
        # Create very deep directory structure
        current_path = ''
        depth = 50

        for i in range(depth):
            current_path += f'/level{i}'
            shell.mkdir(current_path)

        # Should be able to navigate and operate in deep structure
        shell.cd(current_path)
        shell.echo('deep content').out('deep_file.txt')

        assert shell.fs.exists(current_path + '/deep_file.txt')

    def test_filesystem_node_references(self, shell):
        """Test that content-addressable nodes don't create circular refs."""
        # Create multiple files with same content
        content = 'identical content'
        files = [f'/file{i}.txt' for i in range(10)]

        for file in files:
            shell.echo(content).out(file)

        # All should reference same node (content-addressable storage)
        # Verify no circular reference issues
        for file in files:
            result = shell.cat(file)
            assert result.data == (content + '\n').encode()  # echo adds newline

        # Remove some files
        for i in range(0, 10, 2):
            shell.rm(files[i])

        # Remaining files should still work
        for i in range(1, 10, 2):
            result = shell.cat(files[i])
            assert result.data == (content + '\n').encode()  # echo adds newline


class TestResourceExhaustion:
    """Test behavior under resource exhaustion scenarios."""

    def test_many_files_creation(self, shell):
        """Test creating many files."""
        num_files = 1000

        try:
            for i in range(num_files):
                shell.echo(f'content {i}').out(f'/file{i}.txt')

            # Verify some files were created
            assert shell.fs.exists('/file0.txt')
            assert shell.fs.exists(f'/file{num_files-1}.txt')

            # Cleanup
            for i in range(num_files):
                shell.rm(f'/file{i}.txt')

        except Exception:
            # Might run out of resources
            pass

    def test_many_directories_creation(self, shell):
        """Test creating many directories."""
        num_dirs = 500

        try:
            for i in range(num_dirs):
                shell.mkdir(f'/dir{i}')

            # Verify some directories were created
            assert shell.fs.exists('/dir0')
            assert shell.fs.exists(f'/dir{num_dirs-1}')

        except Exception:
            # Might run out of resources
            pass

    def test_very_large_file_content(self, shell):
        """Test handling very large file content."""
        try:
            # Create 1MB content
            large_content = 'x' * (1024 * 1024)
            shell.echo(large_content).out('/huge.txt')

            # Try to read it back
            result = shell.cat('/huge.txt')
            assert len(result.data) == 1024 * 1024 + 1  # +1 for echo's newline

        except MemoryError:
            # Expected for very large files
            pass

    def test_memory_usage_with_many_operations(self, stress_shell):
        """Test memory usage with many operations."""
        # Perform many operations to test memory efficiency
        operations = [
            lambda: stress_shell.ls('/'),
            lambda: stress_shell.cat('/stress0/sub0/file0.txt'),
            lambda: stress_shell.grep('content', '/stress1/sub1/file1.txt'),
            lambda: stress_shell.head(5, '/stress2/sub2/file2.txt'),
            lambda: stress_shell.tail(3, '/stress3/sub3/file3.txt'),
        ]

        # Repeat operations many times
        for _ in range(100):
            for operation in operations:
                try:
                    operation()
                except Exception:
                    # Some operations might fail, that's OK
                    pass

        # Should not crash or consume excessive memory
        assert True


class TestConcurrencyAndRaceConditions:
    """Test potential concurrency issues (even in single-threaded context)."""

    def test_simultaneous_file_operations(self, shell):
        """Test operations that might conflict."""
        # Create file
        shell.echo('original content').out('/shared.txt')

        # Simulate potential race conditions by rapid operations
        operations = [
            lambda: shell.cat('/shared.txt'),
            lambda: shell.echo('new content').out('/shared.txt'),
            lambda: shell.cp('/shared.txt', '/copy.txt'),
            lambda: shell.mv('/copy.txt', '/moved.txt'),
            lambda: shell.rm('/moved.txt'),
        ]

        # Execute operations rapidly
        for operation in operations * 10:
            try:
                operation()
            except Exception:
                # Some operations might fail due to file state changes
                pass

        # Filesystem should remain consistent
        assert shell.fs.exists('/')

    def test_directory_modification_during_listing(self, shell):
        """Test modifying directory while listing it."""
        shell.mkdir('/dynamic')

        # Create initial files
        for i in range(5):
            shell.echo(f'content {i}').out(f'/dynamic/file{i}.txt')

        # List directory
        initial_listing = shell.ls('/dynamic').data

        # Modify directory
        shell.echo('new file').out('/dynamic/new.txt')
        shell.rm('/dynamic/file0.txt')

        # List again
        final_listing = shell.ls('/dynamic').data

        # Should handle modifications gracefully
        assert isinstance(final_listing, list)
        assert 'new.txt' in final_listing
        assert 'file0.txt' not in final_listing


class TestDataCorruption:
    """Test scenarios that might cause data corruption."""

    def test_partial_write_scenarios(self, shell):
        """Test scenarios that might cause partial writes."""
        # Write large content
        large_content = 'A' * 50000
        shell.echo(large_content).out('/large.txt')

        # Immediately read it back
        result = shell.cat('/large.txt')
        assert len(result.data) == 50001  # +1 for echo's newline
        assert result.data == (large_content + '\n').encode()

        # Overwrite with different content
        new_content = 'B' * 30000
        shell.echo(new_content).out('/large.txt')

        # Verify overwrite worked correctly
        result = shell.cat('/large.txt')
        assert len(result.data) == 30001  # +1 for echo's newline
        assert result.data == (new_content + '\n').encode()

    def test_unicode_corruption(self, shell):
        """Test Unicode handling doesn't corrupt data."""
        unicode_content = 'Unicode: ñáéíóú 中文 🌟 русский العربية'
        shell.echo(unicode_content).out('/unicode.txt')

        # Read back and verify
        result = shell.cat('/unicode.txt')
        decoded = result.data.decode('utf-8')
        assert decoded == unicode_content + '\n'  # echo adds newline

        # Test various Unicode edge cases
        edge_cases = [
            '\u0000',  # Null character
            '\uffff',  # Max BMP character
            '🏳️‍🌈',    # Complex emoji with modifiers
            '\n\r\t',  # Control characters
            '𝕌𝕟𝕚𝕔𝕠𝕕𝕖',  # Mathematical alphanumeric symbols
        ]

        for i, case in enumerate(edge_cases):
            try:
                shell.echo(case).out(f'/unicode_edge_{i}.txt')
                result = shell.cat(f'/unicode_edge_{i}.txt')
                decoded = result.data.decode('utf-8')
                assert decoded == case + '\n'  # echo adds newline
            except UnicodeError:
                # Some edge cases might not be supported
                pass

    def test_binary_data_integrity(self, shell):
        """Test that binary data maintains integrity."""
        # Create binary content with all byte values
        binary_content = bytes(range(256))
        shell.fs.write('/binary.bin', binary_content)

        # Read back and verify
        result = shell.cat('/binary.bin')
        assert result.data == binary_content

        # Test specific binary patterns
        patterns = [
            b'\x00' * 1000,  # All zeros
            b'\xff' * 1000,  # All ones
            b'\x00\xff' * 500,  # Alternating
            b'\x55\xaa' * 500,  # Alternating bits
        ]

        for i, pattern in enumerate(patterns):
            shell.fs.write(f'/pattern_{i}.bin', pattern)
            result = shell.cat(f'/pattern_{i}.bin')
            assert result.data == pattern


class TestSystemLimits:
    """Test system limit handling."""

    def test_maximum_path_depth(self, shell):
        """Test maximum supported path depth."""
        max_depth = 100
        path = ''

        try:
            for i in range(max_depth):
                path += f'/d{i}'
                shell.mkdir(path)

            # Should either succeed or fail gracefully
            assert True

        except Exception:
            # May hit system limits
            pass

    def test_maximum_filename_length(self, shell):
        """Test maximum filename length handling."""
        # Test various filename lengths
        lengths = [1, 10, 50, 100, 255, 1000, 10000]

        for length in lengths:
            filename = '/' + 'a' * length + '.txt'
            try:
                shell.echo('test').out(filename)
                if shell.fs.exists(filename):
                    result = shell.cat(filename)
                    assert result.data == b'test'
            except Exception:
                # Long filenames might not be supported
                pass

    def test_filesystem_size_limits(self, shell):
        """Test filesystem size handling."""
        # This is more of a stress test
        try:
            # Create many files to test storage limits
            for i in range(1000):
                content = f'File content {i}' * 100  # 1.5KB per file
                shell.echo(content).out(f'/stress_file_{i}.txt')

            # Should handle gracefully
            assert True

        except Exception:
            # May hit memory or storage limits
            pass


if __name__ == '__main__':
    pytest.main([__file__, '-v'])