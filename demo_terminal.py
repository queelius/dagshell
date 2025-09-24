#!/usr/bin/env python3
"""
Demo script for the dagshell terminal emulator.

This script demonstrates the key features of the terminal emulator,
showing how shell commands are translated into fluent API calls.
"""

import dagshell
from terminal import TerminalSession, TerminalConfig
from dagshell_fluent import DagShell


def setup_demo_environment():
    """Set up a demo filesystem environment."""
    print("Setting up demo environment...")

    # The global filesystem is already initialized
    # Just add our demo content

    # Create directory structure
    dagshell.mkdir('/home')
    dagshell.mkdir('/home/user')
    dagshell.mkdir('/home/user/documents')
    dagshell.mkdir('/home/user/projects')
    dagshell.mkdir('/tmp')
    dagshell.mkdir('/etc')
    dagshell.mkdir('/var')
    dagshell.mkdir('/var/log')

    # Create some demo files
    dagshell.write('/home/user/hello.txt', b'Hello, World!\nWelcome to dagshell.\n')
    dagshell.write('/home/user/documents/readme.md', b'# DagShell Terminal\n\nA Unix-like terminal emulator.\n')
    dagshell.write('/home/user/documents/notes.txt', b'Important notes:\n- Task 1\n- Task 2\n- Task 3\n')

    # Create log files
    dagshell.write('/var/log/system.log', b'2024-01-01 10:00:00 System started\n2024-01-01 10:05:00 Service initialized\n')
    dagshell.write('/var/log/app.log', b'INFO: Application started\nDEBUG: Loading configuration\nINFO: Ready\n')

    # Create config file
    dagshell.write('/etc/config.conf', b'# Configuration\nport=8080\nhost=localhost\ndebug=true\n')

    # Create some test data files
    for i in range(1, 6):
        dagshell.write(f'/home/user/projects/test{i}.txt', f'Test file {i}\nContent line 1\nContent line 2\n'.encode())

    # Create a CSV file
    csv_content = b'name,age,city\nAlice,30,New York\nBob,25,Los Angeles\nCharlie,35,Chicago\n'
    dagshell.write('/home/user/data.csv', csv_content)

    print("Demo environment ready!\n")


def run_demo_commands():
    """Run a series of demo commands."""
    print("=" * 60)
    print("DagShell Terminal Emulator Demo")
    print("=" * 60)
    print()

    # Create terminal session
    config = TerminalConfig(
        user='demo',
        hostname='dagshell',
        home_dir='/home/user',
        initial_dir='/home/user'
    )
    session = TerminalSession(config=config)

    # Demo commands with explanations
    demo_commands = [
        ("# Navigation and listing", None),
        ("pwd", "Show current directory"),
        ("ls", "List files in current directory"),
        ("ls -la", "Detailed listing with hidden files"),
        ("cd documents", "Change to documents directory"),
        ("pwd", "Verify we're in documents"),
        ("ls", "List documents"),

        ("# File operations", None),
        ("cat readme.md", "Display file contents"),
        ("cd ..", "Go back to parent directory"),
        ("echo 'New file content' > newfile.txt", "Create a new file"),
        ("cat newfile.txt", "Display the new file"),
        ("echo 'Appended line' >> newfile.txt", "Append to file"),
        ("cat newfile.txt", "Display updated file"),

        ("# Text processing with pipes", None),
        ("cat documents/notes.txt | grep Task", "Filter lines with 'Task'"),
        ("ls projects | head -n 3", "Show first 3 files"),
        ("ls projects | sort -r", "List files in reverse order"),
        ("cat data.csv | grep Alice", "Find specific data"),

        ("# Complex pipelines", None),
        ("ls -la | grep txt | wc -l", "Count text files"),
        ("cat /var/log/app.log | grep INFO", "Filter log entries"),
        ("find /home -name '*.txt' | sort", "Find and sort text files"),

        ("# Working with multiple commands", None),
        ("cd /var/log ; ls", "Change dir and list"),
        ("cd /nonexistent && echo 'Success' || echo 'Failed'", "Conditional execution"),

        ("# Directory operations", None),
        ("mkdir /tmp/testdir", "Create a directory"),
        ("cd /tmp/testdir", "Enter the directory"),
        ("touch file1.txt file2.txt", "Create empty files"),
        ("ls", "List the created files"),

        ("# Environment variables", None),
        ("env", "Show all environment variables"),
        ("env HOME", "Show HOME variable"),
        ("env USER", "Show USER variable"),
    ]

    for cmd, description in demo_commands:
        if cmd.startswith('#'):
            # Section header
            print(f"\n{cmd}")
            print("-" * 40)
            continue

        # Display command with description
        if description:
            print(f"\n[{description}]")

        # Show the command being executed
        prompt = session.get_prompt()
        print(f"{prompt}{cmd}")

        # Execute and show output
        output = session.execute_command(cmd)
        if output:
            # Indent output for clarity
            for line in output.split('\n'):
                if line:
                    print(f"  {line}")

    print("\n" + "=" * 60)
    print("Demo completed!")
    print("=" * 60)


def interactive_demo():
    """Run an interactive demo session."""
    print("\n" + "=" * 60)
    print("Interactive Terminal Demo")
    print("=" * 60)
    print("\nYou can now interact with the terminal.")
    print("Try commands like: ls, cd, cat, echo, grep, etc.")
    print("Use pipes: ls | grep txt")
    print("Use redirections: echo hello > file.txt")
    print("Type 'exit' or 'quit' to leave.\n")

    # Create terminal session
    config = TerminalConfig(
        user='demo',
        hostname='dagshell',
        home_dir='/home/user',
        initial_dir='/home/user'
    )
    session = TerminalSession(config=config)

    # Run interactive session
    session.run_interactive()


def test_api_translation():
    """Demonstrate how terminal commands translate to API calls."""
    print("\n" + "=" * 60)
    print("Command to API Translation Demo")
    print("=" * 60)
    print("\nShowing how terminal commands map to Python API:\n")

    # Initialize
    shell = DagShell()

    # Examples of command translations
    examples = [
        ("ls -la", "shell.ls(all=True, long=True)"),
        ("cd /home", "shell.cd('/home')"),
        ("cat file.txt", "shell.cat('file.txt')"),
        ("echo hello > out.txt", "shell.echo('hello').out('out.txt')"),
        ("ls | grep test", "shell.ls().grep('test')"),
        ("cat f1 f2 | sort | uniq", "shell.cat('f1', 'f2').sort().uniq()"),
        ("find /home -name '*.txt'", "shell.find('/home', name='*.txt')"),
        ("head -n 20 file.txt", "shell.head(20, 'file.txt')"),
    ]

    for terminal_cmd, api_call in examples:
        print(f"Terminal: {terminal_cmd:30} → API: {api_call}")

    print("\nAll terminal commands execute through the fluent API!")


def main():
    """Main demo entry point."""
    import sys

    if len(sys.argv) > 1:
        mode = sys.argv[1]
        if mode == 'interactive':
            setup_demo_environment()
            interactive_demo()
        elif mode == 'commands':
            setup_demo_environment()
            run_demo_commands()
        elif mode == 'translation':
            test_api_translation()
        else:
            print(f"Unknown mode: {mode}")
            print("Available modes: interactive, commands, translation")
    else:
        # Default: run all demos
        setup_demo_environment()
        run_demo_commands()
        test_api_translation()
        print("\nRun with 'interactive' argument for interactive mode:")
        print("  python demo_terminal.py interactive")


if __name__ == '__main__':
    main()