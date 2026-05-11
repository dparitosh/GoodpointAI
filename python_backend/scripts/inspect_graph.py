import requests
import json

def main():
    try:
        resp = requests.get("http://127.0.0.1:8011/api/graph")
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            nodes = data.get("nodes", [])
            edges = data.get("edges", [])
            print(f"Nodes: {len(nodes)}")
            print(f"Edges: {len(edges)}")
            if len(nodes) > 0:
                print("Sample Node:", json.dumps(nodes[0], indent=2))
            if len(edges) > 0:
                print("Sample Edge:", json.dumps(edges[0], indent=2))
        else:
            print(resp.text)
    except Exception as e:
        print(e)

if __name__ == "__main__":
    main()