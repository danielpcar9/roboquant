#!/usr/bin/env python3
"""
Analizador de tamaño de archivos Python para identificar archivos muy largos
"""

from pathlib import Path


def analyze_python_files():
    """Analiza todos los archivos .py y muestra los más largos"""
    print("🔍 ANALIZANDO ARCHIVOS PYTHON POR TAMAÑO\n")
    print("=" * 50)

    # Recopilar información de archivos (excluyendo .venv)
    files_info = []
    for py_file in Path(".").rglob("*.py"):
        # Excluir directorio virtual y archivos de sistema
        if ".venv" in str(py_file) or "__pycache__" in str(py_file):
            continue

        try:
            # Contar líneas ignorando líneas vacías y comentarios
            with open(py_file, encoding="utf-8") as f:
                lines = f.readlines()

            # Filtrar líneas vacías y comentarios
            code_lines = [
                line
                for line in lines
                if line.strip() and not line.strip().startswith("#")
            ]

            files_info.append(
                {
                    "path": str(py_file.relative_to(".")),
                    "total_lines": len(lines),
                    "code_lines": len(code_lines),
                    "blank_lines": len([line for line in lines if not line.strip()]),
                },
            )
        except Exception as e:
            print(f"❌ Error leyendo {py_file}: {e}")

    # Ordenar por líneas totales (descendente)
    files_info.sort(key=lambda x: x["total_lines"], reverse=True)

    # Mostrar archivos más largos
    print("📁 ARCHIVOS MÁS LARGOS (>300 líneas):")
    print("-" * 50)

    long_files = [f for f in files_info if f["total_lines"] > 300]

    for i, file_info in enumerate(long_files[:15], 1):
        print(f"{i:2d}. {file_info['path']}")
        print(
            f"    Total: {file_info['total_lines']:4d} líneas | "
            f"Código: {file_info['code_lines']:4d} líneas | "
            f"Vacías: {file_info['blank_lines']:3d}",
        )

        # Alertas según tamaño
        if file_info["total_lines"] > 1000:
            print("    ⚠️  MUY LARGO - REFACTORIZAR URGENTE!")
        elif file_info["total_lines"] > 800:
            print("    ⚠️  LARGO - Considerar división")
        elif file_info["total_lines"] > 600:
            print("    ⚠️  Moderadamente largo")
        print()

    # Estadísticas generales
    print("\n📊 ESTADÍSTICAS GENERALES:")
    print("-" * 30)
    total_files = len(files_info)
    long_count = len([f for f in files_info if f["total_lines"] > 500])
    very_long_count = len([f for f in files_info if f["total_lines"] > 1000])

    print(f"Total archivos Python: {total_files}")
    print(f"Archivos >500 líneas: {long_count} ({long_count / total_files * 100:.1f}%)")
    print(
        f"Archivos >1000 líneas: {very_long_count} ({very_long_count / total_files * 100:.1f}%)",
    )

    if long_files:
        avg_length = sum(f["total_lines"] for f in long_files) / len(long_files)
        print(f"Promedio archivos largos: {avg_length:.0f} líneas")


if __name__ == "__main__":
    analyze_python_files()
