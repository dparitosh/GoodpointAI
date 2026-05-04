/**
 * AgentPipelineStrip
 * ==================
 * A compact, horizontal pipeline status bar that shows the 5-stage agent DAG:
 *
 *   Discovery → Profiling → Quality → ETL → Reporting
 *
 * Embed at the top of any data page (Discovery, DQ Dashboard, Lineage,
 * Observability) to give users immediate pipeline context and clear
 * "what to do next" signposting.
 *
 * Props:
 *   activeStageName  — highlight a specific stage as the "current page"
 *                      e.g. 'quality' on the DQ Dashboard
 *   compact          — boolean; reduces to icon-only labels (default false)
 *   className        — extra CSS class
 */
import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useAgentPipeline } from '../../hooks/useAgentPipeline.js';
import './AgentPipelineStrip.css';

const STATUS_META = {
  done:    { icon: 'fa-check-circle',  label: 'Done',    cls: 'aps-done'    },
  active:  { icon: 'fa-circle-notch',  label: 'Active',  cls: 'aps-active'  },
  blocked: { icon: 'fa-exclamation-circle', label: 'Blocked', cls: 'aps-blocked' },
  idle:    { icon: 'fa-circle',        label: 'Idle',    cls: 'aps-idle'    },
};

export function AgentPipelineStrip({ activeStageName, compact = false, className = '' }) {
  const { stages, workflowName, sourceSystem, hasActiveWorkflow, nextAction } = useAgentPipeline();

  const [svcHealth, setSvcHealth] = useState(null);
  useEffect(() => {
    let alive = true;
    fetch('/health')
      .then((r) => r.ok ? r.json() : null)
      .then((data) => { if (alive && data) setSvcHealth(data); })
      .catch(() => {});
    return () => { alive = false; };
  }, []);

  // No active workflow — strip is still useful as a navigation map, shown dimmed
  const isLive = hasActiveWorkflow;

  return (
    <div
      className={`agent-pipeline-strip ${isLive ? 'aps-live' : 'aps-no-workflow'} ${className}`}
      role="navigation"
      aria-label="Agent pipeline stages"
    >
      {/* Left context label */}
      <div className="aps-context">
        {isLive ? (
          <>
            <i className="fas fa-route aps-route-icon" aria-hidden="true" />
            <span className="aps-workflow-name" title={workflowName || undefined}>
              {workflowName || 'Active workflow'}
            </span>
            {sourceSystem && (
              <span className="aps-source-badge">
                <i className="fas fa-database" aria-hidden="true" />
                {sourceSystem}
              </span>
            )}
          </>
        ) : (
          <>
            <i className="fas fa-route aps-route-icon" aria-hidden="true" />
            <span className="aps-no-workflow-label">No active workflow</span>
          </>
        )}
      </div>

      {/* Stage chain */}
      <ol className="aps-stages" aria-label="Pipeline stages">
        {stages.map((stage, idx) => {
          const sm = STATUS_META[stage.status] || STATUS_META.idle;
          const isCurrentPage = stage.id === activeStageName;
          const isNext =
            isLive && nextAction?.id === stage.id && stage.status === 'idle';

          return (
            <React.Fragment key={stage.id}>
              {idx > 0 && (
                <li className="aps-connector" aria-hidden="true">
                  <i className={`fas fa-chevron-right aps-chevron ${stage.status === 'done' || stages[idx - 1].status === 'done' ? 'aps-chevron-done' : ''}`} />
                </li>
              )}
              <li
                className={[
                  'aps-stage',
                  sm.cls,
                  isCurrentPage ? 'aps-current-page' : '',
                  isNext        ? 'aps-next-action'  : '',
                ].join(' ')}
                title={`${stage.label}: ${stage.description}`}
              >
                <Link
                  to={isLive ? stage.route : stage.standalonePage}
                  className="aps-stage-link"
                  aria-current={isCurrentPage ? 'step' : undefined}
                >
                  <span className="aps-stage-status-dot">
                    <i
                      className={`fas ${sm.icon} ${stage.status === 'active' ? 'fa-spin' : ''}`}
                      aria-hidden="true"
                    />
                  </span>
                  {!compact && (
                    <span className="aps-stage-label">
                      {stage.shortLabel}
                      {isNext && (
                        <span className="aps-next-badge" aria-label="Next recommended step">
                          Next
                        </span>
                      )}
                    </span>
                  )}
                </Link>
              </li>
            </React.Fragment>
          );
        })}
      </ol>

      {/* Health badge */}
      {svcHealth && (
        <div className="aps-health-badge" title={`System: ${svcHealth.status}`} aria-label="Service health">
          <span
            className={`aps-health-dot ${svcHealth.status === 'healthy' ? 'aps-health-ok' : 'aps-health-warn'}`}
            aria-hidden="true"
          />
          <span className="aps-health-label">
            {svcHealth.status === 'healthy' ? 'All OK' : 'Degraded'}
          </span>
        </div>
      )}

      {/* Right CTA — only when there's a live next action on a different page */}
      {isLive && nextAction && nextAction.id !== activeStageName && (
        <Link
          to={nextAction.route}
          className="aps-next-cta"
          aria-label={`Next: ${nextAction.label}`}
        >
          <i className={`fas ${nextAction.icon}`} aria-hidden="true" />
          <span>Next: {nextAction.label}</span>
          <i className="fas fa-arrow-right" aria-hidden="true" />
        </Link>
      )}

      {/* Right CTA — when no workflow, prompt to start one */}
      {!isLive && (
        <Link to="/migration" className="aps-start-cta" aria-label="Start a new migration">
          <i className="fas fa-plus" aria-hidden="true" />
          <span>Start Migration</span>
        </Link>
      )}
    </div>
  );
}

export default AgentPipelineStrip;
