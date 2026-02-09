import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from core.db_session import SessionLocal
from services.admin_config_service import AdminConfigService

def check_connections():
    db = SessionLocal()
    try:
        acs = AdminConfigService(db)
        config = acs.get_connection_config("opensearch")
        print("--- OpenSearch Config from AdminConfigService ---")
        print(config)
        
        # Also check EncryptedConfig manually to see if it exists
        from models.configuration_models import EncryptedConfig
        row = db.get(EncryptedConfig, "opensearch")
        if row:
            print(f"--- Legacy EncryptedConfig found for 'opensearch': Yes (ID: {row.key}) ---")
        else:
            print("--- Legacy EncryptedConfig found for 'opensearch': No ---")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_connections()
