# Embedding a Scheme Interpreter: Building a DSL for Filesystem Operations

*How to implement a minimal Scheme and integrate it with your application*

---

Every sufficiently complex application eventually grows a scripting language. Emacs has Elisp. AutoCAD has AutoLISP. Blender has Python. The pattern is clear: users need programmability beyond what a fixed UI provides.

But embedding a full language runtime is heavy. What if we just need something small—variables, functions, conditionals, loops? A Lisp-family language is perfect for this: the syntax is trivial to parse, the semantics are clean, and it's powerful enough for real scripting.

In this post, I'll walk through building a minimal Scheme interpreter in Python and integrating it with a virtual filesystem. We'll cover the complete pipeline: tokenization, parsing, evaluation, and extension with custom primitives.

## Why Scheme?

Scheme is a minimalist Lisp dialect. Its syntax is just parentheses and atoms:

```scheme
(define x 10)
(+ x (* 2 3))
(if (> x 5) "big" "small")
```

This uniformity makes parsing trivial. There's no operator precedence, no complex grammar—just:

1. Atoms: numbers, strings, symbols
2. Lists: `(thing thing thing ...)`

That's it. The entire parser can be written in under 50 lines.

## Step 1: Tokenization

First, we convert source code into tokens. Scheme's tokenization is simple: split on whitespace, but respect strings and parentheses.

```python
def tokenize(text: str) -> List[str]:
    """Convert Scheme code into tokens."""
    # Handle comments (lines starting with ;)
    lines = text.split('\n')
    text = '\n'.join(line.split(';')[0] for line in lines)

    # Add spaces around parens for easy splitting
    text = text.replace('(', ' ( ').replace(')', ' ) ')

    # Split, handling string literals
    tokens = []
    in_string = False
    current = []

    for char in text:
        if char == '"':
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

    return tokens
```

Input: `(define x (+ 1 2))`
Output: `['(', 'define', 'x', '(', '+', '1', '2', ')', ')']`

## Step 2: Parsing

Parsing converts tokens into an Abstract Syntax Tree (AST). In Scheme, the AST is just nested Python lists:

```python
@dataclass
class Symbol:
    """Represents a Scheme symbol."""
    name: str

def parse(tokens: List[str]) -> Any:
    """Parse tokens into an AST."""
    def parse_expr(index: int) -> Tuple[Any, int]:
        token = tokens[index]

        if token == '(':
            # Parse a list
            lst = []
            index += 1
            while tokens[index] != ')':
                expr, index = parse_expr(index)
                lst.append(expr)
            return lst, index + 1

        elif token == ')':
            raise SyntaxError("Unexpected )")

        else:
            # Parse an atom
            return parse_atom(token), index + 1

    expr, _ = parse_expr(0)
    return expr

def parse_atom(token: str) -> Any:
    """Parse a single atom."""
    # Try integer
    try:
        return int(token)
    except ValueError:
        pass

    # Try float
    try:
        return float(token)
    except ValueError:
        pass

    # String literal
    if token.startswith('"') and token.endswith('"'):
        return token[1:-1]

    # Boolean
    if token == '#t':
        return True
    if token == '#f':
        return False

    # Symbol
    return Symbol(token)
```

Input tokens: `['(', 'define', 'x', '(', '+', '1', '2', ')', ')']`
Output AST: `[Symbol('define'), Symbol('x'), [Symbol('+'), 1, 2]]`

The beauty of Lisp: the AST *is* the syntax. There's no separate tree structure—it's just lists of symbols and values.

## Step 3: The Environment

Before evaluation, we need an environment to track variable bindings. This is where lexical scoping lives:

```python
class Environment:
    """Lexical environment for variable bindings."""

    def __init__(self, parent: Optional['Environment'] = None):
        self.bindings: Dict[str, Any] = {}
        self.parent = parent

    def define(self, name: str, value: Any):
        """Define a new binding in this environment."""
        self.bindings[name] = value

    def get(self, name: str) -> Any:
        """Look up a binding, checking parent scopes."""
        if name in self.bindings:
            return self.bindings[name]
        elif self.parent:
            return self.parent.get(name)
        else:
            raise NameError(f"Undefined variable: {name}")

    def set(self, name: str, value: Any):
        """Update an existing binding."""
        if name in self.bindings:
            self.bindings[name] = value
        elif self.parent:
            self.parent.set(name, value)
        else:
            raise NameError(f"Undefined variable: {name}")
```

Each function call creates a new Environment with the current one as its parent. This chain enables closures—inner functions that remember their enclosing scope.

## Step 4: Evaluation

The evaluator is the heart of the interpreter. It walks the AST and computes values:

```python
def evaluate(expr: Any, env: Environment) -> Any:
    """Evaluate an expression in an environment."""

    # Self-evaluating: numbers, strings, booleans
    if isinstance(expr, (int, float, str, bool, type(None))):
        return expr

    # Variable lookup
    if isinstance(expr, Symbol):
        return env.get(expr.name)

    # Must be a list (function call or special form)
    if not isinstance(expr, list) or not expr:
        return expr

    op = expr[0]

    # Special forms
    if isinstance(op, Symbol):
        if op.name == 'quote':
            return expr[1]

        if op.name == 'define':
            name = expr[1]
            value = evaluate(expr[2], env)
            env.define(name.name, value)
            return value

        if op.name == 'if':
            condition = evaluate(expr[1], env)
            if condition:
                return evaluate(expr[2], env)
            elif len(expr) > 3:
                return evaluate(expr[3], env)
            return None

        if op.name == 'lambda':
            params = expr[1]
            body = expr[2]
            return Procedure(params, body, env)

    # Function application
    func = evaluate(op, env)
    args = [evaluate(arg, env) for arg in expr[1:]]
    return func(*args)
```

Special forms (`define`, `if`, `lambda`, etc.) have custom evaluation rules. Everything else is a function call: evaluate the operator, evaluate the arguments, call the function.

## Step 5: User-Defined Functions

The `lambda` form creates procedures. A Procedure captures its parameters, body, and defining environment:

```python
@dataclass
class Procedure:
    """A user-defined function."""
    params: List[Symbol]
    body: Any
    env: Environment

    def __call__(self, *args):
        # Create a new environment for the call
        local_env = Environment(parent=self.env)

        # Bind parameters to arguments
        for param, arg in zip(self.params, args):
            local_env.define(param.name, arg)

        # Evaluate the body in this new environment
        return evaluate(self.body, local_env)
```

When called, a Procedure:
1. Creates a new environment with its defining environment as parent (closure!)
2. Binds parameters to the passed arguments
3. Evaluates its body in this new environment

This simple structure gives us closures, higher-order functions, and lexical scoping.

## Step 6: Built-in Primitives

The global environment provides built-in functions:

```python
def create_global_env() -> Environment:
    """Create environment with built-in primitives."""
    env = Environment()

    # Arithmetic
    env.define('+', lambda *args: sum(args))
    env.define('-', lambda a, b=None: -a if b is None else a - b)
    env.define('*', lambda *args: reduce(lambda x, y: x * y, args, 1))
    env.define('/', lambda a, b: a / b)

    # Comparison
    env.define('=', lambda a, b: a == b)
    env.define('<', lambda a, b: a < b)
    env.define('>', lambda a, b: a > b)

    # List operations
    env.define('car', lambda lst: lst[0])
    env.define('cdr', lambda lst: lst[1:])
    env.define('cons', lambda a, b: [a] + list(b))
    env.define('list', lambda *args: list(args))
    env.define('null?', lambda lst: lst == [])

    # Higher-order functions
    env.define('map', lambda f, lst: [f(x) for x in lst])
    env.define('filter', lambda f, lst: [x for x in lst if f(x)])
    env.define('reduce', lambda f, lst, init: reduce(f, lst, init))

    return env
```

Each primitive is just a Python function. The interpreter treats them identically to user-defined procedures.

## Step 7: Filesystem Integration

Now the interesting part: extending Scheme with filesystem primitives.

```python
def create_global_env(shell=None) -> Environment:
    env = Environment()

    # ... standard primitives ...

    # Filesystem primitives (if shell provided)
    if shell:
        env.define('ls', lambda path='/': shell.ls(path).lines())
        env.define('cat', lambda path: shell.cat(path).text)
        env.define('mkdir', lambda path: shell.mkdir(path) and path)
        env.define('write', lambda path, content:
            shell.fs.write(path, content.encode()) and path)
        env.define('exists?', lambda path: shell.fs.exists(path))
        env.define('cd', lambda path: shell.cd(path) and path)
        env.define('pwd', lambda: shell._cwd)

    return env
```

Now Scheme can script filesystem operations:

```scheme
; Create a project structure
(mkdir "/project")
(mkdir "/project/src")
(mkdir "/project/tests")

(write "/project/README.md" "# My Project\n")
(write "/project/src/main.py" "def main(): pass\n")

; List files
(ls "/project")
; => ("README.md" "src" "tests")

; Check existence
(if (exists? "/project/README.md")
    "Found it!"
    "Not found")
```

## Step 8: The REPL

A Read-Eval-Print Loop ties it together:

```python
class SchemeREPL:
    def __init__(self, shell=None):
        self.env = create_global_env(shell=shell)

    def eval_string(self, code: str) -> Any:
        """Evaluate a string of Scheme code."""
        tokens = tokenize(code)
        if not tokens:
            return None

        result = None
        idx = 0

        while idx < len(tokens):
            expr, idx = self._parse_one(tokens, idx)
            result = evaluate(expr, self.env)

        return result

    def run(self):
        """Interactive REPL."""
        print("Scheme REPL (type 'quit' to exit)")
        while True:
            try:
                code = input("scheme> ")
                if code.strip() == 'quit':
                    break
                result = self.eval_string(code)
                if result is not None:
                    print(format_value(result))
            except Exception as e:
                print(f"Error: {e}")
```

## Example Session

Here's what a session looks like:

```
scheme> (define double (lambda (x) (* x 2)))
scheme> (double 21)
42

scheme> (map double (list 1 2 3 4 5))
(2 4 6 8 10)

scheme> (mkdir "/data")
"/data"

scheme> (write "/data/numbers.txt" "1\n2\n3\n")
"/data/numbers.txt"

scheme> (cat "/data/numbers.txt")
"1\n2\n3\n"

scheme> (filter (lambda (x) (> x 1))
               (map (lambda (s) (string->number s))
                    (string-split (cat "/data/numbers.txt") "\n")))
(2 3)
```

We've built a scriptable filesystem with a dozen lines of primitives!

## Design Patterns

Several patterns make this work:

**Homoiconicity**: Code is data. The AST is just lists, so we can generate and manipulate code programmatically.

**Closures**: Functions capture their environment, enabling powerful patterns like partial application and callbacks.

**Extension via primitives**: Adding features is just adding functions to the global environment. No interpreter changes needed.

**Separation of concerns**: Tokenizing, parsing, and evaluating are distinct phases with clean interfaces.

## Trade-offs

This simple interpreter has limitations:

1. **No tail-call optimization**: Deep recursion will overflow the Python stack.
2. **No macros**: We can't extend the language's syntax.
3. **Error messages are basic**: Line numbers would require more tracking.
4. **Performance**: Pure interpretation is slow for heavy computation.

For a DSL extending an application, these trade-offs are often acceptable. The simplicity enables understanding and modification.

## Conclusion

Embedding a language isn't black magic. At its core:

1. **Tokenize**: Break text into tokens
2. **Parse**: Build an AST (for Lisp, just nested lists)
3. **Evaluate**: Walk the AST, computing values
4. **Extend**: Add primitives that call into your application

Scheme's minimal syntax makes this especially tractable. In a few hundred lines, we get variables, functions, closures, conditionals, recursion, and extensibility.

The result is a scriptable application where users can automate, experiment, and build beyond what the core interface provides—exactly what we want from a DSL.

---

*The complete implementation is in [DagShell](https://github.com/queelius/dagshell), demonstrating Scheme as a filesystem scripting language alongside Python's fluent API.*

*This is the final post in the series. Previous posts: [Immutable Content-Addressed Filesystems](#) and [Unix Philosophy in Python](#).*
