#!/usr/bin/env python3
"""
Additional tests for command_parser.py to improve coverage.

This module targets the uncovered lines identified by coverage analysis:
- String representation methods
- Background execution parsing
- Quote handling in pipe splitting
- Here documents and here strings
- End-of-flags marker (--)
- Long flags with = value
- Numeric flags for head/tail
- Value flag conversion errors
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest

from dagshell.command_parser import (
    CommandParser, Command, Pipeline, CommandGroup,
    RedirectType, Redirect
)


class TestCommandStr(unittest.TestCase):
    """Test Command.__str__ method."""

    def test_command_str_simple(self):
        """Test string representation of simple command."""
        cmd = Command(
            name='ls',
            args=[],
            flags={},
            redirects=[],
            raw_args=[]
        )
        self.assertEqual(str(cmd), 'ls')

    def test_command_str_with_args(self):
        """Test string representation with arguments."""
        cmd = Command(
            name='echo',
            args=['hello', 'world'],
            flags={},
            redirects=[],
            raw_args=['hello', 'world']
        )
        self.assertEqual(str(cmd), 'echo hello world')

    def test_command_str_with_boolean_flag(self):
        """Test string representation with boolean flag."""
        cmd = Command(
            name='ls',
            args=[],
            flags={'all': True, 'long': True},
            redirects=[],
            raw_args=[]
        )
        result = str(cmd)
        self.assertIn('-all', result)
        self.assertIn('-long', result)

    def test_command_str_with_value_flag(self):
        """Test string representation with value flag."""
        cmd = Command(
            name='head',
            args=[],
            flags={'lines': 10},
            redirects=[],
            raw_args=[]
        )
        self.assertIn('--lines=10', str(cmd))


class TestPipelineStr(unittest.TestCase):
    """Test Pipeline.__str__ method."""

    def test_pipeline_str_single_command(self):
        """Test string representation of single command pipeline."""
        cmd = Command(
            name='ls',
            args=[],
            flags={},
            redirects=[],
            raw_args=[]
        )
        pipeline = Pipeline(commands=[cmd])
        self.assertEqual(str(pipeline), 'ls')

    def test_pipeline_str_multiple_commands(self):
        """Test string representation of multi-command pipeline."""
        cmd1 = Command(name='ls', args=[], flags={}, redirects=[], raw_args=[])
        cmd2 = Command(name='grep', args=['test'], flags={}, redirects=[], raw_args=['test'])
        pipeline = Pipeline(commands=[cmd1, cmd2])
        self.assertEqual(str(pipeline), 'ls | grep test')


class TestCommandGroupStr(unittest.TestCase):
    """Test CommandGroup.__str__ method."""

    def test_command_group_str_simple(self):
        """Test string representation of simple command group."""
        cmd = Command(name='ls', args=[], flags={}, redirects=[], raw_args=[])
        pipeline = Pipeline(commands=[cmd])
        group = CommandGroup(pipelines=[(pipeline, None)])
        self.assertEqual(str(group), 'ls')

    def test_command_group_str_with_operator(self):
        """Test string representation with operator."""
        cmd1 = Command(name='cd', args=['/home'], flags={}, redirects=[], raw_args=['/home'])
        cmd2 = Command(name='ls', args=[], flags={}, redirects=[], raw_args=[])
        pipeline1 = Pipeline(commands=[cmd1])
        pipeline2 = Pipeline(commands=[cmd2])
        group = CommandGroup(pipelines=[(pipeline1, '&&'), (pipeline2, None)])
        self.assertEqual(str(group), 'cd /home && ls')


class TestBackgroundExecution(unittest.TestCase):
    """Test background execution parsing."""

    def setUp(self):
        """Set up test fixtures."""
        self.parser = CommandParser()

    def test_parse_background_command(self):
        """Test parsing command with & operator."""
        # In the current parser, & is treated as an operator in the pipelines list
        group = self.parser.parse("sleep 5 &")
        self.assertEqual(len(group.pipelines), 1)
        pipeline, operator = group.pipelines[0]
        self.assertEqual(operator, '&')
        self.assertEqual(pipeline.commands[0].name, 'sleep')

    def test_parse_pipeline_background(self):
        """Test parsing pipeline with & operator."""
        group = self.parser.parse("ls | grep test &")
        pipeline, operator = group.pipelines[0]
        self.assertEqual(operator, '&')
        self.assertEqual(len(pipeline.commands), 2)

    def test_parse_pipeline_internal_background(self):
        """Test _parse_pipeline with trailing & (direct call)."""
        # Directly test _parse_pipeline with trailing &
        pipeline = self.parser._parse_pipeline("sleep 5&")
        self.assertTrue(pipeline.background)
        self.assertEqual(pipeline.commands[0].name, 'sleep')


class TestQuoteHandling(unittest.TestCase):
    """Test quote handling in pipe splitting."""

    def setUp(self):
        """Set up test fixtures."""
        self.parser = CommandParser()

    def test_escaped_character(self):
        """Test escaped characters in command."""
        cmd = self.parser.parse_simple("echo hello\\ world")
        self.assertEqual(cmd.name, 'echo')

    def test_single_quotes_with_pipe_char(self):
        """Test single quotes containing pipe character."""
        group = self.parser.parse("echo 'hello | world'")
        # Should be single command, not pipeline
        pipeline = group.pipelines[0][0]
        self.assertEqual(len(pipeline.commands), 1)
        self.assertEqual(pipeline.commands[0].name, 'echo')
        self.assertIn('hello | world', pipeline.commands[0].args)

    def test_double_quotes_with_pipe_char(self):
        """Test double quotes containing pipe character."""
        group = self.parser.parse('echo "hello | world"')
        pipeline = group.pipelines[0][0]
        self.assertEqual(len(pipeline.commands), 1)
        self.assertIn('hello | world', pipeline.commands[0].args)

    def test_mixed_quotes_in_pipeline(self):
        """Test mixed quotes in pipeline."""
        group = self.parser.parse("echo 'test' | grep 'pattern'")
        pipeline = group.pipelines[0][0]
        self.assertEqual(len(pipeline.commands), 2)


class TestUnclosedQuotes(unittest.TestCase):
    """Test handling of unclosed quotes."""

    def setUp(self):
        """Set up test fixtures."""
        self.parser = CommandParser()

    def test_unclosed_single_quote(self):
        """Test unclosed single quote fallback to split()."""
        cmd = self.parser.parse_simple("echo 'unclosed")
        # Should fallback to simple split
        self.assertEqual(cmd.name, 'echo')
        self.assertIn("'unclosed", cmd.args)

    def test_unclosed_double_quote(self):
        """Test unclosed double quote fallback to split()."""
        cmd = self.parser.parse_simple('echo "unclosed')
        self.assertEqual(cmd.name, 'echo')
        self.assertIn('"unclosed', cmd.args)


class TestHereDocuments(unittest.TestCase):
    """Test here document and here string parsing."""

    def setUp(self):
        """Set up test fixtures."""
        self.parser = CommandParser()

    def test_here_doc_redirect(self):
        """Test here document redirection (<<)."""
        cmd = self.parser.parse_simple("cat <<EOF")
        self.assertEqual(cmd.name, 'cat')
        self.assertEqual(len(cmd.redirects), 1)
        self.assertEqual(cmd.redirects[0].type, RedirectType.HERE_DOC)
        self.assertEqual(cmd.redirects[0].target, 'EOF')
        self.assertEqual(cmd.redirects[0].fd, 0)

    def test_here_string_redirect(self):
        """Test here string redirection (<<<)."""
        cmd = self.parser.parse_simple("cat <<<'hello'")
        self.assertEqual(cmd.name, 'cat')
        self.assertEqual(len(cmd.redirects), 1)
        self.assertEqual(cmd.redirects[0].type, RedirectType.HERE_STR)
        self.assertEqual(cmd.redirects[0].target, "'hello'")


class TestEndOfFlagsMarker(unittest.TestCase):
    """Test -- end of flags marker."""

    def setUp(self):
        """Set up test fixtures."""
        self.parser = CommandParser()

    def test_double_dash_ends_flags(self):
        """Test that -- stops flag parsing."""
        cmd = self.parser.parse_simple("grep -- -pattern file.txt")
        self.assertEqual(cmd.name, 'grep')
        # -pattern should be treated as an argument, not a flag
        self.assertIn('-pattern', cmd.args)
        self.assertIn('file.txt', cmd.args)

    def test_double_dash_with_leading_flags(self):
        """Test -- with flags before it."""
        cmd = self.parser.parse_simple("grep -i -- -v file.txt")
        self.assertEqual(cmd.name, 'grep')
        self.assertEqual(cmd.flags.get('ignore_case'), True)
        self.assertIn('-v', cmd.args)
        self.assertIn('file.txt', cmd.args)


class TestLongFlagsWithEquals(unittest.TestCase):
    """Test long flags with = value."""

    def setUp(self):
        """Set up test fixtures."""
        self.parser = CommandParser()

    def test_long_flag_with_equals_value(self):
        """Test long flag with =value syntax."""
        cmd = self.parser.parse_simple("command --output=file.txt")
        self.assertEqual(cmd.name, 'command')
        self.assertEqual(cmd.flags.get('output'), 'file.txt')

    def test_long_flag_with_equals_and_special_chars(self):
        """Test long flag with special characters in value."""
        cmd = self.parser.parse_simple("command --path=/usr/local/bin")
        self.assertEqual(cmd.flags.get('path'), '/usr/local/bin')

    def test_long_flag_boolean(self):
        """Test long flag without value (boolean)."""
        cmd = self.parser.parse_simple("ls --all --long")
        self.assertEqual(cmd.flags.get('all'), True)
        self.assertEqual(cmd.flags.get('long'), True)


class TestNumericFlags(unittest.TestCase):
    """Test numeric flags for head/tail."""

    def setUp(self):
        """Set up test fixtures."""
        self.parser = CommandParser()

    def test_head_numeric_flag(self):
        """Test head -N syntax."""
        cmd = self.parser.parse_simple("head -20 file.txt")
        self.assertEqual(cmd.name, 'head')
        self.assertEqual(cmd.flags.get('n'), 20)
        self.assertIn('file.txt', cmd.args)

    def test_tail_numeric_flag(self):
        """Test tail -N syntax."""
        cmd = self.parser.parse_simple("tail -5 file.txt")
        self.assertEqual(cmd.name, 'tail')
        self.assertEqual(cmd.flags.get('n'), 5)

    def test_head_with_n_flag_and_value(self):
        """Test head -n N syntax with non-numeric value (should fallback)."""
        cmd = self.parser.parse_simple("head -n abc file.txt")
        # 'abc' should be kept as string since it can't be converted to int
        self.assertEqual(cmd.name, 'head')
        self.assertEqual(cmd.flags.get('lines'), 'abc')


class TestValueFlagParsing(unittest.TestCase):
    """Test value flag parsing."""

    def setUp(self):
        """Set up test fixtures."""
        self.parser = CommandParser()

    def test_cut_delimiter_flag(self):
        """Test cut -d flag with value."""
        cmd = self.parser.parse_simple("cut -d , -f 1 file.csv")
        self.assertEqual(cmd.name, 'cut')
        self.assertEqual(cmd.flags.get('delimiter'), ',')
        self.assertEqual(cmd.flags.get('fields'), '1')

    def test_cut_flag_without_value(self):
        """Test cut -d flag without following value."""
        cmd = self.parser.parse_simple("cut -d")
        # When no value follows, flag becomes boolean
        self.assertEqual(cmd.name, 'cut')
        self.assertEqual(cmd.flags.get('delimiter'), True)

    def test_diff_context_flag(self):
        """Test diff -c flag with value."""
        cmd = self.parser.parse_simple("diff -c 3 file1 file2")
        self.assertEqual(cmd.name, 'diff')
        self.assertEqual(cmd.flags.get('context'), 3)


class TestEmptyAndEdgeCases(unittest.TestCase):
    """Test empty and edge case inputs."""

    def setUp(self):
        """Set up test fixtures."""
        self.parser = CommandParser()

    def test_empty_part_in_sequence(self):
        """Test empty parts in command sequence."""
        group = self.parser.parse("; ls ;")
        # Should handle empty parts gracefully
        self.assertIsNotNone(group)
        # Should have at least one valid pipeline
        valid_pipelines = [p for p, _ in group.pipelines if p.commands]
        self.assertGreater(len(valid_pipelines), 0)

    def test_multiple_operators(self):
        """Test multiple operators in sequence."""
        group = self.parser.parse("echo a && echo b || echo c")
        self.assertEqual(len(group.pipelines), 3)

    def test_operator_at_start(self):
        """Test operator at start of command."""
        group = self.parser.parse("&& echo test")
        # Should handle gracefully
        self.assertIsNotNone(group)

    def test_consecutive_pipes_with_spaces(self):
        """Test pipeline with extra spaces."""
        group = self.parser.parse("ls  |  grep test")
        pipeline = group.pipelines[0][0]
        self.assertEqual(len(pipeline.commands), 2)


class TestRedirectionWithFd(unittest.TestCase):
    """Test redirections with file descriptors."""

    def setUp(self):
        """Set up test fixtures."""
        self.parser = CommandParser()

    def test_stderr_redirect(self):
        """Test stderr redirection (2>)."""
        cmd = self.parser.parse_simple("command 2>error.log")
        self.assertEqual(len(cmd.redirects), 1)
        self.assertEqual(cmd.redirects[0].fd, 2)
        self.assertEqual(cmd.redirects[0].type, RedirectType.WRITE)

    def test_stdin_redirect(self):
        """Test stdin redirection (<)."""
        cmd = self.parser.parse_simple("command <input.txt")
        self.assertEqual(len(cmd.redirects), 1)
        self.assertEqual(cmd.redirects[0].fd, 0)
        self.assertEqual(cmd.redirects[0].type, RedirectType.READ)

    def test_stdout_default_fd(self):
        """Test stdout default file descriptor."""
        cmd = self.parser.parse_simple("echo hello >output.txt")
        self.assertEqual(cmd.redirects[0].fd, 1)


class TestEscapedCharactersInPipeSplit(unittest.TestCase):
    """Test escaped characters in pipe splitting."""

    def setUp(self):
        """Set up test fixtures."""
        self.parser = CommandParser()

    def test_escaped_pipe(self):
        """Test escaped pipe character."""
        result = self.parser._split_by_pipe("echo hello\\|world")
        # The escaped pipe should not split
        self.assertEqual(len(result), 1)

    def test_backslash_at_end(self):
        """Test backslash at end of string."""
        result = self.parser._split_by_pipe("echo test\\")
        self.assertEqual(len(result), 1)


class TestComplexCommands(unittest.TestCase):
    """Test complex command scenarios."""

    def setUp(self):
        """Set up test fixtures."""
        self.parser = CommandParser()

    def test_complex_pipeline_with_redirects(self):
        """Test complex pipeline with multiple redirects."""
        group = self.parser.parse("cat input.txt | grep pattern > output.txt 2>errors.txt")
        pipeline = group.pipelines[0][0]
        self.assertEqual(len(pipeline.commands), 2)
        # Last command should have redirects
        self.assertGreater(len(pipeline.commands[1].redirects), 0)

    def test_chained_conditionals(self):
        """Test chained conditional operators."""
        group = self.parser.parse("test -f file && cat file || echo 'not found'")
        self.assertEqual(len(group.pipelines), 3)
        self.assertEqual(group.pipelines[0][1], '&&')
        self.assertEqual(group.pipelines[1][1], '||')


class TestFlagMappings(unittest.TestCase):
    """Test flag mappings for various commands."""

    def setUp(self):
        """Set up test fixtures."""
        self.parser = CommandParser()

    def test_ls_combined_flags(self):
        """Test ls with combined short flags."""
        cmd = self.parser.parse_simple("ls -latr")
        self.assertEqual(cmd.flags.get('long'), True)
        self.assertEqual(cmd.flags.get('all'), True)
        self.assertEqual(cmd.flags.get('time'), True)
        self.assertEqual(cmd.flags.get('reverse'), True)

    def test_grep_flags(self):
        """Test grep with various flags."""
        cmd = self.parser.parse_simple("grep -inv pattern file")
        self.assertEqual(cmd.flags.get('ignore_case'), True)
        self.assertEqual(cmd.flags.get('line_number'), True)
        self.assertEqual(cmd.flags.get('invert'), True)

    def test_unknown_command_flags(self):
        """Test flags for unknown command."""
        cmd = self.parser.parse_simple("unknowncmd -xyz --verbose")
        # Unknown commands should keep short flags as-is
        self.assertEqual(cmd.flags.get('x'), True)
        self.assertEqual(cmd.flags.get('y'), True)
        self.assertEqual(cmd.flags.get('z'), True)
        self.assertEqual(cmd.flags.get('verbose'), True)


if __name__ == '__main__':
    unittest.main()
