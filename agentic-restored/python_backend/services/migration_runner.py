"""
Database Migration Runner

Utility for running database migrations to ensure schema consistency
and performance optimizations are applied.
"""

import logging
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


class MigrationRunner:
    """Manages database migrations."""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine: Engine | None = None
    
    def connect(self) -> Engine:
        """Connect to database."""
        if self.engine is None:
            self.engine = create_engine(self.database_url, echo=False)
            logger.info("Connected to database: %s", self.database_url.split("@")[-1])
        return self.engine
    
    def run_migrations(self) -> None:
        """Run all pending migrations."""
        engine = self.connect()
        
        logger.info("Starting database migrations...")
        
        try:
            # Import migrations
            from services.migrations.add_performance_indexes import migrate_up as add_indexes
            
            # Run migration
            logger.info("Running migration: add_performance_indexes")
            add_indexes(engine)
            logger.info("✓ Migration completed successfully")
            
        except Exception as e:
            logger.error("Migration failed: %s", e)
            raise
    
    def check_schema(self) -> dict:
        """Check database schema health."""
        engine = self.connect()
        
        checks = {
            "tables": self._check_tables(engine),
            "indexes": self._check_indexes(engine),
            "constraints": self._check_constraints(engine),
        }
        
        return checks
    
    def _check_tables(self, engine: Engine) -> list:
        """Check for required tables."""
        with engine.connect() as conn:
            query = text("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name
            """)
            result = conn.execute(query)
            return [row[0] for row in result.fetchall()]
    
    def _check_indexes(self, engine: Engine) -> dict:
        """Check for performance indexes."""
        with engine.connect() as conn:
            query = text("""
                SELECT
                    tablename,
                    indexname,
                    indexdef
                FROM pg_indexes
                WHERE schemaname = 'public'
                ORDER BY tablename, indexname
            """)
            result = conn.execute(query)
            
            indexes_by_table = {}
            for table, idx_name, idx_def in result.fetchall():
                if table not in indexes_by_table:
                    indexes_by_table[table] = []
                indexes_by_table[table].append({
                    "name": idx_name,
                    "definition": idx_def
                })
            
            return indexes_by_table
    
    def _check_constraints(self, engine: Engine) -> dict:
        """Check for table constraints."""
        with engine.connect() as conn:
            query = text("""
                SELECT
                    table_name,
                    constraint_name,
                    constraint_type
                FROM information_schema.table_constraints
                WHERE table_schema = 'public'
                ORDER BY table_name, constraint_name
            """)
            result = conn.execute(query)
            
            constraints_by_table = {}
            for table, constraint, const_type in result.fetchall():
                if table not in constraints_by_table:
                    constraints_by_table[table] = []
                constraints_by_table[table].append({
                    "name": constraint,
                    "type": const_type
                })
            
            return constraints_by_table


# Entry point for running migrations at startup
def ensure_migrations_run(database_url: str) -> bool:
    """
    Run migrations if not already done.
    This should be called at application startup.
    """
    try:
        runner = MigrationRunner(database_url)
        runner.run_migrations()
        return True
    except Exception as e:
        logger.warning("Failed to run migrations: %s", e)
        return False
