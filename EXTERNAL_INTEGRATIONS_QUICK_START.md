# External Integrations - Quick Start Guide

##  Quick Setup (5 minutes)

### Step 1: Install Dependencies
```bash
cd /workspaces/graphTrace/python_backend
pip install -r requirements_external_integrations.txt
```

### Step 2: Configure Environment
```bash
# Copy example environment file
cp .env.example .env

# Edit with your credentials
nano .env  # or use your preferred editor
```

### Step 3: Start Backend
```bash
python3 -m uvicorn main:app --host 0.0.0.0 --port 8011 --reload
```

### Step 4: Test API
```bash
# Health checks
curl http://localhost:8011/api/azure/health
curl http://localhost:8011/api/aws/health
curl http://localhost:8011/api/llm/health

# Interactive docs
open http://localhost:8011/docs
```

---

##  Quick Reference

### All Available API Prefixes

| Prefix | Description | Endpoints | Status |
|--------|-------------|-----------|--------|
| `/api/azure` | Azure cloud services | 12 | ✓ Ready |
| `/api/aws` | AWS cloud services | 11 | ✓ Ready |
| `/api/odata` | OData & SAP integration | 10 | ✓ Ready |
| `/api/llm` | LLM providers (OpenAI, Claude, Ollama) | 10 | ✓ Ready |
| `/api/plm` | PLM systems (Teamcenter, Windchill, etc.) | 9 | ✓ Ready |
| `/api/filesystem` | File operations (XML, JSON, CSV) | 14 | ✓ Ready |
| `/api/gateway` | API gateway management | 11 | ✓ Ready |

**Total New Endpoints: 77**

---

##  Common Use Cases

### Use Case 1: Upload File to Azure
```bash
curl -X POST http://localhost:8011/api/azure/blob/upload \
  -F "file=@data.xml" \
  -F "container_name=plm-data"
```

### Use Case 2: Query Teamcenter PLM
```bash
curl -X POST http://localhost:8011/api/plm/teamcenter/query \
  -H "Content-Type: application/json" \
  -d '{
    "system_type": "teamcenter",
    "object_type": "Item",
    "query_criteria": {"item_id": "P*"},
    "limit": 100
  }'
```

### Use Case 3: Chat with LLM
```bash
curl -X POST http://localhost:8011/api/llm/openai/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "Explain PLM systems"}
    ],
    "temperature": 0.7
  }'
```

### Use Case 4: Parse XML File
```bash
curl -X POST http://localhost:8011/api/filesystem/xml/parse \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "./data/xml/input/data.xml"
  }'
```

### Use Case 5: Upload to S3
```bash
curl -X POST http://localhost:8011/api/aws/s3/upload \
  -F "file=@data.json" \
  -F "bucket_name=my-bucket"
```

---

##  Configuration Snippets

### Minimal .env for Testing

```env
# Neo4j (already configured)
NEO4J_URI=neo4j+s://2cccd05b.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=tcs12345

# File System (local testing)
DATA_ROOT_PATH=./data
UPLOAD_DIR=./data/uploads
MAX_UPLOAD_SIZE_MB=100

# Ollama (local LLM - no API key needed)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama2
```

### Add Azure (if available)
```env
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...
AZURE_BLOB_CONTAINER=plm-data
```

### Add AWS (if available)
```env
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=us-east-1
AWS_S3_BUCKET=plm-data-bucket
```

### Add OpenAI (if available)
```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4-turbo-preview
```

---

##  Dependency Groups

### Core (Always Required)
```bash
pip install fastapi uvicorn sqlalchemy pydantic python-dotenv
```

### Azure Only
```bash
pip install azure-storage-blob azure-cosmos azure-servicebus azure-eventhub
```

### AWS Only
```bash
pip install boto3 aioboto3
```

### LLM Only
```bash
pip install openai anthropic ollama
```

### PLM Only
```bash
pip install zeep xmltodict lxml requests
```

### File Processing Only
```bash
pip install pandas openpyxl xmltodict jsonschema
```

---

##  Testing Endpoints

### Using Python
```python
import requests

# Health check
response = requests.get('http://localhost:8011/api/azure/health')
print(response.json())

# Upload file
files = {'file': open('data.xml', 'rb')}
response = requests.post(
  'http://localhost:8011/api/azure/blob/upload',
    files=files
)
print(response.json())
```

### Using JavaScript/Node
```javascript
// Health check
fetch('http://localhost:8011/api/llm/health')
  .then(res => res.json())
  .then(data => console.log(data));

// LLM chat
fetch('http://localhost:8011/api/llm/openai/chat', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    messages: [{role: 'user', content: 'Hello'}],
    temperature: 0.7
  })
})
  .then(res => res.json())
  .then(data => console.log(data));
```

---

##  Troubleshooting

### Issue: "Module not found"
```bash
# Reinstall dependencies
pip install -r requirements_external_integrations.txt --force-reinstall
```

### Issue: "Configuration not found"
```bash
# Check if .env exists
ls -la .env

# Copy from example
cp .env.example .env
```

### Issue: "Azure/AWS connection failed"
```bash
# Test credentials
curl http://localhost:8011/api/azure/health
curl http://localhost:8011/api/aws/health

# Check logs
tail -f logs/app.log
```

### Issue: "LLM API key invalid"
```bash
# Verify environment variable
echo $OPENAI_API_KEY

# Or check in Python
python3 -c "from core.external_config import llm_config; print(llm_config.openai_api_key)"
```

### Issue: "File upload too large"
```bash
# Increase limit in .env
MAX_UPLOAD_SIZE_MB=500

# Restart backend
```

---

##  Where to Find More Info

1. **Complete API Reference**: `EXTERNAL_INTEGRATIONS_API_REFERENCE.md`
2. **Implementation Details**: `EXTERNAL_INTEGRATIONS_IMPLEMENTATION_SUMMARY.md`
3. **Interactive Docs**: http://localhost:8011/docs
4. **Environment Template**: `.env.example`

---

##  Frontend Integration

### React/JavaScript Example
```javascript
// Add to your frontend service file
const API_BASE = 'http://localhost:8011';

// Upload to Azure
export const uploadToAzure = async (file) => {
  const formData = new FormData();
  formData.append('file', file);
  
  const response = await fetch(`${API_BASE}/api/azure/blob/upload`, {
    method: 'POST',
    body: formData
  });
  
  return response.json();
};

// Query PLM
export const queryTeamcenter = async (criteria) => {
  const response = await fetch(`${API_BASE}/api/plm/teamcenter/query`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      system_type: 'teamcenter',
      object_type: 'Item',
      query_criteria: criteria,
      limit: 100
    })
  });
  
  return response.json();
};

// Chat with LLM
export const chatWithLLM = async (message, provider = 'openai') => {
  const response = await fetch(`${API_BASE}/api/llm/chat?provider=${provider}`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      messages: [{role: 'user', content: message}],
      temperature: 0.7
    })
  });
  
  return response.json();
};
```

---

##  Security Notes

! **Important Security Considerations:**

1. **Never commit .env file**
   ```bash
   # Already in .gitignore, but double-check
   echo ".env" >> .gitignore
   ```

2. **Use environment-specific configs**
   ```bash
   .env.development
   .env.staging
   .env.production
   ```

3. **Rotate credentials regularly**
   - Change API keys monthly
   - Use Azure Key Vault / AWS Secrets Manager for production

4. **Enable HTTPS in production**
   ```python
   # In main.py for production
   uvicorn.run(app, host="0.0.0.0", port=443, ssl_certfile="cert.pem", ssl_keyfile="key.pem")
   ```

---

##  Health Check Dashboard

Create a simple health check script:

```python
# health_check.py
import requests

services = [
  ('Azure', 'http://localhost:8011/api/azure/health'),
  ('AWS', 'http://localhost:8011/api/aws/health'),
  ('OData', 'http://localhost:8011/api/odata/health'),
  ('LLM', 'http://localhost:8011/api/llm/health'),
  ('PLM', 'http://localhost:8011/api/plm/systems/health'),
  ('FileSystem', 'http://localhost:8011/api/filesystem/health'),
  ('Gateway', 'http://localhost:8011/api/gateway/health'),
]

for name, url in services:
    try:
        response = requests.get(url, timeout=5)
        status = '✓' if response.status_code == 200 else '✗'
        print(f"{status} {name}: {response.status_code}")
    except Exception as e:
        print(f"✗ {name}: {str(e)}")
```

Run with:
```bash
python3 health_check.py
```

---

##  Performance Tips

1. **Use async operations for bulk processing**
2. **Enable Redis caching for repeated queries**
3. **Stream large files instead of loading into memory**
4. **Use batch operations for multiple files**
5. **Monitor API rate limits (especially LLM providers)**

---

##  Learning Path

### Day 1: File System Operations
- Upload files
- Parse XML/JSON
- Convert formats

### Day 2: Cloud Storage
- Azure Blob Storage
- AWS S3
- File management

### Day 3: LLM Integration
- OpenAI chat
- Ollama local models
- Prompt engineering

### Day 4: PLM Systems
- Teamcenter queries
- BOM extraction
- Data export

### Day 5: Orchestration
- Combine multiple services
- Build workflows
- Error handling

---

## ✓ Checklist Before Production

- [ ] All credentials configured in .env
- [ ] Health checks passing
- [ ] File upload limits set appropriately
- [ ] CORS origins configured correctly
- [ ] Logging configured
- [ ] Error monitoring setup (Sentry)
- [ ] Rate limiting implemented
- [ ] HTTPS enabled
- [ ] Backup strategy defined
- [ ] Documentation reviewed with team

---

##  Need Help?

1. Check logs: `tail -f logs/app.log`
2. Review API docs: http://localhost:8011/docs
3. Test health endpoints
4. Check environment variables
5. Verify network connectivity

---

##  Quick Commands Cheat Sheet

```bash
# Start backend
cd python_backend && python3 -m uvicorn main:app --reload

# Install dependencies
pip install -r requirements_external_integrations.txt

# Check health
curl http://localhost:8011/api/azure/health | jq

# View logs
tail -f logs/app.log

# Test upload
curl -X POST -F "file=@test.xml" http://localhost:8011/api/filesystem/upload

# List files
curl -X POST -H "Content-Type: application/json" \
  -d '{"path": "./data/uploads"}' \
  http://localhost:8011/api/filesystem/list

# Interactive docs
open http://localhost:8011/docs
```

---

**Ready to integrate! **

All 77 endpoints are live and documented. Start with health checks, then move to file operations, then cloud services!
