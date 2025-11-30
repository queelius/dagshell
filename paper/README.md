# DagShell Technical Paper

This directory contains the technical paper describing DagShell's design, implementation, and evaluation.

## Building the Paper

### Requirements

- LaTeX distribution (TeX Live, MiKTeX, or MacTeX)
- pdflatex command

### Building

```bash
# Build PDF
make

# Or manually:
pdflatex dagshell.tex
pdflatex dagshell.tex  # Run twice for references
```

### Output

The build process generates `dagshell.pdf`.

## Paper Structure

The paper is organized as follows:

1. **Abstract** - Overview of DagShell and contributions
2. **Introduction** - Motivation and background
3. **Design** - Architecture, node types, and core concepts
4. **Implementation** - Details of Python API, Scheme DSL, and Terminal
5. **Features** - POSIX compliance, permissions, persistence
6. **Use Cases** - Testing, sandboxing, pipelines, reproducible builds
7. **Evaluation** - Test coverage and performance analysis
8. **Related Work** - Comparison with Git, IPFS, Nix, FUSE, Plan 9
9. **Future Work** - Compression, distribution, garbage collection
10. **Conclusion** - Summary and implications

## Key Highlights

- **Content-Addressable DAG**: SHA256-based immutable nodes
- **Triple Interface**: Python API, Scheme DSL, Terminal emulator
- **POSIX Compliance**: Standard filesystem operations
- **99% Test Coverage**: 243 tests across 10 comprehensive suites
- **Practical Applications**: Testing, sandboxing, data pipelines

## Viewing

```bash
# Open PDF (Linux/Mac)
make view

# Or open manually
xdg-open dagshell.pdf  # Linux
open dagshell.pdf      # macOS
```

## Paper Statistics

- **Length**: ~10 pages (two-column format)
- **Sections**: 9 main sections + bibliography
- **Code Examples**: 20+ listings demonstrating key concepts
- **References**: 9 citations to related work
- **Test Coverage**: 99% across 243 tests

## Citation Format

If you use DagShell in academic work, please cite:

```bibtex
@article{dagshell2025,
  title={DagShell: A Content-Addressable Virtual Filesystem with Multiple Interface Paradigms},
  author={DagShell Project},
  year={2025}
}
```

## License

The paper is provided under the same MIT license as the DagShell project.
