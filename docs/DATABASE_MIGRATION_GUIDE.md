# Database Migration Guide

## Overview

GraphTrace supports comprehensive database migration workflows using ETL Orchestrator agents. This guide covers migrating data between different RDBMS sources with intelligent schema mapping, data transformation, and quality validation.

## Supported Migration Paths

### Source Databases
- **PostgreSQL** - Native support via psycopg
- **MySQL** - Support via psycopg with MySQL connector
- **SQL Server** - Support via pyodbc + ODBC Driver 17
- **Oracle** - Support via python-oracledb (thick/thin mode)

### Target Databases
- **PostgreSQL** - Primary data warehouse
- **Neo4j** - Knowledge graph with lineage tracking
- **OpenSearch** - Full-text search and analytics

## Architecture

```
┌─────────────────┐
│  Source RDBMS   │
│  (SQL Server,   │
│   Oracle, etc.) │
└────────┬────────┘
         │
         │ 1. Extract (via SQLAlchemy/pyodbc/oracledb)
         ↓
┌─────────────────────────┐
│   ETL Orchestrator      │
│       Agent             │
│  ┌──────────────────┐   │
│  │ Schema Discovery │   │
│  └────────┬─────────┘   │
│           │             │
│  ┌────────▼─────────┐   │
│  │ Column Mapping   │   │ 2. Transform
│  │  (Score-based)   │   │
│  └────────┬─────────┘   │
│           │             │
│  ┌────────▼─────────┐   │
│  │ Data Transform   │   │
│  │   (pandas)       │   │
│  └────────┬─────────┘   │
│           │             │
│  ┌────────▼─────────┐   │
│  │ Quality Check    │   │
│  │ (Rule Engine +   │   │
│  │  SODA)           │   │
│  └────────┬─────────┘   │
└───────────┼─────────────┘
            │
            │ 3. Load
            ↓
   ┌────────┴──────────┐
   │                   │
   ↓                   ↓
┌──────────┐    ┌──────────┐
│PostgreSQL│    │  Neo4j   │
│ (Target) │    │(Lineage) │
└──────────┘    └──────────┘
```

## Migration Workflow

### 1. Configure Source Connection

Add source database in Admin UI → Connections:

**SQL Server Example:**
```json
{
  "name": "legacy_sqlserver",
  "type": "sqlserver",
  "host": "sql-server.company.com",
  "port": 1433,
  "database": "ProductionDB",
  "username": "migration_user",
  "password": "encrypted_password",
  "driver": "{ODBC Driver 17 for SQL Server}",
  "isActive": true
}
```

**Oracle Example:**
```json
{
  "name": "oracle_erp",
  "type": "oracle",
  "host": "oracle-prod.company.com",
  "port": 1521,
  "service_name": "ORCL",
  "username": "system",
  "password": "encrypted_password",
  "thick_mode": false,
  "isActive": true
}
```

### 2. Define Table Mappings

Create migration configuration with intelligent column mapping:

```python
# Example: Migrate Oracle parts catalog to PostgreSQL
table_mappings = [
    {
        "source_table": "PARTS_MASTER",
        "target_table": "plm_parts",
        "query": """
            SELECT 
                PART_ID,
                PART_NUMBER,
                DESCRIPTION,
                UNIT_COST,
                CATEGORY_CODE,
                CREATED_DATE,
                LAST_MODIFIED
            FROM PARTS_MASTER
            WHERE STATUS = 'ACTIVE'
        """,
        "transform": lambda df: df.rename(columns={
            "PART_ID": "id",
            "PART_NUMBER": "part_number",
            "DESCRIPTION": "description",
            "UNIT_COST": "cost",
            "CATEGORY_CODE": "category",
            "CREATED_DATE": "created_at",
            "LAST_MODIFIED": "updated_at"
        })
    },
    {
        "source_table": "BOM_ITEMS",
        "target_table": "plm_bom",
        "query": "SELECT * FROM BOM_ITEMS WHERE ACTIVE_FLAG = 1"
    }
]
```

### 3. Execute Migration via Agent

#### Option A: Via API

```bash
POST /api/migrations/execute
Content-Type: application/json

{
  "source_connection_id": 123,
  "target_connection_id": 456,
  "table_mappings": [
    {
      "source_table": "PARTS_MASTER",
      "target_table": "plm_parts",
      "batch_size": 1000,
      "enable_quality_checks": true
    }
  ],
  "options": {
    "track_lineage": true,
    "fail_on_validation_error": false,
    "enable_soda_checks": true
  }
}
```

#### Option B: Via ETL Orchestrator Agent (MCP)

```python
# Call ETL Orchestrator agent via MCP
import asyncio
from agent_services.etl_orchestrator.main import ETLOrchestratorAgent

async def migrate_data():
    agent = ETLOrchestratorAgent()
    
    # Perform discovery and intelligent mapping
    result = await agent.perform_discovery(
        records=[...],  # Data from source
        source_name="oracle_erp",
        target_table="plm_parts"
    )
    
    print(f"Migration complete: {result['staged_count']} rows")
    print(f"Quality score: {result['quality_score']:.2f}")
    print(f"Column mapping: {result['mapping']}")

asyncio.run(migrate_data())
```

### 4. Intelligent Column Mapping

The ETL Orchestrator uses a scoring algorithm to map source columns to target schema:

**Scoring Rules:**
- **Direct match** (case-insensitive): 100 points
- **Semantic approximation**: 60-80 points
  - `part_no` → `part_number`: 80 points
  - `desc` → `description`: 70 points
  - `qty` → `quantity`: 75 points
- **Minimum threshold**: 50 points

**Example Mapping Output:**
```python
{
  "PART_ID": "id",           # Score: 100 (direct match)
  "PART_NO": "part_number",  # Score: 80 (semantic)
  "DESC": "description",     # Score: 70 (semantic)
  "STATUS_CD": "status",     # Score: 65 (semantic)
}
```

Columns below threshold are logged for manual review.

### 5. Data Transformation

Transformations applied during migration:

1. **Type conversions**: Oracle NUMBER → PostgreSQL NUMERIC
2. **Date normalization**: TIMESTAMP → ISO 8601 UTC
3. **String encoding**: Handle Oracle NLS_CHARACTERSET
4. **NULL handling**: Convert Oracle empty strings to NULL
5. **LOB conversion**: CLOB/BLOB → TEXT/BYTEA

**Custom Transformations:**
```python
def normalize_part_data(df):
    """Custom transformation for parts data."""
    # Normalize part numbers to uppercase
    df['part_number'] = df['part_number'].str.upper().str.strip()
    
    # Convert costs to USD (if source is in different currency)
    if 'unit_cost' in df.columns:
        df['cost_usd'] = df['unit_cost'] * 1.0  # Apply exchange rate
    
    # Parse category codes
    df['category'] = df['category_code'].str.split('-').str[0]
    
    # Add migration metadata
    df['data_source'] = 'oracle_erp'
    df['migrated_at'] = pd.Timestamp.utcnow()
    
    return df
```

### 6. Quality Validation

**Rule Engine Validation:**
```python
# Quality rules applied during migration
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
    },
    {
        "rule_id": "R003",
        "name": "Category Valid",
        "condition": "category IN ('ELECTRICAL', 'MECHANICAL', 'FASTENER')",
        "severity": "warning"
    }
]
```

**SODA Quality Checks:**
```yaml
# soda_check.yml
checks for plm_parts:
  - row_count > 0
  - missing_count(part_number) = 0
  - missing_count(description) < 100
  - duplicate_count(part_number) = 0
  - values in (category) must be in ['ELECTRICAL', 'MECHANICAL', 'FASTENER']
  - avg(cost) between 0 and 10000
```

### 7. Lineage Tracking in Neo4j

Migration lineage is automatically recorded in Neo4j:

**Cypher Query to View Lineage:**
```cypher
// Find all migrations from Oracle
MATCH (m:Migration {source_type: 'oracle'})-[:MIGRATED_TABLE]->(t:Table)
RETURN m.migration_id, m.started_at, m.total_rows, t.name, m.status
ORDER BY m.started_at DESC

// Find migration path for specific part
MATCH path = (src:DataSource {name: 'oracle_erp'})-[:EXTRACTED_FROM]->(m:Migration)-[:LOADED_TO]->(t:Table {name: 'plm_parts'})
RETURN path
```

**Lineage Graph Structure:**
```
(DataSource:oracle_erp)
    └─[:EXTRACTED_FROM]→(Migration:mig_20240115_143022)
        ├─[:MIGRATED_TABLE {rows: 15420}]→(Table:plm_parts)
        ├─[:MIGRATED_TABLE {rows: 8301}]→(Table:plm_bom)
        └─[:VALIDATED_BY]→(QualityCheck {score: 0.98})
```

## Complete Migration Example

### Scenario: Migrate SQL Server Parts Database to PostgreSQL

```python
from services.database_migration_service import DatabaseMigrationService
from core.database import get_db

async def migrate_sqlserver_parts():
    """Complete migration from SQL Server to PostgreSQL."""
    
    # Initialize migration service
    db = next(get_db())
    migration_service = DatabaseMigrationService(db)
    
    # Source configuration
    source_config = {
        "type": "sqlserver",
        "host": "legacy-sql.company.com",
        "port": 1433,
        "database": "PartsDB",
        "username": "migration_user",
        "password": "SecurePassword123",
        "driver": "{ODBC Driver 17 for SQL Server}"
    }
    
    # Target configuration
    target_config = {
        "type": "postgres",
        "connection_string": "postgresql://user:pass@localhost:5432/graphtrace"
    }
    
    # Define transformations
    def transform_parts(df):
        df['part_number'] = df['PartNo'].str.upper()
        df['description'] = df['PartDesc']
        df['cost'] = df['UnitCost'].astype(float)
        df['category'] = df['CategoryCode'].str.split('-').str[0]
        return df[['part_number', 'description', 'cost', 'category']]
    
    # Table mappings
    table_mappings = [
        {
            "source_table": "Parts",
            "target_table": "plm_parts",
            "query": """
                SELECT PartNo, PartDesc, UnitCost, CategoryCode, CreatedDate
                FROM Parts
                WHERE Active = 1 AND DeletedFlag = 0
            """,
            "transform": transform_parts
        }
    ]
    
    # Execute migration
    result = await migration_service.migrate_from_sqlserver(
        source_config=source_config,
        target_config=target_config,
        table_mappings=table_mappings,
        batch_size=1000
    )
    
    print(f"Migration ID: {result['migration_id']}")
    print(f"Status: {result['status']}")
    print(f"Total rows migrated: {result['total_rows']}")
    print(f"Errors: {result['total_errors']}")
    
    for table in result['tables_migrated']:
        print(f"  - {table['table']}: {table['rows_migrated']} rows in {table['batches']} batches")
    
    # Validate migration
    validation = await migration_service.validate_migration(
        migration_id=result['migration_id'],
        source_count_queries={"Parts": "SELECT COUNT(*) FROM Parts WHERE Active = 1"},
        target_count_queries={"plm_parts": "SELECT COUNT(*) FROM plm_parts WHERE _migration_id = '{}'".format(result['migration_id'])}
    )
    
    print(f"\nValidation status: {validation['overall_status']}")
    
    return result

# Run migration
import asyncio
result = asyncio.run(migrate_sqlserver_parts())
```

**Expected Output:**
```
Migration ID: mig_20240115_143022
Status: success
Total rows migrated: 15,420
Errors: 0
  - plm_parts: 15,420 rows in 16 batches

Validation status: pass
```

## Agent-Based Migration (Advanced)

### Using ETL Orchestrator Agent

```python
# agent_services/etl_orchestrator/main.py

class ETLOrchestratorAgent:
    async def perform_discovery(
        self, 
        records: List[Dict], 
        source_name: str, 
        target_table: str = "plm_parts"
    ) -> Dict[str, Any]:
        """
        Intelligent data discovery and migration.
        
        Workflow:
        1. Staging - Convert to DataFrame
        2. Schema Inference - Analyze column types
        3. Intelligent Mapping - Score-based column matching
        4. Transformation - Apply business rules
        5. Validation - Rule Engine + SODA checks
        6. Persistence - Load into PostgreSQL
        7. Lineage - Track in Neo4j
        """
        
        # 1. Stage data
        df = pd.DataFrame(records)
        
        # 2. Infer schema
        schema = {}
        for col in df.columns:
            schema[col] = str(df[col].dtype)
        
        # 3. Intelligent column mapping
        target_columns = ["id", "part_number", "description", "cost", "category"]
        mapping = self._intelligent_column_mapping(df.columns.tolist(), target_columns)
        
        # 4. Transform
        df_transformed = df.rename(columns=mapping)
        
        # 5. Validate
        validation_result = await self._run_rule_validation(df_transformed)
        quality_score = validation_result.get("quality_score", 0.0)
        
        # 6. Persist
        if quality_score >= 0.7:  # Quality threshold
            df_transformed.to_sql(
                target_table,
                self.engine,
                if_exists="append",
                index=False,
                method="multi"
            )
        
        # 7. Record lineage in Neo4j
        await self._record_lineage(source_name, target_table, len(df_transformed))
        
        return {
            "staged_count": len(df),
            "quality_score": quality_score,
            "mapping": mapping,
            "validation": validation_result
        }
    
    def _intelligent_column_mapping(
        self, 
        source_columns: List[str], 
        target_columns: List[str]
    ) -> Dict[str, str]:
        """Score-based column matching."""
        mapping = {}
        
        for src_col in source_columns:
            best_score = 0
            best_match = None
            
            for tgt_col in target_columns:
                score = self._calculate_similarity(src_col.lower(), tgt_col.lower())
                
                if score > best_score and score >= 50:  # Minimum threshold
                    best_score = score
                    best_match = tgt_col
            
            if best_match:
                mapping[src_col] = best_match
        
        return mapping
    
    def _calculate_similarity(self, col1: str, col2: str) -> int:
        """Calculate column name similarity score."""
        # Direct match
        if col1 == col2:
            return 100
        
        # Semantic approximations
        semantic_pairs = {
            ("part_no", "part_number"): 80,
            ("desc", "description"): 70,
            ("qty", "quantity"): 75,
            ("amt", "amount"): 75,
            ("id", "identifier"): 85,
        }
        
        for (term1, term2), score in semantic_pairs.items():
            if (term1 in col1 and term2 in col2) or (term2 in col1 and term1 in col2):
                return score
        
        # Fuzzy match (simplified)
        common = len(set(col1) & set(col2))
        max_len = max(len(col1), len(col2))
        return int((common / max_len) * 60) if max_len > 0 else 0
```

## Monitoring and Troubleshooting

### Check Migration Status

```bash
# Query migration history
GET /api/migrations/history?source_type=oracle&limit=10

# Get specific migration details
GET /api/migrations/{migration_id}

# View validation results
GET /api/migrations/{migration_id}/validation
```

### Common Issues

**1. Connection Failures**

```python
# Test connection before migration
POST /api/data-sources/test-connection
{
  "type": "sqlserver",
  "host": "sql-server.company.com",
  "port": 1433,
  "database": "ProductionDB",
  "username": "migration_user",
  "password": "password"
}
```

**2. Data Type Mismatches**

```python
# Handle Oracle NUMBER → PostgreSQL NUMERIC
def transform_numeric_types(df):
    numeric_columns = ['cost', 'quantity', 'weight']
    for col in numeric_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    return df
```

**3. Large Dataset Migrations**

```python
# Use smaller batch sizes for memory-constrained environments
table_mappings = [{
    "source_table": "LARGE_TABLE",
    "target_table": "target_table",
    "batch_size": 500  # Reduce from default 1000
}]
```

## Best Practices

1. **Test connections first** - Always validate source and target connections
2. **Start with small batches** - Test migration with limited data first
3. **Enable quality checks** - Use Rule Engine and SODA validation
4. **Track lineage** - Enable Neo4j lineage recording for auditability
5. **Validate results** - Compare row counts and sample data after migration
6. **Handle errors gracefully** - Configure error handling strategy (fail-fast vs. continue)
7. **Monitor performance** - Use batch sizing appropriate for data volume
8. **Document transformations** - Keep transformation logic in version control

## API Reference

### Migration Endpoints

- `POST /api/migrations/execute` - Start new migration
- `GET /api/migrations/{id}` - Get migration status
- `GET /api/migrations/history` - List migration history
- `POST /api/migrations/{id}/validate` - Validate migration results
- `DELETE /api/migrations/{id}/rollback` - Rollback migration (if supported)

### ETL Agent Capabilities

- `perform_data_discovery` - Intelligent schema discovery and mapping
- `manage_data_pipelines` - Orchestrate multi-step migrations
- `handle_data_transformations` - Apply business rules and transformations
- `monitor_pipeline_health` - Track migration status and quality

## See Also

- [OAuth Configuration](OAUTH_CONFIGURATION.md) - Secure connections to external systems
- [User Guide](USER_GUIDE.md) - General GraphTrace usage
- [Installation](INSTALLATION.md) - Setup and configuration
