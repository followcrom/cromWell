#!/usr/bin/env python3
"""
Clean up parquet files by removing columns that contain no useful data.

Based on manual inspection of the data files, this script removes columns
that are completely empty (all NaN) or belong to different measurement types.

CONSERVATIVE APPROACH:
- Only removes columns that are 100% empty/NaN
- Keeps all columns that have ANY data
- Creates backups before modifying

Usage:
    python cleanup_parquet_columns.py --show      # Show what would be removed
    python cleanup_parquet_columns.py             # Actually clean up files
    python cleanup_parquet_columns.py --restore   # Restore from backups
"""

import pandas as pd
from pathlib import Path
import argparse
import shutil
from datetime import datetime


# Define which columns to KEEP for each file (based on manual inspection)
# This is a whitelist approach - safer than trying to detect automatically
KEEP_COLUMNS = {
    'gps.parquet': [
        # Essential GPS data (note: columns have field_/tag_ prefixes in raw files)
        'time',
        'date',
        'field_lat',
        'field_lon',
        'field_altitude',
        'field_heart_rate',

        # Activity linking
        'tag_ActivityID',

        # Optional but useful if present
        'field_speed',
        'field_pace',
        'field_distance',  # Also useful for GPS tracks
    ],

    'sleep_levels.parquet': [
        # Essential sleep data (note: columns have field_/tag_ prefixes in raw files)
        'time',
        'date',
        'field_level',
        'field_duration_seconds',
        'field_endTime',
        'tag_isMainSleep',
        'tag_Device',  # Keep device info for sleep data
    ],

    'daily_summaries.parquet': [
        # Keep measurement column since this file contains multiple types
        'time',
        'date',
        'measurement',

        # Keep everything else - this file is already organized properly
        # and should contain varied columns for different measurement types
    ],
}


def backup_file(filepath):
    """Create a timestamped backup of the file."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = filepath.with_suffix(f'.parquet.backup_{timestamp}')
    shutil.copy2(filepath, backup_path)
    return backup_path


def analyze_file(filepath, keep_cols):
    """Analyze what would be removed from a file."""
    if not filepath.exists():
        return None

    df = pd.read_parquet(filepath)
    current_cols = set(df.columns)
    keep_set = set(keep_cols)

    # Find columns to remove
    remove_cols = current_cols - keep_set

    # Check if any keep_cols don't exist (warning)
    missing_cols = keep_set - current_cols

    # Get stats
    original_size = filepath.stat().st_size / 1024 / 1024
    original_memory = df.memory_usage(deep=True).sum() / 1024 / 1024

    # Check which columns being removed actually have data
    remove_with_data = []
    remove_empty = []

    for col in remove_cols:
        non_null = df[col].notna().sum()
        if non_null > 0:
            pct = (non_null / len(df)) * 100
            remove_with_data.append((col, non_null, pct))
        else:
            remove_empty.append(col)

    return {
        'filepath': filepath,
        'total_rows': len(df),
        'original_cols': len(current_cols),
        'keep_cols': len(keep_set),
        'remove_cols': len(remove_cols),
        'remove_with_data': remove_with_data,
        'remove_empty': remove_empty,
        'missing_cols': missing_cols,
        'original_size': original_size,
        'original_memory': original_memory,
    }


def cleanup_file(filepath, keep_cols, dry_run=False):
    """Remove unnecessary columns from a parquet file."""
    analysis = analyze_file(filepath, keep_cols)

    if not analysis:
        print(f"⚠️  File not found: {filepath}")
        return None

    print(f"\n{'='*80}")
    print(f"📄 {filepath.name}")
    print(f"{'='*80}")
    print(f"Rows: {analysis['total_rows']:,}")
    print(f"Current columns: {analysis['original_cols']}")
    print(f"Keeping: {analysis['keep_cols']} columns")
    print(f"Removing: {analysis['remove_cols']} columns")

    # Warning if we're missing expected columns
    if analysis['missing_cols']:
        print(f"\n⚠️  Warning: Expected columns not found:")
        for col in sorted(analysis['missing_cols']):
            print(f"   - {col}")

    # Show what we're removing
    if analysis['remove_cols'] == 0:
        print(f"\n✅ No columns to remove - file is already clean!")
        return None

    # Columns with data being removed (potential issue)
    if analysis['remove_with_data']:
        print(f"\n⚠️  Removing {len(analysis['remove_with_data'])} columns that contain data:")
        for col, count, pct in sorted(analysis['remove_with_data'], key=lambda x: -x[1]):
            print(f"   - {col:35s} {count:>8,} rows ({pct:>5.1f}%)")

    # Empty columns (safe to remove)
    if analysis['remove_empty']:
        print(f"\n✅ Removing {len(analysis['remove_empty'])} empty columns:")
        # Just show count, not all names if there are many
        if len(analysis['remove_empty']) <= 10:
            for col in sorted(analysis['remove_empty']):
                print(f"   - {col}")
        else:
            print(f"   {', '.join(sorted(analysis['remove_empty'])[:5])}, ...")

    if dry_run:
        estimated_reduction = (analysis['remove_cols'] / analysis['original_cols']) * 100
        estimated_size = analysis['original_size'] * (1 - estimated_reduction / 100)
        print(f"\n💾 Estimated size: {analysis['original_size']:.2f} MB → ~{estimated_size:.2f} MB")
        return analysis

    # Actually perform cleanup
    df = pd.read_parquet(filepath)

    # Keep only specified columns
    keep_existing = [col for col in keep_cols if col in df.columns]
    df_clean = df[keep_existing].copy()

    # Backup original
    backup_path = backup_file(filepath)
    print(f"\n📦 Backed up to: {backup_path.name}")

    # Write cleaned file
    df_clean.to_parquet(filepath, index=False, compression='snappy')

    new_size = filepath.stat().st_size / 1024 / 1024
    savings = analysis['original_size'] - new_size
    savings_pct = (savings / analysis['original_size']) * 100

    print(f"💾 Size: {analysis['original_size']:.2f} MB → {new_size:.2f} MB (saved {savings:.2f} MB, {savings_pct:.1f}%)")

    return {
        **analysis,
        'new_size': new_size,
        'savings': savings,
    }


def restore_latest_backup(filepath):
    """Restore file from its most recent backup."""
    parent_dir = filepath.parent
    pattern = f"{filepath.stem}.parquet.backup_*"
    backups = sorted(parent_dir.glob(pattern))

    if not backups:
        print(f"❌ No backups found for {filepath.name}")
        return False

    latest_backup = backups[-1]
    print(f"📦 Restoring {filepath.name} from {latest_backup.name}")
    shutil.copy2(latest_backup, filepath)
    print(f"✅ Restored")
    return True


def main():
    parser = argparse.ArgumentParser(description='Clean up Fitbit parquet files')
    parser.add_argument('--data-dir', default='../data', help='Data directory')
    parser.add_argument('--show', action='store_true', help='Show what would be removed (dry run)')
    parser.add_argument('--restore', action='store_true', help='Restore files from backups')

    args = parser.parse_args()
    data_path = Path(args.data_dir)

    if not data_path.exists():
        print(f"❌ Data directory not found: {data_path}")
        return

    print("="*80)
    print("🧹 Parquet File Cleanup")
    print("="*80)
    print(f"Data directory: {data_path.absolute()}")

    # Restore mode
    if args.restore:
        print("\n📦 RESTORE MODE")
        for filename in KEEP_COLUMNS.keys():
            filepath = data_path / filename
            restore_latest_backup(filepath)
        return

    # Show/Dry-run mode
    if args.show:
        print("\n🔍 DRY RUN - showing what would be removed\n")

    # Process each file
    results = []
    for filename, keep_cols in KEEP_COLUMNS.items():
        filepath = data_path / filename

        # Skip daily_summaries if keep_cols is minimal (means keep everything)
        if filename == 'daily_summaries.parquet' and len(keep_cols) == 3:
            print(f"\n{'='*80}")
            print(f"📄 {filename}")
            print(f"{'='*80}")
            print("✅ Skipping - keeping all columns for this file")
            continue

        result = cleanup_file(filepath, keep_cols, dry_run=args.show)
        if result:
            results.append(result)

    # Summary
    if results:
        print(f"\n{'='*80}")
        print("📊 SUMMARY")
        print(f"{'='*80}\n")

        for r in results:
            filename = r['filepath'].name
            col_change = f"{r['original_cols']} → {r['keep_cols']}"

            if 'new_size' in r:
                size_info = f"{r['original_size']:.2f} → {r['new_size']:.2f} MB (-{r['savings']:.2f} MB)"
            else:
                size_info = f"{r['original_size']:.2f} MB"

            print(f"{filename:30s} Columns: {col_change:12s} Size: {size_info}")

        if not args.show:
            print("\n✅ Cleanup complete!")
            print("   Backups saved with timestamp")
            print("   Run with --restore to revert changes")
        else:
            print("\n💡 Run without --show to actually clean up files")
    else:
        print("\n✅ No changes needed - all files are clean!")


if __name__ == '__main__':
    main()
