
import io
import sys
import os

# PowerShell 5 / cp1252 compatibility
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "buffer"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from services.neo4j_graphrag_service import Neo4jGraphRAGService
from core.db_session import SessionLocal

def inspect_neo4j():
    db = SessionLocal()
    try:
        service = Neo4jGraphRAGService(db_session=db)
        
        print("--- Connecting to Neo4j ---")
        health = service.health_check()
        print(f"Status: {health['status']}")
        print(f"Connected: {health['neo4j_connected']}")
        
        if not health['neo4j_connected']:
            status = health.get('status', '')
            error  = str(health.get('error', '') or health.get('message', '')).lower()

            print()
            print("[FAIL] Neo4j connection failed.")

            if 'refused' in error or 'unavailable' in error or 'timeout' in error:
                print("  Cause: Neo4j service is not running or unreachable at the configured URI.")
                print("  Fix:   Start Neo4j locally:")
                print("           docker run -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/password neo4j:5")
                print("  Fix:   Or verify NEO4J_URI in python_backend/.env points to a running instance.")
            elif 'auth' in error or 'unauthorized' in error or 'forbidden' in error or 'credentials' in error:
                print("  Cause: Authentication failed. Neo4j rejected the username/password.")
                print("  Fix:   Check NEO4J_USERNAME and NEO4J_PASSWORD in python_backend/.env.")
                print("         Default credentials for Neo4j 5+ are neo4j / <chosen at first login>.")
            elif 'not found' in error or 'no route' in error:
                print("  Cause: The NEO4J_URI hostname/IP cannot be resolved or routed.")
                print("  Fix:   Check NEO4J_URI in python_backend/.env.")
                print("         Example: NEO4J_URI=bolt://localhost:7687")
            else:
                print(f"  Cause: {health.get('error') or health.get('message') or 'Unknown error'}")
                print("  Fix:   Check NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD in python_backend/.env.")
                print("         Ensure Neo4j 5.x is running and bolt port 7687 is accessible.")

            print()
            print("  Note:  Neo4j is OPTIONAL. The backend starts without it; only Graph RAG")
            print("         features are affected. Set NEO4J_URI= (empty) to suppress this warning.")
            return 1

        from neo4j import GraphDatabase

        # Using the driver directly to run a cypher query
        with service.driver.session() as session:
            result = session.run("MATCH (n) RETURN count(n) as count")
            count = result.single()["count"]
            print(f"\n[OK] Total Nodes: {count}")
            
            if count > 0:
                print("\n--- Node Labels ---")
                labels = session.run("MATCH (n) RETURN distinct labels(n) as l, count(*) as c")
                for record in labels:
                    print(f"  Label: {record['l']} - Count: {record['c']}")
                    
                print("\n--- Testing Search Query (GraphRAG) ---")
                try:
                    res = service.run_query("Widget", top_k=1)
                    print(f"[OK] Search result count: {res['result_count']}")
                    if res['answers']:
                        print(f"     Answer: {res['answers'][0]}")
                except Exception as e:
                    print(f"[WARN] Graph Search Error: {e}")
            else:
                print("\n[INFO] Graph is empty. Import data to populate nodes.")
                print("       See docs/ for data import instructions.")

        return 0

    except Exception as e:
        err = str(e).lower()
        print(f"\n[FAIL] Unexpected error: {e}")
        if 'refused' in err or 'timeout' in err:
            print("  Cause: Neo4j is not running.")
            print("  Fix:   docker run -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/password neo4j:5")
        elif 'module' in err or 'import' in err:
            print("  Cause: neo4j Python driver not installed.")
            print("  Fix:   pip install neo4j==5.25.0")
        else:
            print("  Fix:   Check NEO4J_URI/NEO4J_USERNAME/NEO4J_PASSWORD in python_backend/.env.")
        return 1
    finally:
        db.close()

if __name__ == "__main__":
    raise SystemExit(inspect_neo4j())
