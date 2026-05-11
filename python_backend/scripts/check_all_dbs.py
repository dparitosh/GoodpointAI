import os
from neo4j import GraphDatabase
from dotenv import load_dotenv
from pathlib import Path

# Load .env
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

uri = os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
user = os.getenv("NEO4J_USER", "neo4j")
password = os.getenv("NEO4J_PASSWORD", "")

print(f"Connecting to {uri} as {user}...")

try:
    driver = GraphDatabase.driver(uri, auth=(user, password))
    
    # List databases
    with driver.session(database="system") as session:
        result = session.run("SHOW DATABASES")
        dbs = [record["name"] for record in result]
    
    print(f"Found databases: {dbs}")
    
    for db in dbs:
        if db == "system":
            continue
        try:
            with driver.session(database=db) as session:
                count = session.run("MATCH (n) RETURN count(n) as c").single()["c"]
                print(f"Database '{db}': {count} nodes")
        except Exception as e:
            print(f"Database '{db}': Failed to count ({e})")
            
    driver.close()
except Exception as e:
    print(f"Error: {e}")
