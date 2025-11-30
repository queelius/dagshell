#!/usr/bin/env python3
"""
Scheme-like DSL for dagshell.

A minimal, elegant Scheme interpreter for filesystem operations.
Following the principle of simplicity and composability.
"""

import re
import sys
import os
import fnmatch
from typing import Any, List, Dict, Callable, Optional, Union
from dataclasses import dataclass
from functools import reduce
import operator

from . import dagshell


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

            # Let* - sequential let (each binding can reference previous ones)
            if op.name == 'let*':
                if len(expr) < 3:
                    raise SyntaxError("let* requires bindings and body")
                bindings = expr[1]
                if not isinstance(bindings, list):
                    raise SyntaxError("let* bindings must be a list")

                local_env = Environment(parent=env)
                for binding in bindings:
                    if not isinstance(binding, list) or len(binding) != 2:
                        raise SyntaxError("Each let* binding must be a list of 2 elements")
                    name = binding[0]
                    if not isinstance(name, Symbol):
                        raise SyntaxError("Binding name must be a symbol")
                    # Key difference: evaluate in local_env so previous bindings are visible
                    value = evaluate(binding[1], local_env)
                    local_env.define(name.name, value)

                # Evaluate body in local environment
                result = None
                for body_expr in expr[2:]:
                    result = evaluate(body_expr, local_env)
                return result

            # Cond - multi-way conditional
            if op.name == 'cond':
                if len(expr) < 2:
                    raise SyntaxError("cond requires at least one clause")

                for clause in expr[1:]:
                    if not isinstance(clause, list) or len(clause) < 2:
                        raise SyntaxError("Each cond clause must be a list of at least 2 elements")

                    test = clause[0]
                    # Handle else clause
                    if isinstance(test, Symbol) and test.name == 'else':
                        result = None
                        for body_expr in clause[1:]:
                            result = evaluate(body_expr, env)
                        return result

                    # Evaluate test condition
                    if evaluate(test, env):
                        result = None
                        for body_expr in clause[1:]:
                            result = evaluate(body_expr, env)
                        return result

                # No clause matched
                return None

            # And - logical and (short-circuiting)
            # In Scheme, only #f is false, everything else is truthy
            if op.name == 'and':
                result = True
                for arg in expr[1:]:
                    result = evaluate(arg, env)
                    if result is False:  # Only False is falsy in Scheme
                        return False
                return result

            # Or - logical or (short-circuiting)
            # In Scheme, only #f is false, everything else is truthy
            if op.name == 'or':
                for arg in expr[1:]:
                    result = evaluate(arg, env)
                    if result is not False:  # Anything except False is truthy
                        return result
                return False

            # Try - error handling
            # (try expr (catch error-handler))
            if op.name == 'try':
                if len(expr) < 2:
                    raise SyntaxError("try requires an expression")

                try:
                    # Try to evaluate the main expression
                    return evaluate(expr[1], env)
                except Exception as e:
                    # If there's a catch clause, use it
                    if len(expr) >= 3 and isinstance(expr[2], list) and len(expr[2]) >= 2:
                        catch_clause = expr[2]
                        if isinstance(catch_clause[0], Symbol) and catch_clause[0].name == 'catch':
                            # Create an environment with the error bound
                            catch_env = Environment(parent=env)
                            catch_env.define('error', str(e))
                            # Evaluate the catch handler
                            result = None
                            for handler_expr in catch_clause[1:]:
                                result = evaluate(handler_expr, catch_env)
                            return result
                    # No catch clause or invalid catch, return False
                    return False

        # Function application
        func = evaluate(op, env)
        args = [evaluate(arg, env) for arg in expr[1:]]

        if callable(func):
            return func(*args)
        else:
            raise TypeError(f"Cannot call non-function: {func}")

    # Unknown expression type
    raise ValueError(f"Cannot evaluate: {expr}")


def create_global_env(shell=None) -> Environment:
    """Create the global environment with built-in functions.

    Args:
        shell: Optional DagShell instance to use for filesystem operations.
               If not provided, a new instance will be created.
    """
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
    env.define('append', lambda *lists: sum(lists, []))
    env.define('reverse', lambda lst: list(reversed(lst)))
    env.define('map', lambda f, lst: [f(x) for x in lst])
    env.define('filter', lambda f, lst: [x for x in lst if f(x)])
    env.define('reduce', lambda f, lst, init=0: reduce(f, lst, init))

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
    env.define('string-split', lambda s, sep=' ': s.split(sep))
    env.define('string-join', lambda lst, sep=' ': sep.join(str(x) for x in lst))
    env.define('string-contains?', lambda s, sub: sub in s)
    env.define('string-replace', lambda s, old, new: s.replace(old, new))

    # I/O operations
    env.define('display', lambda x: print(x, end=''))
    env.define('newline', lambda: print())
    env.define('read-line', lambda: input())

    # Filesystem operations - the heart of dagshell
    # Use fluent API for more features
    from .dagshell_fluent import DagShell
    if shell is None:
        shell = DagShell()
    fs = shell.fs

    # Navigation
    env.define('pwd', lambda: _pwd(shell))
    env.define('cd', lambda path='/': _cd(shell, path))
    env.define('pushd', lambda path: _pushd(shell, path))
    env.define('popd', lambda: _popd(shell))

    # File operations
    env.define('read-file', lambda path: _read_file(shell, path))
    env.define('write-file', lambda path, content: _write_file(shell, path, content))
    env.define('append-file', lambda path, content: _append_file_resolved(shell, path, content))
    env.define('touch', lambda path: _touch_resolved(shell, path))
    env.define('cp', lambda src, dst: _cp_resolved(shell, src, dst))
    env.define('mv', lambda src, dst: _mv_resolved(shell, src, dst))
    env.define('exists?', lambda path: _exists_resolved(shell, path))
    env.define('file-exists?', lambda path: _exists_resolved(shell, path))  # Alias for compatibility
    env.define('file?', lambda path: _is_file_resolved(shell, path))
    env.define('directory?', lambda path: _is_directory_resolved(shell, path))

    # Directory operations
    env.define('mkdir', lambda path, parents=False: _mkdir_resolved(shell, path, parents))
    env.define('ls', lambda path=None: _ls(shell, path))
    env.define('rm', lambda path, recursive=False: _rm_resolved(shell, path, recursive))
    env.define('purge', lambda: fs.purge())

    # Text processing
    env.define('grep', lambda pattern, text: _grep(pattern, text))
    env.define('head', lambda lines, n=10: lines[:n] if isinstance(lines, list) else lines.split('\n')[:n])
    env.define('tail', lambda lines, n=10: lines[-n:] if isinstance(lines, list) else lines.split('\n')[-n:])
    env.define('sort', lambda lines: sorted(lines) if isinstance(lines, list) else sorted(lines.split('\n')))
    env.define('uniq', lambda lines: _uniq(lines))
    env.define('wc', lambda text: _wc(text))
    env.define('echo', lambda *args: ' '.join(str(arg) for arg in args))

    # Search
    env.define('find', lambda path='/', name=None, type=None: _find_resolved(shell, path, name, type))

    # Metadata operations
    env.define('stat', lambda path: _stat_resolved(shell, path))
    env.define('get-hash', lambda path: _get_hash_resolved(shell, path))

    # Advanced operations
    env.define('with-file', lambda path, mode, proc: _with_file(fs, path, mode, proc))
    env.define('map-directory', lambda proc, path='/': _map_directory(fs, proc, path))
    env.define('pipe', lambda *procs: _pipe(*procs))

    # Persistence
    env.define('save', lambda path='dagshell.json': _save_fs(fs, path))
    env.define('load', lambda path='dagshell.json': _load_fs(path))
    env.define('export', lambda target_path: _export(fs, target_path))

    # User management
    env.define('whoami', lambda: _whoami(shell))
    env.define('su', lambda user='root': _su(shell, user))

    # Aliases for common operations
    env.define('cat', lambda path: fs.read(path).decode('utf-8') if fs.read(path) else None)

    return env


# Helper functions for filesystem operations

# Directory stack for pushd/popd
_dir_stack = []

def _pwd(shell):
    """Get current working directory."""
    return shell._cwd

def _cd(shell, path):
    """Change directory."""
    shell.cd(path)
    return shell._cwd

def _read_file(shell, path):
    """Read file with path resolution."""
    resolved_path = shell._resolve_path(path)
    content = shell.fs.read(resolved_path)
    return content.decode('utf-8') if content else None

def _write_file(shell, path, content):
    """Write file with path resolution."""
    resolved_path = shell._resolve_path(path)
    return shell.fs.write(resolved_path, content)

def _append_file_resolved(shell, path, content):
    """Append to file with path resolution."""
    resolved_path = shell._resolve_path(path)
    return _append_file(shell.fs, resolved_path, content)

def _touch_resolved(shell, path):
    """Touch file with path resolution."""
    resolved_path = shell._resolve_path(path)
    return _touch(shell.fs, resolved_path)

def _cp_resolved(shell, src, dst):
    """Copy file with path resolution."""
    resolved_src = shell._resolve_path(src)
    resolved_dst = shell._resolve_path(dst)
    return _cp(shell.fs, resolved_src, resolved_dst)

def _mv_resolved(shell, src, dst):
    """Move file with path resolution."""
    resolved_src = shell._resolve_path(src)
    resolved_dst = shell._resolve_path(dst)
    return _mv(shell.fs, resolved_src, resolved_dst)

def _exists_resolved(shell, path):
    """Check if path exists with path resolution."""
    resolved_path = shell._resolve_path(path)
    return shell.fs.exists(resolved_path)

def _is_file_resolved(shell, path):
    """Check if path is a file with path resolution."""
    resolved_path = shell._resolve_path(path)
    return _is_file(shell.fs, resolved_path)

def _is_directory_resolved(shell, path):
    """Check if path is a directory with path resolution."""
    resolved_path = shell._resolve_path(path)
    return _is_directory(shell.fs, resolved_path)

def _mkdir_resolved(shell, path, parents=False):
    """Create directory with path resolution."""
    resolved_path = shell._resolve_path(path)
    return _mkdir(shell.fs, resolved_path, parents)

def _rm_resolved(shell, path, recursive=False):
    """Remove file/directory with path resolution."""
    resolved_path = shell._resolve_path(path)
    return _rm(shell.fs, resolved_path, recursive)

def _stat_resolved(shell, path):
    """Get file stats with path resolution."""
    resolved_path = shell._resolve_path(path)
    return _stat_to_list(shell.fs.stat(resolved_path))

def _get_hash_resolved(shell, path):
    """Get file hash with path resolution."""
    resolved_path = shell._resolve_path(path)
    return _get_hash(shell.fs, resolved_path)

def _find_resolved(shell, path='.', name=None, type=None):
    """Find files with path resolution."""
    resolved_path = shell._resolve_path(path)
    return _find(shell.fs, resolved_path, name, type)

def _pushd(shell, path):
    """Push current directory and change to new one."""
    _dir_stack.append(shell._cwd)
    shell.cd(path)
    return shell._cwd

def _popd(shell):
    """Pop directory from stack and change to it."""
    if _dir_stack:
        path = _dir_stack.pop()
        shell.cd(path)
        return shell._cwd
    return None

def _touch(fs, path):
    """Create empty file or update timestamp."""
    if not fs.exists(path):
        fs.write(path, b'')
    return True

def _cp(fs, src, dst):
    """Copy file."""
    content = fs.read(src)
    if content is not None:
        return fs.write(dst, content)
    return False

def _mv(fs, src, dst):
    """Move file."""
    if _cp(fs, src, dst):
        fs.rm(src)
        return True
    return False

def _mkdir(fs, path, parents=False):
    """Create directory."""
    if parents:
        parts = path.strip('/').split('/')
        current = '/'
        for part in parts:
            current = os.path.join(current, part)
            if not fs.exists(current):
                fs.mkdir(current)
        return True
    return fs.mkdir(path)

def _rm(fs, path, recursive=False):
    """Remove file or directory."""
    # TODO: Implement recursive removal
    return fs.rm(path)

def _ls(shell, path=None):
    """List directory contents."""
    if path is None:
        path = shell._cwd
    return shell.fs.ls(path) or []

def _grep(pattern, text):
    """Search for pattern in text."""
    import re
    if isinstance(text, str):
        lines = text.split('\n')
    else:
        lines = text

    result = []
    for line in lines:
        if re.search(pattern, str(line)):
            result.append(line)
    return result

def _uniq(lines):
    """Remove duplicate consecutive lines."""
    if isinstance(lines, str):
        lines = lines.split('\n')

    result = []
    prev = None
    for line in lines:
        if line != prev:
            result.append(line)
            prev = line
    return result

def _wc(text):
    """Count lines, words, and characters."""
    if isinstance(text, list):
        text = '\n'.join(str(x) for x in text)

    lines = text.count('\n')
    words = len(text.split())
    chars = len(text)
    return [lines, words, chars]

def _find(fs, path='/', name=None, type=None):
    """Find files and directories."""
    import fnmatch

    results = []

    def search(current_path):
        entries = fs.ls(current_path) or []
        for entry in entries:
            full_path = os.path.join(current_path, entry)

            # Check type filter
            if type:
                stat = fs.stat(full_path)
                if stat:
                    if type == 'f' and stat['type'] != 'file':
                        continue
                    if type == 'd' and stat['type'] != 'dir':
                        continue

            # Check name filter
            if name:
                if not fnmatch.fnmatch(entry, name):
                    continue

            results.append(full_path)

            # Recurse into directories
            if fs.stat(full_path) and fs.stat(full_path)['type'] == 'dir':
                search(full_path)

    search(path)
    return results

def _pipe(*procs):
    """Pipe data through multiple procedures."""
    def piped(*args):
        result = args[0] if args else None
        for proc in procs:
            result = proc(result)
        return result
    return piped

def _export(fs, target_path):
    """Export virtual filesystem to real filesystem."""
    try:
        count = fs.export_to_real(target_path)
        return f"Exported {count} files/directories to {target_path}"
    except Exception as e:
        return f"Export failed: {e}"

def _whoami(shell):
    """Get current user."""
    return shell._env.get('USER', 'user')

def _su(shell, user):
    """Switch user."""
    shell.setenv('USER', user)
    return f"Switched to user: {user}"

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

    def __init__(self, shell=None):
        self.shell = shell  # Optional shell for filesystem access
        self.env = create_global_env(shell=shell)
        self.history = []

    def eval_string(self, code: str) -> Any:
        """Evaluate a string of Scheme code (may contain multiple expressions)."""
        tokens = tokenize(code)
        if not tokens:
            return None

        # Parse and evaluate all expressions, return the last result
        result = None
        idx = 0

        while idx < len(tokens):
            def parse_expr(tokens: List[str], idx: int) -> tuple[Any, int]:
                """Parse a single expression and return it with the next index."""
                if idx >= len(tokens):
                    raise SyntaxError("Unexpected EOF")

                token = tokens[idx]

                if token == '(':
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
                    return parse_atom(token), idx + 1

            expr, idx = parse_expr(tokens, idx)
            result = evaluate(expr, self.env)

        return result

    def eval_file(self, filepath: str) -> Any:
        """Evaluate a Scheme file from the virtual filesystem.

        Args:
            filepath: Path to the Scheme file in the virtual filesystem

        Returns:
            Result of the last expression evaluated in the file

        Raises:
            ValueError: If no shell is configured
            FileNotFoundError: If the file doesn't exist
        """
        if not self.shell:
            raise ValueError("No shell configured. Set repl.shell before calling eval_file()")

        if not self.shell.fs.exists(filepath):
            raise FileNotFoundError(f"Scheme file not found: {filepath}")

        # Read the file content from virtual filesystem
        content = self.shell.fs.read(filepath).decode('utf-8')

        # Tokenize the entire file once
        tokens = tokenize(content)
        if not tokens:
            return None

        # Parse and evaluate all expressions in the file
        result = None
        idx = 0

        while idx < len(tokens):
            # Use the internal parse_expr function to parse one expression
            # and get the next index
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
                    return parse_atom(tokens[idx]), idx + 1

            expr, idx = parse_expr(tokens, idx)
            result = evaluate(expr, self.env)

        return result

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
FILESYSTEM NAVIGATION:
  (pwd)                            - Print working directory
  (cd "/path")                     - Change directory
  (pushd "/path")                  - Push directory onto stack
  (popd)                           - Pop directory from stack
  (ls)                             - List current directory
  (ls "/path")                     - List specific directory

FILE OPERATIONS:
  (cat "/file")                    - Display file contents
  (touch "/file")                  - Create empty file
  (write-file "/file" "text")      - Write to file
  (append-file "/file" "text")     - Append to file
  (read-file "/file")              - Read file contents
  (cp "/src" "/dst")               - Copy file
  (mv "/src" "/dst")               - Move/rename file
  (rm "/file")                     - Remove file

DIRECTORY OPERATIONS:
  (mkdir "/dir")                   - Create directory
  (mkdir "/a/b/c" #t)              - Create with parents
  (rm "/dir" #t)                   - Remove recursively

TEXT PROCESSING:
  (echo "hello" "world")           - Print arguments
  (grep "pattern" text)            - Search for pattern
  (head lines 5)                   - First 5 lines
  (tail lines 10)                  - Last 10 lines
  (sort lines)                     - Sort lines
  (uniq lines)                     - Remove duplicates
  (wc text)                        - Count lines/words/chars

SEARCHING:
  (find "/path")                   - Find all files/dirs
  (find "/path" "*.txt")           - Find by pattern
  (find "/path" #f "f")            - Find only files
  (find "/path" #f "d")            - Find only directories

PERSISTENCE:
  (save)                           - Save to dagshell.json
  (load)                           - Load from dagshell.json
  (save "/backup.json")            - Save to specific file
  (export "/real/path")            - Export to real filesystem

LIST OPERATIONS:
  (list 1 2 3)                     - Create list
  (car lst)                        - First element
  (cdr lst)                        - Rest of list
  (cons x lst)                     - Prepend element
  (append lst1 lst2)               - Concatenate lists
  (map proc lst)                   - Apply proc to each
  (filter pred lst)                - Keep matching elements
  (reduce proc lst init)           - Fold/reduce list

STRING OPERATIONS:
  (string-split "a b c")           - Split on spaces
  (string-join lst ", ")           - Join with separator
  (string-contains? str "sub")     - Check substring
  (string-replace str "old" "new") - Replace substring

PIPING & COMPOSITION:
  (pipe proc1 proc2 proc3)         - Compose procedures
  Example: ((pipe (lambda (x) (grep "error" x))
                  (lambda (x) (head x 5)))
            (read-file "/log"))

EXAMPLES:
  ; Create project structure
  (begin
    (mkdir "/project")
    (write-file "/project/README.md" "# My Project")
    (ls "/project"))

  ; Process log files
  (define errors
    (grep "ERROR" (read-file "/app.log")))

  ; Backup files
  (map (lambda (f) (cp f (string-append f ".bak")))
       (find "/src" "*.scm"))
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