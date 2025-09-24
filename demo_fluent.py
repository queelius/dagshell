#!/usr/bin/env python3
"""
Demo of the dagshell fluent API - showcasing elegant, composable operations.

This demonstrates how the fluent API serves as the foundation for terminal emulation.
"""

from dagshell_fluent import DagShell, shell
import dagshell_fluent as ds

def demo_basic_operations():
    """Demonstrate basic shell operations."""
    print("=" * 60)
    print("BASIC OPERATIONS DEMO")
    print("=" * 60)

    # Use the global shell for consistency
    sh = shell

    # Navigate and create directory structure
    sh.mkdir('/home', parents=True)
    sh.mkdir('/home/user', parents=True)
    sh.cd('/home/user')

    print(f"Current directory: {sh.pwd().data}")

    # Create some files
    sh.touch('README.md')
    sh.echo('# My Project\nWelcome to dagshell!').out('README.md')
    sh.echo('TODO: Build amazing things').out('todo.txt')

    # List files
    print("\nDirectory contents:")
    for file in sh.ls().data:
        print(f"  - {file}")

    # Read a file
    print(f"\nREADME.md contents:\n{sh.cat('README.md').data.decode()}")


def demo_chaining():
    """Demonstrate method chaining and piping."""
    print("\n" + "=" * 60)
    print("METHOD CHAINING DEMO")
    print("=" * 60)

    sh = shell

    # Setup test data
    sh.mkdir('/data', parents=True)
    sh.cd('/data')

    # Create a log file
    log_content = """2024-01-01 ERROR Failed to connect
2024-01-01 INFO Connected successfully
2024-01-02 ERROR Timeout occurred
2024-01-02 WARNING Low memory
2024-01-03 INFO Task completed
2024-01-03 ERROR Network unreachable"""

    sh.echo(log_content).out('system.log')

    # Chain operations: find ERROR lines, sort them, count them
    print("Finding and counting ERROR lines:")

    # Method 1: Using last result propagation
    sh.cat('system.log')
    sh.grep('ERROR')
    error_lines = sh._last_result.data
    print(f"Found {len(error_lines)} errors:")
    for line in error_lines:
        print(f"  {line}")

    # Count words in error messages
    sh.cat('system.log')
    sh.grep('ERROR')
    word_count = sh.wc(words=True, lines=False).data
    print(f"\nTotal words in error messages: {word_count}")


def demo_text_processing():
    """Demonstrate text processing capabilities."""
    print("\n" + "=" * 60)
    print("TEXT PROCESSING DEMO")
    print("=" * 60)

    sh = shell
    sh.mkdir('/text', parents=True)
    sh.cd('/text')

    # Create sample data
    data = """apple
banana
cherry
apple
date
banana
elderberry
apple"""

    sh.echo(data).out('fruits.txt')

    print("Original data:")
    print(sh.cat('fruits.txt').data.decode())

    # Sort and get unique values
    print("\nUnique fruits (sorted):")
    result = sh.sort('fruits.txt', unique=True)
    for fruit in result.data:
        print(f"  - {fruit}")

    # Count occurrences
    print("\nFruit occurrences:")
    sh.sort('fruits.txt')
    result = sh.uniq(count=True)
    for count, fruit in result.data:
        print(f"  {fruit}: {count}")


def demo_find_and_glob():
    """Demonstrate find and glob pattern matching."""
    print("\n" + "=" * 60)
    print("FIND AND GLOB DEMO")
    print("=" * 60)

    sh = shell

    # Create complex directory structure
    sh.mkdir('/project', parents=True)
    sh.mkdir('/project/src', parents=True)
    sh.mkdir('/project/tests', parents=True)
    sh.mkdir('/project/docs', parents=True)

    # Create various files
    sh.touch('/project/README.md')
    sh.touch('/project/setup.py')
    sh.touch('/project/src/main.py')
    sh.touch('/project/src/utils.py')
    sh.touch('/project/tests/test_main.py')
    sh.touch('/project/tests/test_utils.py')
    sh.touch('/project/docs/api.md')
    sh.touch('/project/docs/guide.md')

    # Find all Python files
    print("Python files in project:")
    result = sh.find('/project', name='*.py')
    for path in sorted(result.data):
        print(f"  {path}")

    # Find all directories
    print("\nDirectories in project:")
    result = sh.find('/project', type='d', maxdepth=2)
    for path in sorted(result.data):
        print(f"  {path}")

    # Find markdown files
    print("\nMarkdown files:")
    result = sh.find('/project', name='*.md')
    for path in sorted(result.data):
        print(f"  {path}")


def demo_environment():
    """Demonstrate environment variable handling."""
    print("\n" + "=" * 60)
    print("ENVIRONMENT VARIABLES DEMO")
    print("=" * 60)

    sh = shell

    # Show current environment
    print("Current environment variables:")
    env = sh.env().data
    for key, value in sorted(env.items())[:5]:  # Show first 5
        print(f"  {key}={value}")

    # Set custom variables
    sh.setenv('MY_APP_VERSION', '1.0.0')
    sh.setenv('MY_APP_ENV', 'development')

    print(f"\nMY_APP_VERSION: {sh.env('MY_APP_VERSION').data}")
    print(f"MY_APP_ENV: {sh.env('MY_APP_ENV').data}")


def demo_pipelines():
    """Demonstrate complex pipelines."""
    print("\n" + "=" * 60)
    print("COMPLEX PIPELINES DEMO")
    print("=" * 60)

    sh = shell

    # Create sample CSV data
    sh.mkdir('/analytics', parents=True)
    sh.cd('/analytics')

    csv_data = """name,age,department
Alice,30,Engineering
Bob,25,Marketing
Charlie,35,Engineering
Diana,28,Sales
Eve,32,Engineering
Frank,29,Marketing"""

    sh.echo(csv_data).out('employees.csv')

    # Pipeline: Find Engineering employees, sort by name
    print("Engineering team members:")
    sh.cat('employees.csv')
    sh.grep('Engineering')
    engineers = sh._last_result.data
    for line in sorted(engineers):
        if 'name' not in line:  # Skip header if present
            print(f"  {line}")

    # Count employees per department
    print("\nEmployees per department:")
    sh.cat('employees.csv')
    sh.tail(6)  # Skip header
    lines = sh._last_result.data

    dept_count = {}
    for line in lines:
        if line:
            parts = line.split(',')
            if len(parts) >= 3:
                dept = parts[2]
                dept_count[dept] = dept_count.get(dept, 0) + 1

    for dept, count in sorted(dept_count.items()):
        print(f"  {dept}: {count} employees")


def demo_output_redirection():
    """Demonstrate output redirection."""
    print("\n" + "=" * 60)
    print("OUTPUT REDIRECTION DEMO")
    print("=" * 60)

    sh = shell
    sh.mkdir('/output', parents=True)
    sh.cd('/output')

    # Generate some data and redirect to file
    print("Generating random numbers...")
    import random
    numbers = [str(random.randint(1, 100)) for _ in range(10)]
    sh.echo('\n'.join(numbers)).out('numbers.txt')

    # Process and redirect
    print("Sorting numbers...")
    sorted_result = sh.sort('numbers.txt', numeric=True)
    sorted_result.out('sorted_numbers.txt')

    # Show results
    print(f"\nOriginal: {sh.cat('numbers.txt').data.decode().splitlines()}")
    print(f"Sorted: {sh.cat('sorted_numbers.txt').data.decode().splitlines()}")


def demo_module_level_api():
    """Demonstrate module-level convenience functions."""
    print("\n" + "=" * 60)
    print("MODULE-LEVEL API DEMO")
    print("=" * 60)

    # Use module-level functions for quick operations
    ds.cd('/')
    ds.mkdir('/quick-test')
    ds.cd('/quick-test')

    print(f"Current directory: {ds.pwd().data}")

    # Create and read a file
    ds.echo('Quick test content').out('test.txt')
    content = ds.cat('test.txt')
    print(f"File content: {content.data.decode()}")

    # List directory
    files = ds.ls()
    print(f"Files: {files.data}")


if __name__ == '__main__':
    # Run all demos
    demo_basic_operations()
    demo_chaining()
    demo_text_processing()
    demo_find_and_glob()
    demo_environment()
    demo_pipelines()
    demo_output_redirection()
    demo_module_level_api()

    print("\n" + "=" * 60)
    print("DEMO COMPLETE")
    print("=" * 60)
    print("\nThe fluent API provides:")
    print("  ✓ Stateful operations (cd, env)")
    print("  ✓ Method chaining for pipe-like composition")
    print("  ✓ Python object returns for programmatic use")
    print("  ✓ Virtual filesystem redirection with .out()")
    print("  ✓ Complete Unix command set")
    print("  ✓ Foundation for terminal emulation")