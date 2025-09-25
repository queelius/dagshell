#!/usr/bin/env python3
"""
Test suite for the fluent API of dagshell.

Tests the composable, chainable interface that serves as the foundation
for terminal emulation.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import dagshell.dagshell as dagshell
from dagshell.dagshell_fluent import DagShell, CommandResult, shell, _shell
import dagshell.dagshell_fluent as ds


class TestCommandResult:
    """Test the CommandResult class."""

    def test_string_conversion(self):
        """Test string representation of results."""
        # Bytes data
        result = CommandResult(data=b'hello world')
        assert str(result) == 'hello world'

        # List data
        result = CommandResult(data=['line1', 'line2', 'line3'])
        assert str(result) == 'line1\nline2\nline3'

        # Dict data
        result = CommandResult(data={'key1': 'value1', 'key2': 'value2'})
        assert 'key1: value1' in str(result)
        assert 'key2: value2' in str(result)

        # Text override
        result = CommandResult(data=[1, 2, 3], text='custom text')
        assert str(result) == 'custom text'

    def test_bytes_conversion(self):
        """Test bytes representation."""
        result = CommandResult(data=b'binary data')
        assert bytes(result) == b'binary data'

        result = CommandResult(data='text data')
        assert bytes(result) == b'text data'

        result = CommandResult(data=['line1', 'line2'])
        assert bytes(result) == b'line1\nline2'

    def test_iteration(self):
        """Test iteration over results."""
        result = CommandResult(data=['item1', 'item2', 'item3'])
        items = list(result)
        assert items == ['item1', 'item2', 'item3']

        result = CommandResult(data='line1\nline2\nline3')
        lines = list(result)
        assert lines == ['line1', 'line2', 'line3']

        result = CommandResult(data=b'byte1\nbyte2')
        lines = list(result)
        assert lines == ['byte1', 'byte2']

    def test_lines_method(self):
        """Test lines() method."""
        result = CommandResult(data='line1\nline2\nline3')
        assert result.lines() == ['line1', 'line2', 'line3']

        result = CommandResult(data=['a', 'b', 'c'])
        assert result.lines() == ['a', 'b', 'c']

    def test_out_redirection(self):
        """Test output redirection to virtual filesystem."""
        # Reset filesystem
        dagshell._default_fs = None
        fs = dagshell.get_fs()

        # Create a result and redirect to file
        result = CommandResult(data='test content')
        result.out('/tmp/test.txt')

        # Verify file was created
        assert fs.exists('/tmp/test.txt')
        assert fs.read('/tmp/test.txt') == b'test content'


class TestDagShellBasics:
    """Test basic DagShell operations."""

    def setup_method(self):
        """Setup a fresh shell for each test."""
        self.shell = DagShell()

    def test_pwd(self):
        """Test pwd command."""
        result = self.shell.pwd()
        assert result.data == '/'
        assert str(result) == '/'

    def test_cd(self):
        """Test cd command."""
        # Create directory structure
        self.shell.mkdir('/home')
        self.shell.mkdir('/home/user')

        # Change directory
        self.shell.cd('/home/user')
        result = self.shell.pwd()
        assert result.data == '/home/user'

        # Relative cd
        self.shell.cd('..')
        assert self.shell.pwd().data == '/home'

        # cd to home
        self.shell.setenv('HOME', '/home/user')
        self.shell.cd()
        assert self.shell.pwd().data == '/home/user'

    def test_cd_errors(self):
        """Test cd error handling."""
        # Non-existent directory
        self.shell.cd('/nonexistent')
        assert self.shell._last_result.exit_code == 1
        assert 'No such file' in str(self.shell._last_result)

        # cd to file
        self.shell.fs.write('/file.txt', 'content')
        self.shell.cd('/file.txt')
        assert self.shell._last_result.exit_code == 1
        assert 'Not a directory' in str(self.shell._last_result)

    def test_env_operations(self):
        """Test environment variable operations."""
        # Get all env vars
        result = self.shell.env()
        assert isinstance(result.data, dict)
        assert 'PATH' in result.data
        assert 'HOME' in result.data

        # Get specific var
        result = self.shell.env('PATH')
        assert '/bin' in result.data

        # Set env var
        self.shell.setenv('CUSTOM', 'value123')
        result = self.shell.env('CUSTOM')
        assert result.data == 'value123'

    def test_ls(self):
        """Test ls command."""
        # Setup directory structure
        self.shell.mkdir('/test')
        self.shell.fs.write('/test/file1.txt', 'content1')
        self.shell.fs.write('/test/file2.txt', 'content2')
        self.shell.mkdir('/test/subdir')

        # List directory
        result = self.shell.ls('/test')
        assert result.data == ['file1.txt', 'file2.txt', 'subdir']

        # List with long format
        result = self.shell.ls('/test', long=True)
        assert 'file1.txt' in str(result)
        assert 'file2.txt' in str(result)
        assert 'subdir' in str(result)
        assert 'd' in str(result)  # directory indicator

    def test_cat(self):
        """Test cat command."""
        # Create files
        self.shell.fs.write('/file1.txt', 'content1\n')
        self.shell.fs.write('/file2.txt', 'content2\n')

        # Cat single file
        result = self.shell.cat('/file1.txt')
        assert result.data == b'content1\n'

        # Cat multiple files
        result = self.shell.cat('/file1.txt', '/file2.txt')
        assert result.data == b'content1\ncontent2\n'

        # Cat non-existent file
        result = self.shell.cat('/nonexistent.txt')
        assert result.exit_code == 1

    def test_echo(self):
        """Test echo command."""
        result = self.shell.echo('hello', 'world')
        assert str(result) == 'hello world'
        assert result.data == b'hello world\n'

        # Without newline
        result = self.shell.echo('test', n=True)
        assert result.data == b'test'


class TestDagShellFileOps:
    """Test file operation methods."""

    def setup_method(self):
        """Setup a fresh shell for each test."""
        self.shell = DagShell()

    def test_touch(self):
        """Test touch command."""
        self.shell.touch('/newfile.txt')
        assert self.shell.fs.exists('/newfile.txt')
        assert self.shell.fs.read('/newfile.txt') == b''

    def test_mkdir(self):
        """Test mkdir command."""
        self.shell.mkdir('/newdir')
        assert self.shell.fs.exists('/newdir')
        stat = self.shell.fs.stat('/newdir')
        assert stat['type'] == 'dir'

        # With parents flag
        self.shell.mkdir('/path/to/dir', parents=True)
        assert self.shell.fs.exists('/path')
        assert self.shell.fs.exists('/path/to')
        assert self.shell.fs.exists('/path/to/dir')

    def test_rm(self):
        """Test rm command."""
        self.shell.fs.write('/file.txt', 'content')
        self.shell.rm('/file.txt')
        assert not self.shell.fs.exists('/file.txt')

        # Force flag
        self.shell.rm('/nonexistent', force=True)  # Should not error

    def test_cp(self):
        """Test cp command."""
        self.shell.fs.write('/source.txt', 'content')
        self.shell.cp('/source.txt', '/dest.txt')

        assert self.shell.fs.exists('/source.txt')
        assert self.shell.fs.exists('/dest.txt')
        assert self.shell.fs.read('/dest.txt') == b'content'

    def test_mv(self):
        """Test mv command."""
        self.shell.fs.write('/old.txt', 'content')
        self.shell.mv('/old.txt', '/new.txt')

        assert not self.shell.fs.exists('/old.txt')
        assert self.shell.fs.exists('/new.txt')
        assert self.shell.fs.read('/new.txt') == b'content'


class TestDagShellTextProcessing:
    """Test text processing commands."""

    def setup_method(self):
        """Setup a fresh shell with test data."""
        self.shell = DagShell()
        # Create test file
        self.shell.fs.write('/data.txt', 'line1\nline2\ntest line\nline3\ntest data\n')

    def test_grep(self):
        """Test grep command."""
        result = self.shell.grep('test', '/data.txt')
        assert result.data == ['test line', 'test data']

        # Case insensitive
        self.shell.fs.write('/mixed.txt', 'Test\ntest\nTEST\n')
        result = self.shell.grep('test', '/mixed.txt', ignore_case=True)
        assert len(result.data) == 3

        # Invert match
        result = self.shell.grep('test', '/data.txt', invert=True)
        assert 'test' not in ' '.join(result.data)

    def test_head(self):
        """Test head command."""
        result = self.shell.head(2, '/data.txt')
        assert result.data == ['line1', 'line2']

        # Default 10 lines
        self.shell.fs.write('/long.txt', '\n'.join(f'line{i}' for i in range(20)))
        result = self.shell.head(10, '/long.txt')
        assert len(result.data) == 10

    def test_tail(self):
        """Test tail command."""
        result = self.shell.tail(2, '/data.txt')
        assert result.data == ['line3', 'test data']

        # From large file
        self.shell.fs.write('/long.txt', '\n'.join(f'line{i}' for i in range(20)))
        result = self.shell.tail(5, '/long.txt')
        assert len(result.data) == 5
        assert result.data[0] == 'line15'

    def test_wc(self):
        """Test wc command."""
        # Line count (default)
        result = self.shell.wc('/data.txt')
        assert result.data == 5  # 5 lines (counting newlines)

        # Word count
        result = self.shell.wc('/data.txt', words=True, lines=False)
        assert result.data == 7

        # Character count
        result = self.shell.wc('/data.txt', chars=True, lines=False)
        assert result.data > 0

    def test_sort(self):
        """Test sort command."""
        self.shell.fs.write('/unsorted.txt', 'zebra\napple\nbanana\n')

        result = self.shell.sort('/unsorted.txt')
        assert result.data == ['apple', 'banana', 'zebra']

        # Reverse sort
        result = self.shell.sort('/unsorted.txt', reverse=True)
        assert result.data == ['zebra', 'banana', 'apple']

        # Numeric sort
        self.shell.fs.write('/numbers.txt', '10\n2\n30\n4\n')
        result = self.shell.sort('/numbers.txt', numeric=True)
        assert result.data == ['2', '4', '10', '30']

    def test_uniq(self):
        """Test uniq command."""
        self.shell.fs.write('/dupes.txt', 'line1\nline1\nline2\nline2\nline2\nline3\n')

        result = self.shell.uniq('/dupes.txt')
        assert result.data == ['line1', 'line2', 'line3']

        # With count
        result = self.shell.uniq('/dupes.txt', count=True)
        assert len(result.data) == 3
        assert result.data[0] == (2, 'line1')
        assert result.data[1] == (3, 'line2')


class TestDagShellChaining:
    """Test method chaining and piping."""

    def setup_method(self):
        """Setup a fresh shell with test data."""
        self.shell = DagShell()
        # Create test structure
        self.shell.mkdir('/home')
        self.shell.mkdir('/home/user')
        self.shell.fs.write('/home/user/data.txt', 'apple\nbanana\napricot\ngrape\n')

    def test_basic_chaining(self):
        """Test basic method chaining."""
        # Navigate and create structure
        self.shell.cd('/home').mkdir('test').cd('test').touch('file.txt')

        assert self.shell.pwd().data == '/home/test'
        assert self.shell.fs.exists('/home/test/file.txt')

    def test_piping_through_last_result(self):
        """Test piping through _last_result."""
        # ls -> grep pattern
        self.shell.ls('/home/user')
        result = self.shell.grep('data')
        assert result.data == ['data.txt']

        # cat -> head
        self.shell.cat('/home/user/data.txt')
        result = self.shell.head(2)
        assert result.data == ['apple', 'banana']

        # cat -> grep -> wc
        self.shell.cat('/home/user/data.txt')
        self.shell.grep('a')  # matches apple, banana, apricot, grape
        result = self.shell.wc()
        assert result.data == 3  # 3 newlines in matched lines

    def test_output_redirection(self):
        """Test output redirection with .out()."""
        # Simple redirection
        result = self.shell.echo('test content')
        result.out('/output.txt')

        assert self.shell.fs.read('/output.txt') == b'test content\n'

        # Chain with redirection
        result = self.shell.cat('/home/user/data.txt').out('/copy.txt')
        assert self.shell.fs.read('/copy.txt') == b'apple\nbanana\napricot\ngrape\n'

    def test_tee(self):
        """Test tee command."""
        self.shell.echo('test data')
        result = self.shell.tee('/tee_out.txt')

        assert str(result) == 'test data'
        assert self.shell.fs.read('/tee_out.txt') == b'test data\n'


class TestDagShellAdvanced:
    """Test advanced shell features."""

    def setup_method(self):
        """Setup a complex directory structure."""
        self.shell = DagShell()
        # Create directory tree
        self.shell.mkdir('/root', parents=True)
        self.shell.mkdir('/root/dir1', parents=True)
        self.shell.mkdir('/root/dir2', parents=True)
        self.shell.mkdir('/root/dir1/subdir', parents=True)

        self.shell.fs.write('/root/file1.txt', 'content')
        self.shell.fs.write('/root/dir1/file2.txt', 'content')
        self.shell.fs.write('/root/dir1/test.py', 'code')
        self.shell.fs.write('/root/dir2/data.csv', 'data')

    def test_find(self):
        """Test find command."""
        # Find all
        result = self.shell.find('/root')
        assert '/root' in result.data
        assert '/root/dir1' in result.data
        assert '/root/file1.txt' in result.data

        # Find by name
        result = self.shell.find('/root', name='*.txt')
        assert '/root/file1.txt' in result.data
        assert '/root/dir1/file2.txt' in result.data
        assert '/root/dir1/test.py' not in result.data

        # Find by type
        result = self.shell.find('/root', type='d')
        assert '/root' in result.data
        assert '/root/dir1' in result.data
        assert '/root/file1.txt' not in result.data

        # Max depth
        result = self.shell.find('/root', maxdepth=1)
        assert '/root/dir1/subdir' not in result.data

    def test_glob_patterns(self):
        """Test glob pattern matching."""
        files = self.shell._glob_match('*.txt', '/root')
        assert 'file1.txt' in files

        files = self.shell._glob_match('dir*', '/root')
        assert 'dir1' in files
        assert 'dir2' in files

    def test_path_resolution(self):
        """Test path resolution."""
        self.shell.cd('/root/dir1')

        # Relative paths
        assert self.shell._resolve_path('.') == '/root/dir1'
        assert self.shell._resolve_path('..') == '/root'
        assert self.shell._resolve_path('./subdir') == '/root/dir1/subdir'
        assert self.shell._resolve_path('../dir2') == '/root/dir2'

        # Absolute paths
        assert self.shell._resolve_path('/root') == '/root'


class TestModuleLevelFunctions:
    """Test module-level convenience functions."""

    def setup_method(self):
        """Reset global shell."""
        # Reset both the global filesystem and the shell
        dagshell._default_fs = None
        import dagshell.dagshell_fluent as dagshell_fluent
        dagshell_fluent._shell = DagShell()
        ds.shell.mkdir('/test')
        ds.shell.fs.write('/test/file.txt', 'test content')

    def test_convenience_functions(self):
        """Test module-level functions."""
        # cd and pwd
        ds.cd('/test')
        assert ds.pwd().data == '/test'

        # ls
        result = ds.ls()
        assert 'file.txt' in result.data

        # cat
        result = ds.cat('file.txt')
        assert result.data == b'test content'

        # echo
        result = ds.echo('hello')
        assert str(result) == 'hello'

        # grep
        ds.shell.fs.write('/test/data.txt', 'line1\ntest line\nline3\n')
        result = ds.grep('test', '/test/data.txt')
        assert result.data == ['test line']

    def test_global_shell_access(self):
        """Test direct access to global shell instance."""
        # Use the module's shell instance directly
        ds.shell.cd('/').mkdir('global_test')

        assert ds.shell.fs.exists('/global_test')
        assert ds.pwd().data == '/'


class TestComplexPipelines:
    """Test complex command pipelines."""

    def setup_method(self):
        """Setup test data."""
        self.shell = DagShell()
        # Create log file
        log_data = """
2024-01-01 10:00:00 ERROR Failed to connect
2024-01-01 10:01:00 INFO Connection established
2024-01-01 10:02:00 WARNING Low memory
2024-01-01 10:03:00 ERROR Timeout occurred
2024-01-01 10:04:00 INFO Task completed
2024-01-01 10:05:00 ERROR Network unreachable
"""
        self.shell.fs.write('/system.log', log_data.strip())

    def test_log_analysis_pipeline(self):
        """Test a realistic log analysis pipeline."""
        # Find ERROR lines, sort them, count them
        self.shell.cat('/system.log')
        self.shell.grep('ERROR')
        errors = self.shell._last_result.data

        assert len(errors) == 3

        # Get unique error messages
        self.shell.cat('/system.log')
        self.shell.grep('ERROR')
        result = self.shell.sort()
        assert len(result.data) == 3

        # Count error lines
        self.shell.cat('/system.log')
        self.shell.grep('ERROR')
        result = self.shell.wc()
        assert result.data == 2  # 2 newlines in 3 lines

    def test_file_processing_pipeline(self):
        """Test file processing pipeline."""
        # Create multiple files
        self.shell.mkdir('/data')
        self.shell.fs.write('/data/file1.csv', 'name,age\nAlice,30\nBob,25\n')
        self.shell.fs.write('/data/file2.csv', 'name,age\nCharlie,35\nDiana,28\n')
        self.shell.fs.write('/data/readme.txt', 'Data files for processing\n')

        # Find all CSV files
        result = self.shell.find('/data', name='*.csv')
        assert len(result.data) == 2

        # Process CSV files
        self.shell.cat('/data/file1.csv', '/data/file2.csv')
        self.shell.grep('Alice')
        assert 'Alice,30' in self.shell._last_result.data[0]

    def test_data_transformation_pipeline(self):
        """Test data transformation pipeline."""
        # Create data file
        data = "3\n1\n4\n1\n5\n9\n2\n6\n5\n3\n5\n"
        self.shell.fs.write('/numbers.txt', data)

        # Sort numerically and get unique values
        result = self.shell.sort('/numbers.txt', numeric=True, unique=True)
        assert result.data == ['1', '2', '3', '4', '5', '6', '9']

        # Get top 3 numbers
        self.shell.sort('/numbers.txt', numeric=True, reverse=True)
        result = self.shell.head(3)
        assert result.data == ['9', '6', '5']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])