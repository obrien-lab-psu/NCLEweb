#!/usr/bin/env python3
"""
Migration script to add structure_type and ent_detection_method columns to jobs table
"""

import sqlite3
import os
from datetime import datetime

def migrate():
    db_path = 'data/ncle.db'
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return
    
    # Backup database
    backup_path = f'data/ncle.db.backup_detection_method_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    import shutil
    shutil.copy2(db_path, backup_path)
    print(f"✅ Database backed up to: {backup_path}")
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(jobs)")
        columns = [col[1] for col in cursor.fetchall()]
        
        # Add structure_type column if it doesn't exist
        if 'structure_type' not in columns:
            cursor.execute("ALTER TABLE jobs ADD COLUMN structure_type VARCHAR DEFAULT 'EXP'")
            print("✅ Added structure_type column")
        else:
            print("ℹ️  structure_type column already exists")
        
        # Add ent_detection_method column if it doesn't exist
        if 'ent_detection_method' not in columns:
            cursor.execute("ALTER TABLE jobs ADD COLUMN ent_detection_method INTEGER DEFAULT 3")
            print("✅ Added ent_detection_method column")
        else:
            print("ℹ️  ent_detection_method column already exists")
        
        # Update existing rows with default values
        cursor.execute("UPDATE jobs SET structure_type = 'EXP' WHERE structure_type IS NULL")
        cursor.execute("UPDATE jobs SET ent_detection_method = 2 WHERE ent_detection_method IS NULL")
        
        conn.commit()
        print("✅ Migration completed successfully")
        print(f"   - structure_type: Default 'EXP' for existing jobs")
        print(f"   - ent_detection_method: Default 2 (TLN-based) for existing jobs")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Migration failed: {e}")
        raise
    
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
