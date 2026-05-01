import io
import ollama
import requests
import sys

# PowerShell 5 / cp1252 compatibility
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "buffer"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# 1. Check raw HTTP connectivity
print("Checking Ollama API connectivity...")
try:
    resp = requests.get("http://localhost:11434")
    print(f"[OK]  Ollama Server Status: {resp.status_code}")
except Exception as e:
    print(f"[FAIL] Ollama server not reachable: {e}")
    print()
    print("  Cause: Ollama is not running or is not installed.")
    print("  Fix:   Install Ollama from https://ollama.com/download")
    print("         Then start it:  ollama serve")
    print("         Or on Windows it auto-starts as a system tray app after install.")
    print()
    print("  Note:  Ollama is OPTIONAL. Only multimodal/vision features require it.")
    sys.exit(1)

# 2. Check Python Client & Models
print("\nChecking available models via Python library...")
try:
    # ollama.list() returns a dict with 'models' key which is a list
    models_response = ollama.list()
    
    if hasattr(models_response, 'models'):
        models_list = models_response.models
    elif isinstance(models_response, dict):
        models_list = models_response.get('models', [])
    else:
        models_list = models_response

    print(f"Found {len(models_list)} models.")
    
    vision_models = []
    for m in models_list:
        name = m.model if hasattr(m, 'model') else m.get('name', 'unknown')
        print(f"  - {name}")
        
        if 'llava' in name.lower() or 'bakllava' in name.lower() or 'moondream' in name.lower():
            vision_models.append(name)

    print("-" * 30)
    if vision_models:
        print(f"[OK]  Found vision-capable models: {', '.join(vision_models)}")
        print("      Multimodal Vision features should WORK.")
        sys.exit(0)
    else:
        print("[FAIL] No vision-capable models found (llava, bakllava, moondream).")
        print()
        print("  Cause: Vision models have not been pulled into Ollama yet.")
        print("  Fix:   ollama pull llava")
        print("         ollama pull llava:13b   (higher quality, needs ~8 GB VRAM)")
        print("         ollama pull moondream   (lightweight alternative)")
        print()
        print("  Note:  Text-only LLM features still work if a text model is loaded.")
        sys.exit(1)

except Exception as e:
    print(f"[FAIL] Error listing models: {e}")
    print("  Fix:  Ensure Ollama is running:  ollama serve")
    sys.exit(1)

