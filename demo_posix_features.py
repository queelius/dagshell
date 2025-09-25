#!/usr/bin/env python3
"""Demonstration of POSIX user/permission features in DagShell."""

from terminal import TerminalSession

def main():
    print("=" * 70)
    print("DagShell POSIX Features Demonstration")
    print("=" * 70)

    session = TerminalSession()

    # Demo 1: User system
    print("\n1. USER MANAGEMENT")
    print("-" * 30)
    commands = [
        ("whoami", "Show current user"),
        ("cat /etc/passwd", "View users"),
        ("su alice", "Switch to alice"),
        ("whoami", "Confirm user changed"),
        ("pwd", "Alice's home directory"),
        ("su root", "Switch to root"),
        ("whoami", "Now running as root"),
    ]

    for cmd, desc in commands:
        print(f"\n# {desc}")
        print(f"$ {cmd}")
        output = session.run_command(cmd)
        if output:
            print(output)

    # Demo 2: Create files with different permissions
    print("\n\n2. FILE PERMISSIONS")
    print("-" * 30)
    session.run_command("su user")  # Switch back to regular user

    commands = [
        ("mkdir /shared", "Create shared directory"),
        ("echo 'Public data' > /shared/public.txt", "Create public file"),
        ("echo 'Private data' > /shared/private.txt", "Create private file"),
        ("ls -la /shared", "List files with permissions"),
    ]

    for cmd, desc in commands:
        print(f"\n# {desc}")
        print(f"$ {cmd}")
        output = session.run_command(cmd)
        if output:
            print(output)

    # Demo 3: Export to real filesystem
    print("\n\n3. EXPORT TO REAL FILESYSTEM")
    print("-" * 30)

    import tempfile
    import os
    temp_dir = tempfile.mkdtemp(prefix="dagshell_demo_")

    commands = [
        ("mkdir /webapp", "Create web application structure"),
        ("echo '<!DOCTYPE html>' > /webapp/index.html", "Create HTML file"),
        ("mkdir /webapp/css", "Create CSS directory"),
        ("echo 'body { margin: 0; }' > /webapp/css/style.css", "Add stylesheet"),
        ("mkdir /webapp/js", "Create JS directory"),
        ("echo 'console.log(\"Ready\");' > /webapp/js/app.js", "Add JavaScript"),
        ("ls -la /webapp", "Show structure"),
        (f"export {temp_dir}", "Export to real filesystem"),
    ]

    for cmd, desc in commands:
        print(f"\n# {desc}")
        print(f"$ {cmd}")
        output = session.run_command(cmd)
        if output:
            print(output)

    # Verify export
    print(f"\n# Verify exported files in {temp_dir}:")
    for root, dirs, files in os.walk(temp_dir):
        level = root.replace(temp_dir, '').count(os.sep)
        indent = '  ' * level
        print(f"{indent}{os.path.basename(root)}/")
        subindent = '  ' * (level + 1)
        for file in files:
            print(f"{subindent}{file}")

    # Clean up
    import shutil
    shutil.rmtree(temp_dir)

    # Demo 4: Save and restore
    print("\n\n4. PERSISTENCE")
    print("-" * 30)

    commands = [
        ("save workspace.json", "Save current state"),
        ("rm -r /webapp", "Remove webapp"),
        ("ls /", "Verify it's gone"),
        ("load workspace.json", "Restore from saved state"),
        ("ls /webapp", "Webapp is back!"),
    ]

    for cmd, desc in commands:
        print(f"\n# {desc}")
        print(f"$ {cmd}")
        output = session.run_command(cmd)
        if output:
            print(output)

    # Clean up
    if os.path.exists("workspace.json"):
        os.remove("workspace.json")

    print("\n" + "=" * 70)
    print("Demo complete!")
    print("\nKey features demonstrated:")
    print("✓ User management (whoami, su)")
    print("✓ User database (/etc/passwd, /etc/group)")
    print("✓ File permissions")
    print("✓ Export to real filesystem")
    print("✓ Save/load virtual filesystem state")
    print("=" * 70)


if __name__ == "__main__":
    main()