# MCP Server - Standalone Agent Orchestration Service

**Status**: 🚧 Under Development (Phase 1)

This is the standalone Model Context Protocol (MCP) server extracted from the monolithic GraphTrace application. It provides intelligent agent orchestration, task routing, and workflow coordination as an independently deployable microservice.

## Quick Start

### Local Development

```bash
# 1. Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set environment variables
cp .env.example .env
# Edit .env with your configuration

# 4. Run the server
python -m uvicorn main:app --reload --port 8012
```

Server will be available at: http://localhost:8012

- API Docs: http://localhost:8012/docs
- Health Check: http://localhost:8012/health
- Metrics: http://localhost:8012/metrics

## Architecture

The MCP Server acts as the central orchestrator for all agentic tasks:

```
┌─────────────┐       ┌──────────────┐       ┌─────────────────┐
│   Client    │──────▶│  MCP Server  │──────▶│ Agent Services  │
│  (Backend)  │       │              │       │ (6 types)       │
└─────────────┘       └──────┬───────┘       └─────────────────┘
                             │
                    ┌────────┴──────────┐
                    │                   │
              ┌─────▼──────┐   ┌───────▼──────┐
              │ Redis      │   │ Service Bus  │
              │ (State)    │   │ (Queue)      │
              └────────────┘   └──────────────┘
```

## API Endpoints

### Task Management

#### Submit Task
```http
POST /mcp/v1/tasks
Content-Type: application/json

{
  "task_type": "data_analysis",
  "required_capabilities": ["analyze_data_patterns"],
  "payload": {
    "query": "MATCH (n:Part) RETURN count(n)",
    "options": {}
  },
  "priority": 5,
  "timeout": 30
}
```

#### Get Task Status
```http
GET /mcp/v1/tasks/{task_id}
```

#### Cancel Task
```http
DELETE /mcp/v1/tasks/{task_id}
```

### Agent Management

#### List Agents
```http
GET /mcp/v1/agents
```

#### Get Agent Capabilities
```http
GET /mcp/v1/agents/{agent_id}/capabilities
```

### Chat Coordination

#### Process Chat Message
```http
POST /mcp/v1/chat
Content-Type: application/json

{
  "message": "Analyze data quality for Part objects",
  "context": {},
  "session_id": "session_123"
}
```

### System Status

#### Health Check
```http
GET /health
```

#### Metrics (Prometheus format)
```http
GET /metrics
```

## Configuration

### Environment Variables

```bash
# Server Identity
MCP_SERVER_ID=mcp-server-01
MCP_SERVER_PORT=8012

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/graphtrace
REDIS_URL=redis://localhost:6379/0

# Azure Service Bus (or use local emulator)
AZURE_SERVICE_BUS_CONNECTION_STRING=Endpoint=sb://...
MCP_TASK_QUEUE_NAME=mcp-tasks
MCP_RESULT_QUEUE_NAME=mcp-results

# Agent Discovery
AGENT_REGISTRY_BACKEND=postgres  # or redis
AGENT_HEARTBEAT_INTERVAL_SECONDS=30
AGENT_TIMEOUT_SECONDS=120

# Performance
MAX_CONCURRENT_TASKS=50
TASK_TIMEOUT_DEFAULT_SECONDS=30
QUEUE_POLL_INTERVAL_SECONDS=1

# Observability
LOG_LEVEL=INFO
ENABLE_METRICS=true
ENABLE_TRACING=true
```

## Development

### Project Structure

```
mcp_server/
├── __init__.py
├── main.py                 # FastAPI application
├── orchestrator.py         # AgenticOrchestrator class
├── models.py               # Pydantic models
├── dependencies.py         # FastAPI dependencies
├── config.py               # Configuration management
├── queue_client.py         # Azure Service Bus client
├── state_manager.py        # Redis state management
├── agent_registry.py       # Agent discovery/registration
├── routes/
│   ├── tasks.py           # Task management endpoints
│   ├── agents.py          # Agent management endpoints
│   ├── chat.py            # Chat coordination endpoints
│   └── system.py          # Health, metrics, status
├── tests/
│   ├── test_orchestrator.py
│   ├── test_routes.py
│   └── test_integration.py
├── requirements.txt
└── README.md
```

### Running Tests

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run unit tests
pytest tests/unit

# Run integration tests (requires infrastructure)
pytest tests/integration

# Run with coverage
pytest --cov=. --cov-report=html
```

## Deployment

### Azure App Service

#### ZIP Deployment (Recommended)

```bash
# 1. Create App Service resources
az group create --name rg-graphtrace-dev --location eastus

az appservice plan create \
  --name asp-graphtrace-dev \
  --resource-group rg-graphtrace-dev \
  --sku P1V3 \
  --is-linux

az webapp create \
  --name app-mcp-server-dev \
  --resource-group rg-graphtrace-dev \
  --plan asp-graphtrace-dev \
  --runtime "PYTHON:3.12"

# 2. Configure startup command
az webapp config set \
  --name app-mcp-server-dev \
  --resource-group rg-graphtrace-dev \
  --startup-file "python -m uvicorn main:app --host 0.0.0.0 --port 8000"

# 3. Package and deploy
zip -r mcp-server.zip . -x "*.pyc" "__pycache__/*" ".git/*" "tests/*"

az webapp deploy \
  --resource-group rg-graphtrace-dev \
  --name app-mcp-server-dev \
  --src-path mcp-server.zip \
  --type zip

# 4. Configure environment variables
az webapp config appsettings set \
  --name app-mcp-server-dev \
  --resource-group rg-graphtrace-dev \
  --settings \
    DATABASE_URL="postgresql://..." \
    REDIS_URL="redis://..." \
    MCP_SERVER_PORT=8000 \
    PYTHONUNBUFFERED=1

# 5. Enable Application Insights
az webapp config appsettings set \
  --name app-mcp-server-dev \
  --resource-group rg-graphtrace-dev \
  --settings APPLICATIONINSIGHTS_CONNECTION_STRING="InstrumentationKey=..."

# 6. Test
curl https://app-mcp-server-dev.azurewebsites.net/health
```

### Production Considerations

- **Use deployment slots** for zero-downtime deployments
- **Enable VNet Integration** for secure backend communication
- **Configure auto-scaling** based on CPU/memory metrics
- **Use managed identities** instead of connection strings
- **Enable Application Insights** for comprehensive monitoring

## Agent Types

The MCP Server coordinates the following agent types:

1. **DATA_ANALYST**: Graph analysis, pattern detection, insights
2. **ETL_ORCHESTRATOR**: Pipeline management, data transformations
3. **QUERY_PLANNER**: Query optimization, execution strategies
4. **VISUALIZATION_AGENT**: Graph layouts, chart configurations
5. **QUALITY_MONITOR**: Data quality metrics, monitoring
6. **CHAT_COORDINATOR**: NLP, intent detection, LLM integration

## Monitoring

### Key Metrics

- `mcp_tasks_total{status}` - Total tasks by status
- `mcp_task_duration_seconds` - Task execution time histogram
- `mcp_queue_depth` - Current queue depth by agent type
- `mcp_agent_availability` - Number of available agents by type
- `mcp_errors_total{type}` - Total errors by type

### Logs

Structured JSON logs with correlation IDs for distributed tracing.

### Alerts

- High task failure rate (> 5%)
- Queue depth growing (> 100 tasks)
- No available agents for task type
- High latency (P95 > 2s)

## Troubleshooting

### MCP Server won't start

1. Check DATABASE_URL is correct and accessible
2. Verify Redis connection
3. Ensure no port conflicts (8012)
4. Check application logs via Azure Portal or `az webapp log tail`

### Tasks stuck in queue

1. Verify agent services are running and registered
2. Check Service Bus connection
3. Review agent capacity and scaling rules
4. Check task timeout configuration

### High latency

1. Check database query performance
2. Review Redis hit rate
3. Scale up agent replicas
4. Optimize task payload size

## Contributing

See [../docs/MCP_ARCHITECTURE_ROADMAP.md](../docs/MCP_ARCHITECTURE_ROADMAP.md) for:
- Architecture overview
- Implementation tasks
- Development guidelines

## References

- [MCP Architecture Roadmap](../docs/MCP_ARCHITECTURE_ROADMAP.md)
- [GraphTrace Documentation](../docs/README.md)
- [Model Context Protocol Spec](https://modelcontextprotocol.io/)
