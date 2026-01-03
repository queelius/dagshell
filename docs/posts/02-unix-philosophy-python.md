# Unix Philosophy in Python: Composable Commands with Method Chaining

*How to build pipeable, chainable interfaces that do one thing well*

---

The Unix philosophy, articulated by Doug McIlroy, can be summarized as:

> Write programs that do one thing and do it well. Write programs to work together. Write programs to handle text streams, because that is a universal interface.

This philosophy gave us pipes (`|`), small focused utilities (`cat`, `grep`, `sort`), and the ability to compose complex operations from simple parts:

```bash
cat access.log | grep "404" | cut -d' ' -f1 | sort | uniq -c | sort -rn
```

Can we bring this composability to Python? Not just subprocess calls, but native Python objects that pipe and chain as naturally as Unix commands? Let's build it.

## The Problem with Methods

Standard Python methods have a composition problem. Consider:

```python
# We want to: read a file, filter lines, count words
content = read_file("/data/log.txt")
filtered = grep(content, "ERROR")
count = wc(filtered)
```

This works, but it's inside-out compared to how we think about it. We think "read, then filter, then count"—a left-to-right pipeline. But we write it bottom-up with intermediate variables.

Method chaining helps:

```python
read_file("/data/log.txt").grep("ERROR").wc()
```

Now it flows left-to-right. But how do we make arbitrary operations chainable?

## The CommandResult Pattern

The key insight is wrapping every result in a chainable container:

```python
@dataclass
class CommandResult:
    """Wrapper that enables method chaining."""
    data: Any           # The actual result data
    text: str = None    # Text representation
    exit_code: int = 0  # Unix-style exit code
    _shell: 'DagShell' = None  # Reference back to the shell

    def __str__(self) -> str:
        if self.text is not None:
            return self.text
        return str(self.data)
```

Every command returns a `CommandResult`. The result carries the data *and* a reference to the shell that produced it. This reference enables chaining—we can call more methods through it.

## Making Commands Chainable

Here's a simple command implementation:

```python
class DagShell:
    def echo(self, *args) -> CommandResult:
        """Echo arguments to output."""
        text = ' '.join(str(arg) for arg in args)
        return CommandResult(
            data=text,
            text=text,
            exit_code=0,
            _shell=self
        )
```

The magic happens in `CommandResult`. We add methods that delegate back to the shell:

```python
@dataclass
class CommandResult:
    # ... fields as before ...

    def grep(self, pattern: str) -> 'CommandResult':
        """Filter lines matching pattern."""
        return self._shell.grep(pattern, input_data=self.data)

    def wc(self, *flags) -> 'CommandResult':
        """Count lines, words, or characters."""
        return self._shell.wc(*flags, input_data=self.data)

    def out(self, path: str) -> 'CommandResult':
        """Redirect output to a file."""
        self._shell.fs.write(path, str(self).encode())
        return self
```

Now we can chain:

```python
shell.echo("hello world").wc("-w")  # Returns: 2
shell.cat("/data/log.txt").grep("ERROR").wc("-l")  # Count error lines
```

## The Dual Nature: Objects and Files

Unix commands have a superpower: the same output can go to the screen, a file, or another command. We can replicate this:

```python
# Chain more commands
result = shell.cat("/data/log.txt").grep("ERROR")

# Get as Python object
lines = result.lines()  # List[str]

# Or redirect to a file
result.out("/data/errors.txt")
```

The `CommandResult` is simultaneously:
1. A Python object you can inspect and manipulate
2. A text stream you can redirect to files
3. An input source for the next command in a pipeline

This dual nature—structured data *and* text stream—bridges the gap between Unix philosophy and Python's object orientation.

## Implementing Piping

True Unix pipes pass data between processes. We simulate this with a "last result" mechanism:

```python
class DagShell:
    def __init__(self):
        self._last_result: Optional[CommandResult] = None

    def _(self) -> CommandResult:
        """Return the last command's result (like $? or $_)."""
        if self._last_result is None:
            return CommandResult(data='', text='', exit_code=0, _shell=self)
        return self._last_result
```

Now we can build pipelines:

```python
shell.cat("/data/log.txt")
shell._().grep("ERROR")
shell._().wc("-l")
```

Or more elegantly, commands can accept piped input:

```python
def grep(self, pattern: str, input_data=None) -> CommandResult:
    """Filter lines matching pattern."""
    if input_data is None:
        input_data = self._last_result.data if self._last_result else ''

    lines = str(input_data).splitlines()
    matching = [line for line in lines if pattern in line]

    result = CommandResult(
        data=matching,
        text='\n'.join(matching),
        exit_code=0 if matching else 1,
        _shell=self
    )
    self._last_result = result
    return result
```

## Method Chaining in Action

Let's build something real—a log analysis pipeline:

```python
# Create a shell and some test data
shell = DagShell()
shell.mkdir("/logs")
shell.echo("""
2024-01-15 10:30:00 INFO  User login: alice
2024-01-15 10:31:00 ERROR Database connection failed
2024-01-15 10:32:00 INFO  User login: bob
2024-01-15 10:33:00 ERROR Timeout waiting for response
2024-01-15 10:34:00 WARN  High memory usage
2024-01-15 10:35:00 ERROR Disk space low
""".strip()).out("/logs/app.log")

# Pipeline: find errors, extract timestamps, save to file
(shell
    .cat("/logs/app.log")
    .grep("ERROR")
    .cut(delimiter=" ", fields="1,2")
    .out("/logs/error_times.txt"))

# Read the result
print(shell.cat("/logs/error_times.txt"))
# Output:
# 2024-01-15 10:31:00
# 2024-01-15 10:33:00
# 2024-01-15 10:35:00
```

Each step does one thing. The chain composes them into a useful operation. The data flows left-to-right, just like our mental model.

## Directory Navigation with a Stack

Unix has `cd`, but shells also have `pushd` and `popd` for directory stacks. We implement this:

```python
class DagShell:
    def __init__(self):
        self._cwd = '/'
        self._dir_stack = []

    def pushd(self, path: str) -> CommandResult:
        """Push current directory and change to new one."""
        self._dir_stack.append(self._cwd)
        return self.cd(path)

    def popd(self) -> CommandResult:
        """Pop directory from stack and change to it."""
        if not self._dir_stack:
            return CommandResult(data='', text='popd: directory stack empty', exit_code=1)
        old_dir = self._dir_stack.pop()
        return self.cd(old_dir)
```

Now we can navigate without losing our place:

```python
shell.pushd("/project/src")
# ... work in src ...
shell.pushd("tests")
# ... work in tests ...
shell.popd()  # back to /project/src
shell.popd()  # back to original directory
```

## Exit Codes: Success and Failure

Unix commands return exit codes: 0 for success, non-zero for failure. We include this in `CommandResult`:

```python
def grep(self, pattern: str) -> CommandResult:
    # ... filtering logic ...
    return CommandResult(
        data=matching,
        text='\n'.join(matching),
        exit_code=0 if matching else 1,  # 1 if no matches
        _shell=self
    )
```

This enables conditional logic:

```python
result = shell.grep("pattern", file="/data/log.txt")
if result.exit_code == 0:
    print(f"Found {len(result.lines())} matches")
else:
    print("No matches found")
```

## The Philosophy Applied

Let's revisit McIlroy's principles and see how we've applied them:

**"Do one thing well"**: Each method (`cat`, `grep`, `wc`, `cut`) does exactly one thing.

**"Work together"**: `CommandResult` enables any command to connect to any other.

**"Text streams as universal interface"**: Every result has a text representation via `__str__`, making it redirectable and pipeable.

We've also added Python-specific benefits:
- **Type safety**: Results carry structured `data`, not just text
- **Introspection**: `result.lines()`, `result.data`, etc.
- **Chaining**: Method chains read left-to-right like pipelines

## The Fluent Pattern

This is an instance of the **Fluent Interface** pattern, where methods return `self` (or a related object) to enable chaining. Martin Fowler described it in 2005, but the idea is older—Smalltalk embraced it from the beginning.

The key is designing methods that:
1. Perform their action
2. Return something chainable
3. Maintain enough context for the next operation

When done well, code reads almost like prose:

```python
(shell
    .mkdir("/project")
    .cd("/project")
    .echo("# My Project")
    .out("README.md")
    .echo("def main(): pass")
    .out("main.py")
    .ls("-la"))
```

## Trade-offs

This approach isn't free:

1. **Wrapper overhead**: Every result is wrapped in `CommandResult`
2. **Learning curve**: Users must understand the chaining pattern
3. **Debugging**: Long chains can be hard to debug—where did it fail?

For scripting and exploratory work, the expressiveness outweighs these costs. For performance-critical code, you might unwrap to raw operations.

## Conclusion

The Unix philosophy isn't about Unix—it's about composability. Small, focused operations that connect through a universal interface create systems greater than the sum of their parts.

In Python, we achieve this with:
- **Wrapper types** that carry data and context
- **Method chaining** for left-to-right flow
- **Dual representations** as objects and text streams
- **Exit codes** for success/failure signaling

The result is a fluent interface where complex operations emerge from simple, composable parts—Unix philosophy, realized in Python.

---

*See the full implementation in [DagShell](https://github.com/queelius/dagshell), which builds a complete virtual filesystem with this fluent pattern.*

*Next in this series: [Embedding a Scheme Interpreter](#) — adding a DSL for filesystem scripting.*
