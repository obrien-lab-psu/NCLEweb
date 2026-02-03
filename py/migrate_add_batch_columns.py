#!/usr/bin/env python3
"""
Migration script to add batch submission columns to existing jobs table
"""

import sqlite3
from pathlib import Path
import sys

# Add py directory to path
sys.path.insert(0, str(Path(__file__).parent))

DB_PATH = Path(__file__).parent.parent / 'data' / 'ncle.db'

def migrate():
    """Add missing columns to jobs table"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Get existing columns
        cursor.execute("PRAGMA table_info(jobs)")
        existing_columns = {row[1] for row in cursor.fetchall()}
        
        print(f"Existing columns: {existing_columns}")
        
        # Columns to add
        columns_to_add = [
            ('batch_id', 'TEXT'),
            ('estimated_size', 'INTEGER'),
            ('queue_priority', 'INTEGER'),
            ('queue_position', 'INTEGER'),
        ]
        
        # Add missing columns
        for col_name, col_type in columns_to_add:
            if col_name not in existing_columns:
                print(f"Adding column: {col_name} ({col_type})")
                cursor.execute(f"ALTER TABLE jobs ADD COLUMN {col_name} {col_type}")
                print(f"  ✓ Added {col_name}")
            else:
                print(f"  → {col_name} already exists, skipping")
        
        # Add index for batch_id
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='ix_jobs_batch_id'")
        if not cursor.fetchone():
            print("Creating index for batch_id")
            cursor.execute("CREATE INDEX ix_jobs_batch_id ON jobs(batch_id)")
            print("  ✓ Created index")
        
        conn.commit()
        print("\n✓ Migration completed successfully!")
        
    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()
    
    return True

if __name__ == '__main__':
    if not DB_PATH.exists():
        print(f"Error: Database not found at {DB_PATH}")
        sys.exit(1)
    
    print(f"Database: {DB_PATH}")
    print("Starting migration...")
    
    if migrate():
        sys.exit(0)
    else:
        sys.exit(1)
