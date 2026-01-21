#!/usr/bin/env python3
"""
Migration script to add skipped_chains column to jobs table
"""

import sqlite3
import shutil
from pathlib import Path
from datetime import datetime

def migrate_database():
    """Add skipped_chains column to jobs table"""
    
    # Get database path
    db_path = Path(__file__).parent.parent / 'data' / 'ncle.db'
    
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        return False
    
    # Create backup
    backup_path = db_path.parent / f"ncle.db.backup_skipped_chains_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print(f"Creating backup at {backup_path}")
    shutil.copy2(db_path, backup_path)
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(jobs)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'skipped_chains' in columns:
            print("Column 'skipped_chains' already exists. Skipping migration.")
            return True
        
        # Add the new column
        print("Adding 'skipped_chains' column to jobs table...")
        cursor.execute("""
            ALTER TABLE jobs 
            ADD COLUMN skipped_chains TEXT
        """)
        
        conn.commit()
        print("Migration completed successfully!")
        
        # Verify the change
        cursor.execute("PRAGMA table_info(jobs)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'skipped_chains' in columns:
            print(f"✓ Verified: 'skipped_chains' column exists")
        else:
            print(f"✗ Error: 'skipped_chains' column not found after migration")
            return False
        
        return True
        
    except Exception as e:
        print(f"Error during migration: {e}")
        conn.rollback()
        return False
        
    finally:
        conn.close()

if __name__ == "__main__":
    success = migrate_database()
    exit(0 if success else 1)
