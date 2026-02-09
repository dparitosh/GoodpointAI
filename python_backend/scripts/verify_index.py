
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from services.opensearch_service import OpenSearchService
from core.db_session import SessionLocal

def inspect_index():
    db = SessionLocal()
    try:
        service = OpenSearchService(db_session=db)
        client = service._build_client()
        
        if not client:
            print("Client failed to initialize.")
            return

        # Updated using patterns from conversational_search_router.py
        target_indices = "plm_*,graphtrace_e2e_*,unstructured_*"
        
        print(f"--- Checking Patterns: {target_indices} ---")
        
        # Test search capability
        try:
             # Just checks if it can search at all (even if 0 hits makes it successful connection)
            res = client.search(index=target_indices, body={"query": {"match_all": {}}}, size=1, ignore_unavailable=True)
            print(f"Search Successful against '{target_indices}'")
            print(f"Hits: {res['hits']['total']['value']}")
            
            if res['hits']['total']['value'] == 0:
                print("WARNING: 0 docs match this pattern. Search will return empty results.")
        except Exception as e:
            print(f"Search FAILED: {e}")
            
        # Test Hypothesis: User expects 'mcp_migration_published' to be searchable
        print("\n--- Testing Search Router Logic Adjustment ---")
        
        # Simulating the router's query but adding the migration index and nested fields
        target_indices_expanded = "plm_*,graphtrace_e2e_*,unstructured_*,mcp_migration_*"
        search_fields = [
            "name^3", "title^3", "part_number^2.5", 
            "description^2", "content^2", "text^2", "source_file",
            "record.name^3", "record.description^2" # Added nested fields
        ]
        
        query_text = "Widget" # Known value from previous inspection
        
        search_body = {
            "query": {
                "multi_match": {
                    "query": query_text,
                    "fields": search_fields,
                    "type": "best_fields"
                }
            },
            "size": 1
        }
        
        try:
            res = client.search(index=target_indices_expanded, body=search_body)
            print(f"Search for '{query_text}' hits: {res['hits']['total']['value']}")
            if res['hits']['hits']:
                print("SUCCESS: Found data in expanded search.")
                print("Source Index:", res['hits']['hits'][0]['_index'])
            else:
                print("FAILURE: Still no hits.")
        except Exception as e:
            print(f"Search Error: {e}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    inspect_index()
