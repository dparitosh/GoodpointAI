import React, { useState, useCallback, useEffect, useMemo, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import writeXlsxFile from 'write-excel-file';
import { e2etraceFetchWithRetry } from '../../api/e2etrace-api';
import { API_CONFIG } from '../../config/api-config.js';
import { useGraphQLTransform } from '../../hooks/useGraphQL.js';
import { useAISuggestions, useGraphRAGHealth } from '../../hooks/useGraphRAG.js';
import { useAgenticSystemStatus } from '../../hooks/useAgenticAI.js';
import { toast } from '../../hooks/useToast';
import WizardRuleEngine from './WizardRuleEngine';
import SmartGuidancePanel from './SmartGuidancePanel';
import DiscoveryResults from './DiscoveryResults';
import DataHealthPanel from './DataHealthPanel';
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
      if (step >= 1 && step <= 6) {
        return step;
      }
    }
    return initialStep;
  };
  
  // Wizard state
  const [currentStep, setCurrentStep] = useState(getInitialStepFromURL);
  // Per-operation loading flags — prevents unrelated buttons from being disabled during an operation
  const [opLoading, setOpLoading] = useState({ discovery: false, suggestions: false, validation: false, execute: false });
  // Template browser panel expanded/collapsed in the Mapping step
  const [showTemplateBrowser, setShowTemplateBrowser] = useState(false);
  // Smart Guidance: dismissed by user or after an operation starts
  const [smartGuidanceDismissed, setSmartGuidanceDismissed] = useState(false);
  // Guard against double-firing the initial data load (React StrictMode / HMR)
  const initialLoadRef = useRef(false);
  // Synchronous in-flight guard for runDiscovery — prevents concurrent runs when
  // SmartGuidancePanel button and the main "Run Discovery" button both fire before
  // React's opLoading state update propagates.
  const discoveryInFlightRef = useRef(false);
  // Tracks the step we last wrote to the URL so the read effect skips it
  const urlWriteRef = useRef(false);
  // AbortController for the fire-and-forget semantic profiling fetch (prevents stale responses on unmount)
  const semProfileAbortRef = useRef(null);
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
    // Step 2: Semantic profiling (DataProfilerAgent — column semantics, entity classification)
    semanticProfile: null,         // { column_semantics, entity_classifications, ... } | null
    semanticProfileStatus: 'idle', // idle | running | completed | failed
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
    savedWorkflowId: null,
    // Name that was persisted (used to detect renames on step 1 revisit)
    savedWorkflowName: null,
    // Backend rule_set_id created when wizard rules are persisted in step 4
    savedRuleSetId: null,
    // Step 2: AI Data Health Report (DataDiscoveryAgent `data_health_report` task)
    dataHealthReport: null,
    dataHealthLoading: false,
    // Step 3: Profile — DataProfilerAgent
    profileStatus: 'idle',    // idle | running | completed | failed
    profileResult: null,
    profileError: null,
    profileAccepted: false,
    // Step 4: Quality — QualityMonitorAgent
    qualityStatus: 'idle',    // idle | running | completed | failed
    qualityResult: null,
    qualityError: null,
    qualityRun: false,
    qualityAccepted: false,
    // Step 5: ETL completion flag (set when executeMigration finishes)
    etlCompleted: false,
    // Step 6: Report — ReportingAgent
    agentReportStatus: 'idle', // idle | running | completed | failed
    agentReportResult: null,
    agentReportError: null,
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
    5: { complete: false, valid: false },
    6: { complete: false, valid: false }
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
    { id: 1, name: 'Connect',  icon: 'fa-plug',         description: 'Configure data sources' },
    { id: 2, name: 'Discover', icon: 'fa-search',        description: 'AI-driven discovery & schema' },
    { id: 3, name: 'Profile',  icon: 'fa-brain',         description: 'Semantic profiling & entity classification' },
    { id: 4, name: 'Quality',  icon: 'fa-shield-alt',    description: 'DQ rules, anomaly detection & scoring' },
    { id: 5, name: 'ETL',      icon: 'fa-exchange-alt',  description: 'Extract, transform, load via agent' },
    { id: 6, name: 'Report',   icon: 'fa-chart-bar',     description: 'AI-generated comprehensive report' },
  ], []);

  // Load data from Data Workbench (via localStorage)
  const loadWorkbenchData = useCallback(() => {
    try {
      const stored = localStorage.getItem('workbench_migration_data');
      if (!stored) return;

      // Guard against oversized payloads (10 MB max) before parsing.
      if (stored.length > 10 * 1024 * 1024) {
        localStorage.removeItem('workbench_migration_data');
        return;
      }

      let workbenchData;
      try {
        workbenchData = JSON.parse(stored);
      } catch {
        localStorage.removeItem('workbench_migration_data');
        return;
      }

      if (!workbenchData || typeof workbenchData !== 'object') return;
      const { schema, timestamp } = workbenchData;
      // Validate expected shape before using
      if (!schema || typeof schema !== 'object' || !timestamp || typeof timestamp !== 'string') return;
      
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

      if (import.meta.env.DEV) console.log('Loaded workbench data:', schema);
    } catch (error) {
      console.error('Error loading workbench data:', error);
    }
  // useCallback stable: only uses React state setters which are guaranteed stable.
  }, []);

  const loadDataSources = useCallback(async () => {
    try {
      const response = await e2etraceFetchWithRetry(API_CONFIG.ENDPOINTS.DATA_SOURCES);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const sources = await response.json();
      // Show all sources that are configured in Admin Settings (even if not currently connected).
      // This keeps the wizard usable for end-users who must select from the configured catalog.
      const list = Array.isArray(sources) ? sources : [];
      setAvailableSources(list);
      return list;
    } catch (error) {
      if (import.meta.env.DEV) console.error('Error loading data sources:', error);
      setAvailableSources([]);
      return [];
    }
  // useCallback stable: only uses React state setters which are guaranteed stable.
  }, []);

  const loadMappingTemplates = useCallback(async () => {
    try {
      const response = await e2etraceFetchWithRetry(API_CONFIG.ENDPOINTS.DATA_MAPPING_TEMPLATES);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
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

    const init = async () => {
      const sources = await loadDataSources();
      loadMappingTemplates();

      // Run health checks once on mount (avoid polling spam)
      graphRAGHealth.checkHealth().catch(() => {});
      agenticSystem.checkStatus().catch(() => {});

      // Check for pre-loaded data from Data Workbench
      const source = searchParams.get('source');
      if (source === 'workbench') {
        loadWorkbenchData();
        return;
      }

      // Resume an existing workflow: pre-populate wizard fields and restore saved step
      const resumeId = searchParams.get('resumeWorkflowId');
      if (resumeId) {
        try {
          const apiBase = import.meta.env.VITE_API_BASE_URL || '';
          const res = await e2etraceFetchWithRetry(`${apiBase}${API_CONFIG.ENDPOINTS.WORKFLOW_DETAILS(resumeId)}`);
          if (res.ok) {
            const wf = await res.json();
            const srcMatch = sources.find(s => s.id === wf.source_id) || null;
            const tgtMatch = sources.find(s => s.id === wf.target_id) || null;

            // If the saved workflow references a source/target that no longer
            // exists in the data-sources registry, do NOT fabricate a synthetic
            // entry — downstream sampling/test calls will 404 and confuse the
            // user. Surface a clear warning and force the user to re-select.
            const orphanSrc = !srcMatch && wf.source_id;
            const orphanTgt = !tgtMatch && wf.target_id;
            if (orphanSrc || orphanTgt) {
              const missing = [
                orphanSrc ? `source "${wf.source_name || wf.source_id}"` : null,
                orphanTgt ? `target "${wf.target_name || wf.target_id}"` : null,
              ].filter(Boolean).join(' and ');
              console.warn(`Resumed workflow references missing ${missing}. Please re-select in Step 1.`);
            }

            setWizardData(prev => ({
              ...prev,
              workflowName: wf.name || '',
              savedWorkflowId: wf.id,
              savedWorkflowName: wf.name || '',
              sourceSystem: srcMatch,
              targetSystem: tgtMatch,
            }));
            setStepStatus(prev => ({
              ...prev,
              1: { complete: !!(srcMatch && tgtMatch), valid: !!(srcMatch && tgtMatch) },
            }));
            // Restore the step the user was on when they navigated away (from localStorage),
            // falling back to step 2 (first step after a configured source/target).
            const savedProgress = (() => {
              try { return JSON.parse(localStorage.getItem('migration_in_progress') || 'null'); }
              catch { return null; }
            })();
            const targetStep = (savedProgress?.savedWorkflowId === resumeId && savedProgress?.step > 1)
              ? savedProgress.step
              : 2;
            setCurrentStep(targetStep);
          }
        } catch (e) {
          console.error('Failed to resume workflow:', e);
        }
      }
    };

    init();
  // Only run once on mount - don't re-run when searchParams changes
  // eslint-disable-next-line react-hooks/exhaustive-deps -- stable method refs via hooks
  }, []);

  // URL-based step navigation - Read step from URL on mount / external nav link clicks.
  // Use the PRIMITIVE step string as dependency (not the searchParams object) so this only
  // fires when the step value actually changes, not when searchParams object identity changes.
  const urlStepParam = searchParams.get('step');
  useEffect(() => {
    // Skip if the URL change was caused by our own write effect below
    if (urlWriteRef.current) {
      urlWriteRef.current = false;
      return;
    }
    if (urlStepParam && !isNaN(urlStepParam)) {
      const step = parseInt(urlStepParam, 10);
      if (step >= 1 && step <= 5 && step !== currentStep) {
        setCurrentStep(step);
      }
    }
  // urlStepParam is a primitive — avoids re-running on every searchParams object recreation
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [urlStepParam]);

  // URL-based step navigation - Keep URL in sync when step changes via buttons / code.
  useEffect(() => {
    if (!embedded && currentStep) {
      const stepString = currentStep.toString();
      // Read the current param directly from searchParams at effect time
      if (urlStepParam !== stepString) {
        urlWriteRef.current = true; // tell read effect to ignore the resulting searchParams change
        const newParams = new URLSearchParams(searchParams);
        newParams.set('step', stepString);
        setSearchParams(newParams, { replace: true });
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentStep, embedded, setSearchParams]);

  // Persist migration progress to localStorage for "Resume Migration" feature
  // Cleanup: abort any in-flight semantic profiling fetch when the component unmounts
  useEffect(() => {
    return () => { if (semProfileAbortRef.current) semProfileAbortRef.current.abort(); };
  }, []);

  useEffect(() => {
    // Only persist if there's meaningful progress (beyond step 1)
    if (currentStep > 1 || wizardData.sourceSystem || wizardData.targetSystem) {
      const migrationProgress = {
        step: currentStep,
        workflowName: wizardData.workflowName,
        sourceSystem: wizardData.sourceSystem?.name || null,
        targetSystem: wizardData.targetSystem?.name || null,
        savedWorkflowId: wizardData.savedWorkflowId || null,
        stepStatus,
        timestamp: new Date().toISOString(),
      };
      localStorage.setItem('migration_in_progress', JSON.stringify(migrationProgress));
    }
  }, [currentStep, wizardData.workflowName, wizardData.sourceSystem, wizardData.targetSystem, wizardData.savedWorkflowId, stepStatus]);

  // Step navigation
  const canProceed = useCallback((step) => {
    switch (step) {
      case 1: return (
        wizardData.workflowName.trim().length > 0 &&
        wizardData.sourceSystem &&
        wizardData.targetSystem &&
        // Prevent migrating from a system to itself
        wizardData.sourceSystem.id !== wizardData.targetSystem.id
      );
      case 2: return wizardData.discoveryAccepted;
      case 3: return wizardData.profileAccepted || wizardData.profileResult != null;
      case 4: return wizardData.qualityAccepted || wizardData.qualityRun;
      case 5: return wizardData.etlCompleted || wizardData.migrationStatus === 'completed';
      case 6: return true;
      default: return false;
    }
  }, [wizardData]);

  const nextStep = useCallback(async () => {
    if (currentStep < 6 && canProceed(currentStep)) {
      // On leaving step 1, enforce workflow name uniqueness before advancing
      if (currentStep === 1) {
        const apiBase = import.meta.env.VITE_API_BASE_URL || '';
        const nameToSave = wizardData.workflowName.trim();

        if (!wizardData.savedWorkflowId) {
          // First time leaving step 1 — create a new workflow instance
          try {
            const src = wizardData.sourceSystem;
            const tgt = wizardData.targetSystem;
            const payload = {
              name: nameToSave,
              description: `Migration from ${src.name} to ${tgt.name}`,
              source: { id: String(src.id), name: src.name, type: src.source_type || src.type || 'unknown', connection_details: { path: src.path || src.connection_string || '' } },
              target: { id: String(tgt.id), name: tgt.name, type: tgt.source_type || tgt.type || 'unknown', connection_details: { path: tgt.path || tgt.connection_string || '' } },
              workflow_config: { nodes: [], edges: [] }
            };
            // Use plain fetch so we can inspect res.status (e2etraceFetchWithRetry throws on 4xx)
            const res = await fetch(`${apiBase}${API_CONFIG.ENDPOINTS.WORKFLOWS}`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(payload)
            });
            if (res.ok) {
              const wf = await res.json();
              setWizardData(prev => ({ ...prev, savedWorkflowId: wf.id, savedWorkflowName: nameToSave }));
            } else if (res.status === 409) {
              const errData = await res.json().catch(() => ({}));
              toast.error(errData.detail || `A workflow named "${nameToSave}" already exists. Choose a unique name.`, 6000);
              return; // block step advancement
            }
            // Other non-OK statuses are non-fatal — wizard continues
          } catch (_e) {
            // Network error: non-fatal, wizard continues
          }
        } else if (wizardData.savedWorkflowName !== nameToSave) {
          // User went back and changed the name — PATCH to enforce uniqueness
          try {
            const res = await fetch(`${apiBase}${API_CONFIG.ENDPOINTS.WORKFLOWS}/${wizardData.savedWorkflowId}`, {
              method: 'PATCH',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ name: nameToSave })
            });
            if (res.ok) {
              setWizardData(prev => ({ ...prev, savedWorkflowName: nameToSave }));
            } else if (res.status === 409) {
              const errData = await res.json().catch(() => ({}));
              toast.error(errData.detail || `A workflow named "${nameToSave}" already exists. Choose a unique name.`, 6000);
              return; // block step advancement
            }
            // Other non-OK statuses are non-fatal
          } catch (_e) {
            // Network error: non-fatal, wizard continues
          }
        }
      }
      setStepStatus(prev => ({
        ...prev,
        [currentStep]: { complete: true, valid: true }
      }));
      setCurrentStep(prev => prev + 1);
    }
  // Specific deps instead of entire wizardData to avoid recreating on every state change
  // (e.g., progress updates during executeMigration would otherwise re-create nextStep)
  }, [currentStep, canProceed, wizardData.workflowName, wizardData.sourceSystem, wizardData.targetSystem, wizardData.savedWorkflowId, wizardData.savedWorkflowName]);

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
      // Reset all downstream discovery/mapping/validation state when source changes
      // to prevent stale data from a prior source flowing through the wizard
      discoveryStatus: 'idle',
      discoveryAccepted: false,
      discoveryRunId: null,
      discoverySodaResult: null,
      discoveryInsights: [],
      discoveryError: null,
      discoveryIntrospect: null,
      semanticProfile: null,
      semanticProfileStatus: 'idle',
      sourceSchema: null,
      targetSchema: null,
      // Also clear mapping/validation/rule state — stale data from the prior source
      // would silently pass validation against a different target
      fieldMappings: [],
      aiSuggestedMappings: [],
      rules: [],
      validationResults: [],
      qualityChecks: { passed: 0, failed: 0, warnings: 0 },
      validationRun: false,
      savedRuleSetId: null,
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
    if (discoveryInFlightRef.current) return;   // already running — ignore concurrent call
    discoveryInFlightRef.current = true;

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
      let stagedFrom = 'none';
      let samplePayload = null;

      try {
        const sourceId = wizardData.sourceSystem?.id;
        // Skip sampling if the selected source isn't in the live catalog -
        // a stale id would just trigger a noisy 404 with no useful outcome.
        const sourceKnown = sourceId && availableSources.some(s => s.id === sourceId);
        if (sourceId && !sourceKnown) {
          stagedFrom = 'not_registered';
        }
        if (sourceKnown) {
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
        // Non-fatal: discovery continues with whatever records were collected.
        // Distinguish 4xx (source not registered / access denied) from network/5xx (connection failed).
        // e?.isClientError is not a standard Fetch API property — check HTTP status code instead.
        const httpStatus = e?.status || e?.response?.status || 0;
        stagedFrom = (httpStatus >= 400 && httpStatus < 500) ? 'not_registered' : 'unreachable';
        console.warn('Data source sampling unavailable:', e?.message || e);
      }

      // If sample was attempted (samplePayload set) but returned no records,
      // mark as synthetic so the UI can show "Source Fields Not Detected".
      // Only override if stagedFrom hasn't already been set to a specific value.
      if (stagedFrom === 'none' && samplePayload !== null) {
        stagedFrom = 'synthetic';
      }

      if (!stagedRecords) {
        stagedRecords = [];
      }

      if (stagedRecords.length > 0) await e2etraceFetchWithRetry(`${plmBaseUrl}/runs/${discoveryRunId}/stage`, {
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
        // Use the dedicated discovery endpoint which routes to DataDiscoveryAgent via MCP.
        // Pass retries=1 so a 503 (MCP server not running) fails fast and falls through
        // to the legacy SODA path without burning 3 retry cycles.
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
        }, 1);

        const taskResult = agentResponse.status === 204
          ? {}
          : await agentResponse.json().catch(() => ({}));
        
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
                  confidence: '90%'
              }));
           }
        }

      } catch (agentError) {
         if (import.meta.env.DEV) console.warn("Agentic discovery failed, falling back:", agentError);
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
        sodaResult = await sodaResponse.json().catch(() => null);

        // Promote failed dq/scan checks as issues (the gates endpoint only checks record count).
        // dq/scan checks have: { name, status, score?, detail } — surface the non-passing ones.
        const failedChecks = Array.isArray(sodaResult?.checks)
          ? sodaResult.checks.filter(c => c?.status !== 'pass')
          : [];
        issues = failedChecks.map(c => ({ name: c.name, message: c.detail || c.name }));

        const gatesResponse = await e2etraceFetchWithRetry(`${plmBaseUrl}/runs/${discoveryRunId}/dq/gates`, {
          method: 'GET'
        });
        const gatesData = await gatesResponse.json();
        const gates = Array.isArray(gatesData?.gates) ? gatesData.gates : [];
        const latestGate = gates.find(g => String(g?.tool || '').toLowerCase() === 'soda') || gates[0];
        const report = latestGate?.details?.report;
        // Merge gates issues (no-records sentinel) with scan checks; avoid duplicates by name.
        const gatesIssues = Array.isArray(report?.issues) ? report.issues : [];
        const existingNames = new Set(issues.map(i => i.name));
        for (const gi of gatesIssues) {
          if (!existingNames.has(gi.name)) issues.push(gi);
        }
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

      // If Agent didn't provide schema, infer from union of all staged record keys
      // (not just the first record — different files may have different columns)
      if (inferredSourceFields.length === 0) {
          const keySet = new Set();
          if (Array.isArray(stagedRecords)) {
            for (const rec of stagedRecords) {
              if (rec && typeof rec === 'object' && !Array.isArray(rec)) {
                Object.keys(rec).forEach(k => keySet.add(k));
              }
            }
          }
          inferredSourceFields = Array.from(keySet);
      }

      // Normalize MCP quality_scan shape — the agent may return a non-standard envelope.
      // Ensure .overall_score / .status / .issues_count are always defined so the
      // SODA insight card never shows `undefined`.
      if (sodaResult && typeof sodaResult === 'object') {
        sodaResult = {
          overall_score: sodaResult.overall_score ?? sodaResult.score ?? null,
          status: sodaResult.status ?? (sodaResult.pass === true ? 'pass' : sodaResult.pass === false ? 'warn' : null),
          issues_count: sodaResult.issues_count ?? sodaResult.issues?.length ?? issues.length,
          checks: sodaResult.checks ?? [],
          ...sodaResult,
        };
      }

      // Seed mapping suggestions: prefer Agent output, then identity-map inferred source fields.
      let defaultMappingSuggestions = aiSuggestedMappings.length > 0
        ? aiSuggestedMappings
        : inferredSourceFields.map(f => ({ sourceField: f, targetField: f, transformation: null, confidence: '70%' }));

      // Use actual source fields as the canonical target schema when no Agent output is available.
      const canonicalTargetFields = inferredSourceFields;
      
      const finalSourceSchema = inferredSourceSchema || (inferredSourceFields.length > 0
        ? { fields: inferredSourceFields.map((name) => ({ name })) }
        : null);
      
      const finalTargetSchema = canonicalTargetFields.length > 0
        ? { fields: canonicalTargetFields.map((name) => ({ name })) }
        : null;

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

      // ── Agent Director: POST discovery/ingest ────────────────────────────────
      // Works without MCP: persists the discovery result, runs heuristic semantic
      // profiling, evaluates DB-backed DQ rules, and returns recommended actions.
      // Returns report_id so acceptDiscovery can call infer-mappings later.
      let agentDirectorReportId = null;
      let agentDirectorActions = [];
      try {
        const ingestRes = await e2etraceFetchWithRetry(
          `${API_CONFIG?.API_BASE_URL || ''}${API_CONFIG.ENDPOINTS.AGENTIC_DISCOVERY_INGEST}`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              run_id: discoveryRunId,
              source_id: wizardData.sourceSystem?.id || null,
              source_system_name: wizardData.sourceSystem?.name || null,
              staged_from: stagedFrom,
              inferred_source_fields: inferredSourceFields,
              soda_result: sodaResult || null,
              issues_count: issues.length,
              issues_preview: issues.slice(0, 5),
              recommendations: recommendations.slice(0, 10),
            }),
          },
          2
        );
        const ingestData = await ingestRes.json();
        agentDirectorReportId = ingestData.report_id || null;
        agentDirectorActions = Array.isArray(ingestData.recommended_actions) ? ingestData.recommended_actions : [];

        // Enrich mapping suggestions from agent director's canonical-name output.
        // Only replace non-Agent suggestions (i.e. when we're on the legacy/fallback path).
        if (!agentTaskSucceeded && Array.isArray(ingestData.mapping_suggestions) && ingestData.mapping_suggestions.length > 0) {
          defaultMappingSuggestions = ingestData.mapping_suggestions.map(s => ({
            sourceField: s.sourceField,
            targetField: s.targetField,
            transformation: s.transformation || null,
            confidence: s.confidence === 'High' ? '95%' : s.confidence === 'Medium' ? '75%' : '60%',
          }));
        }

        // Inject agent-director DQ violation insights.
        const violations = Array.isArray(ingestData.dq_violations) ? ingestData.dq_violations : [];
        const critViolations = violations.filter(v => v.severity === 'critical' || v.severity === 'error');
        const warnViolations = violations.filter(v => v.severity !== 'critical' && v.severity !== 'error');
        if (critViolations.length > 0) {
          insights.push({
            id: `dq-rule-crit-${Date.now()}`,
            title: `${critViolations.length} DQ rule violation(s)`,
            severity: 'warning',
            detail: critViolations.slice(0, 3).map(v => `${v.rule_name}: ${v.detail}`).join(' • '),
          });
        }
        if (warnViolations.length > 0) {
          insights.push({
            id: `dq-rule-warn-${Date.now()}`,
            title: `${warnViolations.length} DQ rule warning(s)`,
            severity: 'info',
            detail: warnViolations.slice(0, 3).map(v => v.rule_name).join(', '),
          });
        }

        // Inject top-priority agent action as an insight when it's not already covered.
        const topAction = agentDirectorActions[0];
        if (topAction && topAction.action !== 'proceed_to_mapping') {
          const alreadyCovered = insights.some(i =>
            i.detail?.includes(topAction.action) || i.title?.includes(topAction.label)
          );
          if (!alreadyCovered) {
            insights.push({
              id: `agent-action-${Date.now()}`,
              title: topAction.label,
              severity: topAction.severity === 'error' ? 'warning' : topAction.severity,
              detail: topAction.detail,
            });
          }
        }

        // Persist semantic insights into wizardData (ingest includes heuristic profile).
        const si = ingestData.semantic_insights;
        if (si && (si.column_semantics || si.entity_classifications)) {
          setWizardData(prev => ({
            ...prev,
            semanticProfile: si,
            semanticProfileStatus: 'completed',
          }));
        }

        if (import.meta.env.DEV) console.info('Agent Director ingested discovery:', {
          report_id: agentDirectorReportId,
          actions: agentDirectorActions.length,
          dq_violations: violations.length,
        });
      } catch (ingestErr) {
        if (import.meta.env.DEV) console.warn('Agent Director ingest unavailable:', ingestErr?.message || ingestErr);
      }

      // ── Fire DataProfilerAgent (non-blocking, via MCP) ────────────────────────
      // Only run if MCP is potentially available (skip when ingest already returned semantics).
      const _semCols = inferredSourceFields.length > 0
        ? inferredSourceFields
        : stagedRecords.length > 0
          ? [...new Set(stagedRecords.flatMap(r => (r && typeof r === 'object' ? Object.keys(r) : [])))]
          : [];

      if (_semCols.length > 0) {
        // Abort any previous in-flight semantic profiling request
        if (semProfileAbortRef.current) semProfileAbortRef.current.abort();
        const semAbortCtrl = new AbortController();
        semProfileAbortRef.current = semAbortCtrl;

        const _semPayload = {
          source_name: wizardData.sourceSystem?.name || 'source',
          file_profiles: [{
            file: wizardData.sourceSystem?.name || 'source',
            columns: _semCols.map(k => ({
              name: k,
              dtype: typeof (stagedRecords[0]?.[k] ?? 'string'),
              cardinality_ratio: 0.8,
              null_rate: 0.05
            }))
          }],
          min_relationship_similarity: 0.85,
        };
        // setWizardData with running status before the fetch so the spinner shows immediately.
        // Only set 'running' if ingest didn't already deliver semantics (which would be 'completed').
        setWizardData(prev => ({
          ...prev,
          semanticProfileStatus: prev.semanticProfileStatus === 'completed' ? 'completed' : 'running',
        }));
        e2etraceFetchWithRetry(`${API_CONFIG?.API_BASE_URL || ''}${API_CONFIG.ENDPOINTS.AGENTIC_SEMANTIC_PROFILE}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          signal: semAbortCtrl.signal,
          body: JSON.stringify({
            source_name:      _semPayload.source_name,
            folder_path:      wizardData.sourceSystem?.folder_path || null,
            file_profiles:    _semPayload.file_profiles,
            discovery_run_id: discoveryRunId,
            sample_rows:      500,
            save_report:      true,
          })
        }, 1)
          .then(r => r.json())
          .then(profileResult => {
            const si = profileResult?.result?.semantic_insights
                    || profileResult?.semantic_insights
                    || profileResult?.result;
            if (si && (si.column_semantics || si.entity_classifications)) {
              // Feed profiler confidence into mapping suggestions for any column
              // where the profiler derived a higher-confidence canonical name.
              const confMap = Object.fromEntries(
                (si.column_semantics || []).map(cs => [cs.column, cs.confidence ?? 0])
              );
              setWizardData(prev => ({
                ...prev,
                semanticProfile: si,
                semanticProfileStatus: 'completed',
                // Upgrade confidence label on any mapping where profiler is high-confidence
                aiSuggestedMappings: prev.aiSuggestedMappings.map(m => {
                  const profilerConf = confMap[m.sourceField];
                  if (profilerConf != null && profilerConf >= 0.75 && m.confidence === '70%') {
                    return { ...m, confidence: `${Math.round(profilerConf * 100)}% (profiler)` };
                  }
                  return m;
                }),
              }));
            } else {
              setWizardData(prev => ({
                ...prev,
                semanticProfileStatus: prev.semanticProfileStatus === 'completed' ? 'completed' : 'idle',
              }));
            }
          })
          .catch(profileError => {
            console.warn('Semantic profiling (MCP) unavailable:', profileError?.message || profileError);
            setWizardData(prev => ({
              ...prev,
              semanticProfileStatus: prev.semanticProfileStatus === 'completed' ? 'completed' : 'failed',
            }));
          });
      }

      // Inject a source-registration insight when source is not in DB.
      if (stagedFrom === 'not_registered') {
        const sourceId = wizardData.sourceSystem?.id;
        const sourceName = wizardData.sourceSystem?.name || sourceId;
        insights.unshift({
          id: `src-unreg-${Date.now()}`,
          title: `Source "${sourceName}" is not registered`,
          severity: 'warning',
          detail: `No data source with ID "${sourceId}" exists. Register it via Admin → Data Sources, then re-run discovery.`,
        });
      } else if (stagedFrom === 'unreachable') {
        insights.unshift({
          id: `src-reach-${Date.now()}`,
          title: 'Source could not be reached',
          severity: 'warning',
          detail: 'The configured source returned an error during sampling. Check connection settings in Admin → Data Sources.',
        });
      }

      setWizardData(prev => ({
        ...prev,
        discoveryStatus: 'completed',
        discoveryRunId,
        discoverySodaResult: sodaResult,
        discoveryInsights: insights,
        discoverySample: samplePayload ? { ...samplePayload, stagedFrom } : { stagedFrom },
        discoveryIntrospect: {
          ...introspectPayload,
          // report_id from agent director lets acceptDiscovery call infer-mappings
          report_id: agentDirectorReportId || null,
          // Attach recommended actions so DiscoveryResults can render them
          recommended_actions: agentDirectorActions,
        },
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
      discoveryInFlightRef.current = false;
      setOpLoading(prev => ({ ...prev, discovery: false }));
    }
  }, [wizardData.sourceSystem, wizardData.targetSystem, availableSources]);

  const acceptDiscovery = useCallback(async () => {
    setWizardData(prev => ({
      ...prev,
      discoveryAccepted: true
    }));

    // ── Call backend infer-mappings if we have a saved discovery report_id ──
    // The backend reads the column profile from the discovery_reports table and
    // matches source fields against the PLM canonical target schema.
    const reportId = wizardData.discoverySodaResult?.report_id
      || wizardData.discoveryIntrospect?.report_id
      || null;

    if (reportId) {
      try {
        const _apiBase = import.meta.env.VITE_API_BASE_URL || '';
        const res = await e2etraceFetchWithRetry(`${_apiBase}${API_CONFIG.ENDPOINTS.DISCOVERY_INFER_MAPPINGS(reportId)}`);
        if (res.ok) {
          const inferData = await res.json();
          const backendMappings = (inferData.mappings || []).map(m => ({
            sourceField: m.sourceField,
            targetField: m.targetField,
            transformation: m.transformation || null,
            confidence: m.confidence === 'High' ? '95%' : m.confidence === 'Medium' ? '75%' : '50%',
          }));

          if (backendMappings.length > 0) {
            setWizardData(prev => ({
              ...prev,
              // Prefer backend-inferred mappings; only keep prior suggestions not covered
              aiSuggestedMappings: backendMappings,
              // Pre-populate fieldMappings so Map step has something on arrival
              fieldMappings: prev.fieldMappings.length === 0 ? backendMappings : prev.fieldMappings,
            }));
          }

          // Surface any DQ rule violations as extra insights
          const violations = inferData.dq_violations || [];
          if (violations.length > 0) {
            const criticalCount = violations.filter(v => v.severity === 'critical' || v.severity === 'high').length;
            setWizardData(prev => ({
              ...prev,
              discoveryInsights: [
                ...prev.discoveryInsights,
                {
                  id: `dq-rules-${Date.now()}`,
                  title: 'DQ rule violations detected',
                  severity: criticalCount > 0 ? 'warning' : 'info',
                  detail: `${violations.length} DQ rule(s) failed on discovered data${criticalCount > 0 ? ` (${criticalCount} critical/high)` : ''}.`,
                },
              ],
            }));
          }
        }
      } catch (inferErr) {
        // Non-fatal: wizard still works without backend inference
        console.warn('Backend mapping inference unavailable:', inferErr?.message || inferErr);
      }
    }

    // Show success confirmation toast
    const fieldsDetected = wizardData.discoveryIntrospect?.inferred_source_fields?.length ||
                          extractSchemaFields(wizardData.sourceSchema).length || 0;
    const qualityScore = wizardData.discoveryIntrospect?.soda?.overall_score ||
                        wizardData.discoveryIntrospect?.quality_score || null;
    const suggestionCount = wizardData.aiSuggestedMappings?.length || 0;

    let message = 'Discovery Accepted!';
    const details = [];
    if (fieldsDetected > 0) details.push(`${fieldsDetected} fields discovered`);
    if (qualityScore !== null) details.push(`Quality: ${qualityScore}%`);
    if (suggestionCount > 0) details.push(`${suggestionCount} AI suggestions ready`);

    if (details.length > 0) {
      message += '\n' + details.join(' • ');
    }
    message += '\nReady to proceed to field mapping.';

    toast.success(message, 6000);
  }, [wizardData.discoveryIntrospect, wizardData.sourceSchema, wizardData.discoverySodaResult, wizardData.aiSuggestedMappings]);

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

  // Bulk-add rules returned by the NLP rule generator
  const addRules = useCallback((newRules) => {
    if (!Array.isArray(newRules) || newRules.length === 0) return;
    setWizardData(prev => ({
      ...prev,
      rules: [...prev.rules, ...newRules],
    }));
  }, []);

  /** Single-rule wrapper used by DataHealthPanel "Apply" button */
  const applyInferredRule = useCallback((rule) => {
    addRules([rule]);
  }, [addRules]);

  // ── Step 3: Profile — DataProfilerAgent via MCP ──────────────────────────
  const runProfileAgent = useCallback(async () => {
    if (!wizardData.sourceSystem && !wizardData.discoveryRunId) return;
    setOpLoading(prev => ({ ...prev, profile: true }));
    setWizardData(prev => ({ ...prev, profileStatus: 'running', profileResult: null, profileError: null }));
    try {
      const fileProfiles = wizardData.discoveryIntrospect?.file_profiles
        || (wizardData.discoverySample ? [{ file: wizardData.sourceSystem?.name || 'source', columns: Object.keys(wizardData.discoverySample[0] || {}).map(n => ({ name: n })) }] : []);

      const res = await e2etraceFetchWithRetry(
        `${API_CONFIG?.API_BASE_URL || ''}${API_CONFIG.ENDPOINTS.AGENTIC_WORKFLOW_PROFILE}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            source_id: wizardData.sourceSystem?.id || null,
            folder_path: wizardData.sourceSystem?.connection?.file_path || null,
            run_id: wizardData.discoveryRunId || null,
            file_profiles: fileProfiles,
            records: wizardData.discoverySample?.slice?.(0, 200) || [],
            prior_results: {},
            params: { source_name: wizardData.sourceSystem?.name },
          }),
        }
      );
      const data = await res.json();
      if (data.success !== false) {
        setWizardData(prev => ({
          ...prev,
          profileStatus: 'completed',
          profileResult: data.result || data,
          profileAccepted: true,
        }));
      } else {
        throw new Error(data.error || 'Profile agent returned failure');
      }
    } catch (err) {
      console.error('Profile agent failed:', err);
      setWizardData(prev => ({
        ...prev,
        profileStatus: 'failed',
        profileError: err.message || String(err),
        // Allow proceeding even if profiling fails — heuristic fallback
        profileAccepted: true,
      }));
    } finally {
      setOpLoading(prev => ({ ...prev, profile: false }));
    }
  }, [wizardData.sourceSystem, wizardData.discoveryRunId, wizardData.discoverySample, wizardData.discoveryIntrospect]);

  // ── Step 4: Quality — QualityMonitorAgent via MCP ───────────────────────
  const runQualityAgent = useCallback(async () => {
    if (!wizardData.sourceSystem && !wizardData.discoveryRunId) return;
    setOpLoading(prev => ({ ...prev, quality: true }));
    setWizardData(prev => ({ ...prev, qualityStatus: 'running', qualityResult: null, qualityError: null }));
    try {
      const res = await e2etraceFetchWithRetry(
        `${API_CONFIG?.API_BASE_URL || ''}${API_CONFIG.ENDPOINTS.AGENTIC_WORKFLOW_QUALITY}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            source_id: wizardData.sourceSystem?.id || null,
            folder_path: wizardData.sourceSystem?.connection?.file_path || null,
            run_id: wizardData.discoveryRunId || null,
            file_profiles: [],
            records: wizardData.discoverySample?.slice?.(0, 500) || [],
            prior_results: wizardData.profileResult ? { profile: wizardData.profileResult } : {},
            params: {
              source_name: wizardData.sourceSystem?.name,
              profile_summary: wizardData.profileResult || null,
            },
          }),
        }
      );
      const data = await res.json();
      if (data.success !== false) {
        const result = data.result || data;
        setWizardData(prev => ({
          ...prev,
          qualityStatus: 'completed',
          qualityResult: result,
          qualityRun: true,
          qualityAccepted: true,
          // Back-fill validation results for the legacy quality checks panel
          validationResults: (result.rule_validation?.violations || []).map((v, i) => ({
            id: `qv-${i}`,
            insight: `[${v.rule_name || 'Rule'}] ${v.message || v.detail || v.severity}`,
            severity: v.severity === 'critical' ? 'error' : v.severity || 'warning',
            recommendation: v.action || '',
          })),
          qualityChecks: {
            passed: result.quality_score >= 80 ? 1 : 0,
            failed: (result.anomalies_found || 0),
            warnings: result.quality_score < 80 && result.quality_score >= 50 ? 1 : 0,
          },
        }));
      } else {
        throw new Error(data.error || 'Quality agent returned failure');
      }
    } catch (err) {
      console.error('Quality agent failed:', err);
      setWizardData(prev => ({
        ...prev,
        qualityStatus: 'failed',
        qualityError: err.message || String(err),
        qualityRun: true,
      }));
    } finally {
      setOpLoading(prev => ({ ...prev, quality: false }));
    }
  }, [wizardData.sourceSystem, wizardData.discoveryRunId, wizardData.discoverySample, wizardData.profileResult]);

  // ── Step 6: Report — ReportingAgent via MCP ─────────────────────────────
  const generateAgentReport = useCallback(async () => {
    setOpLoading(prev => ({ ...prev, report: true }));
    setWizardData(prev => ({ ...prev, agentReportStatus: 'running', agentReportResult: null, agentReportError: null }));
    try {
      const priorResults = {};
      if (wizardData.discoveryIntrospect || wizardData.discoveryInsights?.length)
        priorResults.discover = {
          file_profiles: wizardData.discoveryIntrospect?.file_profiles || [],
          files: wizardData.discoveryIntrospect?.discovered_files || [],
        };
      if (wizardData.profileResult)
        priorResults.profile = wizardData.profileResult;
      if (wizardData.qualityResult)
        priorResults.quality = wizardData.qualityResult;
      if (wizardData.migrationStatus === 'completed')
        priorResults.etl = {
          records_processed: wizardData.processedRecords,
          nodes_created: wizardData.nodesCreated,
          status: wizardData.migrationStatus,
        };

      const res = await e2etraceFetchWithRetry(
        `${API_CONFIG?.API_BASE_URL || ''}${API_CONFIG.ENDPOINTS.AGENTIC_WORKFLOW_REPORT}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            source_id: wizardData.sourceSystem?.id || null,
            folder_path: wizardData.sourceSystem?.connection?.file_path || null,
            run_id: wizardData.discoveryRunId || null,
            prior_results: priorResults,
            params: {
              source_name: wizardData.sourceSystem?.name,
              workflow_name: wizardData.workflowName,
              capability: 'report_generation',
            },
          }),
        }
      );
      const data = await res.json();
      if (data.success !== false) {
        setWizardData(prev => ({
          ...prev,
          agentReportStatus: 'completed',
          agentReportResult: data.result || data,
        }));
      } else {
        throw new Error(data.error || 'Reporting agent returned failure');
      }
    } catch (err) {
      console.error('Report generation failed:', err);
      setWizardData(prev => ({
        ...prev,
        agentReportStatus: 'failed',
        agentReportError: err.message || String(err),
      }));
    } finally {
      setOpLoading(prev => ({ ...prev, report: false }));
    }
  }, [wizardData.sourceSystem, wizardData.discoveryRunId, wizardData.discoveryIntrospect, wizardData.discoveryInsights, wizardData.profileResult, wizardData.qualityResult, wizardData.migrationStatus, wizardData.processedRecords, wizardData.nodesCreated, wizardData.workflowName]);

  /** Trigger the DataDiscoveryAgent data_health_report task and store result */
  const generateDataHealthReport = useCallback(async () => {
    if (!wizardData.sourceSystem) return;
    setWizardData(prev => ({ ...prev, dataHealthLoading: true, dataHealthReport: null }));
    try {
      const res = await e2etraceFetchWithRetry(
        `${API_CONFIG?.API_BASE_URL || ''}/api/agentic/task`,
        {
          method:  'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            type: 'data_health_report',
            required_capabilities: ['data_health_report'],
            payload: {
              source_id:   wizardData.sourceSystem?.id   || null,
              folder_path: wizardData.sourceSystem?.connection?.file_path
                        || wizardData.sourceSystem?.connection?.connection_string
                        || null,
              run_id:      wizardData.discoveryRunId || null,
            },
          }),
        },
        { retries: 1 }
      );
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || `HTTP ${res.status}`);
      // AgenticTaskResult wraps agent response in `.result`
      const report = data?.result ?? data;
      setWizardData(prev => ({ ...prev, dataHealthReport: report, dataHealthLoading: false }));
    } catch (err) {
      if (import.meta.env.DEV) console.warn('Data health report unavailable:', err.message);
      toast.error('Could not generate Data Health Report. Ensure the agent service is running.');
      setWizardData(prev => ({ ...prev, dataHealthLoading: false }));
    }
  }, [wizardData.sourceSystem, wizardData.discoveryRunId]);

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
      // ── 1. Persist wizard rules to the backend rule engine ──────────────
      // Rules are saved as a proper RuleSet so they survive session reloads
      // and can be re-executed independently of the wizard.
      let ruleSetId = null;
      const enabledRules = (wizardData.rules || []).filter(r => r.enabled && r.condition);
      if (enabledRules.length > 0) {
        try {
          const saveRes = await e2etraceFetchWithRetry(API_CONFIG.ENDPOINTS.RULES_FROM_WIZARD, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              workflow_name: wizardData.workflowName || 'Wizard',
              workflow_id: wizardData.savedWorkflowId || null,
              rules: enabledRules,
            }),
          });
          if (saveRes.ok) {
            const saveData = await saveRes.json();
            ruleSetId = saveData.rule_set_id;
          }
        } catch (saveErr) {
          console.warn('Could not persist wizard rules to backend:', saveErr?.message || saveErr);
        }
      }

      // ── 2. Execute the saved rule set against sample data ───────────────
      let ruleViolations = [];
      if (ruleSetId) {
        try {
          // Build a representative sample record from discovery schema or field mappings
          const sampleRecord = {};
          const sourceFields = extractSchemaFields(wizardData.sourceSchema);
          sourceFields.forEach(f => { sampleRecord[f] = null; }); // null triggers not_null rules
          (wizardData.fieldMappings || []).forEach(m => {
            // fieldMappings may use camelCase (sourceField) or snake_case (source_field)
            const srcField = m.source_field || m.sourceField;
            if (srcField) sampleRecord[srcField] = sampleRecord[srcField] ?? '';
          });

          const execRes = await e2etraceFetchWithRetry(API_CONFIG.ENDPOINTS.RULES_EXECUTE, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              rule_set_id: ruleSetId,
              entity_data: sampleRecord,
              entity_id: 'validation_sample',
            }),
          });
          if (execRes.ok) {
            const execData = await execRes.json();
            ruleViolations = execData.violations || [];
          }
        } catch (execErr) {
          console.warn('Rule execution unavailable:', execErr?.message || execErr);
        }
      }

      // ── 3. AI schema / mapping validation insights ──────────────────────
      const validationInsights = await aiSuggestions.getValidationInsights(
        { schema: wizardData.sourceSchema, mappings: wizardData.fieldMappings },
        { nodeCompleteness: true, relationshipIntegrity: true, dataTypeConsistency: true }
      );

      // ── 4. Merge rule violations into validation results ─────────────────
      const ruleInsights = ruleViolations.map((v, i) => ({
        id: `rule-${i}-${Date.now()}`,
        insight: `Rule "${v.rule_name}" failed: ${v.message || v.severity}`,
        severity: v.severity === 'critical' || v.severity === 'blocker' ? 'error' : 'warning',
        recommendation: `Action: ${v.action || 'review'}`,
      }));

      const allInsights = [...validationInsights, ...ruleInsights];
      const passed = allInsights.filter(v => v.severity === 'success' || v.severity === 'info').length;
      const failed = allInsights.filter(v => v.severity === 'error').length;
      const warnings = allInsights.filter(v => v.severity === 'warning').length;

      setWizardData(prev => ({
        ...prev,
        validationResults: allInsights,
        qualityChecks: { passed, failed, warnings },
        validationRun: true,
        savedRuleSetId: ruleSetId,
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
  }, [wizardData.sourceSchema, wizardData.fieldMappings, wizardData.rules, wizardData.workflowName, wizardData.savedWorkflowId, aiSuggestions]);

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
        // Replace SODA-contributed quality check counts (don't accumulate — re-runs would double count)
        qualityChecks: { 
          passed: Math.max(0, prev.qualityChecks.passed - (prev.sodaScanResult?.status === 'pass' ? 1 : 0)) + passed,
          failed: Math.max(0, prev.qualityChecks.failed - (prev.sodaScanResult?.status === 'fail' ? 1 : 0)) + failed,
          warnings: Math.max(0, prev.qualityChecks.warnings - (prev.sodaScanResult?.status === 'warn' ? 1 : 0)) + warnings
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
  }, [wizardData.sourceSchema, wizardData.targetSchema, wizardData.fieldMappings, graphqlTransform]);

  // Generate Non-Conformance Report (NCR) as Excel — called from Validate step
  const generateNcr = useCallback(async () => {
    const { validationResults = [], qualityChecks = {}, workflowName, fieldMappings = [] } = wizardData;
    const issueRows = validationResults.filter(r => r.severity !== 'success');
    const HEADER = { fontWeight: 'bold', backgroundColor: '#1F3864', color: '#FFFFFF', align: 'center' };
    const RED   = { backgroundColor: '#FFC7CE', color: '#9C0006' };
    const AMBER = { backgroundColor: '#FFEB9C', color: '#7F6000' };
    const dateStr = new Date().toISOString().slice(0, 10);

    const headers = [
      { value: 'NCR #',         ...HEADER, width: 8  },
      { value: 'Severity',      ...HEADER, width: 12 },
      { value: 'Description',   ...HEADER, width: 55 },
      { value: 'Field',         ...HEADER, width: 22 },
      { value: 'Rule / Check',  ...HEADER, width: 30 },
      { value: 'Recommendation',...HEADER, width: 55 },
      { value: 'Status',        ...HEADER, width: 12 },
      { value: 'Date Raised',   ...HEADER, width: 16 },
      { value: 'Comments',      ...HEADER, width: 40 },
    ];

    const dataRows = issueRows.length > 0
      ? issueRows.map((r, i) => {
          const style = r.severity === 'error' ? RED : AMBER;
          return [
            { value: `NCR-${String(i + 1).padStart(3, '0')}` },
            { value: (r.severity || 'warning').toUpperCase(), ...style, fontWeight: 'bold' },
            { value: r.insight || '' },
            { value: r.field || '' },
            { value: r.rule || r.check || '' },
            { value: r.recommendation || '' },
            { value: 'Open', color: '#C00000', fontWeight: 'bold' },
            { value: dateStr },
            { value: '' },
          ];
        })
      : [[
          { value: 'NCR-001' },
          { value: 'INFO', color: '#375623', fontWeight: 'bold' },
          { value: `${qualityChecks.warnings || 0} warning(s) noted — no hard failures` },
          { value: '' }, { value: '' }, { value: '' },
          { value: 'Open' }, { value: dateStr }, { value: '' },
        ]];

    // Summary sheet
    const summarySheet = [
      [{ value: 'Non-Conformance Report', span: 2, fontWeight: 'bold', fontSize: 14, color: '#1F3864' }],
      [{ value: 'Workflow', ...HEADER }, { value: workflowName || '(unnamed)' }],
      [{ value: 'Date', ...HEADER }, { value: dateStr }],
      [{ value: 'Total Issues', ...HEADER }, { value: issueRows.length, type: Number }],
      [{ value: 'Failed Checks', ...HEADER }, { value: qualityChecks.failed || 0, type: Number, ...RED }],
      [{ value: 'Warnings', ...HEADER }, { value: qualityChecks.warnings || 0, type: Number, ...AMBER }],
      [{ value: 'Passed Checks', ...HEADER }, { value: qualityChecks.passed || 0, type: Number, backgroundColor: '#C6EFCE', color: '#375623' }],
      [{ value: 'Field Mappings', ...HEADER }, { value: fieldMappings.length, type: Number }],
    ];

    await writeXlsxFile(
      [summarySheet, [headers, ...dataRows]],
      {
        sheets: ['NCR Summary', 'Issue Register'],
        fileName: `ncr-${(workflowName || 'migration').replace(/\s+/g, '-').toLowerCase()}-${dateStr}.xlsx`,
        columns: [
          [{ width: 24 }, { width: 30 }],
          headers.map(h => ({ width: h.width || 20 })),
        ],
      }
    ).then(() => {
      toast.success('Non-Conformance Report exported as Excel', 3000);
    }).catch(exportErr => {
      console.error('NCR export failed:', exportErr);
      toast.error(`NCR export failed: ${exportErr?.message || 'Unknown error'}`, 5000);
    });
  }, [wizardData]);

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
        // Accept both snake_case (manual UI rows) and camelCase (AI/backend suggestions)
        const src = (m?.source_field || m?.sourceField || '').trim();
        const dest = (m?.target_field || m?.targetField || '').trim();
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
        processedRecords: syncResult?.parts_synced ?? records.length,
        totalRecords: syncResult?.parts_synced ?? records.length,
        nodesCreated: syncResult?.nodes_created || 0,
        etlCompleted: true,
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
  }, [wizardData.sourceSystem, wizardData.targetSystem, wizardData.fieldMappings, onComplete]);

  // Render step content
  const renderStepContent = () => {
    switch (currentStep) {
      case 1: return renderConnectStep();
      case 2: return renderSchemaStep();
      case 3: return renderProfileStep();
      case 4: return renderQualityStep();
      case 5: return renderMappingStep();
      case 6: return renderReportStep();
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
          <i className="fas fa-brain" /> AI Assistant: {graphRAGHealth.isLoading ? 'Checking...' : (graphRAGHealth.health?.status || 'unavailable')}
        </span>
        <span className={`status-indicator ${agenticSystem.status?.status === 'healthy' ? 'active' : ''}`}>
          <i className="fas fa-robot" /> Agentic: {agenticSystem.isLoading ? 'Checking...' : (agenticSystem.status?.status || 'unavailable')}
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

      {/* ── Smart Guidance panel: shown while discovery is idle ── */}
      {wizardData.discoveryStatus === 'idle'
        && wizardData.sourceSystem
        && !smartGuidanceDismissed && (
        <SmartGuidancePanel
          sourceSystem={wizardData.sourceSystem}
          fileCount={wizardData.discoverySample?.total_files ?? null}
          fileTypes={wizardData.discoverySample?.file_types ?? null}
          previousRuns={Boolean(wizardData.semanticProfile || wizardData.discoveryRunId)}
          userRole="business"
          onAction={(action) => {
            setSmartGuidanceDismissed(true);
            if (action === 'discovery' || action === 'profiling') {
              runDiscovery();
            }
            // 'quality' is handled in step 4 — just dismiss the panel here
          }}
          onDismiss={() => setSmartGuidanceDismissed(true)}
        />
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

      {/* ── Error state ─────────────────────────────────────────────── */}
      {wizardData.discoveryStatus === 'failed' && wizardData.discoveryError && (
        <div className="discovery-error" style={{ marginTop: 12 }}>{wizardData.discoveryError}</div>
      )}

      {/* ── Idle placeholder ─────────────────────────────────────────── */}
      {wizardData.discoveryStatus === 'idle' && wizardData.discoveryInsights.length === 0 && (
        <p className="placeholder" style={{ marginTop: 12 }}>
          Run Discovery to generate insights. You must accept discovery before continuing.
        </p>
      )}

      {/* ── Discovery Intelligence Dashboard (DiscoveryResults widget) ─── */}
      {(wizardData.discoveryStatus === 'completed' || wizardData.discoveryInsights.length > 0
        || wizardData.semanticProfileStatus === 'running') && (
        <DiscoveryResults
          runId={wizardData.discoveryRunId}
          insights={wizardData.discoveryInsights}
          introspect={wizardData.discoveryIntrospect}
          sample={wizardData.discoverySample}
          mappings={wizardData.aiSuggestedMappings || []}
          semanticProfile={wizardData.semanticProfile}
          sodaResult={wizardData.discoverySodaResult}
          sourceSystem={wizardData.sourceSystem}
        />
      )}

      {/* ── AI Data Health Report ──────────────────────────────────────── */}
      {wizardData.discoveryStatus === 'completed' && !wizardData.dataHealthReport && !wizardData.dataHealthLoading && (
        <button
          className="dh-generate-btn"
          onClick={generateDataHealthReport}
          disabled={wizardData.dataHealthLoading}
          title="Run AI-powered Data Health Report: Readiness Score, Trust Score, anomaly detection, inferred rules"
        >
          <i className="fas fa-heartbeat" />
          Generate AI Data Health Report
        </button>
      )}
      {(wizardData.dataHealthReport || wizardData.dataHealthLoading) && (
        <DataHealthPanel
          healthReport={wizardData.dataHealthReport}
          loading={wizardData.dataHealthLoading}
          onApplyRule={applyInferredRule}
        />
      )}

      {/* ── Synthetic / no-fields notice (still show when live fields not available) ─── */}
      {wizardData.discoveryStatus === 'completed'
        && !wizardData.discoveryIntrospect?.inferred_source_fields?.length
        && !wizardData.aiSuggestedMappings?.length
        && wizardData.discoverySample?.stagedFrom === 'synthetic' && (
        <div className="discovery-data-panel" style={{ marginTop: 16 }}>
          <div className="ddp-header">
            <i className="fas fa-exclamation-triangle" /> Source Fields Not Detected
          </div>
          <p style={{ padding: '8px 12px', margin: 0, fontSize: '0.85rem', color: 'var(--text-muted-color)' }}>
            Could not connect to the source system for live sampling. Configure a reachable data source
            (file, database, or API) to detect real fields. You can manually define field mappings in Step 3.
          </p>
        </div>
      )}
    </div>
  );

  // ── Step 3: Profile — DataProfilerAgent via MCP ──────────────────────────
  const renderProfileStep = () => {
    const pr = wizardData.profileResult;
    const si = pr?.semantic_insights || pr?.result?.semantic_insights || wizardData.semanticProfile || {};
    const colSem = si.column_semantics || [];
    const entityCls = si.entity_classifications || [];
    const relationships = si.relationships || [];
    const summary = si.summary || {};
    const hasResults = colSem.length > 0 || entityCls.length > 0 || wizardData.semanticProfile;

    return (
      <div className="wizard-step-content profile-step">
        <div className="step-hero">
          <h3><i className="fas fa-brain" /> Semantic Profiling</h3>
          <p className="step-description">
            DataProfilerAgent performs deep semantic analysis — classifying column roles, entity types,
            and cross-file relationships using AI so downstream ETL is data-aware.
          </p>
        </div>

        <div className="agent-action-panel">
          <div className="agent-info">
            <i className="fas fa-robot agent-icon" />
            <div>
              <strong>Agent:</strong> DataProfilerAgent
              <span className="capability-tags">
                <span className="cap-tag">profiling</span>
                <span className="cap-tag">infer_column_semantics</span>
                <span className="cap-tag">classify_entities</span>
                <span className="cap-tag">detect_relationships</span>
              </span>
            </div>
          </div>
          <button
            className="btn btn-primary btn-ai"
            onClick={runProfileAgent}
            disabled={opLoading.profile || wizardData.profileStatus === 'running'}
          >
            {wizardData.profileStatus === 'running' || opLoading.profile
              ? <><i className="fas fa-spinner fa-spin" /> Profiling…</>
              : wizardData.profileStatus === 'completed'
                ? <><i className="fas fa-redo" /> Re-run Profiling</>
                : <><i className="fas fa-brain" /> Run Semantic Profile</>}
          </button>
        </div>

        {wizardData.profileStatus === 'running' && (
          <div className="agent-running-card">
            <i className="fas fa-spinner fa-spin" />
            <span>DataProfilerAgent is analysing column semantics and entity classification…</span>
          </div>
        )}

        {wizardData.profileStatus === 'failed' && (
          <div className="agent-error-card">
            <i className="fas fa-exclamation-triangle" />
            <span>{wizardData.profileError || 'Profiling failed'}</span>
            <button className="btn btn-sm btn-warning" onClick={runProfileAgent}>
              <i className="fas fa-redo" /> Retry
            </button>
          </div>
        )}

        {hasResults && (
          <div className="profile-results">
            <div className="profile-summary-row">
              <div className="profile-kpi">
                <span className="kpi-value">{colSem.length || '—'}</span>
                <span className="kpi-label">Columns Profiled</span>
              </div>
              <div className="profile-kpi">
                <span className="kpi-value">{summary.top_entity_class || entityCls[0]?.entity_type || '—'}</span>
                <span className="kpi-label">Entity Class</span>
              </div>
              <div className="profile-kpi">
                <span className="kpi-value">{relationships.length || summary.relationship_count || 0}</span>
                <span className="kpi-label">Relationships</span>
              </div>
              <div className="profile-kpi">
                <span className="kpi-value">
                  {summary.high_confidence_semantics || colSem.filter(c => (c.confidence || 0) >= 0.75).length || 0}
                </span>
                <span className="kpi-label">High-Confidence</span>
              </div>
            </div>

            {colSem.length > 0 && (
              <div className="profile-section">
                <h4><i className="fas fa-columns" /> Column Semantics</h4>
                <div className="semantics-table-wrap">
                  <table className="semantics-table">
                    <thead>
                      <tr>
                        <th>Column</th>
                        <th>Semantic Role</th>
                        <th>Entity Hint</th>
                        <th>Confidence</th>
                      </tr>
                    </thead>
                    <tbody>
                      {colSem.slice(0, 20).map((cs, i) => (
                        <tr key={i}>
                          <td><code>{cs.column || cs.canonical_name || '—'}</code></td>
                          <td>
                            <span className={`role-badge role-${(cs.semantic_role || '').toLowerCase()}`}>
                              {cs.semantic_role || '—'}
                            </span>
                          </td>
                          <td>{cs.entity_hint || '—'}</td>
                          <td>
                            <div className="conf-bar-wrap">
                              <div className="conf-bar" style={{ width: `${Math.round((cs.confidence || 0) * 100)}%` }} />
                              <span>{Math.round((cs.confidence || 0) * 100)}%</span>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {colSem.length > 20 && <p className="more-note">+{colSem.length - 20} more columns</p>}
                </div>
              </div>
            )}

            {entityCls.length > 0 && (
              <div className="profile-section">
                <h4><i className="fas fa-tags" /> Entity Classifications</h4>
                <div className="entity-cls-grid">
                  {entityCls.map((ec, i) => (
                    <div key={i} className="entity-cls-card">
                      <span className="entity-type">{ec.entity_type || ec.type || '—'}</span>
                      <span className="entity-conf">{Math.round((ec.confidence || 0) * 100)}%</span>
                      {ec.files?.length > 0 && <span className="entity-files">{ec.files.length} file(s)</span>}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {relationships.length > 0 && (
              <div className="profile-section">
                <h4><i className="fas fa-link" /> Detected Relationships</h4>
                <div className="relationships-list">
                  {relationships.slice(0, 10).map((rel, i) => (
                    <div key={i} className="relationship-item">
                      <span className="rel-source">{rel.source_column || rel.from || '—'}</span>
                      <i className="fas fa-long-arrow-alt-right rel-arrow" />
                      <span className="rel-target">{rel.target_column || rel.to || '—'}</span>
                      {rel.relationship_type && <span className="rel-type-badge">{rel.relationship_type}</span>}
                      {rel.similarity_score != null && (
                        <span className="rel-score">{Math.round(rel.similarity_score * 100)}%</span>
                      )}
                    </div>
                  ))}
                  {relationships.length > 10 && <p className="more-note">+{relationships.length - 10} more</p>}
                </div>
              </div>
            )}
          </div>
        )}

        {wizardData.profileStatus === 'idle' && !hasResults && (
          <div className="agent-idle-card">
            <i className="fas fa-brain" />
            <p>
              Click <strong>Run Semantic Profile</strong> to have DataProfilerAgent classify every
              column&rsquo;s semantic role, identify entity types, and detect cross-column
              relationships — enriching all downstream ETL and quality steps.
            </p>
          </div>
        )}

        <SmartGuidancePanel
          context={{ step: 'profile', source: wizardData.sourceSystem?.name, profileStatus: wizardData.profileStatus }}
          dismissed={smartGuidanceDismissed}
          onDismiss={() => setSmartGuidanceDismissed(true)}
        />
      </div>
    );
  };

  // ── Step 4: Quality — QualityMonitorAgent via MCP ─────────────────────────
  const renderQualityStep = () => {
    const qr = wizardData.qualityResult;
    const score = qr?.quality_score ?? qr?.overall_score ?? null;
    const anomalies = qr?.anomalies_found ?? 0;
    const violations = qr?.rule_validation?.violations || qr?.violations || [];
    const scoreClass = score == null ? '' : score >= 80 ? 'score-good' : score >= 50 ? 'score-warn' : 'score-bad';

    return (
      <div className="wizard-step-content quality-step">
        <div className="step-hero">
          <h3><i className="fas fa-shield-alt" /> Data Quality</h3>
          <p className="step-description">
            QualityMonitorAgent runs comprehensive DQ rules, anomaly detection, and quality scoring —
            generating actionable violation reports to gate your ETL pipeline.
          </p>
        </div>

        <div className="agent-action-panel">
          <div className="agent-info">
            <i className="fas fa-robot agent-icon" />
            <div>
              <strong>Agent:</strong> QualityMonitorAgent
              <span className="capability-tags">
                <span className="cap-tag">quality_scan</span>
                <span className="cap-tag">scan_datasource_quality</span>
                <span className="cap-tag">recommend_rules</span>
              </span>
            </div>
          </div>
          <div className="quality-action-row">
            <button
              className="btn btn-primary btn-ai"
              onClick={runQualityAgent}
              disabled={opLoading.quality || wizardData.qualityStatus === 'running'}
            >
              {wizardData.qualityStatus === 'running' || opLoading.quality
                ? <><i className="fas fa-spinner fa-spin" /> Scanning…</>
                : wizardData.qualityStatus === 'completed'
                  ? <><i className="fas fa-redo" /> Re-scan Quality</>
                  : <><i className="fas fa-shield-alt" /> Run Quality Scan</>}
            </button>
            {wizardData.sourceSystem && (
              <button
                className="btn btn-secondary"
                onClick={generateDataHealthReport}
                disabled={wizardData.dataHealthLoading}
                title="Generate a comprehensive Data Health Report via DataDiscoveryAgent"
              >
                {wizardData.dataHealthLoading
                  ? <><i className="fas fa-spinner fa-spin" /> Generating…</>
                  : <><i className="fas fa-heartbeat" /> Data Health Report</>}
              </button>
            )}
          </div>
        </div>

        {wizardData.qualityStatus === 'running' && (
          <div className="agent-running-card">
            <i className="fas fa-spinner fa-spin" />
            <span>QualityMonitorAgent is running DQ rules and anomaly detection…</span>
          </div>
        )}

        {wizardData.qualityStatus === 'failed' && (
          <div className="agent-error-card">
            <i className="fas fa-exclamation-triangle" />
            <span>{wizardData.qualityError || 'Quality scan failed'}</span>
            <button className="btn btn-sm btn-warning" onClick={runQualityAgent}>
              <i className="fas fa-redo" /> Retry
            </button>
          </div>
        )}

        {qr && (
          <div className="quality-results">
            <div className="quality-kpi-row">
              <div className={`quality-score-kpi ${scoreClass}`}>
                <span className="qs-value">{score != null ? `${Math.round(score)}` : '—'}</span>
                <span className="qs-label">Quality Score</span>
                {score != null && (
                  <div className="qs-bar">
                    <div className="qs-fill" style={{ width: `${Math.min(100, score)}%` }} />
                  </div>
                )}
              </div>
              <div className="quality-kpi">
                <span className="kpi-value text-error">{anomalies}</span>
                <span className="kpi-label">Anomalies Found</span>
              </div>
              <div className="quality-kpi">
                <span className="kpi-value">{violations.length}</span>
                <span className="kpi-label">Rule Violations</span>
              </div>
              {qr.columns_checked != null && (
                <div className="quality-kpi">
                  <span className="kpi-value">{qr.columns_checked}</span>
                  <span className="kpi-label">Columns Checked</span>
                </div>
              )}
            </div>

            {violations.length > 0 && (
              <div className="quality-section">
                <h4><i className="fas fa-exclamation-triangle" /> Rule Violations</h4>
                <div className="violations-list">
                  {violations.slice(0, 15).map((v, i) => (
                    <div key={i} className={`violation-item sev-${v.severity || 'warning'}`}>
                      <i className={`fas ${v.severity === 'critical' || v.severity === 'error' ? 'fa-times-circle' : 'fa-exclamation-circle'}`} />
                      <div className="viol-body">
                        <span className="viol-rule">{v.rule_name || 'Rule'}</span>
                        <span className="viol-msg">{v.message || v.detail || v.description || ''}</span>
                      </div>
                      <span className={`sev-badge sev-${v.severity || 'warning'}`}>{v.severity || 'warning'}</span>
                    </div>
                  ))}
                  {violations.length > 15 && <p className="more-note">+{violations.length - 15} more violations</p>}
                </div>
              </div>
            )}

            {qr.anomaly_details?.length > 0 && (
              <div className="quality-section">
                <h4><i className="fas fa-search" /> Anomalies</h4>
                <div className="anomalies-list">
                  {qr.anomaly_details.slice(0, 10).map((a, i) => (
                    <div key={i} className="anomaly-item">
                      <span className="anom-col">{a.column || a.field || '—'}</span>
                      <span className="anom-desc">{a.description || a.type || a.message || '—'}</span>
                      {a.value != null && <code className="anom-val">{String(a.value)}</code>}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {qr.recommendations?.length > 0 && (
              <div className="quality-section">
                <h4><i className="fas fa-lightbulb" /> AI Recommendations</h4>
                <ul className="recommendations-list">
                  {qr.recommendations.slice(0, 8).map((r, i) => (
                    <li key={i}>{typeof r === 'string' ? r : r.recommendation || r.message || JSON.stringify(r)}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {/* Data Health Report panel */}
        {wizardData.dataHealthReport && (
          <DataHealthPanel report={wizardData.dataHealthReport} />
        )}

        {wizardData.qualityStatus === 'idle' && !qr && !wizardData.dataHealthReport && (
          <div className="agent-idle-card">
            <i className="fas fa-shield-alt" />
            <p>
              Click <strong>Run Quality Scan</strong> to have QualityMonitorAgent evaluate DQ rules,
              detect anomalies, and compute a quality score. Use <strong>Data Health Report</strong>
              for a comprehensive readiness analysis with trust and readiness scores.
            </p>
          </div>
        )}

        <SmartGuidancePanel
          context={{ step: 'quality', source: wizardData.sourceSystem?.name, qualityScore: score }}
          dismissed={smartGuidanceDismissed}
          onDismiss={() => setSmartGuidanceDismissed(true)}
        />

        {/* ── Legacy QA Tools ──────────────────────────────────────────── */}
        <details className="legacy-qa-section">
          <summary><i className="fas fa-wrench" /> Advanced / Legacy QA Tools</summary>
          <div className="legacy-qa-content">
            <div className="validation-actions">
              <button
                className="btn btn-secondary btn-sm"
                onClick={runValidation}
                disabled={opLoading.validation}
              >
                <i className="fas fa-check-double" /> {opLoading.validation ? 'Running…' : 'Run Validation Rules'}
              </button>
              <button
                className="btn btn-secondary btn-sm"
                onClick={runSodaScan}
                disabled={opLoading.validation || !wizardData.runId}
                title={!wizardData.runId ? 'Execute ETL first to enable SODA scan' : 'Run SODA data quality checks'}
              >
                <i className="fas fa-shield-alt" /> SODA Quality Scan
              </button>
            </div>
            {wizardData.validationResults.length > 0 && (
              <div className="validation-results">
                <div className="results-list">
                  {wizardData.validationResults.slice(0, 10).map((result, idx) => (
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
        </details>
      </div>
    );
  };

  // ── Step 6: Report — ReportingAgent via MCP ───────────────────────────────
  const renderReportStep = () => {
    const rr = wizardData.agentReportResult;
    const hasSummary = rr?.summary || rr?.pipeline_summary || rr?.report_summary;
    const reportId = rr?.report_id || rr?.id;

    return (
      <div className="wizard-step-content report-step">
        <div className="step-hero">
          <h3><i className="fas fa-chart-bar" /> AI Pipeline Report</h3>
          <p className="step-description">
            ReportingAgent assembles a comprehensive end-to-end report consolidating discovery,
            profiling, quality, and ETL results into a single exportable artefact.
          </p>
        </div>

        <div className="agent-action-panel">
          <div className="agent-info">
            <i className="fas fa-robot agent-icon" />
            <div>
              <strong>Agent:</strong> ReportingAgent
              <span className="capability-tags">
                <span className="cap-tag">report_generation</span>
                <span className="cap-tag">generate_report</span>
              </span>
            </div>
          </div>
          <button
            className="btn btn-primary btn-ai"
            onClick={generateAgentReport}
            disabled={opLoading.report || wizardData.agentReportStatus === 'running'}
          >
            {wizardData.agentReportStatus === 'running' || opLoading.report
              ? <><i className="fas fa-spinner fa-spin" /> Generating…</>
              : wizardData.agentReportStatus === 'completed'
                ? <><i className="fas fa-redo" /> Regenerate Report</>
                : <><i className="fas fa-file-alt" /> Generate AI Report</>}
          </button>
        </div>

        {wizardData.agentReportStatus === 'running' && (
          <div className="agent-running-card">
            <i className="fas fa-spinner fa-spin" />
            <span>ReportingAgent is assembling the pipeline report from all step artefacts…</span>
          </div>
        )}

        {wizardData.agentReportStatus === 'failed' && (
          <div className="agent-error-card">
            <i className="fas fa-exclamation-triangle" />
            <span>{wizardData.agentReportError || 'Report generation failed'}</span>
            <button className="btn btn-sm btn-warning" onClick={generateAgentReport}>
              <i className="fas fa-redo" /> Retry
            </button>
          </div>
        )}

        {rr && (
          <div className="report-results">
            {/* Report header */}
            <div className="report-header-card">
              <i className="fas fa-file-alt report-icon" />
              <div className="report-meta">
                <span className="report-title">
                  {rr.report_title || rr.title || `Migration Report — ${wizardData.workflowName || 'Pipeline'}`}
                </span>
                {reportId && <span className="report-id">ID: {reportId}</span>}
                {rr.generated_at && <span className="report-date">{new Date(rr.generated_at).toLocaleString()}</span>}
              </div>
            </div>

            {/* KPI bar */}
            <div className="report-kpi-row">
              {rr.files_discovered != null && (
                <div className="report-kpi">
                  <span className="kpi-value">{rr.files_discovered}</span>
                  <span className="kpi-label">Files Discovered</span>
                </div>
              )}
              {rr.columns_profiled != null && (
                <div className="report-kpi">
                  <span className="kpi-value">{rr.columns_profiled}</span>
                  <span className="kpi-label">Columns Profiled</span>
                </div>
              )}
              {rr.quality_score != null && (
                <div className={`report-kpi ${rr.quality_score >= 80 ? 'score-good' : rr.quality_score >= 50 ? 'score-warn' : 'score-bad'}`}>
                  <span className="kpi-value">{Math.round(rr.quality_score)}</span>
                  <span className="kpi-label">Quality Score</span>
                </div>
              )}
              {rr.records_loaded != null && (
                <div className="report-kpi">
                  <span className="kpi-value">{rr.records_loaded}</span>
                  <span className="kpi-label">Records Loaded</span>
                </div>
              )}
            </div>

            {/* Pipeline summary */}
            {(hasSummary || rr.executive_summary) && (
              <div className="report-section">
                <h4><i className="fas fa-align-left" /> Executive Summary</h4>
                <div className="report-summary-text">
                  {rr.executive_summary
                    || (typeof hasSummary === 'string' ? hasSummary : null)
                    || rr.pipeline_summary?.overview
                    || rr.report_summary?.overview
                    || JSON.stringify(hasSummary, null, 2)}
                </div>
              </div>
            )}

            {/* Step summaries */}
            {rr.step_summaries && (
              <div className="report-section">
                <h4><i className="fas fa-list-alt" /> Step Results</h4>
                <div className="step-summaries-list">
                  {Object.entries(rr.step_summaries).map(([step, summary]) => (
                    <div key={step} className={`step-summary-item ${summary.status || ''}`}>
                      <span className="ss-step">{step.charAt(0).toUpperCase() + step.slice(1)}</span>
                      <span className={`ss-status ss-${summary.status || 'unknown'}`}>
                        <i className={`fas ${summary.status === 'completed' ? 'fa-check-circle' : summary.status === 'failed' ? 'fa-times-circle' : 'fa-circle'}`} />
                        {summary.status || '—'}
                      </span>
                      {summary.message && <span className="ss-message">{summary.message}</span>}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Recommendations */}
            {rr.recommendations?.length > 0 && (
              <div className="report-section">
                <h4><i className="fas fa-star" /> Recommendations</h4>
                <ul className="recommendations-list">
                  {rr.recommendations.slice(0, 10).map((r, i) => (
                    <li key={i}>{typeof r === 'string' ? r : r.recommendation || r.message || JSON.stringify(r)}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Raw JSON for developers */}
            {import.meta.env.DEV && (
              <details className="debug-panel" style={{ marginTop: 16 }}>
                <summary style={{ cursor: 'pointer', color: '#999', fontSize: '0.85em' }}>🛠️ Full Report JSON</summary>
                <pre className="schema-preview" style={{ fontSize: '0.75em', maxHeight: 400, overflowY: 'auto' }}>
                  {JSON.stringify(rr, null, 2)}
                </pre>
              </details>
            )}
          </div>
        )}

        {/* Pipeline summary when report not yet generated */}
        {wizardData.agentReportStatus === 'idle' && !rr && (
          <div className="report-pipeline-summary">
            <h4><i className="fas fa-list-check" /> Pipeline Status</h4>
            <div className="pipeline-status-grid">
              <div className={`pipeline-step-status ${wizardData.discoveryStatus === 'completed' ? 'done' : 'pending'}`}>
                <i className={`fas ${wizardData.discoveryStatus === 'completed' ? 'fa-check-circle' : 'fa-circle'}`} />
                <span>Discover</span>
              </div>
              <div className={`pipeline-step-status ${wizardData.profileStatus === 'completed' ? 'done' : 'pending'}`}>
                <i className={`fas ${wizardData.profileStatus === 'completed' ? 'fa-check-circle' : 'fa-circle'}`} />
                <span>Profile</span>
              </div>
              <div className={`pipeline-step-status ${wizardData.qualityStatus === 'completed' ? 'done' : 'pending'}`}>
                <i className={`fas ${wizardData.qualityStatus === 'completed' ? 'fa-check-circle' : 'fa-circle'}`} />
                <span>Quality</span>
              </div>
              <div className={`pipeline-step-status ${wizardData.migrationStatus === 'completed' ? 'done' : 'pending'}`}>
                <i className={`fas ${wizardData.migrationStatus === 'completed' ? 'fa-check-circle' : 'fa-circle'}`} />
                <span>ETL</span>
              </div>
            </div>
            <p className="report-idle-hint">
              Click <strong>Generate AI Report</strong> to have ReportingAgent compile a comprehensive
              pipeline report. Run the Discover, Profile, Quality, and ETL steps first for the richest report.
            </p>
          </div>
        )}

        <SmartGuidancePanel
          context={{ step: 'report', source: wizardData.sourceSystem?.name, reportGenerated: !!rr }}
          dismissed={smartGuidanceDismissed}
          onDismiss={() => setSmartGuidanceDismissed(true)}
        />

        {/* NCR export — available when validation issues exist */}
        {(wizardData.qualityChecks.failed > 0 || wizardData.qualityChecks.warnings > 0) && (
          <div className="ncr-export-section">
            <div className="ncr-export-info">
              <i className="fas fa-exclamation-triangle ncr-icon" />
              <div>
                <strong>Non-Conformance Report</strong>
                <p>
                  {wizardData.qualityChecks.failed > 0 && (
                    <span className="ncr-fail-count">{wizardData.qualityChecks.failed} failed check(s)</span>
                  )}
                  {wizardData.qualityChecks.failed > 0 && wizardData.qualityChecks.warnings > 0 && ' · '}
                  {wizardData.qualityChecks.warnings > 0 && (
                    <span className="ncr-warn-count">{wizardData.qualityChecks.warnings} warning(s)</span>
                  )}
                  {' '}detected. Export for traceability.
                </p>
              </div>
            </div>
            <button className="btn btn-ncr-export" onClick={generateNcr} title="Export NCR as Excel">
              <i className="fas fa-file-excel" /> Export NCR
            </button>
          </div>
        )}
      </div>
    );
  };

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

          {/* ── Semantic insights summary (from DataProfilerAgent) ── */}
          {wizardData.semanticProfile?.summary && (
            <div className="sem-summary-row">
              <span className="sem-summary-item" title="Dominant entity class in this dataset">
                <i className="fas fa-tags" />
                {wizardData.semanticProfile.summary.top_entity_class || '—'} entity
              </span>
              <span className="sem-summary-item" title="Cross-column relationships detected">
                <i className="fas fa-link" />
                {wizardData.semanticProfile.summary.relationship_count || 0} relationship
                {wizardData.semanticProfile.summary.relationship_count !== 1 ? 's' : ''}
              </span>
              <span className="sem-summary-item" title="Columns with high-confidence semantic classification">
                <i className="fas fa-check-circle" />
                {wizardData.semanticProfile.summary.high_confidence_semantics || 0} confident columns
              </span>
            </div>
          )}
          
          <div className="summary-actions">
            <a
              href={`#/data-discovery${wizardData.sourceSystem?.id ? `?source=${encodeURIComponent(wizardData.sourceSystem.id)}` : ''}`}
              className="view-details-link"
              target="_blank"
              rel="noopener noreferrer"
            >
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
          
          <div className="workflow-method workflow-method--template-featured">
            <span className="method-badge template-badge">
              <i className="fas fa-layer-group" /> Use Template
            </span>
            {wizardData.selectedTemplate && (
              <span className="template-active-badge">
                <i className="fas fa-check-circle" /> {wizardData.selectedTemplate.name} applied
              </span>
            )}
            <div className="method-content">
              <div className="method-header">
                <i className="fas fa-file-alt" />
                <h5>2. Use a Template</h5>
              </div>
              <p>Apply pre-configured mappings for common migration scenarios (e.g., Teamcenter to SAP, Excel to Database).</p>
              <div className="template-browser-actions">
                <button
                  className="btn btn-template-browse"
                  onClick={() => setShowTemplateBrowser(p => !p)}
                  title="Browse available mapping templates"
                >
                  <i className={`fas fa-${showTemplateBrowser ? 'chevron-up' : 'th-large'}`} />
                  {showTemplateBrowser ? 'Close Browser' : 'Browse Templates'}
                  <span className="template-count-pill">{mappingTemplates.length}</span>
                </button>
                {wizardData.selectedTemplate && (
                  <button
                    className="btn btn-sm btn-outline-danger"
                    style={{ marginLeft: 8, fontSize: 11, padding: '3px 8px' }}
                    onClick={() => setWizardData(p => ({ ...p, selectedTemplate: null, fieldMappings: [] }))}
                    title="Remove applied template"
                  >
                    <i className="fas fa-times" /> Clear
                  </button>
                )}
              </div>
              {showTemplateBrowser && (
                <div className="template-browser-panel">
                  <div className="template-cards-grid">
                    {mappingTemplates.map(t => {
                      const fieldCount = t.field_mappings?.length ?? 0;
                      const isActive = wizardData.selectedTemplate?.id === t.id;
                      return (
                        <div
                          key={t.id}
                          className={`template-card${isActive ? ' template-card--active' : ''}`}
                          title={t.description || t.name}
                        >
                          <div className="template-card-header">
                            <i className="fas fa-file-import" />
                            <span className="template-card-name">{t.name}</span>
                            {isActive && <i className="fas fa-check-circle template-card-check" />}
                          </div>
                          {t.description && (
                            <p className="template-card-desc">{t.description}</p>
                          )}
                          <div className="template-card-footer">
                            <span className="template-field-count">
                              <i className="fas fa-columns" /> {fieldCount} field{fieldCount !== 1 ? 's' : ''}
                            </span>
                            <button
                              className={`btn btn-sm ${isActive ? 'btn-success' : 'btn-template-apply'}`}
                              disabled={isActive}
                              onClick={() => {
                                applyTemplate(t);
                                setShowTemplateBrowser(false);
                                toast.success(`Template "${t.name}" applied — ${fieldCount} field mappings loaded!`, 4000);
                              }}
                            >
                              {isActive ? <><i className="fas fa-check" /> Applied</> : <><i className="fas fa-bolt" /> Apply</>}
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
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
              {sourceFields.slice(0, 15).map((field, idx) => {
                const sem = wizardData.semanticProfile?.column_semantics?.find(
                  cs => cs.column === field || cs.canonical_name === field
                );
                const titleParts = ['Click to add mapping'];
                if (sem) {
                  titleParts.push(`Role: ${sem.semantic_role}`);
                  if (sem.entity_hint) titleParts.push(`Entity: ${sem.entity_hint}`);
                  titleParts.push(`Confidence: ${Math.round((sem.confidence || 0) * 100)}%`);
                }
                return (
                  <span
                    key={idx}
                    className={`field-tag source${sem?.semantic_role ? ` sem-${sem.semantic_role}` : ''}`}
                    title={titleParts.join(' · ')}
                    onClick={() => addFieldMapping({
                      source_field: field,
                      target_field: sem?.canonical_name || '',
                      transformation: null
                    })}
                  >
                    {field}
                    {sem?.semantic_role && (
                      <span className="field-sem-badge">{sem.semantic_role}</span>
                    )}
                  </span>
                );
              })}
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
        fieldMappings={wizardData.fieldMappings}
        onPhaseChange={phase => setWizardData(prev => ({ ...prev, activeRulePhase: phase }))}
        onAddRule={addRule}
        onRemoveRule={removeRule}
        onUpdateRule={updateRule}
        onAddRules={addRules}
      />
      {/* ── Execute ETL Pipeline ────────────────────────────────────────── */}
      <div className="etl-execute-card">
        <h4><i className="fas fa-rocket" /> Execute ETL Pipeline</h4>
        <p className="etl-execute-desc">
          Once field mappings are configured above, execute the Extract → Transform → Load pipeline.
        </p>

        {/* Pre-execution summary */}
        {wizardData.migrationStatus === 'pending' && (
          <div className="etl-pre-exec">
            <div className="etl-summary-row">
              <span><i className="fas fa-map-signs" /> {wizardData.fieldMappings.length} mapping(s) defined</span>
              {wizardData.qualityResult?.quality_score != null && (
                <span>
                  <i className="fas fa-shield-alt" /> Quality: {Math.round(wizardData.qualityResult.quality_score)}
                </span>
              )}
              {wizardData.profileResult && (
                <span><i className="fas fa-check-circle" /> Profile complete</span>
              )}
            </div>
            <button
              className="btn btn-primary btn-lg btn-execute"
              onClick={executeMigration}
              disabled={opLoading.execute || wizardData.fieldMappings.length === 0}
            >
              <i className="fas fa-play" /> {opLoading.execute ? 'Executing…' : 'Start ETL Pipeline'}
            </button>
            <button
              className="btn btn-secondary"
              onClick={testTransformation}
              disabled={opLoading.validation || !wizardData.fieldMappings.length}
              title="Test transformation rules without running the full pipeline"
            >
              <i className="fas fa-flask" /> Test Transform
            </button>
            {wizardData.fieldMappings.length === 0 && (
              <p className="execute-warning">Define at least one field mapping above before executing.</p>
            )}
          </div>
        )}

        {/* Progress */}
        {wizardData.migrationStatus === 'running' && (
          <div className="migration-progress">
            <div className="progress-bar">
              <div
                className="progress-fill"
                style={{ width: wizardData.totalRecords > 0 ? `${Math.round((wizardData.processedRecords / wizardData.totalRecords) * 100)}%` : '0%' }}
              />
            </div>
            <div className="progress-text">
              <i className="fas fa-spinner fa-spin" /> {wizardData.migrationStep || 'Processing…'}
            </div>
            <div className="migration-steps-list">
              {[
                { label: 'Create Run',          threshold: 1 },
                { label: 'Stage Records',       threshold: 2 },
                { label: 'Transform Data',      threshold: 3 },
                { label: 'SODA Scan & Validate',threshold: 4 },
                { label: 'Sync to Neo4j',       threshold: 5 },
              ].map(({ label, threshold }) => (
                <div
                  key={label}
                  className={`migration-step-item ${wizardData.processedRecords >= threshold ? 'complete' : wizardData.processedRecords >= threshold - 1 ? 'active' : ''}`}
                >
                  <i className="fas fa-circle" /> {label}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Completion */}
        {wizardData.migrationStatus === 'completed' && (
          <div className="execute-complete">
            <i className="fas fa-check-circle" />
            <div>
              <strong>ETL Pipeline Complete!</strong>
              <span>
                {wizardData.processedRecords} record(s) processed
                {wizardData.nodesCreated > 0 && ` · ${wizardData.nodesCreated} node(s) created`}.
                Proceed to <strong>Report</strong>.
              </span>
            </div>
          </div>
        )}

        {/* Failure */}
        {wizardData.migrationStatus === 'failed' && (
          <div className="execute-failed">
            <i className="fas fa-times-circle" />
            <div className="error-list">
              {wizardData.errors.map((e, i) => <div key={i} className="error-item">{e}</div>)}
            </div>
            <button
              className="btn btn-sm btn-warning"
              onClick={() => setWizardData(prev => ({ ...prev, migrationStatus: 'pending', errors: [] }))}
            >
              <i className="fas fa-redo" /> Retry
            </button>
          </div>
        )}
      </div>
    </div>
  );
  };


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
        
        {currentStep < steps.length ? (
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
            disabled={wizardData.agentReportStatus !== 'completed' && wizardData.migrationStatus !== 'completed'}
          >
            Finish <i className="fas fa-check" />
          </button>
        )}
      </div>
    </div>
  );
};

export default MigrationWizard;
