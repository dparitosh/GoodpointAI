#!/usr/bin/env python
"""
Database Initialization Script for Data Quality Rules Engine

Creates the data_quality_rule_sets table in PostgreSQL.
This is run automatically on application startup but can also be run manually.

Usage:
    python -m scripts.init_dqre_db

Environment Variables:
    DATABASE_URL: PostgreSQL connection string (uses default if not set)
    GRAPH_TRACE_LOAD_DOTENV: Set to 'true' to load .env file
"""

import sys
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def init_dqre_tables():
    """Initialize DQRE tables"""
    try:
        logger.info("=" * 60)
        logger.info("Database Initialization for Data Quality Rules Engine")
        logger.info("=" * 60)
        
        # Import after logging is configured
        from core.db_session import engine, Base, init_db
        from models.data_quality_rules_models import DataQualityRuleSetORM
        
        logger.info(f"Database URL: {engine.url}")
        logger.info("")
        
        # Create all tables
        logger.info("Creating table: data_quality_rule_sets...")
        init_db()
        logger.info("✓ Table created successfully")
        
        # Verify table exists
        inspector_result = engine.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'data_quality_rule_sets'")
        if inspector_result:
            logger.info("✓ Table verified in database")
        
        logger.info("")
        logger.info("=" * 60)
        logger.info("Database initialization complete!")
        logger.info("=" * 60)
        logger.info("")
        logger.info("The data_quality_rule_sets table has been created with:")
        logger.info("  - Primary key: id (auto-increment)")
        logger.info("  - Unique index: rule_set_id")
        logger.info("  - Indexes: enabled, created_at, is_active")
        logger.info("  - JSON columns: mandatory/uniqueness/dropdown/format/range/datatype/cross_field rules")
        logger.info("  - Audit columns: created_at, updated_at, created_by, updated_by, version")
        logger.info("")
        logger.info("You can now use the /api/quality-rules endpoints to manage rule sets.")
        logger.info("Rule sets will be persisted to the database.")
        
        return True
        
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}", exc_info=True)
        return False


if __name__ == "__main__":
    import os
    
    # Load .env if needed
    if os.getenv("GRAPH_TRACE_LOAD_DOTENV", "").lower() == "true":
        from dotenv import load_dotenv
        load_dotenv()
        logger.info("Loaded environment from .env file")
    
    success = init_dqre_tables()
    sys.exit(0 if success else 1)
