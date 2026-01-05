import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { saveAs } from 'file-saver';
import { useSearchParams } from 'react-router-dom';
import { e2etraceFetchWithRetry } from '../../api/e2etrace-api';
import { API_CONFIG } from '../../config/api-config.js';
import { DataQualityDashboard } from '../quality/DataQualityDashboard.jsx';

import './DataProcessingHubPage.css';

const DataProcessingHubPage = () => {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();

  const plmBaseUrl = useMemo(() => `${API_CONFIG?.API_BASE_URL || ''}/api/plm/etl`, []);

  const [activeTab, setActiveTab] = useState('workflows');
  const [workflows, setWorkflows] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [workflowsUnavailable, setWorkflowsUnavailable] = useState(false);
  const [templatesUnavailable, setTemplatesUnavailable] = useState(false);
  const [totalWorkflowsCount, setTotalWorkflowsCount] = useState(null);

  const [showCreateModal, setShowCreateModal] = useState(false);
  const [selectedTemplateId, setSelectedTemplateId] = useState('');
  const [workflowName, setWorkflowName] = useState('');
  const [sourceId, setSourceId] = useState('');
  const [targetId, setTargetId] = useState('');

  const [plmSourceSystem, setPlmSourceSystem] = useState('plm');
  const [plmTargetSystem, setPlmTargetSystem] = useState('graph');
  const [plmPartsJson, setPlmPartsJson] = useState('[]');
  const [plmBomJson, setPlmBomJson] = useState('[]');
  const [plmTransformJson, setPlmTransformJson] = useState('{}');
  const [plmSodaChecksPartsYaml, setPlmSodaChecksPartsYaml] = useState('');
  const [plmSodaChecksBomYaml, setPlmSodaChecksBomYaml] = useState('');
  const [_plmRunResult, setPlmRunResult] = useState(null);
  const [plmRunError, setPlmRunError] = useState(null);
  const [plmTasks, setPlmTasks] = useState([]);
  const [plmSelectedTaskKey, setPlmSelectedTaskKey] = useState('');
  const [plmRunReport, setPlmRunReport] = useState(null);
  const [plmRunReportId, setPlmRunReportId] = useState(null);
  const [plmRunIdForGates, setPlmRunIdForGates] = useState('');
  const [plmGateHistory, setPlmGateHistory] = useState([]);
  const [plmGatesUnavailable, setPlmGatesUnavailable] = useState(false);

  const fetchJson = useCallback(async (url, options = {}) => {
    const response = await e2etraceFetchWithRetry(url, {
      headers: {
        'Content-Type': 'application/json',
        ...(options.headers || {}),
      },
      ...options,
    });
    const data = await response.json();
    return { data, response };
  }, []);

  const fetchJsonFailClosed = useCallback(async (url, options = {}) => {
    const response = await e2etraceFetchWithRetry(url, {
      headers: {
        'Content-Type': 'application/json',
        ...(options.headers || {}),
      },
      ...options,
    });

    const isJson = (response.headers.get('content-type') || '').includes('application/json');
    const body = isJson ? await response.json().catch(() => null) : await response.text().catch(() => '');

    if (response.status === 503) {
      const detail = (body && typeof body === 'object' ? body.detail : null) || 'Dependency unavailable (503)';
      const err = new Error(detail);
      err.code = 'DEPENDENCY_UNAVAILABLE';
      err.status = 503;
      err.detail = detail;
      throw err;
    }

    if (!response.ok) {
      const detail = (body && typeof body === 'object' ? body.detail : null) || response.statusText || 'Request failed';
      const err = new Error(detail);
      err.status = response.status;
      err.detail = detail;
      throw err;
    }

    return body;
  }, []);

  const safeParseJson = (raw, fallback) => {
    if (raw === null || raw === undefined) return fallback;
    const text = String(raw).trim();
    if (!text) return fallback;
    return JSON.parse(text);
  };

  const initPlmTasks = ({ hasParts, hasBom }) => {
    const tasks = [
      { key: 'create_run', label: 'Create run', status: 'pending' },
      { key: 'stage_parts', label: 'Stage parts', status: hasParts ? 'pending' : 'skipped' },
      { key: 'stage_bom', label: 'Stage BOM', status: hasBom ? 'pending' : 'skipped' },
      { key: 'transform', label: 'Transform', status: 'pending' },
      { key: 'dq_parts', label: 'Soda gate (plm_parts)', status: hasParts ? 'pending' : 'skipped' },
      { key: 'dq_bom', label: 'Soda gate (plm_bom_items)', status: hasBom ? 'pending' : 'skipped' },
      { key: 'validate', label: 'Validate', status: 'pending' },
      { key: 'results', label: 'Results', status: 'pending' },
    ];

    return tasks.map((t) => ({
      ...t,
      startedAt: null,
      endedAt: null,
      durationMs: null,
      output: null,
      error: null,
    }));
  };

  const updatePlmTask = (tasks, key, patch) =>
    tasks.map((t) => (t.key === key ? { ...t, ...patch } : t));

  const computePlmAnalytics = ({ tasks, run_id, partsCount, bomCount, gates }) => {
    const totalMs = tasks
      .filter((t) => typeof t.durationMs === 'number')
      .reduce((sum, t) => sum + t.durationMs, 0);

    const gateSummary = Array.isArray(gates)
      ? gates.map((g) => ({
          table: g?.table_name || g?.tableName || null,
          status: g?.status || null,
          score: g?.overall_score ?? g?.overallScore ?? null,
          issues: g?.issues_count ?? g?.issuesCount ?? null,
        }))
      : [];

    return {
      run_id,
      inputs: { partsCount, bomCount },
      totalDurationMs: totalMs,
      stepStatus: tasks.reduce((acc, t) => {
        acc[t.key] = t.status;
        return acc;
      }, {}),
      gateSummary,
      generatedAt: new Date().toISOString(),
    };
  };

  const downloadJson = (filename, payload) => {
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json;charset=utf-8' });
    saveAs(blob, filename);
  };

  const runBackendPlmEtl = async () => {
    try {
      setPlmRunError(null);
      setPlmRunResult(null);
      setPlmGatesUnavailable(false);
      setPlmGateHistory([]);
      setPlmTasks([]);
      setPlmSelectedTaskKey('');
      setPlmRunReport(null);
        setPlmRunReportId(null);
      setIsLoading(true);

      const parts_records = safeParseJson(plmPartsJson, []);
      const bom_records = safeParseJson(plmBomJson, []);
      const transform = safeParseJson(plmTransformJson, {});

      if (!Array.isArray(parts_records)) {
        throw new Error('Parts JSON must be an array');
      }
      if (!Array.isArray(bom_records)) {
        throw new Error('BOM JSON must be an array');
      }
      if (transform && typeof transform !== 'object') {
        throw new Error('Transform JSON must be an object');
      }

      const hasParts = parts_records.length > 0;
      const hasBom = bom_records.length > 0;
      let tasks = initPlmTasks({ hasParts, hasBom });
      setPlmTasks(tasks);
      setPlmSelectedTaskKey('create_run');

      const runStep = async (key, fn) => {
        const startedAt = new Date().toISOString();
        tasks = updatePlmTask(tasks, key, { status: 'running', startedAt, endedAt: null, durationMs: null, error: null });
        setPlmTasks(tasks);
        setPlmSelectedTaskKey(key);

        const startMs = Date.now();
        try {
          const output = await fn();
          const endedAt = new Date().toISOString();
          tasks = updatePlmTask(tasks, key, {
            status: 'success',
            endedAt,
            durationMs: Date.now() - startMs,
            output,
          });
          setPlmTasks(tasks);
          return output;
        } catch (error) {
          const endedAt = new Date().toISOString();
          tasks = updatePlmTask(tasks, key, {
            status: 'failed',
            endedAt,
            durationMs: Date.now() - startMs,
            error: error?.message || String(error),
          });
          setPlmTasks(tasks);
          throw error;
        }
      };

      const run = await runStep('create_run', async () =>
        fetchJsonFailClosed(`${plmBaseUrl}/runs`, {
          method: 'POST',
          body: JSON.stringify({ source_system: plmSourceSystem, target_system: plmTargetSystem }),
        })
      );

      const run_id = run?.run_id;
      if (!run_id) {
        throw new Error('Backend did not return run_id');
      }

      setPlmRunIdForGates(run_id);

      if (parts_records.length > 0) {
        await runStep('stage_parts', async () =>
          fetchJsonFailClosed(`${plmBaseUrl}/runs/${encodeURIComponent(run_id)}/stage`, {
            method: 'POST',
            body: JSON.stringify({
              object_type: 'part',
              records: parts_records,
              source_object_id_field: null,
            }),
          })
        );
      }

      if (bom_records.length > 0) {
        await runStep('stage_bom', async () =>
          fetchJsonFailClosed(`${plmBaseUrl}/runs/${encodeURIComponent(run_id)}/stage`, {
            method: 'POST',
            body: JSON.stringify({
              object_type: 'bom',
              records: bom_records,
              source_object_id_field: null,
            }),
          })
        );
      }

      await runStep('transform', async () =>
        fetchJsonFailClosed(`${plmBaseUrl}/runs/${encodeURIComponent(run_id)}/transform`, {
          method: 'POST',
          body: JSON.stringify(transform || {}),
        })
      );

      const gates = [];
      const shouldGateParts = parts_records.length > 0;
      const shouldGateBom = bom_records.length > 0;

      if (shouldGateParts) {
        const gate = await runStep('dq_parts', async () =>
          fetchJsonFailClosed(
            `${plmBaseUrl}/runs/${encodeURIComponent(run_id)}/dq/soda/scan/${encodeURIComponent('public.plm_parts')}`,
            {
              method: 'POST',
              body: JSON.stringify({
                stage: 'transformed',
                checks_yaml: plmSodaChecksPartsYaml?.trim() ? plmSodaChecksPartsYaml : null,
                data_source_name: 'postgres',
              }),
            }
          )
        );
        gates.push(gate);
        if (gate?.blocked || gate?.status === 'fail') {
          const err = new Error('Quality gate failed');
          err.code = 'QUALITY_GATE_FAILED';
          err.gate = gate;
          throw err;
        }
      }

      if (shouldGateBom) {
        const gate = await runStep('dq_bom', async () =>
          fetchJsonFailClosed(
            `${plmBaseUrl}/runs/${encodeURIComponent(run_id)}/dq/soda/scan/${encodeURIComponent('public.plm_bom_items')}`,
            {
              method: 'POST',
              body: JSON.stringify({
                stage: 'transformed',
                checks_yaml: plmSodaChecksBomYaml?.trim() ? plmSodaChecksBomYaml : null,
                data_source_name: 'postgres',
              }),
            }
          )
        );
        gates.push(gate);
        if (gate?.blocked || gate?.status === 'fail') {
          const err = new Error('Quality gate failed');
          err.code = 'QUALITY_GATE_FAILED';
          err.gate = gate;
          throw err;
        }
      }

      await runStep('validate', async () =>
        fetchJsonFailClosed(`${plmBaseUrl}/runs/${encodeURIComponent(run_id)}/validate`, {
          method: 'POST',
          body: JSON.stringify({}),
        })
      );

      const results = await runStep('results', async () =>
        fetchJsonFailClosed(`${plmBaseUrl}/runs/${encodeURIComponent(run_id)}/results`, {
          method: 'GET',
        })
      );

      const finalResult = {
        status: 'completed',
        run_id,
        gates,
        results,
      };

      setPlmRunResult(finalResult);

      const analytics = computePlmAnalytics({
        tasks,
        run_id,
        partsCount: parts_records.length,
        bomCount: bom_records.length,
        gates,
      });

      const report = {
        kind: 'plm_etl_run_report',
        run_id,
        source_system: plmSourceSystem,
        target_system: plmTargetSystem,
        analytics,
        tasks,
        gates,
        results,
        generatedAt: new Date().toISOString(),
      };
      setPlmRunReport(report);

      // Persist the report so Reporting/Analytics/Spreadsheet can reuse it.
      try {
        const baseUrl = API_CONFIG?.API_BASE_URL || '';
        const res = await fetch(`${baseUrl}/api/reports`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            report_type: 'plm_etl_run',
            title: `PLM ETL Run ${run_id}`,
            source: 'data_processing_hub',
            schema_version: '1',
            run_id,
            payload: report,
            summary: {
              run_id,
              status: finalResult.status,
              partsCount: parts_records.length,
              bomCount: bom_records.length,
              blocked: gates?.some((g) => g?.blocked || g?.status === 'fail') || false,
            },
          }),
        });
        if (res.ok) {
          const saved = await res.json();
          setPlmRunReportId(saved?.id || null);
        }
      } catch {
        // Non-fatal: report is still available as a downloadable JSON.
      }
    } catch (error) {
      setPlmRunError(error?.message || String(error));
    } finally {
      setIsLoading(false);
    }
  };

  const refreshPlmGateHistory = useCallback(async () => {
    const runId = String(plmRunIdForGates || '').trim();
    if (!runId) return;

    try {
      setPlmGatesUnavailable(false);
      const baseUrl = API_CONFIG?.API_BASE_URL || '';
      const url = `${baseUrl}/api/plm/etl/runs/${encodeURIComponent(runId)}/dq/gates`;
      const { data } = await fetchJson(url, { method: 'GET' });
      setPlmGateHistory(Array.isArray(data) ? data : []);
    } catch {
      setPlmGatesUnavailable(true);
      setPlmGateHistory([]);
    }
  }, [fetchJson, plmRunIdForGates]);

  const refreshWorkflows = useCallback(async () => {
    try {
      setWorkflowsUnavailable(false);
      const response = await e2etraceFetchWithRetry(API_CONFIG.ENDPOINTS.WORKFLOWS, { method: 'GET' });
      const totalHeader = response.headers.get('X-Total-Count');
      setTotalWorkflowsCount(totalHeader ? Number(totalHeader) : null);
      const data = await response.json();
      setWorkflows(Array.isArray(data) ? data : []);
    } catch {
      setWorkflowsUnavailable(true);
      setWorkflows([]);
      setTotalWorkflowsCount(null);
    }
  }, []);

  const refreshTemplates = useCallback(async () => {
    try {
      setTemplatesUnavailable(false);
      const response = await e2etraceFetchWithRetry(API_CONFIG.ENDPOINTS.WORKFLOW_TEMPLATES, { method: 'GET' });
      const data = await response.json();
      setTemplates(Array.isArray(data) ? data : []);
    } catch {
      setTemplatesUnavailable(true);
      setTemplates([]);
    }
  }, []);

  useEffect(() => {
    refreshTemplates();
    refreshWorkflows();
  }, [refreshTemplates, refreshWorkflows]);

  const statusLabel = (status) => {
    if (!status) return t('processingHub.status.unknown');
    return String(status);
  };

  const openCreate = () => {
    if (templatesUnavailable || templates.length === 0) {
      alert(t('processingHub.templates.unavailable'));
      return;
    }
    const firstTemplate = templates?.[0]?.id || '';
    setSelectedTemplateId(firstTemplate);
    setWorkflowName('');
    setSourceId('');
    setTargetId('');
    setShowCreateModal(true);
  };

  const createWorkflow = async () => {
    if (!selectedTemplateId) return;
    if (!sourceId || !targetId) return;

    try {
      setIsLoading(true);

      const url = `${API_CONFIG.ENDPOINTS.WORKFLOW_INSTANTIATE(selectedTemplateId)}?source_id=${encodeURIComponent(
        sourceId
      )}&target_id=${encodeURIComponent(targetId)}${workflowName ? `&name=${encodeURIComponent(workflowName)}` : ''}`;

      const { data: workflow } = await fetchJson(url, { method: 'POST' });

      setShowCreateModal(false);
      await refreshWorkflows();
      if (workflow) {
        setWorkflows((prev) => [workflow, ...prev]);
      }
    } catch (error) {
      alert(error?.message || 'Failed to create workflow');
    } finally {
      setIsLoading(false);
    }
  };

  const executeWorkflow = async (workflowId) => {
    try {
      setIsLoading(true);

      await fetchJson(API_CONFIG.ENDPOINTS.WORKFLOW_EXECUTE(workflowId), {
        method: 'POST',
        body: JSON.stringify({ action: 'start', execution_params: {} }),
      });

      await refreshWorkflows();
    } catch (error) {
      alert(error?.message || 'Workflow execution failed');
    } finally {
      setIsLoading(false);
    }
  };

  const deleteWorkflow = async (workflowId) => {
    if (!confirm(t('processingHub.confirmDelete'))) return;

    try {
      setIsLoading(true);
      await e2etraceFetchWithRetry(API_CONFIG.ENDPOINTS.WORKFLOW_DELETE(workflowId), { method: 'DELETE' });
      setWorkflows((prev) => prev.filter((w) => w.id !== workflowId));
      await refreshWorkflows();
    } catch (error) {
      alert(error?.message || 'Failed to delete workflow');
    } finally {
      setIsLoading(false);
    }
  };

  const activeWorkflowsCount = useMemo(() => {
    if (!Array.isArray(workflows)) return null;
    return workflows.filter((w) => String(w.status).toLowerCase() === 'running').length;
  }, [workflows]);

  const completedWorkflowsCount = useMemo(() => {
    if (!Array.isArray(workflows)) return null;
    return workflows.filter((w) => String(w.status).toLowerCase() === 'completed').length;
  }, [workflows]);

  const metricValue = (value) => (value === null || value === undefined ? 'N/A' : value);

  useEffect(() => {
    const requested = String(searchParams.get('tab') || '').trim();
    if (!requested) return;
    if (!['workflows', 'templates', 'quick', 'quality'].includes(requested)) return;
    if (requested === activeTab) return;
    setActiveTab(requested);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  const selectTab = (nextTab) => {
    setActiveTab(nextTab);
    const next = new URLSearchParams(searchParams);
    next.set('tab', nextTab);
    setSearchParams(next, { replace: true });
  };

  return (
    <div className="data-processing-hub">
      <div className="data-processing-hub__header">
        <h1>{t('nav.dataProcessingHub')}</h1>
        <p>{t('processingHub.subtitle')}</p>
      </div>

      <div className="data-processing-hub__metrics">
        <div className="data-processing-hub__metric">
          <span className="data-processing-hub__metric-value">{metricValue(totalWorkflowsCount ?? workflows.length)}</span>
          <span className="data-processing-hub__metric-label">{t('processingHub.metrics.total')}</span>
        </div>
        <div className="data-processing-hub__metric">
          <span className="data-processing-hub__metric-value">{metricValue(completedWorkflowsCount)}</span>
          <span className="data-processing-hub__metric-label">{t('processingHub.metrics.success')}</span>
        </div>
        <div className="data-processing-hub__metric">
          <span className="data-processing-hub__metric-value">{metricValue(activeWorkflowsCount)}</span>
          <span className="data-processing-hub__metric-label">{t('processingHub.metrics.active')}</span>
        </div>
      </div>

      <div className="data-processing-hub__tabs" role="tablist" aria-label={t('processingHub.tabs.label')}>
        <button
          type="button"
          className={`data-processing-hub__tab ${activeTab === 'workflows' ? 'data-processing-hub__tab--active' : ''}`}
          onClick={() => selectTab('workflows')}
        >
          {t('processingHub.tabs.workflows')}
        </button>
        <button
          type="button"
          className={`data-processing-hub__tab ${activeTab === 'templates' ? 'data-processing-hub__tab--active' : ''}`}
          onClick={() => selectTab('templates')}
        >
          {t('processingHub.tabs.templates')}
        </button>
        <button
          type="button"
          className={`data-processing-hub__tab ${activeTab === 'quick' ? 'data-processing-hub__tab--active' : ''}`}
          onClick={() => selectTab('quick')}
        >
          {t('processingHub.tabs.quick')}
        </button>
        <button
          type="button"
          className={`data-processing-hub__tab ${activeTab === 'quality' ? 'data-processing-hub__tab--active' : ''}`}
          onClick={() => selectTab('quality')}
        >
          {t('processingHub.tabs.quality')}
        </button>
      </div>

      {activeTab === 'workflows' ? (
        <section className="data-processing-hub__panel">
          <div className="data-processing-hub__panel-header">
            <h2>{t('processingHub.workflows.title')}</h2>
            <button
              type="button"
              className="data-processing-hub__btn data-processing-hub__btn--primary"
              onClick={openCreate}
              disabled={isLoading || templatesUnavailable || templates.length === 0}
            >
              {t('processingHub.workflows.create')}
            </button>
          </div>
          <div className="data-processing-hub__content">
            <div className="data-processing-hub__list">
              {workflowsUnavailable ? (
                <div className="data-processing-hub__item">{t('processingHub.workflows.unavailable')}</div>
              ) : null}
              {workflows.length === 0 ? (
                <div className="data-processing-hub__item">{t('processingHub.workflows.empty')}</div>
              ) : null}
              {workflows.map((workflow) => (
                <div className="data-processing-hub__item" key={workflow.id}>
                  <div className="data-processing-hub__item-title">
                    <h3>{workflow.name}</h3>
                    <span className="data-processing-hub__badge">{statusLabel(workflow.status)}</span>
                  </div>
                  <div style={{ marginTop: 'var(--space-2)', color: 'var(--text-muted-color)' }}>
                    {workflow.description}
                  </div>
                  <div className="data-processing-hub__actions">
                    <button type="button" className="data-processing-hub__btn data-processing-hub__btn--primary" onClick={() => executeWorkflow(workflow.id)} disabled={isLoading}>
                      {t('processingHub.actions.run')}
                    </button>
                    <button type="button" className="data-processing-hub__btn" onClick={() => deleteWorkflow(workflow.id)} disabled={isLoading}>
                      {t('processingHub.actions.delete')}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>
      ) : null}

      {activeTab === 'templates' ? (
        <section className="data-processing-hub__panel">
          <div className="data-processing-hub__panel-header">
            <h2>{t('processingHub.templates.title')}</h2>
          </div>
          <div className="data-processing-hub__content">
            <div className="data-processing-hub__list">
              {templatesUnavailable ? (
                <div className="data-processing-hub__item">{t('processingHub.templates.unavailable')}</div>
              ) : null}
              {!templatesUnavailable && templates.length === 0 ? (
                <div className="data-processing-hub__item">{t('processingHub.templates.unavailable')}</div>
              ) : null}
              {templates.map((tpl) => (
                <div className="data-processing-hub__item" key={tpl.id}>
                  <div className="data-processing-hub__item-title">
                    <h3>{tpl.name}</h3>
                    {tpl.complexity ? <span className="data-processing-hub__badge">{tpl.complexity}</span> : null}
                  </div>
                  <div style={{ marginTop: 'var(--space-2)', color: 'var(--text-muted-color)' }}>{tpl.description}</div>
                </div>
              ))}
            </div>
          </div>
        </section>
      ) : null}

      {activeTab === 'quick' ? (
        <section className="data-processing-hub__panel">
          <div className="data-processing-hub__panel-header">
            <h2>{t('processingHub.quick.title')}</h2>
          </div>
          <div className="data-processing-hub__content">
            <div className="data-processing-hub__item">
              <div className="data-processing-hub__item-title">
                <h3>PLM ETL (Backend)</h3>
                <span className="data-processing-hub__badge">run-scoped Soda gates</span>
              </div>
              <div style={{ marginTop: 'var(--space-2)', color: 'var(--text-muted-color)' }}>
                Artery view: each step runs as a task with a status, output, analytics, and a report.
              </div>

              <div className="data-processing-hub__field" style={{ marginTop: 'var(--space-3)' }}>
                <label htmlFor="plmSourceSystem">source_system</label>
                <input id="plmSourceSystem" value={plmSourceSystem} onChange={(e) => setPlmSourceSystem(e.target.value)} disabled={isLoading} />
              </div>
              <div className="data-processing-hub__field">
                <label htmlFor="plmTargetSystem">target_system</label>
                <input id="plmTargetSystem" value={plmTargetSystem} onChange={(e) => setPlmTargetSystem(e.target.value)} disabled={isLoading} />
              </div>
              <div className="data-processing-hub__field">
                <label htmlFor="plmPartsRecords">parts_records (JSON array)</label>
                <textarea
                  id="plmPartsRecords"
                  value={plmPartsJson}
                  onChange={(e) => setPlmPartsJson(e.target.value)}
                  disabled={isLoading}
                  rows="4"
                />
              </div>
              <div className="data-processing-hub__field">
                <label htmlFor="plmBomRecords">bom_records (JSON array)</label>
                <textarea
                  id="plmBomRecords"
                  value={plmBomJson}
                  onChange={(e) => setPlmBomJson(e.target.value)}
                  disabled={isLoading}
                  rows="4"
                />
              </div>
              <div className="data-processing-hub__field">
                <label htmlFor="plmTransform">transform (JSON object)</label>
                <textarea
                  id="plmTransform"
                  value={plmTransformJson}
                  onChange={(e) => setPlmTransformJson(e.target.value)}
                  disabled={isLoading}
                  rows="4"
                />
              </div>
              <div className="data-processing-hub__field">
                <label htmlFor="plmSodaChecksParts">Soda checks (YAML) for public.plm_parts</label>
                <textarea
                  id="plmSodaChecksParts"
                  value={plmSodaChecksPartsYaml}
                  onChange={(e) => setPlmSodaChecksPartsYaml(e.target.value)}
                  disabled={isLoading}
                  rows="6"
                />
              </div>
              <div className="data-processing-hub__field">
                <label htmlFor="plmSodaChecksBom">Soda checks (YAML) for public.plm_bom_items</label>
                <textarea
                  id="plmSodaChecksBom"
                  value={plmSodaChecksBomYaml}
                  onChange={(e) => setPlmSodaChecksBomYaml(e.target.value)}
                  disabled={isLoading}
                  rows="6"
                />
              </div>

              <div className="data-processing-hub__actions">
                <button
                  type="button"
                  className="data-processing-hub__btn data-processing-hub__btn--primary"
                  onClick={runBackendPlmEtl}
                  disabled={isLoading || !String(plmSourceSystem || '').trim() || !String(plmTargetSystem || '').trim()}
                >
                  Run PLM ETL
                </button>
                {plmRunReport ? (
                  <button
                    type="button"
                    className="data-processing-hub__btn"
                    onClick={() => downloadJson(`plm_etl_run_${plmRunReport.run_id || 'report'}.json`, plmRunReport)}
                    disabled={isLoading}
                  >
                    Download report (JSON)
                  </button>
                ) : null}
                {plmRunReportId ? (
                  <>
                    <button
                      type="button"
                      className="data-processing-hub__btn"
                      onClick={() => {
                        window.location.hash = `#/reporting?reportId=${encodeURIComponent(plmRunReportId)}`;
                      }}
                      disabled={isLoading}
                    >
                      Open in Reporting
                    </button>
                    <button
                      type="button"
                      className="data-processing-hub__btn"
                      onClick={() => {
                        window.location.hash = `#/spreadsheet?reportId=${encodeURIComponent(plmRunReportId)}`;
                      }}
                      disabled={isLoading}
                    >
                      Open in Spreadsheet
                    </button>
                  </>
                ) : null}
              </div>

              {plmRunError ? (
                <div className="data-processing-hub__item" style={{ marginTop: 'var(--space-3)' }}>
                  <strong style={{ color: 'var(--error-color)' }}>Error:</strong> {plmRunError}
                </div>
              ) : null}

              {plmTasks.length > 0 ? (
                <div style={{ marginTop: 'var(--space-3)' }}>
                  <div className="data-processing-hub__task-list" role="list">
                    {plmTasks.map((task) => (
                      <button
                        key={task.key}
                        type="button"
                        className={`data-processing-hub__task ${plmSelectedTaskKey === task.key ? 'data-processing-hub__task--selected' : ''}`}
                        onClick={() => setPlmSelectedTaskKey(task.key)}
                        disabled={isLoading && task.status === 'pending'}
                      >
                        <div className="data-processing-hub__task-row">
                          <span className="data-processing-hub__task-label">{task.label}</span>
                          <span className={`data-processing-hub__status data-processing-hub__status--${task.status}`}>{task.status}</span>
                        </div>
                        <div className="data-processing-hub__task-meta">
                          {typeof task.durationMs === 'number' ? `${task.durationMs}ms` : task.status === 'running' ? 'running…' : ''}
                        </div>
                      </button>
                    ))}
                  </div>

                  {(() => {
                    const selected = plmTasks.find((t) => t.key === plmSelectedTaskKey) || null;
                    if (!selected) return null;
                    return (
                      <details style={{ marginTop: 'var(--space-3)' }} open>
                        <summary>Selected step output: {selected.label}</summary>
                        {selected.error ? (
                          <div style={{ marginTop: 'var(--space-2)', color: 'var(--error-color)' }}>{selected.error}</div>
                        ) : null}
                        {selected.output ? (
                          <pre style={{ marginTop: 'var(--space-2)' }}>{JSON.stringify(selected.output, null, 2)}</pre>
                        ) : (
                          <div style={{ marginTop: 'var(--space-2)', color: 'var(--text-muted-color)' }}>No output.</div>
                        )}
                      </details>
                    );
                  })()}

                  {plmRunReport ? (
                    <details style={{ marginTop: 'var(--space-3)' }}>
                      <summary>Run analytics + report</summary>
                      <pre style={{ marginTop: 'var(--space-2)' }}>{JSON.stringify(plmRunReport.analytics, null, 2)}</pre>
                      <pre style={{ marginTop: 'var(--space-2)' }}>{JSON.stringify(plmRunReport, null, 2)}</pre>
                    </details>
                  ) : null}
                </div>
              ) : null}
            </div>

            <div className="data-processing-hub__item">
              <div className="data-processing-hub__item-title">
                <h3>Quality gate history</h3>
              </div>
              <div className="data-processing-hub__field" style={{ marginTop: 'var(--space-3)' }}>
                <label htmlFor="plmRunIdForGates">run_id</label>
                <input
                  id="plmRunIdForGates"
                  value={plmRunIdForGates}
                  onChange={(e) => setPlmRunIdForGates(e.target.value)}
                  disabled={isLoading}
                />
              </div>
              <div className="data-processing-hub__actions">
                <button type="button" className="data-processing-hub__btn data-processing-hub__btn--primary" onClick={refreshPlmGateHistory} disabled={isLoading || !String(plmRunIdForGates || '').trim()}>
                  Refresh gates
                </button>
              </div>

              {plmGatesUnavailable ? (
                <div style={{ marginTop: 'var(--space-2)', color: 'var(--text-muted-color)' }}>Gates unavailable.</div>
              ) : null}

              {plmGateHistory.length > 0 ? (
                <details style={{ marginTop: 'var(--space-2)' }}>
                  <summary>View persisted gates ({plmGateHistory.length})</summary>
                  <pre style={{ marginTop: 'var(--space-2)' }}>{JSON.stringify(plmGateHistory, null, 2)}</pre>
                </details>
              ) : null}
            </div>
          </div>
        </section>
      ) : null}

      {activeTab === 'quality' ? (
        <section className="data-processing-hub__panel">
          <div className="data-processing-hub__content">
            <DataQualityDashboard />
          </div>
        </section>
      ) : null}

      {showCreateModal ? (
        <div className="data-processing-hub__modal-overlay" role="dialog" aria-modal="true" aria-label={t('processingHub.createModal.title')}>
          <div className="data-processing-hub__modal">
            <div className="data-processing-hub__panel-header">
              <h2>{t('processingHub.createModal.title')}</h2>
              <button type="button" className="data-processing-hub__btn" onClick={() => setShowCreateModal(false)}>
                {t('processingHub.actions.close')}
              </button>
            </div>
            <div className="data-processing-hub__modal-body">
              <div className="data-processing-hub__field">
                <label htmlFor="processingHubTemplate">{t('processingHub.createModal.template')}</label>
                <select id="processingHubTemplate" value={selectedTemplateId} onChange={(e) => setSelectedTemplateId(e.target.value)} disabled={isLoading}>
                  {templates.map((tpl) => (
                    <option key={tpl.id} value={tpl.id}>
                      {tpl.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="data-processing-hub__field">
                <label htmlFor="processingHubSourceId">{t('processingHub.createModal.sourceId')}</label>
                <input id="processingHubSourceId" value={sourceId} onChange={(e) => setSourceId(e.target.value)} disabled={isLoading} />
              </div>
              <div className="data-processing-hub__field">
                <label htmlFor="processingHubTargetId">{t('processingHub.createModal.targetId')}</label>
                <input id="processingHubTargetId" value={targetId} onChange={(e) => setTargetId(e.target.value)} disabled={isLoading} />
              </div>
              <div className="data-processing-hub__field">
                <label htmlFor="processingHubName">{t('processingHub.createModal.name')}</label>
                <input id="processingHubName" value={workflowName} onChange={(e) => setWorkflowName(e.target.value)} disabled={isLoading} />
              </div>
            </div>
            <div className="data-processing-hub__modal-footer">
              <button type="button" className="data-processing-hub__btn" onClick={() => setShowCreateModal(false)} disabled={isLoading}>
                {t('processingHub.actions.cancel')}
              </button>
              <button type="button" className="data-processing-hub__btn data-processing-hub__btn--primary" onClick={createWorkflow} disabled={isLoading || !selectedTemplateId || !sourceId || !targetId}>
                {t('processingHub.actions.create')}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
};

export default DataProcessingHubPage;
