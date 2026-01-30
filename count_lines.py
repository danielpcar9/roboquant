#!/usr/bin/env python3
"""Script simple para contar líneas en archivos Python"""

import os


def count_lines_simple():
    print("🔍 CONTANDO LÍNEAS EN ARCHIVOS PYTHON\n")

    # Get Python files excluding problematic directories
    py_files = _get_python_files()

    # Count lines for each file
    file_stats = _count_file_lines(py_files)

    # Display results
    _display_results(file_stats)


def _get_python_files():
    """Get list of Python files excluding problematic directories."""
    exclude_dirs = {".venv", "__pycache__", ".git", "node_modules"}
    py_files = []

    for root, dirs, files in os.walk("."):
        # Filter directories
        dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith(".")]

        # Skip excluded paths
        if any(excluded in root for excluded in [".venv", "__pycache__"]):
            continue

        # Collect Python files
        for file in files:
            if file.endswith(".py"):
                full_path = os.path.join(root, file)
                py_files.append(full_path)

    return py_files


def _count_file_lines(py_files):
    """Count lines for each Python file."""
    file_stats = []

    for file_path in py_files:
        try:
            with open(file_path, encoding="utf-8") as f:
                lines = f.readlines()

            rel_path = os.path.relpath(file_path, ".")
            total_lines = len(lines)

            if total_lines > 300:
                file_stats.append((rel_path, total_lines))

        except Exception as e:
            print(f"❌ Error {file_path}: {e}")

    return file_stats


def _display_results(file_stats):
    """Display file statistics and warnings."""
    # Sort files by line count
    file_stats.sort(key=lambda x: x[1], reverse=True)

    print("📁 ARCHIVOS MÁS LARGOS (>300 líneas):")
    print("=" * 50)

    for i, (path, lines) in enumerate(file_stats[:15], 1):
        print(f"{i:2d}. {path:<50} {lines:>4} líneas")
        _print_length_warning(lines)

    # Show statistics
    _print_statistics(file_stats)


def _print_length_warning(lines):
    """Print warning based on file length."""
    if lines > 1000:
        print("    ⚠️  MUY LARGO - REFACTORIZAR URGENTE!")
    elif lines > 800:
        print("    ⚠️  LARGO - Considerar división")
    elif lines > 600:
        print("    ⚠️  Moderadamente largo")


def _print_statistics(file_stats):
    """Print summary statistics."""
    total_files = len(file_stats)
    long_count = len([f for f, line_count in file_stats if line_count > 500])
    very_long_count = len([f for f, line_count in file_stats if line_count > 1000])

    print("\n📊 ESTADÍSTICAS:")
    print(f"Total archivos analizados: {total_files}")
    print(f"Archivos >500 líneas: {long_count}")
    print(f"Archivos >1000 líneas: {very_long_count}")


if __name__ == "__main__":
    count_lines_simple()
