/**
 * useAgentPipeline
 * ================
 * Reads the active wizard workflow from localStorage and maps it to the
 * backend agent pipeline DAG:
 *
 *   Discovery → Profiling → Quality → ETL → Reporting
 *
 * Each stage has a `status`:
 *   'idle'      — not yet reached
 *   'active'    — currently in progress (user is on this wizard step)
 *   'done'      — completed successfully
 *   'blocked'   — reached but has unresolved issues
 *
 * Cross-page deep-link `route` is also provided for each stage so any
 * page can render a "go there" CTA without knowing the wizard step numbers.
 */
import { useState, useEffect, useCallback } from 'react';

// Maps wizard step + stepStatus → pipeline stage statuses
const STAGES = [
  {
    id: 'discovery',
    label: 'Discovery',
    shortLabel: 'Discover',
    icon: 'fa-compass',
    route: '/migration?step=2',
    standalonePage: '/data-discovery',
    description: 'Scan files, detect schema, count records',
    agentName: 'DataDiscoveryAgent',
  },
  {
    id: 'profiling',
    label: 'Profiling',
    shortLabel: 'Profile',
    icon: 'fa-microscope',
    route: '/migration?step=2',
    standalonePage: '/data-discovery',
    description: 'Column statistics, null rates, pattern analysis',
    agentName: 'DataProfilerAgent',
  },
  {
    id: 'quality',
    label: 'Quality',
    shortLabel: 'Quality',
    icon: 'fa-shield-alt',
    route: '/migration?step=4',
    standalonePage: '/dq-dashboard',
    description: 'SODA checks, completeness, validity rules',
    agentName: 'QualityAgent',
  },
  {
    id: 'etl',
    label: 'ETL',
    shortLabel: 'ETL',
    icon: 'fa-exchange-alt',
    route: '/migration?step=5',
    standalonePage: '/lineage',
    description: 'Field mapping, transformation, load',
    agentName: 'ETLAgent',
  },
  {
    id: 'reporting',
    label: 'Reporting',
    shortLabel: 'Report',
    icon: 'fa-chart-bar',
    route: '/reporting-hub',
    standalonePage: '/reporting-hub',
    description: 'Generate audit trail, quality report',
    agentName: 'ReportingAgent',
  },
];

/**
 * Derives stage statuses from the persisted wizard state.
 *
 * Wizard step → pipeline stages:
 *  step 1  (Connect):    all idle
 *  step 2  (Discovery):  discovery=active, rest idle
 *                        if stepStatus[2].complete → discovery+profiling done
 *  step 3  (Map):        discovery+profiling done, quality idle, etl active
 *  step 4  (Validate):   discovery+profiling done, quality active
 *                        if stepStatus[4].complete → quality done
 *  step 5  (Execute):    discovery+profiling+quality done, etl active
 *                        if stepStatus[5].complete → all done
 */
function deriveStages(progress) {
  if (!progress) return STAGES.map((s) => ({ ...s, status: 'idle' }));

  const { step = 1, stepStatus = {} } = progress;
  const done = (n) => stepStatus[n]?.complete === true;

  const status = {
    discovery: 'idle',
    profiling: 'idle',
    quality: 'idle',
    etl: 'idle',
    reporting: 'idle',
  };

  if (step >= 2) {
    status.discovery = done(2) ? 'done' : 'active';
    status.profiling = done(2) ? 'done' : 'idle';
  }
  if (step >= 3) {
    status.discovery = 'done';
    status.profiling = 'done';
    status.etl = step === 3 ? 'active' : status.etl;
  }
  if (step >= 4) {
    status.discovery = 'done';
    status.profiling = 'done';
    status.quality = done(4) ? 'done' : 'active';
    status.etl = 'idle';
  }
  if (step >= 5) {
    status.discovery = 'done';
    status.profiling = 'done';
    status.quality = 'done';
    status.etl = done(5) ? 'done' : 'active';
    status.reporting = done(5) ? 'done' : 'idle';
  }

  return STAGES.map((s) => ({ ...s, status: status[s.id] }));
}

/**
 * Returns the logical "next" stage a user should act on.
 */
function getNextAction(stages) {
  const active = stages.find((s) => s.status === 'active');
  if (active) return active;
  const firstIdle = stages.find((s) => s.status === 'idle');
  return firstIdle ?? null;
}

export function useAgentPipeline() {
  const [pipeline, setPipeline] = useState({
    stages: STAGES.map((s) => ({ ...s, status: 'idle' })),
    workflowName: null,
    workflowId: null,
    sourceSystem: null,
    targetSystem: null,
    wizardStep: null,
    nextAction: null,
    hasActiveWorkflow: false,
  });

  const refresh = useCallback(() => {
    try {
      const raw = localStorage.getItem('migration_in_progress');
      if (!raw) {
        setPipeline({
          stages: STAGES.map((s) => ({ ...s, status: 'idle' })),
          workflowName: null,
          workflowId: null,
          sourceSystem: null,
          targetSystem: null,
          wizardStep: null,
          nextAction: null,
          hasActiveWorkflow: false,
        });
        return;
      }

      const progress = JSON.parse(raw);

      // Ignore stale entries (> 24 h)
      const age = Date.now() - new Date(progress.timestamp || 0).getTime();
      if (age > 24 * 60 * 60 * 1000) {
        localStorage.removeItem('migration_in_progress');
        return;
      }

      const stages = deriveStages(progress);
      setPipeline({
        stages,
        workflowName: progress.workflowName || null,
        workflowId:   progress.workflowId   || null,
        sourceSystem: progress.sourceSystem || null,
        targetSystem: progress.targetSystem || null,
        wizardStep:   progress.step         || null,
        nextAction:   getNextAction(stages),
        hasActiveWorkflow: true,
      });
    } catch {
      // Corrupt localStorage — ignore silently
    }
  }, []);

  useEffect(() => {
    refresh();

    const onStorage = (e) => {
      if (e.key === 'migration_in_progress') refresh();
    };

    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, [refresh]);

  return pipeline;
}

export { STAGES };
