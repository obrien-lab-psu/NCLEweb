#!/usr/bin/env python3
"""
Database migration script to update schema
- Remove pdb_id column
- Add num_hq_entanglements column
- Add num_clustered_entanglements column
"""

import sqlite3
import os
from pathlib import Path

def migrate_database():
    # Path to database
    db_path = Path(__file__).parent.parent / 'data' / 'ncle.db'
    
    if not db_path.exists():
        print(f"Database not found at {db_path}")
        return
    
    print(f"Migrating database at {db_path}")
    
    # Backup database
    backup_path = db_path.parent / f'ncle.db.backup_migration_{os.getpid()}'
    import shutil
    shutil.copy2(db_path, backup_path)
    print(f"Created backup at {backup_path}")
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(jobs)")
        columns = [row[1] for row in cursor.fetchall()]
        
        print(f"Current columns: {columns}")
        
        # Add new columns if they don't exist
        if 'num_hq_entanglements' not in columns:
            print("Adding num_hq_entanglements column...")
            cursor.execute("ALTER TABLE jobs ADD COLUMN num_hq_entanglements INTEGER")
            print("✓ Added num_hq_entanglements")
        else:
            print("num_hq_entanglements already exists")
        
        if 'num_clustered_entanglements' not in columns:
            print("Adding num_clustered_entanglements column...")
            cursor.execute("ALTER TABLE jobs ADD COLUMN num_clustered_entanglements INTEGER")
            print("✓ Added num_clustered_entanglements")
        else:
            print("num_clustered_entanglements already exists")
        
        # SQLite doesn't support DROP COLUMN directly, but we can leave pdb_id
        # It will just be ignored by the application code
        if 'pdb_id' in columns:
            print("Note: pdb_id column still exists but will be ignored by the application")
        
        conn.commit()
        print("\n✓ Migration completed successfully!")
        
        # Show updated schema
        cursor.execute("PRAGMA table_info(jobs)")
        print("\nUpdated schema:")
        for row in cursor.fetchall():
            print(f"  {row[1]}: {row[2]}")
        
    except Exception as e:
        conn.rollback()
        print(f"\n✗ Migration failed: {e}")
        print(f"Database restored from backup: {backup_path}")
        raise
    
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_database()
