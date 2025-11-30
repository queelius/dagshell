#!/usr/bin/env python3
"""
Integration tests for dagshell - testing Scheme DSL with filesystem operations.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import json
import tempfile
import os
import dagshell.dagshell as dagshell
from dagshell.scheme_interpreter import SchemeREPL


class TestSchemeFilesystemIntegration:
    """Comprehensive integration tests for Scheme DSL with filesystem."""

    def setup_method(self):
        """Reset filesystem before each test."""
        dagshell._default_fs = None

    def test_complete_filesystem_workflow(self):
        """Test complete filesystem workflow using Scheme DSL."""
        repl = SchemeREPL()

        # Define a helper function in Scheme
        repl.eval_string("""
            (define create-project
              (lambda (name)
                (begin
                  (mkdir (string-append "/" name))
                  (mkdir (string-append "/" name "/src"))
                  (mkdir (string-append "/" name "/tests"))
                  (mkdir (string-append "/" name "/docs"))
                  (write-file
                    (string-append "/" name "/README.md")
                    (string-append "# Project " name))
                  name)))
        """)

        # Create a project
        result = repl.eval_string('(create-project "myapp")')
        assert result == "myapp"

        # Verify structure was created
        assert repl.eval_string('(exists? "/myapp")') is True
        assert repl.eval_string('(exists? "/myapp/src")') is True
        assert repl.eval_string('(exists? "/myapp/tests")') is True
        assert repl.eval_string('(exists? "/myapp/docs")') is True
        assert repl.eval_string('(read-file "/myapp/README.md")') == "# Project myapp"

    def test_dag_versioning_through_scheme(self):
        """Test DAG versioning behavior through Scheme operations."""
        repl = SchemeREPL()

        # Create initial file
        repl.eval_string('(write-file "/data.txt" "version 1")')
        hash1 = repl.eval_string('(get-hash "/data.txt")')

        # Update file
        repl.eval_string('(write-file "/data.txt" "version 2")')
        hash2 = repl.eval_string('(get-hash "/data.txt")')

        # Hashes should be different
        assert hash1 != hash2

        # Both versions exist in the DAG (though only one is accessible via path)
        fs = dagshell.get_fs()
        assert hash1 in fs.nodes
        assert hash2 in fs.nodes

    def test_recursive_directory_operations(self):
        """Test recursive directory operations using Scheme."""
        repl = SchemeREPL()

        # Define recursive directory walker
        repl.eval_string("""
            (define walk-dir
              (lambda (path prefix)
                (let ((entries (ls path)))
                  (if (null? entries)
                      (display (string-append prefix path " [empty]"))
                      (begin
                        (display (string-append prefix path))
                        (newline)
                        entries)))))
        """)

        # Create nested structure
        repl.eval_string('(mkdir "/root")')
        repl.eval_string('(mkdir "/root/a")')
        repl.eval_string('(mkdir "/root/b")')
        repl.eval_string('(write-file "/root/a/file1.txt" "content1")')
        repl.eval_string('(write-file "/root/b/file2.txt" "content2")')

        # Walk directory
        result = repl.eval_string('(walk-dir "/root" "")')
        assert 'a' in result
        assert 'b' in result

    def test_content_deduplication(self):
        """Test that identical content is deduplicated in the DAG."""
        repl = SchemeREPL()

        # Create multiple files with same content
        # We need to ensure same mtime for proper deduplication testing
        fs = dagshell.get_fs()

        # Create files directly with fixed mtime
        fixed_time = 1000000.0
        fs.write('/file1.txt', 'identical content', mtime=fixed_time)
        fs.write('/file2.txt', 'identical content', mtime=fixed_time)
        fs.write('/file3.txt', 'identical content', mtime=fixed_time)

        # Get hashes through Scheme
        hash1 = repl.eval_string('(get-hash "/file1.txt")')
        hash2 = repl.eval_string('(get-hash "/file2.txt")')
        hash3 = repl.eval_string('(get-hash "/file3.txt")')

        # All should have same hash
        assert hash1 == hash2 == hash3

        # Only one node should exist for this content
        content_nodes = [n for n in fs.nodes.values()
                        if hasattr(n, 'content') and n.content == b'identical content']
        assert len(content_nodes) == 1

    def test_garbage_collection_workflow(self):
        """Test garbage collection through Scheme operations."""
        repl = SchemeREPL()

        # Create temporary files
        repl.eval_string('(mkdir "/temp")')
        repl.eval_string('(write-file "/temp/file1.txt" "temporary data 1")')
        repl.eval_string('(write-file "/temp/file2.txt" "temporary data 2")')
        repl.eval_string('(write-file "/keep.txt" "important data")')

        # Get initial node count
        fs = dagshell.get_fs()
        initial_nodes = len(fs.nodes)

        # Delete temporary files
        repl.eval_string('(rm "/temp/file1.txt")')
        repl.eval_string('(rm "/temp/file2.txt")')
        repl.eval_string('(rm "/temp")')

        # Nodes still exist before purge
        assert len(fs.nodes) >= initial_nodes

        # Run garbage collection
        removed = repl.eval_string('(purge)')
        assert removed > 0

        # Important file still exists
        assert repl.eval_string('(exists? "/keep.txt")') is True
        assert repl.eval_string('(read-file "/keep.txt")') == "important data"

        # Temp files are gone
        assert repl.eval_string('(exists? "/temp")') is False

    def test_filesystem_persistence(self):
        """Test saving and loading filesystem state through Scheme."""
        repl = SchemeREPL()

        # Create a complex filesystem
        repl.eval_string("""
            (begin
              (mkdir "/projects")
              (mkdir "/projects/web")
              (mkdir "/projects/api")
              (write-file "/projects/web/index.html" "<h1>Hello</h1>")
              (write-file "/projects/api/server.py" "from flask import Flask")
              (mkdir "/config")
              (write-file "/config/settings.json" "{\"debug\": true}")
            )
        """)

        # Save filesystem
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name

        try:
            result = repl.eval_string(f'(save "{temp_path}")')
            assert result is True

            # Reset filesystem
            dagshell._default_fs = dagshell.FileSystem()

            # Verify data is gone
            assert not dagshell.get_fs().exists('/projects')

            # Load filesystem
            result = repl.eval_string(f'(load "{temp_path}")')
            assert result is True

            # Verify data is restored
            assert repl.eval_string('(exists? "/projects/web/index.html")') is True
            assert repl.eval_string('(read-file "/projects/web/index.html")') == "<h1>Hello</h1>"
            assert repl.eval_string('(exists? "/config/settings.json")') is True

        finally:
            os.unlink(temp_path)

    def test_advanced_scheme_filesystem_functions(self):
        """Test advanced Scheme functions working with filesystem."""
        repl = SchemeREPL()

        # Define a file filter function
        repl.eval_string("""
            (define filter-by-extension
              (lambda (dir ext)
                (let ((files (ls dir)))
                  (if (null? files)
                      (list)
                      (filter-files files ext)))))

            (define filter-files
              (lambda (files ext)
                (if (null? files)
                    (list)
                    (let ((file (car files))
                          (rest (cdr files)))
                      (if (ends-with file ext)
                          (cons file (filter-files rest ext))
                          (filter-files rest ext))))))

            (define ends-with
              (lambda (str suffix)
                (let ((str-len (string-length str))
                      (suf-len (string-length suffix)))
                  (if (>= str-len suf-len)
                      (string=?
                        (substring str (- str-len suf-len))
                        suffix)
                      #f))))

            (define string=?
              (lambda (s1 s2) (= s1 s2)))
        """)

        # Create test files
        repl.eval_string('(mkdir "/docs")')
        repl.eval_string('(write-file "/docs/readme.txt" "Read this")')
        repl.eval_string('(write-file "/docs/notes.txt" "My notes")')
        repl.eval_string('(write-file "/docs/data.json" "{}")')
        repl.eval_string('(write-file "/docs/config.json" "{}")')

        # Filter by extension
        txt_files = repl.eval_string('(filter-by-extension "/docs" ".txt")')
        assert len(txt_files) == 2
        assert 'readme.txt' in txt_files
        assert 'notes.txt' in txt_files

        json_files = repl.eval_string('(filter-by-extension "/docs" ".json")')
        assert len(json_files) == 2
        assert 'data.json' in json_files
        assert 'config.json' in json_files

    def test_virtual_devices_through_scheme(self):
        """Test virtual device operations through Scheme."""
        repl = SchemeREPL()

        # Test that /dev/null exists
        assert repl.eval_string('(exists? "/dev/null")') is True
        assert repl.eval_string('(exists? "/dev/zero")') is True
        assert repl.eval_string('(exists? "/dev/random")') is True

        # Note: Direct write through fs.write() creates a regular file,
        # not using the device's special behavior. For full device support,
        # use file handles (fs.open). This tests existence only.

        # Virtual devices should always exist in /dev
        # Note: Current implementation doesn't prevent rm from returning True,
        # but the device should still exist (it's a virtual device)
        assert repl.eval_string('(directory? "/dev")') is True

    def test_scheme_error_handling_with_filesystem(self):
        """Test error handling in Scheme when filesystem operations fail."""
        repl = SchemeREPL()

        # Define error-handling wrapper
        repl.eval_string("""
            (define safe-write
              (lambda (path content)
                (if (write-file path content)
                    (string-append "Successfully wrote to " path)
                    (string-append "Failed to write to " path))))
        """)

        # Successful write
        result = repl.eval_string('(safe-write "/test.txt" "content")')
        assert "Successfully wrote" in result

        # Failed write (invalid parent)
        result = repl.eval_string('(safe-write "/nonexistent/test.txt" "content")')
        assert "Failed to write" in result

    def test_batch_operations(self):
        """Test batch filesystem operations through Scheme."""
        repl = SchemeREPL()

        # Define batch creation function
        repl.eval_string("""
            (define create-files
              (lambda (dir prefix count)
                (if (= count 0)
                    (list)
                    (let ((filename (string-append
                                    dir "/" prefix
                                    (number->string count) ".txt"))
                          (content (string-append
                                   "Content for file "
                                   (number->string count))))
                      (write-file filename content)
                      (cons filename
                            (create-files dir prefix (- count 1)))))))

            (define number->string
              (lambda (n)
                (if (= n 0) "0"
                    (if (= n 1) "1"
                        (if (= n 2) "2"
                            (if (= n 3) "3"
                                (if (= n 4) "4"
                                    (if (= n 5) "5"
                                        "many"))))))))
        """)

        # Create batch of files
        repl.eval_string('(mkdir "/batch")')
        files = repl.eval_string('(create-files "/batch" "file" 5)')

        # Verify files were created
        assert len(files) == 5
        assert repl.eval_string('(exists? "/batch/file1.txt")') is True
        assert repl.eval_string('(exists? "/batch/file5.txt")') is True

        # Verify content
        content = repl.eval_string('(read-file "/batch/file3.txt")')
        assert "Content for file 3" in content

    def test_filesystem_statistics(self):
        """Test gathering filesystem statistics through Scheme."""
        repl = SchemeREPL()

        # Define statistics gathering function
        repl.eval_string("""
            (define count-files-and-dirs
              (lambda (path)
                (let ((entries (ls path)))
                  (count-types entries path 0 0))))

            (define count-types
              (lambda (entries path files dirs)
                (if (null? entries)
                    (list files dirs)
                    (let* ((entry (car entries))
                           (entry-path (string-append path "/" entry))
                           (is-file (file? entry-path))
                           (is-dir (directory? entry-path)))
                      (count-types
                        (cdr entries)
                        path
                        (if is-file (+ files 1) files)
                        (if is-dir (+ dirs 1) dirs))))))
        """)

        # Create test structure
        repl.eval_string('(mkdir "/stats")')
        repl.eval_string('(mkdir "/stats/subdir1")')
        repl.eval_string('(mkdir "/stats/subdir2")')
        repl.eval_string('(write-file "/stats/file1.txt" "content")')
        repl.eval_string('(write-file "/stats/file2.txt" "content")')
        repl.eval_string('(write-file "/stats/file3.txt" "content")')

        # Count files and directories
        counts = repl.eval_string('(count-files-and-dirs "/stats")')
        assert counts == [3, 2]  # 3 files, 2 directories

    def test_concurrent_scheme_operations(self):
        """Test that multiple Scheme operations maintain filesystem consistency."""
        repl = SchemeREPL()

        # Define operations that modify same directory
        repl.eval_string("""
            (define operation1
              (lambda ()
                (begin
                  (mkdir "/concurrent")
                  (write-file "/concurrent/op1.txt" "from op1"))))

            (define operation2
              (lambda ()
                (write-file "/concurrent/op2.txt" "from op2")))
        """)

        # Execute operations
        repl.eval_string('(operation1)')
        repl.eval_string('(operation2)')

        # Verify both files exist
        assert repl.eval_string('(exists? "/concurrent/op1.txt")') is True
        assert repl.eval_string('(exists? "/concurrent/op2.txt")') is True

        # Verify content integrity
        assert repl.eval_string('(read-file "/concurrent/op1.txt")') == "from op1"
        assert repl.eval_string('(read-file "/concurrent/op2.txt")') == "from op2"


class TestComplexWorkflows:
    """Test complex real-world workflows."""

    def test_build_system_simulation(self):
        """Simulate a simple build system using Scheme and filesystem."""
        repl = SchemeREPL()

        # Define build system
        repl.eval_string("""
            (define build-project
              (lambda (name)
                (begin
                  ; Create project structure
                  (mkdir (string-append "/" name))
                  (mkdir (string-append "/" name "/src"))
                  (mkdir (string-append "/" name "/build"))

                  ; Simulate source files
                  (write-file
                    (string-append "/" name "/src/main.c")
                    "#include <stdio.h>\\nint main() { return 0; }")

                  ; Simulate build process
                  (write-file
                    (string-append "/" name "/build/main.o")
                    "compiled object file")

                  ; Create build log
                  (write-file
                    (string-append "/" name "/build.log")
                    (string-append "Build completed for " name))

                  ; Return build status
                  (list "success" name))))
        """)

        # Run build
        result = repl.eval_string('(build-project "myproject")')
        assert result == ['success', 'myproject']

        # Verify build artifacts
        assert repl.eval_string('(exists? "/myproject/src/main.c")') is True
        assert repl.eval_string('(exists? "/myproject/build/main.o")') is True
        assert repl.eval_string('(exists? "/myproject/build.log")') is True

    def test_configuration_management(self):
        """Test configuration file management workflow."""
        repl = SchemeREPL()

        # Define config management functions
        repl.eval_string("""
            (define create-config
              (lambda (env)
                (let ((config-dir (string-append "/config/" env)))
                  (begin
                    (mkdir "/config")
                    (mkdir config-dir)
                    (write-file
                      (string-append config-dir "/database.conf")
                      (string-append "host=" env ".db.example.com"))
                    (write-file
                      (string-append config-dir "/app.conf")
                      (string-append "debug="
                                   (if (= env "dev") "true" "false")))
                    config-dir))))
        """)

        # Create configurations for different environments
        dev_dir = repl.eval_string('(create-config "dev")')
        prod_dir = repl.eval_string('(create-config "prod")')

        # Verify configurations
        dev_db = repl.eval_string('(read-file "/config/dev/database.conf")')
        assert "dev.db.example.com" in dev_db

        prod_app = repl.eval_string('(read-file "/config/prod/app.conf")')
        assert "debug=false" in prod_app

    def test_data_pipeline(self):
        """Test a data processing pipeline using Scheme and filesystem."""
        repl = SchemeREPL()

        # Define data pipeline
        repl.eval_string("""
            (define process-data
              (lambda ()
                (begin
                  ; Stage 1: Input
                  (mkdir "/pipeline")
                  (mkdir "/pipeline/input")
                  (write-file "/pipeline/input/data.csv"
                             "id,value\\n1,100\\n2,200\\n3,300")

                  ; Stage 2: Processing
                  (mkdir "/pipeline/processing")
                  (let ((input (read-file "/pipeline/input/data.csv")))
                    (write-file "/pipeline/processing/processed.csv"
                               (string-append input "\\n4,400")))

                  ; Stage 3: Output
                  (mkdir "/pipeline/output")
                  (write-file "/pipeline/output/final.csv"
                             (read-file "/pipeline/processing/processed.csv"))

                  ; Create summary
                  (write-file "/pipeline/summary.txt"
                             "Pipeline completed successfully")

                  "completed")))
        """)

        # Run pipeline
        result = repl.eval_string('(process-data)')
        assert result == 'completed'

        # Verify pipeline stages
        assert repl.eval_string('(exists? "/pipeline/input/data.csv")') is True
        assert repl.eval_string('(exists? "/pipeline/processing/processed.csv")') is True
        assert repl.eval_string('(exists? "/pipeline/output/final.csv")') is True

        # Verify data transformation
        final_data = repl.eval_string('(read-file "/pipeline/output/final.csv")')
        assert "1,100" in final_data
        assert "4,400" in final_data  # Added by processing


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--cov=dagshell,scheme_interpreter', '--cov-report=term-missing'])