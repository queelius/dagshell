#!/usr/bin/env python3
"""
Scheme-like DSL for dagshell.

A minimal, elegant Scheme interpreter for filesystem operations.
Following the principle of simplicity and composability.
"""

import re
import sys
from typing import Any, List, Dict, Callable, Optional, Union
from dataclasses import dataclass
from functools import reduce
import operator

import dagshell


@dataclass
class Symbol:
    """Represents a Scheme symbol."""
    name: str

    def __repr__(self):
        return self.name


@dataclass
class Procedure:
    """Represents a user-defined procedure."""
    params: List[Symbol]
    body: Any
    env: 'Environment'

    def __call__(self, *args):
        """Execute the procedure with given arguments."""
        local_env = Environment(parent=self.env)
        for param, arg in zip(self.params, args):
            local_env.define(param.name, arg)
        return evaluate(self.body, local_env)


class Environment:
    """Lexical environment for variable bindings."""

    def __init__(self, parent: Optional['Environment'] = None):
        self.bindings: Dict[str, Any] = {}
        self.parent = parent

    def define(self, name: str, value: Any):
        """Define a new binding in this environment."""
        self.bindings[name] = value

    def set(self, name: str, value: Any):
        """Update an existing binding."""
        if name in self.bindings:
            self.bindings[name] = value
        elif self.parent:
            self.parent.set(name, value)
        else:
            raise NameError(f"Undefined variable: {name}")

    def get(self, name: str) -> Any:
        """Look up a binding."""
        if name in self.bindings:
            return self.bindings[name]
        elif self.parent:
            return self.parent.get(name)
        else:
            raise NameError(f"Undefined variable: {name}")


def tokenize(text: str) -> List[str]:
    """Convert Scheme code into tokens."""
    # Remove comments first
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        # Find semicolon not in string
        in_string = False
        for i, char in enumerate(line):
            if char == '"' and (i == 0 or line[i-1] != '\\'):
                in_string = not in_string
            elif char == ';' and not in_string:
                line = line[:i]
                break
        cleaned_lines.append(line)
    text = '\n'.join(cleaned_lines)

    # Add spaces around parentheses for easier splitting
    text = text.replace('(', ' ( ').replace(')', ' ) ')
    # Handle string literals properly
    tokens = []
    in_string = False
    current = []

    for char in text:
        if char == '"' and (not current or current[-1] != '\\'):
            in_string = not in_string
            current.append(char)
        elif in_string:
            current.append(char)
        elif char.isspace():
            if current:
                tokens.append(''.join(current))
                current = []
        else:
            current.append(char)

    if current:
        tokens.append(''.join(current))

    # Now split non-string tokens on whitespace
    result = []
    for token in tokens:
        if token.startswith('"'):
            result.append(token)
        else:
            result.extend(token.split())

    return [t for t in result if t]


def parse(tokens: List[str]) -> Any:
    """Parse tokens into S-expressions."""
    if not tokens:
        raise SyntaxError("Unexpected EOF")

    def parse_expr(tokens: List[str], idx: int) -> tuple[Any, int]:
        """Parse a single expression and return it with the next index."""
        if idx >= len(tokens):
            raise SyntaxError("Unexpected EOF")

        token = tokens[idx]

        if token == '(':
            # Parse list
            lst = []
            idx += 1
            while idx < len(tokens) and tokens[idx] != ')':
                expr, idx = parse_expr(tokens, idx)
                lst.append(expr)
            if idx >= len(tokens):
                raise SyntaxError("Missing closing parenthesis")
            return lst, idx + 1

        elif token == ')':
            raise SyntaxError("Unexpected closing parenthesis")

        else:
            # Parse atom
            return parse_atom(token), idx + 1

    expr, next_idx = parse_expr(tokens, 0)

    # Check for extra tokens (like extra closing parens)
    if next_idx < len(tokens):
        if tokens[next_idx] == ')':
            raise SyntaxError("Unexpected closing parenthesis")

    return expr


def parse_atom(token: str) -> Any:
    """Parse an atomic token."""
    # String literal
    if token.startswith('"') and token.endswith('"'):
        return token[1:-1]  # Remove quotes

    # Number
    try:
        if '.' in token:
            return float(token)
        return int(token)
    except ValueError:
        pass

    # Boolean
    if token == '#t':
        return True
    if token == '#f':
        return False

    # Symbol
    return Symbol(token)


def evaluate(expr: Any, env: Environment) -> Any:
    """Evaluate an expression in an environment."""

    # Self-evaluating expressions
    if isinstance(expr, (int, float, str, bool, type(None))):
        return expr

    # Variable reference
    if isinstance(expr, Symbol):
        return env.get(expr.name)

    # Lists (function calls or special forms)
    if isinstance(expr, list):
        if not expr:
            return []

        # Get the operator
        op = expr[0]

        # Special forms
        if isinstance(op, Symbol):
            # Quote
            if op.name == 'quote':
                return expr[1] if len(expr) > 1 else None

            # Define
            if op.name == 'define':
                if len(expr) != 3:
                    raise SyntaxError("define requires exactly 2 arguments")
                name = expr[1]
                if not isinstance(name, Symbol):
                    raise SyntaxError("First argument to define must be a symbol")
                value = evaluate(expr[2], env)
                env.define(name.name, value)
                return value

            # Set!
            if op.name == 'set!':
                if len(expr) != 3:
                    raise SyntaxError("set! requires exactly 2 arguments")
                name = expr[1]
                if not isinstance(name, Symbol):
                    raise SyntaxError("First argument to set! must be a symbol")
                value = evaluate(expr[2], env)
                env.set(name.name, value)
                return value

            # Lambda
            if op.name == 'lambda':
                if len(expr) < 3:
                    raise SyntaxError("lambda requires parameters and body")
                params = expr[1]
                if not isinstance(params, list):
                    raise SyntaxError("Lambda parameters must be a list")
                for p in params:
                    if not isinstance(p, Symbol):
                        raise SyntaxError("Lambda parameters must be symbols")
                body = expr[2] if len(expr) == 3 else [Symbol('begin')] + expr[2:]
                return Procedure(params, body, env)

            # If
            if op.name == 'if':
                if len(expr) not in [3, 4]:
                    raise SyntaxError("if requires 2 or 3 arguments")
                condition = evaluate(expr[1], env)
                if condition:
                    return evaluate(expr[2], env)
                elif len(expr) == 4:
                    return evaluate(expr[3], env)
                return None

            # Begin
            if op.name == 'begin':
                result = None
                for e in expr[1:]:
                    result = evaluate(e, env)
                return result

            # Let
            if op.name == 'let':
                if len(expr) < 3:
                    raise SyntaxError("let requires bindings and body")
                bindings = expr[1]
                if not isinstance(bindings, list):
                    raise SyntaxError("let bindings must be a list")

                local_env = Environment(parent=env)
                for binding in bindings:
                    if not isinstance(binding, list) or len(binding) != 2:
                        raise SyntaxError("Each let binding must be a list of 2 elements")
                    name = binding[0]
                    if not isinstance(name, Symbol):
                        raise SyntaxError("Binding name must be a symbol")
                    value = evaluate(binding[1], env)
                    local_env.define(name.name, value)

                # Evaluate body in local environment
                result = None
                for body_expr in expr[2:]:
                    result = evaluate(body_expr, local_env)
                return result

        # Function application
        func = evaluate(op, env)
        args = [evaluate(arg, env) for arg in expr[1:]]

        if callable(func):
            return func(*args)
        else:
            raise TypeError(f"Cannot call non-function: {func}")

    # Unknown expression type
    raise ValueError(f"Cannot evaluate: {expr}")


def create_global_env() -> Environment:
    """Create the global environment with built-in functions."""
    env = Environment()

    # Arithmetic operations
    env.define('+', lambda *args: sum(args))
    env.define('-', lambda x, y=None: -x if y is None else x - y)
    env.define('*', lambda *args: reduce(operator.mul, args, 1))
    env.define('/', lambda x, y: x / y)
    env.define('mod', lambda x, y: x % y)

    # Comparison operations
    env.define('=', lambda x, y: x == y)
    env.define('<', lambda x, y: x < y)
    env.define('>', lambda x, y: x > y)
    env.define('<=', lambda x, y: x <= y)
    env.define('>=', lambda x, y: x >= y)

    # Logical operations
    env.define('and', lambda x, y: x and y)
    env.define('or', lambda x, y: x or y)
    env.define('not', lambda x: not x)

    # List operations
    env.define('list', lambda *args: list(args))
    env.define('car', lambda lst: lst[0] if lst else None)
    env.define('cdr', lambda lst: lst[1:] if lst else [])
    env.define('cons', lambda x, lst: [x] + (lst if isinstance(lst, list) else [lst]))
    env.define('null?', lambda lst: lst == [] or lst is None)
    env.define('length', lambda lst: len(lst) if isinstance(lst, list) else 0)

    # Type predicates
    env.define('number?', lambda x: isinstance(x, (int, float)))
    env.define('string?', lambda x: isinstance(x, str))
    env.define('list?', lambda x: isinstance(x, list))
    env.define('symbol?', lambda x: isinstance(x, Symbol))
    env.define('procedure?', lambda x: callable(x))

    # String operations
    env.define('string-append', lambda *args: ''.join(str(a) for a in args))
    env.define('string-length', lambda s: len(s))
    env.define('substring', lambda s, start, end=None: s[start:end])

    # I/O operations
    env.define('display', lambda x: print(x, end=''))
    env.define('newline', lambda: print())
    env.define('read-line', lambda: input())

    # Filesystem operations - the heart of dagshell
    fs = dagshell.get_fs()

    # File operations
    env.define('read-file', lambda path: fs.read(path).decode('utf-8') if fs.read(path) else None)
    env.define('write-file', lambda path, content: fs.write(path, content))
    env.define('append-file', lambda path, content: _append_file(fs, path, content))
    env.define('exists?', lambda path: fs.exists(path))
    env.define('file?', lambda path: _is_file(fs, path))
    env.define('directory?', lambda path: _is_directory(fs, path))

    # Directory operations
    env.define('mkdir', lambda path: fs.mkdir(path))
    env.define('ls', lambda path='/': fs.ls(path))
    env.define('rm', lambda path: fs.rm(path))
    env.define('purge', lambda: fs.purge())

    # Metadata operations
    env.define('stat', lambda path: _stat_to_list(fs.stat(path)))
    env.define('get-hash', lambda path: _get_hash(fs, path))

    # Advanced operations
    env.define('with-file', lambda path, mode, proc: _with_file(fs, path, mode, proc))
    env.define('map-directory', lambda proc, path='/': _map_directory(fs, proc, path))

    # Serialization
    env.define('save-filesystem', lambda path: _save_fs(fs, path))
    env.define('load-filesystem', lambda path: _load_fs(path))

    return env


# Helper functions for filesystem operations

def _append_file(fs, path: str, content: str) -> bool:
    """Append content to a file."""
    existing = fs.read(path)
    if existing is not None:
        return fs.write(path, existing + content.encode('utf-8'))
    return fs.write(path, content)


def _is_file(fs, path: str) -> bool:
    """Check if path is a regular file."""
    stat = fs.stat(path)
    return stat is not None and stat['type'] == 'file'


def _is_directory(fs, path: str) -> bool:
    """Check if path is a directory."""
    stat = fs.stat(path)
    return stat is not None and stat['type'] == 'dir'


def _stat_to_list(stat: Optional[dict]) -> Optional[list]:
    """Convert stat dict to Scheme list."""
    if stat is None:
        return None
    return [
        ['type', stat['type']],
        ['mode', stat['mode']],
        ['uid', stat['uid']],
        ['gid', stat['gid']],
        ['mtime', stat['mtime']],
        ['size', stat['size']],
        ['hash', stat['hash']]
    ]


def _get_hash(fs, path: str) -> Optional[str]:
    """Get the content hash of a path."""
    stat = fs.stat(path)
    return stat['hash'] if stat else None


def _with_file(fs, path: str, mode: str, proc: Callable) -> Any:
    """Open a file and apply a procedure to its handle."""
    handle = fs.open(path, mode)
    if handle:
        with handle as f:
            return proc(f)
    return None


def _map_directory(fs, proc: Callable, path: str) -> list:
    """Apply a procedure to each entry in a directory."""
    entries = fs.ls(path)
    if entries is None:
        return []
    return [proc(entry) for entry in entries]


def _save_fs(fs, path: str) -> bool:
    """Save filesystem state to a file."""
    import json
    try:
        with open(path, 'w') as f:
            f.write(fs.to_json())
        return True
    except Exception:
        return False


def _load_fs(path: str) -> bool:
    """Load filesystem state from a file."""
    import json
    try:
        with open(path, 'r') as f:
            content = f.read()
        new_fs = dagshell.FileSystem.from_json(content)
        # Replace the global filesystem
        dagshell._default_fs = new_fs
        return True
    except Exception:
        return False


class SchemeREPL:
    """Read-Eval-Print Loop for the Scheme interpreter."""

    def __init__(self):
        self.env = create_global_env()
        self.history = []

    def eval_string(self, code: str) -> Any:
        """Evaluate a string of Scheme code."""
        tokens = tokenize(code)
        if not tokens:
            return None

        expr = parse(tokens)
        return evaluate(expr, self.env)

    def run(self):
        """Run the interactive REPL."""
        print("DagShell Scheme Interpreter")
        print("Type (help) for available commands or (exit) to quit")
        print()

        # Add help function
        self.env.define('help', lambda: self._show_help())
        self.env.define('exit', lambda: sys.exit(0))

        while True:
            try:
                # Read
                line = input("dagshell> ")
                if not line.strip():
                    continue

                self.history.append(line)

                # Eval
                result = self.eval_string(line)

                # Print
                if result is not None:
                    self._print_result(result)

            except KeyboardInterrupt:
                print("\nUse (exit) to quit")
            except EOFError:
                print("\nBye!")
                break
            except Exception as e:
                print(f"Error: {e}")

    def _print_result(self, result: Any):
        """Pretty print a result."""
        if isinstance(result, bool):
            print("#t" if result else "#f")
        elif isinstance(result, list):
            print(self._list_to_string(result))
        elif isinstance(result, Symbol):
            print(f"'{result.name}")
        elif isinstance(result, Procedure):
            print("#<procedure>")
        elif callable(result):
            print("#<built-in>")
        else:
            print(result)

    def _list_to_string(self, lst: list) -> str:
        """Convert a list to Scheme notation."""
        elements = []
        for item in lst:
            if isinstance(item, list):
                elements.append(self._list_to_string(item))
            elif isinstance(item, bool):
                elements.append("#t" if item else "#f")
            elif isinstance(item, str):
                elements.append(f'"{item}"')
            else:
                elements.append(str(item))
        return f"({' '.join(elements)})"

    def _show_help(self):
        """Display help information."""
        help_text = """
Filesystem Operations:
  (mkdir "/path/to/dir")           - Create directory
  (ls "/path")                     - List directory contents
  (write-file "/path" "content")   - Write file
  (read-file "/path")              - Read file
  (rm "/path")                     - Remove file/directory
  (exists? "/path")                - Check if path exists
  (file? "/path")                  - Check if path is a file
  (directory? "/path")             - Check if path is a directory
  (stat "/path")                   - Get file statistics
  (get-hash "/path")               - Get content hash
  (purge)                          - Garbage collect unreferenced nodes

Data Operations:
  (define name value)              - Define a variable
  (lambda (params) body)           - Create a function
  (if condition then else)         - Conditional
  (let ((var val) ...) body)       - Local bindings

List Operations:
  (list 1 2 3)                     - Create a list
  (car lst)                        - First element
  (cdr lst)                        - Rest of list
  (cons elem lst)                  - Prepend element

Examples:
  (mkdir "/home")
  (write-file "/home/test.txt" "Hello, World!")
  (read-file "/home/test.txt")
  (map-directory display "/")
"""
        print(help_text)
        return None


def main():
    """Main entry point for the Scheme interpreter."""
    import sys

    if len(sys.argv) > 1:
        # Execute file
        filename = sys.argv[1]
        try:
            with open(filename, 'r') as f:
                code = f.read()

            repl = SchemeREPL()
            result = repl.eval_string(code)
            if result is not None:
                repl._print_result(result)
        except FileNotFoundError:
            print(f"Error: File not found: {filename}")
            sys.exit(1)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    else:
        # Interactive REPL
        repl = SchemeREPL()
        repl.run()


if __name__ == '__main__':
    main()