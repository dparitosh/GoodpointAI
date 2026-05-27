#!/usr/bin/env python3
"""
Direct migration execution script for database setup.
"""
import sys
import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy.exc import SQLAlchemyError

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Load .env file explicitly
env_path = Path(__file__).parent / '.env'
if env_path.exists():
    load_dotenv(env_path, override=True)
    print(f"✅ Loaded .env from {env_path}")

# Get DATABASE_URL directly from environment
database_url = os.environ.get('DATABASE_URL')
if not database_url:
    print("❌ DATABASE_URL environment variable not set!")
    sys.exit(1)

print(f"📦 Database URL: {database_url.split('@')[1] if '@' in database_url else 'hidden'}")

from services.migration_runner import MigrationRunner

def main():
    """Run all pending migrations."""
    print("=" * 60)
    print("📦 Database Migration Runner")
    print("=" * 60)
    
    try:
        runner = MigrationRunner(database_url)
        
        print(f"\n🔗 Connecting to database...")
        runner.connect()
        print(f"✅ Connected successfully")
        
        print(f"\n🚀 Executing migrations...")
        runner.run_migrations()
        print(f"✅ All migrations completed successfully!\n")
        
        print(f"📊 Checking schema health...")
        schema_info = runner.check_schema()
        
        print(f"\n📈 Schema Health Report:")
        print(f"   Tables: {len(schema_info.get('tables', []))} total")
        print(f"   Indexes: {len(schema_info.get('indexes', []))} total")
        print(f"   Constraints: {len(schema_info.get('constraints', []))} total")
        
        print(f"\n📋 Index Details:")
        for idx in schema_info.get('indexes', []):
            print(f"   - {idx}")
        
        print(f"\n✅ Migration execution completed successfully!")
        return 0
        
    except (SQLAlchemyError, ValueError, RuntimeError, AttributeError) as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
