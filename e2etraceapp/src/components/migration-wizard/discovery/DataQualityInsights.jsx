/**
 * DataQualityInsights — Quality metrics and AI-powered anomaly detection
 * Shows: SODA results, anomalies, trust breakdown, and actionable insights
 */

import React, { useState, useMemo } from 'react';
import { detectAnomalies, calculateQualitySummary } from './discoveryUtils.js';

export default function DataQualityInsights({
  dqReport,
  sodaResult,
  qualityScore,
  insights = [],
  sample,
  semanticProfile,
  mappings,
}) {
  const [anomaliesExpanded, setAnomaliesExpanded] = useState(true);

  const qualitySummary = calculateQualitySummary(dqReport, sodaResult, qualityScore);
  const anomalies = useMemo(
    () => detectAnomalies(sample, dqReport, semanticProfile, mappings),
    [sample, dqReport, semanticProfile, mappings]
  );

  const sodaInsights = insights.filter(i => /soda|quality/i.test(i.title || ''));

  return (
    <div className="dqi-root">
      <div className="dqi-container">
        {/* Section: Quality Scorecard */}
        <section className="dqi-section">
          <div className="dqi-section-header">
            <i className="fas fa-chart-line" />
            <h3 className="dqi-section-title">Data Quality Scorecard</h3>
          </div>

          <div className="dqi-scorecard">
            {/* Overall Score */}
            <div className="dqi-score-box">
              <div className="dqi-score-label">Overall Quality Score</div>
              <div className={`dqi-score-value dqi-score-${qualityScore >= 80 ? 'high' : qualityScore >= 60 ? 'medium' : 'low'}`}>
                {qualityScore}%
              </div>
              <div className="dqi-score-sub">
                {sodaResult?.status ? `SODA Gate: ${sodaResult.status.toUpperCase()}` : 'Not scanned'}
              </div>
            </div>

            {/* Metrics Grid */}
            <div className="dqi-metrics-grid">
              <div className="dqi-metric-item">
                <div className="dqi-metric-icon dqi-metric-completeness">
                  <i className="fas fa-fill" />
                </div>
                <div className="dqi-metric-content">
                  <div className="dqi-metric-label">Completeness</div>
                  <div className="dqi-metric-value">{qualitySummary.avgCompleteness}%</div>
                  <div className="dqi-metric-sub">
                    {qualitySummary.avgCompleteness >= 95
                      ? 'Excellent'
                      : qualitySummary.avgCompleteness >= 80
                      ? 'Good'
                      : 'Needs attention'}
                  </div>
                </div>
              </div>

              <div className="dqi-metric-item">
                <div className="dqi-metric-icon dqi-metric-nulls">
                  <i className="fas fa-minus-circle" />
                </div>
                <div className="dqi-metric-content">
                  <div className="dqi-metric-label">Null Values</div>
                  <div className="dqi-metric-value">{qualitySummary.totalNulls}</div>
                  <div className="dqi-metric-sub">
                    {qualitySummary.fieldsWithNulls > 0
                      ? `${qualitySummary.fieldsWithNulls} fields affected`
                      : 'None detected'}
                  </div>
                </div>
              </div>

              <div className="dqi-metric-item">
                <div className="dqi-metric-icon dqi-metric-duplicates">
                  <i className="fas fa-copy" />
                </div>
                <div className="dqi-metric-content">
                  <div className="dqi-metric-label">Duplicate Rows</div>
                  <div className="dqi-metric-value">{qualitySummary.totalDups}</div>
                  <div className="dqi-metric-sub">
                    {qualitySummary.fieldsWithDups > 0
                      ? `${qualitySummary.fieldsWithDups} files affected`
                      : 'None detected'}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Quality Issues Summary */}
          {(sodaResult?.issues_count > 0 || qualitySummary.totalNulls > 0 || qualitySummary.totalDups > 0) && (
            <div className="dqi-issues-summary">
              <div className="dqi-issues-title">
                <i className="fas fa-exclamation-triangle" /> Issues Detected
              </div>
              <ul className="dqi-issues-list">
                {qualitySummary.totalNulls > 0 && (
                  <li>
                    <strong>{qualitySummary.totalNulls}</strong> null/empty values across{' '}
                    <strong>{qualitySummary.fieldsWithNulls}</strong> fields
                  </li>
                )}
                {qualitySummary.totalDups > 0 && (
                  <li>
                    <strong>{qualitySummary.totalDups}</strong> duplicate rows found in{' '}
                    <strong>{qualitySummary.fieldsWithDups}</strong> files
                  </li>
                )}
                {qualitySummary.fieldWithLowCompleteness > 0 && (
                  <li>
                    <strong>{qualitySummary.fieldWithLowCompleteness}</strong> fields have completeness &lt;70%
                  </li>
                )}
                {sodaResult?.issues_count > 0 && (
                  <li>
                    <strong>{sodaResult.issues_count}</strong> SODA validation rule violations
                  </li>
                )}
              </ul>
            </div>
          )}
        </section>

        {/* Section: Anomaly Detection */}
        {anomalies.length > 0 && (
          <section className="dqi-section dqi-section-anomalies">
            <div className="dqi-section-header">
              <button
                className="dqi-section-toggle"
                onClick={() => setAnomaliesExpanded(!anomaliesExpanded)}
                aria-expanded={anomaliesExpanded}
              >
                <i className={`fas fa-chevron-${anomaliesExpanded ? 'down' : 'right'}`} />
              </button>
              <i className="fas fa-robot" />
              <h3 className="dqi-section-title">
                AI Anomaly Detection
                <span className="dqi-anomaly-count">{anomalies.length}</span>
              </h3>
            </div>

            {anomaliesExpanded && (
              <div className="dqi-anomalies-list">
                {anomalies.map((anomaly, idx) => (
                  <div key={anomaly.id} className={`dqi-anomaly dqi-anomaly-${anomaly.severity}`}>
                    <div className="dqi-anomaly-header">
                      <i
                        className={`fas ${
                          anomaly.severity === 'high'
                            ? 'fa-circle-exclamation'
                            : anomaly.severity === 'medium'
                            ? 'fa-exclamation-triangle'
                            : 'fa-info-circle'
                        }`}
                      />
                      <div className="dqi-anomaly-title-group">
                        <h4 className="dqi-anomaly-title">{anomaly.title}</h4>
                        <span className="dqi-anomaly-confidence">
                          Confidence: {Math.round(anomaly.confidence * 100)}%
                        </span>
                      </div>
                    </div>

                    <div className="dqi-anomaly-body">
                      <p className="dqi-anomaly-description">{anomaly.description}</p>

                      {anomaly.sampleValues && (
                        <div className="dqi-anomaly-samples">
                          <span className="dqi-sample-label">Sample values:</span>
                          <code className="dqi-sample-code">
                            {anomaly.sampleValues.map((v, i) => (
                              <span key={i}>
                                "{v}"
                                {i < anomaly.sampleValues.length - 1 ? ', ' : ''}
                              </span>
                            ))}
                          </code>
                        </div>
                      )}

                      {(anomaly.affectedFields || anomaly.affectedFile || anomaly.affectedFiles) && (
                        <div className="dqi-anomaly-affected">
                          <span className="dqi-affected-label">Affected:</span>
                          <span className="dqi-affected-items">
                            {anomaly.affectedField && <code>{anomaly.affectedField}</code>}
                            {anomaly.affectedFields && anomaly.affectedFields.map((f, i) => (
                              <code key={i}>{f}</code>
                            ))}
                            {anomaly.affectedFiles && anomaly.affectedFiles.map((f, i) => (
                              <code key={i}>{f}</code>
                            ))}
                          </span>
                        </div>
                      )}

                      <div className="dqi-anomaly-action">
                        <span className="dqi-action-icon">
                          <i className="fas fa-arrow-right" />
                        </span>
                        <span className="dqi-action-text">
                          <strong>Recommended:</strong> {anomaly.action}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        )}

        {/* Non-Anomaly SODA Insights */}
        {sodaInsights.length > 0 && (
          <section className="dqi-section dqi-section-insights">
            <div className="dqi-section-header">
              <i className="fas fa-lightbulb" />
              <h3 className="dqi-section-title">Quality Insights</h3>
            </div>

            <div className="dqi-insights-list">
              {sodaInsights.map(insight => (
                <div key={insight.id} className={`dqi-insight dqi-insight-${insight.severity || 'info'}`}>
                  <i
                    className={`fas ${
                      insight.severity === 'success'
                        ? 'fa-check-circle'
                        : insight.severity === 'warning'
                        ? 'fa-exclamation-triangle'
                        : insight.severity === 'error'
                        ? 'fa-times-circle'
                        : 'fa-info-circle'
                    }`}
                  />
                  <div className="dqi-insight-body">
                    <strong>{insight.title}</strong>
                    {insight.detail && <span>{insight.detail}</span>}
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
