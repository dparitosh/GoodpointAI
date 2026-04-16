"""
Initialize Rule Engine Database Tables

Run this script to create the necessary tables for the PLM Rule Engine.
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from core.database import Base
from models.rule_engine_models import (
    RuleSet, Rule, RuleTemplate, 
    RuleSetExecution, RuleExecution, QuarantineRecord
)


def get_database_url():
    """Get database URL from environment."""
    host = os.getenv("POSTGRES_HOST", "127.0.0.1")
    port = os.getenv("POSTGRES_PORT", "5432")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "")
    database = os.getenv("POSTGRES_DB", "graphtrace")
    
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{database}"


def init_rule_engine_tables(drop_first=False):
    """Create rule engine tables."""
    database_url = get_database_url()
    print(f"Connecting to database: {database_url.replace(os.getenv('POSTGRES_PASSWORD', 'postgres'), '***')}")
    
    engine = create_engine(database_url)
    
    # Tables in order (considering foreign key dependencies)
    tables = [
        QuarantineRecord.__table__,
        RuleExecution.__table__,
        RuleSetExecution.__table__,
        Rule.__table__,
        RuleTemplate.__table__,
        RuleSet.__table__,
    ]
    
    if drop_first:
        print("\nDropping existing tables (in dependency order)...")
        for table in tables:
            try:
                table.drop(engine, checkfirst=True)
                print(f"  ✓ Dropped table: {table.name}")
            except Exception as e:
                print(f"  ✗ Error dropping table {table.name}: {e}")
    
    # Create tables (reverse order for foreign keys)
    create_order = [
        RuleSet.__table__,
        RuleTemplate.__table__,
        Rule.__table__,
        RuleSetExecution.__table__,
        RuleExecution.__table__,
        QuarantineRecord.__table__,
    ]
    
    print("\nCreating Rule Engine tables...")
    for table in create_order:
        try:
            table.create(engine, checkfirst=True)
            print(f"  ✓ Created/verified table: {table.name}")
        except Exception as e:
            print(f"  ✗ Error with table {table.name}: {e}")
    
    print("\nRule Engine database initialization complete!")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Initialize Rule Engine database tables")
    parser.add_argument("--drop", action="store_true", help="Drop existing tables first")
    args = parser.parse_args()
    init_rule_engine_tables(drop_first=args.drop)
