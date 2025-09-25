#!/usr/bin/env python3
"""
Interactive test script for the terminal emulator.

This script allows manual testing of the terminal emulator functionality.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dagshell.terminal import TerminalSession, TerminalConfig
from dagshell.dagshell_fluent import DagShell


def test_commands():
    """Test a series of commands programmatically."""
    print("Testing terminal emulator programmatically...")
    print("=" * 60)

    # Create session
    config = TerminalConfig(
        user='test',
        hostname='dagshell',
        home_dir='/home/test'
    )
    session = TerminalSession(config=config)

    # Test commands
    test_cases = [
        ("pwd", "/"),
        ("echo hello", "hello"),
        ("echo hello world", "hello world"),
        ("ls | grep dev", "dev"),
        ("cd /dev && pwd", "/dev"),
        ("cd / ; pwd", "/"),
        ("echo test > /tmp/test.txt && cat /tmp/test.txt", "test"),
        ("ls -la | head -n 2 | wc -l", "2"),
    ]

    passed = 0
    failed = 0

    for cmd, expected in test_cases:
        print(f"\nCommand: {cmd}")
        result = session.execute_command(cmd)
        print(f"Output: {result}")

        if expected in str(result):
            print("✓ PASSED")
            passed += 1
        else:
            print(f"✗ FAILED: Expected '{expected}' in output")
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    return failed == 0


def main():
    """Main entry point."""
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "test":
        success = test_commands()
        sys.exit(0 if success else 1)
    else:
        print("Starting interactive terminal emulator...")
        print("Type 'help' for help, 'exit' to quit\n")

        config = TerminalConfig(
            user='user',
            hostname='dagshell',
            home_dir='/home/user'
        )

        # Create some test data
        shell = DagShell()
        shell.fs.mkdir('/home')
        shell.fs.mkdir('/home/user')
        shell.fs.write('/home/user/test.txt', b'Test file content\n')
        shell.fs.write('/home/user/data.txt', b'Line 1\nLine 2\nLine 3\n')

        session = TerminalSession(config=config, shell=shell)
        session.run_interactive()


if __name__ == '__main__':
    main()