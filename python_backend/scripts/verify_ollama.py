import ollama
import requests
import sys

# 1. Check raw HTTP connectivity
print("Checking Ollama API connectivity...")
try:
    resp = requests.get("http://localhost:11434")
    print(f"Ollama Server Status: {resp.status_code} (OK)")
except Exception as e:
    print(f"Ollama Server Status: FAIL connection ({e})")
    sys.exit(1)

# 2. Check Python Client & Models
print("\nChecking available models via Python library...")
try:
    # ollama.list() returns a dict with 'models' key which is a list
    models_response = ollama.list()
    # It seems the structure might have changed in recent versions or depends on version.
    # The router code uses: models.get('models', [])
    
    if hasattr(models_response, 'models'):
        # For object-based response in newer clients
        models_list = models_response.models
    elif isinstance(models_response, dict):
        models_list = models_response.get('models', [])
    else:
        models_list = models_response # Fallback if it returns list directly

    print(f"Found {len(models_list)} models.")
    
    vision_models = []
    for m in models_list:
        # Handling potentially different model object structures
        name = m.model if hasattr(m, 'model') else m.get('name', 'unknown')
        print(f" - {name}")
        
        if 'llava' in name.lower() or 'bakllava' in name.lower() or 'moondream' in name.lower():
            vision_models.append(name)

    print("-" * 30)
    if vision_models:
        print(f"SUCCESS: Found vision-capable models: {', '.join(vision_models)}")
        print("Multimodal Vision features should WORK.")
    else:
        print("WARNING: No common vision models (llava, bakllava) found.")
        print("Multimodal Vision features will FAIL until you run: 'ollama pull llava'")

except Exception as e:
    print(f"Error listing models: {e}")
