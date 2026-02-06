#!/usr/bin/env python3
"""
MT5 Import Migration Script

This script automatically updates all direct MetaTrader5 imports to use
the cross-platform compatibility layer (core/mt5_compat.py).

Usage:
    python scripts/migrate_mt5_imports.py --dry-run  # Preview changes
    python scripts/migrate_mt5_imports.py            # Apply changes
"""

import argparse
import re
from pathlib import Path


# Files to skip (already using compat or are the compat module itself)
SKIP_FILES = {
    "core/mt5_compat.py",
    "ANALYSIS_REPORT.md",
}

# Files to skip entirely (backups, etc.)
SKIP_PATTERNS = [
    ".backup",
    "__pycache__",
    ".git",
    ".venv",
    "node_modules",
]


def should_process_file(filepath: Path, base_path: Path) -> bool:
    """Check if file should be processed."""
    rel_path = str(filepath.relative_to(base_path))
    
    # Skip if in skip list
    if rel_path in SKIP_FILES:
        return False
    
    # Skip if matches skip patterns
    for pattern in SKIP_PATTERNS:
        if pattern in str(filepath):
            return False
    
    # Only process Python files
    return filepath.suffix == ".py"


def migrate_imports(filepath: Path, dry_run: bool = True) -> tuple[bool, list[str]]:
    """
    Migrate MT5 imports in a file.
    
    Returns:
        Tuple of (was_modified, list of changes made)
    """
    changes = []
    
    try:
        content = filepath.read_text()
    except Exception as e:
        return False, [f"Error reading file: {e}"]
    
    original_content = content
    
    # Pattern 1: Simple import at top level
    # import MetaTrader5 as mt5
    pattern1 = r'^import MetaTrader5 as mt5(\s*#.*)?$'
    replacement1 = 'from core.mt5_compat import mt5, MT5_AVAILABLE'
    
    if re.search(pattern1, content, re.MULTILINE):
        content = re.sub(pattern1, replacement1, content, flags=re.MULTILINE)
        changes.append("Replaced top-level 'import MetaTrader5 as mt5'")
    
    # Pattern 2: Import inside function/method
    # Check for indented imports
    pattern2 = r'^(\s+)import MetaTrader5 as mt5(\s*#.*)?$'
    
    if re.search(pattern2, content, re.MULTILINE):
        # For indented imports, we need special handling
        # These are typically try/except or conditional imports
        content = re.sub(
            pattern2, 
            r'\1from core.mt5_compat import mt5, MT5_AVAILABLE', 
            content, 
            flags=re.MULTILINE
        )
        changes.append("Replaced indented 'import MetaTrader5 as mt5'")
    
    # Pattern 3: Try/except import pattern
    pattern3 = r'''try:\s*
\s*import MetaTrader5 as mt5\s*
\s*MT5_AVAILABLE = True\s*
except ImportError:\s*
\s*MT5_AVAILABLE = False\s*
\s*mt5 = None'''
    
    replacement3 = 'from core.mt5_compat import mt5, MT5_AVAILABLE'
    
    if re.search(pattern3, content, re.MULTILINE):
        content = re.sub(pattern3, replacement3, content, flags=re.MULTILINE)
        changes.append("Replaced try/except import pattern")
    
    # Check if content was modified
    was_modified = content != original_content
    
    if was_modified and not dry_run:
        filepath.write_text(content)
        changes.append("FILE MODIFIED")
    
    return was_modified, changes


def main():
    parser = argparse.ArgumentParser(description="Migrate MT5 imports to use compat layer")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without applying")
    parser.add_argument("--path", default=".", help="Base path to search")
    args = parser.parse_args()
    
    base_path = Path(args.path).resolve()
    
    print("=" * 70)
    print("  MT5 Import Migration Tool")
    print("=" * 70)
    print(f"Base path: {base_path}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'APPLY CHANGES'}")
    print("=" * 70)
    
    # Find all Python files
    python_files = list(base_path.rglob("*.py"))
    
    modified_files = []
    skipped_files = []
    error_files = []
    
    for filepath in python_files:
        if not should_process_file(filepath, base_path):
            skipped_files.append(filepath)
            continue
        
        was_modified, changes = migrate_imports(filepath, dry_run=args.dry_run)
        
        if was_modified:
            rel_path = filepath.relative_to(base_path)
            modified_files.append((rel_path, changes))
            print(f"\n✏️  {rel_path}")
            for change in changes:
                print(f"    - {change}")
    
    # Summary
    print("\n" + "=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    print(f"Total files scanned:  {len(python_files)}")
    print(f"Files to modify:      {len(modified_files)}")
    print(f"Files skipped:        {len(skipped_files)}")
    
    if args.dry_run and modified_files:
        print("\n⚠️  This was a dry run. No files were modified.")
        print("   Run without --dry-run to apply changes.")
    elif modified_files:
        print(f"\n✅ {len(modified_files)} files were modified.")
    else:
        print("\n✅ No files need to be modified.")
    
    print("=" * 70)
    
    return 0


if __name__ == "__main__":
    exit(main())
