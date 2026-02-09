import requests
import json
import sys

def test_search():
    url = "http://localhost:8011/api/search/query"
    payload = {
        "query": "Agentic ai mcp interaction code",
        "mode": "hybrid",
        "top_k": 5,
        "include_snippets": True
    }
    
    print(f"Testing Search: {url}")
    try:
        response = requests.post(url, json=payload, timeout=30)
        
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print("\n--- Search Response Summary ---")
            print(f"Mode: {data.get('mode')}")
            print(f"Total Results: {data.get('total_count')}")
            print(f"Took: {data.get('took_ms')}ms")
            
            results = data.get('results', [])
            if results:
                print(f"\nTop {len(results)} Results:")
                for i, res in enumerate(results[:3]):
                    print(f"{i+1}. [{res.get('score', 0):.2f}] {res.get('title')} ({res.get('source_type')})")
            else:
                print("\nNo results found.")
                
            return True
        else:
            print(f"Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"Connection Failed: {e}")
        return False

if __name__ == "__main__":
    success = test_search()
    sys.exit(0 if success else 1)
