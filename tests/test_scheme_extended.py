#!/usr/bin/env python3
"""
Extended tests for the Scheme interpreter - achieving comprehensive coverage.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import sys
import io
import dagshell.dagshell as dagshell
from dagshell.scheme_interpreter import (
    tokenize, parse, Symbol, evaluate, Environment, Procedure,
    create_global_env, SchemeREPL,
    _append_file, _is_file, _is_directory, _stat_to_list, _get_hash,
    _with_file, _map_directory, _save_fs, _load_fs
)


class TestSymbol:
    """Test Symbol class."""

    def test_symbol_repr(self):
        """Test Symbol string representation."""
        sym = Symbol("test-symbol")
        assert repr(sym) == "test-symbol"
        assert str(sym) == "test-symbol"


class TestEnvironment:
    """Test Environment class."""

    def test_environment_set_undefined(self):
        """Test setting undefined variable."""
        env = Environment()

        # Try to set undefined variable (covers lines 56-61)
        with pytest.raises(NameError, match="Undefined variable: x"):
            env.set('x', 42)

    def test_environment_set_in_parent(self):
        """Test setting variable defined in parent environment."""
        parent = Environment()
        parent.define('x', 10)

        child = Environment(parent=parent)
        child.set('x', 20)

        # Parent should be updated
        assert parent.get('x') == 20

    def test_environment_nested_lookup(self):
        """Test nested environment variable lookup."""
        grandparent = Environment()
        grandparent.define('a', 1)

        parent = Environment(parent=grandparent)
        parent.define('b', 2)

        child = Environment(parent=parent)
        child.define('c', 3)

        # Child can access all
        assert child.get('a') == 1
        assert child.get('b') == 2
        assert child.get('c') == 3

        # Parent cannot access child's variables
        with pytest.raises(NameError):
            parent.get('c')


class TestTokenizerExtended:
    """Extended tests for tokenizer."""

    def test_comments_in_strings(self):
        """Test that semicolons in strings are not treated as comments."""
        code = '(display "This ; is not a comment")'
        tokens = tokenize(code)
        assert tokens == ['(', 'display', '"This ; is not a comment"', ')']

    def test_empty_input(self):
        """Test tokenizing empty input."""
        assert tokenize("") == []
        assert tokenize("   \n  \t  ") == []

    def test_comment_only_input(self):
        """Test input with only comments."""
        code = "; This is a comment\n; Another comment"
        assert tokenize(code) == []

    def test_mixed_comments_and_code(self):
        """Test code with inline and full-line comments."""
        code = """
        ; Define a function
        (define square ; square function
          (lambda (x) (* x x))) ; returns x squared
        """
        tokens = tokenize(code)
        assert '(' in tokens
        assert 'define' in tokens
        assert 'square' in tokens
        assert ';' not in ' '.join(tokens)


class TestParserExtended:
    """Extended tests for parser."""

    def test_parse_empty_list(self):
        """Test parsing empty list."""
        result = parse(tokenize("()"))
        assert result == []

    def test_parse_unexpected_eof(self):
        """Test parse error on unexpected EOF."""
        # Missing closing paren (covers line 144)
        with pytest.raises(SyntaxError, match="Missing closing parenthesis"):
            parse(tokenize("(define x"))

    def test_parse_extra_closing_paren_inline(self):
        """Test parse error on extra closing paren inline."""
        # Extra closing paren in middle (covers line 148)
        with pytest.raises(SyntaxError, match="Unexpected closing parenthesis"):
            parse(['(', 'define', 'x', '42', ')', ')'])

    def test_parse_missing_closing_paren(self):
        """Test missing closing parenthesis error."""
        # Covers line 132
        with pytest.raises(SyntaxError, match="Unexpected EOF"):
            parse([])


class TestEvaluatorExtended:
    """Extended tests for evaluator."""

    def test_evaluate_none(self):
        """Test evaluating None."""
        env = create_global_env()
        assert evaluate(None, env) is None

    def test_evaluate_empty_list(self):
        """Test evaluating empty list."""
        env = create_global_env()
        result = evaluate([], env)
        assert result == []

    def test_quote_special_form(self):
        """Test quote special form."""
        env = create_global_env()

        # Quote with argument (covers line 211)
        result = evaluate(parse(tokenize("(quote (1 2 3))")), env)
        assert result == [1, 2, 3]

        # Quote without argument
        result = evaluate([Symbol('quote')], env)
        assert result is None

    def test_define_errors(self):
        """Test define special form errors."""
        env = create_global_env()

        # Wrong number of arguments (covers line 216)
        with pytest.raises(SyntaxError, match="define requires exactly 2 arguments"):
            evaluate([Symbol('define')], env)

        # Non-symbol name (covers line 219)
        with pytest.raises(SyntaxError, match="First argument to define must be a symbol"):
            evaluate([Symbol('define'), 42, 10], env)

    def test_set_bang(self):
        """Test set! special form."""
        env = create_global_env()

        # Define then set
        evaluate(parse(tokenize("(define x 10)")), env)
        result = evaluate(parse(tokenize("(set! x 20)")), env)
        assert result == 20
        assert env.get('x') == 20

        # Set! errors - wrong number of args (covers line 226-227)
        with pytest.raises(SyntaxError, match="set! requires exactly 2 arguments"):
            evaluate([Symbol('set!')], env)

        # Set! errors - non-symbol (covers line 230)
        with pytest.raises(SyntaxError, match="First argument to set! must be a symbol"):
            evaluate([Symbol('set!'), 42, 10], env)

    def test_lambda_errors(self):
        """Test lambda special form errors."""
        env = create_global_env()

        # Lambda without body (covers line 238)
        with pytest.raises(SyntaxError, match="lambda requires parameters and body"):
            evaluate([Symbol('lambda')], env)

        # Non-list parameters (covers line 241)
        with pytest.raises(SyntaxError, match="Lambda parameters must be a list"):
            evaluate([Symbol('lambda'), Symbol('x'), [Symbol('*'), Symbol('x'), Symbol('x')]], env)

        # Non-symbol parameters (covers line 244)
        with pytest.raises(SyntaxError, match="Lambda parameters must be symbols"):
            evaluate([Symbol('lambda'), [42], [Symbol('+'), 1, 2]], env)

    def test_begin_empty(self):
        """Test begin with no expressions."""
        env = create_global_env()
        result = evaluate([Symbol('begin')], env)
        assert result is None

    def test_let_errors(self):
        """Test let special form errors."""
        env = create_global_env()

        # Let without body (covers line 269)
        with pytest.raises(SyntaxError, match="let requires bindings and body"):
            evaluate([Symbol('let')], env)

        # Let with only bindings, no body
        with pytest.raises(SyntaxError, match="let requires bindings and body"):
            evaluate([Symbol('let'), []], env)

        # Non-list bindings (covers line 272)
        with pytest.raises(SyntaxError, match="let bindings must be a list"):
            evaluate([Symbol('let'), Symbol('x'), [Symbol('+'), 1, 2]], env)

        # Invalid binding format (covers line 277)
        with pytest.raises(SyntaxError, match="Each let binding must be a list of 2 elements"):
            evaluate([Symbol('let'), [[Symbol('x')]], [Symbol('x')]], env)

        # Non-symbol binding name (covers line 280)
        with pytest.raises(SyntaxError, match="Binding name must be a symbol"):
            evaluate([Symbol('let'), [[42, 10]], [Symbol('+'), 1, 2]], env)

    def test_call_non_function(self):
        """Test calling non-function value."""
        env = create_global_env()

        # Try to call a number (covers line 297)
        with pytest.raises(TypeError, match="Cannot call non-function"):
            evaluate([42, 1, 2], env)

    def test_evaluate_unknown_expression(self):
        """Test evaluating unknown expression type."""
        env = create_global_env()

        # Pass an object that's not a known type (covers line 300)
        class UnknownType:
            pass

        with pytest.raises(ValueError, match="Cannot evaluate"):
            evaluate(UnknownType(), env)


class TestProcedure:
    """Test user-defined procedures."""

    def test_procedure_call(self):
        """Test calling user-defined procedure."""
        env = create_global_env()

        # Define a procedure
        proc_expr = parse(tokenize("(lambda (x y) (+ x y))"))
        proc = evaluate(proc_expr, env)

        assert isinstance(proc, Procedure)

        # Call it directly
        result = proc(3, 4)
        assert result == 7

    def test_procedure_closure(self):
        """Test procedure captures lexical environment."""
        env = create_global_env()

        # Define outer variable
        evaluate(parse(tokenize("(define outer 10)")), env)

        # Define procedure that uses outer variable
        evaluate(parse(tokenize("""
            (define add-outer
              (lambda (x) (+ x outer)))
        """)), env)

        # Call procedure
        result = evaluate(parse(tokenize("(add-outer 5)")), env)
        assert result == 15


class TestBuiltinFunctions:
    """Test built-in functions."""

    def test_arithmetic_edge_cases(self):
        """Test arithmetic with edge cases."""
        env = create_global_env()

        # Addition with no args
        result = evaluate(parse(tokenize("(+)")), env)
        assert result == 0

        # Multiplication with no args
        result = evaluate(parse(tokenize("(*)")), env)
        assert result == 1

        # Unary minus
        result = evaluate(parse(tokenize("(- 5)")), env)
        assert result == -5

        # Modulo
        result = evaluate(parse(tokenize("(mod 10 3)")), env)
        assert result == 1

    def test_logical_operations(self):
        """Test logical operations."""
        env = create_global_env()

        assert evaluate(parse(tokenize("(and #t #t)")), env) is True
        assert evaluate(parse(tokenize("(and #t #f)")), env) is False
        assert evaluate(parse(tokenize("(or #f #t)")), env) is True
        assert evaluate(parse(tokenize("(not #f)")), env) is True

    def test_type_predicates(self):
        """Test type predicate functions."""
        env = create_global_env()

        assert evaluate(parse(tokenize('(number? 42)')), env) is True
        assert evaluate(parse(tokenize('(number? "hello")')), env) is False
        assert evaluate(parse(tokenize('(string? "hello")')), env) is True
        assert evaluate(parse(tokenize('(list? (list 1 2 3))')), env) is True
        assert evaluate(parse(tokenize('(symbol? (quote x))')), env) is True
        assert evaluate(parse(tokenize('(procedure? +)')), env) is True

    def test_string_operations(self):
        """Test string manipulation functions."""
        env = create_global_env()

        # String append
        result = evaluate(parse(tokenize('(string-append "hello" " " "world")')), env)
        assert result == "hello world"

        # String length
        result = evaluate(parse(tokenize('(string-length "hello")')), env)
        assert result == 5

        # Substring with end
        result = evaluate(parse(tokenize('(substring "hello" 1 4)')), env)
        assert result == "ell"

        # Substring without end
        result = evaluate(parse(tokenize('(substring "hello" 2)')), env)
        assert result == "llo"

    def test_list_edge_cases(self):
        """Test list operations with edge cases."""
        env = create_global_env()

        # Car/cdr on empty list
        assert evaluate(parse(tokenize("(car (list))")), env) is None
        assert evaluate(parse(tokenize("(cdr (list))")), env) == []

        # Null? predicate
        assert evaluate(parse(tokenize("(null? (list))")), env) is True
        # Test with non-empty list
        assert evaluate(parse(tokenize("(null? (list 1 2))")), env) is False

        # Length of non-list
        assert evaluate(parse(tokenize("(length 42)")), env) == 0


class TestFilesystemHelpers:
    """Test filesystem helper functions."""

    def setup_method(self):
        """Reset filesystem before each test."""
        dagshell._default_fs = None

    def test_append_file(self):
        """Test _append_file helper."""
        fs = dagshell.get_fs()

        # Append to existing file (covers lines 387-390)
        fs.write('/test.txt', 'Hello')
        result = _append_file(fs, '/test.txt', ' World')
        assert result is True
        assert fs.read('/test.txt') == b'Hello World'

        # Append to nonexistent file
        result = _append_file(fs, '/new.txt', 'New content')
        assert result is True
        assert fs.read('/new.txt') == b'New content'

    def test_is_file_helper(self):
        """Test _is_file helper."""
        fs = dagshell.get_fs()

        # Create a file and directory
        fs.write('/file.txt', 'content')
        fs.mkdir('/dir')

        assert _is_file(fs, '/file.txt') is True
        assert _is_file(fs, '/dir') is False
        assert _is_file(fs, '/nonexistent') is False

    def test_is_directory_helper(self):
        """Test _is_directory helper."""
        fs = dagshell.get_fs()

        fs.write('/file.txt', 'content')
        fs.mkdir('/dir')

        assert _is_directory(fs, '/dir') is True
        assert _is_directory(fs, '/file.txt') is False
        assert _is_directory(fs, '/nonexistent') is False

    def test_stat_to_list(self):
        """Test _stat_to_list helper."""
        # Valid stat (covers line 408)
        stat = {
            'type': 'file',
            'mode': 0o644,
            'uid': 1000,
            'gid': 1000,
            'mtime': 1234567890.0,
            'size': 100,
            'hash': 'abc123'
        }
        result = _stat_to_list(stat)
        assert isinstance(result, list)
        assert ['type', 'file'] in result
        assert ['size', 100] in result

        # None stat
        assert _stat_to_list(None) is None

    def test_get_hash_helper(self):
        """Test _get_hash helper."""
        fs = dagshell.get_fs()

        fs.write('/test.txt', 'content')
        hash_val = _get_hash(fs, '/test.txt')
        assert isinstance(hash_val, str)
        assert len(hash_val) == 64  # SHA256 hex

        # Nonexistent file
        assert _get_hash(fs, '/nonexistent') is None

    def test_with_file_helper(self):
        """Test _with_file helper."""
        fs = dagshell.get_fs()

        # Write file using with_file (covers lines 428-432)
        def write_proc(handle):
            return handle.write('test content')

        result = _with_file(fs, '/test.txt', 'w', write_proc)
        assert result == 12  # Length of 'test content'
        assert fs.read('/test.txt') == b'test content'

        # Read file using with_file
        def read_proc(handle):
            return handle.read().decode('utf-8')

        result = _with_file(fs, '/test.txt', 'r', read_proc)
        assert result == 'test content'

        # Nonexistent file
        result = _with_file(fs, '/nonexistent', 'r', read_proc)
        assert result is None

    def test_map_directory(self):
        """Test _map_directory helper."""
        fs = dagshell.get_fs()

        # Create directory with files (covers lines 437-440)
        fs.mkdir('/testdir')
        fs.write('/testdir/file1.txt', 'content1')
        fs.write('/testdir/file2.txt', 'content2')

        # Map uppercase function over entries
        result = _map_directory(fs, str.upper, '/testdir')
        assert result == ['FILE1.TXT', 'FILE2.TXT']

        # Map over nonexistent directory
        result = _map_directory(fs, str.upper, '/nonexistent')
        assert result == []

    def test_save_load_filesystem(self):
        """Test _save_fs and _load_fs helpers."""
        import tempfile
        import os

        # Create a filesystem with content
        fs = dagshell.get_fs()
        fs.mkdir('/data')
        fs.write('/data/file.txt', 'test content')

        # Save to temp file (covers lines 445-451)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name

        try:
            result = _save_fs(fs, temp_path)
            assert result is True

            # Reset and load (covers lines 456-465)
            dagshell._default_fs = dagshell.FileSystem()
            result = _load_fs(temp_path)
            assert result is True

            # Verify content was loaded
            new_fs = dagshell.get_fs()
            assert new_fs.exists('/data/file.txt')
            assert new_fs.read('/data/file.txt') == b'test content'

            # Test loading nonexistent file
            result = _load_fs('/nonexistent/file.json')
            assert result is False

            # Test saving to invalid path
            result = _save_fs(fs, '/invalid/path/file.json')
            assert result is False

        finally:
            os.unlink(temp_path)


class TestSchemeREPL:
    """Test REPL functionality."""

    def test_eval_string(self):
        """Test eval_string method."""
        repl = SchemeREPL()

        # Valid expression (covers line 479)
        result = repl.eval_string("(+ 1 2 3)")
        assert result == 6

        # Empty string
        result = repl.eval_string("")
        assert result is None

        # Whitespace only
        result = repl.eval_string("   \n  ")
        assert result is None

    def test_print_result(self):
        """Test _print_result method."""
        repl = SchemeREPL()

        # Capture output
        import io
        import sys

        old_stdout = sys.stdout
        sys.stdout = captured = io.StringIO()

        try:
            # Boolean (covers lines 520-521)
            repl._print_result(True)
            assert captured.getvalue() == "#t\n"
            captured.truncate(0)
            captured.seek(0)

            repl._print_result(False)
            assert captured.getvalue() == "#f\n"
            captured.truncate(0)
            captured.seek(0)

            # List (covers lines 522-523)
            repl._print_result([1, 2, 3])
            assert "(1 2 3)" in captured.getvalue()
            captured.truncate(0)
            captured.seek(0)

            # Symbol (covers lines 524-525)
            repl._print_result(Symbol('test'))
            assert "'test" in captured.getvalue()
            captured.truncate(0)
            captured.seek(0)

            # Procedure (covers lines 526-527)
            proc = Procedure([], None, Environment())
            repl._print_result(proc)
            assert "#<procedure>" in captured.getvalue()
            captured.truncate(0)
            captured.seek(0)

            # Built-in function (covers lines 528-529)
            repl._print_result(lambda x: x)
            assert "#<built-in>" in captured.getvalue()
            captured.truncate(0)
            captured.seek(0)

            # Other types (covers lines 530-531)
            repl._print_result(42)
            assert "42" in captured.getvalue()

        finally:
            sys.stdout = old_stdout

    def test_list_to_string(self):
        """Test _list_to_string method."""
        repl = SchemeREPL()

        # Nested list (covers lines 535-545)
        result = repl._list_to_string([1, [2, 3], "hello", True, False])
        assert result == '(1 (2 3) "hello" #t #f)'

        # Empty list
        result = repl._list_to_string([])
        assert result == "()"

    def test_show_help(self):
        """Test _show_help method."""
        repl = SchemeREPL()

        # Capture output (covers lines 549-582)
        import io
        import sys

        old_stdout = sys.stdout
        sys.stdout = captured = io.StringIO()

        try:
            result = repl._show_help()
            assert result is None
            output = captured.getvalue()
            assert "Filesystem Operations:" in output
            assert "mkdir" in output
            assert "write-file" in output

        finally:
            sys.stdout = old_stdout


class TestMainFunction:
    """Test main entry point."""

    def test_main_with_file(self, monkeypatch, tmp_path):
        """Test main function with file argument."""
        # Create a test script file (covers lines 587-605)
        script_file = tmp_path / "test_script.scm"
        script_file.write_text('(+ 1 2 3)')

        # Mock sys.argv
        monkeypatch.setattr(sys, 'argv', ['scheme_interpreter.py', str(script_file)])

        # Capture output
        old_stdout = sys.stdout
        sys.stdout = captured = io.StringIO()

        try:
            from dagshell.scheme_interpreter import main

            # Should not raise SystemExit for valid script
            main()

            # Check output
            assert "6" in captured.getvalue()

        except SystemExit:
            pass  # Expected for successful execution
        finally:
            sys.stdout = old_stdout

    def test_main_file_not_found(self, monkeypatch):
        """Test main with nonexistent file."""
        monkeypatch.setattr(sys, 'argv', ['scheme_interpreter.py', '/nonexistent/file.scm'])

        # Capture output
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = sys.stderr = captured = io.StringIO()

        try:
            from dagshell.scheme_interpreter import main
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

    def test_main_script_error(self, monkeypatch, tmp_path):
        """Test main with script that has errors."""
        # Create a script with syntax error
        script_file = tmp_path / "error_script.scm"
        script_file.write_text('(define')  # Missing closing paren

        monkeypatch.setattr(sys, 'argv', ['scheme_interpreter.py', str(script_file)])

        # Capture output
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = sys.stderr = captured = io.StringIO()

        try:
            from dagshell.scheme_interpreter import main
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr


class TestREPLInteractive:
    """Test interactive REPL features."""

    def test_repl_help_and_exit_functions(self):
        """Test that help and exit are defined in REPL."""
        repl = SchemeREPL()

        # The help and exit functions are defined in run() method,
        # not in __init__, so we need to check the base environment
        # has the other built-in functions
        assert '+' in repl.env.bindings
        assert 'define' not in repl.env.bindings  # Special form, not in bindings

        # Verify we can define help manually
        repl.env.define('help', lambda: None)
        assert 'help' in repl.env.bindings

    def test_repl_history(self):
        """Test REPL history tracking."""
        repl = SchemeREPL()

        # Evaluate some expressions
        repl.eval_string("(+ 1 2)")
        repl.eval_string("(* 3 4)")

        # History should be empty (tracking happens in run() method)
        assert repl.history == []


class TestIntegrationExtended:
    """Extended integration tests."""

    def test_complex_recursive_functions(self):
        """Test complex recursive function definitions."""
        repl = SchemeREPL()

        # Fibonacci
        repl.eval_string("""
            (define fib
              (lambda (n)
                (if (<= n 1)
                    n
                    (+ (fib (- n 1)) (fib (- n 2))))))
        """)

        assert repl.eval_string("(fib 0)") == 0
        assert repl.eval_string("(fib 1)") == 1
        assert repl.eval_string("(fib 5)") == 5
        assert repl.eval_string("(fib 10)") == 55

    def test_filesystem_script_with_errors(self):
        """Test filesystem operations with error handling."""
        repl = SchemeREPL()

        # Try to write to nonexistent directory
        result = repl.eval_string('(write-file "/nonexistent/file.txt" "content")')
        assert result is False

        # Try to list a file as directory
        repl.eval_string('(write-file "/file.txt" "content")')
        result = repl.eval_string('(ls "/file.txt")')
        assert result is None

        # Try to read nonexistent file
        result = repl.eval_string('(read-file "/nonexistent.txt")')
        assert result is None

    def test_io_operations(self):
        """Test I/O operations."""
        repl = SchemeREPL()

        # Capture display output
        old_stdout = sys.stdout
        sys.stdout = captured = io.StringIO()

        try:
            repl.eval_string('(display "Hello, World!")')
            assert captured.getvalue() == "Hello, World!"
            captured.truncate(0)
            captured.seek(0)

            repl.eval_string('(newline)')
            assert captured.getvalue() == "\n"

        finally:
            sys.stdout = old_stdout


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--cov=scheme_interpreter', '--cov-report=term-missing'])