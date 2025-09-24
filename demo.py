#!/usr/bin/env python3
"""
Demo script showcasing dagshell's capabilities.

This demonstrates:
1. Content-addressable filesystem with immutable nodes
2. Soft deletes and garbage collection
3. Scheme DSL for filesystem manipulation
4. Python API for programmatic access
"""

import dagshell
from scheme_interpreter import SchemeREPL


def demo_python_api():
    """Demonstrate Python API usage."""
    print("=== Python API Demo ===")
    print()

    # Get a fresh filesystem
    fs = dagshell.FileSystem()

    # Create directory structure
    fs.mkdir("/home")
    fs.mkdir("/home/user")
    fs.mkdir("/home/user/documents")

    # Write files
    fs.write("/home/user/hello.txt", "Hello, World!")
    fs.write("/home/user/documents/note.txt", "Important note")

    # Show filesystem structure
    print("Directory listing of /home/user:")
    for item in fs.ls("/home/user"):
        stat = fs.stat(f"/home/user/{item}")
        print(f"  {item:<20} {stat['type']:<10} size={stat.get('size', 0)}")

    # Demonstrate content addressing
    print("\nContent addressing:")
    hash1 = fs.stat("/home/user/hello.txt")['hash']
    print(f"  Hash of hello.txt: {hash1[:16]}...")

    # Write identical content elsewhere
    fs.mkdir("/backup")
    fs.write("/backup/hello_copy.txt", "Hello, World!")
    hash2 = fs.stat("/backup/hello_copy.txt")['hash']
    print(f"  Hash of hello_copy.txt: {hash2[:16]}...")

    # Note: hashes will differ due to different mtime, but content is deduplicated

    # Demonstrate soft delete
    print("\nSoft delete demonstration:")
    print(f"  Nodes before delete: {len(fs.nodes)}")
    fs.rm("/backup/hello_copy.txt")
    print(f"  Nodes after soft delete: {len(fs.nodes)}")
    removed = fs.purge()
    print(f"  Nodes after purge: {len(fs.nodes)} ({removed} removed)")

    # Demonstrate devices
    print("\nVirtual devices:")
    with fs.open("/dev/random", "r") as f:
        random_bytes = f.read(8)
        print(f"  Read from /dev/random: {random_bytes.hex()}")

    with fs.open("/dev/zero", "r") as f:
        zeros = f.read(4)
        print(f"  Read from /dev/zero: {zeros.hex()}")

    print()


def demo_scheme_dsl():
    """Demonstrate Scheme DSL usage."""
    print("=== Scheme DSL Demo ===")
    print()

    repl = SchemeREPL()

    # Basic filesystem operations
    print("Creating project structure with Scheme:")
    script = '''
    (begin
      ;; Create a project structure
      (mkdir "/project")
      (mkdir "/project/src")
      (mkdir "/project/tests")
      (mkdir "/project/docs")

      ;; Create README
      (write-file "/project/README.md"
        "# My Project\n\nA demonstration of dagshell")

      ;; Create source file
      (write-file "/project/src/main.py"
        "def main():\n    print('Hello from dagshell!')")

      ;; Create test file
      (write-file "/project/tests/test_main.py"
        "def test_main():\n    assert True")

      ;; Return directory listing
      (ls "/project"))
    '''

    result = repl.eval_string(script)
    print(f"  Created structure: {result}")

    # Define helper functions
    print("\nDefining helper functions:")
    repl.eval_string('''
    (define file-size
      (lambda (path)
        (let ((stats (stat path)))
          (if stats
              (car (cdr (car (cdr (cdr (cdr (cdr (cdr stats))))))))
              0))))
    ''')

    repl.eval_string('''
    (define total-size
      (lambda (dir)
        (let ((entries (ls dir)))
          (if (null? entries)
              0
              (+ (file-size (string-append dir "/" (car entries)))
                 (total-size-helper dir (cdr entries)))))))
    ''')

    repl.eval_string('''
    (define total-size-helper
      (lambda (dir entries)
        (if (null? entries)
            0
            (+ (file-size (string-append dir "/" (car entries)))
               (total-size-helper dir (cdr entries))))))
    ''')

    # Use the helper function
    size = repl.eval_string('(file-size "/project/README.md")')
    print(f"  Size of README.md: {size} bytes")

    # Demonstrate higher-order functions
    print("\nHigher-order filesystem operations:")
    repl.eval_string('''
    (define with-temp-file
      (lambda (name content proc)
        (begin
          (write-file name content)
          (let ((result (proc name)))
            (rm name)
            result))))
    ''')

    result = repl.eval_string('''
    (with-temp-file "/tmp.txt" "temporary data"
      (lambda (path)
        (string-length (read-file path))))
    ''')
    print(f"  Temporary file had {result} characters")

    # Check that temp file is gone
    exists = repl.eval_string('(exists? "/tmp.txt")')
    print(f"  Temp file still exists: {exists}")

    print()


def demo_dag_structure():
    """Demonstrate the DAG nature of the filesystem."""
    print("=== DAG Structure Demo ===")
    print()

    fs = dagshell.FileSystem()

    # Create initial structure
    fs.mkdir("/data")
    fs.write("/data/file.txt", "Original content")

    # Get initial hash
    original_hash = fs.stat("/data/file.txt")['hash']
    print(f"Original file hash: {original_hash[:16]}...")

    # Modify the file
    fs.write("/data/file.txt", "Modified content")
    modified_hash = fs.stat("/data/file.txt")['hash']
    print(f"Modified file hash: {modified_hash[:16]}...")

    # Both versions exist in the DAG
    print(f"Total nodes in DAG: {len(fs.nodes)}")

    # The original is still there until we purge
    if original_hash in fs.nodes:
        original_node = fs.nodes[original_hash]
        print(f"Original content still in DAG: '{original_node.content.decode()}'")

    # After purge, unreferenced nodes are removed
    fs.purge()
    print(f"Nodes after purge: {len(fs.nodes)}")
    print(f"Original still exists: {original_hash in fs.nodes}")

    print()


def demo_serialization():
    """Demonstrate filesystem serialization."""
    print("=== Serialization Demo ===")
    print()

    # Create a filesystem with content
    fs = dagshell.FileSystem()
    fs.mkdir("/persistent")
    fs.write("/persistent/data.txt", "This will be saved")

    # Serialize to JSON
    json_str = fs.to_json()
    print(f"Serialized filesystem size: {len(json_str)} bytes")

    # Show a snippet of the JSON structure
    import json
    data = json.loads(json_str)
    print(f"Number of nodes: {len(data['nodes'])}")
    print(f"Number of path mappings: {len(data['paths'])}")

    # Deserialize into a new filesystem
    fs2 = dagshell.FileSystem.from_json(json_str)

    # Verify content is preserved
    content = fs2.read("/persistent/data.txt")
    print(f"Restored content: '{content.decode()}'")

    print()


def main():
    """Run all demos."""
    print("DagShell Demo - Content-Addressable Virtual Filesystem")
    print("=" * 60)
    print()

    demo_python_api()
    demo_scheme_dsl()
    demo_dag_structure()
    demo_serialization()

    print("=" * 60)
    print("Demo complete!")
    print()
    print("To start the interactive Scheme REPL, run:")
    print("  python scheme_interpreter.py")
    print()
    print("To use the Python API directly:")
    print("  import dagshell")
    print("  fs = dagshell.FileSystem()")


if __name__ == "__main__":
    main()