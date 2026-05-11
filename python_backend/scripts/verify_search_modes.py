
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from services.opensearch_service import OpenSearchService
from core.db_session import SessionLocal

def check_vector_capabilities():
    db = SessionLocal()
    try:
        service = OpenSearchService(db_session=db)
        client = service._build_client()
        
        if not client:
            print("OpenSearch client not available.")
            return

        print("\n--- 1. Checking Existence of Vector Indices ---")
        # Check specifically for the index pattern used in code
        knn_pattern = "graphtrace_e2e_knn*"
        indices = client.cat.indices(index=knn_pattern, format="json")
        if not indices:
             print(f"Index pattern '{knn_pattern}' found NO match.")
        else:
             print(f"Index pattern '{knn_pattern}' matched: {[i['index'] for i in indices]}")

        print("\n--- 2. Checking Migration Index for Vector Fields ---")
        migration_index = "mcp_migration_published"
        if client.indices.exists(index=migration_index):
            mapping = client.indices.get_mapping(index=migration_index)
            # Dump full mapping to see nested types
            # print(json.dumps(mapping, indent=2)) 
            
            # Recursive search for 'knn_vector' type or fields named 'embedding'/'vector'
            has_vector = False
            
            def check_props(props, prefix=""):
                nonlocal has_vector
                for k, v in props.items():
                    full_name = f"{prefix}.{k}" if prefix else k
                    if 'type' in v and v['type'] == 'knn_vector':
                        print(f" [FOUND] Vector field: {full_name} (type: knn_vector)")
                        has_vector = True
                    if k in ['embedding', 'content_vector', 'vector']:
                        print(f" [FOUND] Potential vector field name: {full_name} (type: {v.get('type', 'unknown')})")
                        if v.get('type') == 'float' or v.get('type') == 'knn_vector':
                             has_vector = True
                    
                    if 'properties' in v:
                        check_props(v['properties'], full_name)
            
            props = mapping[migration_index]['mappings'].get('properties', {})
            check_props(props)
            
            if not has_vector:
                print(f"No explicit vector/embedding fields found in '{migration_index}'.")
        else:
            print(f"Index '{migration_index}' does not exist.")

        print("\n--- 3. Testing 'Vector Mode' Fallback (More-Like-This) ---")
        # In conversational_search_router.py, if KNN fails, it tries 'more_like_this' on ALL_SEARCH_INDICES
        # We manually test this fallback mechanics
        all_indices_pattern = "plm_*,graphtrace_e2e_*,unstructured_*,mcp_migration_*"
        
        mlt_body = {
            "query": {
                "more_like_this": {
                    "fields": ["name", "title", "description", "content", "text", "record.name", "record.description"],
                    "like": "Widget",
                    "min_term_freq": 1,
                    "min_doc_freq": 1,
                    "max_query_terms": 25,
                    "minimum_should_match": "0%" # Loose matching for test
                }
            },
            "size": 5,
            "_source": True
        }
        
        try:
            res = client.search(index=all_indices_pattern, body=mlt_body)
            hits = res.get("hits", {}).get("hits", [])
            print(f"MLT Fallback Hits: {len(hits)}")
            if hits:
                print(f"Sample Hit: {hits[0]['_source'].get('record', {}).get('name') or hits[0]['_index']}")
        except Exception as e:
            print(f"MLT Fallback Failed: {e}")


        print("\n--- 4. Conclusion ---")
        if indices:
            print("True Vector Search (KNN): LIKELY WORKING (Target indices exist).")
        elif hits:
             print("True Vector Search (KNN): NOT WORKING (Indicies missing).")
             print("Fallback Vector Sim (MLT): WORKING (Found data via 'More Like This').")
        else:
             print("Vector Search: NOT WORKING (Both KNN and MLT Fallback failed).")
             
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_vector_capabilities()
