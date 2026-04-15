"""List all PostgreSQL tables defined in SQLAlchemy models."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import Base
import importlib

# Import all model modules
for module_name in [
    "models.configuration_models",
    "models.graphql_models", 
    "models.workflow_models",
    "models.plm_models",
    "models.quality_models",
    "models.report_models",
    "models.pipeline_config_models",
    "models.admin_config_models",
    "models.rule_engine_models",
]:
    importlib.import_module(module_name)

print("\n" + "="*80)
print("PostgreSQL Tables Registered in SQLAlchemy")
print("="*80)

tables = sorted(Base.metadata.tables.values(), key=lambda x: x.name)

for i, table in enumerate(tables, 1):
    print(f"\n{i:2d}. {table.name}")
    print(f"    Columns: {len(table.columns)}")
    
    # Show primary keys
    pks = [col.name for col in table.columns if col.primary_key]
    if pks:
        print(f"    Primary Key(s): {', '.join(pks)}")
    
    # Show key columns (first 5)
    key_cols = [col.name for col in list(table.columns)[:5]]
    if len(table.columns) > 5:
        print(f"    Key Columns: {', '.join(key_cols)}, ... (+{len(table.columns)-5} more)")
    else:
        print(f"    Key Columns: {', '.join(key_cols)}")

print(f"\n{'='*80}")
print(f"Total Tables: {len(tables)}")
print(f"{'='*80}\n")
