import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from neo4j import GraphDatabase

# Replicate setup
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)
db_name = os.getenv("NEO4J_DATABASE", "neo4j")
uri = os.getenv("NEO4J_URI", "neo4j://localhost:7687")
user = os.getenv("NEO4J_USER", "neo4j")
password = os.getenv("NEO4J_PASSWORD", "")

print(f"Connecting to {uri} DB={db_name} as {user}")

DEFAULT_GRAPH_QUERY = "MATCH (n) OPTIONAL MATCH (n)-[r]-(m) RETURN n, r, m"

async def main():
    driver = GraphDatabase.driver(uri, auth=(user, password))
    
    # Use execute_query (5.x API used in router)
    try:
        # Note: driver.execute_query is synchronous in standard driver? 
        # But router uses `neo4j.AsyncDriver`.
        # I'll use sync driver but same method signature pattern if possible, or just session.
        # router.py uses: driver_instance.execute_query(..., database_=NEO4J_DATABASE)
        
        # Verify driver version first
        import neo4j
        print(f"Neo4j Driver Version: {neo4j.__version__}")
        
        with driver.session(database=db_name) as session:
            print(f"Running query: {DEFAULT_GRAPH_QUERY}")
            result = session.run(DEFAULT_GRAPH_QUERY)
            records = list(result)
            print(f"Found {len(records)} records")
            if len(records) > 0:
                print("First record keys:", records[0].keys())
                n = records[0].get("n")
                print("First node:", n)
                if hasattr(n, 'element_id'):
                     print("Element ID:", n.element_id)
                else:
                     print("No element_id on node!")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        driver.close()

if __name__ == "__main__":
    asyncio.run(main())
