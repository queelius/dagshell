#!/usr/bin/env python3
"""Test user permissions and export functionality."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dagshell.terminal import TerminalSession, TerminalConfig
from dagshell.dagshell_fluent import DagShell
import os
import tempfile
import shutil

def test_user_system():
    """Test user management features."""
    print("=" * 60)
    print("Testing User Management and Permissions")
    print("=" * 60)

    # Create session
    session = TerminalSession()

    # Test 1: Check initial user files
    print("\n1. Checking /etc/passwd and /etc/group:")
    output = session.run_command("cat /etc/passwd")
    print("Users:")
    print(output)

    output = session.run_command("cat /etc/group")
    print("\nGroups:")
    print(output)

    # Test 2: whoami command
    print("\n2. Testing whoami:")
    output = session.run_command("whoami")
    print(f"Current user: {output}")

    # Test 3: Switch users
    print("\n3. Testing su command:")
    print(f"Initial user: {session.run_command('whoami')}")

    session.run_command("su alice")
    print(f"After 'su alice': {session.run_command('whoami')}")

    session.run_command("su bob")
    print(f"After 'su bob': {session.run_command('whoami')}")

    session.run_command("su root")
    print(f"After 'su root': {session.run_command('whoami')}")

    # Test 4: Try invalid user
    print("\n4. Testing invalid user:")
    output = session.run_command("su nobody")
    print(f"Result: {output}")

    # Go back to normal user
    session.run_command("su user")

    print("\n" + "=" * 60)
    print("User management tests complete!")


def test_export():
    """Test export to real filesystem."""
    print("\n" + "=" * 60)
    print("Testing Export to Real Filesystem")
    print("=" * 60)

    # Create session and some test data
    session = TerminalSession()

    print("\n1. Creating test filesystem structure:")
    commands = [
        "mkdir /project",
        "echo '# Test Project' > /project/README.md",
        "mkdir /project/src",
        "echo 'print(\"Hello\")' > /project/src/main.py",
        "mkdir /project/docs",
        "echo 'Documentation' > /project/docs/guide.txt",
        "ls -la /project"
    ]

    for cmd in commands:
        print(f"$ {cmd}")
        output = session.run_command(cmd)
        if output:
            print(output)

    # Test export
    print("\n2. Exporting to real filesystem:")
    temp_dir = tempfile.mkdtemp(prefix="dagshell_export_")
    print(f"Export target: {temp_dir}")

    output = session.run_command(f"export {temp_dir}")
    print(output)

    # Verify exported files
    print("\n3. Verifying exported files:")
    for root, dirs, files in os.walk(temp_dir):
        level = root.replace(temp_dir, '').count(os.sep)
        indent = ' ' * 2 * level
        print(f"{indent}{os.path.basename(root)}/")
        subindent = ' ' * 2 * (level + 1)
        for file in files:
            filepath = os.path.join(root, file)
            size = os.path.getsize(filepath)
            print(f"{subindent}{file} ({size} bytes)")

    # Read a file to verify content
    readme_path = os.path.join(temp_dir, "project", "README.md")
    if os.path.exists(readme_path):
        with open(readme_path, 'r') as f:
            content = f.read()
        print(f"\n4. Content of exported README.md:")
        print(content)

    # Clean up
    shutil.rmtree(temp_dir)
    print(f"\n5. Cleaned up temporary directory: {temp_dir}")

    print("\n" + "=" * 60)
    print("Export tests complete!")


def test_permission_checking():
    """Test permission checking functionality."""
    print("\n" + "=" * 60)
    print("Testing Permission Checking")
    print("=" * 60)

    from dagshell.dagshell import FileSystem, Mode

    fs = FileSystem()

    # Create files with different permissions
    fs.write("/public.txt", b"Everyone can read this")
    fs.write("/private.txt", b"Only owner can read this")

    # Modify permissions
    node_hash = fs._resolve_path("/private.txt")
    node = fs.nodes[node_hash]
    # Create new node with restricted permissions (owner read/write only)
    import dagshell.dagshell as dagshell
    new_node = dagshell.FileNode(
        content=node.content,
        mode=Mode.IFREG | Mode.IRUSR | Mode.IWUSR,  # 0o600
        uid=1001,  # alice
        gid=1001
    )
    new_hash = fs._add_node(new_node)
    fs.paths["/private.txt"] = new_hash

    # Test permission checks
    print("\n1. Testing permission checks:")

    # Check as alice (uid=1001)
    alice_groups = fs.get_user_groups("alice")
    can_read = fs.check_permission("/private.txt", 1001, alice_groups, Mode.IRUSR)
    print(f"Alice can read /private.txt: {can_read}")

    # Check as bob (uid=1002)
    bob_groups = fs.get_user_groups("bob")
    can_read = fs.check_permission("/private.txt", 1002, bob_groups, Mode.IRUSR)
    print(f"Bob can read /private.txt: {can_read}")

    # Check as root (uid=0)
    root_groups = fs.get_user_groups("root")
    can_read = fs.check_permission("/private.txt", 0, root_groups, Mode.IRUSR)
    print(f"Root can read /private.txt: {can_read}")

    print("\n" + "=" * 60)
    print("Permission tests complete!")


if __name__ == "__main__":
    test_user_system()
    test_export()
    test_permission_checking()

    print("\n" + "=" * 60)
    print("All tests completed successfully!")
    print("=" * 60)