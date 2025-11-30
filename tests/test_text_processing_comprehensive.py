#!/usr/bin/env python3
"""
Comprehensive tests for DagShell text processing commands.

This test suite covers cat, echo, grep, sort, uniq, head, tail, wc, piping,
and tee commands, including fixes for tee file writing and append operations.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from dagshell.dagshell_fluent import DagShell, CommandResult


@pytest.fixture
def shell():
    """Create a fresh DagShell instance for each test."""
    return DagShell()


@pytest.fixture
def text_shell():
    """Create a DagShell instance with text processing test data."""
    shell = DagShell()

    # Create directories
    shell.mkdir('/data')
    shell.mkdir('/logs')
    shell.mkdir('/tmp')

    # Create text files with various content for testing
    shell.echo('apple\nbanana\ncherry\napricot\ngrape\nbanana').out('/data/fruits.txt')
    shell.echo('line 1\nline 2\nline 3\nline 4\nline 5\nline 6\nline 7\nline 8\nline 9\nline 10').out('/data/numbers.txt')
    shell.echo('Error: Failed to connect\nInfo: Starting service\nError: Database timeout\nWarning: Low memory\nInfo: Service ready\nError: Network error').out('/logs/system.log')
    shell.echo('one word\ntwo words here\nthree words in line\nfour words in this line').out('/data/words.txt')
    shell.touch('/data/empty.txt')  # Empty file
    shell.echo('single line').out('/data/single.txt')

    return shell


class TestCatCommand:
    """Test cat command for file reading and concatenation."""

    def test_cat_single_file(self, text_shell):
        """Test reading a single file with cat."""
        result = text_shell.cat('/data/fruits.txt')
        expected_lines = ['apple', 'banana', 'cherry', 'apricot', 'grape', 'banana']
        assert result.data.decode().strip().split('\n') == expected_lines

    def test_cat_multiple_files(self, text_shell):
        """Test concatenating multiple files."""
        result = text_shell.cat('/data/single.txt', '/data/empty.txt', '/data/single.txt')
        # Should concatenate: "single line" + "" + "single line"
        assert b'single line' in result.data
        lines = result.data.decode().strip().split('\n')
        assert lines[0] == 'single line'
        assert lines[-1] == 'single line'

    def test_cat_nonexistent_file(self, shell):
        """Test cat on nonexistent file."""
        result = shell.cat('/nonexistent.txt')
        # Should handle gracefully
        assert result.exit_code != 0 or result.data == b''

    def test_cat_empty_file(self, text_shell):
        """Test cat on empty file."""
        result = text_shell.cat('/data/empty.txt')
        assert result.data == b''

    def test_cat_with_piping_context(self, text_shell):
        """Test cat used in piping context."""
        # cat file | head -3
        result = text_shell.cat('/data/numbers.txt').out('/tmp/temp.txt')
        head_result = text_shell.head(3, '/tmp/temp.txt')
        assert len(head_result.data) == 3
        assert head_result.data[0] == 'line 1'


class TestEchoCommand:
    """Test echo command for text output."""

    def test_echo_simple_text(self, shell):
        """Test echoing simple text."""
        result = shell.echo('Hello, World!')
        assert result.text == 'Hello, World!'

    def test_echo_multiple_arguments(self, shell):
        """Test echoing multiple arguments."""
        result = shell.echo('Hello', 'World', 'Test')
        assert result.data == b'Hello World Test\n'

    def test_echo_with_newline_flag(self, shell):
        """Test echo with -n flag (no newline)."""
        result = shell.echo('No newline', n=True)
        assert result.data == b'No newline'
        # Verify no trailing newline in text representation
        assert result.text == 'No newline'

    def test_echo_empty_string(self, shell):
        """Test echoing empty string."""
        result = shell.echo('')
        assert result.data == b'\n'

    def test_echo_with_special_characters(self, shell):
        """Test echo with special characters."""
        result = shell.echo('Line 1\nLine 2\tTabbed')
        assert b'Line 1\nLine 2\tTabbed' in result.data

    def test_echo_to_file_output(self, shell):
        """Test echo redirected to file."""
        shell.echo('Test content').out('/test.txt')
        result = shell.cat('/test.txt')
        assert result.data == b'Test content\n'


class TestGrepCommand:
    """Test grep command for pattern matching."""

    def test_grep_simple_pattern(self, text_shell):
        """Test grep with simple pattern."""
        result = text_shell.grep('Error', '/logs/system.log')
        assert len(result.data) == 3  # Three error lines
        for line in result.data:
            assert 'Error' in line

    def test_grep_case_insensitive(self, text_shell):
        """Test grep with case-insensitive flag."""
        result = text_shell.grep('error', '/logs/system.log', ignore_case=True)
        assert len(result.data) == 3  # Should match 'Error' lines

    def test_grep_line_numbers(self, text_shell):
        """Test grep with line numbers (feature not implemented, testing basic grep)."""
        result = text_shell.grep('line', '/data/numbers.txt')
        # Should find all lines with 'line' in them
        assert len(result.data) == 10  # All 10 lines contain 'line'

    def test_grep_invert_match(self, text_shell):
        """Test grep with inverted matching."""
        result = text_shell.grep('Error', '/logs/system.log', invert=True)
        # Should return lines that don't contain 'Error'
        for line in result.data:
            assert 'Error' not in line

    def test_grep_multiple_files(self, text_shell):
        """Test grep across multiple files."""
        result = text_shell.grep('line', '/data/numbers.txt', '/data/words.txt')
        # Should find matches in both files
        assert len(result.data) > 0

    def test_grep_no_matches(self, text_shell):
        """Test grep with pattern that matches nothing."""
        result = text_shell.grep('nonexistent_pattern', '/data/fruits.txt')
        assert len(result.data) == 0

    def test_grep_piped_input(self, text_shell):
        """Test grep working on piped input."""
        # Test chaining: cat file | grep pattern
        text_shell.cat('/logs/system.log')
        result = text_shell.grep('Info')
        assert len(result.data) == 2  # Two info lines


class TestSortCommand:
    """Test sort command for line sorting."""

    def test_sort_basic(self, text_shell):
        """Test basic alphabetical sorting."""
        result = text_shell.sort('/data/fruits.txt')
        expected = ['apple', 'apricot', 'banana', 'banana', 'cherry', 'grape']
        assert result.data == expected

    def test_sort_reverse(self, text_shell):
        """Test reverse sorting."""
        result = text_shell.sort('/data/fruits.txt', reverse=True)
        expected = ['grape', 'cherry', 'banana', 'banana', 'apricot', 'apple']
        assert result.data == expected

    def test_sort_numeric(self, shell):
        """Test numeric sorting."""
        shell.echo('10\n2\n1\n20\n3').out('/data/numbers_unsorted.txt')
        result = shell.sort('/data/numbers_unsorted.txt', numeric=True)
        expected = ['1', '2', '3', '10', '20']
        assert result.data == expected

    def test_sort_piped_input(self, text_shell):
        """Test sort on piped input."""
        text_shell.cat('/data/fruits.txt')
        result = text_shell.sort()
        expected = ['apple', 'apricot', 'banana', 'banana', 'cherry', 'grape']
        assert result.data == expected

    def test_sort_empty_file(self, text_shell):
        """Test sort on empty file."""
        result = text_shell.sort('/data/empty.txt')
        assert result.data == []


class TestUniqCommand:
    """Test uniq command for removing duplicate lines."""

    def test_uniq_basic(self, text_shell):
        """Test basic duplicate removal."""
        # First sort, then uniq (as uniq typically works on sorted input)
        text_shell.sort('/data/fruits.txt')
        result = text_shell.uniq()
        expected = ['apple', 'apricot', 'banana', 'cherry', 'grape']
        assert result.data == expected

    def test_uniq_with_count(self, text_shell):
        """Test uniq with count flag."""
        text_shell.sort('/data/fruits.txt')
        result = text_shell.uniq(count=True)
        # Should return tuples (count, value)
        banana_line = [line for line in result.data if line[1] == 'banana'][0]
        assert banana_line == (2, 'banana')

    def test_uniq_on_unsorted_data(self, shell):
        """Test uniq on unsorted data (only removes consecutive duplicates)."""
        shell.echo('a\na\nb\na\na').out('/data/consecutive.txt')
        result = shell.uniq('/data/consecutive.txt')
        # Should remove consecutive duplicates only
        expected = ['a', 'b', 'a']
        assert result.data == expected


class TestHeadCommand:
    """Test head command for showing first lines."""

    def test_head_default(self, text_shell):
        """Test head with default number of lines (10)."""
        text_shell.cat('/data/numbers.txt')
        result = text_shell.head()
        assert len(result.data) == 10
        assert result.data[0] == 'line 1'
        assert result.data[9] == 'line 10'

    def test_head_specified_lines(self, text_shell):
        """Test head with specified number of lines."""
        text_shell.cat('/data/fruits.txt')
        result = text_shell.head(3)
        assert len(result.data) == 3
        expected = ['apple', 'banana', 'cherry']
        assert result.data == expected

    def test_head_more_lines_than_file(self, text_shell):
        """Test head requesting more lines than file has."""
        text_shell.cat('/data/single.txt')
        result = text_shell.head(10)
        assert len(result.data) == 1
        assert result.data[0] == 'single line'

    def test_head_empty_file(self, text_shell):
        """Test head on empty file."""
        text_shell.cat('/data/empty.txt')
        result = text_shell.head(5)
        assert len(result.data) == 0

    def test_head_piped_input(self, text_shell):
        """Test head on piped input."""
        text_shell.cat('/data/numbers.txt')
        result = text_shell.head(3)
        assert len(result.data) == 3
        assert result.data[0] == 'line 1'


class TestTailCommand:
    """Test tail command for showing last lines."""

    def test_tail_default(self, text_shell):
        """Test tail with default number of lines (10)."""
        text_shell.cat('/data/numbers.txt')
        result = text_shell.tail()
        assert len(result.data) == 10
        assert result.data[0] == 'line 1'  # File only has 10 lines
        assert result.data[9] == 'line 10'

    def test_tail_specified_lines(self, text_shell):
        """Test tail with specified number of lines."""
        text_shell.cat('/data/fruits.txt')
        result = text_shell.tail(3)
        assert len(result.data) == 3
        expected = ['apricot', 'grape', 'banana']  # Last 3 lines
        assert result.data == expected

    def test_tail_more_lines_than_file(self, text_shell):
        """Test tail requesting more lines than file has."""
        text_shell.cat('/data/single.txt')
        result = text_shell.tail(10)
        assert len(result.data) == 1
        assert result.data[0] == 'single line'

    def test_tail_piped_input(self, text_shell):
        """Test tail on piped input."""
        text_shell.cat('/data/fruits.txt')
        result = text_shell.tail(2)
        assert len(result.data) == 2
        expected = ['grape', 'banana']
        assert result.data == expected


class TestWcCommand:
    """Test wc command for counting lines, words, characters."""

    def test_wc_lines_only(self, text_shell):
        """Test wc counting lines only."""
        result = text_shell.wc('/data/fruits.txt', lines=True, words=False, chars=False)
        assert result.data == 6  # 6 lines in fruits.txt

    def test_wc_words_only(self, text_shell):
        """Test wc counting words only."""
        result = text_shell.wc('/data/words.txt', lines=False, words=True, chars=False)
        # "one word" + "two words here" + "three words in line" + "four words in this line"
        # = 2 + 3 + 4 + 5 = 14 words
        assert result.data == 14

    def test_wc_chars_only(self, text_shell):
        """Test wc counting characters only."""
        result = text_shell.wc('/data/single.txt', lines=False, words=False, chars=True)
        # "single line\n" = 12 characters (including newline)
        assert result.data == 12

    def test_wc_all_counts(self, text_shell):
        """Test wc with all counts enabled."""
        result = text_shell.wc('/data/single.txt', lines=True, words=True, chars=True)
        # Should return a dict with all counts
        assert isinstance(result.data, dict)
        assert 'lines' in result.data
        assert 'words' in result.data
        assert 'chars' in result.data

    def test_wc_empty_file(self, text_shell):
        """Test wc on empty file."""
        result = text_shell.wc('/data/empty.txt', lines=True, words=True, chars=True)
        # Should return all counts as 0
        assert isinstance(result.data, dict)
        assert result.data['lines'] == 0
        assert result.data['words'] == 0
        assert result.data['chars'] == 0

    def test_wc_piped_input(self, text_shell):
        """Test wc on piped input."""
        text_shell.echo('line 1\nline 2\nline 3')
        result = text_shell.wc(lines=True, words=False, chars=False)
        assert result.data == 3


class TestTeeCommand:
    """Test tee command including the fix for writing to files."""

    def test_tee_basic_functionality(self, text_shell):
        """Test basic tee functionality - display and save."""
        text_shell.echo('test output')
        result = text_shell.tee('/tmp/tee_test.txt')

        # Should return the original data
        assert result.data == b'test output\n'

        # Should also save to file
        file_content = text_shell.cat('/tmp/tee_test.txt')
        assert file_content.data == b'test output\n'

    def test_tee_with_piped_input(self, text_shell):
        """Test tee with piped input."""
        text_shell.cat('/data/fruits.txt')
        result = text_shell.tee('/tmp/fruits_copy.txt')

        # Should preserve the original data
        original = text_shell.cat('/data/fruits.txt').data
        saved = text_shell.cat('/tmp/fruits_copy.txt').data
        assert original == saved

    def test_tee_file_writing_fix(self, text_shell):
        """Test the fix for tee writing to files correctly."""
        # Create some data and tee it
        text_shell.echo('line 1\nline 2\nline 3')
        result = text_shell.tee('/tmp/multiline.txt')

        # Verify file was written correctly
        file_content = text_shell.cat('/tmp/multiline.txt')
        assert b'line 1' in file_content.data
        assert b'line 2' in file_content.data
        assert b'line 3' in file_content.data

    def test_tee_preserves_data_for_chaining(self, text_shell):
        """Test that tee preserves data for further chaining."""
        text_shell.cat('/data/fruits.txt')
        text_shell.tee('/tmp/backup.txt')
        result = text_shell.head(3)

        # Should get head of the original data
        assert len(result.data) == 3
        assert result.data[0] == 'apple'

        # File should contain full original data
        file_content = text_shell.cat('/tmp/backup.txt')
        assert b'grape' in file_content.data  # Last item in original


class TestPipingAndChaining:
    """Test command piping and chaining functionality."""

    def test_simple_pipe_chain(self, text_shell):
        """Test simple command chaining."""
        # cat | grep | head
        text_shell.cat('/logs/system.log')
        text_shell.grep('Error')
        result = text_shell.head(2)
        assert len(result.data) == 2
        for line in result.data:
            assert 'Error' in line

    def test_complex_pipe_chain(self, text_shell):
        """Test complex command chaining."""
        # cat | grep | sort | uniq | tail
        text_shell.cat('/data/fruits.txt')
        text_shell.grep('a')  # Lines containing 'a'
        text_shell.sort()
        text_shell.uniq()
        result = text_shell.tail(2)

        # Should get last 2 unique lines containing 'a', sorted
        assert len(result.data) <= 2

    def test_pipe_with_tee_in_middle(self, text_shell):
        """Test piping with tee in the middle of chain."""
        text_shell.cat('/data/fruits.txt')
        text_shell.tee('/tmp/intermediate.txt')
        text_shell.grep('a')
        result = text_shell.head(3)

        # Should get grep results
        for line in result.data:
            assert 'a' in line

        # Intermediate file should have original data
        intermediate = text_shell.cat('/tmp/intermediate.txt')
        assert b'apple' in intermediate.data

    def test_data_flow_through_pipes(self, text_shell):
        """Test that data flows correctly through pipe chain."""
        # Start with known data, transform it step by step
        text_shell.echo('zebra\napple\nbanana')
        text_shell.sort()  # [apple, banana, zebra]
        text_shell.head(2)  # [apple, banana]
        result = text_shell.grep('a')  # Lines containing 'a'

        assert len(result.data) == 2  # Both apple and banana contain 'a'


class TestAppendOperations:
    """Test append operations and persistence fix."""

    def test_append_to_file(self, text_shell):
        """Test the >> append operation persistence fix."""
        # Create initial file
        text_shell.echo('line 1').out('/tmp/append_test.txt')

        # Append to it
        text_shell.echo('line 2').append('/tmp/append_test.txt')
        text_shell.echo('line 3').append('/tmp/append_test.txt')

        # Verify content
        result = text_shell.cat('/tmp/append_test.txt')
        lines = result.data.decode().strip().split('\n')
        assert len(lines) == 3
        assert lines[0] == 'line 1'
        assert lines[1] == 'line 2'
        assert lines[2] == 'line 3'

    def test_append_creates_file_if_not_exists(self, shell):
        """Test that append creates file if it doesn't exist."""
        shell.echo('first line').append('/tmp/new_file.txt')

        result = shell.cat('/tmp/new_file.txt')
        assert result.data == b'first line\n'

    def test_append_with_empty_content(self, text_shell):
        """Test appending empty content."""
        text_shell.echo('initial').out('/tmp/empty_append.txt')
        text_shell.echo('').append('/tmp/empty_append.txt')

        result = text_shell.cat('/tmp/empty_append.txt')
        # Should have original content plus empty line
        assert b'initial' in result.data


if __name__ == '__main__':
    pytest.main([__file__, '-v'])