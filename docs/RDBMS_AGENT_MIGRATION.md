# RDBMS Sources and Agent Migration Workflows

## Executive Summary

GraphTrace supports **comprehensive database migration** between RDBMS sources (SQL Server, Oracle, MySQL, PostgreSQL) and target databases (PostgreSQL, Neo4j, OpenSearch). The **ETL Orchestrator Agent** performs intelligent data discovery, schema mapping, transformation, and quality validation during migrations.

## Supported RDBMS Sources

| Database | Driver | System Dependency | Status |
|----------|--------|-------------------|--------|
| **SQL Server** | `pyodbc` | ODBC Driver 17 for SQL Server | ✅ Fully Supported |
| **Oracle** | `python-oracledb` | None (thin mode) / Oracle Client (thick mode) | ✅ Fully Supported |
| **MySQL** | `pymysql` / `psycopg[mysql]` | None | ✅ Fully Supported |
| **PostgreSQL** | `psycopg` | None | ✅ Fully Supported |

## How Agents Use RDBMS Sources for Migration

### 1. ETL Orchestrator Agent (Port 8021)

**Role:** Primary agent for database migration and data discovery

**Capabilities:**
- `perform_data_discovery` - Intelligent schema discovery and column mapping
- `manage_data_pipelines` - Orchestrate multi-step migrations
- `handle_data_transformations` - Apply business rules and transformations
- `monitor_pipeline_health` - Track migration status and quality

**Migration Workflow:**

```
┌──────────────────┐
│  Source RDBMS    │  
│  (SQL Server/    │  ← Step 1: Connect via SQLAlchemy/pyodbc/oracledb
│   Oracle/MySQL)  │     Extract: SELECT * FROM source_table
└────────┬─────────┘
         │
         ↓ Raw data records
┌─────────────────────────────────────────────┐
│       ETL Orchestrator Agent (8021)         │
│  ┌───────────────────────────────────────┐  │  Step 2: Staging
│  │  1. Staging                           │  │  Convert to pandas DataFrame
│  │     records → pandas DataFrame        │  │
│  └────────────┬──────────────────────────┘  │
│               │                             │
│  ┌────────────▼──────────────────────────┐  │  Step 3: Schema Inference
│  │  2. Schema Inference                  │  │  Analyze column dtypes
│  │     Analyze column types & patterns   │  │
│  └────────────┬──────────────────────────┘  │
│               │                             │
│  ┌────────────▼──────────────────────────┐  │  Step 4: Intelligent Mapping
│  │  3. Intelligent Column Mapping        │  │  Scoring algorithm:
│  │     - Direct match: 100 points        │  │  - part_no → part_number: 80
│  │     - Semantic: 60-80 points          │  │  - desc → description: 70
│  │     - Threshold: 50 minimum           │  │  - qty → quantity: 75
│  └────────────┬──────────────────────────┘  │
│               │                             │
│  ┌────────────▼──────────────────────────┐  │  Step 5: Transformation
│  │  4. Data Transformation               │  │  - Type conversions
│  │     - Rename columns via mapping      │  │  - Date normalization
│  │     - Type conversions                │  │  - String cleaning
│  │     - Business rules                  │  │
│  └────────────┬──────────────────────────┘  │
│               │                             │
│  ┌────────────▼──────────────────────────┐  │  Step 6: Quality Validation
│  │  5. Rule Engine Validation            │  │  - Rule Engine checks
│  │     - Data quality rules              │  │  - SODA quality checks
│  │     - SODA checks                     │  │  - Quality score: 0.0-1.0
│  │     - Quality score: 0.98             │  │
│  └────────────┬──────────────────────────┘  │
└───────────────┼─────────────────────────────┘
                │ quality_score >= 0.7 threshold
                ↓
       ┌────────┴─────────┐
       │                  │
       ↓                  ↓
┌──────────────┐   ┌──────────────┐  Step 7: Persistence
│  PostgreSQL  │   │    Neo4j     │  - to_sql() → plm_parts table
│  (plm_parts) │   │  (Lineage)   │  - Lineage tracking in graph
└──────────────┘   └──────────────┘
```

**Code Example:**

```python
# agent_services/etl_orchestrator/main.py

class ETLOrchestratorAgent(AgentService):
    async def perform_discovery(
        self,
        records: List[Dict],  # From source RDBMS
        source_name: str,     # e.g., "sqlserver_migration_source"
        target_table: str = "plm_parts"
    ) -> Dict[str, Any]:
        """
        Agentic data discovery and migration.
        
        Returns:
            {
                "staged_count": 15420,
                "quality_score": 0.98,
                "mapping": {"PART_NO": "part_number", "DESC": "description"},
                "validation": {...}
            }
        """
        # 1. Staging
        df = pd.DataFrame(records)
        
        # 2. Schema Inference
        schema = {col: str(df[col].dtype) for col in df.columns}
        
        # 3. Intelligent Mapping
        target_columns = ["id", "part_number", "description", "cost"]
        mapping = self._intelligent_column_mapping(
            df.columns.tolist(),
            target_columns
        )
        
        # 4. Transformation
        df_transformed = df.rename(columns=mapping)
        
        # 5. Validation
        validation = await self._run_rule_validation(df_transformed)
        quality_score = validation.get("quality_score", 0.0)
        
        # 6. Persistence (only if quality threshold met)
        if quality_score >= 0.7:
            df_transformed.to_sql(
                target_table,
                self.engine,  # PostgreSQL connection
                if_exists="append",
                index=False,
                method="multi"
            )
            
            # 7. Track lineage in Neo4j
            await self._record_lineage(source_name, target_table, len(df))
        
        return {
            "staged_count": len(df),
            "quality_score": quality_score,
            "mapping": mapping,
            "validation": validation
        }
```

### 2. Query Planner Agent (Port 8023)

**Role:** Optimize migration queries for large datasets

- Analyze source table schemas
- Generate optimized SELECT queries with indexing hints
- Suggest partition strategies for large tables
- Estimate migration time and resource requirements

### 3. Quality Monitor Agent (Port 8024)

**Role:** Continuous quality monitoring during migration

- Real-time quality metrics calculation
- Anomaly detection in migrated data
- Data profiling and statistics generation
- Alert on quality threshold violations

### 4. Data Analyst Agent (Port 8020)

**Role:** Post-migration analysis and validation

- Compare source vs. target row counts
- Analyze data distributions
- Identify data discrepancies
- Generate migration reports

## Connection Configuration

### SQL Server Migration Source

```json
{
  "id": "sqlserver_migration_source",
  "connection_type": "sqlserver",
  "name": "SQL Server Legacy Database",
  "host": "sql-server.company.com",
  "port": 1433,
  "database": "ProductionDB",
  "username": "migration_user",
  "password": "encrypted_password",
  "extra_options": {
    "driver": "{ODBC Driver 17 for SQL Server}",
    "trust_server_certificate": "yes"
  },
  "status": "active"
}
```

**Seeded in:** `python_backend/scripts/seed_admin_configs.py`

### Oracle Migration Source

```json
{
  "id": "oracle_migration_source",
  "connection_type": "oracle",
  "name": "Oracle ERP Database",
  "host": "oracle-prod.company.com",
  "port": 1521,
  "database": "ORCL",
  "username": "system",
  "password": "encrypted_password",
  "extra_options": {
    "service_name": "ORCL",
    "thick_mode": false,
    "encoding": "UTF-8"
  },
  "status": "active"
}
```

## Migration API Endpoints

### Execute RDBMS Migration

```http
POST /api/migration/advanced/rdbms/execute
Content-Type: application/json

{
  "source_connection_id": "sqlserver_migration_source",
  "target_connection_id": "postgres_primary",
  "table_mappings": [
    {
      "source_table": "Parts",
      "target_table": "plm_parts",
      "query": "SELECT PartID, PartNo, Description, UnitCost FROM Parts WHERE Active = 1",
      "batch_size": 1000
    }
  ]
}
```

**Response:**

```json
{
  "migration_id": "mig_20240115_143022",
  "source_type": "sqlserver",
  "target_type": "postgres",
  "started_at": "2024-01-15T14:30:22Z",
  "completed_at": "2024-01-15T14:35:18Z",
  "status": "success",
  "total_rows": 15420,
  "total_errors": 0,
  "tables_migrated": [
    {
      "table": "plm_parts",
      "rows_migrated": 15420,
      "batches": 16,
      "errors": 0
    }
  ]
}
```

### Get Supported RDBMS Types

```http
GET /api/migration/advanced/rdbms/supported-types
```

**Response includes:**
- Supported source databases (SQL Server, Oracle, MySQL, PostgreSQL)
- Driver requirements
- Sample connection configurations
- Target database options

## Quality Validation

### Rule Engine Validation

Applied during agent migration:

```python
rules = [
    {
        "rule_id": "R001",
        "name": "Part Number Format",
        "condition": "part_number LIKE 'P-%'",
        "severity": "error"
    },
    {
        "rule_id": "R002",
        "name": "Cost Non-Negative",
        "condition": "cost >= 0",
        "severity": "error"
    }
]
```

### SODA Quality Checks

```yaml
checks for plm_parts:
  - row_count > 0
  - missing_count(part_number) = 0
  - duplicate_count(part_number) = 0
  - avg(cost) between 0 and 10000
```

## Lineage Tracking in Neo4j

Migration lineage is automatically recorded:

```cypher
// View migration lineage
MATCH (m:Migration {migration_id: 'mig_20240115_143022'})-[:MIGRATED_TABLE]->(t:Table)
RETURN m.source_type, m.target_type, m.total_rows, t.name, m.status

// Find migration path for specific part
MATCH path = (src:DataSource)-[:EXTRACTED_FROM]->(m:Migration)-[:LOADED_TO]->(t:Table)
WHERE src.name = 'sqlserver_migration_source'
RETURN path
```

**Graph Structure:**

```
(DataSource:sqlserver_migration_source)
  └─[:EXTRACTED_FROM]→(Migration:mig_20240115_143022 {
       source_type: "sqlserver",
       target_type: "postgres",
       total_rows: 15420,
       status: "success"
     })
      └─[:MIGRATED_TABLE {rows: 15420, errors: 0}]→(Table:plm_parts)
          └─[:VALIDATED_BY]→(QualityCheck {score: 0.98})
```

## Complete Migration Example

### Scenario: SQL Server Parts → PostgreSQL

```python
from services.database_migration_service import DatabaseMigrationService

# Initialize service
migration_service = DatabaseMigrationService(db)

# Source config (SQL Server)
source_config = {
    "type": "sqlserver",
    "host": "legacy-sql.company.com",
    "port": 1433,
    "database": "PartsDB",
    "username": "migration_user",
    "password": "SecurePassword123"
}

# Target config (PostgreSQL)
target_config = {
    "type": "postgres",
    "connection_string": "postgresql://user:pass@localhost:5432/graphtrace"
}

# Execute migration
result = await migration_service.migrate_from_sqlserver(
    source_config=source_config,
    target_config=target_config,
    table_mappings=[
        {
            "source_table": "Parts",
            "target_table": "plm_parts",
            "query": "SELECT * FROM Parts WHERE Active = 1",
            "transform": lambda df: df.rename(columns={
                "PartNo": "part_number",
                "PartDesc": "description"
            })
        }
    ],
    batch_size=1000
)

print(f"Migration ID: {result['migration_id']}")
print(f"Total rows: {result['total_rows']}")
print(f"Status: {result['status']}")
```

## Files and Components

### Core Services

- **`services/database_migration_service.py`** - Migration orchestration service
  - `migrate_from_sqlserver()` - SQL Server migration
  - `migrate_from_oracle()` - Oracle migration
  - `validate_migration()` - Post-migration validation
  - `_record_migration_lineage()` - Neo4j lineage tracking

### API Endpoints

- **`graph_api/migration_router.py`** - Migration REST API
  - `POST /api/migration/advanced/rdbms/execute` - Execute migration
  - `GET /api/migration/advanced/rdbms/supported-types` - Get supported databases

### Agent Implementation

- **`agent_services/etl_orchestrator/main.py`** - ETL Orchestrator Agent
  - `perform_discovery()` - Intelligent migration workflow
  - `_intelligent_column_mapping()` - Score-based column matching
  - `_run_rule_validation()` - Quality validation

### Seeding Scripts

- **`scripts/seed_admin_configs.py`** - Seed connection configurations
  - `sqlserver_migration_source` - Example SQL Server connection
  - `oracle_migration_source` - Example Oracle connection
  - `mysql_migration_source` - Example MySQL connection

### Documentation

- **`docs/DATABASE_MIGRATION_GUIDE.md`** - Complete migration guide (450+ lines)
- **`docs/OAUTH_CONFIGURATION.md`** - OAuth for secure PLM connections

## Key Features

✅ **Multi-RDBMS Support** - SQL Server, Oracle, MySQL, PostgreSQL  
✅ **Intelligent Schema Mapping** - Score-based column matching (100-point algorithm)  
✅ **Quality Validation** - Rule Engine + SODA checks  
✅ **Lineage Tracking** - Neo4j graph for auditability  
✅ **Batch Processing** - Memory-efficient large dataset handling  
✅ **Agent Orchestration** - ETL agent performs migration autonomously  
✅ **OAuth Support** - Secure connections to external PLM systems  
✅ **Database Seeding** - Pre-configured example connections  

## Next Steps

1. **Configure Source Connection** - Add SQL Server/Oracle connection in Admin UI
2. **Test Connection** - Use `/api/data-sources/test-connection` endpoint
3. **Define Table Mappings** - Specify source/target tables and queries
4. **Execute Migration** - Call `/api/migration/advanced/rdbms/execute`
5. **Validate Results** - Verify row counts and data quality
6. **View Lineage** - Query Neo4j graph for migration tracking

## See Also

- [Database Migration Guide](DATABASE_MIGRATION_GUIDE.md) - Comprehensive migration documentation
- [OAuth Configuration](OAUTH_CONFIGURATION.md) - Secure API connections
- [User Guide](USER_GUIDE.md) - General GraphTrace usage
