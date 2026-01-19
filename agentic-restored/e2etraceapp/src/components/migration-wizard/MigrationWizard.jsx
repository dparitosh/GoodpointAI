import React, { useState, useCallback, useEffect, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { e2etraceFetchWithRetry } from '../../api/e2etrace-api';
import { API_CONFIG } from '../../config/api-config.js';
import { useGraphQLTransform } from '../../hooks/useGraphQL.js';
import { useAISuggestions, useGraphRAGHealth } from '../../hooks/useGraphRAG.js';
import { useAgenticSystemStatus } from '../../hooks/useAgenticAI.js';
import { XStateVisualizer } from '../xstate-visualizer/XStateVisualizer';
import ApprovalsPanel from './ApprovalsPanel.jsx';
import './MigrationWizard.css';

/**
 * MigrationWizard - Unified PLM Data Migration Workflow
 * 
 * A streamlined 5-step wizard for end-to-end data migration:
 * 1. Connect - Configure source and target data sources
 * 2. Discovery - Run discovery agent insights (SODA-driven when available)
 * 3. Map - Define field mappings with AI assistance
 * 4. Validate - Run data quality checks and transformations
 * 5. Execute - Run migration and monitor progress
 */
const MigrationWizard = ({ embedded = false, initialStep = 1, onComplete }) => {
  const [searchParams] = useSearchParams();
  
  // Wizard state
  const [currentStep, setCurrentStep] = useState(initialStep);
  const [isLoading, setIsLoading] = useState(false);
  const [wizardData, setWizardData] = useState({
    // Step 0: Run identity
    workflowName: '',
    // MCP migration run (state machine / audit trail)
    mcpRunId: null,
    mcpApprovalToken: '',
    mcpApprovalTokenAction: '',
    mcpApprovalRequired: false,
    mcpApprovalRequiredAction: '',
    mcpMaterializeSummary: null,
    mcpPublishSummary: null,
    mcpLastStagedSample: null,
    // Step 1: Sources
    sourceSystem: null,
    targetSystem: null,
    // Step 2: Discovery Agent
    discoveryStatus: 'idle', // idle | running | completed | failed
    discoveryAccepted: false,
    discoveryRunId: null,
    discoverySodaResult: null,
    discoveryInsights: [],
    discoverySample: null,
    discoveryIntrospect: null,
    discoveryError: null,
    // Optional schema data (used by mapping/validation if available)
    sourceSchema: null,
    targetSchema: null,
    schemaMapping: [],
    // Step 3: Mapping
    fieldMappings: [],
    aiSuggestedMappings: [],
    selectedTemplate: null,
    // Step 4: Validation
    validationResults: [],
    transformationRules: [],
    qualityChecks: { passed: 0, failed: 0, warnings: 0 },
    // Step 5: Execution
    migrationStatus: 'pending',
    processedRecords: 0,
    totalRecords: 0,
    errors: [],
    runId: null
  });
  
  // Available data sources
  const [availableSources, setAvailableSources] = useState([]);
  const [showAllSources, setShowAllSources] = useState(false);
  const [mappingTemplates, setMappingTemplates] = useState([]);

  const visibleSources = useMemo(() => {
    const sources = Array.isArray(availableSources) ? availableSources : [];
    if (showAllSources) return sources;

    // Default behavior: treat Admin-configured “connection settings” as the canonical catalog.
    // Those entries are surfaced as Data Sources with ids like `conn_<id>`.
    // Also include explicitly active sources.
    return sources.filter((s) => {
      const id = String(s?.id || '');
      const status = String(s?.status || '').toLowerCase();
      return id.startsWith('conn_') || status === 'active' || status === 'connected';
    });
  }, [availableSources, showAllSources]);
  
  // AI Hooks
  const graphqlTransform = useGraphQLTransform();
  const aiSuggestions = useAISuggestions();
  const graphRAGHealth = useGraphRAGHealth();
  const agenticSystem = useAgenticSystemStatus();
  
  // Step completion status
  const [stepStatus, setStepStatus] = useState({
    1: { complete: false, valid: false },
    2: { complete: false, valid: false },
    3: { complete: false, valid: false },
    4: { complete: false, valid: false },
    5: { complete: false, valid: false }
  });

  // Define steps as a memoized constant to avoid dependency array issues
  const steps = useMemo(() => [
    { id: 1, name: 'Connect', icon: 'fa-plug', description: 'Configure data sources' },
    { id: 2, name: 'Discovery', icon: 'fa-search', description: 'Agentic discovery insights' },
    { id: 3, name: 'Map', icon: 'fa-arrows-alt-h', description: 'Define field mappings' },
    { id: 4, name: 'Validate', icon: 'fa-check-double', description: 'Quality & transform' },
    { id: 5, name: 'Execute', icon: 'fa-play-circle', description: 'Run migration' }
  ], []);

  // Toggle state for showing/hiding the state flow diagram
  const [showStateFlow, setShowStateFlow] = useState(true);

  const [showApprovals, setShowApprovals] = useState(false);

  // Generate XState graph data based on current wizard state
  const stateFlowGraphData = useMemo(() => {
    const stepColors = {
      completed: '#22c55e',
      active: '#3b82f6',
      pending: '#6b7280'
    };

    const getStepStatus = (stepId) => {
      if (stepStatus[stepId]?.complete) return 'completed';
      if (stepId === currentStep) return 'active';
      return 'pending';
    };

    const nodes = steps.map((step) => ({
      id: `step-${step.id}`,
      label: step.name,
      type: 'state',
      status: getStepStatus(step.id),
      color: stepColors[getStepStatus(step.id)],
      metadata: {
        description: step.description,
        icon: step.icon,
        stepNumber: step.id,
        isActive: step.id === currentStep,
        isComplete: stepStatus[step.id]?.complete
      }
    }));

    const edges = steps.slice(0, -1).map((step, idx) => ({
      id: `edge-${step.id}`,
      source: `step-${step.id}`,
      target: `step-${steps[idx + 1].id}`,
      label: stepStatus[step.id]?.complete ? 'NEXT' : '',
      type: 'transition',
      animated: step.id === currentStep
    }));

    return { nodes, edges };
  }, [currentStep, stepStatus, steps]);

  // Load initial data
  useEffect(() => {
    loadDataSources();
    loadMappingTemplates();
    graphRAGHealth.checkHealth().catch(() => {});
    agenticSystem.checkStatus().catch(() => {});
    
    // Check for pre-loaded data from Data Workbench
    const source = searchParams.get('source');
    if (source === 'workbench') {
      loadWorkbenchData();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Load data from Data Workbench (via localStorage)
  const loadWorkbenchData = () => {
    try {
      const stored = localStorage.getItem('workbench_migration_data');
      if (!stored) return;
      
      const workbenchData = JSON.parse(stored);
      const { schema, timestamp } = workbenchData;
      
      // Check if data is not too old (1 hour max)
      const age = Date.now() - new Date(timestamp).getTime();
      if (age > 60 * 60 * 1000) {
        localStorage.removeItem('workbench_migration_data');
        return;
      }
      
      // Pre-populate wizard with workbench data
      setWizardData(prev => ({
        ...prev,
        sourceSystem: {
          id: 'workbench',
          name: 'Data Workbench Import',
          type: 'file',
          status: 'connected'
        },
        sourceSchema: schema
      }));
      
      // Mark step 1 as complete and move to step 2
      setStepStatus(prev => ({
        ...prev,
        1: { complete: true, valid: true }
      }));
      setCurrentStep(2);
      
      // Clean up localStorage
      localStorage.removeItem('workbench_migration_data');
      
      console.log('Loaded workbench data:', schema);
    } catch (error) {
      console.error('Error loading workbench data:', error);
    }
  };

  const loadDataSources = async () => {
    try {
      const response = await e2etraceFetchWithRetry(API_CONFIG.ENDPOINTS.DATA_SOURCES);
      const sources = await response.json();
      // Show all sources that are configured in Admin Settings (even if not currently connected).
      // This keeps the wizard usable for end-users who must select from the configured catalog.
      setAvailableSources(Array.isArray(sources) ? sources : []);
    } catch (error) {
      console.error('Error loading data sources:', error);
    }
  };

  const loadMappingTemplates = async () => {
    try {
      const response = await e2etraceFetchWithRetry(API_CONFIG.ENDPOINTS.DATA_MAPPING_TEMPLATES);
      const templates = await response.json();
      const fetchedTemplates = Array.isArray(templates) ? templates : [];
      
      // Add default PLM mapping templates if none exist
      const defaultTemplates = [
        {
          id: 'plm-part-standard',
          name: 'PLM Part → Neo4j (Standard)',
          description: 'Standard PLM part data to Neo4j Part node mapping',
          field_mappings: [
            { source_field: 'part_number', target_field: 'part_number', transformation: null },
            { source_field: 'name', target_field: 'name', transformation: null },
            { source_field: 'description', target_field: 'description', transformation: null },
            { source_field: 'category', target_field: 'classification', transformation: null },
            { source_field: 'revision', target_field: 'revision', transformation: null }
          ]
        },
        {
          id: 'plm-bom-standard',
          name: 'PLM BOM → Neo4j Relationship',
          description: 'Bill of Materials parent-child relationship mapping',
          field_mappings: [
            { source_field: 'parent_part_number', target_field: 'parent_part_number', transformation: null },
            { source_field: 'child_part_number', target_field: 'child_part_number', transformation: null },
            { source_field: 'quantity', target_field: 'quantity', transformation: 'NUMBER' }
          ]
        },
        {
          id: 'generic-entity',
          name: 'Generic Entity Mapping',
          description: 'Basic entity to node mapping with common fields',
          field_mappings: [
            { source_field: 'id', target_field: 'id', transformation: null },
            { source_field: 'name', target_field: 'name', transformation: null },
            { source_field: 'type', target_field: 'type', transformation: 'UPPER' },
            { source_field: 'created_at', target_field: 'created_at', transformation: 'TIMESTAMP' }
          ]
        }
      ];
      
      // Merge fetched templates with defaults, avoiding duplicates
      const existingIds = new Set(fetchedTemplates.map(t => t.id));
      const mergedTemplates = [
        ...fetchedTemplates,
        ...defaultTemplates.filter(t => !existingIds.has(t.id))
      ];
      
      setMappingTemplates(mergedTemplates);
    } catch (error) {
      console.error('Error loading templates:', error);
      // Use default templates on error
      setMappingTemplates([
        {
          id: 'plm-part-standard',
          name: 'PLM Part → Neo4j (Standard)',
          description: 'Standard PLM part data mapping',
          field_mappings: [
            { source_field: 'part_number', target_field: 'part_number', transformation: null },
            { source_field: 'name', target_field: 'name', transformation: null },
            { source_field: 'category', target_field: 'classification', transformation: null }
          ]
        }
      ]);
    }
  };

  // Step navigation
  const canProceed = useCallback((step) => {
    switch (step) {
      case 1: return wizardData.workflowName.trim().length > 0 && wizardData.sourceSystem && wizardData.targetSystem;
      case 2: return wizardData.discoveryAccepted;
      case 3: return wizardData.fieldMappings.length > 0;
      case 4: return wizardData.validationResults.length > 0 || wizardData.qualityChecks.passed > 0;
      case 5: return true;
      default: return false;
    }
  }, [wizardData]);

  const nextStep = useCallback(() => {
    if (currentStep < 5 && canProceed(currentStep)) {
      setStepStatus(prev => ({
        ...prev,
        [currentStep]: { complete: true, valid: true }
      }));
      setCurrentStep(prev => prev + 1);
    }
  }, [currentStep, canProceed]);

  const prevStep = useCallback(() => {
    if (currentStep > 1) {
      setCurrentStep(prev => prev - 1);
    }
  }, [currentStep]);

  const setWorkflowName = useCallback((name) => {
    setWizardData(prev => ({
      ...prev,
      workflowName: String(name ?? '')
    }));
  }, []);

  // Step 1: Source selection
  const selectSource = useCallback((type, source) => {
    setWizardData(prev => ({
      ...prev,
      [type === 'source' ? 'sourceSystem' : 'targetSystem']: source,
      mcpRunId: null,
      mcpApprovalToken: '',
      mcpApprovalRequired: false,
      mcpMaterializeSummary: null,
      mcpLastStagedSample: null,
      discoveryStatus: 'idle',
      discoveryAccepted: false,
      discoveryRunId: null,
      discoverySodaResult: null,
      discoveryInsights: [],
      discoveryError: null,
      discoveryIntrospect: null,
      sourceSchema: null,
      targetSchema: null
    }));

    // Reset completion for downstream steps when changing sources
    setStepStatus(prev => ({
      ...prev,
      2: { complete: false, valid: false },
      3: { complete: false, valid: false },
      4: { complete: false, valid: false },
      5: { complete: false, valid: false }
    }));
  }, []);

  // Step 2: Discovery Agent
  const runDiscovery = useCallback(async () => {
    if (!wizardData.sourceSystem || !wizardData.targetSystem) return;

    setIsLoading(true);
    setWizardData(prev => ({
      ...prev,
      discoveryStatus: 'running',
      discoveryAccepted: false,
      discoveryRunId: null,
      discoverySodaResult: null,
      discoveryInsights: [],
      discoverySample: null,
      discoveryIntrospect: null,
      discoveryError: null
    }));

    try {
      const plmBaseUrl = `${API_CONFIG?.API_BASE_URL || ''}/api/plm/etl`;

      // Best-effort: create an MCP migration run for audit/state tracking.
      // This is separate from the PLM ETL run id.
      try {
        if (!wizardData.mcpRunId) {
          const mcpBaseUrl = `${API_CONFIG?.API_BASE_URL || ''}/api/migrations`;
          const mcpRunResp = await e2etraceFetchWithRetry(`${mcpBaseUrl}/runs`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              workflow_name: wizardData.workflowName || '',
              source_id: wizardData.sourceSystem?.id || wizardData.sourceSystem?.name || null,
              target_id: wizardData.targetSystem?.id || wizardData.targetSystem?.name || null,
              initial_status: 'discovery',
              options: {
                ui: 'MigrationWizard',
                phase: 'discovery'
              }
            })
          });

          const mcpRunData = await mcpRunResp.json();
          const mcpRunId = mcpRunData?.run_id;
          if (mcpRunId) {
            setWizardData(prev => ({ ...prev, mcpRunId }));
          }
        }
      } catch (mcpError) {
        // Non-fatal: wizard still works without MCP vertical slice enabled.
        console.warn('MCP run tracking unavailable:', mcpError?.message || mcpError);
      }

      // Create a lightweight discovery run
      const runResponse = await e2etraceFetchWithRetry(`${plmBaseUrl}/runs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source_system: wizardData.sourceSystem?.name || 'source',
          target_system: wizardData.targetSystem?.name || 'target'
        })
      });

      const runData = await runResponse.json();
      const discoveryRunId = runData?.run_id;
      if (!discoveryRunId) throw new Error('Failed to create discovery run');

      // Stage a sample for discovery.
      // Prefer real sampling from the configured source (S3/Blob/local file) when supported.
      let stagedRecords = null;
      let stagedFrom = 'synthetic';
      let samplePayload = null;

      const findKey = (keys, candidates) => {
        const lowerKeys = keys.map(k => String(k));
        for (const c of candidates) {
          const match = lowerKeys.find(k => k.toLowerCase().includes(c));
          if (match) return match;
        }
        return null;
      };

      try {
        const sourceId = wizardData.sourceSystem?.id;
        if (sourceId) {
          const sampleUrl = `${API_CONFIG?.API_BASE_URL || ''}/api/data-sources/${encodeURIComponent(sourceId)}/sample?limit=200`;
          const sampleResponse = await e2etraceFetchWithRetry(sampleUrl, { method: 'GET' });
          if (sampleResponse.ok) {
            samplePayload = await sampleResponse.json();
            const sampleRecords = Array.isArray(samplePayload?.records) ? samplePayload.records : [];
            if (sampleRecords.length > 0) {
              stagedRecords = sampleRecords;
              stagedFrom = 'source';
            }
          }
        }
      } catch (e) {
        // Non-fatal: fall back to synthetic sample
        console.warn('Data source sampling unavailable, falling back to synthetic sample:', e?.message || e);
      }

      if (!stagedRecords) {
        const now = Date.now();
        stagedRecords = [
          { part_number: `PART-${now}-A`, name: 'Sample Part A', category: 'General', revision: 'A' },
          { part_number: `PART-${now}-B`, name: 'Sample Part B', category: 'General', revision: 'B' },
          { part_number: `PART-${now}-C`, name: 'Sample Part C', category: 'General', revision: 'A' }
        ];
      }

      await e2etraceFetchWithRetry(`${plmBaseUrl}/runs/${discoveryRunId}/stage`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          object_type: 'part',
          records: stagedRecords
        })
      });

      // Transform with deterministic defaults so SODA can evaluate canonical tables
      // If we sampled arbitrary keys, attempt a best-effort mapping guess from the first record.
      const first = Array.isArray(stagedRecords) && stagedRecords.length > 0 ? stagedRecords[0] : null;
      const keys = first && typeof first === 'object' && !Array.isArray(first) ? Object.keys(first) : [];
      const guessedPart = findKey(keys, ['part_number', 'partnumber', 'part', 'id', 'key']) || 'part_number';
      const guessedName = findKey(keys, ['name', 'title', 'label']) || 'name';
      const guessedCategory = findKey(keys, ['category', 'class', 'classification', 'type']) || 'category';
      const guessedRevision = findKey(keys, ['revision', 'rev', 'version']) || 'revision';

      await e2etraceFetchWithRetry(`${plmBaseUrl}/runs/${discoveryRunId}/transform`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          part_mapping: {
            [guessedPart]: 'part_number',
            [guessedName]: 'name',
            [guessedCategory]: 'classification',
            [guessedRevision]: 'description'
          }
        })
      });

      // Attempt SODA gate scan + detailed gate fetch (fail-soft)
      let sodaResult = null;
      let issues = [];
      let recommendations = [];

      try {
        const sodaResponse = await e2etraceFetchWithRetry(
          `${plmBaseUrl}/runs/${discoveryRunId}/dq/soda/scan/public.plm_parts`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ stage: 'transformed' })
          }
        );
        sodaResult = await sodaResponse.json();

        const gatesResponse = await e2etraceFetchWithRetry(`${plmBaseUrl}/runs/${discoveryRunId}/dq/gates`, {
          method: 'GET'
        });
        const gatesData = await gatesResponse.json();
        const gates = Array.isArray(gatesData?.gates) ? gatesData.gates : [];
        const latestGate = gates.find(g => String(g?.tool || '').toLowerCase() === 'soda') || gates[0];
        const report = latestGate?.details?.report;
        issues = Array.isArray(report?.issues) ? report.issues : [];
        recommendations = Array.isArray(report?.recommendations) ? report.recommendations : [];
      } catch (sodaError) {
        // SODA or Postgres may not be configured; discovery still continues.
        console.warn('Discovery SODA scan unavailable:', sodaError?.message || sodaError);
      }

      const insights = [];
      if (sodaResult) {
        const scorePct = Number.isFinite(sodaResult?.overall_score)
          ? Math.round(Number(sodaResult.overall_score) * 100)
          : null;

        insights.push({
          id: `dq-${Date.now()}`,
          title: 'Data quality gate (SODA)',
          severity: sodaResult?.status === 'pass' ? 'success' : 'warning',
          detail: scorePct === null
            ? `Status: ${String(sodaResult?.status || 'unknown').toUpperCase()}`
            : `Score: ${scorePct}% • Status: ${String(sodaResult?.status || 'unknown').toUpperCase()} • Issues: ${sodaResult?.issues_count ?? 0}`
        });
      } else {
        insights.push({
          id: `dq-${Date.now()}`,
          title: 'Data quality gate (SODA)',
          severity: 'info',
          detail: 'SODA scan not available in this environment.'
        });
      }

      if (issues.length > 0) {
        const preview = issues.slice(0, 5).map(i => i?.message || i?.name || JSON.stringify(i)).filter(Boolean);
        insights.push({
          id: `issues-${Date.now()}`,
          title: 'Detected issues',
          severity: 'warning',
          detail: preview.length > 0 ? preview.join(' • ') : `${issues.length} issue(s) detected`
        });
      }

      if (recommendations.length > 0) {
        insights.push({
          id: `recs-${Date.now()}`,
          title: 'Recommendations',
          severity: 'info',
          detail: recommendations.slice(0, 3).join(' • ')
        });
      }

      // Seed mapping suggestions based on canonical defaults
      const defaultMappingSuggestions = [
        { sourceField: 'part_number', targetField: 'part_number', transformation: null, confidence: '90%' },
        { sourceField: 'name', targetField: 'name', transformation: 'TRIM', confidence: '90%' },
        { sourceField: 'category', targetField: 'classification', transformation: null, confidence: '85%' },
        { sourceField: 'revision', targetField: 'description', transformation: null, confidence: '70%' }
      ];

      const inferredSourceFields = Array.isArray(keys) && keys.length > 0
        ? keys
        : (Array.isArray(stagedRecords) && stagedRecords.length > 0 && stagedRecords[0] && typeof stagedRecords[0] === 'object')
          ? Object.keys(stagedRecords[0])
          : [];
      const canonicalTargetFields = ['part_number', 'name', 'classification', 'description'];
      const inferredSourceSchema = inferredSourceFields.length > 0
        ? { fields: inferredSourceFields.map((name) => ({ name })) }
        : null;
      const inferredTargetSchema = { fields: canonicalTargetFields.map((name) => ({ name })) };

      const introspectPayload = {
        run_id: discoveryRunId,
        staged_from: stagedFrom,
        inferred_source_fields: inferredSourceFields,
        inferred_target_fields: canonicalTargetFields,
        soda: sodaResult || null,
        issues_count: issues.length,
        issues_preview: issues.slice(0, 5),
        recommendations: recommendations.slice(0, 10)
      };

      setWizardData(prev => ({
        ...prev,
        discoveryStatus: 'completed',
        discoveryRunId,
        discoverySodaResult: sodaResult,
        discoveryInsights: insights,
        discoverySample: samplePayload ? { ...samplePayload, stagedFrom } : { stagedFrom },
        discoveryIntrospect: introspectPayload,
        sourceSchema: inferredSourceSchema,
        targetSchema: inferredTargetSchema,
        aiSuggestedMappings: defaultMappingSuggestions
      }));
    } catch (error) {
      console.error('Discovery failed:', error);
      setWizardData(prev => ({
        ...prev,
        discoveryStatus: 'failed',
        discoveryError: error?.message || 'Discovery failed',
        discoveryIntrospect: null,
        discoveryInsights: [{
          id: `err-${Date.now()}`,
          title: 'Discovery failed',
          severity: 'warning',
          detail: error?.message || 'Unknown error'
        }]
      }));
    } finally {
      setIsLoading(false);
    }
  }, [wizardData.sourceSystem, wizardData.targetSystem, wizardData.mcpRunId, wizardData.workflowName]);

  const stageMcpSampleBestEffort = useCallback(
    async ({ mcpRunId, entity, records }) => {
      const rid = String(mcpRunId || '').trim();
      if (!rid) return null;
      const recs = Array.isArray(records) ? records.filter((r) => r && typeof r === 'object').slice(0, 25) : [];
      if (recs.length === 0) return null;

      const mcpBaseUrl = `${API_CONFIG?.API_BASE_URL || ''}/api/migrations`;
      const resp = await e2etraceFetchWithRetry(`${mcpBaseUrl}/runs/${encodeURIComponent(rid)}/stage`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          entity: String(entity || 'part'),
          records: recs,
        }),
      });
      const data = await resp.json().catch(() => null);
      setWizardData((prev) => ({
        ...prev,
        mcpLastStagedSample: recs.slice(0, 10),
      }));
      return data;
    },
    []
  );

  const transitionMcpRunBestEffort = useCallback(async ({ mcpRunId, toStatus, event, note }) => {
    const rid = String(mcpRunId || '').trim();
    if (!rid) return null;
    const mcpBaseUrl = `${API_CONFIG?.API_BASE_URL || ''}/api/migrations`;
    const resp = await e2etraceFetchWithRetry(`${mcpBaseUrl}/runs/${encodeURIComponent(rid)}/transition`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        to_status: String(toStatus || '').trim(),
        event: event || null,
        note: note || null,
      }),
    });
    return await resp.json().catch(() => null);
  }, []);

  const materializeMcpRunBestEffort = useCallback(
    async ({ mcpRunId, approvalToken }) => {
      const rid = String(mcpRunId || '').trim();
      if (!rid) return null;
      const tok = String(approvalToken || '').trim();

      const mcpBaseUrl = `${API_CONFIG?.API_BASE_URL || ''}/api/migrations`;
      const headers = {
        'Content-Type': 'application/json',
        ...(tok ? { 'X-MCP-Approval-Token': tok } : {}),
      };

      const resp = await e2etraceFetchWithRetry(`${mcpBaseUrl}/runs/${encodeURIComponent(rid)}/materialize`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          entities: null,
          batch_id: null,
        }),
      });
      return await resp.json().catch(() => null);
    },
    []
  );

  const publishMcpRunBestEffort = useCallback(
    async ({ mcpRunId, approvalToken }) => {
      const rid = String(mcpRunId || '').trim();
      if (!rid) return null;
      const tok = String(approvalToken || '').trim();

      const mcpBaseUrl = `${API_CONFIG?.API_BASE_URL || ''}/api/migrations`;
      const headers = {
        'Content-Type': 'application/json',
        ...(tok ? { 'X-MCP-Approval-Token': tok } : {}),
      };

      const resp = await e2etraceFetchWithRetry(`${mcpBaseUrl}/runs/${encodeURIComponent(rid)}/publish`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          entities: null,
          batch_id: null,
          opensearch_index: null,
        }),
      });
      return await resp.json().catch(() => null);
    },
    []
  );

  const acceptDiscovery = useCallback(() => {
    setWizardData(prev => ({
      ...prev,
      discoveryAccepted: true
    }));
  }, []);

  // Step 3: AI-powered mapping suggestions with fallback
  const getAIMappingSuggestions = useCallback(async () => {
    setIsLoading(true);
    try {
      // Try AI suggestions first
      if (wizardData.sourceSchema && wizardData.targetSchema) {
        const suggestions = await aiSuggestions.getMappingSuggestions(
          wizardData.sourceSchema,
          wizardData.targetSchema
        );
        if (suggestions && suggestions.length > 0) {
          setWizardData(prev => ({
            ...prev,
            aiSuggestedMappings: suggestions
          }));
          return;
        }
      }
      
      // Fallback: Generate suggestions from schema fields
      const sourceFields = extractSchemaFields(wizardData.sourceSchema);
      const targetFields = extractSchemaFields(wizardData.targetSchema);
      
      // Smart matching based on field names
      const suggestions = sourceFields.map(sourceField => {
        // Find best matching target field
        const exactMatch = targetFields.find(t => t.toLowerCase() === sourceField.toLowerCase());
        const partialMatch = targetFields.find(t => 
          t.toLowerCase().includes(sourceField.toLowerCase()) || 
          sourceField.toLowerCase().includes(t.toLowerCase())
        );
        const targetField = exactMatch || partialMatch || sourceField;
        
        // Suggest transformation based on field type
        let transformation = null;
        if (sourceField.toLowerCase().includes('date') || sourceField.toLowerCase().includes('time')) {
          transformation = 'TIMESTAMP';
        } else if (sourceField.toLowerCase().includes('amount') || sourceField.toLowerCase().includes('price') || sourceField.toLowerCase().includes('quantity')) {
          transformation = 'NUMBER';
        } else if (sourceField.toLowerCase().includes('name') || sourceField.toLowerCase().includes('type')) {
          transformation = 'TRIM';
        }
        
        return {
          sourceField,
          targetField,
          transformation,
          confidence: exactMatch ? '95%' : partialMatch ? '75%' : '50%'
        };
      });
      
      setWizardData(prev => ({
        ...prev,
        aiSuggestedMappings: suggestions
      }));
    } catch (error) {
      console.error('AI suggestions failed:', error);
      // Provide basic fallback suggestions
      const fallbackSuggestions = [
        { sourceField: 'part_number', targetField: 'part_number', transformation: null, confidence: '90%' },
        { sourceField: 'name', targetField: 'name', transformation: 'TRIM', confidence: '90%' },
        { sourceField: 'description', targetField: 'description', transformation: null, confidence: '85%' },
        { sourceField: 'category', targetField: 'classification', transformation: null, confidence: '80%' }
      ];
      setWizardData(prev => ({
        ...prev,
        aiSuggestedMappings: fallbackSuggestions
      }));
    } finally {
      setIsLoading(false);
    }
  }, [wizardData.sourceSchema, wizardData.targetSchema, aiSuggestions]);
  
  // Helper function to extract field names from schema
  const extractSchemaFields = (schema) => {
    if (!schema) return [];
    
    // Handle different schema formats
    if (Array.isArray(schema.entities)) {
      return schema.entities.flatMap(e => e.properties?.map(p => p.name) || [e.name]);
    }
    if (Array.isArray(schema.fields)) {
      return schema.fields.map(f => f.name || f);
    }
    if (schema.properties) {
      return Object.keys(schema.properties);
    }
    if (Array.isArray(schema)) {
      return schema.map(f => typeof f === 'string' ? f : f.name);
    }
    
    // Try to extract keys from the schema object
    return Object.keys(schema).filter(k => !['__typename', 'kind', 'name'].includes(k));
  };

  const addFieldMapping = useCallback((mapping) => {
    setWizardData(prev => ({
      ...prev,
      fieldMappings: [...prev.fieldMappings, mapping]
    }));
  }, []);

  const removeFieldMapping = useCallback((index) => {
    setWizardData(prev => ({
      ...prev,
      fieldMappings: prev.fieldMappings.filter((_, i) => i !== index)
    }));
  }, []);

  const applyTemplate = useCallback((template) => {
    if (!template?.field_mappings) return;
    setWizardData(prev => ({
      ...prev,
      selectedTemplate: template,
      fieldMappings: template.field_mappings.map(fm => ({
        source_field: fm.source_field || '',
        target_field: fm.target_field || '',
        transformation: fm.transformation || null
      }))
    }));
  }, []);

  // Step 4: Validation & transformation
  const runValidation = useCallback(async () => {
    setIsLoading(true);
    try {
      const validationInsights = await aiSuggestions.getValidationInsights(
        { schema: wizardData.sourceSchema, mappings: wizardData.fieldMappings },
        { nodeCompleteness: true, relationshipIntegrity: true, dataTypeConsistency: true }
      );
      
      const passed = validationInsights.filter(v => v.severity === 'success' || v.severity === 'info').length;
      const failed = validationInsights.filter(v => v.severity === 'error').length;
      const warnings = validationInsights.filter(v => v.severity === 'warning').length;
      
      setWizardData(prev => ({
        ...prev,
        validationResults: validationInsights,
        qualityChecks: { passed, failed, warnings }
      }));
    } catch (error) {
      console.error('Validation failed:', error);
      setWizardData(prev => ({
        ...prev,
        validationResults: [{ id: 0, insight: 'Validation service unavailable', severity: 'warning' }],
        qualityChecks: { passed: 0, failed: 0, warnings: 1 }
      }));
    } finally {
      setIsLoading(false);
    }
  }, [wizardData.sourceSchema, wizardData.fieldMappings, aiSuggestions]);

  // SODA Data Quality Scan
  const runSodaScan = useCallback(async () => {
    if (!wizardData.runId) {
      setWizardData(prev => ({
        ...prev,
        validationResults: [...prev.validationResults, { id: Date.now(), insight: 'No active run - create a run first in Execute step', severity: 'warning' }]
      }));
      return;
    }
    
    setIsLoading(true);
    try {
      const plmBaseUrl = `${API_CONFIG?.API_BASE_URL || ''}/api/plm/etl`;
      const response = await e2etraceFetchWithRetry(
        `${plmBaseUrl}/runs/${wizardData.runId}/dq/soda/scan/public.plm_parts`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ stage: 'transformed' })
        }
      );
      
      const sodaResult = await response.json();
      
      const sodaInsight = {
        id: Date.now(),
        insight: `SODA Quality Score: ${(sodaResult.overall_score * 100).toFixed(0)}% - ${sodaResult.status?.toUpperCase()}`,
        severity: sodaResult.status === 'pass' ? 'success' : sodaResult.status === 'warn' ? 'warning' : 'error',
        recommendation: sodaResult.issues_count > 0 ? `${sodaResult.issues_count} issue(s) detected` : 'All quality checks passed'
      };
      
      const passed = sodaResult.status === 'pass' ? 1 : 0;
      const failed = sodaResult.status === 'fail' ? 1 : 0;
      const warnings = sodaResult.status === 'warn' ? 1 : 0;
      
      setWizardData(prev => ({
        ...prev,
        validationResults: [...prev.validationResults.filter(v => !v.insight?.includes('SODA')), sodaInsight],
        qualityChecks: { 
          passed: prev.qualityChecks.passed + passed,
          failed: prev.qualityChecks.failed + failed,
          warnings: prev.qualityChecks.warnings + warnings
        },
        sodaScanResult: sodaResult
      }));
    } catch (error) {
      console.error('SODA scan failed:', error);
      setWizardData(prev => ({
        ...prev,
        validationResults: [...prev.validationResults, { id: Date.now(), insight: 'SODA scan unavailable - Soda Core may not be installed', severity: 'warning' }]
      }));
    } finally {
      setIsLoading(false);
    }
  }, [wizardData.runId]);

  const testTransformation = useCallback(async () => {
    if (!wizardData.fieldMappings.length) return;
    
    setIsLoading(true);
    try {
      const result = await graphqlTransform.transform(
        { sample: true, source: wizardData.sourceSchema },
        { target: wizardData.targetSchema },
        wizardData.fieldMappings
      );
      console.log('Transformation test result:', result);
    } catch (error) {
      console.error('Transformation test failed:', error);
    } finally {
      setIsLoading(false);
    }
  }, [wizardData, graphqlTransform]);

  // Step 5: Execute migration - Complete 5-step workflow
  const executeMigration = useCallback(async () => {
    setIsLoading(true);
    setWizardData(prev => ({ ...prev, migrationStatus: 'running', migrationStep: 'creating' }));
    
    try {
      const plmBaseUrl = `${API_CONFIG?.API_BASE_URL || ''}/api/plm/etl`;

      // Best-effort: mark MCP run as executing (audit/state tracking)
      try {
        if (wizardData.mcpRunId) {
          await transitionMcpRunBestEffort({
            mcpRunId: wizardData.mcpRunId,
            toStatus: 'executing',
            event: 'execute',
            note: 'Execute step started from Migration Wizard',
          });
        }
      } catch (e) {
        console.warn('MCP run transition unavailable:', e?.message || e);
      }
      
      const willPublishToOpenSearch = String(wizardData.targetSystem?.id || '')
        .toLowerCase()
        .includes('opensearch');

      // STEP 1: Create migration run
      setWizardData(prev => ({ ...prev, migrationStep: 'Step 1: Creating run...', processedRecords: 0 }));
      const runResponse = await e2etraceFetchWithRetry(`${plmBaseUrl}/runs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source_system: wizardData.sourceSystem?.name || 'source',
          target_system: wizardData.targetSystem?.name || 'target'
        })
      });
      
      const runData = await runResponse.json();
      const runId = runData?.run_id;
      
      if (!runId) throw new Error('Failed to create migration run');
      
      setWizardData(prev => ({
        ...prev,
        runId,
        processedRecords: 1,
        totalRecords: willPublishToOpenSearch ? 6 : 5,
      }));
      
      // STEP 2: Stage records (extract from source)
      setWizardData(prev => ({ ...prev, migrationStep: 'Step 2: Staging records...', processedRecords: 2 }));
      
      // Prepare records from schema or use sample data
      const records = wizardData.sourceSchema?.entities?.slice(0, 5).map(entity => ({
        part_number: `PART-${Date.now()}-${Math.random().toString(36).substring(7)}`,
        name: entity.name || 'Unnamed Part',
        category: entity.type || 'General',
        revision: 'A'
      })) || [
        { part_number: `PART-${Date.now()}-A`, name: 'Sample Part A', category: 'General', revision: 'A' },
        { part_number: `PART-${Date.now()}-B`, name: 'Sample Part B', category: 'General', revision: 'B' }
      ];
      
      await e2etraceFetchWithRetry(`${plmBaseUrl}/runs/${runId}/stage`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          object_type: 'part',
          records: records
        })
      });
      
      // STEP 3: Transform using field mappings
      setWizardData(prev => ({ ...prev, migrationStep: 'Step 3: Transforming data...', processedRecords: 3 }));
      
      // Build part_mapping from fieldMappings or use defaults
      const partMapping = wizardData.fieldMappings.reduce((acc, m) => {
        const src = (m?.source_field || '').trim();
        const dest = (m?.target_field || '').trim();
        if (src && dest) acc[src] = dest;
        return acc;
      }, {}) || {
        part_number: 'part_number',
        name: 'name',
        category: 'classification',
        revision: 'description'
      };
      
      // Ensure required mappings exist
      if (!partMapping.part_number) partMapping.part_number = 'part_number';
      if (!partMapping.name) partMapping.name = 'name';
      
      await e2etraceFetchWithRetry(`${plmBaseUrl}/runs/${runId}/transform`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ part_mapping: partMapping })
      });
      
      // STEP 4: Data Quality Scan + Validate
      setWizardData(prev => ({ ...prev, migrationStep: 'Step 4: Running quality scan & validate...', processedRecords: 4 }));
      try {
        const sodaResponse = await e2etraceFetchWithRetry(`${plmBaseUrl}/runs/${runId}/dq/soda/scan/public.plm_parts`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ stage: 'transformed' })
        });
        const sodaResult = await sodaResponse.json();
        setWizardData(prev => ({ ...prev, sodaScanResult: sodaResult }));
        
        if (sodaResult.blocked) {
          throw new Error(`SODA quality gate blocked: ${sodaResult.issues_count} issues detected`);
        }
      } catch (sodaError) {
        console.warn('SODA scan skipped:', sodaError.message);
        // Continue even if SODA is not available
      }
      
      // Validate
      setWizardData(prev => ({ ...prev, migrationStep: 'Step 4: Validating data...', processedRecords: 4 }));
      await e2etraceFetchWithRetry(`${plmBaseUrl}/runs/${runId}/validate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      });
      
      // STEP 5: Materialize lineage to Neo4j
      setWizardData(prev => ({ ...prev, migrationStep: 'Step 5: Materializing lineage to Neo4j...', processedRecords: 5 }));

      // Prefer MCP-governed sample materialization (enables approvals + audit trail).
      // Fall back to direct PLM sync when MCP slice isn't enabled.
      let syncResult = null;
      let mcpMaterialize = null;

      if (wizardData.mcpRunId) {
        try {
          setWizardData((prev) => ({
            ...prev,
            mcpApprovalRequired: false,
            mcpApprovalRequiredAction: '',
            mcpMaterializeSummary: null,
            mcpPublishSummary: null,
          }));

          // Stage a bounded sample to the MCP run so it can be materialized.
          await stageMcpSampleBestEffort({ mcpRunId: wizardData.mcpRunId, entity: 'part', records });

          mcpMaterialize = await materializeMcpRunBestEffort({
            mcpRunId: wizardData.mcpRunId,
            approvalToken:
              String(wizardData.mcpApprovalTokenAction || '').toLowerCase() === 'materialize'
                ? wizardData.mcpApprovalToken
                : '',
          });

          setWizardData((prev) => ({
            ...prev,
            mcpMaterializeSummary: mcpMaterialize,
          }));
        } catch (e) {
          // Approval required: pause execution and let the operator request/approve, then retry.
          if (e?.status === 403) {
            setWizardData((prev) => ({
              ...prev,
              migrationStatus: 'awaiting_approval',
              migrationStep: 'Waiting for approval to materialize to Neo4j',
              mcpApprovalRequired: true,
              mcpApprovalRequiredAction: 'materialize',
              errors: [...prev.errors, e?.message || 'Approval required'],
            }));
            setShowApprovals(true);
            return;
          }

          // If MCP materialize fails for environment reasons (e.g., Neo4j not configured), try the PLM direct sync.
          console.warn('MCP materialize skipped:', e?.message || e);
        }
      }

      if (!mcpMaterialize) {
        try {
          const syncResponse = await e2etraceFetchWithRetry(`${plmBaseUrl}/runs/${runId}/sync/neo4j/direct`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
          });
          syncResult = await syncResponse.json();
        } catch (syncError) {
          console.warn('Direct Neo4j sync skipped (Neo4j may not be configured):', syncError?.message || syncError);
        }
      }

      // STEP 6: Publish to target service (OpenSearch)
      let mcpPublish = null;
      if (willPublishToOpenSearch && wizardData.mcpRunId) {
        setWizardData((prev) => ({
          ...prev,
          migrationStep: 'Step 6: Publishing to OpenSearch...',
          processedRecords: 6,
        }));
        try {
          mcpPublish = await publishMcpRunBestEffort({
            mcpRunId: wizardData.mcpRunId,
            approvalToken:
              String(wizardData.mcpApprovalTokenAction || '').toLowerCase() === 'publish'
                ? wizardData.mcpApprovalToken
                : '',
          });
          setWizardData((prev) => ({
            ...prev,
            mcpPublishSummary: mcpPublish,
          }));
        } catch (e) {
          if (e?.status === 403) {
            setWizardData((prev) => ({
              ...prev,
              migrationStatus: 'awaiting_approval',
              migrationStep: 'Waiting for approval to publish to OpenSearch',
              mcpApprovalRequired: true,
              mcpApprovalRequiredAction: 'publish',
              errors: [...prev.errors, e?.message || 'Approval required'],
            }));
            setShowApprovals(true);
            return;
          }
          console.warn('MCP publish skipped:', e?.message || e);
        }
      }

      // Best-effort: mark MCP run as completed
      try {
        if (wizardData.mcpRunId) {
          await transitionMcpRunBestEffort({
            mcpRunId: wizardData.mcpRunId,
            toStatus: 'completed',
            event: 'execute.complete',
            note: 'Execute step completed from Migration Wizard',
          });
        }
      } catch (e) {
        console.warn('MCP run completion transition unavailable:', e?.message || e);
      }
      
      setWizardData(prev => ({
        ...prev,
        migrationStatus: 'completed',
        migrationStep: 'Complete!',
        processedRecords: willPublishToOpenSearch ? 6 : 5,
        totalRecords: willPublishToOpenSearch ? 6 : 5,
        nodesCreated: syncResult?.nodes_created || mcpMaterialize?.sample_nodes || 0
      }));
      
      setStepStatus(prev => ({
        ...prev,
        5: { complete: true, valid: true }
      }));
      
      if (onComplete) onComplete({ runId, syncResult });
      
    } catch (error) {
      console.error('Migration failed:', error);

      // Best-effort: mark MCP run as failed
      try {
        if (wizardData.mcpRunId) {
          await transitionMcpRunBestEffort({
            mcpRunId: wizardData.mcpRunId,
            toStatus: 'failed',
            event: 'execute.failed',
            note: error?.message || 'Execute step failed',
          });
        }
      } catch (e) {
        console.warn('MCP run failure transition unavailable:', e?.message || e);
      }

      setWizardData(prev => ({
        ...prev,
        migrationStatus: 'failed',
        migrationStep: 'Failed',
        errors: [...prev.errors, error.message]
      }));
    } finally {
      setIsLoading(false);
    }
  }, [
    wizardData,
    onComplete,
    stageMcpSampleBestEffort,
    materializeMcpRunBestEffort,
    publishMcpRunBestEffort,
    transitionMcpRunBestEffort,
  ]);

  const retryGovernedAction = useCallback(async () => {
    const rid = String(wizardData.mcpRunId || '').trim();
    if (!rid) return;

    const requiredAction = String(wizardData.mcpApprovalRequiredAction || 'materialize').toLowerCase();
    const willPublishToOpenSearch = String(wizardData.targetSystem?.id || '')
      .toLowerCase()
      .includes('opensearch');

    setIsLoading(true);
    try {
      setWizardData((prev) => ({
        ...prev,
        migrationStatus: 'running',
        migrationStep:
          requiredAction === 'publish'
            ? 'Retrying publish to OpenSearch...'
            : 'Retrying materialize lineage to Neo4j...',
      }));

      if (requiredAction === 'publish') {
        const mcpPublish = await publishMcpRunBestEffort({
          mcpRunId: rid,
          approvalToken:
            String(wizardData.mcpApprovalTokenAction || '').toLowerCase() === 'publish'
              ? wizardData.mcpApprovalToken
              : '',
        });
        setWizardData((prev) => ({
          ...prev,
          migrationStatus: 'completed',
          migrationStep: 'Complete!',
          mcpApprovalRequired: false,
          mcpApprovalRequiredAction: '',
          mcpPublishSummary: mcpPublish,
          processedRecords: willPublishToOpenSearch ? 6 : prev.processedRecords,
        }));
      } else {
        const sample = Array.isArray(wizardData.mcpLastStagedSample) ? wizardData.mcpLastStagedSample : [];
        await stageMcpSampleBestEffort({ mcpRunId: rid, entity: 'part', records: sample });
        const mcpMaterialize = await materializeMcpRunBestEffort({
          mcpRunId: rid,
          approvalToken:
            String(wizardData.mcpApprovalTokenAction || '').toLowerCase() === 'materialize'
              ? wizardData.mcpApprovalToken
              : '',
        });

        // If the selected target is OpenSearch, follow up with publish (may require its own approval).
        if (willPublishToOpenSearch) {
          setWizardData((prev) => ({
            ...prev,
            migrationStep: 'Step 6: Publishing to OpenSearch...',
            processedRecords: 6,
          }));
          try {
            const mcpPublish = await publishMcpRunBestEffort({
              mcpRunId: rid,
              approvalToken:
                String(wizardData.mcpApprovalTokenAction || '').toLowerCase() === 'publish'
                  ? wizardData.mcpApprovalToken
                  : '',
            });
            setWizardData((prev) => ({
              ...prev,
              mcpPublishSummary: mcpPublish,
            }));
          } catch (e) {
            if (e?.status === 403) {
              setWizardData((prev) => ({
                ...prev,
                migrationStatus: 'awaiting_approval',
                migrationStep: 'Waiting for approval to publish to OpenSearch',
                mcpApprovalRequired: true,
                mcpApprovalRequiredAction: 'publish',
                errors: [...prev.errors, e?.message || 'Approval required'],
              }));
              setShowApprovals(true);
              return;
            }
          }
        }

        setWizardData((prev) => ({
          ...prev,
          migrationStatus: 'completed',
          migrationStep: 'Complete!',
          mcpApprovalRequired: false,
          mcpApprovalRequiredAction: '',
          mcpMaterializeSummary: mcpMaterialize,
          nodesCreated: mcpMaterialize?.sample_nodes || prev.nodesCreated || 0,
          processedRecords: willPublishToOpenSearch ? 6 : 5,
          totalRecords: willPublishToOpenSearch ? 6 : 5,
        }));
      }

      setStepStatus(prev => ({
        ...prev,
        5: { complete: true, valid: true }
      }));
    } catch (e) {
      if (e?.status === 403) {
        setWizardData((prev) => ({
          ...prev,
          migrationStatus: 'awaiting_approval',
          migrationStep: requiredAction === 'publish' ? 'Waiting for approval to publish to OpenSearch' : 'Waiting for approval to materialize to Neo4j',
          mcpApprovalRequired: true,
          mcpApprovalRequiredAction: requiredAction,
          errors: [...prev.errors, e?.message || 'Approval required'],
        }));
      } else {
        setWizardData((prev) => ({
          ...prev,
          migrationStatus: 'failed',
          migrationStep: 'Failed',
          errors: [...prev.errors, e?.message || 'Materialize failed'],
        }));
      }
    } finally {
      setIsLoading(false);
    }
  }, [
    wizardData.mcpRunId,
    wizardData.mcpLastStagedSample,
    wizardData.mcpApprovalToken,
    wizardData.mcpApprovalTokenAction,
    wizardData.mcpApprovalRequiredAction,
    wizardData.targetSystem,
    stageMcpSampleBestEffort,
    materializeMcpRunBestEffort,
    publishMcpRunBestEffort,
  ]);

  // Render step content
  const renderStepContent = () => {
    switch (currentStep) {
      case 1: return renderConnectStep();
      case 2: return renderSchemaStep();
      case 3: return renderMappingStep();
      case 4: return renderValidateStep();
      case 5: return renderExecuteStep();
      default: return null;
    }
  };

  const renderConnectStep = () => (
    <div className="wizard-step-content connect-step">
      <h3>Configure Data Sources</h3>
      <p className="step-description">Select source and target systems for your PLM data migration</p>

      <div className="form-group" style={{ marginTop: '8px' }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <input
            type="checkbox"
            checked={showAllSources}
            onChange={(e) => setShowAllSources(e.target.checked)}
          />
          Show all configured sources (including legacy/test entries)
        </label>
      </div>

      <div className="run-identity">
        <div className="run-identity-header">
          <h4><i className="fas fa-tag" /> Workflow Instance Name</h4>
          <p>Name this migration run so it can be tracked consistently across steps.</p>
        </div>
        <input
          className="run-identity-input"
          type="text"
          value={wizardData.workflowName}
          onChange={(e) => setWorkflowName(e.target.value)}
          placeholder="e.g., PLM Parts Migration - Jan 2026"
          aria-label="Workflow instance name"
        />
        {wizardData.workflowName.trim().length === 0 && (
          <div className="run-identity-hint">
            A workflow instance name is required to continue.
          </div>
        )}
      </div>
      
      <div className="source-selection-grid">
        <div className="source-panel">
          <h4><i className="fas fa-database" /> Source System</h4>
          <p>Where is your data coming from?</p>
          
          {visibleSources.length === 0 ? (
            <div className="no-sources">
              <p>No connected data sources available.</p>
              <p className="no-sources-hint">
                Ask an administrator to configure connection settings (data sources) in Admin Settings, then return here.
              </p>
            </div>
          ) : (
            <div className="source-list">
              {visibleSources.map(source => (
                <div 
                  key={source.id}
                  className={`source-option ${wizardData.sourceSystem?.id === source.id ? 'selected' : ''}`}
                  onClick={() => selectSource('source', source)}
                >
                  <div className="source-icon">
                    <i className={`fas ${getSourceIcon(source.type)}`} />
                  </div>
                  <div className="source-info">
                    <span className="source-name">{source.name}</span>
                    <span className="source-type">{source.type}</span>
                  </div>
                  <div className="source-status connected">
                    <i className={source?.status === 'connected' || source?.status === 'active' ? 'fas fa-check-circle' : 'fas fa-cog'} /> {source?.status || 'configured'}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
        
        <div className="flow-indicator">
          <i className="fas fa-long-arrow-alt-right" />
        </div>
        
        <div className="source-panel">
          <h4><i className="fas fa-bullseye" /> Target System</h4>
          <p>Where should the data go?</p>
          
          <div className="source-list">
            {visibleSources.map(source => (
              <div 
                key={source.id}
                className={`source-option ${wizardData.targetSystem?.id === source.id ? 'selected' : ''} ${wizardData.sourceSystem?.id === source.id ? 'disabled' : ''}`}
                onClick={() => wizardData.sourceSystem?.id !== source.id && selectSource('target', source)}
              >
                <div className="source-icon">
                  <i className={`fas ${getSourceIcon(source.type)}`} />
                </div>
                <div className="source-info">
                  <span className="source-name">{source.name}</span>
                  <span className="source-type">{source.type}</span>
                </div>
                <div className="source-status connected">
                  <i className={source?.status === 'connected' || source?.status === 'active' ? 'fas fa-check-circle' : 'fas fa-cog'} /> {source?.status || 'configured'}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
      
      {/* AI Status */}
      <div className="ai-status-bar">
        <span className={`status-indicator ${graphRAGHealth.health?.neo4j_connected ? 'active' : ''}`}>
          <i className="fas fa-brain" /> AI Assistant: {graphRAGHealth.health?.status || 'Checking...'}
        </span>
        <span className={`status-indicator ${agenticSystem.status?.status === 'healthy' ? 'active' : ''}`}>
          <i className="fas fa-robot" /> Agentic: {agenticSystem.status?.status || 'Checking...'}
        </span>
      </div>
    </div>
  );

  const renderSchemaStep = () => (
    <div className="wizard-step-content discovery-step">
      <h3>Discovery Agent</h3>
      <p className="step-description">Run discovery to generate SODA-driven insights and mapping hints</p>

      <div className="discovery-actions">
        <button
          className="btn btn-primary"
          onClick={runDiscovery}
          disabled={!wizardData.sourceSystem || !wizardData.targetSystem || isLoading || wizardData.discoveryStatus === 'running'}
        >
          <i className="fas fa-search" /> {wizardData.discoveryStatus === 'running' ? 'Running Discovery...' : 'Run Discovery'}
        </button>

        <button
          className="btn btn-success"
          onClick={acceptDiscovery}
          disabled={wizardData.discoveryStatus !== 'completed' || wizardData.discoveryAccepted}
        >
          <i className="fas fa-check" /> {wizardData.discoveryAccepted ? 'Discovery Accepted' : 'Accept Discovery'}
        </button>
      </div>

      {wizardData.discoveryRunId && (
        <div className="discovery-meta">
          Discovery run: <strong>{wizardData.discoveryRunId}</strong>
        </div>
      )}

      {wizardData.mcpRunId && (
        <div className="discovery-meta">
          MCP run: <strong>{wizardData.mcpRunId}</strong>
        </div>
      )}

      <div className="discovery-results">
        {wizardData.discoveryInsights.length > 0 ? (
          <div className="discovery-insights">
            {wizardData.discoveryInsights.map((insight) => (
              <div key={insight.id} className={`discovery-insight ${insight.severity || 'info'}`}>
                <div className="discovery-insight-title">{insight.title}</div>
                <div className="discovery-insight-detail">{insight.detail}</div>
              </div>
            ))}
          </div>
        ) : (
          <p className="placeholder">
            Run Discovery to generate insights. You must accept discovery before continuing.
          </p>
        )}

        {wizardData.discoveryStatus === 'failed' && wizardData.discoveryError && (
          <div className="discovery-error">{wizardData.discoveryError}</div>
        )}
      </div>
    </div>
  );

  const renderMappingStep = () => {
    const sourceFields = extractSchemaFields(wizardData.sourceSchema);
    const targetFields = extractSchemaFields(wizardData.targetSchema);
    
    return (
    <div className="wizard-step-content mapping-step">
      <h3>Define Field Mappings</h3>
      <p className="step-description">Map source fields to target fields with AI assistance</p>

      {wizardData.discoveryIntrospect && (
        <div className="schema-panels" style={{ marginBottom: 24 }}>
          <div className="schema-panel">
            <div className="schema-header">
              <h4><i className="fas fa-microscope" /> Introspect (Discovery Outcome)</h4>
              <span className="discovery-meta">Run: <strong>{wizardData.discoveryRunId}</strong></span>
            </div>
            <div className="schema-content">
              {wizardData.discoveryInsights?.length > 0 && (
                <div className="discovery-insights" style={{ marginBottom: 12 }}>
                  {wizardData.discoveryInsights.slice(0, 3).map((insight) => (
                    <div key={insight.id} className={`discovery-insight ${insight.severity || 'info'}`}>
                      <div className="discovery-insight-title">{insight.title}</div>
                      <div className="discovery-insight-detail">{insight.detail}</div>
                    </div>
                  ))}
                </div>
              )}
              <pre className="schema-preview">{JSON.stringify(wizardData.discoveryIntrospect, null, 2)}</pre>
            </div>
          </div>
          <div className="schema-panel">
            <div className="schema-header">
              <h4><i className="fas fa-table" /> Sample Preview</h4>
            </div>
            <div className="schema-content">
              <pre className="schema-preview">{JSON.stringify((wizardData.discoverySample && Array.isArray(wizardData.discoverySample.records)
                ? wizardData.discoverySample.records.slice(0, 8)
                : null), null, 2)}</pre>
            </div>
          </div>
        </div>
      )}
      
      {/* Help text for users */}
      {(!wizardData.sourceSchema && !wizardData.targetSchema) && (
        <div className="mapping-help-alert">
          <i className="fas fa-info-circle" />
          <span>Go back to <strong>Step 2 (Discovery)</strong> to run discovery first, or use a template below.</span>
        </div>
      )}
      
      <div className="mapping-tools">
        <button 
          className="btn btn-primary btn-ai"
          onClick={getAIMappingSuggestions}
          disabled={isLoading}
          title="Get AI-powered field mapping suggestions"
        >
          <i className="fas fa-magic" /> {isLoading ? 'Loading...' : 'Get AI Suggestions'}
        </button>
        
        <div className="template-selector">
          <label>Apply Template:</label>
          <select 
            value={wizardData.selectedTemplate?.id || ''}
            onChange={(e) => {
              const template = mappingTemplates.find(t => t.id === e.target.value);
              if (template) applyTemplate(template);
            }}
          >
            <option value="">Select template...</option>
            {mappingTemplates.map(t => (
              <option key={t.id} value={t.id}>{t.name}</option>
            ))}
          </select>
        </div>
      </div>
      
      {/* Available Fields Reference */}
      <div className="available-fields-panel">
        <div className="fields-column">
          <h5><i className="fas fa-arrow-right" /> Source Fields ({sourceFields.length})</h5>
          {sourceFields.length > 0 ? (
            <div className="fields-list">
              {sourceFields.slice(0, 15).map((field, idx) => (
                <span key={idx} className="field-tag source" title="Click to add mapping" onClick={() => addFieldMapping({ source_field: field, target_field: '', transformation: null })}>
                  {field}
                </span>
              ))}
              {sourceFields.length > 15 && <span className="more-fields">+{sourceFields.length - 15} more</span>}
            </div>
          ) : (
            <p className="no-fields">No source schema available - run Discovery in Step 2 or select a template</p>
          )}
        </div>
        <div className="fields-arrow"><i className="fas fa-long-arrow-alt-right" /></div>
        <div className="fields-column">
          <h5><i className="fas fa-bullseye" /> Target Fields ({targetFields.length})</h5>
          {targetFields.length > 0 ? (
            <div className="fields-list">
              {targetFields.slice(0, 15).map((field, idx) => (
                <span key={idx} className="field-tag target">{field}</span>
              ))}
              {targetFields.length > 15 && <span className="more-fields">+{targetFields.length - 15} more</span>}
            </div>
          ) : (
            <p className="no-fields">No target schema available - run Discovery in Step 2 or select a template</p>
          )}
        </div>
      </div>
      
      {/* AI Suggestions */}
      {wizardData.aiSuggestedMappings.length > 0 && (
        <div className="ai-suggestions-panel">
          <h4><i className="fas fa-lightbulb" /> AI Suggested Mappings</h4>
          <div className="suggestions-actions">
            <button 
              className="btn btn-sm btn-success"
              onClick={() => {
                wizardData.aiSuggestedMappings.forEach(s => addFieldMapping({
                  source_field: s.sourceField,
                  target_field: s.targetField,
                  transformation: s.transformation
                }));
              }}
            >
              <i className="fas fa-check-double" /> Apply All
            </button>
          </div>
          <div className="suggestions-list">
            {wizardData.aiSuggestedMappings.map((suggestion, idx) => (
              <div key={idx} className="suggestion-item">
                <span className="mapping-arrow">{suggestion.sourceField} → {suggestion.targetField}</span>
                {suggestion.transformation && <span className="transform-badge">{suggestion.transformation}</span>}
                <span className="confidence">{suggestion.confidence || 'N/A'}</span>
                <button 
                  className="btn btn-sm btn-success"
                  onClick={() => addFieldMapping({
                    source_field: suggestion.sourceField,
                    target_field: suggestion.targetField,
                    transformation: suggestion.transformation
                  })}
                >
                  <i className="fas fa-plus" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
      
      {/* Current Mappings */}
      <div className="mappings-table">
        <h4>Current Field Mappings ({wizardData.fieldMappings.length})</h4>
        <table>
          <thead>
            <tr>
              <th>Source Field</th>
              <th>Target Field</th>
              <th>Transformation</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {wizardData.fieldMappings.map((mapping, idx) => (
              <tr key={idx}>
                <td>
                  <input 
                    type="text" 
                    value={mapping.source_field}
                    onChange={(e) => {
                      const updated = [...wizardData.fieldMappings];
                      updated[idx] = { ...mapping, source_field: e.target.value };
                      setWizardData(prev => ({ ...prev, fieldMappings: updated }));
                    }}
                  />
                </td>
                <td>
                  <input 
                    type="text" 
                    value={mapping.target_field}
                    onChange={(e) => {
                      const updated = [...wizardData.fieldMappings];
                      updated[idx] = { ...mapping, target_field: e.target.value };
                      setWizardData(prev => ({ ...prev, fieldMappings: updated }));
                    }}
                  />
                </td>
                <td>
                  <input 
                    type="text" 
                    value={mapping.transformation || ''}
                    placeholder="e.g., UPPER, TRIM"
                    onChange={(e) => {
                      const updated = [...wizardData.fieldMappings];
                      updated[idx] = { ...mapping, transformation: e.target.value || null };
                      setWizardData(prev => ({ ...prev, fieldMappings: updated }));
                    }}
                  />
                </td>
                <td>
                  <button 
                    className="btn btn-sm btn-danger"
                    onClick={() => removeFieldMapping(idx)}
                  >
                    <i className="fas fa-trash" />
                  </button>
                </td>
              </tr>
            ))}
            <tr className="add-row">
              <td colSpan="4">
                <button 
                  className="btn btn-sm btn-secondary"
                  onClick={() => addFieldMapping({ source_field: '', target_field: '', transformation: null })}
                >
                  <i className="fas fa-plus" /> Add Mapping
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
  };

  const renderValidateStep = () => (
    <div className="wizard-step-content validate-step">
      <h3>Validate & Transform</h3>
      <p className="step-description">Run quality checks and test transformations before execution</p>
      
      <div className="validation-actions">
        <button 
          className="btn btn-primary"
          onClick={runValidation}
          disabled={isLoading}
        >
          <i className="fas fa-check-double" /> Run Validation
        </button>
        <button 
          className="btn btn-secondary"
          onClick={testTransformation}
          disabled={isLoading || !wizardData.fieldMappings.length}
        >
          <i className="fas fa-exchange-alt" /> Test Transform
        </button>
        <button 
          className="btn btn-info"
          onClick={runSodaScan}
          disabled={isLoading || !wizardData.runId}
          title={!wizardData.runId ? 'Run migration first to enable SODA scan' : 'Run SODA data quality checks'}
        >
          <i className="fas fa-shield-alt" /> SODA Quality Scan
        </button>
      </div>
      
      {/* SODA Scan Result */}
      {wizardData.sodaScanResult && (
        <div className={`soda-result ${wizardData.sodaScanResult.status}`}>
          <div className="soda-header">
            <i className={`fas ${wizardData.sodaScanResult.status === 'pass' ? 'fa-check-circle' : 'fa-exclamation-triangle'}`} />
            <span>SODA Quality Gate: <strong>{wizardData.sodaScanResult.status?.toUpperCase()}</strong></span>
          </div>
          <div className="soda-metrics">
            <span>Score: <strong>{(wizardData.sodaScanResult.overall_score * 100).toFixed(0)}%</strong></span>
            <span>Issues: <strong>{wizardData.sodaScanResult.issues_count}</strong></span>
            <span>Blocked: <strong>{wizardData.sodaScanResult.blocked ? 'Yes' : 'No'}</strong></span>
          </div>
        </div>
      )}
      
      {/* Quality Metrics */}
      <div className="quality-metrics">
        <div className={`metric passed ${wizardData.qualityChecks.passed > 0 ? 'has-value' : ''}`}>
          <span className="metric-value">{wizardData.qualityChecks.passed}</span>
          <span className="metric-label">Passed</span>
        </div>
        <div className={`metric warnings ${wizardData.qualityChecks.warnings > 0 ? 'has-value' : ''}`}>
          <span className="metric-value">{wizardData.qualityChecks.warnings}</span>
          <span className="metric-label">Warnings</span>
        </div>
        <div className={`metric failed ${wizardData.qualityChecks.failed > 0 ? 'has-value' : ''}`}>
          <span className="metric-value">{wizardData.qualityChecks.failed}</span>
          <span className="metric-label">Failed</span>
        </div>
      </div>
      
      {/* Validation Results */}
      {wizardData.validationResults.length > 0 && (
        <div className="validation-results">
          <h4>Validation Results</h4>
          <div className="results-list">
            {wizardData.validationResults.map((result, idx) => (
              <div key={idx} className={`result-item ${result.severity}`}>
                <i className={`fas ${getSeverityIcon(result.severity)}`} />
                <div className="result-content">
                  <span className="result-insight">{result.insight}</span>
                  {result.recommendation && (
                    <span className="result-recommendation">{result.recommendation}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );

  const renderExecuteStep = () => (
    <div className="wizard-step-content execute-step">
      <h3>Execute Migration</h3>
      <p className="step-description">Run the migration and monitor progress</p>

      {/* Governance / approvals */}
      <div className="mcp-governance-card">
        <div className="mcp-governance-header">
          <h4><i className="fas fa-user-shield" /> Governance & approvals</h4>
          <button
            className="btn btn-sm btn-ghost"
            onClick={() => setShowApprovals((s) => !s)}
            aria-expanded={showApprovals ? 'true' : 'false'}
          >
            <i className={`fas fa-chevron-${showApprovals ? 'up' : 'down'}`} />
            {showApprovals ? 'Hide' : 'Show'}
          </button>
        </div>

        {!wizardData.mcpRunId ? (
          <div className="inline-alert info">
            MCP run tracking is not available yet. Run Discovery first (Step 2) to create the MCP run.
          </div>
        ) : (
          <div className="mcp-governance-meta">
            <div>
              MCP run: <code>{wizardData.mcpRunId}</code>
            </div>
            <div className="mcp-token-row">
              Approval token:{' '}
              {wizardData.mcpApprovalToken ? (
                <>
                  <code>{wizardData.mcpApprovalToken}</code>
                  {wizardData.mcpApprovalTokenAction ? (
                    <span className="muted" style={{ marginLeft: 8 }}>
                      (for <code>{wizardData.mcpApprovalTokenAction}</code>)
                    </span>
                  ) : null}
                </>
              ) : (
                <span className="muted">(none)</span>
              )}
              <button
                className="btn btn-sm btn-secondary"
                onClick={() =>
                  setWizardData((prev) => ({
                    ...prev,
                    mcpApprovalToken: '',
                    mcpApprovalTokenAction: '',
                  }))
                }
                disabled={!wizardData.mcpApprovalToken}
                title="Clear selected token"
              >
                Clear
              </button>
            </div>
          </div>
        )}

        {wizardData.mcpApprovalRequired && (
          <div className="inline-alert warning">
            Approval is required to{' '}
            <strong>{wizardData.mcpApprovalRequiredAction || 'materialize'}</strong>. Request an approval below, approve it (admin), then click “Use token”.
          </div>
        )}

        {(showApprovals || wizardData.mcpApprovalRequired) && (
          <ApprovalsPanel
            runId={wizardData.mcpRunId}
            defaultAction={wizardData.mcpApprovalRequiredAction || 'materialize'}
            defaultRequestedBy=""
            sample={wizardData.mcpLastStagedSample}
            impact={{
              operation: wizardData.mcpApprovalRequiredAction || 'materialize',
              target: (wizardData.mcpApprovalRequiredAction || 'materialize') === 'publish' ? 'opensearch' : 'neo4j',
              note:
                (wizardData.mcpApprovalRequiredAction || 'materialize') === 'publish'
                  ? 'Indexes staged sample documents to OpenSearch and records publish lineage in Neo4j'
                  : 'Writes staged sample nodes for this run to Neo4j (idempotent MERGE)'
            }}
            onTokenSelected={(sel) =>
              setWizardData((prev) => ({
                ...prev,
                mcpApprovalToken: String(sel?.token || ''),
                mcpApprovalTokenAction: String(sel?.action || ''),
              }))
            }
          />
        )}
      </div>
      
      {/* Migration Summary */}
      <div className="migration-summary">
        <h4>Migration Summary</h4>
        <div className="summary-grid">
          <div className="summary-item">
            <label>Source:</label>
            <span>{wizardData.sourceSystem?.name || 'Not configured'}</span>
          </div>
          <div className="summary-item">
            <label>Target:</label>
            <span>{wizardData.targetSystem?.name || 'Not configured'}</span>
          </div>
          <div className="summary-item">
            <label>Mappings:</label>
            <span>{wizardData.fieldMappings.length} field mappings</span>
          </div>
          <div className="summary-item">
            <label>Validation:</label>
            <span className={wizardData.qualityChecks.failed === 0 ? 'success' : 'warning'}>
              {wizardData.qualityChecks.failed === 0 ? 'All checks passed' : `${wizardData.qualityChecks.failed} issues`}
            </span>
          </div>
        </div>
      </div>
      
      {/* Execution Controls */}
      {wizardData.migrationStatus === 'pending' && (
        <div className="execution-controls">
          <button 
            className="btn btn-primary btn-lg"
            onClick={executeMigration}
            disabled={isLoading || wizardData.qualityChecks.failed > 0}
          >
            <i className="fas fa-play" /> Start Migration
          </button>
          {wizardData.qualityChecks.failed > 0 && (
            <p className="warning">Please resolve validation errors before executing</p>
          )}
        </div>
      )}
      
      {/* Progress */}
      {wizardData.migrationStatus === 'running' && (
        <div className="migration-progress">
          <div className="progress-bar">
            <div 
              className="progress-fill"
              style={{ width: wizardData.totalRecords > 0 ? `${(wizardData.processedRecords / wizardData.totalRecords) * 100}%` : '0%' }}
            />
          </div>
          <div className="progress-text">
            {wizardData.migrationStep || 'Processing...'}
          </div>
          <div className="migration-steps-list">
            <div className={`migration-step-item ${wizardData.processedRecords >= 1 ? 'complete' : wizardData.processedRecords > 0 ? 'active' : ''}`}>
              <i className="fas fa-plus-circle" /> Step 1: Create Run
            </div>
            <div className={`migration-step-item ${wizardData.processedRecords >= 2 ? 'complete' : wizardData.processedRecords >= 1 ? 'active' : ''}`}>
              <i className="fas fa-database" /> Step 2: Stage Records
            </div>
            <div className={`migration-step-item ${wizardData.processedRecords >= 3 ? 'complete' : wizardData.processedRecords >= 2 ? 'active' : ''}`}>
              <i className="fas fa-exchange-alt" /> Step 3: Transform
            </div>
            <div className={`migration-step-item ${wizardData.processedRecords >= 4 ? 'complete' : wizardData.processedRecords >= 3 ? 'active' : ''}`}>
              <i className="fas fa-shield-alt" /> Step 4: Quality Scan & Validate
            </div>
            <div className={`migration-step-item ${wizardData.processedRecords >= 5 ? 'complete' : wizardData.processedRecords >= 4 ? 'active' : ''}`}>
              <i className="fas fa-project-diagram" /> Step 5: Materialize lineage (Neo4j)
            </div>
            {String(wizardData.targetSystem?.id || '').toLowerCase().includes('opensearch') && (
              <div className={`migration-step-item ${wizardData.processedRecords >= 6 ? 'complete' : wizardData.processedRecords >= 5 ? 'active' : ''}`}>
                <i className="fas fa-search" /> Step 6: Publish/index (OpenSearch)
              </div>
            )}
          </div>
          <div className="spinner">
            <i className="fas fa-spinner fa-spin" />
          </div>
        </div>
      )}

      {/* Awaiting approval */}
      {wizardData.migrationStatus === 'awaiting_approval' && (
        <div className="migration-failed" style={{ paddingTop: 24 }}>
          <div className="error-icon" style={{ color: 'var(--warning-color, #ffc107)' }}>
            <i className="fas fa-user-check" />
          </div>
          <h4 style={{ color: 'var(--warning-color, #ffc107)' }}>Waiting for approval</h4>
          <p className="step-description" style={{ marginBottom: 12 }}>
            This operation is gated (<code>{wizardData.mcpApprovalRequiredAction || 'materialize'}</code>). Select an approved token above, then retry.
          </p>
          <button
            className="btn btn-primary"
            onClick={retryGovernedAction}
            disabled={
              !wizardData.mcpRunId ||
              !String(wizardData.mcpApprovalToken || '').trim() ||
              String(wizardData.mcpApprovalTokenAction || '').toLowerCase() !==
                String(wizardData.mcpApprovalRequiredAction || 'materialize').toLowerCase() ||
              isLoading
            }
            title={
              !wizardData.mcpApprovalToken
                ? 'Select an approved token first'
                : String(wizardData.mcpApprovalTokenAction || '').toLowerCase() !==
                  String(wizardData.mcpApprovalRequiredAction || 'materialize').toLowerCase()
                  ? 'Selected token action does not match required action'
                  : 'Retry governed action'
            }
          >
            <i className="fas fa-play" /> Retry
          </button>
        </div>
      )}
      
      {/* Completion */}
      {wizardData.migrationStatus === 'completed' && (
        <div className="migration-complete">
          <div className="success-icon">
            <i className="fas fa-check-circle" />
          </div>
          <h4>Migration Completed Successfully!</h4>
          <p>Processed {wizardData.processedRecords} records</p>
          <div className="completion-actions">
            <span className="completion-note">
              Migration is complete. You can review results from the main navigation after finishing.
            </span>
          </div>
        </div>
      )}
      
      {/* Errors */}
      {wizardData.migrationStatus === 'failed' && (
        <div className="migration-failed">
          <div className="error-icon">
            <i className="fas fa-exclamation-circle" />
          </div>
          <h4>Migration Failed</h4>
          <div className="error-list">
            {wizardData.errors.map((error, idx) => (
              <div key={idx} className="error-item">{error}</div>
            ))}
          </div>
          <button 
            className="btn btn-warning"
            onClick={() => setWizardData(prev => ({ ...prev, migrationStatus: 'pending', errors: [] }))}
          >
            <i className="fas fa-redo" /> Retry
          </button>
        </div>
      )}
    </div>
  );

  // Helper functions
  const getSourceIcon = (type) => {
    const icons = {
      database: 'fa-database',
      neo4j: 'fa-project-diagram',
      mongodb: 'fa-leaf',
      api: 'fa-plug',
      file: 'fa-file',
      kafka: 'fa-stream'
    };
    return icons[type] || 'fa-database';
  };

  const getSeverityIcon = (severity) => {
    const icons = {
      success: 'fa-check-circle',
      info: 'fa-info-circle',
      warning: 'fa-exclamation-triangle',
      error: 'fa-times-circle'
    };
    return icons[severity] || 'fa-info-circle';
  };

  return (
    <div className={`migration-wizard ${embedded ? 'embedded' : ''}`}>
      {/* Interactive State Flow Visualization */}
      <div className="state-flow-section">
        <div className="state-flow-header">
          <h4>
            <i className="fas fa-project-diagram" /> Migration State Flow
          </h4>
          <button 
            className="btn btn-sm btn-ghost"
            onClick={() => setShowStateFlow(!showStateFlow)}
          >
            <i className={`fas fa-chevron-${showStateFlow ? 'up' : 'down'}`} />
            {showStateFlow ? 'Hide' : 'Show'}
          </button>
        </div>
        {showStateFlow && (
          <div className="state-flow-visualizer">
            <XStateVisualizer
              graphData={stateFlowGraphData}
              embedded
              enabledViewModes={['graph']}
              uiVariant="graph-only"
            />
          </div>
        )}
      </div>

      {/* Progress Steps */}
      <div className="wizard-steps">
        {steps.map((step, index) => (
          <div 
            key={step.id}
            className={`wizard-step ${currentStep === step.id ? 'active' : ''} ${stepStatus[step.id]?.complete ? 'completed' : ''} ${step.id < currentStep ? 'past' : ''}`}
          >
            <div className="step-indicator">
              {stepStatus[step.id]?.complete ? (
                <i className="fas fa-check" />
              ) : (
                <i className={`fas ${step.icon}`} />
              )}
            </div>
            <div className="step-info">
              <span className="step-name">{step.name}</span>
              <span className="step-description">{step.description}</span>
            </div>
            {index < steps.length - 1 && <div className="step-connector" />}
          </div>
        ))}
      </div>
      
      {/* Step Content */}
      <div className="wizard-content">
        {isLoading && (
          <div className="loading-overlay">
            <i className="fas fa-spinner fa-spin" />
            <span>Processing...</span>
          </div>
        )}
        {renderStepContent()}
      </div>
      
      {/* Navigation */}
      <div className="wizard-navigation">
        <button 
          className="btn btn-secondary"
          onClick={prevStep}
          disabled={currentStep === 1}
        >
          <i className="fas fa-arrow-left" /> Previous
        </button>
        
        <div className="step-indicator-text">
          Step {currentStep} of {steps.length}
        </div>
        
        {currentStep < 5 ? (
          <button 
            className="btn btn-primary"
            onClick={nextStep}
            disabled={!canProceed(currentStep)}
          >
            Next <i className="fas fa-arrow-right" />
          </button>
        ) : (
          <button 
            className="btn btn-success"
            onClick={() => onComplete && onComplete({ runId: wizardData.runId })}
            disabled={wizardData.migrationStatus !== 'completed'}
          >
            Finish <i className="fas fa-check" />
          </button>
        )}
      </div>
    </div>
  );
};

export default MigrationWizard;
