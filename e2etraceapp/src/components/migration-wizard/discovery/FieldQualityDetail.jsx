/**
 * FieldQualityDetail — Risk-sorted field breakdown with detailed metrics
 * Shows: High-risk → Medium → Low-risk fields with quality metrics and actions
 */

import React, { useState, useMemo } from 'react';
import { groupFieldsByRisk, getFieldRiskTier } from './discoveryUtils.js';

export default function FieldQualityDetail({ dqReport, selectedFile, onFileSelect }) {
  const [expandedRiskGroups, setExpandedRiskGroups] = useState({ high: true, medium: false, low: false });
  const [selectedField, setSelectedField] = useState(null);

  // Filter by selected file if provided
  const filteredReport = useMemo(() => {
    if (!selectedFile) return dqReport;
    return dqReport.filter(f => f.file === selectedFile);
  }, [dqReport, selectedFile]);

  // Group by risk
  const fieldRisks = useMemo(() => groupFieldsByRisk(filteredReport), [filteredReport]);

  const toggleRiskGroup = (risk) => {
    setExpandedRiskGroups(prev => ({ ...prev, [risk]: !prev[risk] }));
  };

  const renderFieldRow = (field, idx) => {
    const isSelected = selectedField === `${field.file}-${field.field}`;
    const compColor = !field.completeness
      ? 'dq-unknown'
      : field.completeness >= 90
      ? 'dq-high'
      : field.completeness >= 70
      ? 'dq-medium'
      : 'dq-low';

    return (
      <div
        key={`${field.file}-${field.field}`}
        className={`fqd-field-row ${isSelected ? 'fqd-field-row--selected' : ''}`}
        onClick={() => setSelectedField(isSelected ? null : `${field.file}-${field.field}`)}
        role="button"
        tabIndex={0}
        onKeyDown={e => e.key === 'Enter' && setSelectedField(isSelected ? null : `${field.file}-${field.field}`)}
      >
        <div className="fqd-field-name-col">
          <code className="fqd-field-code">{field.field}</code>
          <span className="fqd-field-type" title={`Data type: ${field.type}`}>
            {field.type}
          </span>
        </div>

        <div className="fqd-field-file-col">{field.file.length > 20 ? `${field.file.slice(0, 20)}…` : field.file}</div>

        <div className="fqd-field-metrics">
          {/* Records */}
          <span className="fqd-metric" title="Total records in file">
            <i className="fas fa-bars" />
            {field.totalRecords}
          </span>

          {/* Nulls */}
          <span className={`fqd-metric ${field.nullCount > 0 ? 'fqd-metric-warn' : ''}`} title="Null/empty values">
            <i className="fas fa-minus-circle" />
            {field.nullCount ?? '—'}
          </span>

          {/* Unique */}
          <span className="fqd-metric" title="Unique values">
            <i className="fas fa-random" />
            {field.uniqueCount ?? '—'}
          </span>

          {/* Completeness */}
          <span className={`fqd-metric fqd-metric-comp ${compColor}`} title="Completeness %">
            <i className="fas fa-fill" />
            {field.completeness != null ? `${field.completeness}%` : '—'}
          </span>

          {/* Duplicates */}
          <span className={`fqd-metric ${field.duplicateRows > 0 ? 'fqd-metric-warn' : ''}`} title="Duplicate rows">
            <i className="fas fa-copy" />
            {field.duplicateRows > 0 ? field.duplicateRows : '0'}
          </span>
        </div>

        <div className="fqd-field-status">
          {field.nullCount > 0 && <span className="fqd-badge-null">Nulls</span>}
          {field.completeness != null && field.completeness < 70 && <span className="fqd-badge-low">Low Comp</span>}
          {field.duplicateRows > 0 && <span className="fqd-badge-dup">Dups</span>}
          {field.nullCount === 0 && (field.completeness == null || field.completeness >= 90) && (
            <span className="fqd-badge-ok">✓ OK</span>
          )}
        </div>

        <i className={`fas fa-chevron-${isSelected ? 'up' : 'down'} fqd-field-toggle`} />
      </div>
    );
  };

  return (
    <div className="fqd-root">
      <div className="fqd-container">
        {/* Header */}
        <div className="fqd-header">
          <h3 className="fqd-title">Field-Level Quality Breakdown</h3>
          <div className="fqd-header-actions">
            <span className="fqd-field-count">
              {filteredReport.length} field
              {filteredReport.length !== 1 ? 's' : ''}
              {selectedFile && ` in ${selectedFile}`}
            </span>
            {selectedFile && (
              <button className="fqd-clear-filter" onClick={() => onFileSelect?.(null)} title="Clear file filter">
                Clear Filter
              </button>
            )}
          </div>
        </div>

        {/* Risk Groups */}
        <div className="fqd-risk-groups">
          {/* HIGH RISK */}
          {fieldRisks.high.length > 0 && (
            <div className="fqd-risk-group fqd-risk-group-high">
              <button
                className="fqd-risk-group-header"
                onClick={() => toggleRiskGroup('high')}
                aria-expanded={expandedRiskGroups.high}
              >
                <i className={`fas fa-chevron-${expandedRiskGroups.high ? 'down' : 'right'}`} />
                <i className="fas fa-circle-exclamation" />
                <span className="fqd-risk-label">
                  HIGH RISK
                  <span className="fqd-risk-count">{fieldRisks.high.length}</span>
                </span>
                <span className="fqd-risk-description">Fields with data quality issues</span>
              </button>

              {expandedRiskGroups.high && (
                <div className="fqd-risk-group-content">
                  {fieldRisks.high.map((field, idx) => renderFieldRow(field, idx))}
                </div>
              )}
            </div>
          )}

          {/* MEDIUM RISK */}
          {fieldRisks.medium.length > 0 && (
            <div className="fqd-risk-group fqd-risk-group-medium">
              <button
                className="fqd-risk-group-header"
                onClick={() => toggleRiskGroup('medium')}
                aria-expanded={expandedRiskGroups.medium}
              >
                <i className={`fas fa-chevron-${expandedRiskGroups.medium ? 'down' : 'right'}`} />
                <i className="fas fa-exclamation-triangle" />
                <span className="fqd-risk-label">
                  MEDIUM RISK
                  <span className="fqd-risk-count">{fieldRisks.medium.length}</span>
                </span>
                <span className="fqd-risk-description">Fields with minor quality issues</span>
              </button>

              {expandedRiskGroups.medium && (
                <div className="fqd-risk-group-content">
                  {fieldRisks.medium.map((field, idx) => renderFieldRow(field, idx))}
                </div>
              )}
            </div>
          )}

          {/* LOW RISK */}
          {fieldRisks.low.length > 0 && (
            <div className="fqd-risk-group fqd-risk-group-low">
              <button
                className="fqd-risk-group-header"
                onClick={() => toggleRiskGroup('low')}
                aria-expanded={expandedRiskGroups.low}
              >
                <i className={`fas fa-chevron-${expandedRiskGroups.low ? 'down' : 'right'}`} />
                <i className="fas fa-check-circle" />
                <span className="fqd-risk-label">
                  LOW RISK
                  <span className="fqd-risk-count">{fieldRisks.low.length}</span>
                </span>
                <span className="fqd-risk-description">Fields passing all quality gates</span>
              </button>

              {expandedRiskGroups.low && (
                <div className="fqd-risk-group-content">
                  {fieldRisks.low.length > 10 ? (
                    <>
                      {fieldRisks.low.slice(0, 10).map((field, idx) => renderFieldRow(field, idx))}
                      <div className="fqd-field-row fqd-field-row--collapsed">
                        <span className="fqd-collapsed-message">
                          Showing 10 of {fieldRisks.low.length}. Low-risk fields are OK to proceed.
                        </span>
                      </div>
                    </>
                  ) : (
                    fieldRisks.low.map((field, idx) => renderFieldRow(field, idx))
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Legend */}
        <div className="fqd-legend">
          <div className="fqd-legend-title">Legend:</div>
          <div className="fqd-legend-items">
            <span className="fqd-legend-item">
              <i className="fas fa-bars" /> Total records in file
            </span>
            <span className="fqd-legend-item">
              <i className="fas fa-minus-circle" /> Null values (missing data)
            </span>
            <span className="fqd-legend-item">
              <i className="fas fa-random" /> Unique values (distinct entries)
            </span>
            <span className="fqd-legend-item">
              <i className="fas fa-fill" /> Completeness (% of non-null values)
            </span>
            <span className="fqd-legend-item">
              <i className="fas fa-copy" /> Duplicate rows in file
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
