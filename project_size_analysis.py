#!/usr/bin/env python3
"""Script para analizar tamaño de archivos del proyecto (excluyendo .venv)"""

import os


def scan_directory(directory_path: str, project_root: str) -> list[tuple[str, int]]:
    """Scan a directory for Python files and count lines"""
    long_files = []

    for root, dirs, files in os.walk(directory_path):
        # Excluir subdirectorios innecesarios
        dirs[:] = [d for d in dirs if d not in ["__pycache__", ".git"]]

        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, encoding="utf-8") as f:
                        lines = f.readlines()

                    total_lines = len(lines)
                    rel_path = os.path.relpath(file_path, project_root)

                    if total_lines > 300:
                        long_files.append((rel_path, total_lines))
                        print(f"   📄 {file:<30} {total_lines:>4} líneas")
                except Exception as e:
                    print(f"   ❌ Error leyendo {file}: {e}")

    return long_files


def scan_root_files(project_root: str) -> list[tuple[str, int]]:
    """Scan root directory Python files"""
    long_files = []

    print("\n📁 Analizando archivos raíz:")
    for file in os.listdir(project_root):
        if file.endswith(".py") and file not in ["count_lines.py"]:
            file_path = os.path.join(project_root, file)
            try:
                with open(file_path, encoding="utf-8") as f:
                    lines = f.readlines()

                total_lines = len(lines)
                if total_lines > 300:
                    long_files.append((file, total_lines))
                    print(f"   📄 {file:<30} {total_lines:>4} líneas")
            except Exception as e:
                print(f"   ❌ Error leyendo {file}: {e}")

    return long_files


def print_file_analysis(long_files: list[tuple[str, int]]) -> None:
    """Print detailed file analysis"""
    long_files.sort(key=lambda x: x[1], reverse=True)

    print(f"\n{'=' * 60}")
    print("🎯 ARCHIVOS MÁS LARGOS DEL PROYECTO:")
    print("=" * 60)

    for i, (path, lines) in enumerate(long_files[:20], 1):
        print(f"{i:2d}. {path:<50} {lines:>4} líneas")

        if lines > 1000:
            print("    ⚠️  MUY LARGO - REFACTORIZAR URGENTE!")
        elif lines > 800:
            print("    ⚠️  LARGO - Considerar división")
        elif lines > 600:
            print("    ⚠️  Moderadamente largo")
        elif lines > 500:
            print("    ℹ️  Largo pero manejable")


def print_statistics(long_files: list[tuple[str, int]]) -> None:
    """Print project statistics"""
    print("\n📊 ESTADÍSTICAS DEL PROYECTO:")
    print("=" * 40)
    total_files = len(long_files)
    very_long = len([f for f, line_count in long_files if line_count > 1000])
    long = len([f for f, line_count in long_files if 800 <= line_count <= 1000])
    moderate = len([f for f, line_count in long_files if 600 <= line_count < 800])
    acceptable = len([f for f, line_count in long_files if 500 <= line_count < 600])

    print(f"Archivos >1000 líneas: {very_long}")
    print(f"Archivos 800-1000 líneas: {long}")
    print(f"Archivos 600-800 líneas: {moderate}")
    print(f"Archivos 500-600 líneas: {acceptable}")
    print(f"Total archivos largos: {total_files}")


def analyze_project_files():
    print("🔍 ANALIZANDO ARCHIVOS DEL PROYECTO ROBOQUANT\n")
    print("=" * 60)

    # Obtener el directorio raíz del proyecto
    project_root = os.getcwd()
    print(f"Directorio del proyecto: {project_root}")

    # Archivos largos encontrados
    long_files = []

    # Recorrer solo directorios del proyecto principal
    project_dirs = [
        "core",
        "services",
        "brokers",
        "risk",
        "analysis",
        "tests_integration",
        "scripts",
    ]

    for dir_name in project_dirs:
        dir_path = os.path.join(project_root, dir_name)
        if os.path.exists(dir_path):
            print(f"\n📁 Analizando directorio: {dir_name}")
            dir_files = scan_directory(dir_path, project_root)
            long_files.extend(dir_files)

    # También revisar archivos en la raíz
    root_files = scan_root_files(project_root)
    long_files.extend(root_files)

    # Mostrar resultados
    print_file_analysis(long_files)
    print_statistics(long_files)


if __name__ == "__main__":
    analyze_project_files()
