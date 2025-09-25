#!/usr/bin/env python3
"""
Test suite for the Scheme interpreter.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import dagshell.dagshell as dagshell
from dagshell.scheme_interpreter import (
    tokenize, parse, Symbol, evaluate, Environment,
    create_global_env, SchemeREPL, Procedure
)


class TestTokenizer:
    """Test tokenization of Scheme code."""

    def test_simple_tokens(self):
        """Test basic tokenization."""
        assert tokenize("(+ 1 2)") == ['(', '+', '1', '2', ')']
        assert tokenize("(define x 42)") == ['(', 'define', 'x', '42', ')']

    def test_nested_expressions(self):
        """Test nested parentheses."""
        assert tokenize("(+ (* 2 3) 4)") == ['(', '+', '(', '*', '2', '3', ')', '4', ')']

    def test_string_literals(self):
        """Test string literal handling."""
        assert tokenize('(display "hello world")') == ['(', 'display', '"hello world"', ')']
        assert tokenize('(write-file "/path" "content")') == [
            '(', 'write-file', '"/path"', '"content"', ')'
        ]

    def test_whitespace_handling(self):
        """Test various whitespace scenarios."""
        code = """
        (define factorial
          (lambda (n)
            (if (= n 0)
                1
                (* n (factorial (- n 1))))))
        """
        tokens = tokenize(code)
        assert tokens[0] == '('
        assert tokens[1] == 'define'
        assert tokens[2] == 'factorial'


class TestParser:
    """Test parsing of tokenized code."""

    def test_parse_atoms(self):
        """Test parsing of atomic values."""
        assert parse(tokenize("42")) == 42
        assert parse(tokenize("3.14")) == 3.14
        assert parse(tokenize('"hello"')) == "hello"
        assert parse(tokenize("#t")) is True
        assert parse(tokenize("#f")) is False
        assert parse(tokenize("foo")) == Symbol("foo")

    def test_parse_lists(self):
        """Test parsing of lists."""
        result = parse(tokenize("(+ 1 2)"))
        assert isinstance(result, list)
        assert result[0] == Symbol('+')
        assert result[1] == 1
        assert result[2] == 2

    def test_parse_nested(self):
        """Test parsing of nested expressions."""
        result = parse(tokenize("(+ (* 2 3) 4)"))
        assert isinstance(result, list)
        assert result[0] == Symbol('+')
        assert isinstance(result[1], list)
        assert result[1][0] == Symbol('*')
        assert result[2] == 4


class TestEvaluator:
    """Test expression evaluation."""

    def test_arithmetic(self):
        """Test arithmetic operations."""
        env = create_global_env()
        assert evaluate(parse(tokenize("(+ 1 2 3)")), env) == 6
        assert evaluate(parse(tokenize("(* 2 3 4)")), env) == 24
        assert evaluate(parse(tokenize("(- 10 3)")), env) == 7
        assert evaluate(parse(tokenize("(/ 10 2)")), env) == 5.0

    def test_comparison(self):
        """Test comparison operations."""
        env = create_global_env()
        assert evaluate(parse(tokenize("(= 5 5)")), env) is True
        assert evaluate(parse(tokenize("(< 3 5)")), env) is True
        assert evaluate(parse(tokenize("(> 3 5)")), env) is False

    def test_define_and_reference(self):
        """Test variable definition and reference."""
        env = create_global_env()
        evaluate(parse(tokenize('(define x 42)')), env)
        assert evaluate(Symbol('x'), env) == 42

        evaluate(parse(tokenize('(define y (+ x 8))')), env)
        assert evaluate(Symbol('y'), env) == 50

    def test_lambda(self):
        """Test lambda expressions."""
        env = create_global_env()

        # Simple lambda
        evaluate(parse(tokenize('(define square (lambda (x) (* x x)))')), env)
        result = evaluate(parse(tokenize('(square 5)')), env)
        assert result == 25

        # Lambda with multiple params
        evaluate(parse(tokenize('(define add (lambda (a b) (+ a b)))')), env)
        result = evaluate(parse(tokenize('(add 3 4)')), env)
        assert result == 7

    def test_if_expression(self):
        """Test conditional expressions."""
        env = create_global_env()

        # True branch
        result = evaluate(parse(tokenize('(if #t 1 2)')), env)
        assert result == 1

        # False branch
        result = evaluate(parse(tokenize('(if #f 1 2)')), env)
        assert result == 2

        # Without else branch
        result = evaluate(parse(tokenize('(if #f 1)')), env)
        assert result is None

    def test_let_expression(self):
        """Test let bindings."""
        env = create_global_env()

        # Simple let
        result = evaluate(parse(tokenize('(let ((x 5) (y 10)) (+ x y))')), env)
        assert result == 15

        # Nested let
        code = '''
        (let ((x 5))
          (let ((y (+ x 3)))
            (* x y)))
        '''
        result = evaluate(parse(tokenize(code)), env)
        assert result == 40

    def test_list_operations(self):
        """Test list manipulation."""
        env = create_global_env()

        result = evaluate(parse(tokenize('(list 1 2 3)')), env)
        assert result == [1, 2, 3]

        result = evaluate(parse(tokenize('(car (list 1 2 3))')), env)
        assert result == 1

        result = evaluate(parse(tokenize('(cdr (list 1 2 3))')), env)
        assert result == [2, 3]

        result = evaluate(parse(tokenize('(cons 0 (list 1 2 3))')), env)
        assert result == [0, 1, 2, 3]


class TestFilesystemIntegration:
    """Test Scheme filesystem operations."""

    def setup_method(self):
        """Reset filesystem before each test."""
        dagshell._default_fs = None

    def test_mkdir_and_ls(self):
        """Test directory creation and listing."""
        repl = SchemeREPL()

        # Create directory
        result = repl.eval_string('(mkdir "/test")')
        assert result is True

        # List root
        result = repl.eval_string('(ls "/")')
        assert 'test' in result

    def test_file_operations(self):
        """Test file read/write operations."""
        repl = SchemeREPL()

        # Create directory
        repl.eval_string('(mkdir "/data")')

        # Write file
        result = repl.eval_string('(write-file "/data/test.txt" "Hello Scheme!")')
        assert result is True

        # Read file
        result = repl.eval_string('(read-file "/data/test.txt")')
        assert result == "Hello Scheme!"

        # Check existence
        result = repl.eval_string('(exists? "/data/test.txt")')
        assert result is True

        # Check file type
        result = repl.eval_string('(file? "/data/test.txt")')
        assert result is True

        result = repl.eval_string('(directory? "/data")')
        assert result is True

    def test_stat_operation(self):
        """Test file statistics."""
        repl = SchemeREPL()

        repl.eval_string('(mkdir "/test")')
        repl.eval_string('(write-file "/test/file.txt" "content")')

        result = repl.eval_string('(stat "/test/file.txt")')
        assert isinstance(result, list)

        # Check stat structure
        stat_dict = {item[0]: item[1] for item in result}
        assert stat_dict['type'] == 'file'
        assert stat_dict['size'] == 7  # len("content")
        assert 'hash' in stat_dict

    def test_hash_operation(self):
        """Test content hash retrieval."""
        repl = SchemeREPL()

        repl.eval_string('(write-file "/test.txt" "test content")')
        hash1 = repl.eval_string('(get-hash "/test.txt")')
        assert isinstance(hash1, str)
        assert len(hash1) == 64  # SHA256 hex length

        # Same content should have same hash
        repl.eval_string('(write-file "/test2.txt" "test content")')
        hash2 = repl.eval_string('(get-hash "/test2.txt")')

        # Note: hashes will differ due to mtime, but both should be valid
        assert isinstance(hash2, str)
        assert len(hash2) == 64

    def test_rm_and_purge(self):
        """Test deletion and garbage collection."""
        repl = SchemeREPL()

        # Create and delete
        repl.eval_string('(mkdir "/temp")')
        repl.eval_string('(write-file "/temp/file.txt" "temporary")')

        result = repl.eval_string('(rm "/temp/file.txt")')
        assert result is True

        result = repl.eval_string('(exists? "/temp/file.txt")')
        assert result is False

        # Purge should remove unreferenced nodes
        result = repl.eval_string('(purge)')
        assert isinstance(result, int)


class TestAdvancedFeatures:
    """Test advanced Scheme features."""

    def test_recursive_function(self):
        """Test recursive function definition."""
        repl = SchemeREPL()

        # Define factorial
        repl.eval_string('''
        (define factorial
          (lambda (n)
            (if (= n 0)
                1
                (* n (factorial (- n 1))))))
        ''')

        assert repl.eval_string('(factorial 5)') == 120
        assert repl.eval_string('(factorial 0)') == 1

    def test_higher_order_functions(self):
        """Test functions that take/return functions."""
        repl = SchemeREPL()

        # Define compose
        repl.eval_string('''
        (define compose
          (lambda (f g)
            (lambda (x) (f (g x)))))
        ''')

        # Define simple functions
        repl.eval_string('(define add1 (lambda (x) (+ x 1)))')
        repl.eval_string('(define double (lambda (x) (* x 2)))')

        # Compose them
        repl.eval_string('(define add1-then-double (compose double add1))')
        result = repl.eval_string('(add1-then-double 5)')
        assert result == 12  # (5 + 1) * 2

    def test_complex_filesystem_script(self):
        """Test a complex filesystem manipulation script."""
        repl = SchemeREPL()

        script = '''
        (begin
          ;; Create directory structure
          (mkdir "/project")
          (mkdir "/project/src")
          (mkdir "/project/test")

          ;; Create some files
          (write-file "/project/README.md" "# Project")
          (write-file "/project/src/main.py" "print('hello')")
          (write-file "/project/test/test_main.py" "assert True")

          ;; Count files
          (define count-files
            (lambda (dir)
              (length (ls dir))))

          (list
            (count-files "/project")
            (count-files "/project/src")
            (exists? "/project/README.md")))
        '''

        result = repl.eval_string(script)
        assert result == [3, 1, True]  # 3 items in /project, 1 in src, README exists


class TestErrorHandling:
    """Test error conditions and handling."""

    def test_undefined_variable(self):
        """Test undefined variable error."""
        env = create_global_env()
        with pytest.raises(NameError):
            evaluate(Symbol('undefined'), env)

    def test_syntax_errors(self):
        """Test various syntax errors."""
        env = create_global_env()

        # Missing closing paren
        with pytest.raises(SyntaxError):
            parse(tokenize("(+ 1 2"))

        # Extra closing paren
        with pytest.raises(SyntaxError):
            parse(tokenize("(+ 1 2))"))

        # Invalid define
        with pytest.raises(SyntaxError):
            evaluate(parse(tokenize("(define)")), env)

    def test_type_errors(self):
        """Test type errors in operations."""
        env = create_global_env()

        # Cannot call non-function
        with pytest.raises(TypeError):
            evaluate(parse(tokenize("(42 1 2)")), env)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])