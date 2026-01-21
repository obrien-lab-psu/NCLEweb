#!/usr/bin/env python3
"""
Migration script to add rcsb_pdb_id column to jobs table
"""

import sqlite3
import shutil
from pathlib import Path
from datetime import datetime

def migrate_database():
    """Add rcsb_pdb_id column to jobs table"""
    
    # Get database path
    db_path = Path(__file__).parent.parent / 'data' / 'ncle.db'
    
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        return False
    
    # Create backup
    backup_path = db_path.parent / f"ncle.db.backup_rcsb_migration_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print(f"Creating backup at {backup_path}")
    shutil.copy2(db_path, backup_path)
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(jobs)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'rcsb_pdb_id' in columns:
            print("Column 'rcsb_pdb_id' already exists. Skipping migration.")
            return True
        
        # Add the new column
        print("Adding 'rcsb_pdb_id' column to jobs table...")
        cursor.execute("""
            ALTER TABLE jobs 
            ADD COLUMN rcsb_pdb_id TEXT
        """)
        
        # Create index on the new column for faster lookups
        print("Creating index on 'rcsb_pdb_id' column...")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_jobs_rcsb_pdb_id 
            ON jobs(rcsb_pdb_id)
        """)
        
        conn.commit()
        print("Migration completed successfully!")
        
        # Verify the change
        cursor.execute("PRAGMA table_info(jobs)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'rcsb_pdb_id' in columns:
            print(f"✓ Verified: 'rcsb_pdb_id' column exists")
        else:
            print(f"✗ Error: 'rcsb_pdb_id' column not found after migration")
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
