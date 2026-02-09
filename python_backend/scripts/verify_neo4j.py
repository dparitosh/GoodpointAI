
import sys
import os
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
        
        if health['neo4j_connected']:
            from neo4j import GraphDatabase
            
            # Using the driver directly to run a cypher query
            with service.driver.session() as session:
                result = session.run("MATCH (n) RETURN count(n) as count")
                count = result.single()["count"]
                print(f"\nTotal Nodes: {count}")
                
                if count > 0:
                    print("\n--- Node Labels ---")
                    labels = session.run("MATCH (n) RETURN distinct labels(n) as l, count(*) as c")
                    for record in labels:
                        print(f"Label: {record['l']} - Count: {record['c']}")
                        
                    print("\n--- Testing Search Query (GraphRAG) ---")
                    # Try a simple text search if indexes exist
                    try:
                        res = service.run_query("Widget", top_k=1)
                        print(f"Search 'Widget' result count: {res['result_count']}")
                        if res['answers']:
                            print(f"Answer: {res['answers'][0]}")
                    except Exception as e:
                        print(f"Graph Search Error: {e}")

        else:
            print("Failed to connect to Neo4j.")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    inspect_neo4j()
