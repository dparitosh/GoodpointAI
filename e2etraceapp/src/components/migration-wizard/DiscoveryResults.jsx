/**
 * DiscoveryResults — IXDF-compliant widget dashboard for Step 2 discovery output.
 *
 * Design principles applied (IXDF):
 *  • Progressive disclosure — KPIs first, detail on demand
 *  • Visibility of system status — every % is labelled with plain-English meaning
 *  • Recognition over recall — semantic role badges instead of raw column names
 *  • Goal-gradient effect — clear confidence tiers guide users toward acceptance
 *  • Miller's Law — max 5 KPIs visible simultaneously; rest behind group tabs
 */
import React, { useState, useMemo, useCallback } from 'react';
import './DiscoveryResults.css';

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Parse any confidence representation (0-1 float, "70%", integer) → 0-100 integer */
const parsePct = (v) => {
  if (v == null) return 0;
  if (typeof v === 'string' && v.endsWith('%')) return Math.min(100, parseInt(v, 10));
  if (typeof v === 'number' && v > 0 && v <= 1.0) return Math.round(v * 100);
  if (typeof v === 'number') return Math.min(100, Math.round(v));
  return 0;
};

/** Map 0-100 pct → confidence tier key */
const tier = (pct) => pct >= 80 ? 'high' : pct >= 60 ? 'medium' : 'low';

const CONF_MEANING = {
  high:   'Strong match — field name, data type, and semantic role all align with target',
  medium: 'Name match — field names are identical or very similar; review data type compatibility',
  low:    'Weak match — AI found partial similarity; manual review required before mapping',
};

const ROLE_LABELS = {
  identifier:  'Unique ID / Key',
  foreign_key: 'Foreign Key',
  name:        'Name / Label',
  label:       'Label / Tag',
  date:        'Date / Time',
  quantity:    'Quantity / Amount',
  status:      'Status / Flag',
  metric:      'Metric / KPI',
  unknown:     'Unclassified',
};

const ROLE_DESC = {
  identifier:  'Uniquely identifies a record — maps to primary key or ID fields in the target',
  foreign_key: 'References another entity — drives relationship mapping between tables',
  name:        'Human-readable name or description',
  label:       'Classification tag — maps to category or type fields',
  date:        'Date or timestamp value',
  quantity:    'Numeric measurement or count',
  status:      'Enumerated state or flag (e.g., Active, Approved)',
  metric:      'Calculated or aggregated KPI value',
  unknown:     'Semantic role could not be determined with sufficient confidence',
};

// ── Sub-components ────────────────────────────────────────────────────────────

/** Atlas-style KPI stat card */
const KpiCard = ({ icon, value, label, sub, variant = '' }) => (
  <div className={`dr-kpi dr-kpi-${variant}`}>
    <div className="dr-kpi-icon">
      <i className={`fas ${icon}`} />
    </div>
    <div className="dr-kpi-body">
      <div className="dr-kpi-value">{value ?? '—'}</div>
      <div className="dr-kpi-label">{label}</div>
      {sub && <div className="dr-kpi-sub">{sub}</div>}
    </div>
  </div>
);

/** Horizontal confidence progress bar with % label */
const ConfBar = ({ pct, confTier }) => {
  const t = confTier || tier(pct);
  return (
    <div className={`dr-conf-bar-wrap dr-conf-wrap-${t}`} title={CONF_MEANING[t]}>
      <div className="dr-conf-track">
        <div className={`dr-conf-fill dr-conf-fill-${t}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="dr-conf-pct">{pct}%</span>
    </div>
  );
};

// ── Main component ────────────────────────────────────────────────────────────

export default function DiscoveryResults({
  runId,
  insights = [],
  introspect,
  sample,
  mappings = [],
  semanticProfile,
  sodaResult,
  sourceSystem,
}) {
  const [samplePage, setSamplePage]   = useState(1);
  const [fieldView, setFieldView]     = useState('entity'); // 'entity' | 'role' | 'all'
  const [expandedGroups, setExpanded] = useState({});
  const [selectedFile, setSelectedFile] = useState(null); // name of selected file row, or null = all
  const [dqExpanded, setDqExpanded]   = useState(false);
  const PAGE_SIZE = 10;

  // ── KPI derivations ─────────────────────────────────────────────────────────
  const _inferredFields = introspect?.inferred_source_fields;
  const totalFields   = (_inferredFields?.length > 0 ? _inferredFields.length : null) ?? mappings.length;
  const allRecords    = Array.isArray(sample?.records) ? sample.records : [];
  const totalRecords  = allRecords.length;
  const totalFiles    = sample?.total_files ?? sample?.source_files?.length ?? null;
  const mappingCount  = mappings.length;

  const sodaInsight   = insights.find(i =>
    /soda|quality/i.test(i.title || ''));
  const qualityScore  = sodaResult?.overall_score != null
    ? Math.round(Number(sodaResult.overall_score) * 100)
    : (() => {
        const m = (sodaInsight?.detail || '').match(/(\d+)%/);
        return m ? parseInt(m[1], 10) : null;
      })();
  const qualityStatus = sodaResult?.status
    ?? (qualityScore != null
      ? (qualityScore >= 80 ? 'pass' : qualityScore >= 60 ? 'warn' : 'fail')
      : null);

  const qualityVariant = qualityStatus === 'pass' ? 'success'
    : qualityStatus === 'warn' ? 'warning'
    : qualityStatus === 'fail' ? 'danger' : '';

  // ── Source inventory (file / entity groups) ─────────────────────────────────
  const sourceGroups = useMemo(() => {
    // Case 1: backend gave explicit source_files array
    if (sample?.source_files?.length > 0) {
      return sample.source_files.map(f => ({
        name:        f.name || f.path || String(f),
        type:        f.type || 'file',
        records:     f.record_count ?? f.row_count ?? null,
        fields:      f.field_count ?? null,
        quality:     f.quality_score != null ? Math.round(f.quality_score * 100) : null,
        issues:      f.issues ?? 0,
        field_names: f.field_names || [],
        isFile:      true,
      }));
    }
    // Case 2: derive from entity classifications (Neo4j: node types ≈ "tables")
    // Only applies for graph/neo4j sources — file-based sources use Case 1 / Case 3.
    const isGraphSource = /neo4j|graph|neptune|graphdb/i.test(sourceSystem?.type || '');
    if (isGraphSource && semanticProfile?.entity_classifications?.length > 0) {
      return semanticProfile.entity_classifications.map(ec => ({
        name:         ec.entity_class || 'Unknown',
        type:         'node-type',
        records:      null,
        fields:       semanticProfile.column_semantics?.filter(
                        cs => cs.entity_hint === ec.entity_class).length || null,
        quality:      Math.round((ec.confidence || 0) * 100),
        issues:       0,
        isEntityGroup: true,
        reasoning:    ec.reasoning,
      }));
    }
    // Case 3: single row for the entire source system
    return [{
      name:    sourceSystem?.name || 'Source System',
      type:    sourceSystem?.type || 'system',
      records: totalRecords || null,
      fields:  totalFields || null,
      quality: qualityScore,
      issues:  sodaResult?.issues_count ?? 0,
    }];
  }, [sample, semanticProfile, sourceSystem, totalRecords, totalFields, qualityScore, sodaResult]);

  // ── Field grouping ──────────────────────────────────────────────────────────
  const colSemMap = useMemo(() => {
    const m = {};
    (semanticProfile?.column_semantics || []).forEach(cs => { m[cs.column] = cs; });
    return m;
  }, [semanticProfile]);

  const fieldGroups = useMemo(() => {
    const inferredList = introspect?.inferred_source_fields;
    const allFields = (inferredList?.length > 0 ? inferredList : null)
      ?? mappings.map(m => m.sourceField);

    if (fieldView === 'entity') {
      const groups = {};
      allFields.forEach(f => {
        const key = colSemMap[f]?.entity_hint || 'Unclassified';
        (groups[key] = groups[key] || []).push(f);
      });
      return Object.entries(groups)
        .sort(([a], [b]) => (a === 'Unclassified' ? 1 : b === 'Unclassified' ? -1 : 0))
        .map(([name, fields]) => ({ name, fields }));
    }
    if (fieldView === 'role') {
      const groups = {};
      allFields.forEach(f => {
        const key = colSemMap[f]?.semantic_role || 'unknown';
        (groups[key] = groups[key] || []).push(f);
      });
      return Object.entries(groups)
        .sort(([a], [b]) => (a === 'unknown' ? 1 : b === 'unknown' ? -1 : 0))
        .map(([roleKey, fields]) => ({
          name: ROLE_LABELS[roleKey] || roleKey,
          roleKey,
          fields,
        }));
    }
    // 'all'
    return [{ name: 'All Fields', fields: allFields }];
  }, [fieldView, introspect, mappings, colSemMap]);

  // ── Mapping tiers ───────────────────────────────────────────────────────────
  const { highMaps, medMaps, lowMaps } = useMemo(() => {
    const sorted = [...mappings].sort(
      (a, b) => parsePct(b.confidence) - parsePct(a.confidence));
    return {
      highMaps: sorted.filter(m => parsePct(m.confidence) >= 80),
      medMaps:  sorted.filter(m => parsePct(m.confidence) >= 60 && parsePct(m.confidence) < 80),
      lowMaps:  sorted.filter(m => parsePct(m.confidence) < 60),
    };
  }, [mappings]);

  // ── Per-field lookup: O(1) mapping target for inline display ─────────────────
  const mappingBySource = useMemo(() => {
    const m = {};
    mappings.forEach(mp => { m[mp.sourceField] = mp; });
    return m;
  }, [mappings]);

  // ── Per-column sample values (up to 3 distinct non-empty values) ─────────────
  const sampleValuesByCol = useMemo(() => {
    const out = {};
    allRecords.forEach(row => {
      Object.entries(row).forEach(([col, val]) => {
        const s = String(val ?? '').trim();
        if (!s || s === '—') return;
        if (!out[col]) out[col] = [];
        if (!out[col].includes(s) && out[col].length < 3) out[col].push(s);
      });
    });
    return out;
  }, [allRecords]);

  // ── Selected-file filter ────────────────────────────────────────────────────
  // When user clicks a file row, derive the whitelist of column names for that file
  const activeFileGroup = useMemo(
    () => selectedFile ? sourceGroups.find(g => g.name === selectedFile) : null,
    [selectedFile, sourceGroups],
  );
  const activeFileFields = useMemo(
    () => activeFileGroup?.field_names ? new Set(activeFileGroup.field_names) : null,
    [activeFileGroup],
  );
  // Filter fieldGroups to only show fields belonging to the selected file
  const displayedFieldGroups = useMemo(() => {
    if (!activeFileFields) return fieldGroups;
    return fieldGroups
      .map(grp => ({ ...grp, fields: grp.fields.filter(f => activeFileFields.has(f)) }))
      .filter(grp => grp.fields.length > 0);
  }, [fieldGroups, activeFileFields]);

  // ── Sample pagination ───────────────────────────────────────────────────────
  // When a file is selected, filter records to only those whose key-set matches the file's fields
  const filteredRecords = useMemo(() => {
    if (!activeFileFields || activeFileFields.size === 0) return allRecords;
    return allRecords.filter(row => {
      const keys = Object.keys(row);
      // Row belongs to this file if every key it has is in the file's field set
      return keys.length > 0 && keys.every(k => activeFileFields.has(k));
    });
  }, [allRecords, activeFileFields]);
  const displayedRecords = activeFileFields ? filteredRecords : allRecords;
  const totalDisplayed   = displayedRecords.length;
  const totalPages  = Math.ceil(totalDisplayed / PAGE_SIZE);
  const pageRecords = displayedRecords.slice((samplePage - 1) * PAGE_SIZE, samplePage * PAGE_SIZE);
  // Columns come from the current page rows (no column filter needed — rows already filtered)
  const sampleCols  = pageRecords.length > 0 ? Object.keys(pageRecords[0]) : [];

  // ── Toggle group expand ─────────────────────────────────────────────────────
  const toggleGroup = (key) =>
    setExpanded(prev => ({ ...prev, [key]: !prev[key] }));

  // ── Non-SODA insights ───────────────────────────────────────────────────────
  const nonSodaInsights = insights.filter(i => !/soda/i.test(i.title || ''));

  // ── DQ report: aggregate per-field stats across all source files ─────────────
  // Rows = one per field per file. Used for the tabular DQ report & CSV export.
  const dqReport = useMemo(() => {
    const rows = [];
    const files = sample?.source_files || [];
    files.forEach(f => {
      const fname = f.name || '—';
      const totalRec = f.record_count ?? 0;
      const dupRows  = f.duplicate_rows ?? 0;
      const stats    = Array.isArray(f.field_stats) ? f.field_stats : [];
      if (stats.length > 0) {
        stats.forEach(s => rows.push({
          file: fname,
          field: s.field,
          type: s.type || '—',
          totalRecords: totalRec,
          nullCount: s.null_count ?? 0,
          uniqueCount: s.unique_count ?? 0,
          completeness: s.completeness != null ? Math.round(s.completeness * 100) : null,
          duplicateRows: dupRows,
        }));
      } else if (Array.isArray(f.field_names) && f.field_names.length > 0) {
        // field_stats not present — emit summary row per field without per-field detail
        f.field_names.forEach(fn => rows.push({
          file: fname,
          field: fn,
          type: '—',
          totalRecords: totalRec,
          nullCount: null,
          uniqueCount: null,
          completeness: f.quality_score != null ? Math.round(f.quality_score * 100) : null,
          duplicateRows: dupRows,
        }));
      }
    });
    return rows;
  }, [sample]);

  const exportDqCsv = useCallback(() => {
    const header = 'File,Field,Type,Total Records,Null Count,Unique Values,Completeness (%),Duplicate Rows';
    const lines  = dqReport.map(r =>
      [r.file, r.field, r.type, r.totalRecords,
       r.nullCount ?? '', r.uniqueCount ?? '',
       r.completeness ?? '', r.duplicateRows]
      .map(v => `"${String(v).replace(/"/g, '""')}"`)
      .join(',')
    );
    const csv  = [header, ...lines].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href     = url;
    a.download = `dq-report-${runId || 'discovery'}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [dqReport, runId]);

  // Don't render if there's genuinely nothing to show
  if (!introspect && !mappings.length && !allRecords.length && !insights.length) {
    return null;
  }

  // ── RENDER ──────────────────────────────────────────────────────────────────
  return (
    <div className="dr-root">

      {/* ── Run header ────────────────────────────────────────────────────── */}
      <div className="dr-run-header">
        <div className="dr-run-title">
          <i className="fas fa-microscope" />
          Discovery Intelligence Report
        </div>
        <div className="dr-run-badges">
          {runId && (
            <span className="dr-badge dr-badge-neutral" title={`Full ID: ${runId}`}>
              <i className="fas fa-fingerprint" /> {runId.slice(0, 8)}…
            </span>
          )}
          {sourceSystem?.name && (
            <span className="dr-badge dr-badge-neutral">
              <i className="fas fa-database" /> {sourceSystem.name}
            </span>
          )}
          {sample?.stagedFrom === 'source' && (
            <span className="dr-badge dr-badge-live">
              <i className="fas fa-circle" /> Live Source
            </span>
          )}
          {sample?.stagedFrom === 'unreachable' && (
            <span className="dr-badge dr-badge-synthetic">
              <i className="fas fa-exclamation-triangle" /> Source Unreachable
            </span>
          )}
          {sample?.stagedFrom === 'not_registered' && (
            <span className="dr-badge dr-badge-synthetic">
              <i className="fas fa-unlink" /> Source Not Registered
            </span>
          )}
          {(sample?.stagedFrom === 'none' || sample?.stagedFrom == null) && (
            <span className="dr-badge dr-badge-neutral">
              <i className="fas fa-minus-circle" /> Not Sampled
            </span>
          )}
        </div>
      </div>

      {/* ── KPI strip — 5 stat widgets ───────────────────────────────────── */}
      <div className="dr-kpi-strip">
        {(totalFiles != null || sourceGroups[0]?.isEntityGroup) && (
          <KpiCard
            icon="fa-layer-group"
            value={totalFiles ?? sourceGroups.length}
            label={sourceGroups[0]?.isEntityGroup ? 'Entity Types' : 'Files Scanned'}
            sub="from source system"
          />
        )}
        <KpiCard
          icon="fa-columns"
          value={totalFields}
          label="Fields Detected"
          sub="in source schema"
        />
        <KpiCard
          icon={qualityStatus === 'pass' ? 'fa-shield-alt' : 'fa-exclamation-triangle'}
          value={qualityScore != null ? `${qualityScore}%` : '—'}
          label="Data Quality"
          sub={qualityStatus
            ? `SODA gate: ${qualityStatus.toUpperCase()}`
            : 'Not yet scanned'}
          variant={qualityVariant}
        />
        <KpiCard
          icon="fa-random"
          value={mappingCount}
          label="Mapping Suggestions"
          sub={`${highMaps.length} strong · ${medMaps.length} review · ${lowMaps.length} weak`}
        />
        <KpiCard
          icon="fa-table"
          value={totalRecords > 0 ? totalRecords.toLocaleString() : '—'}
          label="Sample Records"
          sub={sample?.stagedFrom === 'source' ? 'live from source'
            : sample?.stagedFrom === 'not_registered' ? 'source not registered — see insights'
            : sample?.stagedFrom === 'unreachable' ? 'source not reachable'
            : 'no sample available'}
        />
      </div>

      {/* ── Non-SODA insights (warnings, errors, info) ───────────────────── */}
      {nonSodaInsights.length > 0 && (
        <div className="dr-insights">
          {nonSodaInsights.map(ins => (
            <div key={ins.id} className={`dr-insight dr-insight-${ins.severity || 'info'}`}>
              <i className={`fas fa-${
                ins.severity === 'success'  ? 'check-circle' :
                ins.severity === 'warning'  ? 'exclamation-triangle' :
                ins.severity === 'error'    ? 'times-circle' : 'info-circle'
              }`} />
              <div className="dr-insight-body">
                <strong>{ins.title}</strong>
                {ins.detail && <span>{ins.detail}</span>}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Agent Director: recommended actions ──────────────────────────── */}
      {Array.isArray(introspect?.recommended_actions) && introspect.recommended_actions.length > 0 && (
        <div className="dr-actions-panel">
          <div className="dr-actions-header">
            <i className="fas fa-robot" />
            <span>Agent-recommended actions</span>
          </div>
          <ol className="dr-actions-list">
            {introspect.recommended_actions.map((act, i) => (
              <li key={act.action || i} className={`dr-action-item dr-action-${act.severity || 'info'}`}>
                <span className="dr-action-label">
                  <i className={`fas fa-${
                    act.severity === 'success'  ? 'check-circle' :
                    act.severity === 'error'    ? 'times-circle' :
                    act.severity === 'warning'  ? 'exclamation-triangle' : 'arrow-right'
                  }`} />
                  {act.label}
                </span>
                {act.detail && <span className="dr-action-detail">{act.detail}</span>}
              </li>
            ))}
          </ol>
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════════════════
          WIDGET 1: SOURCE INVENTORY SCOREBOARD
          Purpose: Answer "what files/tables were scanned, and how healthy is each?"
      ═══════════════════════════════════════════════════════════════════ */}
      <section className="dr-section">
        <div className="dr-section-header">
          <i className="fas fa-clipboard-list" />
          <div className="dr-section-title-group">
            <span className="dr-section-title">
              {sourceGroups[0]?.isEntityGroup ? 'Entity Type Inventory' : 'Source File Inventory'}
            </span>
            <span className="dr-section-desc">
              {sourceGroups[0]?.isEntityGroup
                ? 'Node types (logical "tables") discovered in the graph source — quality score = AI classification confidence'
                : 'Per-file quality metrics — click a row to filter the Field Intelligence panel below'}
            </span>
          </div>
          <span className="dr-section-count">
            {sourceGroups.length} {sourceGroups[0]?.isEntityGroup ? 'types' : 'files'}
          </span>
        </div>

        <div className="dr-scoreboard">
          {/* Scoreboard column headers */}
          <div className="dr-sb-head">
            <span className="dr-sb-col-name">Source</span>
            <span className="dr-sb-col-type">Type</span>
            <span className="dr-sb-col-records">Records</span>
            <span className="dr-sb-col-fields">Fields</span>
            <span className="dr-sb-col-quality">
              Quality / Confidence
              <span className="dr-sb-col-hint">
                {sourceGroups[0]?.isEntityGroup
                  ? '(AI entity classification confidence)'
                  : '(SODA data quality score)'}
              </span>
            </span>
            <span className="dr-sb-col-issues">Issues</span>
            <span className="dr-sb-col-status">Status</span>
          </div>

          {sourceGroups.map((grp, i) => {
            const qPct  = grp.quality;
            const qTier = qPct != null ? tier(qPct) : 'none';
            const isActive = selectedFile === grp.name;
            const fileIcon = grp.isEntityGroup ? 'fa-sitemap'
              : grp.type === 'csv'  ? 'fa-file-csv'
              : grp.type === 'xml'  ? 'fa-file-code'
              : grp.type === 'json' ? 'fa-file-alt'
              : 'fa-database';

            return (
              <div
                key={i}
                className={`dr-sb-row dr-sb-tier-${qTier}${isActive ? ' dr-sb-row--active' : ''}${grp.isFile || !grp.isEntityGroup ? ' dr-sb-row--clickable' : ''}`}
                onClick={() => { setSelectedFile(isActive ? null : grp.name); setSamplePage(1); }}
                title={isActive ? 'Click to clear filter' : 'Click to focus Field Intelligence + Sample Explorer on this file'}
                role="button"
                tabIndex={0}
                onKeyDown={e => e.key === 'Enter' && (setSelectedFile(isActive ? null : grp.name), setSamplePage(1))}
              >
                <span className="dr-sb-col-name" title={grp.reasoning || grp.name}>
                  <i className={`fas ${fileIcon}`} />
                  <span>{grp.name}</span>
                </span>
                <span className="dr-sb-col-type">
                  {grp.isEntityGroup ? 'Node type' : grp.type}
                </span>
                <span className="dr-sb-col-records">
                  {grp.records != null ? grp.records.toLocaleString() : '—'}
                </span>
                <span className="dr-sb-col-fields">
                  {grp.fields != null ? grp.fields : '—'}
                </span>
                <span className="dr-sb-col-quality">
                  {qPct != null ? (
                    <div className="dr-minibar-wrap">
                      <div className="dr-minibar-track">
                        <div
                          className={`dr-minibar-fill dr-minibar-${qTier}`}
                          style={{ width: `${qPct}%` }}
                        />
                      </div>
                      <span className={`dr-minibar-pct dr-minibar-pct-${qTier}`}>
                        {qPct}%
                      </span>
                    </div>
                  ) : '—'}
                </span>
                <span className={`dr-sb-col-issues${grp.issues > 0 ? ' has-issues' : ''}`}>
                  {grp.issues > 0 ? grp.issues : <i className="fas fa-check" />}
                </span>
                <span className={`dr-sb-col-status dr-status-${qTier}`}>
                  {qTier === 'high'   && <><i className="fas fa-check-circle" />  Pass</>}
                  {qTier === 'medium' && <><i className="fas fa-dot-circle" />    Review</>}
                  {qTier === 'low'    && <><i className="fas fa-exclamation-circle" /> Attention</>}
                  {qTier === 'none'   && '—'}
                </span>
              </div>
            );
          })}
        </div>
      </section>

      {/* ═══════════════════════════════════════════════════════════════════
          WIDGET 1b: DATA QUALITY REPORT
          Purpose: Per-field tabular metrics — records, types, nulls, uniques, duplicates
      ═══════════════════════════════════════════════════════════════════ */}
      {dqReport.length > 0 && (
        <section className="dr-section dr-section--dq">
          <div className="dr-section-header">
            <i className="fas fa-clipboard-check" />
            <div className="dr-section-title-group">
              <span className="dr-section-title">Data Quality Report</span>
              <span className="dr-section-desc">
                Per-field metrics — record count, inferred type, null values, unique values and duplicate rows.
                Conforms to data quality assessment standards.
              </span>
            </div>
            <div className="dr-dq-header-actions">
              <span className="dr-section-count">{dqReport.length} fields</span>
              <button className="dr-dq-export-btn" onClick={exportDqCsv} title="Export as CSV">
                <i className="fas fa-download" /> Export CSV
              </button>
              <button
                className="dr-dq-toggle-btn"
                onClick={() => setDqExpanded(x => !x)}
                aria-expanded={dqExpanded}
              >
                <i className={`fas fa-chevron-${dqExpanded ? 'up' : 'down'}`} />
                {dqExpanded ? 'Collapse' : 'Expand'}
              </button>
            </div>
          </div>

          {dqExpanded && (
            <div className="dr-dq-table-wrap">
              <table className="dr-dq-table">
                <thead>
                  <tr>
                    <th>File</th>
                    <th>Field</th>
                    <th>Type</th>
                    <th className="dr-dq-num">Total Records</th>
                    <th className="dr-dq-num">Null Values</th>
                    <th className="dr-dq-num">Unique Values</th>
                    <th className="dr-dq-num">Completeness</th>
                    <th className="dr-dq-num">Duplicate Rows</th>
                  </tr>
                </thead>
                <tbody>
                  {dqReport.map((r, i) => {
                    const compCls = r.completeness == null ? ''
                      : r.completeness >= 90 ? 'dr-dq-comp-high'
                      : r.completeness >= 70 ? 'dr-dq-comp-med'
                      : 'dr-dq-comp-low';
                    return (
                      <tr key={i} className={i % 2 === 0 ? 'dr-dq-row-even' : ''}>
                        <td className="dr-dq-file" title={r.file}>{r.file.length > 30 ? `${r.file.substring(0, 30)}…` : r.file}</td>
                        <td className="dr-dq-field"><code>{r.field}</code></td>
                        <td><span className={`dr-dq-type dr-dq-type-${r.type}`}>{r.type}</span></td>
                        <td className="dr-dq-num">{r.totalRecords.toLocaleString()}</td>
                        <td className={`dr-dq-num${r.nullCount > 0 ? ' dr-dq-has-nulls' : ''}`}>
                          {r.nullCount ?? '—'}
                          {r.nullCount > 0 && <i className="fas fa-exclamation-circle dr-dq-null-icon" title="Has null values" />}
                        </td>
                        <td className="dr-dq-num">{r.uniqueCount ?? '—'}</td>
                        <td className={`dr-dq-num ${compCls}`}>
                          {r.completeness != null ? `${r.completeness}%` : '—'}
                        </td>
                        <td className={`dr-dq-num${r.duplicateRows > 0 ? ' dr-dq-has-dups' : ''}`}>
                          {r.duplicateRows > 0
                            ? <><i className="fas fa-copy dr-dq-dup-icon" title="Duplicate rows detected" /> {r.duplicateRows}</>
                            : '0'}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {!dqExpanded && (
            <div className="dr-dq-summary-bar">
              {(() => {
                const totalNulls = dqReport.reduce((s, r) => s + (r.nullCount || 0), 0);
                const totalDups  = [...new Set(dqReport.map(r => r.file))].reduce((s, fname) => {
                  const row = dqReport.find(r => r.file === fname);
                  return s + (row?.duplicateRows || 0);
                }, 0);
                const avgComp = dqReport.filter(r => r.completeness != null);
                const compAvg = avgComp.length
                  ? Math.round(avgComp.reduce((s, r) => s + r.completeness, 0) / avgComp.length)
                  : null;
                return (
                  <>
                    <span className="dr-dq-summary-item">
                      <i className="fas fa-columns" /> {dqReport.length} fields profiled
                    </span>
                    <span className="dr-dq-summary-item">
                      <i className="fas fa-shield-alt" /> {compAvg != null ? `${compAvg}% avg completeness` : 'completeness n/a'}
                    </span>
                    {totalNulls > 0 && (
                      <span className="dr-dq-summary-item dr-dq-summary-warn">
                        <i className="fas fa-exclamation-triangle" /> {totalNulls.toLocaleString()} null values
                      </span>
                    )}
                    {totalDups > 0 && (
                      <span className="dr-dq-summary-item dr-dq-summary-warn">
                        <i className="fas fa-copy" /> {totalDups.toLocaleString()} duplicate rows
                      </span>
                    )}
                    {totalNulls === 0 && totalDups === 0 && (
                      <span className="dr-dq-summary-item dr-dq-summary-ok">
                        <i className="fas fa-check-circle" /> No nulls or duplicates detected
                      </span>
                    )}
                    <button className="dr-dq-summary-expand" onClick={() => setDqExpanded(true)}>
                      View full report <i className="fas fa-table" />
                    </button>
                  </>
                );
              })()}
            </div>
          )}
        </section>
      )}

      {/* ═══════════════════════════════════════════════════════════════════
          WIDGET 2: FIELD INTELLIGENCE
          Purpose: Answer "what fields exist, what do they mean, where do they come from?"
      ═══════════════════════════════════════════════════════════════════ */}
      {totalFields > 0 && (
        <section className="dr-section">
          <div className="dr-section-header">
            <i className="fas fa-brain" />
            <div className="dr-section-title-group">
              <span className="dr-section-title">Field Intelligence</span>
              <span className="dr-section-desc">
                AI-classified fields with semantic roles — hover a role badge for its description
              </span>
            </div>
            <span className="dr-section-count">
              {activeFileGroup
                ? `${activeFileGroup.field_names?.length ?? 0} of ${totalFields} fields`
                : `${totalFields} fields`}
            </span>
            <div className="dr-view-tabs">
              {[
                { key: 'entity', label: 'By Entity',  icon: 'fa-sitemap' },
                { key: 'role',   label: 'By Role',    icon: 'fa-tag' },
                { key: 'all',    label: 'All Fields', icon: 'fa-list' },
              ].map(v => (
                <button
                  key={v.key}
                  className={`dr-view-tab${fieldView === v.key ? ' active' : ''}`}
                  onClick={() => setFieldView(v.key)}
                >
                  <i className={`fas ${v.icon}`} /> {v.label}
                </button>
              ))}
            </div>
          </div>

          {/* ── Per-file filter banner ──────────────────────────────────── */}
          {activeFileGroup && (
            <div className="dr-file-filter-bar">
              <i className="fas fa-filter" />
              <span className="dr-file-filter-name" title={activeFileGroup.name}>
                {activeFileGroup.name}
              </span>
              <span className="dr-file-filter-meta">
                {activeFileGroup.record_count != null
                  ? `${activeFileGroup.record_count} records · ` : ''}
                {activeFileGroup.field_names?.length ?? 0} fields
                {activeFileGroup.quality != null
                  ? ` · ${activeFileGroup.quality}% completeness` : ''}
              </span>
              <button
                className="dr-file-filter-clear"
                onClick={() => { setSelectedFile(null); setSamplePage(1); }}
                title="Show all files"
              >
                <i className="fas fa-times" /> Clear filter
              </button>
            </div>
          )}

          <div className="dr-field-groups">
            {displayedFieldGroups.map((grp, gi) => {
              const groupKey  = grp.name;
              const isOpen    = expandedGroups[groupKey] !== false; // default open
              const roleKey   = grp.roleKey;

              return (
                <div key={gi} className="dr-field-group">
                  <button
                    className="dr-field-group-hdr"
                    onClick={() => toggleGroup(groupKey)}
                    aria-expanded={isOpen}
                  >
                    <i className={`fas fa-chevron-${isOpen ? 'down' : 'right'} dr-chevron`} />
                    <span className="dr-field-group-name">{grp.name}</span>
                    <span className="dr-field-group-count">{grp.fields.length} fields</span>
                    {roleKey && roleKey !== 'unknown' && (
                      <span className="dr-field-group-hint" title={ROLE_DESC[roleKey] || ''}>
                        {ROLE_DESC[roleKey]?.substring(0, 70)}…
                      </span>
                    )}
                  </button>

                  {isOpen && (
                    <div className="dr-field-rows">
                      {grp.fields.map((f, fi) => {
                        const sem     = colSemMap[f] || {};
                        const role    = sem.semantic_role || 'unknown';
                        const confPct = parsePct(sem.confidence);
                        const mp       = mappingBySource[f];
                        const mpPct    = mp ? parsePct(mp.confidence) : 0;
                        const mpTier   = mpPct >= 80 ? 'high' : mpPct >= 60 ? 'medium' : 'low';
                        const samples  = sampleValuesByCol[f] || [];
                        const hasSub   = mp || samples.length > 0;
                        return (
                          <div key={fi} className={`dr-field-row${hasSub ? ' dr-field-row--has-sub' : ''}`}>
                            {/* ── top line: name / role / confidence ── */}
                            <span className="dr-field-name" title={f}>{f}</span>
                            {sem.canonical_name && sem.canonical_name !== f && (
                              <span
                                className="dr-field-canon"
                                title="AI-suggested canonical / standardised name"
                              >
                                <i className="fas fa-arrow-right" /> {sem.canonical_name}
                              </span>
                            )}
                            {sem.entity_hint && fieldView !== 'entity' && (
                              <span className="dr-field-entity">{sem.entity_hint}</span>
                            )}
                            <span
                              className={`dr-role-badge dr-role-${role}`}
                              title={ROLE_DESC[role] || role}
                            >
                              {ROLE_LABELS[role] || role}
                            </span>
                            {confPct > 0 && (
                              <span
                                className="dr-field-conf"
                                title={`${confPct}% certainty that this field serves the "${ROLE_LABELS[role] || role}" role`}
                              >
                                {confPct}%
                              </span>
                            )}
                            {/* ── sub-line: mapping target + sample values ── */}
                            {hasSub && (
                              <div className="dr-field-row-sub">
                                {mp && (
                                  <span
                                    className="dr-field-map-hint"
                                    title={`Maps to "${mp.targetField}" with ${mpPct}% confidence${mp.transformation ? ` · Transform: ${mp.transformation}` : ''}`}
                                  >
                                    <i className="fas fa-long-arrow-alt-right dr-field-map-arrow" />
                                    <span className="dr-field-map-tgt">{mp.targetField}</span>
                                    <span className={`dr-fmc dr-fmc-${mpTier}`}>{mpPct}%</span>
                                    {mp.transformation && (
                                      <span className="dr-field-map-xform">
                                        <i className="fas fa-cog" /> {mp.transformation}
                                      </span>
                                    )}
                                  </span>
                                )}
                                {samples.length > 0 && (
                                  <span className="dr-field-samples" title="Sample values from your data">
                                    {samples.map((v, si) => (
                                      <span key={si} className="dr-field-sample-val">
                                        {v.length > 16 ? `${v.substring(0, 16)}…` : v}
                                      </span>
                                    ))}
                                  </span>
                                )}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Semantic summary footer */}
          {semanticProfile?.summary && (
            <div className="dr-sem-footer">
              {semanticProfile.summary.top_entity_class && (
                <span>
                  <i className="fas fa-crown" />
                  Dominant entity: <strong>{semanticProfile.summary.top_entity_class}</strong>
                </span>
              )}
              {semanticProfile.summary.relationship_count > 0 && (
                <span>
                  <i className="fas fa-link" />
                  {semanticProfile.summary.relationship_count} cross-field relationship
                  {semanticProfile.summary.relationship_count !== 1 ? 's' : ''} detected
                </span>
              )}
              {semanticProfile.summary.high_confidence_semantics > 0 && (
                <span>
                  <i className="fas fa-check-double" />
                  {semanticProfile.summary.high_confidence_semantics} high-confidence classifications
                </span>
              )}
            </div>
          )}
        </section>
      )}

      {/* ═══════════════════════════════════════════════════════════════════
          WIDGET 3: MAPPING SUGGESTIONS
          Purpose: Answer "what will map where, and how confident should I be?"
      ═══════════════════════════════════════════════════════════════════ */}
      {mappings.length > 0 && (
        <section className="dr-section">
          <div className="dr-section-header">
            <i className="fas fa-random" />
            <div className="dr-section-title-group">
              <span className="dr-section-title">Mapping Suggestions</span>
              <span className="dr-section-desc">
                Per-field mapping targets are shown inline in Field Intelligence above ↑.
                Use this panel to bulk-review confidence tiers and carry all suggestions forward to Step 3 (Map).
              </span>
            </div>
            <span className="dr-section-count">{mappings.length} suggestions → Step 3</span>
          </div>

          {/* Confidence legend — always visible so users know what % means */}
          <div className="dr-conf-legend">
            <span className="dr-conf-legend-title">
              <i className="fas fa-info-circle" /> What does the % mean?
            </span>
            <span className="dr-conf-legend-item dr-conf-legend-high">
              <span className="dr-conf-dot" /> ≥ 80% Strong — name, type &amp; semantic role align
            </span>
            <span className="dr-conf-legend-item dr-conf-legend-medium">
              <span className="dr-conf-dot" /> 60-79% Name match — identical names, verify type
            </span>
            <span className="dr-conf-legend-item dr-conf-legend-low">
              <span className="dr-conf-dot" /> &lt; 60% Weak — partial similarity, manual review
            </span>
          </div>

          {[
            {
              tierKey: 'high',
              maps: highMaps,
              label: `Strong matches (≥ 80%) — ${highMaps.length} suggestions`,
              icon: 'fa-check-double',
              defaultOpen: true,
            },
            {
              tierKey: 'medium',
              maps: medMaps,
              label: `Name matches (60-79%) — ${medMaps.length} suggestions · Review recommended`,
              icon: 'fa-equals',
              defaultOpen: true,
            },
            {
              tierKey: 'low',
              maps: lowMaps,
              label: `Weak matches (< 60%) — ${lowMaps.length} suggestions · Manual review required`,
              icon: 'fa-question-circle',
              defaultOpen: false,
            },
          ].filter(t => t.maps.length > 0).map(({ tierKey, maps, label, icon, defaultOpen }) => {
            const grpKey = `map-${tierKey}`;
            const isOpen = expandedGroups[grpKey] !== undefined
              ? expandedGroups[grpKey]
              : defaultOpen;

            return (
              <div key={tierKey} className={`dr-map-tier dr-map-tier-${tierKey}`}>
                <button
                  className="dr-map-tier-hdr"
                  onClick={() => toggleGroup(grpKey)}
                  aria-expanded={isOpen}
                >
                  <i className={`fas fa-chevron-${isOpen ? 'down' : 'right'} dr-chevron`} />
                  <i className={`fas ${icon}`} />
                  <span>{label}</span>
                  <span className={`dr-tier-badge dr-tier-badge-${tierKey}`}>
                    {tierKey === 'high' ? 'Auto-apply safe' :
                     tierKey === 'medium' ? 'Review recommended' : 'Manual review'}
                  </span>
                </button>

                {isOpen && (
                  <div className="dr-map-rows">
                    <div className="dr-map-row dr-map-row-head">
                      <span className="dr-map-src">Source Field</span>
                      <span className="dr-map-arrow" />
                      <span className="dr-map-tgt">Target Field</span>
                      <span className="dr-map-role-col">Semantic Role</span>
                      <span className="dr-map-xform-col">Transform</span>
                      <span className="dr-map-conf-col">Confidence</span>
                    </div>
                    {maps.map((m, mi) => {
                      const pct   = parsePct(m.confidence);
                      const sem   = colSemMap[m.sourceField];
                      const role  = sem?.semantic_role || 'unknown';
                      return (
                        <div key={mi} className="dr-map-row">
                          <span className="dr-map-src" title={m.sourceField}>
                            {m.sourceField}
                          </span>
                          <span className="dr-map-arrow">
                            <i className="fas fa-long-arrow-alt-right" />
                          </span>
                          <span className="dr-map-tgt" title={m.targetField}>
                            {m.targetField}
                          </span>
                          <span
                            className={`dr-map-role-col dr-role-badge dr-role-${role}`}
                            title={ROLE_DESC[role] || role}
                          >
                            {ROLE_LABELS[role] || role}
                          </span>
                          {m.transformation ? (
                            <span
                              className="dr-map-xform-col dr-xform-badge"
                              title={`Transform: ${m.transformation}`}
                            >
                              <i className="fas fa-cog" /> {m.transformation}
                            </span>
                          ) : (
                            <span className="dr-map-xform-col dr-xform-none">direct</span>
                          )}
                          <ConfBar pct={pct} confTier={tierKey} />
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </section>
      )}

      {/* ═══════════════════════════════════════════════════════════════════
          WIDGET 4: SAMPLE DATA EXPLORER
          Purpose: Answer "what does the actual data look like?"
                   Paginated (10/page), column headers annotated with semantic role
      ═══════════════════════════════════════════════════════════════════ */}
      {allRecords.length > 0 && (
        <section className="dr-section">
          <div className="dr-section-header">
            <i className="fas fa-table" />
            <div className="dr-section-title-group">
              <span className="dr-section-title">Sample Data Explorer</span>
              <span className="dr-section-desc">
                Validate mapping proposals — each column header shows its proposed target field.
                Null/blank cells are flagged so you can spot data quality issues before Step 3.
                {activeFileGroup && <> · Showing <strong>{sampleCols.length}</strong> columns for <em>{activeFileGroup.name}</em></>}
              </span>
            </div>
            <span className="dr-section-count">
              {activeFileGroup
                ? `${sampleCols.length} cols · ${totalDisplayed} rows`
                : `Rows ${(samplePage - 1) * PAGE_SIZE + 1}–${Math.min(samplePage * PAGE_SIZE, totalRecords)} of ${totalRecords.toLocaleString()}`}
            </span>
          </div>

          <div className="dr-sample-wrap">
            <table className="dr-sample-table">
              <thead>
                <tr>
                  <th className="dr-sample-rownum">#</th>
                  {sampleCols.map(col => {
                    const sem   = colSemMap[col];
                    const role  = sem?.semantic_role;
                    const colMp = mappingBySource[col];
                    return (
                      <th
                        key={col}
                        className={`dr-sample-th${role && role !== 'unknown' ? ` dr-sample-th-${role}` : ''}`}
                        title={
                          role && role !== 'unknown'
                            ? `${ROLE_LABELS[role] || role}: ${ROLE_DESC[role] || ''}`
                            : col
                        }
                      >
                        <div className="dr-sample-col-name">{col}</div>
                        {role && role !== 'unknown' && (
                          <div className={`dr-sample-col-role dr-role-badge dr-role-${role}`}>
                            {ROLE_LABELS[role]}
                          </div>
                        )}
                        {colMp && (
                          <div
                            className={`dr-sample-col-target dr-sample-col-target-${parsePct(colMp.confidence) >= 80 ? 'high' : parsePct(colMp.confidence) >= 60 ? 'medium' : 'low'}`}
                            title={`Maps to "${colMp.targetField}" (${parsePct(colMp.confidence)}% confidence)`}
                          >
                            <i className="fas fa-arrow-right" /> {colMp.targetField}
                          </div>
                        )}
                      </th>
                    );
                  })}
                </tr>
              </thead>
              <tbody>
                {pageRecords.map((row, ri) => (
                  <tr key={ri}>
                    <td className="dr-sample-rownum">
                      {(samplePage - 1) * PAGE_SIZE + ri + 1}
                    </td>
                    {sampleCols.map(col => {
                      const sem     = colSemMap[col];
                      const role    = sem?.semantic_role;
                      const raw     = row[col];
                      const val     = String(raw ?? '—');
                      const isEmpty = raw === null || raw === undefined
                        || val.trim() === '' || val === '—'
                        || val.toLowerCase() === 'null'
                        || val.toLowerCase() === 'none';
                      const hasMp   = !!mappingBySource[col];
                      const classes = [
                        role && role !== 'unknown' ? `dr-cell-${role}` : '',
                        isEmpty ? (hasMp ? 'dr-cell-null-mapped' : 'dr-cell-null') : '',
                      ].filter(Boolean).join(' ');
                      return (
                        <td
                          key={col}
                          title={isEmpty ? `⚠ Empty value${hasMp ? ` — this field maps to "${mappingBySource[col].targetField}"` : ''}` : val}
                          className={classes || undefined}
                        >
                          {isEmpty
                            ? <span className="dr-cell-null-marker" aria-label="empty">—</span>
                            : val.length > 50 ? `${val.substring(0, 50)}…` : val}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <div className="dr-pagination">
              <button
                className="dr-page-btn"
                onClick={() => setSamplePage(p => 1)}
                disabled={samplePage === 1}
                title="First page"
              >
                <i className="fas fa-angle-double-left" />
              </button>
              <button
                className="dr-page-btn"
                onClick={() => setSamplePage(p => Math.max(1, p - 1))}
                disabled={samplePage === 1}
              >
                <i className="fas fa-chevron-left" /> Prev
              </button>
              <span className="dr-page-info">
                Page {samplePage} of {totalPages}
                <span className="dr-page-total"> ({totalRecords} records)</span>
              </span>
              <button
                className="dr-page-btn"
                onClick={() => setSamplePage(p => Math.min(totalPages, p + 1))}
                disabled={samplePage === totalPages}
              >
                Next <i className="fas fa-chevron-right" />
              </button>
              <button
                className="dr-page-btn"
                onClick={() => setSamplePage(totalPages)}
                disabled={samplePage === totalPages}
                title="Last page"
              >
                <i className="fas fa-angle-double-right" />
              </button>
            </div>
          )}
        </section>
      )}

    </div>
  );
}
