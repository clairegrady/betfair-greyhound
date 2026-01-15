"""
Automatically fix all betting scripts to use proper database connections
with timeout, retry logic, and WAL mode.
"""

import os
import re
from pathlib import Path

# Base directory
BASE_DIR = Path("/Users/clairegrady/RiderProjects/betfair")

# Scripts to fix
GREYHOUND_SCRIPTS = [
    BASE_DIR / "greyhound-predictor/lay_betting" / f"lay_position_{i}.py"
    for i in range(1, 9)
]

HORSE_SCRIPTS = [
    BASE_DIR / "horse-racing-predictor/lay_betting" / f"lay_position_{i}.py"
    for i in range(1, 19)
]

CHECK_RESULTS_SCRIPTS = [
    BASE_DIR / "greyhound-predictor/check_results_greyhounds.py",
    BASE_DIR / "horse-racing-predictor/check_results_horses.py",
]

BACKFILL_SCRIPT = BASE_DIR / "utilities/continuous_backfill_greyhound_data.py"

ALL_SCRIPTS = GREYHOUND_SCRIPTS + HORSE_SCRIPTS + CHECK_RESULTS_SCRIPTS + [BACKFILL_SCRIPT]


def add_import_if_missing(content: str) -> str:
    """Add db_connection_helper import if not present"""
    if "from utilities.db_connection_helper import" in content:
        return content
    
    # Find the last import statement
    import_lines = []
    other_lines = []
    in_imports = True
    
    for line in content.split('\n'):
        if in_imports and (line.startswith('import ') or line.startswith('from ')):
            import_lines.append(line)
        elif in_imports and line.strip() == '':
            import_lines.append(line)
        else:
            in_imports = False
            other_lines.append(line)
    
    # Add our import
    import_lines.append("import sys")
    import_lines.append("sys.path.insert(0, '/Users/clairegrady/RiderProjects/betfair')")
    import_lines.append("from utilities.db_connection_helper import get_db_connection, db_transaction")
    import_lines.append("")
    
    return '\n'.join(import_lines + other_lines)


def fix_simple_connection(content: str) -> str:
    """
    Replace simple sqlite3.connect() calls with get_db_connection()
    
    Pattern: conn = sqlite3.connect(DB_PATH)
    Replace: conn = get_db_connection(DB_PATH, timeout=30.0)
    """
    # Pattern 1: conn = sqlite3.connect(path)
    pattern1 = r'(\s+)conn = sqlite3\.connect\(([^)]+)\)'
    replacement1 = r'\1conn = get_db_connection(\2, timeout=30.0)'
    content = re.sub(pattern1, replacement1, content)
    
    # Pattern 2: connection = sqlite3.connect(path)
    pattern2 = r'(\s+)connection = sqlite3\.connect\(([^)]+)\)'
    replacement2 = r'\1connection = get_db_connection(\2, timeout=30.0)'
    content = re.sub(pattern2, replacement2, content)
    
    return content


def wrap_transaction_with_retry(content: str) -> str:
    """
    Wrap database write operations with db_transaction context manager
    
    This is more complex and may need manual review, so we'll add a comment
    """
    # Look for place_lay_bet or similar functions
    if "def place_lay_bet" in content:
        # Add a comment suggesting manual review
        content = content.replace(
            "def place_lay_bet",
            "# TODO: Consider wrapping INSERT operations with db_transaction() for automatic retry\n    def place_lay_bet"
        )
    
    return content


def fix_script(script_path: Path) -> bool:
    """Fix a single script"""
    try:
        if not script_path.exists():
            print(f"❌ Script not found: {script_path}")
            return False
        
        print(f"🔧 Fixing {script_path.name}...")
        
        # Read content
        with open(script_path, 'r') as f:
            content = f.read()
        
        # Apply fixes
        original_content = content
        content = add_import_if_missing(content)
        content = fix_simple_connection(content)
        content = wrap_transaction_with_retry(content)
        
        # Only write if changed
        if content != original_content:
            # Create backup
            backup_path = script_path.with_suffix('.py.backup')
            with open(backup_path, 'w') as f:
                f.write(original_content)
            
            # Write fixed version
            with open(script_path, 'w') as f:
                f.write(content)
            
            print(f"✅ Fixed {script_path.name} (backup: {backup_path.name})")
            return True
        else:
            print(f"ℹ️  {script_path.name} already fixed or no changes needed")
            return False
            
    except Exception as e:
        print(f"❌ Error fixing {script_path}: {e}")
        return False


def main():
    print("=" * 80)
    print("DATABASE CONNECTION FIX - AUTOMATED SCRIPT UPDATER")
    print("=" * 80)
    print()
    print("This script will:")
    print("  1. Add db_connection_helper imports")
    print("  2. Replace sqlite3.connect() with get_db_connection()")
    print("  3. Create .backup files of all modified scripts")
    print()
    print(f"Total scripts to fix: {len(ALL_SCRIPTS)}")
    print()
    
    input("Press ENTER to continue or Ctrl+C to cancel...")
    print()
    
    fixed_count = 0
    skipped_count = 0
    error_count = 0
    
    for script in ALL_SCRIPTS:
        result = fix_script(script)
        if result:
            fixed_count += 1
        elif script.exists():
            skipped_count += 1
        else:
            error_count += 1
    
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"✅ Fixed: {fixed_count}")
    print(f"ℹ️  Skipped: {skipped_count}")
    print(f"❌ Errors: {error_count}")
    print()
    
    if fixed_count > 0:
        print("⚠️  IMPORTANT: Review the changes before running the scripts!")
        print("   Backup files (.py.backup) have been created.")
        print()
        print("Next steps:")
        print("  1. Review a few fixed scripts to verify changes")
        print("  2. Test one script manually")
        print("  3. If successful, restart all scripts")
    
    print()


if __name__ == "__main__":
    main()
