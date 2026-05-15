/**
 * SampleDataPreview — Contextualized sample data records
 * Shows: First N records with quality context (nulls, pass/fail, issues)
 */

import React, { useState, useMemo } from 'react';

export default function SampleDataPreview({ sample, dqReport, selectedFile, onFileSelect }) {
  const [visibleCount, setVisibleCount] = useState(5);
  const [selectedRecord, setSelectedRecord] = useState(null);

  // Filter records by selected file if provided
  const filteredRecords = useMemo(() => {
    if (!selectedFile || !sample?.records) return sample?.records || [];
    return sample.records.filter(r => r._sourceFile === selectedFile);
  }, [sample, selectedFile]);

  const records = filteredRecords?.slice(0, visibleCount) || [];

  // Map field-level data quality info
  const fieldQualityMap = useMemo(() => {
    const map = {};
    if (dqReport) {
      dqReport.forEach(field => {
        if (!map[field.field]) {
          map[field.field] = {
            nullCount: field.nullCount || 0,
            completeness: field.completeness,
            hasIssues: (field.nullCount || 0) > 0 || (field.completeness && field.completeness < 70),
          };
        }
      });
    }
    return map;
  }, [dqReport]);

  const renderCellValue = (value, fieldName) => {
    const qualityInfo = fieldQualityMap[fieldName];

    // Null/empty check
    if (value === null || value === undefined || value === '') {
      return (
        <span className="sdp-cell-null" title="Null/empty value">
          <i className="fas fa-minus" /> NULL
        </span>
      );
    }

    // Long values
    const strVal = String(value);
    const displayVal = strVal.length > 30 ? `${strVal.slice(0, 30)}…` : strVal;

    return (
      <span
        className={`sdp-cell-value ${qualityInfo?.hasIssues ? 'sdp-cell-value--warn' : ''}`}
        title={strVal}
      >
        {displayVal}
      </span>
    );
  };

  if (!records || records.length === 0) {
    return (
      <div className="sdp-root">
        <div className="sdp-container">
          <div className="sdp-empty">
            <i className="fas fa-inbox" />
            <p>No sample data available</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="sdp-root">
      <div className="sdp-container">
        {/* Header */}
        <div className="sdp-header">
          <h3 className="sdp-title">Sample Data Preview</h3>
          <div className="sdp-header-actions">
            <span className="sdp-record-count">
              Showing {records.length} of {filteredRecords.length} record{filteredRecords.length !== 1 ? 's' : ''}
            </span>
            {selectedFile && (
              <button className="sdp-clear-filter" onClick={() => onFileSelect?.(null)} title="Clear file filter">
                Clear Filter
              </button>
            )}
          </div>
        </div>

        {/* Records Table */}
        <div className="sdp-table-wrapper">
          <table className="sdp-table">
            <thead>
              <tr>
                <th className="sdp-th-record">#</th>
                {records[0] && (
                  <>
                    {Object.keys(records[0])
                      .filter(k => !k.startsWith('_'))
                      .map(field => (
                        <th
                          key={field}
                          className={`sdp-th ${fieldQualityMap[field]?.hasIssues ? 'sdp-th--warn' : ''}`}
                          title={fieldQualityMap[field]?.hasIssues ? 'This field has data quality issues' : ''}
                        >
                          <code>{field}</code>
                          {fieldQualityMap[field]?.hasIssues && (
                            <i className="fas fa-exclamation-circle sdp-th-warning-icon" />
                          )}
                        </th>
                      ))}
                  </>
                )}
              </tr>
            </thead>
            <tbody>
              {records.map((record, idx) => (
                <tr
                  key={idx}
                  className={`sdp-tr ${selectedRecord === idx ? 'sdp-tr--selected' : ''}`}
                  onClick={() => setSelectedRecord(selectedRecord === idx ? null : idx)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={e => e.key === 'Enter' && setSelectedRecord(selectedRecord === idx ? null : idx)}
                >
                  <td className="sdp-td-record">{idx + 1}</td>
                  {Object.keys(record)
                    .filter(k => !k.startsWith('_'))
                    .map(field => (
                      <td
                        key={field}
                        className={`sdp-td ${fieldQualityMap[field]?.hasIssues ? 'sdp-td--warn' : ''}`}
                      >
                        {renderCellValue(record[field], field)}
                      </td>
                    ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Load More */}
        {visibleCount < filteredRecords.length && (
          <div className="sdp-load-more">
            <button className="sdp-load-more-btn" onClick={() => setVisibleCount(v => v + 5)}>
              Load More ({filteredRecords.length - visibleCount} remaining)
            </button>
          </div>
        )}

        {/* Legend & Info */}
        <div className="sdp-legend">
          <div className="sdp-legend-item">
            <i className="fas fa-minus" /> Null or empty value (missing data)
          </div>
          <div className="sdp-legend-item sdp-legend-warn">
            <i className="fas fa-exclamation-circle" /> Field with quality issues (nulls or low completeness)
          </div>
          <div className="sdp-legend-item">
            <i className="fas fa-info-circle" /> Click record row to view full details
          </div>
        </div>
      </div>
    </div>
  );
}
