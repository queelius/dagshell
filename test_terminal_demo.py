#!/usr/bin/env python3
"""Quick demo of terminal features."""

from terminal import TerminalSession

# Create and run session
session = TerminalSession()

# Demo commands
commands = [
    "help",
    "mkdir /home/user",
    "cd /home/user",
    "echo 'Hello, DagShell!' > greeting.txt",
    "ls",
    "cat greeting.txt",
    "save my_filesystem.json",
    "rm greeting.txt",
    "ls",
    "load my_filesystem.json",
    "cat greeting.txt",
    "exit"
]

print("Running demo commands...")
print("-" * 50)

for cmd in commands:
    if cmd == "exit":
        print(f"user@dagshell:/home/user$ {cmd}")
        break
    print(f"user@dagshell:/home/user$ {cmd}")
    output = session.run_command(cmd)
    if output:
        print(output)
    print()

print("-" * 50)
print("Demo complete!")
print("\nThe filesystem has been saved to 'my_filesystem.json'")
print("You can load it anytime with: load my_filesystem.json")