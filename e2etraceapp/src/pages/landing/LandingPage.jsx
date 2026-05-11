import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import goodPointLogo from '../../assets/goodpoint-logo.svg';
import { useAgentPipeline } from '../../hooks/useAgentPipeline.js';
import './LandingPage.css';

// ── Type meta for activity feed ──────────────────────────────────────────────
const TYPE_META = {
  migration:        { icon: 'fas fa-exchange-alt',    color: '#3b82f6' },
  lineage:          { icon: 'fas fa-project-diagram', color: '#8b5cf6' },
  analytics:        { icon: 'fas fa-chart-line',      color: '#0ea5e9' },
  dq_scan:          { icon: 'fas fa-shield-alt',      color: '#22c55e' },
  discovery:        { icon: 'fas fa-compass',         color: '#f59e0b' },
  observability:    { icon: 'fas fa-heartbeat',       color: '#ef4444' },
  self_healing:     { icon: 'fas fa-wrench',          color: '#6366f1' },
  semantic_profile: { icon: 'fas fa-brain',           color: '#8b5cf6' },
};

const STATUS_COLORS = {
  pass: '#22c55e', fail: '#ef4444', warning: '#f59e0b', info: '#3b82f6', running: '#8b5cf6',
};

const TOOL_CARDS = [
  { icon: 'fas fa-exchange-alt',    title: 'Migration Wizard',   description: 'End-to-end guided data migration with AI-powered mapping and validation', link: '/migration',      color: 'var(--accent-color)', primary: true },
  { icon: 'fas fa-project-diagram', title: 'Graph Explorer',     description: 'Visualize and explore data relationships in Neo4j',                        link: '/graph-explorer', color: 'var(--success-color)' },
  { icon: 'fas fa-stream',          title: 'Data Lineage',       description: 'Track data flow and transformations across pipeline stages',                link: '/lineage',         color: 'var(--info-color)' },
  { icon: 'fas fa-clipboard-check', title: 'Rule Engine',        description: 'Manage data quality rules and validation logic',                            link: '/rule-engine',    color: 'var(--warning-color)' },
  { icon: 'fas fa-chart-line',      title: 'Analytics',          description: 'Insights and performance metrics across all data sources',                  link: '/analytics',      color: 'var(--primary-light)' },
];

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtAge(iso) {
  if (!iso) return '';
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return 'Just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function stageVisual(status) {
  if (status === 'done')    return { icon: 'fas fa-check-circle',        color: '#22c55e' };
  if (status === 'active')  return { icon: 'fas fa-circle-notch fa-spin', color: '#3b82f6' };
  if (status === 'blocked') return { icon: 'fas fa-exclamation-circle',   color: '#ef4444' };
  return                           { icon: 'fas fa-circle',               color: '#9ca3af' };
}

// ── Sub-components ────────────────────────────────────────────────────────────

function ServiceDot({ label, ok, loading }) {
  const color = loading ? '#9ca3af' : (ok ? '#22c55e' : '#ef4444');
  const title = `${label}: ${loading ? 'checking…' : ok ? 'online' : 'offline'}`;
  return (
    <div className="lp-svc-dot" title={title}>
      <span
        className={`lp-svc-indicator ${ok && !loading ? 'lp-svc-glow' : ''}`}
        style={{ background: color }}
        aria-hidden="true"
      />
      <span className="lp-svc-label">{label}</span>
    </div>
  );
}

function StatTile({ icon, color, value, label, link }) {
  const inner = (
    <div className="lp-stat-tile">
      <i className={icon} style={{ color }} aria-hidden="true" />
      <div className="lp-stat-val">{value}</div>
      <div className="lp-stat-lbl">{label}</div>
    </div>
  );
  return link
    ? <Link to={link} className="lp-stat-link">{inner}</Link>
    : inner;
}

// ── Main Component ────────────────────────────────────────────────────────────

const LandingPage = () => {
  const {
    stages,
    workflowName, sourceSystem, targetSystem,
    wizardStep, nextAction, hasActiveWorkflow,
  } = useAgentPipeline();

  const [health, setHealth]               = useState(null);
  const [recentReports, setRecentReports] = useState([]);
  const [reportSummary, setReportSummary] = useState(null);
  const [loadingStats, setLoadingStats]   = useState(true);

  useEffect(() => {
    let alive = true;
    (async () => {
      setLoadingStats(true);
      try {
        const [healthRes, reportsRes, summaryRes] = await Promise.allSettled([
          fetch('/health'),
          fetch('/api/report-hub?limit=4'),
          fetch('/api/report-hub/summary'),
        ]);
        if (!alive) return;
        if (healthRes.status === 'fulfilled' && healthRes.value.ok) {
          setHealth(await healthRes.value.json());
        }
        if (reportsRes.status === 'fulfilled' && reportsRes.value.ok) {
          const r = await reportsRes.value.json();
          setRecentReports(Array.isArray(r) ? r : []);
        }
        if (summaryRes.status === 'fulfilled' && summaryRes.value.ok) {
          setReportSummary(await summaryRes.value.json());
        }
      } finally {
        if (alive) setLoadingStats(false);
      }
    })();
    return () => { alive = false; };
  }, []);

  const resumeLink  = wizardStep ? `/migration?step=${wizardStep}` : (nextAction?.route || '/migration');
  const deps        = health?.dependencies || {};
  const dbOk        = Boolean(deps.postgres?.ok);
  const n4jOk       = Boolean(deps.neo4j?.ok);
  const mcpOk       = Boolean(deps.mcp_server?.ok);
  const svcOnline   = [dbOk, n4jOk, mcpOk].filter(Boolean).length;
  const totalReports = reportSummary?.total ?? '–';
  const passCount    = reportSummary?.by_status?.pass ?? '–';

  return (
    <div className="landing-page">

      {/* ══ ACTIVE WORKFLOW BANNER ══════════════════════════════════════════ */}
      {hasActiveWorkflow && (
        <section className="lp-wf-banner" aria-label="Active migration workflow">
          <div className="lp-wf-left">
            <span className="lp-wf-pulse" aria-hidden="true" />
            <div className="lp-wf-info">
              <div className="lp-wf-name">{workflowName || 'Migration In Progress'}</div>
              {(sourceSystem || targetSystem) && (
                <div className="lp-wf-route">
                  {sourceSystem && <span className="lp-wf-sys">{sourceSystem}</span>}
                  {sourceSystem && targetSystem && <i className="fas fa-arrow-right" aria-hidden="true" />}
                  {targetSystem && <span className="lp-wf-sys">{targetSystem}</span>}
                </div>
              )}
            </div>
          </div>

          <ol className="lp-pipeline-mini" aria-label="Pipeline stages">
            {stages.map((stage) => {
              const { icon, color } = stageVisual(stage.status);
              return (
                <li key={stage.id} className={`lp-pm-stage lp-pm-${stage.status}`} title={`${stage.label}: ${stage.status}`}>
                  <i className={icon} style={{ color }} aria-hidden="true" />
                  <span className="lp-pm-label">{stage.shortLabel}</span>
                </li>
              );
            })}
          </ol>

          <Link to={resumeLink} className="lp-resume-btn">
            <i className="fas fa-play" aria-hidden="true" /> Resume
          </Link>
        </section>
      )}

      {/* ══ HERO (first-visit / no active workflow) ═════════════════════════ */}
      {!hasActiveWorkflow && (
        <section className="hero-section">
          <div className="hero-content">
            <div className="hero-badge">
              <span className="badge-icon"><i className="fas fa-robot" aria-hidden="true" /></span>
              <span className="badge-text">AI-Powered Migration Platform</span>
            </div>
            <div className="hero-logo">
              <img src={goodPointLogo} alt="GoodPoint AgenticAI" className="hero-logo-img" />
            </div>
            <h1 className="hero-title">
              <span className="brand-highlight">GoodPoint</span> AgenticAI
            </h1>
            <p className="hero-subtitle">Intelligent PLM Data Migration</p>
            <p className="hero-description">
              Streamlined data migration with AI-powered schema mapping, quality validation,
              and enterprise-grade transformation capabilities.
            </p>
            <div className="hero-actions">
              <Link to="/migration" className="btn btn-primary btn-lg">
                <i className="fas fa-rocket" aria-hidden="true" /> Start Migration
              </Link>
              <Link to="/admin" className="btn btn-secondary">
                <i className="fas fa-cog" aria-hidden="true" /> Admin Settings
              </Link>
            </div>
          </div>
          <div className="hero-visual" aria-hidden="true" />
        </section>
      )}

      {/* ══ SERVICE HEALTH BAR ══════════════════════════════════════════════ */}
      <div className="lp-health-bar" role="status" aria-label="Service health">
        <ServiceDot label="PostgreSQL" ok={dbOk}  loading={loadingStats} />
        <ServiceDot label="Neo4j"      ok={n4jOk} loading={loadingStats} />
        <ServiceDot label="MCP Agents" ok={mcpOk} loading={loadingStats} />
        {health && (
          <span className={`lp-health-overall ${health.status === 'healthy' ? 'lp-health-ok' : 'lp-health-warn'}`}>
            <i className={health.status === 'healthy' ? 'fas fa-check-circle' : 'fas fa-exclamation-triangle'} aria-hidden="true" />
            {health.status === 'healthy' ? ' All systems operational' : ' Some services offline'}
          </span>
        )}
      </div>

      {/* ══ LIVE STATS ROW ══════════════════════════════════════════════════ */}
      <section className="lp-stats-row" aria-label="Platform statistics">
        <StatTile icon="fas fa-server"         color={svcOnline === 3 ? '#22c55e' : '#f59e0b'} value={`${svcOnline}/3`}               label="Services Online" />
        <StatTile icon="fas fa-clipboard-list" color="#3b82f6"                                  value={totalReports}                    label="Reports Saved"   link="/reporting-hub" />
        <StatTile icon="fas fa-shield-alt"     color="#22c55e"                                  value={typeof passCount === 'number' ? passCount : '–'} label="Quality Passes" link="/dq-dashboard" />
        <StatTile icon="fas fa-exchange-alt"   color="#8b5cf6"                                  value={hasActiveWorkflow ? '1 active' : 'None'} label="Active Workflow" link={hasActiveWorkflow ? resumeLink : '/migration'} />
      </section>

      {/* ══ AGENT PIPELINE LAUNCHER ═════════════════════════════════════════ */}
      <section className="lp-pipeline-section">
        <div className="lp-section-header">
          <div>
            <h2>Agent Pipeline</h2>
            <p>Click any stage to navigate directly — agents run in DAG order</p>
          </div>
          {hasActiveWorkflow
            ? <Link to={resumeLink}   className="btn btn-primary"><i className="fas fa-play"  aria-hidden="true" /> Resume Migration</Link>
            : <Link to="/migration"   className="btn btn-primary"><i className="fas fa-plus"  aria-hidden="true" /> New Migration</Link>}
        </div>

        <div className="lp-stages-row" role="list">
          {stages.map((stage, i) => {
            const { color } = stageVisual(stage.status);
            const dest = hasActiveWorkflow
              ? (stage.route || stage.standalonePage || '/migration')
              : (stage.standalonePage || '/migration');
            return (
              <React.Fragment key={stage.id}>
                <Link to={dest} className={`lp-stage-tile lp-stage-${stage.status}`} role="listitem" title={stage.description}>
                  <div className="lp-stage-icon-wrap" style={{ borderColor: color }}>
                    <i className={`fas ${stage.icon}`} style={{ color }} aria-hidden="true" />
                  </div>
                  <div className="lp-stage-body">
                    <span className="lp-stage-name">{stage.label}</span>
                    <span className="lp-stage-agent">{stage.agentName}</span>
                    <span className={`lp-stage-badge lp-badge-${stage.status}`}>{stage.status}</span>
                  </div>
                </Link>
                {i < stages.length - 1 && (
                  <i className="fas fa-chevron-right lp-stage-sep" aria-hidden="true" />
                )}
              </React.Fragment>
            );
          })}
        </div>
      </section>

      {/* ══ RECENT ACTIVITY ═════════════════════════════════════════════════ */}
      {recentReports.length > 0 && (
        <section className="lp-activity-section">
          <div className="lp-section-header">
            <h2>Recent Activity</h2>
            <Link to="/reporting-hub" className="lp-view-all">
              View All <i className="fas fa-arrow-right" aria-hidden="true" />
            </Link>
          </div>
          <div className="lp-activity-list" role="list">
            {recentReports.map((r) => {
              const tm = TYPE_META[r.report_type] || { icon: 'fas fa-file', color: '#9ca3af' };
              const sc = STATUS_COLORS[r.status] || '#9ca3af';
              return (
                <div key={r.report_id} className="lp-activity-item" role="listitem">
                  <span className="lp-act-icon">
                    <i className={tm.icon} style={{ color: tm.color }} aria-hidden="true" />
                  </span>
                  <div className="lp-act-body">
                    <div className="lp-act-title">{r.title}</div>
                    <div className="lp-act-meta">
                      {r.report_type?.replace(/_/g, ' ')}
                      {r.created_at && <> · {fmtAge(r.created_at)}</>}
                    </div>
                  </div>
                  <span
                    className="lp-act-status"
                    style={{ background: `${sc}22`, color: sc, border: `1px solid ${sc}44` }}
                  >
                    {r.status}
                  </span>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* ══ PLATFORM TOOLS ══════════════════════════════════════════════════ */}
      <section className="tools-section">
        <div className="section-header">
          <h2 className="section-title">Platform Tools</h2>
          <p className="section-description">Comprehensive toolkit for data engineering and analytics</p>
        </div>
        <div className="tools-grid">
          {TOOL_CARDS.map((tool, i) => (
            <Link
              to={tool.link}
              key={i}
              className={`tool-card ${tool.primary ? 'primary' : ''}`}
              style={{ '--card-color': tool.color }}
            >
              <div className="tool-icon"><i className={tool.icon} aria-hidden="true" /></div>
              <div className="tool-content">
                <h3 className="tool-title">{tool.title}</h3>
                <p className="tool-description">{tool.description}</p>
              </div>
              <div className="tool-arrow"><i className="fas fa-arrow-right" aria-hidden="true" /></div>
            </Link>
          ))}
        </div>
      </section>

      {/* ══ TECH STACK ══════════════════════════════════════════════════════ */}
      <section className="tech-stack-section">
        <div className="section-header"><h2 className="section-title">Technology Stack</h2></div>
        <div className="tech-badges">
          <div className="tech-badge"><i className="fas fa-brain" aria-hidden="true" /> GraphRAG</div>
          <div className="tech-badge"><i className="fas fa-database" aria-hidden="true" /> Neo4j</div>
          <div className="tech-badge"><i className="fas fa-code-branch" aria-hidden="true" /> GraphQL</div>
          <div className="tech-badge"><i className="fas fa-robot" aria-hidden="true" /> Agentic AI</div>
          <div className="tech-badge"><i className="fab fa-react" aria-hidden="true" /> React</div>
          <div className="tech-badge"><i className="fab fa-python" aria-hidden="true" /> FastAPI</div>
        </div>
      </section>

    </div>
  );
};

export default LandingPage;
