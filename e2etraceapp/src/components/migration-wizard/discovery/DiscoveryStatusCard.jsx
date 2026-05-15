/**
 * DiscoveryStatusCard — Consolidated discovery overview
 * Shows: Overall status + Readiness score + Key metrics summary + Health indicators
 */

import React from 'react';
import {
  calculateReadinessScore,
  getReadinessStatus,
  calculateQualitySummary,
  STATUS_MESSAGES,
} from './discoveryUtils.js';

export default function DiscoveryStatusCard({ dqReport, sodaResult, qualityScore, totalFiles, totalRecords, totalFields, mappingCount, highMaps, medMaps, lowMaps, sample }) {
  // Calculate readiness score
  const qualitySummary = calculateQualitySummary(dqReport, sodaResult, qualityScore);
  const readinessScore = calculateReadinessScore(
    qualityScore,
    qualitySummary.totalNulls,
    qualitySummary.totalDups,
    qualitySummary.avgCompleteness,
    totalFields
  );
  const status = getReadinessStatus(readinessScore);
  const statusMsg = STATUS_MESSAGES[status];

  // Identify any unreadable/empty files
  const unreadableFiles = (sample?.source_files || []).filter(
    f => f.record_count === 0 && (f.type === 'json' || f.type === 'xml')
  );

  return (
    <div className="dsc-root">
      <div className="dsc-container">
        {/* Status Badge + Score */}
        <div className="dsc-status-section">
          <div className={`dsc-status-badge dsc-status-${status}`}>
            <i className={`fas ${statusMsg.icon}`} />
            <div className="dsc-status-text">
              <div className="dsc-status-label">{statusMsg.label}</div>
              <div className="dsc-status-message">{statusMsg.message}</div>
            </div>
          </div>

          <div className={`dsc-readiness-gauge dsc-readiness-${status}`}>
            <svg viewBox="0 0 120 120" className="dsc-gauge-svg">
              {/* Background circle */}
              <circle cx="60" cy="60" r="54" className="dsc-gauge-bg" />
              {/* Progress arc */}
              <circle
                cx="60"
                cy="60"
                r="54"
                className="dsc-gauge-progress"
                style={{
                  strokeDasharray: `${(readinessScore / 100) * 339.3} 339.3`,
                }}
              />
            </svg>
            <div className="dsc-gauge-content">
              <div className="dsc-gauge-score">{readinessScore}</div>
              <div className="dsc-gauge-label">Readiness</div>
            </div>
          </div>
        </div>

        {/* Key Metrics Grid */}
        <div className="dsc-metrics-grid">
          {/* Metric 1: Files & Fields */}
          <div className="dsc-metric">
            <div className="dsc-metric-label">Data Coverage</div>
            <div className="dsc-metric-values">
              <span className="dsc-metric-value">
                <strong>{totalFiles}</strong> files
              </span>
              <span className="dsc-metric-separator">•</span>
              <span className="dsc-metric-value">
                <strong>{totalFields}</strong> fields
              </span>
            </div>
            <div className="dsc-metric-sub">{totalRecords.toLocaleString()} sample records</div>
          </div>

          {/* Metric 2: Quality Score */}
          <div className="dsc-metric">
            <div className="dsc-metric-label">Data Quality</div>
            <div className="dsc-metric-values">
              <span className={`dsc-metric-value dsc-quality-${status}`}>
                <strong>{qualityScore}%</strong>
              </span>
            </div>
            <div className="dsc-metric-sub">
              {sodaResult?.status ? `SODA gate: ${sodaResult.status.toUpperCase()}` : 'Not scanned'}
            </div>
          </div>

          {/* Metric 3: Completeness */}
          <div className="dsc-metric">
            <div className="dsc-metric-label">Completeness</div>
            <div className="dsc-metric-values">
              <span className="dsc-metric-value">
                <strong>{qualitySummary.avgCompleteness}%</strong> avg
              </span>
            </div>
            <div className="dsc-metric-sub">
              {qualitySummary.fieldWithLowCompleteness > 0
                ? `${qualitySummary.fieldWithLowCompleteness} fields <70%`
                : 'All fields healthy'}
            </div>
          </div>

          {/* Metric 4: Issues */}
          <div className="dsc-metric">
            <div className="dsc-metric-label">Data Issues</div>
            <div className="dsc-metric-values">
              {qualitySummary.totalNulls > 0 || qualitySummary.totalDups > 0 ? (
                <>
                  {qualitySummary.totalNulls > 0 && (
                    <span className="dsc-metric-value dsc-issue">
                      <strong>{qualitySummary.totalNulls}</strong> nulls
                    </span>
                  )}
                  {qualitySummary.totalDups > 0 && (
                    <span className="dsc-metric-value dsc-issue">
                      <strong>{qualitySummary.totalDups}</strong> dups
                    </span>
                  )}
                </>
              ) : (
                <span className="dsc-metric-value dsc-ok">
                  <i className="fas fa-check-circle" /> No nulls/dups
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Health Indicators (Traffic Light) */}
        <div className="dsc-health-indicators">
          <div className="dsc-indicator">
            <div className={`dsc-indicator-light ${totalFiles === 10 ? 'dsc-ok' : 'dsc-warn'}`} />
            <span className="dsc-indicator-text">
              Files scanned: <strong>{totalFiles}/10</strong>
            </span>
          </div>

          <div className="dsc-indicator">
            <div
              className={`dsc-indicator-light ${
                qualitySummary.avgCompleteness >= 95
                  ? 'dsc-ok'
                  : qualitySummary.avgCompleteness >= 80
                  ? 'dsc-warn'
                  : 'dsc-fail'
              }`}
            />
            <span className="dsc-indicator-text">
              Data completeness: <strong>{qualitySummary.avgCompleteness}%</strong>
            </span>
          </div>

          <div className="dsc-indicator">
            <div className={`dsc-indicator-light ${unreadableFiles.length === 0 ? 'dsc-ok' : 'dsc-fail'}`} />
            <span className="dsc-indicator-text">
              Readable sources:{' '}
              <strong>
                {totalFiles - unreadableFiles.length}/{totalFiles}
              </strong>
            </span>
          </div>

          <div className="dsc-indicator">
            <div
              className={`dsc-indicator-light ${
                highMaps.length > 0 && medMaps.length + lowMaps.length === 0
                  ? 'dsc-ok'
                  : medMaps.length > 0 || lowMaps.length > 0
                  ? 'dsc-warn'
                  : 'dsc-ok'
              }`}
            />
            <span className="dsc-indicator-text">
              Mapping confidence: <strong>{highMaps.length} strong</strong>,{' '}
              <strong>{medMaps.length} review</strong>, <strong>{lowMaps.length} weak</strong>
            </span>
          </div>
        </div>

        {/* Critical Warnings (if any) */}
        {(unreadableFiles.length > 0 || qualitySummary.fieldWithLowCompleteness > 0) && (
          <div className="dsc-warnings">
            {unreadableFiles.length > 0 && (
              <div className="dsc-warning dsc-warning-critical">
                <i className="fas fa-exclamation-circle" />
                <span>
                  <strong>{unreadableFiles.length} JSON/XML file(s) are empty or unreadable.</strong> Check source connection
                  settings.
                </span>
              </div>
            )}
            {qualitySummary.fieldWithLowCompleteness > 0 && (
              <div className="dsc-warning dsc-warning-caution">
                <i className="fas fa-exclamation-triangle" />
                <span>
                  <strong>{qualitySummary.fieldWithLowCompleteness} field(s) have low completeness (&lt;70%).</strong> Review
                  before mapping.
                </span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
