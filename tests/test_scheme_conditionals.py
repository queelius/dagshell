#!/usr/bin/env python3
"""
Comprehensive tests for Scheme conditional expressions.

Tests the new conditional features added to the Scheme interpreter:
cond, and, or, try/catch
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from dagshell.scheme_interpreter import (
    evaluate, Environment, create_global_env, Symbol, tokenize, parse
)


@pytest.fixture
def env():
    """Create a global environment for each test."""
    return create_global_env()


class TestCondExpression:
    """Test cond (multi-way conditional) expressions."""

    def test_cond_first_true_clause(self, env):
        """Given multiple cond clauses, when first is true, then only first body executes."""
        code = '(cond ((> 5 3) "first") ((< 5 3) "second") (else "third"))'
        result = evaluate(parse(tokenize(code)), env)
        assert result == 'first'

    def test_cond_second_clause_executes(self, env):
        """Given multiple cond clauses, when first is false but second is true, then second executes."""
        code = '(cond ((> 2 5) "wrong") ((< 2 5) "correct") (else "also-wrong"))'
        result = evaluate(parse(tokenize(code)), env)
        assert result == 'correct'

    def test_cond_else_clause(self, env):
        """Given cond with else, when no clause matches, then else executes."""
        code = '(cond ((> 2 5) "wrong") ((< 5 2) "also-wrong") (else "correct"))'
        result = evaluate(parse(tokenize(code)), env)
        assert result == 'correct'

    def test_cond_no_matching_clause(self, env):
        """Given cond without else, when no clause matches, then returns None."""
        code = '(cond ((> 2 5) "wrong") ((< 5 2) "also-wrong"))'
        result = evaluate(parse(tokenize(code)), env)
        assert result is None

    def test_cond_evaluates_consequent(self, env):
        """Given cond clause, when test is true, then consequent is evaluated."""
        # Set up environment with variable
        env.define('x', 10)
        code = "(cond ((> x 5) (+ x 5)) (else 0))"
        result = evaluate(parse(tokenize(code)), env)
        assert result == 15

    def test_cond_with_complex_test(self, env):
        """Given cond with complex test expression, when evaluated, then works correctly."""
        code = '(cond ((and (> 5 3) (< 2 4)) "both-true") (else "false"))'
        result = evaluate(parse(tokenize(code)), env)
        assert result == 'both-true'

    def test_cond_requires_at_least_one_clause(self, env):
        """Given cond with no clauses, when evaluated, then raises SyntaxError."""
        with pytest.raises(SyntaxError, match="cond requires at least one clause"):
            code = "(cond)"
            evaluate(parse(tokenize(code)), env)

    def test_cond_clause_must_be_list(self, env):
        """Given cond with non-list clause, when evaluated, then raises SyntaxError."""
        with pytest.raises(SyntaxError, match="Each cond clause must be a list"):
            code = "(cond not-a-list)"
            evaluate(parse(tokenize(code)), env)

    def test_cond_short_circuit_evaluation(self, env):
        """Given cond clauses, when first matches, then later clauses are not evaluated."""
        # If second clause were evaluated, it would cause an error (division by zero)
        # But it should not be evaluated because first clause matches
        code = '(cond (#t "first") ((/ 1 0) "should-not-evaluate"))'
        result = evaluate(parse(tokenize(code)), env)
        assert result == 'first'


class TestAndExpression:
    """Test and (logical conjunction) expressions."""

    def test_and_all_true(self, env):
        """Given and with all true values, when evaluated, then returns last value."""
        code = "(and #t #t #t)"
        result = evaluate(parse(tokenize(code)), env)
        assert result is True

    def test_and_with_false(self, env):
        """Given and with false value, when evaluated, then returns False."""
        code = "(and #t #f #t)"
        result = evaluate(parse(tokenize(code)), env)
        assert result is False

    def test_and_short_circuit(self, env):
        """Given and expression, when first is false, then later expressions don't evaluate."""
        # This would error if it evaluated the division by zero
        code = "(and #f (/ 1 0))"
        result = evaluate(parse(tokenize(code)), env)
        assert result is False

    def test_and_with_expressions(self, env):
        """Given and with comparison expressions, when all true, then returns last result."""
        code = "(and (> 5 3) (< 2 4) (= 3 3))"
        result = evaluate(parse(tokenize(code)), env)
        assert result is True

    def test_and_empty(self, env):
        """Given and with no arguments, when evaluated, then returns True."""
        code = "(and)"
        result = evaluate(parse(tokenize(code)), env)
        assert result is True

    def test_and_single_argument(self, env):
        """Given and with single argument, when evaluated, then returns that argument."""
        code = "(and 42)"
        result = evaluate(parse(tokenize(code)), env)
        assert result == 42

    def test_and_with_variable(self, env):
        """Given and with variables, when evaluated, then works correctly."""
        env.define('x', 10)
        env.define('y', 20)
        code = "(and (> x 5) (< y 30))"
        result = evaluate(parse(tokenize(code)), env)
        assert result is True


class TestOrExpression:
    """Test or (logical disjunction) expressions."""

    def test_or_first_true(self, env):
        """Given or with first value true, when evaluated, then returns first value."""
        code = "(or #t #f #f)"
        result = evaluate(parse(tokenize(code)), env)
        assert result is True

    def test_or_all_false(self, env):
        """Given or with all false values, when evaluated, then returns False."""
        code = "(or #f #f #f)"
        result = evaluate(parse(tokenize(code)), env)
        assert result is False

    def test_or_returns_first_truthy(self, env):
        """Given or expression, when first is truthy, then returns first without evaluating rest."""
        code = "(or 42 (/ 1 0))"
        result = evaluate(parse(tokenize(code)), env)
        assert result == 42

    def test_or_with_expressions(self, env):
        """Given or with comparison expressions, when one is true, then returns that result."""
        code = "(or (> 2 5) (< 2 4) (= 3 5))"
        result = evaluate(parse(tokenize(code)), env)
        assert result is True

    def test_or_empty(self, env):
        """Given or with no arguments, when evaluated, then returns False."""
        code = "(or)"
        result = evaluate(parse(tokenize(code)), env)
        assert result is False

    def test_or_single_argument(self, env):
        """Given or with single argument, when evaluated, then returns that argument."""
        code = "(or 42)"
        result = evaluate(parse(tokenize(code)), env)
        assert result == 42

    def test_or_with_number_values(self, env):
        """Given or with number values, when evaluated, then first truthy value is returned."""
        # Note: In Scheme, only #f is false, everything else (including 0) is truthy
        code = "(or 0 42)"
        result = evaluate(parse(tokenize(code)), env)
        # 0 is truthy, so it should return 0
        assert result == 0


class TestTryExpression:
    """Test try/catch (error handling) expressions."""

    def test_try_without_error(self, env):
        """Given try/catch, when no error occurs, then returns normal result."""
        code = '(try (+ 1 2) (catch "error"))'
        result = evaluate(parse(tokenize(code)), env)
        assert result == 3

    def test_try_catch_on_error(self, env):
        """Given try/catch, when error occurs, then catch handler executes."""
        code = '(try (/ 1 0) (catch "recovered"))'
        result = evaluate(parse(tokenize(code)), env)
        assert result == 'recovered'

    def test_try_catch_with_undefined_variable(self, env):
        """Given try/catch, when undefined variable is accessed, then catch handler executes."""
        code = '(try undefined-var (catch "caught-error"))'
        result = evaluate(parse(tokenize(code)), env)
        assert result == 'caught-error'

    def test_try_without_catch(self, env):
        """Given try without catch, when no error, then returns result."""
        code = "(try (+ 5 10))"
        result = evaluate(parse(tokenize(code)), env)
        assert result == 15

    def test_try_without_catch_on_error(self, env):
        """Given try without catch, when error occurs, then returns False."""
        # Based on the implementation, try without catch returns False on error
        code = "(try (/ 1 0))"
        result = evaluate(parse(tokenize(code)), env)
        assert result is False

    def test_try_catch_evaluates_catch_body(self, env):
        """Given try/catch, when error occurs, then catch body is evaluated."""
        code = "(try (/ 1 0) (catch (+ 10 5)))"
        result = evaluate(parse(tokenize(code)), env)
        assert result == 15

    def test_try_requires_expression(self, env):
        """Given try with no expression, when evaluated, then raises SyntaxError."""
        with pytest.raises(SyntaxError, match="try requires an expression"):
            code = "(try)"
            evaluate(parse(tokenize(code)), env)


class TestConditionalIntegration:
    """Test integration of multiple conditional features."""

    def test_nested_cond_in_and(self, env):
        """Given nested cond inside and, when evaluated, then works correctly."""
        code = "(and (cond ((> 5 3) #t) (else #f)) (cond ((< 2 4) #t) (else #f)))"
        result = evaluate(parse(tokenize(code)), env)
        assert result is True

    def test_try_with_cond(self, env):
        """Given try with cond inside, when evaluated, then works correctly."""
        code = '(try (cond ((> 5 3) "correct") (else "wrong")) (catch "error"))'
        result = evaluate(parse(tokenize(code)), env)
        assert result == 'correct'

    def test_and_or_combination(self, env):
        """Given and/or combination, when evaluated, then short-circuits correctly."""
        code = "(or (and #f (/ 1 0)) (and #t #t))"
        result = evaluate(parse(tokenize(code)), env)
        assert result is True

    def test_complex_nested_conditionals(self, env):
        """Given complex nested conditionals, when evaluated, then produces correct result."""
        env.define('x', 10)
        code = '(cond ((and (> x 5) (or (= x 10) (= x 20))) "match") (else "no-match"))'
        result = evaluate(parse(tokenize(code)), env)
        assert result == 'match'


class TestConditionalParsing:
    """Test parsing of conditional expressions from text."""

    def test_parse_cond_from_text(self, env):
        """Given cond expression as text, when parsed and evaluated, then works correctly."""
        code = '(cond ((> 5 3) "first") (else "second"))'
        tokens = tokenize(code)
        expr = parse(tokens)
        result = evaluate(expr, env)
        assert result == 'first'

    def test_parse_and_from_text(self, env):
        """Given and expression as text, when parsed and evaluated, then works correctly."""
        code = "(and (> 5 3) (< 2 4))"
        tokens = tokenize(code)
        expr = parse(tokens)
        result = evaluate(expr, env)
        assert result is True

    def test_parse_or_from_text(self, env):
        """Given or expression as text, when parsed and evaluated, then works correctly."""
        code = "(or (> 2 5) (< 2 4))"
        tokens = tokenize(code)
        expr = parse(tokens)
        result = evaluate(expr, env)
        assert result is True

    def test_parse_try_from_text(self, env):
        """Given try expression as text, when parsed and evaluated, then works correctly."""
        code = '(try (/ 1 0) (catch "error"))'
        tokens = tokenize(code)
        expr = parse(tokens)
        result = evaluate(expr, env)
        assert result == 'error'
