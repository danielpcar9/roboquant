#!/usr/bin/env python3
"""Análisis de estructura de donchian_strategy.py"""


def read_file_lines(file_path: str) -> list[str]:
    """Read file lines."""
    with open(file_path, encoding="utf-8") as f:
        return f.readlines()


def calculate_general_stats(lines: list[str]) -> tuple[int, int, int, int]:
    """Calculate general statistics for the file."""
    total_lines = len(lines)
    code_lines = len([line for line in lines if line.strip() and not line.strip().startswith('#')])
    blank_lines = len([line for line in lines if not line.strip()])
    comment_lines = len([line for line in lines if line.strip().startswith('#')])

    return total_lines, code_lines, blank_lines, comment_lines


def print_general_stats(total_lines, code_lines, blank_lines, comment_lines):
    """Print general statistics"""
    print("📊 ESTADÍSTICAS GENERALES:")
    print(f"Total líneas: {total_lines}")
    print(f"Líneas de código: {code_lines}")
    print(f"Líneas en blanco: {blank_lines}")
    print(f"Comentarios: {comment_lines}")


def find_classes(lines: list[str]) -> list[tuple[int, str, str]]:
    """Find classes in the file."""
    classes = []
    for i, line in enumerate(lines):
        if line.strip().startswith("class "):
            class_line = line.strip()
            # Extraer nombre de clase
            class_name = class_line.split("(")[0].replace("class ", "").strip()
            classes.append((i + 1, class_name, class_line))
    return classes


def print_classes(classes):
    """Print found classes"""
    print(f"\n🏛️ CLASES ENCONTRADAS ({len(classes)}):")
    print("-" * 50)
    for line_num, class_name, _full_line in classes:
        print(f"Línea {line_num:4d}: {class_name}")


def find_methods(lines):
    """Find methods in the file"""
    methods = []
    current_class = None
    for i, line in enumerate(lines):
        # Detectar cambio de clase
        if line.strip().startswith("class "):
            current_class = line.strip().split("(")[0].replace("class ", "").strip()

        # Detectar métodos
        if line.strip().startswith("def ") and not line.strip().startswith(
            "def __",
        ):
            method_line = line.strip()
            method_name = method_line.split("(")[0].replace("def ", "").strip()
            if current_class:
                methods.append((i + 1, current_class, method_name))
    return methods


def print_methods(methods):
    """Print found methods"""
    print("\n🔧 MÉTODOS PRINCIPALES:")
    print("-" * 50)
    class_methods = {}
    for line_num, class_name, method_name in methods:
        if class_name not in class_methods:
            class_methods[class_name] = []
        class_methods[class_name].append((line_num, method_name))

    for class_name, method_list in class_methods.items():
        print(f"\n{class_name}:")
        for line_num, method_name in method_list[:10]:  # Mostrar primeros 10
            print(f"  Línea {line_num:4d}: {method_name}")
        if len(method_list) > 10:
            print(f"  ... y {len(method_list) - 10} métodos más")


def identify_thematic_sections(lines):
    """Identify thematic sections in the file"""
    section_keywords = {
        "technical_indicators": ["calculate_", "atr", "rsi", "macd", "bollinger"],
        "signal_generation": ["generate_", "signal", "entry", "exit"],
        "position_management": ["position", "lot", "size", "risk"],
        "market_validation": ["filter", "validate", "check_market"],
        "risk_management": ["stop_loss", "take_profit", "risk"],
        "trade_execution": ["execute", "open", "close", "order"],
    }

    sections_found = {}
    for section, keywords in section_keywords.items():
        matching_lines = []
        for i, line in enumerate(lines):
            line_lower = line.lower()
            if any(keyword in line_lower for keyword in keywords):
                matching_lines.append(i + 1)
        if matching_lines:
            sections_found[section] = matching_lines
    return sections_found


def print_thematic_sections(sections_found):
    """Print thematic sections found"""
    print("\n📂 SECCIONES TEMÁTICAS IDENTIFICADAS:")
    print("-" * 50)

    for section, line_numbers in sections_found.items():
        print(
            f"{section.replace('_', ' ').title()}: {len(line_numbers)} líneas encontradas",
        )
        # Mostrar primeras y últimas líneas como ejemplo
        if len(line_numbers) <= 10:
            print(f"  Líneas: {line_numbers}")
        else:
            print(f"  Líneas: {line_numbers[:5]} ... {line_numbers[-5:]}")


def analyze_donchian_structure():
    """Analyze donchian_strategy.py structure."""
    print("🔍 ANALIZANDO ESTRUCTURA DE donchian_strategy.py\n")

    try:
        lines = read_file_lines("core/donchian_strategy.py")

        total_lines, code_lines, blank_lines, comment_lines = calculate_general_stats(lines)
        print_general_stats(total_lines, code_lines, blank_lines, comment_lines)

        classes = find_classes(lines)
        print_classes(classes)

        methods = find_methods(lines)
        print_methods(methods)

        sections_found = identify_thematic_sections(lines)
        print_thematic_sections(sections_found)

        return {
            "total_lines": len(lines),
            "classes": classes,
            "methods": methods,
            "sections": sections_found,
        }

    except Exception as e:
        print(f"❌ Error analizando archivo: {e}")
        return None


if __name__ == "__main__":
    analyze_donchian_structure()
