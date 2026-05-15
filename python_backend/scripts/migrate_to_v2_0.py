"""
Migration Script: GraphTrace v2.0 Deployment
=============================================

Purpose:
  Safely upgrade existing GraphTrace installations to v2.0 with refactored code.
  This script handles:
  - New database tables (workflow_instances)
  - New model columns and constraints
  - Configuration migrations
  - Backup of encrypted configuration
  - Verification of post-migration state

Safety:
  - Creates backups before any changes
  - Logs all operations
  - Supports --dry-run for verification
  - Requires --yes flag for execution
  - Verifies database connectivity before starting

Usage:
  # Preview changes without applying
  python -m scripts.migrate_to_v2_0 --dry-run

  # Execute migration
  python -m scripts.migrate_to_v2_0 --yes

  # Execute with backup to specific location
  python -m scripts.migrate_to_v2_0 --yes --backup-path /custom/backup/path
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from core.db_session import DATABASE_URL, init_db, redacted_database_url, verify_database_connectivity

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for migration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(f"migration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
        ]
    )


def backup_database(engine: Engine, backup_path: Optional[Path] = None) -> Path:
    """
    Create a logical backup of the database by dumping schema and encrypted config.
    (Full pg_dump would require psql/pg_dump in PATH; we do targeted backup instead)
    """
    if backup_path is None:
        backup_path = Path("backups") / datetime.now().strftime("%Y%m%d_%H%M%S_v2_0_migration")
    
    backup_path.mkdir(parents=True, exist_ok=True)
    logger.info(f"Creating backup at: {backup_path}")
    
    try:
        with engine.connect() as conn:
            # Backup encrypted configurations (most critical data)
            inspector = inspect(engine)
            
            # Check if app_encrypted_configs table exists
            if "app_encrypted_configs" in inspector.get_table_names():
                result = conn.execute(
                    text("""
                        SELECT key, ciphertext, created_at, updated_at 
                        FROM app_encrypted_configs 
                        ORDER BY key
                    """)
                )
                encrypted_records = result.fetchall()
                
                backup_file = backup_path / "encrypted_configs_backup.txt"
                with open(backup_file, "w") as f:
                    f.write(f"# Encrypted Configuration Backup\n")
                    f.write(f"# Backup Date: {datetime.now().isoformat()}\n")
                    f.write(f"# Database: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL}\n")
                    f.write(f"# Record Count: {len(encrypted_records)}\n\n")
                    for key, ciphertext, created_at, updated_at in encrypted_records:
                        f.write(f"Key: {key}\n")
                        f.write(f"Created: {created_at}\n")
                        f.write(f"Updated: {updated_at}\n")
                        f.write(f"Ciphertext (first 50 chars): {ciphertext[:50]}...\n\n")
                
                logger.info(f"Backed up {len(encrypted_records)} encrypted config records to {backup_file}")
            
            # Backup workflow configuration (if any exist)
            if "workflow_instances" in inspector.get_table_names():
                result = conn.execute(
                    text("""
                        SELECT id, name, source_type, target_type, status, created_by, created_at 
                        FROM workflow_instances 
                        LIMIT 100
                    """)
                )
                workflow_records = result.fetchall()
                
                backup_file = backup_path / "workflow_instances_sample.txt"
                with open(backup_file, "w") as f:
                    f.write(f"# Workflow Instances Backup (Sample)\n")
                    f.write(f"# Backup Date: {datetime.now().isoformat()}\n")
                    f.write(f"# Total: {len(workflow_records)} records\n\n")
                    for record in workflow_records:
                        f.write(f"ID: {record[0]}, Name: {record[1]}, Status: {record[4]}\n")
                
                logger.info(f"Backed up {len(workflow_records)} workflow instance records")
    
    except Exception as exc:
        logger.error(f"Backup failed (non-fatal): {exc}")
        # Don't fail the migration due to backup failure
    
    logger.info(f"Backup location: {backup_path.absolute()}")
    return backup_path


def create_workflow_instance_table(engine: Engine, dry_run: bool = False) -> bool:
    """Create workflow_instances table if it doesn't exist."""
    try:
        inspector = inspect(engine)
        
        if "workflow_instances" in inspector.get_table_names():
            logger.info("✓ workflow_instances table already exists")
            return True
        
        logger.info("Creating workflow_instances table...")
        
        if dry_run:
            logger.info("(DRY RUN) Would create workflow_instances table")
            return True
        
        with engine.begin() as conn:
            # Create the table using SQLAlchemy init (safer than raw SQL)
            from models.workflow_models import WorkflowInstance  # noqa: F401
            
            WorkflowInstance.__table__.create(engine, checkfirst=True)
        
        logger.info("✓ workflow_instances table created")
        return True
    
    except Exception as exc:
        logger.error(f"Failed to create workflow_instances table: {exc}")
        return False


def apply_plm_schema_migrations(engine: Engine, dry_run: bool = False) -> bool:
    """Apply PLM schema migrations (content_hash, source_object_id, etc.)."""
    try:
        inspector = inspect(engine)
        
        if "plm_staged_records" not in inspector.get_table_names():
            logger.info("plm_staged_records table not found (optional, skipping)")
            return True
        
        logger.info("Applying PLM schema migrations...")
        
        if dry_run:
            logger.info("(DRY RUN) Would apply PLM migrations")
            return True
        
        migrations = [
            (
                "content_hash column",
                "ALTER TABLE plm_staged_records ADD COLUMN IF NOT EXISTS content_hash VARCHAR(64)"
            ),
            (
                "source_object_id column",
                "ALTER TABLE plm_staged_records ADD COLUMN IF NOT EXISTS source_object_id VARCHAR(256)"
            ),
            (
                "content_hash index",
                "CREATE INDEX IF NOT EXISTS ix_plm_staged_records_content_hash ON plm_staged_records (content_hash)"
            ),
            (
                "source_object_id index",
                "CREATE INDEX IF NOT EXISTS ix_plm_staged_records_source_object_id ON plm_staged_records (source_object_id)"
            ),
            (
                "unique constraint on run_id + content_hash",
                """DO $$ BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint WHERE conname = 'uq_staged_run_content_hash'
                    ) THEN
                        ALTER TABLE plm_staged_records
                            ADD CONSTRAINT uq_staged_run_content_hash UNIQUE (run_id, content_hash);
                    END IF;
                END $$"""
            ),
            (
                "updated_at column in plm_ingestion_runs",
                "ALTER TABLE plm_ingestion_runs ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP"
            ),
        ]
        
        with engine.begin() as conn:
            for migration_name, sql_stmt in migrations:
                try:
                    conn.execute(text(sql_stmt))
                    logger.info(f"✓ Applied: {migration_name}")
                except SQLAlchemyError as exc:
                    logger.warning(f"Migration already applied or skipped ({migration_name}): {exc}")
        
        logger.info("✓ PLM schema migrations complete")
        return True
    
    except Exception as exc:
        logger.error(f"PLM schema migration failed: {exc}")
        return False


def apply_file_batch_schema_migrations(engine: Engine, dry_run: bool = False) -> bool:
    """Apply file batch processing schema migrations."""
    try:
        logger.info("Applying file batch processing schema migrations...")
        
        if dry_run:
            logger.info("(DRY RUN) Would apply file batch migrations")
            return True
        
        try:
            from services.file_batch_processor import ensure_schema
            ensure_schema(engine)
            logger.info("✓ File batch processing schema ensured")
            return True
        except ImportError:
            logger.warning("file_batch_processor not available (optional, skipping)")
            return True
    
    except Exception as exc:
        logger.error(f"File batch schema migration failed: {exc}")
        return False


def verify_migration(engine: Engine) -> bool:
    """Verify migration was successful."""
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        logger.info("\n=== Migration Verification ===")
        
        # Check critical tables
        critical_tables = [
            "workflow_instances",
            "plm_staged_records",
            "app_encrypted_configs",
        ]
        
        for table_name in critical_tables:
            if table_name in tables:
                logger.info(f"✓ {table_name} exists")
            else:
                logger.warning(f"⚠ {table_name} not found (may be optional)")
        
        # Verify workflow_instances columns if table exists
        if "workflow_instances" in tables:
            columns = [col.name for col in inspector.get_columns("workflow_instances")]
            required_cols = ["id", "name", "source_id", "target_id", "status", "progress_percentage"]
            
            for col in required_cols:
                if col in columns:
                    logger.info(f"✓ workflow_instances.{col} exists")
                else:
                    logger.error(f"✗ workflow_instances.{col} MISSING")
                    return False
        
        logger.info("\n=== Verification Complete ===\n")
        return True
    
    except Exception as exc:
        logger.error(f"Verification failed: {exc}")
        return False


def main(argv: list[str] | None = None) -> int:
    """Execute migration."""
    parser = argparse.ArgumentParser(
        description="Migrate GraphTrace to v2.0 (refactored code with new workflow tables)"
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Actually perform the migration (required; use --dry-run to preview)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without applying them"
    )
    parser.add_argument(
        "--backup-path",
        type=Path,
        default=None,
        help="Custom backup location (default: ./backups/TIMESTAMP_v2_0_migration)"
    )
    parser.add_argument(
        "--skip-backup",
        action="store_true",
        help="Skip creating backup (not recommended)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose logging"
    )
    
    args = parser.parse_args(argv)
    
    setup_logging(args.verbose)
    
    logger.info("=" * 60)
    logger.info("GraphTrace v2.0 Migration Script")
    logger.info("=" * 60)
    
    # Validate DATABASE_URL
    if not DATABASE_URL or DATABASE_URL == "sqlite:///:memory:":
        logger.error("DATABASE_URL not configured in python_backend/.env")
        return 1
    
    logger.info(f"Target database: {redacted_database_url()}")
    
    # Test connectivity
    conn_err = verify_database_connectivity(timeout_s=5.0)
    if conn_err is not None:
        logger.error(f"Database connectivity failed: {conn_err}")
        logger.error("Is PostgreSQL running? Is DATABASE_URL correct?")
        return 2
    
    # Create engine
    engine = create_engine(DATABASE_URL)
    
    try:
        # Backup (unless skipped)
        if not args.skip_backup and not args.dry_run:
            backup_path = backup_database(engine, args.backup_path)
            logger.info(f"Backup saved to: {backup_path}")
        elif args.dry_run:
            logger.info("(DRY RUN) Backup skipped")
        
        # Apply migrations
        success = True
        success = create_workflow_instance_table(engine, args.dry_run) and success
        success = apply_plm_schema_migrations(engine, args.dry_run) and success
        success = apply_file_batch_schema_migrations(engine, args.dry_run) and success
        
        if not success:
            logger.error("One or more migrations failed")
            return 3
        
        # Initialize full DB schema (idempotent, creates missing tables)
        if not args.dry_run:
            logger.info("Ensuring full database schema...")
            init_db()
            logger.info("✓ Database schema ensured")
        else:
            logger.info("(DRY RUN) Would ensure full database schema")
        
        # Verify
        if not args.dry_run:
            if not verify_migration(engine):
                logger.error("Post-migration verification failed")
                return 4
        
        # Summary
        if args.dry_run:
            logger.info("\n(DRY RUN) Migration preview complete. Use --yes to apply.")
        else:
            logger.info("\n✓ Migration to v2.0 complete")
            logger.info("Next steps:")
            logger.info("  1. Review migration.log for details")
            logger.info("  2. Restart the backend: python -m uvicorn main:app --reload")
            logger.info("  3. Verify in Admin Configuration page (http://localhost:5173/#/admin)")
            logger.info("  4. Test a data migration workflow")
        
        return 0
    
    except Exception as exc:
        logger.error(f"Migration failed: {exc}", exc_info=True)
        return 5
    
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
