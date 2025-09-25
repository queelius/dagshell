#!/usr/bin/env python3
"""Demo of DagShell terminal with persistence."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dagshell.terminal import TerminalSession
import os

def main():
    print("=" * 60)
    print("DagShell Terminal Emulator - Persistence Demo")
    print("=" * 60)

    # Create session
    session = TerminalSession()

    # Part 1: Create some data
    print("\n1. Creating filesystem structure...")
    commands = [
        "mkdir /home",
        "mkdir /home/user",
        "cd /home/user",
        "pwd",
        "echo 'Welcome to DagShell!' > README.md",
        "echo 'TODO: Build amazing things' > todo.txt",
        "mkdir projects",
        "cd projects",
        "touch project1.py",
        "touch project2.py",
        "cd ..",
        "ls -la"
    ]

    for cmd in commands:
        print(f"$ {cmd}")
        output = session.run_command(cmd)
        if output:
            print(output)

    # Part 2: Save the filesystem
    print("\n2. Saving filesystem...")
    print("$ save my_workspace.json")
    output = session.run_command("save my_workspace.json")
    print(output)

    # Part 3: Clear everything
    print("\n3. Clearing the filesystem...")
    print("$ rm -r /home")
    session.run_command("rm -r /home")
    print("$ ls /")
    output = session.run_command("ls /")
    print(output if output else "(empty)")

    # Part 4: Restore from saved file
    print("\n4. Restoring from saved file...")
    print("$ load my_workspace.json")
    output = session.run_command("load my_workspace.json")
    print(output)

    # Part 5: Verify restoration
    print("\n5. Verifying restored data...")
    print("$ cd /home/user")
    session.run_command("cd /home/user")
    print("$ ls -la")
    output = session.run_command("ls -la")
    print(output)
    print("$ cat README.md")
    output = session.run_command("cat README.md")
    print(output)

    print("\n" + "=" * 60)
    print("Demo complete!")
    print(f"Filesystem saved in: my_workspace.json")
    print(f"File size: {os.path.getsize('my_workspace.json')} bytes")
    print("\nYou can now:")
    print("  - Run 'python terminal.py' to start interactive mode")
    print("  - Load your saved workspace with 'load my_workspace.json'")
    print("  - Continue working with your virtual filesystem!")
    print("=" * 60)

if __name__ == "__main__":
    main()