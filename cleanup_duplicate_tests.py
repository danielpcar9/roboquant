#!/usr/bin/env python3
"""
Cleanup Script for Duplicate Test Files
Identifies and removes duplicate/redundant test files based on audit findings
"""

import os
from pathlib import Path

# Duplicate test files to remove (keeping the most comprehensive version)
DUPLICATE_FILES_TO_REMOVE = [
    # Keep test_df.py, remove simple_test.py
    'simple_test.py',

    # Keep test_post_mortem.py, remove duplicates
    'simple_post_mortem_test.py',
    'test_like_post_mortem.py',

    # Keep test_detailed_connection.py, remove test_exness_symbol.py
    'test_exness_symbol.py',

    # Keep exact_test.py, remove test_csv_write.py
    'test_csv_write.py',

    # Keep test_mt5_connection.py, remove .test_login.py
    '.test_login.py',

    # Additional cleanup - redundant test files
    'test.py',  # Generic test file
]

def cleanup_duplicate_tests(dry_run=True):
    """
    Remove duplicate test files

    Args:
        dry_run: If True, only print what would be deleted without actually deleting
    """
    workspace = Path('/workspace')
    removed_count = 0

    print("🧹 Duplicate Test File Cleanup")
    print("=" * 60)

    if dry_run:
        print("⚠️  DRY RUN MODE - No files will be deleted")
        print()

    for filename in DUPLICATE_FILES_TO_REMOVE:
        file_path = workspace / filename

        if file_path.exists():
            file_size = file_path.stat().st_size

            if dry_run:
                print(f"Would remove: {filename} ({file_size} bytes)")
            else:
                try:
                    file_path.unlink()
                    print(f"✓ Removed: {filename} ({file_size} bytes)")
                    removed_count += 1
                except Exception as e:
                    print(f"✗ Failed to remove {filename}: {e}")
        else:
            print(f"⊘ Not found: {filename}")

    print()
    print("=" * 60)

    if dry_run:
        print(f"📊 Summary: {len(DUPLICATE_FILES_TO_REMOVE)} files would be removed")
        print()
        print("To actually remove files, run:")
        print("  python cleanup_duplicate_tests.py --execute")
    else:
        print(f"✅ Cleanup complete: {removed_count} files removed")

    return removed_count

if __name__ == "__main__":
    import sys

    # Check if --execute flag is provided
    execute = '--execute' in sys.argv or '-e' in sys.argv

    if execute:
        print("⚠️  EXECUTING CLEANUP - Files will be permanently deleted!")
        response = input("Are you sure you want to continue? (yes/no): ")

        if response.lower() == 'yes':
            cleanup_duplicate_tests(dry_run=False)
        else:
            print("Cleanup cancelled.")
    else:
        cleanup_duplicate_tests(dry_run=True)
