/**
 * DiscoveryResults (Refactored) — World-class Discovery Step 2 component
 *
 * ✨ NEW ARCHITECTURE: 6-component modular design
 * 
 * Problems FIXED:
 * ✅ Redundancy → Each metric shown once in appropriate context
 * ✅ Missing Intelligence → DataQualityInsights + detectAnomalies() function
 * ✅ Poor Hierarchy → DiscoveryStatusCard unified status at top
 * ✅ No Storytelling → Components flow logically: Status → Quality → Fields → Mappings → Data → Actions
 * ✅ End-User Unfriendly → Plain English explanations throughout
 * ✅ Weak Actionability → RecommendedActions with prioritized next steps
 *
 * Displays (6 sections):
 * 1. DiscoveryStatusCard — Unified status + readiness gauge + critical warnings
 * 2. DataQualityInsights — Quality scorecard + AI-powered anomaly detection
 * 3. FieldQualityDetail — Risk-sorted fields (HIGH/MEDIUM/LOW)
 * 4. MappingIntelligence — Confidence-tiered field mappings (80%+/60-80%/<60%)
 * 5. SampleDataPreview — Contextualized sample records with quality warnings
 * 6. RecommendedActions — Prioritized "what's next?" guidance
 */

import React, { useState, useMemo, useCallback } from 'react';
import writeXlsxFile from 'write-excel-file';

// ── Import 6 world-class specialized components
import DiscoveryStatusCard from './discovery/DiscoveryStatusCard.jsx';
import DataQualityInsights from './discovery/DataQualityInsights.jsx';
import FieldQualityDetail from './discovery/FieldQualityDetail.jsx';
import MappingIntelligence from './discovery/MappingIntelligence.jsx';
import SampleDataPreview from './discovery/SampleDataPreview.jsx';
import RecommendedActions from './discovery/RecommendedActions.jsx';

// ── Import utility functions for calculations and anomaly detection
import {
  calculateReadinessScore,
  getReadinessStatus,
  detectAnomalies,
  generateRecommendedActions,
  calculateQualitySummary,
  groupFieldsByRisk,
  tierMappings,
  parsePct,
} from './discovery/discoveryUtils.js';

// ── Import export utilities
import { buildFilePivotRows, buildIssueEntries, buildIssuePivotRows } from './dqExportUtils.js';

// ── Import unified styles
import './discovery/DiscoveryRefactored.css';
import './DiscoveryResults.css'; // Keep for any legacy KPI styling

// ── Constants (preserved from original) ──────────────────────────────────

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

// ── Main component ────────────────────────────────────────────────────────

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
  // ── State ────────────────────────────────────────────────────────────────
  const [selectedFile, setSelectedFile] = useState(null);
  const [dqComments, setDqComments] = useState({});
  const [samplePage, setSamplePage] = useState(1);
  const PAGE_SIZE = 10;

  // ── KPI derivations (from original) ──────────────────────────────────────
  const _inferredFields = introspect?.inferred_source_fields;
  const totalFields = (_inferredFields?.length > 0 ? _inferredFields.length : null) ?? mappings.length;
  const allRecords = Array.isArray(sample?.records) ? sample.records : [];
  const totalRecords = allRecords.length;
  const totalFiles = sample?.total_files ?? sample?.source_files?.length ?? null;
  const mappingCount = mappings.length;

  const sodaInsight = insights.find(i => /soda|quality/i.test(i.title || ''));
  const qualityScore = sodaResult?.overall_score != null
    ? Math.round(Number(sodaResult.overall_score) * 100)
    : (() => {
        const m = (sodaInsight?.detail || '').match(/(\d+)%/);
        return m ? parseInt(m[1], 10) : null;
      })();
  const qualityStatus = sodaResult?.status
    ?? (qualityScore != null
      ? (qualityScore >= 80 ? 'pass' : qualityScore >= 60 ? 'warn' : 'fail')
      : null);

  // ── DQ Report (from original) ────────────────────────────────────────────
  const dqReport = useMemo(() => {
    const rows = [];
    const files = sample?.source_files || [];
    files.forEach(f => {
      const fname = f.name || '—';
      const totalRec = f.record_count ?? 0;
      const dupRows = f.duplicate_rows ?? 0;
      const stats = Array.isArray(f.field_stats) ? f.field_stats : [];
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

  // ── Issue records (from original) ────────────────────────────────────────
  const dqIssueRecords = useMemo(
    () => buildIssueEntries(allRecords, sample?.source_files || []),
    [allRecords, sample]
  );

  const dqFilePivot = useMemo(() => buildFilePivotRows(dqReport), [dqReport]);
  const dqIssuePivot = useMemo(() => buildIssuePivotRows(dqIssueRecords), [dqIssueRecords]);

  // ── Mapping tiers (from original) ────────────────────────────────────────
  const { highMaps, medMaps, lowMaps } = useMemo(() => {
    const sorted = [...mappings].sort(
      (a, b) => parsePct(b.confidence) - parsePct(a.confidence));
    return {
      highMaps: sorted.filter(m => parsePct(m.confidence) >= 80),
      medMaps: sorted.filter(m => parsePct(m.confidence) >= 60 && parsePct(m.confidence) < 80),
      lowMaps: sorted.filter(m => parsePct(m.confidence) < 60),
    };
  }, [mappings]);

  // ── Discovery utility calculations ───────────────────────────────────────
  const readinessScore = useMemo(() => {
    const nullCount = dqReport.reduce((s, r) => s + (r.nullCount || 0), 0);
    const duplicateRows = dqReport.length > 0 
      ? dqReport[0].duplicateRows || 0 
      : 0;
    const compRows = dqReport.filter(r => r.completeness != null);
    const avgCompleteness = compRows.length
      ? Math.round(compRows.reduce((s, r) => s + r.completeness, 0) / compRows.length)
      : 0;
    const fieldsDetected = totalFields || 0;
    
    return calculateReadinessScore(
      qualityScore || 0,
      nullCount,
      duplicateRows,
      avgCompleteness,
      fieldsDetected
    );
  }, [dqReport, qualityScore, totalFields]);

  const fieldRisks = useMemo(() => groupFieldsByRisk(dqReport), [dqReport]);

  const anomalies = useMemo(() => 
    detectAnomalies(allRecords, dqReport, semanticProfile, mappings),
    [allRecords, dqReport, semanticProfile, mappings]
  );

  const mappingTiers = useMemo(() => tierMappings(mappings), [mappings]);

  const unreadableFiles = useMemo(() => 
    (sample?.source_files || []).filter(f => !f.field_names || f.field_names.length === 0),
    [sample]
  );

  const recommendedActions = useMemo(() =>
    generateRecommendedActions(readinessScore, fieldRisks, anomalies, mappingTiers, unreadableFiles),
    [readinessScore, fieldRisks, anomalies, mappingTiers, unreadableFiles]
  );

  // ── Export to CSV (preserved from original) ─────────────────────────────
  const exportDqCsv = useCallback(() => {
    const csvEscape = (v) => {
      const s = String(v ?? '');
      return /[\n\r,"]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    };

    const summaryLines = [
      '# Data Quality Summary',
      `Run ID,${csvEscape(runId || 'discovery')}`,
      `Total Fields Profiled,${dqReport.length}`,
      `Total Null Values,${dqReport.reduce((s, r) => s + (r.nullCount || 0), 0)}`,
      `Average Completeness (%),${dqReport.filter(r => r.completeness != null).length > 0 ? Math.round(dqReport.filter(r => r.completeness != null).reduce((s, r) => s + r.completeness, 0) / dqReport.filter(r => r.completeness != null).length) : 'N/A'}`,
      `Sample Records Inspected,${allRecords.length}`,
      '',
    ];

    const detailHeader = 'File,Field,Type,Total Records,Null Count,Unique Values,Completeness (%),Duplicate Rows,Review Comment';
    const detailLines = dqReport.map(r => {
      const commentKey = `${r.file}-${r.field}`;
      return [
        r.file, r.field, r.type, r.totalRecords,
        r.nullCount ?? '', r.uniqueCount ?? '',
        r.completeness ?? '', r.duplicateRows,
        dqComments[commentKey] || '',
      ].map(csvEscape).join(',');
    });

    const csv = [
      ...summaryLines,
      '# Per-Field Detail',
      detailHeader,
      ...detailLines,
    ].join('\n');

    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `dq-report-${runId || 'discovery'}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 150);
  }, [dqReport, allRecords, runId, dqComments]);

  // ── Export to XLSX (preserved from original) ────────────────────────────
  const exportDqXlsx = useCallback(async () => {
    if (!dqReport.length) return;

    const HEADER_STYLE = { fontWeight: 'bold', backgroundColor: '#1F3864', color: '#FFFFFF', align: 'center' };
    const compStyle = (pct) => {
      if (pct == null) return {};
      if (pct >= 90) return { backgroundColor: '#C6EFCE' };
      if (pct >= 70) return { backgroundColor: '#FFEB9C' };
      return { backgroundColor: '#FFC7CE' };
    };

    const headerRow = [
      { value: 'File Name', ...HEADER_STYLE },
      { value: 'Field Name', ...HEADER_STYLE },
      { value: 'Type', ...HEADER_STYLE },
      { value: 'Total Records', ...HEADER_STYLE },
      { value: 'Null Count', ...HEADER_STYLE },
      { value: 'Unique Values', ...HEADER_STYLE },
      { value: 'Completeness (%)', ...HEADER_STYLE },
      { value: 'Duplicate Rows', ...HEADER_STYLE },
      { value: 'Review Comment', ...HEADER_STYLE },
    ];

    const dataRows = dqReport.map(r => {
      const commentKey = `${r.file}-${r.field}`;
      return [
        { value: r.file || '' },
        { value: r.field || '', fontWeight: 'bold' },
        { value: r.type || '' },
        { value: r.totalRecords ?? 0, type: Number },
        { value: r.nullCount ?? 0, type: Number },
        { value: r.uniqueCount ?? 0, type: Number },
        { value: r.completeness ?? 0, type: Number, ...compStyle(r.completeness) },
        { value: r.duplicateRows ?? 0, type: Number },
        { value: dqComments[commentKey] || '' },
      ];
    });

    await writeXlsxFile(
      [[HEADER_STYLE, ...dataRows]],
      {
        sheets: ['Field Detail'],
        fileName: `dq-report-${runId || 'discovery'}.xlsx`,
        columns: [
          { width: 28 }, { width: 20 }, { width: 12 }, { width: 14 },
          { width: 12 }, { width: 14 }, { width: 16 }, { width: 14 }, { width: 40 },
        ],
      }
    );
  }, [dqReport, runId, dqComments]);

  // ── Handle action completion ─────────────────────────────────────────────
  const handleActionComplete = useCallback((actionId) => {
    // User marked an action as complete; could integrate with backend here
    console.log('Action completed:', actionId);
  }, []);

  // ── Don't render if there's nothing ──────────────────────────────────────
  if (!introspect && !mappings.length && !allRecords.length && !insights.length) {
    return null;
  }

  // ── RENDER: 6-component modular architecture ─────────────────────────────
  return (
    <div className="dr-root discovery-root-refactored">

      {/* ═══════════════════════════════════════════════════════════════════
          SECTION 1: DISCOVERY STATUS CARD
          Unified health + readiness + critical warnings
      ═══════════════════════════════════════════════════════════════════ */}
      <DiscoveryStatusCard
        dqReport={dqReport}
        sodaResult={sodaResult}
        qualityScore={qualityScore}
        totalFiles={totalFiles}
        totalRecords={totalRecords}
        totalFields={totalFields}
        mappingCount={mappingCount}
        highMaps={highMaps}
        medMaps={medMaps}
        lowMaps={lowMaps}
        sample={sample}
      />

      {/* ═══════════════════════════════════════════════════════════════════
          SECTION 2: DATA QUALITY INSIGHTS
          Quality scorecard + AI-powered anomaly detection
      ═══════════════════════════════════════════════════════════════════ */}
      <DataQualityInsights
        dqReport={dqReport}
        sodaResult={sodaResult}
        qualityScore={qualityScore}
        insights={insights}
        sample={sample}
        semanticProfile={semanticProfile}
        mappings={mappings}
      />

      {/* ═══════════════════════════════════════════════════════════════════
          SECTION 3: FIELD QUALITY DETAIL
          Risk-sorted fields (HIGH/MEDIUM/LOW)
      ═══════════════════════════════════════════════════════════════════ */}
      <FieldQualityDetail
        dqReport={dqReport}
        selectedFile={selectedFile}
        onFileSelect={setSelectedFile}
      />

      {/* ═══════════════════════════════════════════════════════════════════
          SECTION 4: MAPPING INTELLIGENCE
          Confidence-tiered field mappings with AI reasoning
      ═══════════════════════════════════════════════════════════════════ */}
      <MappingIntelligence mappings={mappings} />

      {/* ═══════════════════════════════════════════════════════════════════
          SECTION 5: SAMPLE DATA PREVIEW
          Contextualized sample records with quality awareness
      ═══════════════════════════════════════════════════════════════════ */}
      <SampleDataPreview
        sample={sample}
        dqReport={dqReport}
        selectedFile={selectedFile}
        onFileSelect={setSelectedFile}
      />

      {/* ═══════════════════════════════════════════════════════════════════
          SECTION 6: RECOMMENDED ACTIONS
          Prioritized "what's next?" guidance
      ═══════════════════════════════════════════════════════════════════ */}
      <RecommendedActions
        readinessScore={readinessScore}
        fieldRisks={fieldRisks}
        anomalies={anomalies}
        mappingTiers={mappingTiers}
        unreadableFiles={unreadableFiles}
        onAction={handleActionComplete}
      />

      {/* ═══════════════════════════════════════════════════════════════════
          EXPORT & LEGACY DATA QUALITY REPORT TABLE
          Optional expanded view for auditing/compliance
      ═══════════════════════════════════════════════════════════════════ */}
      {dqReport.length > 0 && (
        <section className="dr-section dr-section--exports">
          <div className="dr-section-header">
            <i className="fas fa-download" />
            <div className="dr-section-title-group">
              <span className="dr-section-title">Export & Compliance Reports</span>
              <span className="dr-section-desc">
                Download detailed quality reports for audit trails, compliance reviews, or enterprise integration.
              </span>
            </div>
          </div>

          <div className="dr-export-buttons">
            <button className="dr-export-btn dr-export-csv" onClick={exportDqCsv} title="Export as CSV">
              <i className="fas fa-file-csv" /> Export CSV Report
            </button>
            <button className="dr-export-btn dr-export-xlsx" onClick={exportDqXlsx} title="Export as Excel">
              <i className="fas fa-file-excel" /> Export Excel Report
            </button>
            <span className="dr-export-note">
              {Object.keys(dqComments).length > 0 && (
                <>
                  <i className="fas fa-sticky-note" />
                  {Object.keys(dqComments).length} review comments included
                </>
              )}
            </span>
          </div>
        </section>
      )}

    </div>
  );
}
