# External Integrations - Complete API Reference

## Overview

This document provides a comprehensive guide to all external data source and cloud service integrations available in the GraphTrace backend.

## Table of Contents

1. [Azure Cloud Services](#azure-cloud-services)
2. [AWS Cloud Services](#aws-cloud-services)
3. [OData Services](#odata-services)
4. [LLM Integration](#llm-integration)
5. [PLM Systems](#plm-systems)
6. [File System Operations](#file-system-operations)
7. [API Gateway Management](#api-gateway-management)
8. [Configuration](#configuration)
9. [Dependencies](#dependencies)

---

## Azure Cloud Services

### Base URL: `/api/azure`

### Azure Blob Storage

#### Upload File
```http
POST /api/azure/blob/upload
Content-Type: multipart/form-data

Parameters:
- file: UploadFile (required)
- container_name: string (default: "plm-data")
- blob_name: string (optional)
```

#### List Blobs
```http
GET /api/azure/blob/list/{container_name}?prefix=optional_prefix
```

#### Download Blob
```http
GET /api/azure/blob/download/{container_name}/{blob_name}
```

#### Delete Blob
```http
DELETE /api/azure/blob/delete/{container_name}/{blob_name}
```

### Azure Data Lake Gen2

#### Upload to Data Lake
```http
POST /api/azure/datalake/upload
Content-Type: multipart/form-data

Parameters:
- file: UploadFile
- file_system: string (default: "raw-data")
- directory_path: string
- file_name: string (optional)
```

### Azure Cosmos DB

#### Create/Update Document
```http
POST /api/azure/cosmos/document
Content-Type: application/json

{
  "container_id": "workflow-state",
  "document": {
    "id": "doc123",
    "data": "..."
  },
  "partition_key": "key1"
}
```

#### Query Documents
```http
GET /api/azure/cosmos/documents/{container_id}?query=SELECT * FROM c&partition_key=key1
```

### Azure Service Bus

#### Send Message
```http
POST /api/azure/servicebus/send
Content-Type: application/json

{
  "queue_name": "workflow-queue",
  "message_body": {
    "event": "workflow_started",
    "data": {}
  },
  "properties": {
    "correlation_id": "123"
  }
}
```

### Azure Event Hub

#### Send Events
```http
POST /api/azure/eventhub/send
Content-Type: application/json

{
  "event_hub_name": "plm-events",
  "events": [
    {"type": "part_created", "timestamp": "2025-11-24T10:00:00Z"},
    {"type": "part_updated", "timestamp": "2025-11-24T10:01:00Z"}
  ],
  "partition_key": "optional_key"
}
```

---

## AWS Cloud Services

### Base URL: `/api/aws`

### AWS S3

#### Upload File
```http
POST /api/aws/s3/upload
Content-Type: multipart/form-data

Parameters:
- file: UploadFile (required)
- bucket_name: string (optional)
- key: string (optional)
```

#### List Objects
```http
GET /api/aws/s3/list/{bucket_name}?prefix=optional_prefix
```

#### Download Object
```http
GET /api/aws/s3/download/{bucket_name}/{key}
```

#### Delete Object
```http
DELETE /api/aws/s3/delete/{bucket_name}/{key}
```

### AWS DynamoDB

#### Put Item
```http
POST /api/aws/dynamodb/put
Content-Type: application/json

{
  "table_name": "workflow-state",
  "item": {
    "id": "workflow_123",
    "status": "running",
    "timestamp": "2025-11-24T10:00:00Z"
  }
}
```

#### Query Table
```http
POST /api/aws/dynamodb/query
Content-Type: application/json

{
  "table_name": "workflow-state",
  "key_condition_expression": "id = :id",
  "expression_attribute_values": {
    ":id": "workflow_123"
  }
}
```

#### Scan Table
```http
GET /api/aws/dynamodb/scan/{table_name}?limit=100
```

### AWS SQS

#### Send Message
```http
POST /api/aws/sqs/send
Content-Type: application/json

{
  "queue_url": "https://sqs.us-east-1.amazonaws.com/123456789/queue-name",
  "message_body": {
    "action": "process_workflow"
  },
  "message_attributes": {}
}
```

#### Receive Messages
```http
GET /api/aws/sqs/receive/{queue_url}?max_messages=10
```

### AWS Lambda

#### Invoke Function
```http
POST /api/aws/lambda/invoke
Content-Type: application/json

{
  "function_name": "data-processor",
  "payload": {
    "input": "data"
  },
  "invocation_type": "RequestResponse"
}
```

---

## OData Services

### Base URL: `/api/odata`

### Service Discovery

#### Get Metadata
```http
GET /api/odata/metadata?service_url=https://odata-service.com/api
```

#### List Entity Sets
```http
GET /api/odata/entities?service_url=https://odata-service.com/api
```

### CRUD Operations

#### Query Entities
```http
POST /api/odata/query
Content-Type: application/json

{
  "service_url": "https://odata-service.com/api",
  "entity_set": "Parts",
  "filter": "Status eq 'Active'",
  "select": "PartNumber,Description",
  "expand": "BOM",
  "orderby": "CreatedDate desc",
  "top": 100,
  "skip": 0
}
```

#### Get Single Entity
```http
GET /api/odata/entity/{entity_set}/{key}?service_url=https://odata-service.com/api
```

#### Create Entity
```http
POST /api/odata/create
Content-Type: application/json

{
  "service_url": "https://odata-service.com/api",
  "entity_set": "Parts",
  "data": {
    "PartNumber": "P12345",
    "Description": "New Part"
  }
}
```

#### Update Entity
```http
PUT /api/odata/update
Content-Type: application/json

{
  "service_url": "https://odata-service.com/api",
  "entity_set": "Parts",
  "key": "'P12345'",
  "data": {
    "Description": "Updated Description"
  }
}
```

#### Delete Entity
```http
DELETE /api/odata/delete/{entity_set}/{key}?service_url=https://odata-service.com/api
```

### SAP OData

#### List SAP Entity Sets
```http
GET /api/odata/sap/entity-sets
```

---

## LLM Integration

### Base URL: `/api/llm`

### OpenAI

#### Chat Completion
```http
POST /api/llm/openai/chat
Content-Type: application/json

{
  "messages": [
    {"role": "system", "content": "You are a helpful assistant"},
    {"role": "user", "content": "Explain PLM systems"}
  ],
  "model": "gpt-4-turbo-preview",
  "temperature": 0.7,
  "max_tokens": 1000
}
```

#### Text Embedding
```http
POST /api/llm/openai/embedding
Content-Type: application/json

{
  "text": "Product lifecycle management data",
  "model": "text-embedding-3-small"
}
```

### Anthropic Claude

#### Chat Completion
```http
POST /api/llm/anthropic/chat
Content-Type: application/json

{
  "messages": [
    {"role": "user", "content": "Analyze this BOM structure"}
  ],
  "model": "claude-3-sonnet-20240229",
  "temperature": 0.7,
  "max_tokens": 1024
}
```

### Azure OpenAI

#### Chat Completion
```http
POST /api/llm/azure-openai/chat
Content-Type: application/json

{
  "messages": [
    {"role": "user", "content": "Generate migration plan"}
  ],
  "model": "gpt-4-deployment",
  "temperature": 0.7
}
```

### Ollama (Local LLM)

#### Chat Completion
```http
POST /api/llm/ollama/chat
Content-Type: application/json

{
  "messages": [
    {"role": "user", "content": "Help me with data quality"}
  ],
  "model": "llama2",
  "temperature": 0.7
}
```

#### Text Generation
```http
POST /api/llm/ollama/generate
Content-Type: application/json

{
  "prompt": "Generate SQL query for...",
  "model": "llama2",
  "temperature": 0.7
}
```

#### List Models
```http
GET /api/llm/ollama/models
```

#### Embedding
```http
POST /api/llm/ollama/embedding
Content-Type: application/json

{
  "text": "Text to embed",
  "model": "llama2"
}
```

### Unified LLM Endpoint

```http
POST /api/llm/chat?provider=openai
Content-Type: application/json

{
  "messages": [...],
  "temperature": 0.7
}

Providers: openai, anthropic, azure-openai, ollama
```

---

## PLM Systems

### Base URL: `/api/plm`

### Teamcenter

#### Query Objects
```http
POST /api/plm/teamcenter/query
Content-Type: application/json

{
  "system_type": "teamcenter",
  "object_type": "Item",
  "query_criteria": {
    "item_id": "P*"
  },
  "properties": ["item_id", "object_name", "object_desc"],
  "limit": 100
}
```

#### Get BOM
```http
GET /api/plm/teamcenter/bom/{part_id}?levels=-1
```

### Windchill

#### Query Objects
```http
POST /api/plm/windchill/query
Content-Type: application/json

{
  "system_type": "windchill",
  "object_type": "Part",
  "query_criteria": {
    "State": "Released"
  },
  "properties": ["Number", "Name", "Version"],
  "limit": 100
}
```

#### Get Part
```http
GET /api/plm/windchill/part/{part_number}
```

### ENOVIA / 3DEXPERIENCE

#### Query Objects
```http
POST /api/plm/enovia/query
Content-Type: application/json

{
  "system_type": "enovia",
  "object_type": "Part",
  "query_criteria": {
    "current": "Release"
  },
  "properties": ["name", "title", "owner"],
  "limit": 100
}
```

### Aras Innovator

#### Query Objects (SOAP/AML)
```http
POST /api/plm/aras/query
Content-Type: application/json

{
  "system_type": "aras",
  "object_type": "Part",
  "query_criteria": {
    "state": "Released"
  },
  "limit": 100
}
```

### CAD File Metadata

#### Extract Metadata
```http
GET /api/plm/cad/metadata/{system}/{file_id}

Systems: catia, nx, creo
```

### Export PLM Data

```http
POST /api/plm/export
Content-Type: application/json

{
  "system_type": "teamcenter",
  "object_type": "Item",
  "object_ids": ["P12345", "P12346"],
  "format": "json"
}
```

---

## File System Operations

### Base URL: `/api/filesystem`

### Directory Operations

#### List Directory
```http
POST /api/filesystem/list
Content-Type: application/json

{
  "path": "./data/uploads",
  "recursive": false,
  "filter_extension": "xml"
}
```

#### Upload File
```http
POST /api/filesystem/upload
Content-Type: multipart/form-data

Parameters:
- file: UploadFile
- destination_path: string (optional)
```

#### Download File
```http
GET /api/filesystem/download/{file_path}
```

#### Delete File
```http
DELETE /api/filesystem/delete/{file_path}
```

### XML Processing

#### Parse XML
```http
POST /api/filesystem/xml/parse
Content-Type: application/json

{
  "file_path": "./data/xml/input/data.xml",
  "namespace_map": {
    "ns": "http://example.com/ns"
  }
}
```

#### Validate XML
```http
POST /api/filesystem/xml/validate?file_path=./data/xml/input/data.xml&schema_path=./schema.xsd
```

### JSON Processing

#### Parse JSON
```http
POST /api/filesystem/json/parse
Content-Type: application/json

{
  "file_path": "./data/json/input/data.json",
  "schema_validate": true,
  "json_schema": {...}
}
```

#### Merge JSON Files
```http
POST /api/filesystem/json/merge
Content-Type: application/json

{
  "file_paths": ["file1.json", "file2.json"],
  "output_path": "./data/merged.json"
}
```

### CSV Processing

#### Parse CSV
```http
POST /api/filesystem/csv/parse
Content-Type: application/json

{
  "file_path": "./data/csv/parts.csv",
  "delimiter": ",",
  "encoding": "utf-8",
  "header_row": 0
}
```

#### Convert CSV to JSON
```http
POST /api/filesystem/csv/to-json
Content-Type: application/json

{
  "csv_path": "./data/csv/parts.csv",
  "json_path": "./data/json/parts.json",
  "delimiter": ",",
  "encoding": "utf-8"
}
```

### Batch Operations

#### Batch File Operation
```http
POST /api/filesystem/batch/operation
Content-Type: application/json

{
  "operation": "copy",
  "source_pattern": "./data/uploads/**/*.xml",
  "destination": "./data/processed/"
}

Operations: copy, move, delete
```

### Folder Monitoring

#### Start Monitoring
```http
POST /api/filesystem/watch/start
Content-Type: application/json

{
  "watch_path": "./data/watch",
  "file_patterns": ["*.xml", "*.json"],
  "action": "process",
  "destination_path": "./data/processed"
}
```

---

## API Gateway Management

### Base URL: `/api/gateway`

### Kong Gateway

#### Create Service
```http
POST /api/gateway/kong/services?name=my-service&url=http://backend:8000
```

#### Create Route
```http
POST /api/gateway/kong/routes
Content-Type: application/json

{
  "name": "workflow-route",
  "path": "/workflows",
  "methods": ["GET", "POST"],
  "upstream_url": "http://backend:8000/api/workflows"
}
```

#### List Services
```http
GET /api/gateway/kong/services
```

#### Add Rate Limiting
```http
POST /api/gateway/kong/plugins/rate-limiting
Content-Type: application/json

{
  "service_name": "my-service",
  "requests_per_minute": 100,
  "requests_per_hour": 1000
}
```

#### Create Consumer
```http
POST /api/gateway/kong/consumers
Content-Type: application/json

{
  "username": "api-user",
  "custom_id": "user-123",
  "tags": ["internal"]
}
```

### Apigee Gateway

#### Create API Proxy
```http
POST /api/gateway/apigee/proxies?name=workflow-api&base_path=/workflows&target_url=http://backend:8000
```

#### List API Proxies
```http
GET /api/gateway/apigee/proxies
```

#### Create API Product
```http
POST /api/gateway/apigee/products
Content-Type: application/json

{
  "name": "workflow-product",
  "display_name": "Workflow API Product",
  "proxies": ["workflow-api"],
  "environments": ["prod", "test"]
}
```

### Generic Gateway

#### Register Endpoint
```http
POST /api/gateway/generic/register
Content-Type: application/json

{
  "name": "workflow-endpoint",
  "path": "/api/workflows",
  "methods": ["GET", "POST", "PUT"],
  "upstream_url": "http://backend:8000/api/workflows",
  "plugins": []
}
```

### Analytics

#### Get Traffic Analytics
```http
GET /api/gateway/analytics/traffic?gateway=kong&timeframe=1h
```

---

## Configuration

### Environment Variables

Create a `.env` file based on `.env.example`:

```bash
cp .env.example .env
```

### Key Configuration Sections

#### 1. Azure Configuration
```env
AZURE_STORAGE_CONNECTION_STRING=...
AZURE_COSMOS_ENDPOINT=...
AZURE_SERVICEBUS_CONNECTION=...
```

#### 2. AWS Configuration
```env
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
AWS_S3_BUCKET=plm-data-bucket
```

#### 3. OData Configuration
```env
ODATA_SERVICE_URL=...
ODATA_AUTH_TYPE=basic
ODATA_USERNAME=...
ODATA_PASSWORD=...
```

#### 4. LLM Configuration
```env
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
OLLAMA_BASE_URL=http://localhost:11434
```

#### 5. PLM Configuration
```env
TEAMCENTER_URL=...
WINDCHILL_URL=...
ENOVIA_URL=...
ARAS_URL=...
```

#### 6. File System Configuration
```env
DATA_ROOT_PATH=./data
UPLOAD_DIR=./data/uploads
MAX_UPLOAD_SIZE_MB=100
```

---

## Dependencies

### Core Dependencies
```txt
fastapi==0.115.0
uvicorn[standard]==0.32.0
sqlalchemy==2.0.35
psycopg2-binary==2.9.9
```

### Cloud Services
```txt
# Azure
azure-storage-blob==12.23.1
azure-cosmos==4.7.0
azure-servicebus==7.12.3

# AWS
boto3==1.35.77
aioboto3==13.2.0
```

### Data Processing
```txt
pandas==2.2.3
openpyxl==3.1.5
xmltodict==0.14.2
lxml==5.3.0
```

### LLM Services
```txt
openai==1.57.0
anthropic==0.39.0
ollama==0.4.4
langchain==0.3.9
```

### PLM & OData
```txt
zeep==4.2.1
pyodata==1.13.0
requests==2.32.3
```

### Installation

```bash
# Install all dependencies
pip install -r requirements_external_integrations.txt

# Or install specific groups
pip install azure-storage-blob azure-cosmos
pip install boto3
pip install openai anthropic ollama
```

---

## Health Checks

All integration routers provide health check endpoints:

```http
GET /api/azure/health
GET /api/aws/health
GET /api/odata/health
GET /api/llm/health
GET /api/plm/systems/health
GET /api/filesystem/health
GET /api/gateway/health
```

---

## Error Handling

All endpoints return standardized error responses:

```json
{
  "status": "error",
  "message": "Error description",
  "detail": "Detailed error information"
}
```

HTTP Status Codes:
- `200` - Success
- `400` - Bad Request
- `404` - Not Found
- `413` - Payload Too Large
- `500` - Internal Server Error

---

## Usage Examples

### Example 1: Upload file to Azure and process with LLM

```python
import requests

# Upload file
files = {'file': open('data.xml', 'rb')}
response = requests.post('http://localhost:8000/api/azure/blob/upload', files=files)
blob_url = response.json()['url']

# Analyze with LLM
llm_request = {
    "messages": [
        {"role": "user", "content": f"Analyze this file: {blob_url}"}
    ],
    "temperature": 0.7
}
analysis = requests.post('http://localhost:8000/api/llm/openai/chat', json=llm_request)
```

### Example 2: Query PLM and store in DynamoDB

```python
# Query Teamcenter
plm_query = {
    "system_type": "teamcenter",
    "object_type": "Item",
    "query_criteria": {"item_id": "P*"},
    "limit": 100
}
parts = requests.post('http://localhost:8000/api/plm/teamcenter/query', json=plm_query)

# Store in DynamoDB
for part in parts.json()['objects']:
    dynamodb_item = {
        "table_name": "plm-parts",
        "item": part
    }
    requests.post('http://localhost:8000/api/aws/dynamodb/put', json=dynamodb_item)
```

### Example 3: Process files from folder and upload to S3

```python
# List files
file_list = requests.post('http://localhost:8000/api/filesystem/list', json={
    "path": "./data/uploads",
    "filter_extension": "xml"
})

# Process and upload each
for file_info in file_list.json()['files']:
    # Parse XML
    parsed = requests.post('http://localhost:8000/api/filesystem/xml/parse', json={
        "file_path": file_info['path']
    })
    
    # Upload to S3
    with open(file_info['path'], 'rb') as f:
        requests.post('http://localhost:8000/api/aws/s3/upload', 
                     files={'file': f},
                     params={'bucket_name': 'processed-data'})
```

---

## Support

For issues or questions:
1. Check logs in `./logs/`
2. Verify environment variables in `.env`
3. Test health endpoints
4. Review FastAPI docs at `http://localhost:8000/docs`
