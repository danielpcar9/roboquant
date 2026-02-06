#!/usr/bin/env python3
"""
Project Cleanup Script

Removes unnecessary files and organizes the project structure.
"""

import shutil
from pathlib import Path


def cleanup_debug_files(base_path: Path, dry_run: bool = True) -> list[Path]:
    """Remove debug files from the project root."""
    debug_patterns = [
        "debug_*.py",
        "minimal_*.py",
        "test_adx_filter.py",
    ]
    
    removed = []
    
    for pattern in debug_patterns:
        for file in base_path.glob(pattern):
            if file.is_file():
                if not dry_run:
                    file.unlink()
                removed.append(file)
                print(f"{'Would remove' if dry_run else 'Removed'}: {file.name}")
    
    return removed


def cleanup_backup_archive(base_path: Path, dry_run: bool = True) -> None:
    """Remove the backup archive folder."""
    backup_dir = base_path / ".backup_archive"
    
    if backup_dir.exists():
        if not dry_run:
            shutil.rmtree(backup_dir)
        print(f"{'Would remove' if dry_run else 'Removed'}: .backup_archive/")


def cleanup_cache_files(base_path: Path, dry_run: bool = True) -> list[Path]:
    """Remove cached and generated files."""
    patterns = [
        "**/__pycache__",
        "**/*.pyc",
        "**/.pytest_cache",
        "**/.ruff_cache",
    ]
    
    removed = []
    
    for pattern in patterns:
        for path in base_path.glob(pattern):
            if path.is_dir():
                if not dry_run:
                    shutil.rmtree(path)
                removed.append(path)
            elif path.is_file():
                if not dry_run:
                    path.unlink()
                removed.append(path)
    
    if removed:
        print(f"{'Would remove' if dry_run else 'Removed'}: {len(removed)} cache items")
    
    return removed


def organize_scripts(base_path: Path, dry_run: bool = True) -> None:
    """Organize scripts into appropriate directories."""
    scripts_dir = base_path / "scripts"
    
    # Move debug scripts to a deprecated folder
    deprecated_dir = scripts_dir / "deprecated"
    
    debug_scripts_in_scripts = list(scripts_dir.glob("debug_*.py"))
    
    if debug_scripts_in_scripts and not dry_run:
        deprecated_dir.mkdir(exist_ok=True)
        
        for script in debug_scripts_in_scripts:
            dest = deprecated_dir / script.name
            shutil.move(str(script), str(dest))
            print(f"Moved {script.name} to scripts/deprecated/")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Clean up RoboQuant project")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes")
    parser.add_argument("--path", default=".", help="Project base path")
    args = parser.parse_args()
    
    base_path = Path(args.path).resolve()
    
    print("=" * 70)
    print("  RoboQuant Project Cleanup")
    print("=" * 70)
    print(f"Base path: {base_path}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'APPLY CHANGES'}")
    print("=" * 70)
    
    print("\n📁 Cleaning debug files...")
    cleanup_debug_files(base_path, args.dry_run)
    
    print("\n📁 Cleaning backup archive...")
    cleanup_backup_archive(base_path, args.dry_run)
    
    print("\n📁 Cleaning cache files...")
    cleanup_cache_files(base_path, args.dry_run)
    
    print("\n📁 Organizing scripts...")
    organize_scripts(base_path, args.dry_run)
    
    print("\n" + "=" * 70)
    if args.dry_run:
        print("⚠️  This was a dry run. No files were modified.")
        print("   Run without --dry-run to apply changes.")
    else:
        print("✅ Cleanup complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
