/**
 * Data Pipeline Wizard Component
 * 
 * Clear visual branching for structured vs unstructured data pipelines.
 * Guides users through pipeline selection and configuration.
 * 
 * Pipeline Types:
 * - Unstructured: search_index, knowledge_graph (OpenSearch + Neo4j)
 * - Structured: database_migration, plm_graph_sync (Postgres + Neo4j)
 */

import { useState, useEffect, useCallback } from 'react';
import API_CONFIG from '../config/api-config';
import { etlWorkflowService } from '../services/etl-workflow-service';
import './data-pipeline-wizard.css';

const API_BASE = API_CONFIG.API_BASE_URL || '';

const PHASE_AGENT_FALLBACK = {
  connect: { agent: 'etl_orchestrator', task: 'pipeline_orchestration', ruleEngineEnabled: false },
  discover: { agent: 'data_discovery_agent', task: 'data_discovery', ruleEngineEnabled: false },
  profile: { agent: 'data_analyst', task: 'data_analysis', ruleEngineEnabled: true },
  map: { agent: 'task_decomposer', task: 'workflow_decomposition', ruleEngineEnabled: false },
  validate: { agent: 'quality_monitor', task: 'data_quality_scan', ruleEngineEnabled: true },
  execute: { agent: 'etl_orchestrator', task: 'pipeline_orchestration', ruleEngineEnabled: false },
};

const normalizeAgenticPlan = (result, executionParams = {}) => {
  const backendPlan = result?.agentic_plan;
  if (backendPlan && Array.isArray(backendPlan.phases) && backendPlan.phases.length > 0) {
    return backendPlan;
  }

  const phases = Array.isArray(executionParams.migration_phases) && executionParams.migration_phases.length > 0
    ? executionParams.migration_phases
    : ['connect', 'discover', 'profile', 'map', 'validate', 'execute'];

  return {
    standard: executionParams.migration_standard || 'plm-governed-sequenced-v1',
    phases: phases.map((phase, index) => {
      const key = String(phase).toLowerCase();
      const fallback = PHASE_AGENT_FALLBACK[key] || PHASE_AGENT_FALLBACK.execute;
      return {
        order: index + 1,
        phase: key,
        agent: fallback.agent,
        task: fallback.task,
        status: 'planned',
        rule_engine: {
          enabled: Boolean(fallback.ruleEngineEnabled),
          scope: key === 'profile' ? 'profiling' : key === 'validate' ? 'validation' : 'none',
        },
      };
    }),
  };
};

const deriveEndpointId = (prefix, config = {}) => {
  const explicit = config.id || config.name || config.sourceId || config.targetId;
  if (explicit) return String(explicit);

  const host = config.host || config.hostname || config.server;
  if (host) return `${prefix}_${String(host).replace(/\s+/g, '_')}`;

  const path = config.path || config.directory || config.file_path;
  if (path) return `${prefix}_${String(path).replace(/[^a-zA-Z0-9_]/g, '_')}`;

  return `${prefix}_default`;
};

// Pipeline definitions with clear categorization
const PIPELINE_BRANCHES = {
  unstructured: {
    title: 'Unstructured Data',
    description: 'Process files, documents, CAD data, logs, and media',
    icon: 'fa-file-alt',
    color: '#2196F3',
    pipelines: [
      {
        id: 'search_index',
        name: 'Search Index Pipeline',
        description: 'Ingest files into OpenSearch for full-text and semantic search',
        icon: 'fa-search',
        targets: ['OpenSearch'],
        features: ['Full-text Search', 'Semantic Search', 'Vector Embeddings', 'Hybrid Search'],
        searchModes: ['semantic', 'vector', 'hybrid']
      },
      {
        id: 'knowledge_graph',
        name: 'Knowledge Graph Pipeline',
        description: 'Extract entities and relationships into Neo4j graph database',
        icon: 'fa-project-diagram',
        targets: ['Neo4j'],
        features: ['Entity Extraction', 'Relationship Mapping', 'Graph Queries', 'GraphRAG']
      }
    ]
  },
  structured: {
    title: 'Structured Data',
    description: 'Migrate relational databases, PLM systems, and ERP data',
    icon: 'fa-database',
    color: '#FF9800',
    pipelines: [
      {
        id: 'database_migration',
        name: 'Database Migration Pipeline',
        description: 'Migrate relational data between databases with schema mapping',
        icon: 'fa-exchange-alt',
        targets: ['PostgreSQL', 'MySQL', 'Oracle'],
        features: ['Schema Mapping', 'Incremental Sync', 'Data Validation', 'Rollback Support']
      },
      {
        id: 'plm_graph_sync',
        name: 'PLM to Graph Pipeline',
        description: 'Sync PLM/ERP data to Neo4j with BOM relationships',
        icon: 'fa-sitemap',
        targets: ['Neo4j'],
        features: ['BOM Hierarchy', 'Part Relationships', 'Change Orders', 'Revision History']
      }
    ]
  }
};

// Supported file categories for unstructured pipelines
const FILE_CATEGORIES = {
  document: { icon: 'fa-file-pdf', label: 'Documents', examples: 'PDF, DOC, XLS, PPT' },
  cad: { icon: 'fa-cube', label: 'CAD Files', examples: 'STEP, IGES, DXF, CATIA' },
  simulation: { icon: 'fa-wave-square', label: 'Simulation', examples: 'NASTRAN, ANSYS, ABAQUS' },
  data: { icon: 'fa-table', label: 'Data Files', examples: 'JSON, XML, CSV, YAML' },
  text: { icon: 'fa-file-alt', label: 'Text Files', examples: 'TXT, LOG, MD, RST' },
  image: { icon: 'fa-image', label: 'Images', examples: 'PNG, JPG, TIFF, SVG' },
  video: { icon: 'fa-video', label: 'Video', examples: 'MP4, AVI, MOV, MKV' },
  archive: { icon: 'fa-file-archive', label: 'Archives', examples: 'ZIP, TAR, 7Z, RAR' }
};

/**
 * Step indicator component
 */
function StepIndicator({ steps, currentStep }) {
  return (
    <div className="wizard-steps">
      {steps.map((step, index) => (
        <div 
          key={step.id}
          className={`wizard-step ${index < currentStep ? 'completed' : ''} ${index === currentStep ? 'active' : ''}`}
        >
          <div className="step-number">
            {index < currentStep ? <i className="fas fa-check" /> : index + 1}
          </div>
          <div className="step-label">{step.label}</div>
          {index < steps.length - 1 && <div className="step-connector" />}
        </div>
      ))}
    </div>
  );
}

/**
 * Branch selection step - Structured vs Unstructured
 */
function BranchSelectionStep({ selectedBranch, onSelect }) {
  return (
    <div className="wizard-content branch-selection">
      <h2>Select Data Type</h2>
      <p className="step-description">Choose the type of data pipeline you want to create</p>
      
      <div className="branch-cards">
        {Object.entries(PIPELINE_BRANCHES).map(([key, branch]) => (
          <div 
            key={key}
            className={`branch-card ${selectedBranch === key ? 'selected' : ''}`}
            onClick={() => onSelect(key)}
            style={{ '--branch-color': branch.color }}
          >
            <div className="branch-icon">
              <i className={`fas ${branch.icon}`} />
            </div>
            <h3>{branch.title}</h3>
            <p>{branch.description}</p>
            <div className="branch-pipelines">
              {branch.pipelines.map(p => (
                <span key={p.id} className="pipeline-badge">
                  <i className={`fas ${p.icon}`} /> {p.name.split(' ')[0]}
                </span>
              ))}
            </div>
            {selectedBranch === key && (
              <div className="selected-indicator">
                <i className="fas fa-check-circle" />
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Pipeline type selection step
 */
function PipelineSelectionStep({ branch, selectedPipeline, onSelect }) {
  const branchData = PIPELINE_BRANCHES[branch];
  
  return (
    <div className="wizard-content pipeline-selection">
      <h2>Select Pipeline Type</h2>
      <p className="step-description">Choose the specific pipeline for your {branchData.title.toLowerCase()} workflow</p>
      
      <div className="pipeline-cards">
        {branchData.pipelines.map(pipeline => (
          <div 
            key={pipeline.id}
            className={`pipeline-card ${selectedPipeline === pipeline.id ? 'selected' : ''}`}
            onClick={() => onSelect(pipeline.id)}
          >
            <div className="pipeline-header" style={{ '--pipeline-color': branchData.color }}>
              <i className={`fas ${pipeline.icon}`} />
              <h3>{pipeline.name}</h3>
            </div>
            <p className="pipeline-description">{pipeline.description}</p>
            
            <div className="pipeline-targets">
              <span className="label">Targets:</span>
              {pipeline.targets.map(t => (
                <span key={t} className="target-badge">{t}</span>
              ))}
            </div>
            
            <div className="pipeline-features">
              <span className="label">Features:</span>
              <ul>
                {pipeline.features.map(f => (
                  <li key={f}><i className="fas fa-check" /> {f}</li>
                ))}
              </ul>
            </div>
            
            {pipeline.searchModes && (
              <div className="pipeline-search-modes">
                <span className="label">Search Modes:</span>
                <div className="search-mode-badges">
                  {pipeline.searchModes.map(m => (
                    <span key={m} className={`search-mode-badge mode-${m}`}>{m}</span>
                  ))}
                </div>
              </div>
            )}
            
            {selectedPipeline === pipeline.id && (
              <div className="selected-indicator">
                <i className="fas fa-check-circle" />
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Source configuration step
 */
function SourceConfigStep({ branch, pipeline: _pipeline, config, onChange }) {
  const isUnstructured = branch === 'unstructured';
  
  const [filePatterns, setFilePatterns] = useState([]);
  const [loadingPatterns, setLoadingPatterns] = useState(false);
  
  // Load file patterns from config API
  useEffect(() => {
    if (isUnstructured) {
      setLoadingPatterns(true);
      fetch(`${API_BASE}${API_CONFIG.ENDPOINTS.FILE_PATTERNS}`)
        .then(res => {
          if (!res.ok) throw new Error(`Failed to load patterns: ${res.status}`);
          return res.json();
        })
        .then(data => {
          setFilePatterns(Array.isArray(data) ? data : []);
          setLoadingPatterns(false);
        })
        .catch(() => {
          setFilePatterns([]);
          setLoadingPatterns(false);
        });
    }
  }, [isUnstructured]);
  
  // Group patterns by category
  const patternsByCategory = filePatterns.reduce((acc, p) => {
    if (!acc[p.category]) acc[p.category] = [];
    acc[p.category].push(p);
    return acc;
  }, {});
  
  return (
    <div className="wizard-content source-config">
      <h2>Configure Source</h2>
      <p className="step-description">
        {isUnstructured 
          ? 'Configure file source location and file types to process'
          : 'Configure database connection and tables to migrate'}
      </p>
      
      {isUnstructured ? (
        <div className="source-form unstructured-source">
          <div className="form-group">
            <label>Source Path</label>
            <div className="input-with-icon">
              <i className="fas fa-folder" />
              <input
                type="text"
                placeholder="/data/unstructured or ${UNSTRUCTURED_DATA_PATH}"
                value={config.sourcePath || ''}
                onChange={(e) => onChange({ ...config, sourcePath: e.target.value })}
              />
            </div>
            <span className="form-hint">Use environment variable ${'{UNSTRUCTURED_DATA_PATH}'} for production</span>
          </div>
          
          <div className="form-group">
            <label>File Categories to Process</label>
            {loadingPatterns ? (
              <div className="loading-indicator"><i className="fas fa-spinner fa-spin" /> Loading patterns...</div>
            ) : (
              <div className="category-grid">
                {Object.entries(FILE_CATEGORIES).map(([catKey, cat]) => {
                  const patterns = patternsByCategory[catKey] || [];
                  const isSelected = config.categories?.includes(catKey);
                  return (
                    <div 
                      key={catKey}
                      className={`category-card ${isSelected ? 'selected' : ''}`}
                      onClick={() => {
                        const cats = config.categories || [];
                        const newCats = isSelected 
                          ? cats.filter(c => c !== catKey)
                          : [...cats, catKey];
                        onChange({ ...config, categories: newCats });
                      }}
                    >
                      <i className={`fas ${cat.icon}`} />
                      <span className="cat-label">{cat.label}</span>
                      <span className="cat-examples">{cat.examples}</span>
                      <span className="pattern-count">{patterns.length} patterns</span>
                      {isSelected && <i className="fas fa-check selected-check" />}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
          
          <div className="form-group">
            <label>Extraction Settings</label>
            <div className="extraction-settings">
              <div className="setting-row">
                <label>Chunk Size</label>
                <input
                  type="number"
                  value={config.chunkSize || 1000}
                  onChange={(e) => onChange({ ...config, chunkSize: parseInt(e.target.value) })}
                />
                <span className="unit">tokens</span>
              </div>
              <div className="setting-row">
                <label>Overlap</label>
                <input
                  type="number"
                  value={config.overlap || 200}
                  onChange={(e) => onChange({ ...config, overlap: parseInt(e.target.value) })}
                />
                <span className="unit">tokens</span>
              </div>
              <div className="setting-row checkbox">
                <input
                  type="checkbox"
                  id="extractMetadata"
                  checked={config.extractMetadata !== false}
                  onChange={(e) => onChange({ ...config, extractMetadata: e.target.checked })}
                />
                <label htmlFor="extractMetadata">Extract file metadata</label>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="source-form structured-source">
          <div className="form-group">
            <label>Connection String</label>
            <div className="input-with-icon">
              <i className="fas fa-plug" />
              <input
                type="text"
                placeholder="postgresql://user:pass@host:5432/db or ${SOURCE_DATABASE_URL}"
                value={config.connectionString || ''}
                onChange={(e) => onChange({ ...config, connectionString: e.target.value })}
              />
            </div>
            <span className="form-hint">Use environment variable ${'{SOURCE_DATABASE_URL}'} for production</span>
          </div>
          
          <div className="form-group">
            <label>Schema</label>
            <input
              type="text"
              placeholder="public"
              value={config.schema || 'public'}
              onChange={(e) => onChange({ ...config, schema: e.target.value })}
            />
          </div>
          
          <div className="form-group">
            <label>Tables (comma-separated, leave empty for all)</label>
            <input
              type="text"
              placeholder="parts, assemblies, documents"
              value={config.tables || ''}
              onChange={(e) => onChange({ ...config, tables: e.target.value })}
            />
          </div>
          
          <div className="form-group">
            <label>Sync Settings</label>
            <div className="sync-settings">
              <div className="setting-row checkbox">
                <input
                  type="checkbox"
                  id="incremental"
                  checked={config.incremental !== false}
                  onChange={(e) => onChange({ ...config, incremental: e.target.checked })}
                />
                <label htmlFor="incremental">Enable incremental sync</label>
              </div>
              {config.incremental !== false && (
                <div className="setting-row">
                  <label>Watermark Column</label>
                  <input
                    type="text"
                    placeholder="updated_at"
                    value={config.watermarkColumn || 'updated_at'}
                    onChange={(e) => onChange({ ...config, watermarkColumn: e.target.value })}
                  />
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * Target configuration step
 */
function TargetConfigStep({ branch, pipeline, config, onChange }) {
  const pipelineData = PIPELINE_BRANCHES[branch]?.pipelines.find(p => p.id === pipeline);
  const targetType = pipelineData?.targets[0] || 'Unknown';
  
  return (
    <div className="wizard-content target-config">
      <h2>Configure Target</h2>
      <p className="step-description">Configure the destination for your processed data</p>
      
      <div className="target-type-indicator">
        <i className={`fas ${targetType === 'OpenSearch' ? 'fa-search' : targetType === 'Neo4j' ? 'fa-project-diagram' : 'fa-database'}`} />
        <span>Target: {targetType}</span>
      </div>
      
      {targetType === 'OpenSearch' && (
        <div className="target-form opensearch-target">
          <div className="form-group">
            <label>OpenSearch URL</label>
            <div className="input-with-icon">
              <i className="fas fa-link" />
              <input
                type="text"
                placeholder="http://localhost:9200 or ${OPENSEARCH_URL}"
                value={config.url || ''}
                onChange={(e) => onChange({ ...config, url: e.target.value })}
              />
            </div>
          </div>
          
          <div className="form-group">
            <label>Index Prefix</label>
            <input
              type="text"
              placeholder="unstructured_"
              value={config.indexPrefix || 'unstructured_'}
              onChange={(e) => onChange({ ...config, indexPrefix: e.target.value })}
            />
          </div>
          
          <div className="form-group">
            <label>Vector Settings</label>
            <div className="vector-settings">
              <div className="setting-row checkbox">
                <input
                  type="checkbox"
                  id="enableVectors"
                  checked={config.enableVectors !== false}
                  onChange={(e) => onChange({ ...config, enableVectors: e.target.checked })}
                />
                <label htmlFor="enableVectors">Enable vector embeddings</label>
              </div>
              {config.enableVectors !== false && (
                <>
                  <div className="setting-row">
                    <label>Embedding Model</label>
                    <select
                      value={config.embeddingModel || 'all-MiniLM-L6-v2'}
                      onChange={(e) => onChange({ ...config, embeddingModel: e.target.value })}
                    >
                      <option value="all-MiniLM-L6-v2">all-MiniLM-L6-v2 (384 dim)</option>
                      <option value="all-mpnet-base-v2">all-mpnet-base-v2 (768 dim)</option>
                      <option value="text-embedding-ada-002">OpenAI ada-002 (1536 dim)</option>
                    </select>
                  </div>
                  <div className="search-modes-config">
                    <label>Enabled Search Modes</label>
                    <div className="mode-toggles">
                      {['semantic', 'vector', 'hybrid'].map(mode => (
                        <label key={mode} className="mode-toggle">
                          <input
                            type="checkbox"
                            checked={config.searchModes?.includes(mode) ?? true}
                            onChange={(e) => {
                              const modes = config.searchModes || ['semantic', 'vector', 'hybrid'];
                              const newModes = e.target.checked
                                ? [...modes, mode]
                                : modes.filter(m => m !== mode);
                              onChange({ ...config, searchModes: newModes });
                            }}
                          />
                          <span className={`mode-label mode-${mode}`}>{mode}</span>
                        </label>
                      ))}
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}
      
      {targetType === 'Neo4j' && (
        <div className="target-form neo4j-target">
          <div className="form-group">
            <label>Neo4j URI</label>
            <div className="input-with-icon">
              <i className="fas fa-link" />
              <input
                type="text"
                placeholder="bolt://localhost:7687 or ${NEO4J_URI}"
                value={config.uri || ''}
                onChange={(e) => onChange({ ...config, uri: e.target.value })}
              />
            </div>
          </div>
          
          <div className="form-group">
            <label>Database</label>
            <input
              type="text"
              placeholder="neo4j"
              value={config.database || 'neo4j'}
              onChange={(e) => onChange({ ...config, database: e.target.value })}
            />
          </div>
          
          <div className="form-group">
            <label>Load Settings</label>
            <div className="load-settings">
              <div className="setting-row checkbox">
                <input
                  type="checkbox"
                  id="createConstraints"
                  checked={config.createConstraints !== false}
                  onChange={(e) => onChange({ ...config, createConstraints: e.target.checked })}
                />
                <label htmlFor="createConstraints">Create constraints automatically</label>
              </div>
              <div className="setting-row checkbox">
                <input
                  type="checkbox"
                  id="mergeNodes"
                  checked={config.mergeNodes !== false}
                  onChange={(e) => onChange({ ...config, mergeNodes: e.target.checked })}
                />
                <label htmlFor="mergeNodes">Merge existing nodes (upsert)</label>
              </div>
              <div className="setting-row">
                <label>Batch Size</label>
                <input
                  type="number"
                  value={config.batchSize || 500}
                  onChange={(e) => onChange({ ...config, batchSize: parseInt(e.target.value) })}
                />
              </div>
            </div>
          </div>
        </div>
      )}
      
      {(targetType === 'PostgreSQL' || targetType === 'MySQL' || targetType === 'Oracle') && (
        <div className="target-form database-target">
          <div className="form-group">
            <label>Target Connection String</label>
            <div className="input-with-icon">
              <i className="fas fa-plug" />
              <input
                type="text"
                placeholder="postgresql://user:pass@host:5432/db or ${TARGET_DATABASE_URL}"
                value={config.connectionString || ''}
                onChange={(e) => onChange({ ...config, connectionString: e.target.value })}
              />
            </div>
          </div>
          
          <div className="form-group">
            <label>Target Schema</label>
            <input
              type="text"
              placeholder="public"
              value={config.schema || 'public'}
              onChange={(e) => onChange({ ...config, schema: e.target.value })}
            />
          </div>
          
          <div className="form-group">
            <label>Load Settings</label>
            <div className="load-settings">
              <div className="setting-row checkbox">
                <input
                  type="checkbox"
                  id="createTables"
                  checked={config.createTables !== false}
                  onChange={(e) => onChange({ ...config, createTables: e.target.checked })}
                />
                <label htmlFor="createTables">Create tables if not exist</label>
              </div>
              <div className="setting-row checkbox">
                <input
                  type="checkbox"
                  id="truncateBeforeLoad"
                  checked={config.truncateBeforeLoad === true}
                  onChange={(e) => onChange({ ...config, truncateBeforeLoad: e.target.checked })}
                />
                <label htmlFor="truncateBeforeLoad">Truncate tables before load</label>
              </div>
              <div className="setting-row">
                <label>Batch Size</label>
                <input
                  type="number"
                  value={config.batchSize || 1000}
                  onChange={(e) => onChange({ ...config, batchSize: parseInt(e.target.value) })}
                />
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * Review and create step
 */
function ReviewStep({ branch, pipeline, sourceConfig, targetConfig, workflowName, onNameChange }) {
  const branchData = PIPELINE_BRANCHES[branch];
  const pipelineData = branchData?.pipelines.find(p => p.id === pipeline);
  
  return (
    <div className="wizard-content review-step">
      <h2>Review Pipeline Configuration</h2>
      <p className="step-description">Review your configuration and create the pipeline</p>
      
      <div className="form-group workflow-name">
        <label>Pipeline Name</label>
        <input
          type="text"
          placeholder="My Data Pipeline"
          value={workflowName}
          onChange={(e) => onNameChange(e.target.value)}
        />
      </div>
      
      <div className="review-summary">
        <div className="summary-section">
          <h4><i className="fas fa-code-branch" /> Pipeline Type</h4>
          <div className="summary-content">
            <div className="summary-item">
              <span className="label">Branch:</span>
              <span className="value">{branchData?.title}</span>
            </div>
            <div className="summary-item">
              <span className="label">Pipeline:</span>
              <span className="value">{pipelineData?.name}</span>
            </div>
          </div>
        </div>
        
        <div className="summary-section">
          <h4><i className="fas fa-upload" /> Source Configuration</h4>
          <div className="summary-content">
            {Object.entries(sourceConfig).map(([key, value]) => (
              <div key={key} className="summary-item">
                <span className="label">{key}:</span>
                <span className="value">
                  {Array.isArray(value) ? value.join(', ') : String(value)}
                </span>
              </div>
            ))}
          </div>
        </div>
        
        <div className="summary-section">
          <h4><i className="fas fa-download" /> Target Configuration</h4>
          <div className="summary-content">
            {Object.entries(targetConfig).map(([key, value]) => (
              <div key={key} className="summary-item">
                <span className="label">{key}:</span>
                <span className="value">
                  {Array.isArray(value) ? value.join(', ') : String(value)}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * Main Data Pipeline Wizard Component
 */
export default function DataPipelineWizard({ onComplete, onCancel }) {
  const [currentStep, setCurrentStep] = useState(0);
  const [selectedBranch, setSelectedBranch] = useState(null);
  const [selectedPipeline, setSelectedPipeline] = useState(null);
  const [sourceConfig, setSourceConfig] = useState({});
  const [targetConfig, setTargetConfig] = useState({});
  const [workflowName, setWorkflowName] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState(null);
  const [createdWorkflow, setCreatedWorkflow] = useState(null);
  
  const steps = [
    { id: 'branch', label: 'Data Type' },
    { id: 'pipeline', label: 'Pipeline' },
    { id: 'source', label: 'Source' },
    { id: 'target', label: 'Target' },
    { id: 'review', label: 'Review' }
  ];

  useEffect(() => {
    setCreatedWorkflow(null);
  }, [workflowName, selectedBranch, selectedPipeline, sourceConfig, targetConfig]);
  
  const canProceed = () => {
    switch (currentStep) {
      case 0: return selectedBranch !== null;
      case 1: return selectedPipeline !== null;
      case 2: return Object.keys(sourceConfig).length > 0;
      case 3: return Object.keys(targetConfig).length > 0;
      case 4: return workflowName.trim().length > 0;
      default: return false;
    }
  };
  
  const handleNext = () => {
    if (currentStep < steps.length - 1) {
      setCurrentStep(currentStep + 1);
    }
  };
  
  const handleBack = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    }
  };
  
  const handleCreate = useCallback(async () => {
    setCreatedWorkflow(null);
    setIsCreating(true);
    setError(null);
    
    try {
      const branchTitle = PIPELINE_BRANCHES[selectedBranch].title;
      const goal = `${branchTitle} pipeline using ${selectedPipeline}`;

      const sourceId = deriveEndpointId('source', sourceConfig);
      const targetId = deriveEndpointId('target', targetConfig);

      const executionParams = {
        data_type: selectedBranch,
        pipeline_type: selectedPipeline,
        source_config: sourceConfig,
        target_config: targetConfig,
        search_modes: targetConfig.searchModes || [],
        migration_phases: ['connect', 'discover', 'profile', 'map', 'validate', 'execute'],
        migration_standard: 'plm-governed-sequenced-v1',
      };

      const result = await etlWorkflowService.createWorkflowFromGoal({
        goal,
        sourceId,
        targetId,
        workflowName,
        autoStart: true,
        executionParams,
      });

      const workflowId = result?.workflow?.workflow_id || null;
      const executionId = result?.execution?.execution_id || null;
      const agenticPlan = normalizeAgenticPlan(result, executionParams);
      setCreatedWorkflow({
        workflowId,
        executionId,
        status: result?.status || 'success',
        agenticPlan,
      });
      
      if (onComplete) {
        onComplete(result);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setIsCreating(false);
    }
  }, [workflowName, selectedBranch, selectedPipeline, sourceConfig, targetConfig, onComplete]);

  const handleOpenWorkflow = useCallback(() => {
    const workflowId = createdWorkflow?.workflowId;
    if (!workflowId) return;

    const encoded = encodeURIComponent(workflowId);
    if (window.location.hash.startsWith('#/')) {
      window.location.hash = `/workflow/${encoded}`;
    } else {
      window.location.assign(`/workflow/${encoded}`);
    }
  }, [createdWorkflow]);
  
  return (
    <div className="data-pipeline-wizard">
      <div className="wizard-header">
        <h1><i className="fas fa-magic" /> Create Data Pipeline</h1>
        <button className="close-btn" onClick={onCancel}>
          <i className="fas fa-times" />
        </button>
      </div>
      
      <StepIndicator steps={steps} currentStep={currentStep} />
      
      <div className="wizard-body">
        {createdWorkflow && (
          <div className="wizard-success-wrap" role="status" aria-live="polite">
            <div className="wizard-success">
              <i className="fas fa-check-circle" />
              <div>
                <strong>Workflow created successfully.</strong>
                <div>Workflow ID: {createdWorkflow.workflowId || 'n/a'}</div>
                {createdWorkflow.executionId ? <div>Execution ID: {createdWorkflow.executionId}</div> : null}
              </div>
            </div>

            {Array.isArray(createdWorkflow.agenticPlan?.phases) && createdWorkflow.agenticPlan.phases.length > 0 ? (
              <div className="wizard-agentic-plan">
                <div className="agentic-plan-header">
                  <i className="fas fa-diagram-project" />
                  <strong>Agentic PLM Task Flow</strong>
                  <span className="plan-standard">{createdWorkflow.agenticPlan.standard || 'plm-governed-sequenced-v1'}</span>
                </div>
                <div className="agentic-plan-list">
                  {createdWorkflow.agenticPlan.phases.map((phase) => (
                    <div key={`${phase.order}-${phase.phase}`} className="agentic-plan-row">
                      <span className="plan-phase-order">{phase.order}</span>
                      <span className="plan-phase-name">{phase.phase}</span>
                      <span className="plan-chip agent">{phase.agent}</span>
                      <span className="plan-chip task">{phase.task}</span>
                      {phase?.rule_engine?.enabled ? (
                        <span className="plan-chip rule-engine">Rule Engine ({phase?.rule_engine?.scope || 'active'})</span>
                      ) : null}
                      <span className="plan-chip status">{phase.status || 'planned'}</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        )}

        {currentStep === 0 && (
          <BranchSelectionStep 
            selectedBranch={selectedBranch} 
            onSelect={setSelectedBranch} 
          />
        )}
        
        {currentStep === 1 && (
          <PipelineSelectionStep 
            branch={selectedBranch}
            selectedPipeline={selectedPipeline}
            onSelect={setSelectedPipeline}
          />
        )}
        
        {currentStep === 2 && (
          <SourceConfigStep
            branch={selectedBranch}
            pipeline={selectedPipeline}
            config={sourceConfig}
            onChange={setSourceConfig}
          />
        )}
        
        {currentStep === 3 && (
          <TargetConfigStep
            branch={selectedBranch}
            pipeline={selectedPipeline}
            config={targetConfig}
            onChange={setTargetConfig}
          />
        )}
        
        {currentStep === 4 && (
          <ReviewStep
            branch={selectedBranch}
            pipeline={selectedPipeline}
            sourceConfig={sourceConfig}
            targetConfig={targetConfig}
            workflowName={workflowName}
            onNameChange={setWorkflowName}
          />
        )}
        
        {error && (
          <div className="wizard-error">
            <i className="fas fa-exclamation-circle" /> {error}
          </div>
        )}
      </div>
      
      <div className="wizard-footer">
        <button 
          className="btn-secondary" 
          onClick={currentStep === 0 ? onCancel : handleBack}
        >
          {currentStep === 0 ? 'Cancel' : 'Back'}
        </button>
        
        {currentStep < steps.length - 1 ? (
          <button 
            className="btn-primary" 
            onClick={handleNext}
            disabled={!canProceed()}
          >
            Next <i className="fas fa-arrow-right" />
          </button>
        ) : (
          <>
            <button 
              className="btn-primary btn-create" 
              onClick={handleCreate}
              disabled={!canProceed() || isCreating || Boolean(createdWorkflow?.workflowId)}
            >
              {isCreating ? (
                <><i className="fas fa-spinner fa-spin" /> Creating...</>
              ) : createdWorkflow?.workflowId ? (
                <><i className="fas fa-check" /> Created</>
              ) : (
                <><i className="fas fa-rocket" /> Create Pipeline</>
              )}
            </button>
            {createdWorkflow?.workflowId ? (
              <button className="btn-secondary" onClick={handleOpenWorkflow}>
                <i className="fas fa-external-link-alt" /> Open Workflow
              </button>
            ) : null}
          </>
        )}
      </div>
    </div>
  );
}
