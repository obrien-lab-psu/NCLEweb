#!/usr/bin/env python3
"""
Migration script to add missing columns to hq_results table
Adds: TLNn, TLNc, Quality, Reason
"""

import sqlite3
import shutil
from pathlib import Path
from datetime import datetime

def migrate_database():
    """Add missing columns to hq_results table"""
    
    # Get database path
    db_path = Path(__file__).parent.parent / 'data' / 'ncle.db'
    
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        return False
    
    # Create backup
    backup_path = db_path.parent / f"ncle.db.backup_hq_columns_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print(f"Creating backup at {backup_path}")
    shutil.copy2(db_path, backup_path)
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check which columns already exist
        cursor.execute("PRAGMA table_info(hq_results)")
        columns = {column[1]: column for column in cursor.fetchall()}
        
        columns_to_add = {
            'TLNn': 'INTEGER',
            'TLNc': 'INTEGER',
            'Quality': 'TEXT',
            'Reason': 'TEXT'
        }
        
        for col_name, col_type in columns_to_add.items():
            if col_name not in columns:
                print(f"Adding '{col_name}' column to hq_results table...")
                cursor.execute(f"""
                    ALTER TABLE hq_results 
                    ADD COLUMN {col_name} {col_type}
                """)
            else:
                print(f"Column '{col_name}' already exists. Skipping.")
        
        conn.commit()
        print("Migration completed successfully!")
        
        # Verify the changes
        cursor.execute("PRAGMA table_info(hq_results)")
        columns = {column[1] for column in cursor.fetchall()}
        print(f"hq_results table now has columns: {sorted(columns)}")
        
        return True
        
    except Exception as e:
        print(f"Error during migration: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    if migrate_database():
        print("\n✓ Migration successful!")
    else:
        print("\n✗ Migration failed!")
