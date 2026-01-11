/**
 * ETL Workflow Service
 * Thin wrapper around the backend Workflow Instance Manager APIs.
 * No local demo templates, no fabricated metrics.
 */

import { e2etraceFetchWithRetry } from '../api/e2etrace-api';
import { API_CONFIG } from '../config/api-config.js';

class ETLWorkflowService {
  async listWorkflows() {
    const response = await e2etraceFetchWithRetry(API_CONFIG.ENDPOINTS.WORKFLOWS, { method: 'GET' });
    const data = await response.json();
    return Array.isArray(data) ? data : [];
  }

  async listWorkflowTemplates() {
    const response = await e2etraceFetchWithRetry(API_CONFIG.ENDPOINTS.WORKFLOW_TEMPLATES, { method: 'GET' });
    const data = await response.json();
    return Array.isArray(data) ? data : [];
  }

  async instantiateWorkflowFromTemplate(templateId, { sourceId, targetId, name } = {}) {
    if (!templateId) throw new Error('templateId is required');
    if (!sourceId) throw new Error('sourceId is required');
    if (!targetId) throw new Error('targetId is required');

    const url = `${API_CONFIG.ENDPOINTS.WORKFLOW_INSTANTIATE(templateId)}?source_id=${encodeURIComponent(
      sourceId
    )}&target_id=${encodeURIComponent(targetId)}${name ? `&name=${encodeURIComponent(name)}` : ''}`;

    const response = await e2etraceFetchWithRetry(url, { method: 'POST' });
    return await response.json();
  }

  async executeWorkflow(workflowId, { action = 'start', executionParams = {} } = {}) {
    if (!workflowId) throw new Error('workflowId is required');

    const response = await e2etraceFetchWithRetry(API_CONFIG.ENDPOINTS.WORKFLOW_EXECUTE(workflowId), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action, execution_params: executionParams }),
    });

    return await response.json();
  }

  async deleteWorkflow(workflowId) {
    if (!workflowId) throw new Error('workflowId is required');
    await e2etraceFetchWithRetry(API_CONFIG.ENDPOINTS.WORKFLOW_DELETE(workflowId), { method: 'DELETE' });
  }
}

export const etlWorkflowService = new ETLWorkflowService();
export default etlWorkflowService;
