import React, { useState, useCallback, useEffect, useMemo, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { e2etraceFetchWithRetry } from '../../api/e2etrace-api';
import { API_CONFIG } from '../../config/api-config.js';
import { useGraphQLTransform } from '../../hooks/useGraphQL.js';
import { useAISuggestions, useGraphRAGHealth } from '../../hooks/useGraphRAG.js';
import { useAgenticSystemStatus } from '../../hooks/useAgenticAI.js';
import { XStateVisualizer } from '../xstate-visualizer/XStateVisualizer';
import { toast } from '../../hooks/useToast';
import WizardRuleEngine from './WizardRuleEngine';
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
  const [searchParams, setSearchParams] = useSearchParams();
  
  // Initialize step from URL if available, otherwise use initialStep prop
  const getInitialStepFromURL = () => {
    const stepParam = searchParams.get('step');
    if (stepParam && !isNaN(stepParam)) {
      const step = parseInt(stepParam, 10);
      if (step >= 1 && step <= 5) {
        return step;
      }
    }
    return initialStep;
  };
  
  // Wizard state
  const [currentStep, setCurrentStep] = useState(getInitialStepFromURL);
  // Per-operation loading flags — prevents unrelated buttons from being disabled during an operation
  const [opLoading, setOpLoading] = useState({ discovery: false, suggestions: false, validation: false, execute: false });
  // Guard against double-firing the initial data load (React StrictMode / HMR)
  const initialLoadRef = useRef(false);
  const [wizardData, setWizardData] = useState({
    // Step 0: Run identity
    workflowName: '',
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
    // Step 3: Mapping
    fieldMappings: [],
    aiSuggestedMappings: [],
    selectedTemplate: null,
    // Rule engine (pre-transform, quality, post-transform)
    rules: [],
    activeRulePhase: 'pre',
    // Step 4: Validation
    validationResults: [],
    qualityChecks: { passed: 0, failed: 0, warnings: 0 },
    validationRun: false,
    // Step 5: Execution
    migrationStatus: 'pending',
    processedRecords: 0,
    totalRecords: 0,
    errors: [],
    runId: null,
    // Saved workflow instance ID (set when user leaves step 1)
    savedWorkflowId: null
  });
  
  // Available data sources
  const [availableSources, setAvailableSources] = useState([]);
  const [mappingTemplates, setMappingTemplates] = useState([]);
  
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

  // Derived loading helpers
  const anyLoading = Object.values(opLoading).some(Boolean);
  const loadingMessage = opLoading.discovery ? 'Running discovery analysis...'
    : opLoading.suggestions ? 'Generating mapping suggestions...'
    : opLoading.validation ? 'Running validation checks...'
    : opLoading.execute ? 'Executing migration pipeline...'
    : 'Processing...';

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

  // Load data from Data Workbench (via localStorage)
  const loadWorkbenchData = useCallback(() => {
    try {
      const stored = localStorage.getItem('workbench_migration_data');
      if (!stored) return;
      
      const workbenchData = JSON.parse(stored);
      if (!workbenchData || typeof workbenchData !== 'object') return;
      const { schema, timestamp } = workbenchData;
      if (!schema || !timestamp) return;
      
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
  // useCallback stable: only uses React state setters which are guaranteed stable.
  }, []);

  const loadDataSources = useCallback(async () => {
    try {
      const response = await e2etraceFetchWithRetry(API_CONFIG.ENDPOINTS.DATA_SOURCES);
      const sources = await response.json();
      // Show all sources that are configured in Admin Settings (even if not currently connected).
      // This keeps the wizard usable for end-users who must select from the configured catalog.
      setAvailableSources(Array.isArray(sources) ? sources : []);
    } catch (error) {
      console.error('Error loading data sources:', error);
      setAvailableSources([]);
    }
  // useCallback stable: only uses React state setters which are guaranteed stable.
  }, []);

  const loadMappingTemplates = useCallback(async () => {
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
  // useCallback stable: only uses React state setters which are guaranteed stable.
  }, []);

  // Load initial data — placed after all three useCallback refs are initialised
  // to avoid the temporal dead zone (TDZ) for const declarations.
  useEffect(() => {
    // Guard against double-fire in React StrictMode or HMR
    if (initialLoadRef.current) return;
    initialLoadRef.current = true;

    loadDataSources();
    loadMappingTemplates();

    // Run health checks once on mount (avoid polling spam)
    graphRAGHealth.checkHealth().catch(() => {});
    agenticSystem.checkStatus().catch(() => {});

    // Check for pre-loaded data from Data Workbench
    const source = searchParams.get('source');
    if (source === 'workbench') {
      loadWorkbenchData();
    }
  // Only run once on mount - don't re-run when searchParams changes
  // eslint-disable-next-line react-hooks/exhaustive-deps -- stable method refs via hooks
  }, []);

  // URL-based step navigation - Read step from URL on mount
  useEffect(() => {
    const stepParam = searchParams.get('step');
    if (stepParam && !isNaN(stepParam)) {
      const step = parseInt(stepParam, 10);
      if (step >= 1 && step <= 5 && step !== currentStep) {
        setCurrentStep(step);
      }
    }
  // Only run on mount or when URL changes
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  // URL-based step navigation - Update URL when step changes (PREVENT CIRCULAR DEPENDENCY)
  useEffect(() => {
    if (!embedded && currentStep) {
      const currentStepParam = searchParams.get('step');
      const stepString = currentStep.toString();
      
      // Only update if step parameter is different to avoid unnecessary navigation
      if (currentStepParam !== stepString) {
        // Preserve all existing query parameters (e.g., source=workbench)
        const newParams = new URLSearchParams(searchParams);
        newParams.set('step', stepString);
        setSearchParams(newParams, { replace: true });
      }
    }
  // Remove searchParams from deps to prevent circular updates with line 294 useEffect
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentStep, embedded, setSearchParams]);

  // Persist migration progress to localStorage for "Resume Migration" feature
  useEffect(() => {
    // Only persist if there's meaningful progress (beyond step 1)
    if (currentStep > 1 || wizardData.sourceSystem || wizardData.targetSystem) {
      const migrationProgress = {
        step: currentStep,
        workflowName: wizardData.workflowName,
        sourceSystem: wizardData.sourceSystem?.name || null,
        targetSystem: wizardData.targetSystem?.name || null,
        stepStatus,
        timestamp: new Date().toISOString(),
      };
      localStorage.setItem('migration_in_progress', JSON.stringify(migrationProgress));
    }
  }, [currentStep, wizardData.workflowName, wizardData.sourceSystem, wizardData.targetSystem, stepStatus]);

  // Step navigation
  const canProceed = useCallback((step) => {
    switch (step) {
      case 1: return wizardData.workflowName.trim().length > 0 && wizardData.sourceSystem && wizardData.targetSystem;
      case 2: return wizardData.discoveryAccepted;
      case 3: return wizardData.fieldMappings.length > 0;
      case 4: return wizardData.validationRun && (wizardData.validationResults.length > 0 || wizardData.qualityChecks.passed > 0);
      case 5: return true;
      default: return false;
    }
  }, [wizardData]);

  const nextStep = useCallback(async () => {
    if (currentStep < 5 && canProceed(currentStep)) {
      // Persist a workflow instance when the user leaves step 1 for the first time
      if (currentStep === 1 && !wizardData.savedWorkflowId) {
        try {
          const src = wizardData.sourceSystem;
          const tgt = wizardData.targetSystem;
          const payload = {
            name: wizardData.workflowName.trim(),
            description: `Migration from ${src.name} to ${tgt.name}`,
            source: { id: String(src.id), name: src.name, type: src.source_type || src.type || 'unknown', connection_details: { path: src.path || src.connection_string || '' } },
            target: { id: String(tgt.id), name: tgt.name, type: tgt.source_type || tgt.type || 'unknown', connection_details: { path: tgt.path || tgt.connection_string || '' } },
            workflow_config: { nodes: [], edges: [] }
          };
          const res = await e2etraceFetchWithRetry(API_CONFIG.ENDPOINTS.WORKFLOWS + '/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          });
          if (res.ok) {
            const wf = await res.json();
            setWizardData(prev => ({ ...prev, savedWorkflowId: wf.id }));
          }
        } catch (_e) {
          // Non-fatal: wizard continues even if persistence fails
        }
      }
      setStepStatus(prev => ({
        ...prev,
        [currentStep]: { complete: true, valid: true }
      }));
      setCurrentStep(prev => prev + 1);
    }
  }, [currentStep, canProceed, wizardData]);

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

    setOpLoading(prev => ({ ...prev, discovery: true }));
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

      const _findKey = (keys, candidates) => {
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

      // Submit Discovery Task to Agentic Backend
      // The ETL Orchestrator Agent will handle schema inference, mapping, transformation, and SODA validation.
      let sodaResult = null;
      let issues = [];
      let recommendations = [];
      let inferredSourceSchema = null;
      let aiSuggestedMappings = [];
      let inferredSourceFields = [];
      let agentTaskSucceeded = false;

      try {
        // Use the dedicated discovery endpoint which routes to DataDiscoveryAgent via MCP
        const agentResponse = await e2etraceFetchWithRetry(`${API_CONFIG?.API_BASE_URL || ''}/api/agentic/task`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
             type: "data_discovery",
             required_capabilities: ["perform_data_discovery", "discover_files"],
             payload: {
               type: "discovery",
               run_id: discoveryRunId,
               records: stagedRecords,
               source_system: wizardData.sourceSystem?.name
             }
          })
        });

        const taskResult = await agentResponse.json();
        
        if (taskResult.success && taskResult.result) {
           const res = taskResult.result;
           agentTaskSucceeded = true;
           sodaResult = res.quality_scan;
           
           // Extract inferred schema
           if (res.inferred_schema) {
              inferredSourceFields = Object.keys(res.inferred_schema);
              inferredSourceSchema = { 
                fields: inferredSourceFields.map(name => ({
                  name, 
                  type: res.inferred_schema[name]
                }))
              };
           }

           // Extract mappings
           if (res.applied_mapping) {
              aiSuggestedMappings = Object.entries(res.applied_mapping).map(([src, target]) => ({
                  sourceField: src,
                  targetField: target,
                  transformation: null,
                  confidence: 'High (Agent)'
              }));
           }
        } else {
             console.warn("Agent task completed but returned no result or failed:", taskResult);
        }

      } catch (agentError) {
         console.warn("Agentic discovery failed, falling back to legacy happy path...", agentError);
         // Fallback logic could go here, but for now we warn and proceed partial
      }

      // Legacy SODA — skip if agentic discovery already supplied quality data (avoids duplicate requests)
      if (!agentTaskSucceeded) try {
        // Run the staged-data DQ scan (internal completeness check, no Soda Core required)
        const sodaResponse = await e2etraceFetchWithRetry(`${plmBaseUrl}/runs/${discoveryRunId}/dq/scan`,

          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ stage: 'staged' })
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
        console.warn('Discovery DQ scan unavailable:', sodaError?.message || sodaError);
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

      // If Agent didn't provide schema, infer from first record
      if (inferredSourceFields.length === 0) {
          const first = Array.isArray(stagedRecords) && stagedRecords.length > 0 ? stagedRecords[0] : null;
          const keys = first && typeof first === 'object' && !Array.isArray(first) ? Object.keys(first) : [];
          inferredSourceFields = keys;
      }

      // Seed mapping suggestions: prefer Agent output, then identity-map real source
      // fields, and only fall back to PLM defaults when no real schema is available.
      const defaultMappingSuggestions = aiSuggestedMappings.length > 0
        ? aiSuggestedMappings
        : inferredSourceFields.length > 0
          ? inferredSourceFields.map(f => ({ sourceField: f, targetField: f, transformation: null, confidence: '70%' }))
          : [
              { sourceField: 'part_number', targetField: 'part_number', transformation: null, confidence: '90%' },
              { sourceField: 'name', targetField: 'name', transformation: 'TRIM', confidence: '90%' },
              { sourceField: 'category', targetField: 'classification', transformation: null, confidence: '85%' },
              { sourceField: 'revision', targetField: 'description', transformation: null, confidence: '70%' }
            ];

      // Use actual source fields as the canonical target schema when no Agent output is available.
      const canonicalTargetFields = inferredSourceFields.length > 0
        ? inferredSourceFields
        : ['part_number', 'name', 'classification', 'description'];
      
      const finalSourceSchema = inferredSourceSchema || (inferredSourceFields.length > 0
        ? { fields: inferredSourceFields.map((name) => ({ name })) }
        : null);
      
      const finalTargetSchema = { fields: canonicalTargetFields.map((name) => ({ name })) };

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
        sourceSchema: finalSourceSchema,
        targetSchema: finalTargetSchema,
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
      setOpLoading(prev => ({ ...prev, discovery: false }));
    }
  }, [wizardData.sourceSystem, wizardData.targetSystem]);

  const acceptDiscovery = useCallback(() => {
    setWizardData(prev => ({
      ...prev,
      discoveryAccepted: true
    }));
    
    // Show success confirmation toast
    const fieldsDetected = wizardData.discoveryIntrospect?.inferred_fields?.length || 
                          extractSchemaFields(wizardData.sourceSchema).length || 0;
    const qualityScore = wizardData.discoveryIntrospect?.soda_result?.score_pct || 
                        wizardData.discoveryIntrospect?.quality_score || null;
    const suggestionCount = wizardData.discoveryIntrospect?.suggested_mappings?.length || 0;
    
    let message = '✅ Discovery Accepted!';
    const details = [];
    if (fieldsDetected > 0) details.push(`${fieldsDetected} fields discovered`);
    if (qualityScore !== null) details.push(`Quality: ${qualityScore}%`);
    if (suggestionCount > 0) details.push(`${suggestionCount} AI suggestions ready`);
    
    if (details.length > 0) {
      message += '\n' + details.join(' • ');
    }
    message += '\nReady to proceed to field mapping.';
    
    toast.success(message, 6000);
  }, [wizardData.discoveryIntrospect, wizardData.sourceSchema]);

  // Step 3: AI-powered mapping suggestions via schema analysis.
  // Uses reliable schema-based smart matching that returns the correct
  // {sourceField, targetField, transformation, confidence} shape required by the UI.
  // Falls back to discoveryIntrospect fields when schemas are not yet loaded.
  const getAIMappingSuggestions = useCallback(async () => {
    setOpLoading(prev => ({ ...prev, suggestions: true }));
    try {
      // Merge schema fields with any fields inferred during Discovery (Step 2)
      const sourceFields = [
        ...extractSchemaFields(wizardData.sourceSchema),
        ...(wizardData.discoveryIntrospect?.inferred_source_fields || [])
      ].filter((v, i, a) => v && a.indexOf(v) === i);  // dedupe + remove empty

      const targetFields = extractSchemaFields(wizardData.targetSchema);

      if (sourceFields.length === 0) {
        // No schema loaded (discovery was skipped or failed).
        // If we already have suggestions from a prior run, just surface them.
        if (wizardData.aiSuggestedMappings?.length > 0) {
          toast.success(`Using ${wizardData.aiSuggestedMappings.length} mapping suggestions from Discovery`, 3000);
          return;
        }
        // No schema and no prior suggestions — apply canonical PLM fallback so
        // the user gets something actionable without running Discovery.
        const fallbackSuggestions = [
          { sourceField: 'part_number', targetField: 'part_number', transformation: null, confidence: '90%' },
          { sourceField: 'name',        targetField: 'name',        transformation: 'TRIM', confidence: '90%' },
          { sourceField: 'description', targetField: 'description', transformation: null, confidence: '85%' },
          { sourceField: 'category',    targetField: 'classification', transformation: null, confidence: '80%' },
          { sourceField: 'revision',    targetField: 'revision',    transformation: null, confidence: '75%' }
        ];
        setWizardData(prev => ({ ...prev, aiSuggestedMappings: fallbackSuggestions }));
        toast.info('Showing default PLM field suggestions — run Discovery for schema-matched results', 4000);
        return;
      }

      const suggestions = sourceFields.map(sourceField => {
        const lf = sourceField.toLowerCase();
        const exactMatch = targetFields.find(t => t.toLowerCase() === lf);
        const partialMatch = targetFields.find(t =>
          t.toLowerCase().includes(lf) || lf.includes(t.toLowerCase())
        );
        const targetField = exactMatch || partialMatch || sourceField;

        let transformation = null;
        if (lf.includes('date') || lf.includes('time')) transformation = 'TIMESTAMP';
        else if (lf.includes('amount') || lf.includes('price') || lf.includes('qty') || lf.includes('quantity')) transformation = 'NUMBER';
        else if (lf.includes('name') || lf.includes('label') || lf.includes('title')) transformation = 'TRIM';

        return {
          sourceField,
          targetField,
          transformation,
          confidence: exactMatch ? '95%' : partialMatch ? '75%' : '50%'
        };
      });

      setWizardData(prev => ({ ...prev, aiSuggestedMappings: suggestions }));
    } catch (error) {
      console.error('AI suggestions failed:', error);
      // Canonical fallback when schemas cannot be parsed
      const fallbackSuggestions = [
        { sourceField: 'part_number', targetField: 'part_number', transformation: null, confidence: '90%' },
        { sourceField: 'name', targetField: 'name', transformation: 'TRIM', confidence: '90%' },
        { sourceField: 'description', targetField: 'description', transformation: null, confidence: '85%' },
        { sourceField: 'category', targetField: 'classification', transformation: null, confidence: '80%' }
      ];
      setWizardData(prev => ({ ...prev, aiSuggestedMappings: fallbackSuggestions }));
    } finally {
      setOpLoading(prev => ({ ...prev, suggestions: false }));
    }
  }, [wizardData.sourceSchema, wizardData.targetSchema, wizardData.aiSuggestedMappings, wizardData.discoveryIntrospect]);
  
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

  // ── Rule Engine CRUD ──────────────────────────────────────────────────────
  const addRule = useCallback((phase) => {
    const id = `rule_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
    setWizardData(prev => ({
      ...prev,
      rules: [...prev.rules, { id, phase, name: '', field: '*', condition: '', condition_value: '', action: '', action_value: '', enabled: true }]
    }));
  }, []);

  const removeRule = useCallback((id) => {
    setWizardData(prev => ({ ...prev, rules: prev.rules.filter(r => r.id !== id) }));
  }, []);

  const updateRule = useCallback((id, patch) => {
    setWizardData(prev => ({
      ...prev,
      rules: prev.rules.map(r => r.id === id ? { ...r, ...patch } : r)
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
    setOpLoading(prev => ({ ...prev, validation: true }));
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
        qualityChecks: { passed, failed, warnings },
        validationRun: true
      }));
    } catch (error) {
      console.error('Validation failed:', error);
      setWizardData(prev => ({
        ...prev,
        validationResults: [{ id: 0, insight: 'Validation service unavailable', severity: 'warning' }],
        qualityChecks: { passed: 0, failed: 0, warnings: 1 },
        validationRun: true
      }));
    } finally {
      setOpLoading(prev => ({ ...prev, validation: false }));
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
    
    setOpLoading(prev => ({ ...prev, validation: true }));
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
        sodaScanResult: sodaResult,
        validationRun: true
      }));
    } catch (error) {
      console.error('SODA scan failed:', error);
      setWizardData(prev => ({
        ...prev,
        validationResults: [...prev.validationResults, { id: Date.now(), insight: 'SODA scan unavailable - Soda Core may not be installed', severity: 'warning' }]
      }));
    } finally {
      setOpLoading(prev => ({ ...prev, validation: false }));
    }
  }, [wizardData.runId]);

  const testTransformation = useCallback(async () => {
    if (!wizardData.fieldMappings.length) return;

    setOpLoading(prev => ({ ...prev, validation: true }));
    try {
      const result = await graphqlTransform.transform(
        { sample: true, source: wizardData.sourceSchema },
        { target: wizardData.targetSchema },
        wizardData.fieldMappings
      );
      // Show transform result as a validation insight
      setWizardData(prev => ({
        ...prev,
        validationResults: [
          ...prev.validationResults.filter(v => !v.insight?.includes('Transform')),
          {
            id: Date.now(),
            insight: `Transform test ${result ? 'succeeded' : 'returned no data'}`,
            severity: result ? 'success' : 'warning',
            recommendation: result ? 'Field transformations are working correctly' : 'Check transformation rules'
          }
        ],
        validationRun: true
      }));
    } catch (error) {
      console.error('Transformation test failed:', error);
      setWizardData(prev => ({
        ...prev,
        validationResults: [
          ...prev.validationResults.filter(v => !v.insight?.includes('Transform')),
          { id: Date.now(), insight: `Transform test failed: ${error?.message || 'Unknown error'}`, severity: 'error' }
        ],
        validationRun: true
      }));
    } finally {
      setOpLoading(prev => ({ ...prev, validation: false }));
    }
  }, [wizardData, graphqlTransform]);

  // Step 5: Execute migration - Complete 5-step workflow
  const executeMigration = useCallback(async () => {
    setOpLoading(prev => ({ ...prev, execute: true }));
    setWizardData(prev => ({ ...prev, migrationStatus: 'running', migrationStep: 'creating' }));
    
    try {
      const plmBaseUrl = `${API_CONFIG?.API_BASE_URL || ''}/api/plm/etl`;
      
      // STEP 1: Create migration run
      setWizardData(prev => ({ ...prev, migrationStep: 'Step 1: Creating run...' }));
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
      
      setWizardData(prev => ({ ...prev, runId, processedRecords: 1, totalRecords: 5 }));
      
      // STEP 2: Stage records (extract from source)
      setWizardData(prev => ({ ...prev, migrationStep: 'Step 2: Extracting records from source...', processedRecords: 2 }));
      
      // Extract REAL records from the configured source via /api/data-sources/{id}/sample
      // Strict policy: NO mock/sample/demo data (matches backend policy)
      const sourceId = wizardData.sourceSystem?.id;
      if (!sourceId) {
        throw new Error('No source system selected. Please complete Step 1 (Connect) first.');
      }

      let records = [];
      try {
        const sampleUrl = `${API_CONFIG?.API_BASE_URL || ''}/api/data-sources/${encodeURIComponent(sourceId)}/sample?limit=500`;
        const sampleResponse = await e2etraceFetchWithRetry(sampleUrl, { method: 'GET' });
        if (!sampleResponse.ok) {
          throw new Error(`Failed to extract records (HTTP ${sampleResponse.status}). Verify the source connection in Admin Settings.`);
        }
        const samplePayload = await sampleResponse.json();
        records = Array.isArray(samplePayload?.records) ? samplePayload.records : [];
      } catch (extractError) {
        throw new Error(`Source extraction failed: ${extractError.message}`);
      }

      if (records.length === 0) {
        throw new Error('Source returned no records. Verify the source contains data and the connection is valid.');
      }

      setWizardData(prev => ({ ...prev, totalRecords: records.length }));
      
      await e2etraceFetchWithRetry(`${plmBaseUrl}/runs/${runId}/stage`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          object_type: 'Part',
          records: records
        })
      });

      // STEP 3: Transform using field mappings
      setWizardData(prev => ({ ...prev, migrationStep: 'Step 3: Transforming data...', processedRecords: 3 }));
      
      // Build part_mapping from user-defined fieldMappings (Step 3)
      // Strict policy: NO hardcoded fallback mappings
      const partMapping = wizardData.fieldMappings.reduce((acc, m) => {
        const src = (m?.source_field || '').trim();
        const dest = (m?.target_field || '').trim();
        if (src && dest) acc[src] = dest;
        return acc;
      }, {});
      
      if (Object.keys(partMapping).length === 0) {
        throw new Error('No field mappings defined. Please complete Step 3 (Map) and define at least one field mapping.');
      }
      
      const transformResponse = await e2etraceFetchWithRetry(`${plmBaseUrl}/runs/${runId}/transform`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ part_mapping: partMapping })
      });
      const transformResult = await transformResponse.json();
      const transformedCount = transformResult?.transformed_count ?? 0;

      if (transformedCount === 0) {
        // Identify which source fields are mapped so user can diagnose
        const mappedSources = Object.keys(partMapping).join(', ');
        throw new Error(
          `Transform produced 0 records. The backend requires a "part_number" field — none of your mapped source fields (${mappedSources || 'none'}) resolved to a non-empty part_number. ` +
          'In Step 3 (Map), add a mapping whose source field contains the part identifier (e.g. source "part_number" → target "part_number").'
        );
      }
      
      // STEP 4a: SODA Data Quality Scan
      setWizardData(prev => ({ ...prev, migrationStep: 'Step 4a: Running SODA quality scan...', processedRecords: 3.5 }));
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
      
      // STEP 4b: Validate
      setWizardData(prev => ({ ...prev, migrationStep: 'Step 4b: Validating data...', processedRecords: 4 }));
      try {
        await e2etraceFetchWithRetry(`${plmBaseUrl}/runs/${runId}/validate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({})
        });
      } catch (validateError) {
        // Validate is a quality step — log the warning but don't block migration
        console.warn('Validate step returned an error (non-fatal, migration continues):', validateError.message);
      }
      
      // STEP 5: Sync to Neo4j (use direct sync for dev environments)
      setWizardData(prev => ({ ...prev, migrationStep: 'Step 5: Syncing to Neo4j...', processedRecords: 4.5 }));
      let syncResult = null;
      try {
        const syncResponse = await e2etraceFetchWithRetry(`${plmBaseUrl}/runs/${runId}/sync/neo4j/direct`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' }
        });
        syncResult = await syncResponse.json();
      } catch (syncError) {
        console.warn('Direct Neo4j sync skipped (Neo4j may not be configured):', syncError.message);
      }
      
      setWizardData(prev => ({
        ...prev,
        migrationStatus: 'completed',
        migrationStep: 'Complete!',
        processedRecords: syncResult?.parts_synced || records.length,
        totalRecords: syncResult?.parts_synced || records.length,
        nodesCreated: syncResult?.nodes_created || 0
      }));
      
      setStepStatus(prev => ({
        ...prev,
        5: { complete: true, valid: true }
      }));
      
      // Clear migration progress from localStorage on successful completion
      localStorage.removeItem('migration_in_progress');
      
      if (onComplete) onComplete({ runId, syncResult });
      
    } catch (error) {
      console.error('Migration failed:', error);
      setWizardData(prev => ({
        ...prev,
        migrationStatus: 'failed',
        migrationStep: 'Failed',
        errors: [...prev.errors, error.message]
      }));
    } finally {
      setOpLoading(prev => ({ ...prev, execute: false }));
    }
  }, [wizardData, onComplete]);

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
          
          {availableSources.length === 0 ? (
            <div className="no-sources">
              <p>No connected data sources available.</p>
              <p className="no-sources-hint">
                Ask an administrator to configure connections in Admin Settings, then return here.
              </p>
            </div>
          ) : (
            <div className="source-dropdown-wrap">
              <div className="source-select-row">
                <i className={`fas ${getSourceIcon(wizardData.sourceSystem?.type)} source-select-icon`} />
                <select
                  className="source-select"
                  value={wizardData.sourceSystem?.id || ''}
                  onChange={e => {
                    const s = availableSources.find(x => x.id === e.target.value);
                    if (s) selectSource('source', s);
                  }}
                >
                  <option value="">— Select a source system —</option>
                  {availableSources.map(source => (
                    <option key={source.id} value={source.id}>
                      {source.name}  ({source.type})  [{source.status || 'configured'}]
                    </option>
                  ))}
                </select>
              </div>
              {wizardData.sourceSystem && (
                <div className="source-selection-preview">
                  <div className="ssp-icon">
                    <i className={`fas ${getSourceIcon(wizardData.sourceSystem.type)}`} />
                  </div>
                  <div className="ssp-info">
                    <span className="ssp-name">{wizardData.sourceSystem.name}</span>
                    <span className="ssp-type">{wizardData.sourceSystem.type}</span>
                    {wizardData.sourceSystem.connection?.folder_path && (
                      <span className="ssp-path" title={wizardData.sourceSystem.connection.folder_path}>
                        {wizardData.sourceSystem.connection.folder_path}
                      </span>
                    )}
                    {wizardData.sourceSystem.description && !wizardData.sourceSystem.connection?.folder_path && (
                      <span className="ssp-path" title={wizardData.sourceSystem.description}>
                        {wizardData.sourceSystem.description}
                      </span>
                    )}
                  </div>
                  <span className={`ssp-status ${
                    wizardData.sourceSystem.status === 'active' || wizardData.sourceSystem.status === 'connected'
                      ? 'ssp-active' : 'ssp-inactive'
                  }`}>
                    <i className={`fas ${
                      wizardData.sourceSystem.status === 'active' || wizardData.sourceSystem.status === 'connected'
                        ? 'fa-check-circle' : 'fa-circle'
                    }`} /> {wizardData.sourceSystem.status || 'configured'}
                  </span>
                </div>
              )}
            </div>
          )}
        </div>
        
        <div className="flow-indicator">
          <i className="fas fa-long-arrow-alt-right" />
        </div>
        
        <div className="source-panel">
          <h4><i className="fas fa-bullseye" /> Target System</h4>
          <p>Where should the data go?</p>
          
          <div className="source-dropdown-wrap">
            <div className="source-select-row">
              <i className={`fas ${getSourceIcon(wizardData.targetSystem?.type)} source-select-icon`} />
              <select
                className="source-select"
                value={wizardData.targetSystem?.id || ''}
                onChange={e => {
                  const s = availableSources.find(x => x.id === e.target.value);
                  if (s && wizardData.sourceSystem?.id !== s.id) selectSource('target', s);
                }}
              >
                <option value="">— Select a target system —</option>
                {availableSources
                  .filter(s => s.id !== wizardData.sourceSystem?.id)
                  .map(source => (
                    <option key={source.id} value={source.id}>
                      {source.name}  ({source.type})  [{source.status || 'configured'}]
                    </option>
                  ))}
              </select>
            </div>
            {wizardData.targetSystem && (
              <div className="source-selection-preview">
                <div className="ssp-icon">
                  <i className={`fas ${getSourceIcon(wizardData.targetSystem.type)}`} />
                </div>
                <div className="ssp-info">
                  <span className="ssp-name">{wizardData.targetSystem.name}</span>
                  <span className="ssp-type">{wizardData.targetSystem.type}</span>
                  {wizardData.targetSystem.connection?.folder_path && (
                    <span className="ssp-path" title={wizardData.targetSystem.connection.folder_path}>
                      {wizardData.targetSystem.connection.folder_path}
                    </span>
                  )}
                  {wizardData.targetSystem.description && !wizardData.targetSystem.connection?.folder_path && (
                    <span className="ssp-path" title={wizardData.targetSystem.description}>
                      {wizardData.targetSystem.description}
                    </span>
                  )}
                </div>
                <span className={`ssp-status ${
                  wizardData.targetSystem.status === 'active' || wizardData.targetSystem.status === 'connected'
                    ? 'ssp-active' : 'ssp-inactive'
                }`}>
                  <i className={`fas ${
                    wizardData.targetSystem.status === 'active' || wizardData.targetSystem.status === 'connected'
                      ? 'fa-check-circle' : 'fa-circle'
                  }`} /> {wizardData.targetSystem.status || 'configured'}
                </span>
              </div>
            )}
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

      {/* Warning when source/target not selected */}
      {(!wizardData.sourceSystem || !wizardData.targetSystem) && (
        <div className="inline-alert warning" style={{ marginBottom: 16 }}>
          <i className="fas fa-exclamation-triangle" />
          <div>
            <strong>Source and target systems required</strong>
            <p>Go back to <strong>Step 1 (Connect)</strong> to select your source and target systems before running discovery.</p>
          </div>
        </div>
      )}

      <div className="discovery-actions">
        <div className="action-group">
          <span className="step-number">1</span>
          <button
            className="btn btn-primary"
            onClick={runDiscovery}
            disabled={!wizardData.sourceSystem || !wizardData.targetSystem || opLoading.discovery}
            title={!wizardData.sourceSystem || !wizardData.targetSystem ? 'Complete Step 1 first to select source and target systems' : 'Run discovery to analyze your data'}
          >
            {opLoading.discovery
              ? <><i className="fas fa-spinner fa-spin" /> Running Discovery...</>
              : <><i className="fas fa-search" /> Run Discovery</>}
          </button>
          <p className="action-help">Analyze data quality and generate AI mapping suggestions</p>
        </div>

        {wizardData.discoveryStatus === 'completed' && (
          <div className="action-group">
            <span className="step-number">2</span>
            <button
              className="btn btn-success"
              onClick={acceptDiscovery}
              disabled={wizardData.discoveryAccepted}
            >
              <i className="fas fa-check" /> {wizardData.discoveryAccepted ? 'Discovery Accepted ✓' : 'Accept & Continue'}
            </button>
            <p className="action-help">Review results above, then accept to proceed to field mapping</p>
          </div>
        )}
        {wizardData.discoveryStatus === 'failed' && !wizardData.discoveryAccepted && (
          <div className="action-group">
            <span className="step-number">2</span>
            <button
              className="btn btn-warning"
              onClick={acceptDiscovery}
            >
              <i className="fas fa-forward" /> Continue Without Discovery
            </button>
            <p className="action-help">Discovery failed — you can still map fields manually or use a template in the next step</p>
          </div>
        )}
      </div>

      {wizardData.discoveryRunId && (
        <div className="discovery-meta">
          Discovery run: <strong>{wizardData.discoveryRunId}</strong>
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

      {/* ── Inferred source fields ─────────────────────────── */}
      {wizardData.discoveryIntrospect?.inferred_source_fields?.length > 0 && (
        <div className="discovery-data-panel">
          <div className="ddp-header">
            <i className="fas fa-columns" /> Inferred Source Fields
            <span className="ddp-badge">{wizardData.discoveryIntrospect.inferred_source_fields.length} fields</span>
          </div>
          <div className="ddp-chips">
            {wizardData.discoveryIntrospect.inferred_source_fields.map((f) => (
              <span key={f} className="ddp-chip">{f}</span>
            ))}
          </div>
        </div>
      )}

      {/* ── Sample records ─────────────────────────────────── */}
      {(() => {
        const sampleRows = Array.isArray(wizardData.discoverySample?.records)
          ? wizardData.discoverySample.records.slice(0, 5)
          : null;
        if (!sampleRows || sampleRows.length === 0) return null;
        const cols = Object.keys(sampleRows[0]);
        return (
          <div className="discovery-data-panel">
            <div className="ddp-header">
              <i className="fas fa-table" /> Sample Records
              <span className="ddp-badge">{sampleRows.length} of {wizardData.discoverySample.records.length}</span>
              <span className="ddp-source-tag">
                {wizardData.discoverySample.stagedFrom === 'source' ? 'live source' : 'synthetic'}
              </span>
            </div>
            <div className="ddp-table-wrap">
              <table className="ddp-table">
                <thead>
                  <tr>{cols.map((c) => <th key={c}>{c}</th>)}</tr>
                </thead>
                <tbody>
                  {sampleRows.map((row, i) => (
                    <tr key={i}>
                      {cols.map((c) => (
                        <td key={c} title={String(row[c] ?? '')}>
                          {String(row[c] ?? '—').substring(0, 40)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        );
      })()}

      {/* ── Mapping hints ──────────────────────────────────── */}
      {wizardData.discoveryStatus === 'completed' && wizardData.aiSuggestedMappings?.length > 0 && (
        <div className="discovery-data-panel">
          <div className="ddp-header">
            <i className="fas fa-random" /> Mapping Hints
            <span className="ddp-badge">{wizardData.aiSuggestedMappings.length} suggestions</span>
            <span className="ddp-note">Carry over to Step 3</span>
          </div>
          <div className="ddp-mappings">
            {wizardData.aiSuggestedMappings.map((m, i) => (
              <div key={i} className="ddp-mapping-row">
                <span className="ddp-src-field">{m.sourceField}</span>
                <span className="ddp-arrow"><i className="fas fa-arrow-right" /></span>
                <span className="ddp-tgt-field">{m.targetField}</span>
                {m.transformation && <span className="ddp-transform">{m.transformation}</span>}
                {m.confidence && <span className="ddp-confidence">{m.confidence}</span>}
              </div>
            ))}
          </div>
          <div className="ddp-footer-link">
            <a href="#/data-discovery" target="_blank" rel="noreferrer">
              <i className="fas fa-external-link-alt" /> View full discovery catalogue
            </a>
          </div>
        </div>
      )}
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
        <div className="discovery-summary-card" style={{ marginBottom: 24 }}>
          <div className="summary-header">
            <i className="fas fa-microscope" /> Discovery Results Summary
            {wizardData.discoveryRunId && (
              <span className="run-badge" title={`Discovery Run ID: ${wizardData.discoveryRunId}`}>
                <i className="fas fa-fingerprint" /> {wizardData.discoveryRunId.slice(0, 8)}...
              </span>
            )}
          </div>
          
          {wizardData.discoveryInsights?.length > 0 && (
            <div className="discovery-insights" style={{ marginBottom: 16 }}>
              {wizardData.discoveryInsights.slice(0, 3).map((insight) => (
                <div key={insight.id} className={`discovery-insight ${insight.severity || 'info'}`}>
                  <div className="discovery-insight-title">{insight.title}</div>
                  <div className="discovery-insight-detail">{insight.detail}</div>
                </div>
              ))}
            </div>
          )}
          
          <div className="summary-metrics">
            <div className="metric">
              <span className="metric-value">
                {wizardData.discoveryIntrospect?.inferred_fields?.length || 
                 wizardData.discoveryIntrospect?.fields_detected || 
                 extractSchemaFields(wizardData.sourceSchema).length || 0}
              </span>
              <span className="metric-label">Fields Detected</span>
            </div>
            <div className="metric">
              <span className="metric-value">
                {wizardData.discoveryIntrospect?.soda_result?.score_pct || 
                 wizardData.discoveryIntrospect?.quality_score || '—'}
                {(wizardData.discoveryIntrospect?.soda_result?.score_pct || 
                  wizardData.discoveryIntrospect?.quality_score) && '%'}
              </span>
              <span className="metric-label">Quality Score</span>
            </div>
            <div className="metric">
              <span className="metric-value">
                {wizardData.discoveryIntrospect?.suggested_mappings?.length ||
                 wizardData.aiSuggestedMappings?.length || 0}
              </span>
              <span className="metric-label">AI Suggestions</span>
            </div>
            {wizardData.discoverySample?.records && (
              <div className="metric">
                <span className="metric-value">
                  {Array.isArray(wizardData.discoverySample.records) 
                    ? wizardData.discoverySample.records.length 
                    : 0}
                </span>
                <span className="metric-label">Sample Records</span>
              </div>
            )}
          </div>
          
          <div className="summary-actions">
            <a href="#/data-discovery" className="view-details-link" target="_blank" rel="noopener noreferrer">
              <i className="fas fa-external-link-alt" /> View Full Discovery Report
            </a>
            
            {/* Developer debug panel - only shown in development */}
            {import.meta.env.DEV && (
              <details className="debug-panel" style={{ marginTop: 12 }}>
                <summary style={{ cursor: 'pointer', color: '#999', fontSize: '0.85em' }}>
                  🛠️ Developer Debug Info
                </summary>
                <div style={{ marginTop: 8 }}>
                  <div style={{ marginBottom: 8 }}>
                    <strong>Discovery Introspect:</strong>
                    <pre className="schema-preview" style={{ fontSize: '0.75em' }}>
                      {JSON.stringify(wizardData.discoveryIntrospect, null, 2)}
                    </pre>
                  </div>
                  {wizardData.discoverySample && (
                    <div>
                      <strong>Sample Data (first 8 records):</strong>
                      <pre className="schema-preview" style={{ fontSize: '0.75em' }}>
                        {JSON.stringify(
                          Array.isArray(wizardData.discoverySample.records)
                            ? wizardData.discoverySample.records.slice(0, 8)
                            : wizardData.discoverySample,
                          null,
                          2
                        )}
                      </pre>
                    </div>
                  )}
                </div>
              </details>
            )}
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
      
      {/* Mapping Workflow Guide - UX Enhancement */}
      <div className="mapping-workflow-guide">
        <h4><i className="fas fa-map-signs" /> How to Create Field Mappings</h4>
        <p className="guide-intro">Choose the method that best fits your workflow:</p>
        
        <div className="workflow-methods">
          <div className="workflow-method recommended">
            <span className="method-badge recommended">
              <i className="fas fa-star" /> Recommended
            </span>
            <div className="method-content">
              <div className="method-header">
                <i className="fas fa-magic" />
                <h5>1. AI-Powered Suggestions</h5>
              </div>
              <p>Let AI analyze your schemas and suggest intelligent field mappings based on field names, types, and patterns.</p>
              <button 
                className="btn btn-primary btn-sm btn-ai"
                onClick={getAIMappingSuggestions}
                disabled={opLoading.suggestions}
                title="Get AI-powered field mapping suggestions"
              >
                {opLoading.suggestions
                  ? <><i className="fas fa-spinner fa-spin" /> Analyzing...</>
                  : <><i className="fas fa-magic" /> Get AI Suggestions</>}
              </button>
            </div>
          </div>
          
          <div className="workflow-method">
            <div className="method-content">
              <div className="method-header">
                <i className="fas fa-file-alt" />
                <h5>2. Use a Template</h5>
              </div>
              <p>Apply pre-configured mappings for common migration scenarios (e.g., Teamcenter to SAP, Excel to Database).</p>
              <div className="template-selector-inline">
                <select 
                  value={wizardData.selectedTemplate?.id || ''}
                  onChange={(e) => {
                    const template = mappingTemplates.find(t => t.id === e.target.value);
                    if (template) {
                      applyTemplate(template);
                      toast.success(`Template "${template.name}" applied successfully!`, 4000);
                    }
                  }}
                  className="form-control form-control-sm"
                >
                  <option value="">Select a template...</option>
                  {mappingTemplates.map(t => (
                    <option key={t.id} value={t.id}>{t.name}</option>
                  ))}
                </select>
              </div>
            </div>
          </div>
          
          <div className="workflow-method">
            <div className="method-content">
              <div className="method-header">
                <i className="fas fa-hand-pointer" />
                <h5>3. Manual Mapping</h5>
              </div>
              <p>Click field tags below or use the mappings table to manually define each field relationship.</p>
              <div className="manual-mapping-hints">
                <span className="hint">
                  <i className="fas fa-lightbulb" /> <strong>Tip:</strong> Click source field tags to quickly add mappings
                </span>
              </div>
              <button
                className="btn btn-secondary btn-sm"
                style={{ marginTop: 8 }}
                onClick={() => addFieldMapping({ source_field: '', target_field: '', transformation: null })}
              >
                <i className="fas fa-plus" /> Add Mapping Row
              </button>
            </div>
          </div>
        </div>
      </div>
      
      {/* Legacy mapping tools section removed — superseded by workflow guide above */}
      
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
                wizardData.aiSuggestedMappings.filter(s => s.sourceField).forEach(s => addFieldMapping({
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
            {wizardData.aiSuggestedMappings.filter(s => s.sourceField).map((suggestion, idx) => {
              const conf = suggestion.confidence;
              // conf may be a string like "95%" or a decimal like 0.95 — normalise to 0–100
              const confRaw = typeof conf === 'number' ? conf : parseFloat(conf);
              const confNum = !isNaN(confRaw)
                ? (confRaw <= 1 ? confRaw * 100 : confRaw)   // 0.95 → 95, 95 → 95
                : NaN;
              const confClass = !isNaN(confNum)
                ? confNum >= 75 ? 'high' : confNum >= 50 ? 'medium' : 'low'
                : 'low';
              const confLabel = !isNaN(confNum) ? `${Math.round(confNum)}%` : (conf || 'N/A');
              return (
                <div key={idx} className="suggestion-item">
                  <span className="mapping-arrow">{suggestion.sourceField} → {suggestion.targetField}</span>
                  {suggestion.transformation && <span className="transform-badge">{suggestion.transformation}</span>}
                  <span className={`confidence ${confClass}`}>{confLabel}</span>
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
              );
            })}
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

      {/* ── Rule Engine ────────────────────────────────────────────────── */}
      <WizardRuleEngine
        rules={wizardData.rules}
        activePhase={wizardData.activeRulePhase}
        sourceFields={extractSchemaFields(wizardData.sourceSchema)}
        onPhaseChange={phase => setWizardData(prev => ({ ...prev, activeRulePhase: phase }))}
        onAddRule={addRule}
        onRemoveRule={removeRule}
        onUpdateRule={updateRule}
      />
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
          disabled={opLoading.validation}
        >
          <i className="fas fa-check-double" /> {opLoading.validation ? 'Running...' : 'Run Validation'}
        </button>
        <button 
          className="btn btn-secondary"
          onClick={testTransformation}
          disabled={opLoading.validation || !wizardData.fieldMappings.length}
        >
          <i className="fas fa-exchange-alt" /> Test Transform
        </button>
        <button 
          className="btn btn-info"
          onClick={runSodaScan}
          disabled={opLoading.validation || !wizardData.runId}
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
            disabled={opLoading.execute || wizardData.qualityChecks.failed > 0}
          >
            <i className="fas fa-play" /> {opLoading.execute ? 'Running...' : 'Start Migration'}
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
              <i className="fas fa-shield-alt" /> Step 4: SODA Scan & Validate
            </div>
            <div className={`migration-step-item ${wizardData.processedRecords >= 5 ? 'complete' : wizardData.processedRecords >= 4 ? 'active' : ''}`}>
              <i className="fas fa-project-diagram" /> Step 5: Sync to Neo4j
            </div>
          </div>
          <div className="spinner">
            <i className="fas fa-spinner fa-spin" />
          </div>
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
      postgres: 'fa-database',
      neo4j: 'fa-project-diagram',
      opensearch: 'fa-search',
      redis: 'fa-memory',
      api: 'fa-plug',
      rest_api: 'fa-plug',
      odata: 'fa-exchange-alt',
      graphql: 'fa-code-branch',
      file: 'fa-file',
      local_folder: 'fa-folder-open',
      s3: 'fa-cloud',
      aws_s3: 'fa-cloud',
      azure_blob: 'fa-cloud-upload-alt',
      onedrive: 'fa-cloud',
      google_drive: 'fa-cloud',
      kafka: 'fa-stream',
      teamcenter: 'fa-cogs',
      '3dexperience': 'fa-cube',
      windchill: 'fa-wind',
      aras: 'fa-sitemap',
      codebeamer: 'fa-tasks',
      enovia: 'fa-cubes',
      powerquery: 'fa-table'
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
        {anyLoading && (
          <div className="loading-overlay">
            <i className="fas fa-spinner fa-spin" />
            <span><i className="fas fa-circle-notch fa-spin" style={{ marginRight: 8, opacity: 0.7 }} />{loadingMessage}</span>
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
