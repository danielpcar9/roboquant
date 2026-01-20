#!/usr/bin/env python3
"""
Script para actualizar automáticamente las importaciones del proyecto
de la estructura monolítica a la nueva arquitectura modular
"""

import re
from pathlib import Path


def update_imports_in_file(file_path: Path) -> bool:
    """
    Actualiza las importaciones en un archivo específico

    Args:
        file_path: Ruta al archivo a procesar

    Returns:
        bool: True si se realizaron cambios, False si no
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        original_content = content
        changes_made = False

        # Mapeo de importaciones antiguas a nuevas
        import_mappings = {
            # Componentes individuales
            "from core.donchian_components.calculators.technical_indicators import TechnicalIndicatorsCalculator as MarketDataService": "from core.donchian_components.calculators.technical_indicators import TechnicalIndicatorsCalculator as MarketDataService",
            "from core.donchian_strategy import DonchianStrategy": "from core.donchian_strategy import DonchianStrategy",
            "from core.donchian_components.validators.risk_market_validators import RiskValidator as RiskCalculator": "from core.donchian_components.validators.risk_market_validators import RiskValidator as RiskCalculator",
            "from core.donchian_components.validators.risk_market_validators import MarketValidator as SessionManager": "from core.donchian_components.validators.risk_market_validators import MarketValidator as SessionManager",
            # Imports completos
            "from core.donchian_components.calculators.technical_indicators import *\nfrom core.donchian_components.validators.risk_market_validators import *\nfrom core.donchian_components.managers.position_managers import *": (
                "from core.donchian_components.calculators.technical_indicators import *\n"
                "from core.donchian_components.validators.risk_market_validators import *\n"
                "from core.donchian_components.managers.position_managers import *"
            ),
            # Variables globales
            "# TRADE_ENTRY_SCORES moved to donchian_strategy.py main module": "# TRADE_ENTRY_SCORES moved to donchian_strategy.py main module",
            # Importaciones como módulo
            "# Module import updated - use specific component imports instead": "# Module import updated - use specific component imports instead",
        }

        # Aplicar las sustituciones
        for old_import, new_import in import_mappings.items():
            if old_import in content:
                content = content.replace(old_import, new_import)
                changes_made = True
                print(f"  ✓ Updated: {old_import}")

        # Manejar casos especiales
        if (
            "TRADE_ENTRY_SCORES" in content
            and "from core.donchian_strategy import" in content
        ):
            # Reemplazar referencias a TRADE_ENTRY_SCORES
            content = re.sub(
                r"from core\.donchian_strategy import TRADE_ENTRY_SCORES\s*\n?",
                "# TRADE_ENTRY_SCORES now managed in main strategy module\n",
                content,
            )
            changes_made = True

        # Guardar cambios si se realizaron
        if changes_made and content != original_content:
            backup_path = file_path.with_suffix(file_path.suffix + ".backup")
            # Crear backup
            with open(backup_path, "w", encoding="utf-8") as f:
                f.write(original_content)

            # Escribir nuevo contenido
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            print(f"  ✓ Changes saved to {file_path}")
            print(f"  ✓ Backup created: {backup_path}")
            return True

        return changes_made

    except Exception as e:
        print(f"  ✗ Error processing {file_path}: {e}")
        return False


def find_python_files(root_dir: str) -> list:
    """
    Encuentra todos los archivos Python en un directorio

    Args:
        root_dir: Directorio raíz para buscar

    Returns:
        list: Lista de rutas a archivos Python
    """
    python_files = []
    root_path = Path(root_dir)

    for py_file in root_path.rglob("*.py"):
        # Excluir directorios de tests y backups
        if "test" not in str(py_file).lower() and ".backup" not in str(py_file):
            python_files.append(py_file)

    return python_files


def main():
    """Función principal del script"""
    project_root = Path.cwd()
    print(f"🔍 Scanning project directory: {project_root}")

    # Encontrar archivos Python
    python_files = find_python_files(str(project_root))
    print(f"📁 Found {len(python_files)} Python files to process")

    files_updated = 0
    files_with_issues = []

    # Procesar cada archivo
    for file_path in python_files:
        print(f"\n📄 Processing: {file_path.relative_to(project_root)}")

        try:
            if update_imports_in_file(file_path):
                files_updated += 1
            else:
                print("  → No changes needed")
        except Exception as e:
            print(f"  ✗ Failed to process: {e}")
            files_with_issues.append((file_path, str(e)))

    # Reporte final
    print(f"\n{'=' * 60}")
    print("📊 UPDATE SUMMARY")
    print(f"{'=' * 60}")
    print(f"Files processed: {len(python_files)}")
    print(f"Files updated: {files_updated}")
    print(f"Files with issues: {len(files_with_issues)}")

    if files_with_issues:
        print("\n❌ Files with issues:")
        for file_path, error in files_with_issues:
            print(f"  • {file_path.relative_to(project_root)}: {error}")

    print("\n✅ Import update process completed!")
    print("💡 Remember to run tests to verify functionality")


if __name__ == "__main__":
    main()
