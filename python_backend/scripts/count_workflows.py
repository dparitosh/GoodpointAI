import sys
import os

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from core.db_session import SessionLocal

def check_workflows():
    db = SessionLocal()
    try:
        result = db.execute(text("SELECT count(*) FROM workflow_instances"))
        count = result.scalar()
        print(f"Total Workflow Instances: {count}")
        
        if count > 0:
            rows = db.execute(text("SELECT id, name, status, processed_records FROM workflow_instances LIMIT 5")).fetchall()
            print("\nExamples:")
            for row in rows:
                print(f"- {row[0]}: {row[1]} ({row[2]}) - Processed: {row[3]}")
    except Exception as e:
        print(f"Error checking workflows: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_workflows()
