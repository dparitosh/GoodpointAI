# 🧬 Data Lineage Quick Start Guide

## Overview
The Data Lineage Visualizer tracks data flow from source systems through transformations to target systems, providing impact analysis and compliance-ready audit trails.

## Accessing the Feature

1. **Navigate to Data Lineage:**
   - Open the application at `http://localhost:5173`
   - Click **"🧬 Data Lineage"** in the left sidebar under "Data Operations"

## Key Features

### 1. Load Workflow Lineage Graph
**Use Case:** View complete data lineage for a workflow

**Steps:**
1. Enter a `Workflow ID` in the first input field
2. Click **"Load Graph"** button
3. The graph will display all nodes and relationships for that workflow
4. Use pan/zoom to explore the graph

**Example:**
```
Workflow ID: wf_1736886000_abc12345
```

### 2. Trace Record Lineage
**Use Case:** Find upstream sources and downstream targets for a specific data record

**Steps:**
1. Enter a `Record ID` in the second input field
2. Select direction:
   - **Both**: Show upstream + downstream
   - **Upstream**: Show only sources
   - **Downstream**: Show only targets
3. Adjust max depth (1-10 levels)
4. Click **"Trace"** button

**Example:**
```
Record ID: rec_12345
Direction: Both
Max Depth: 5
```

### 3. Filter by Node Type
**Use Case:** Focus on specific types of nodes in the lineage graph

**Available Filters:**
- 🗄️ **Source System** - External data sources
- 🎯 **Target System** - Destination systems
- ⚙️ **Transformation** - Data transformation steps
- ✓ **Validation** - Data quality checks
- 🤖 **Agent** - AI agents processing data
- 📄 **Data Record** - Individual data records

**Steps:**
1. Click any filter button to show only that type
2. Click **"All"** to reset filters

### 4. Impact Analysis
**Use Case:** Predict the impact of changes on downstream systems

**Steps:**
1. Click on any node in the graph
2. The **Node Details Panel** appears on the right
3. Click one of the impact analysis buttons:
   - **Schema Change**: Database schema modifications
   - **Data Quality**: Data quality issues
   - **System Failure**: System outage scenarios
4. View the **Impact Analysis Results**:
   - Affected systems count
   - Risk level (Critical/High/Medium/Low)
   - Recommendations
   - List of affected nodes with impact levels

**Example Scenario:**
```
Node: "PLM Source Database"
Change Type: "Schema Change"
Result: 12 affected systems, HIGH risk
Recommendation: "Run data validation tests before deployment"
```

### 5. Audit Trail
**Use Case:** Generate compliance reports for regulatory requirements

**Steps:**
1. Enter a `Workflow ID`
2. Click **"Audit Trail"** button
3. View the audit report:
   - Total records processed
   - Compliance status
   - Generation timestamp
   - Detailed audit records
4. Click **"Export to PDF"** to save the report

**Compliance Standards Supported:**
- FDA 21 CFR Part 11 (Electronic Records)
- CMMC (Cybersecurity Maturity Model)
- ITAR (Export Control)
- GDPR (Data Privacy) - Ready
- CCPA (California Privacy) - Ready

## Graph Navigation

### Controls
- **Pan**: Click and drag the background
- **Zoom**: Scroll mouse wheel or use zoom controls
- **Minimap**: Use the overview map in bottom-right corner
- **Background**: Dotted grid for reference

### Node Information
- **Color**: Indicates node type (see legend)
- **Icon**: Visual identifier (🗄️, 🎯, ⚙️, etc.)
- **Label**: Node name and type
- **Border**: Yellow border = current record (in trace mode)

### Edge Information
- **Label**: Relationship type (e.g., TRANSFORMED_BY)
- **Animation**: Indicates data flow direction
- **Color**: Gray edges connect related nodes

## API Endpoints

For programmatic access:

### Create Lineage Node
```bash
POST http://localhost:8000/api/lineage/nodes
Content-Type: application/json

{
  "id": "node_123",
  "type": "SOURCE_SYSTEM",
  "name": "PLM Database",
  "properties": {"location": "us-east-1"},
  "workflow_id": "wf_12345"
}
```

### Create Lineage Relationship
```bash
POST http://localhost:8000/api/lineage/relationships
Content-Type: application/json

{
  "source_id": "node_123",
  "target_id": "node_456",
  "type": "EXTRACTED_FROM",
  "properties": {"batch_size": 1000},
  "workflow_id": "wf_12345"
}
```

### Trace Lineage
```bash
POST http://localhost:8000/api/lineage/trace
Content-Type: application/json

{
  "record_id": "rec_123",
  "direction": "both",
  "max_depth": 5
}
```

### Impact Analysis
```bash
POST http://localhost:8000/api/lineage/impact-analysis
Content-Type: application/json

{
  "source_node_id": "node_123",
  "change_type": "schema_change",
  "simulation_mode": true
}
```

### Audit Trail
```bash
POST http://localhost:8000/api/lineage/audit-trail
Content-Type: application/json

{
  "workflow_id": "wf_12345",
  "start_date": "2025-01-01T00:00:00Z",
  "end_date": "2025-12-31T23:59:59Z"
}
```

### Get Workflow Lineage Graph
```bash
GET http://localhost:8000/api/lineage/workflows/wf_12345/lineage-graph
```

## Node Types Reference

| Type | Icon | Color | Purpose |
|------|------|-------|---------|
| SOURCE_SYSTEM | 🗄️ | Blue | External data sources (databases, APIs) |
| TARGET_SYSTEM | 🎯 | Green | Destination systems (warehouses, apps) |
| TRANSFORMATION | ⚙️ | Orange | Data transformation logic |
| VALIDATION | ✓ | Purple | Quality checks and validations |
| AGENT | 🤖 | Red | AI agents processing data |
| DATA_RECORD | 📄 | Indigo | Individual data records |

## Relationship Types Reference

| Type | Description | Example |
|------|-------------|---------|
| EXTRACTED_FROM | Data pulled from source | Record ← PLM Database |
| TRANSFORMED_BY | Data modified by process | Record → Transformation Agent |
| VALIDATED_BY | Quality check performed | Record → Validation Rule |
| LOADED_TO | Data written to target | Record → Target Database |
| DEPENDS_ON | Dependency relationship | Transformation → Source Schema |
| PROCESSED_BY | Agent processing | Record → AI Agent |

## Best Practices

### 1. Naming Conventions
- **Nodes**: Use descriptive names (e.g., "PLM_BOM_Extraction")
- **Workflow IDs**: Include timestamp and purpose (e.g., "wf_20250114_bom_migration")
- **Properties**: Add metadata (location, version, owner)

### 2. Lineage Tracking
- Create nodes before relationships
- Use consistent workflow_id across related nodes
- Add timestamps for temporal analysis
- Include source/target system details

### 3. Impact Analysis
- Run simulation mode before actual changes
- Review recommendations carefully
- Consider critical systems first
- Document mitigation strategies

### 4. Audit Trail
- Generate reports before major changes
- Archive reports for compliance
- Review periodically for anomalies
- Use date ranges for specific periods

### 5. Performance
- Limit max depth to 5 for interactive use
- Use specific record IDs instead of loading entire workflow
- Filter by type to reduce visual complexity
- Export large graphs instead of rendering in browser

## Troubleshooting

### Graph Not Loading
**Issue:** Empty graph after clicking "Load Graph"

**Solutions:**
1. Verify workflow ID exists in database
2. Check Neo4j connection in backend logs
3. Confirm nodes have `workflow_id` property set
4. Check browser console for errors

### Trace Returns No Results
**Issue:** "No lineage found for this record"

**Solutions:**
1. Verify record ID is correct
2. Increase max depth (try 7 or 10)
3. Check if relationships exist in Neo4j
4. Try "Both" direction instead of upstream/downstream

### Impact Analysis Shows No Affected Nodes
**Issue:** Zero affected systems in impact analysis

**Solutions:**
1. Ensure downstream relationships exist
2. Check if node is a leaf node (no children)
3. Verify relationship types are correct
4. Increase max depth in Neo4j query

### Performance Issues
**Issue:** Graph rendering is slow

**Solutions:**
1. Reduce max depth to 3-5
2. Filter by specific node type
3. Use smaller workflow scope
4. Consider pagination for large graphs

## Example Workflows

### Scenario 1: BOM Migration
```
1. Load Workflow: "wf_20250114_bom_migration"
2. Identify Source: PLM_BOM_Database (blue node)
3. Trace Transformations: Follow orange nodes
4. Verify Target: ERP_BOM_Table (green node)
5. Run Impact Analysis on PLM_BOM_Database
6. Generate Audit Trail for compliance
```

### Scenario 2: Schema Change Impact
```
1. Click on "PLM_Parts_Table" node
2. Select "Schema Change" impact analysis
3. Review 15 affected systems (8 high risk)
4. Follow recommendations:
   - Update transformation mappings
   - Schedule maintenance window
   - Notify stakeholders
5. Export audit trail for review
```

### Scenario 3: Compliance Audit
```
1. Enter workflow ID: "wf_2024Q4_migrations"
2. Click "Audit Trail"
3. Set date range: 2024-10-01 to 2024-12-31
4. Review 2,345 processed records
5. Verify "COMPLIANT" status
6. Export to PDF for auditor
```

## Integration with Other Features

### XState Workflow
- Lineage nodes created automatically during workflow execution
- State transitions logged as transformation nodes
- Agent actions recorded as relationship properties

### Data Quality Dashboard
- Validation nodes linked to SODA checks
- Quality issues trigger impact analysis
- Audit trails include quality metrics

### Observability
- Lineage integrated with monitoring metrics
- Performance data added to node properties
- Anomaly detection alerts reference lineage

## GraphQL (Future)

### Subscription Example
```graphql
subscription {
  lineageUpdated(workflowId: "wf_12345") {
    id
    type
    name
    createdAt
  }
}
```

### Query Example
```graphql
query {
  traceLineage(recordId: "rec_123", direction: "both", maxDepth: 5) {
    recordId
    nodes {
      id
      name
      type
    }
    relationships {
      type
      sourceId
      targetId
    }
  }
}
```

## Support & Resources

- **API Docs**: http://localhost:8000/docs
- **Implementation Report**: See `TASK_1_DATA_LINEAGE_IMPLEMENTATION_REPORT.md`
- **Neo4j Browser**: http://localhost:7474 (if local)
- **ReactFlow Docs**: https://reactflow.dev

## Next Steps

1. ✅ **Completed**: Data Lineage Tracking (Task 1)
2. ⏭️ **Next**: Semantic Schema Mapping (Task 4)
3. ⏭️ **Future**: Real-Time Collaboration with GraphQL Subscriptions (Task 7)

---

**Quick Reference Card**

| Action | Where | What |
|--------|-------|------|
| View Graph | Enter Workflow ID → Load Graph | Full lineage visualization |
| Trace Record | Enter Record ID → Trace | Upstream/downstream paths |
| Check Impact | Click Node → Impact Analysis | Change risk assessment |
| Get Audit | Enter Workflow ID → Audit Trail | Compliance report |
| Filter Nodes | Click Filter Button | Focus on node type |
| Inspect Node | Click on Graph Node | View details & actions |

---

*Last Updated: 2025-01-14*  
*Version: 1.0.0*
