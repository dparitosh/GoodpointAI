# PostgreSQL Schema Migrations

This document describes the database schema for GraphTrace and guidelines for handling schema changes in existing databases.

## Current Architecture

### Schema Initialization

The application uses **SQLAlchemy ORM** with a non-migration approach:

- **Method**: `create_all()` in `python_backend/core/db_session.py`
- **Process**: 
  1. Imports all model modules (`configuration_models.py`, `workflow_models.py`, `plm_models.py`, etc.)
  2. Calls `Base.metadata.create_all(bind=engine)` to create tables that don't exist
  3. Does **NOT** modify existing tables
  
- **Limitation**: Schema changes (new columns, type changes, table additions) require manual intervention on existing databases.

### Alembic Setup (Prepared but Not Active)

The project has **Alembic 1.13.1** in `requirements.txt` but:
- No migration files exist (no `alembic/versions/` directory)
- Alembic is configured as a dependency but not used for automated migrations

## Core Tables

### 1. Workflow Management

**Table**: `workflow_instances`

Key columns:
- `id` (String, PK): Unique workflow identifier
- `name` (String): Workflow name
- `source_id`, `target_id` (String): Source/target system IDs
- `source_config`, `target_config` (JSON): Connection configurations
- `workflow_config` (JSON): Pipeline configuration (nodes, edges, agents)
- `status` (Enum): DRAFT → CONFIGURED → RUNNING → COMPLETED/FAILED
- `current_stage` (Enum): EXTRACTING, TRANSFORMING, VALIDATING, LOADING, FINALIZING
- `progress_percentage` (Float): 0.0 - 100.0
- `processed_records`, `failed_records` (Integer): Counters
- `created_at`, `updated_at`, `started_at`, `completed_at` (DateTime with TZ)
- `schedule_enabled` (Boolean): Recurring execution flag
- `schedule_cron` (String): Cron expression if scheduled

**Purpose**: Tracks PLM data migration workflows from source (Teamcenter, Windchill, etc.) to target systems.

### 2. Configuration & Settings

**Table**: `configuration` 

Stores application-level settings and admin configurations.

**Table**: `encrypted_config`

Stores sensitive encrypted configuration values:
- Credentials for external systems
- API keys
- Authentication tokens

### 3. Quality & Validation

**Table**: `quality_rules`

Rule definitions for data quality checks.

**Table**: `quality_check_results`

Results of quality rule executions.

### 4. PLM Data Models

**Tables**: `plm_items`, `bom_nodes`, `relationships`

Represent PLM structure (Parts, BOMs, relationships).

### 5. Reports & Analytics

**Table**: `report_definitions`

Stores report templates and queries.

**Table**: `report_executions`

Historical execution records.

## Handling Schema Changes

### For Fresh Installations

Run the initialization script:

```bash
cd agentic-restored/python_backend
python -m scripts.init_db_schema
```

This creates all tables automatically.

### For Existing Databases

When the application code adds new models or modifies existing ones, you may need to manually add schema changes:

#### Option 1: Add Missing Columns (Safe)

If a new column is added to a model and the table exists:

```sql
-- Example: Add a new column to workflow_instances
ALTER TABLE workflow_instances 
ADD COLUMN IF NOT EXISTS new_column_name TYPE VARCHAR(255) DEFAULT NULL;
```

#### Option 2: Create New Tables (Safe)

If a new model/table is added:

```sql
-- Manually create the table based on the model definition
CREATE TABLE new_table (
  id VARCHAR(100) PRIMARY KEY,
  ... (other columns)
);
```

#### Option 3: Type Changes or Complex Migrations (Risk)

For production databases, complex migrations should be:

1. **Planned in advance** with database backups
2. **Tested** on a copy of production data
3. **Documented** with rollback procedures

Example (dropping & recreating a column):

```sql
BEGIN;

-- Backup existing data
CREATE TABLE workflow_instances_backup AS 
SELECT * FROM workflow_instances;

-- Alter column type
ALTER TABLE workflow_instances 
ALTER COLUMN progress_percentage TYPE INTEGER USING 
  CAST(FLOOR(progress_percentage * 100) AS INTEGER);

-- If successful, done; if not, restore from backup
ROLLBACK; -- or COMMIT
```

## Recommended Approach: Enabling Alembic

To automate migrations in the future:

### 1. Initialize Alembic

```bash
cd agentic-restored/python_backend
alembic init alembic
```

### 2. Configure SQLAlchemy URL

Edit `alembic/env.py` to import engine from `core.db_session`.

### 3. Create Initial Migration

```bash
alembic revision --autogenerate -m "Initial schema"
```

### 4. Apply Migrations

```bash
alembic upgrade head
```

## Schema Change Detection

To identify what's changed between code models and database:

1. **Review model files** in `models/` directory
2. **Compare columns** against actual database schema:

```sql
-- View table structure
\d workflow_instances  -- In psql

-- Or via SQL
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'workflow_instances'
ORDER BY ordinal_position;
```

3. **Check for missing tables**:

```sql
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public'
ORDER BY table_name;
```

## Troubleshooting

### Table Doesn't Exist After First Run

**Cause**: Model not imported in `init_db()` function

**Fix**: Add import to `scripts/init_db_schema.py` in the model import loop

### Columns Missing on Existing Database

**Cause**: `create_all()` doesn't alter existing tables

**Fix**: Manually add columns using `ALTER TABLE ... ADD COLUMN` (see **Option 1** above)

### Encryption Key Changes

**Effect**: Existing encrypted configuration values become unreadable

**Workaround** (development only):
- Set `GRAPH_TRACE_CONFIG_ENCRYPTION_KEY` environment variable to match original key
- Or, re-enter encrypted values through the UI after key change

**For Production**: Store encryption key securely and rotate according to your security policy.

## Best Practices

1. **Backup before migrations**: Always backup production databases before schema changes
2. **Test on staging**: Apply schema changes to a test database first
3. **Document changes**: Keep a changelog of schema modifications
4. **Use version control**: Track migration scripts in Git
5. **Minimal windows**: Apply complex migrations during low-traffic periods
6. **Monitor performance**: Watch for locks/blocking during large migrations

## Migration Checklist

When deploying a version with schema changes:

- [ ] Backup production database
- [ ] Test migrations on staging environment
- [ ] Verify all new columns/tables exist: `\dt` and `\d table_name`
- [ ] Check application starts without errors after migration
- [ ] Verify critical features work (login, workflow creation, data ingestion)
- [ ] Monitor logs for migration-related errors
- [ ] Document any manual steps taken
- [ ] Keep rollback procedure ready
