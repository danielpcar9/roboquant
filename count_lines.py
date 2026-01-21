#!/usr/bin/env python3
"""Script simple para contar líneas en archivos Python"""

import os


def count_lines_simple():
    print("🔍 CONTANDO LÍNEAS EN ARCHIVOS PYTHON\n")

    # Directorios a excluir
    exclude_dirs = {".venv", "__pycache__", ".git", "node_modules"}

    # Encontrar archivos Python (solo en directorios del proyecto)
    py_files = []
    for root, dirs, files in os.walk("."):
        # Excluir directorios problemáticos
        dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith(".")]

        # Solo procesar archivos en el directorio principal del proyecto
        if ".venv" in root or "__pycache__" in root:
            continue

        for file in files:
            if file.endswith(".py"):
                full_path = os.path.join(root, file)
                py_files.append(full_path)

    # Contar líneas para cada archivo
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

    # Ordenar y mostrar resultados
    file_stats.sort(key=lambda x: x[1], reverse=True)

    print("📁 ARCHIVOS MÁS LARGOS (>300 líneas):")
    print("=" * 50)

    for i, (path, lines) in enumerate(file_stats[:15], 1):
        print(f"{i:2d}. {path:<50} {lines:>4} líneas")

        if lines > 1000:
            print("    ⚠️  MUY LARGO - REFACTORIZAR URGENTE!")
        elif lines > 800:
            print("    ⚠️  LARGO - Considerar división")
        elif lines > 600:
            print("    ⚠️  Moderadamente largo")

    # Estadísticas
    total_files = len(file_stats)
    long_count = len([f for f, line_count in file_stats if line_count > 500])
    very_long_count = len([f for f, line_count in file_stats if line_count > 1000])

    print("\n📊 ESTADÍSTICAS:")
    print(f"Total archivos analizados: {total_files}")
    print(f"Archivos >500 líneas: {long_count}")
    print(f"Archivos >1000 líneas: {very_long_count}")


if __name__ == "__main__":
    count_lines_simple()
