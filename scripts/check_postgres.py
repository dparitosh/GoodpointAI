#!/usr/bin/env python
"""
PostgreSQL Health Check Script
Validates Postgres connectivity and schema initialization without starting full stack.
Usage:
  python scripts/check_postgres.py [--detailed] [--init-schema]
"""

import sys
import os
import argparse
import logging
from pathlib import Path
from typing import Optional, Tuple

# Add python_backend to path for imports
REPO_ROOT = Path(__file__).parent.parent
SYS_PATH_BACKEND = str(REPO_ROOT / "python_backend")
if SYS_PATH_BACKEND not in sys.path:
    sys.path.insert(0, SYS_PATH_BACKEND)

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s"
)
logger = logging.getLogger(__name__)


def load_env_file(env_path: Path) -> None:
    """Load .env file if it exists."""
    if env_path.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(dotenv_path=env_path, override=True)
            logger.debug(f"Loaded .env from {env_path}")
        except ImportError:
            logger.warning("python-dotenv not installed, skipping .env loading")
    else:
        logger.warning(f".env file not found at {env_path}")


def get_database_url() -> Optional[str]:
    """Extract DATABASE_URL from environment."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        logger.error("❌ DATABASE_URL not set in environment or .env")
        return None
    return db_url


def parse_database_url(db_url: str) -> dict:
    """Parse PostgreSQL connection string."""
    from urllib.parse import urlparse
    
    try:
        parsed = urlparse(db_url)
        return {
            "scheme": parsed.scheme,
            "user": parsed.username or "postgres",
            "password": parsed.password or "***",
            "host": parsed.hostname or "localhost",
            "port": parsed.port or 5432,
            "database": (parsed.path or "/graphtrace").lstrip("/"),
        }
    except Exception as e:
        logger.error(f"Failed to parse DATABASE_URL: {e}")
        return {}


def test_postgres_connection(db_url: str, timeout: int = 5) -> Tuple[bool, str]:
    """Test PostgreSQL connection with timeout."""
    try:
        import psycopg
        
        logger.info("Testing PostgreSQL connection...")
        conn = psycopg.connect(db_url, connect_timeout=timeout)
        cursor = conn.cursor()
        
        # Test query
        cursor.execute("SELECT version()")
        version = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        
        return True, version
    except ImportError:
        return False, "psycopg3 not installed (run: pip install 'psycopg[binary]')"
    except psycopg.OperationalError as e:
        return False, f"Connection failed: {str(e)}"
    except Exception as e:
        return False, f"Error: {type(e).__name__}: {str(e)}"


def check_schema_initialized(db_url: str) -> Tuple[bool, str]:
    """Check if GraphTrace schema is initialized."""
    try:
        import psycopg
        
        logger.info("Checking schema initialization...")
        conn = psycopg.connect(db_url, connect_timeout=5)
        cursor = conn.cursor()
        
        # Check for core tables
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = 'data_source'
            )
        """)
        has_schema = cursor.fetchone()[0]
        
        if has_schema:
            # Get table count
            cursor.execute("""
                SELECT COUNT(*) FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)
            table_count = cursor.fetchone()[0]
            cursor.close()
            conn.close()
            return True, f"Schema initialized ({table_count} tables)"
        else:
            cursor.close()
            conn.close()
            return False, "Schema NOT initialized (run: python scripts/init_db_schema.py)"
            
    except Exception as e:
        return False, f"Schema check failed: {type(e).__name__}: {str(e)}"


def main():
    parser = argparse.ArgumentParser(
        description="Check PostgreSQL connectivity and schema initialization"
    )
    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Show detailed connection info and version"
    )
    parser.add_argument(
        "--init-schema",
        action="store_true",
        help="Auto-initialize schema if missing (requires write access)"
    )
    args = parser.parse_args()
    
    # Load environment
    env_file = REPO_ROOT / "python_backend" / ".env"
    load_env_file(env_file)
    
    # Get database URL
    db_url = get_database_url()
    if not db_url:
        return 1
    
    # Parse and display connection info
    db_info = parse_database_url(db_url)
    if db_info:
        logger.info(f"📋 Connection: {db_info['user']}@{db_info['host']}:{db_info['port']}/{db_info['database']}")
    
    # Test connection
    success, message = test_postgres_connection(db_url)
    if not success:
        logger.error(f"❌ Connection failed: {message}")
        return 1
    
    logger.info(f"✅ Connection OK")
    if args.detailed:
        logger.info(f"   PostgreSQL version: {message}")
    
    # Check schema
    schema_ok, schema_msg = check_schema_initialized(db_url)
    if not schema_ok:
        logger.warning(f"⚠️  {schema_msg}")
        if args.init_schema:
            logger.info("Attempting to initialize schema...")
            try:
                # Import and run schema initialization
                os.chdir(REPO_ROOT / "python_backend")
                from scripts.init_db_schema import main as init_main
                init_main()
                logger.info("✅ Schema initialization complete")
            except Exception as e:
                logger.error(f"❌ Schema init failed: {e}")
                return 1
        else:
            logger.info("   Run: python scripts/init_db_schema.py --initialize")
            return 1
    else:
        logger.info(f"✅ {schema_msg}")
    
    logger.info("\n✅ PostgreSQL is healthy and ready!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
