/**
 * RecommendedActions — Prioritized next-steps guidance
 * Shows: AI-generated action list with priority, category, and CTA buttons
 */

import React, { useState, useMemo } from 'react';
import { generateRecommendedActions } from './discoveryUtils.js';

export default function RecommendedActions({
  readinessScore,
  fieldRisks,
  anomalies,
  mappingTiers,
  unreadableFiles,
  onAction,
}) {
  const [completedActions, setCompletedActions] = useState(new Set());
  const [expandedCategories, setExpandedCategories] = useState({ critical: true, high: true, medium: false });

  const actions = useMemo(
    () =>
      generateRecommendedActions(readinessScore, fieldRisks, anomalies, mappingTiers, unreadableFiles),
    [readinessScore, fieldRisks, anomalies, mappingTiers, unreadableFiles]
  );

  // Group actions by category
  const grouped = useMemo(() => {
    const result = { critical: [], high: [], medium: [], low: [] };
    actions.forEach(a => {
      result[a.priority]?.push(a);
    });
    return result;
  }, [actions]);

  const toggleCategory = (cat) => {
    setExpandedCategories(prev => ({ ...prev, [cat]: !prev[cat] }));
  };

  const markComplete = (actionId) => {
    setCompletedActions(prev => new Set([...prev, actionId]));
  };

  const handleAction = (action) => {
    onAction?.(action);
    markComplete(action.id);
  };

  const renderActionItem = (action) => {
    const isCompleted = completedActions.has(action.id);

    return (
      <div key={action.id} className={`ra-action-item ra-action-${action.priority} ${isCompleted ? 'ra-action--done' : ''}`}>
        <div className="ra-action-header">
          <div className="ra-action-info">
            <i className={`fas ${isCompleted ? 'fa-check-circle' : 'fa-circle'} ra-action-icon`} />
            <h4 className="ra-action-title">{action.title}</h4>
            {action.impact && <span className="ra-action-impact">{action.impact}</span>}
          </div>
          {action.cta && !isCompleted && (
            <button className="ra-action-cta" onClick={() => handleAction(action)}>
              {action.cta}
            </button>
          )}
          {isCompleted && <span className="ra-action-done">✓ Done</span>}
        </div>

        <p className="ra-action-description">{action.description}</p>

        {action.details && (
          <ul className="ra-action-details">
            {action.details.map((detail, idx) => (
              <li key={idx}>{detail}</li>
            ))}
          </ul>
        )}

        {action.affectedArea && (
          <div className="ra-action-affected">
            <strong>Affected:</strong> <code>{action.affectedArea}</code>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="ra-root">
      <div className="ra-container">
        {/* Header */}
        <div className="ra-header">
          <h3 className="ra-title">
            <i className="fas fa-compass" /> Recommended Next Steps
          </h3>
          <p className="ra-subtitle">
            {actions.length} actions recommended based on your discovery results and readiness score.
          </p>
        </div>

        {/* Progress Bar */}
        <div className="ra-progress">
          <div className="ra-progress-label">
            Progress: <strong>{completedActions.size}</strong> of <strong>{actions.length}</strong> actions completed
          </div>
          <div className="ra-progress-bar">
            <div
              className="ra-progress-fill"
              style={{ width: `${((completedActions.size || 0) / actions.length) * 100}%` }}
            />
          </div>
        </div>

        {/* Action Categories */}
        <div className="ra-categories">
          {/* CRITICAL */}
          {grouped.critical.length > 0 && (
            <div className="ra-category ra-category-critical">
              <button
                className="ra-category-header"
                onClick={() => toggleCategory('critical')}
                aria-expanded={expandedCategories.critical}
              >
                <i className={`fas fa-chevron-${expandedCategories.critical ? 'down' : 'right'}`} />
                <i className="fas fa-circle-stop" />
                <span className="ra-category-label">CRITICAL BLOCKERS</span>
                <span className="ra-category-count">{grouped.critical.length}</span>
              </button>

              {expandedCategories.critical && (
                <div className="ra-category-content">
                  {grouped.critical.map(action => renderActionItem(action))}
                </div>
              )}
            </div>
          )}

          {/* HIGH PRIORITY */}
          {grouped.high.length > 0 && (
            <div className="ra-category ra-category-high">
              <button
                className="ra-category-header"
                onClick={() => toggleCategory('high')}
                aria-expanded={expandedCategories.high}
              >
                <i className={`fas fa-chevron-${expandedCategories.high ? 'down' : 'right'}`} />
                <i className="fas fa-exclamation-circle" />
                <span className="ra-category-label">HIGH PRIORITY</span>
                <span className="ra-category-count">{grouped.high.length}</span>
              </button>

              {expandedCategories.high && (
                <div className="ra-category-content">
                  {grouped.high.map(action => renderActionItem(action))}
                </div>
              )}
            </div>
          )}

          {/* MEDIUM PRIORITY */}
          {grouped.medium.length > 0 && (
            <div className="ra-category ra-category-medium">
              <button
                className="ra-category-header"
                onClick={() => toggleCategory('medium')}
                aria-expanded={expandedCategories.medium}
              >
                <i className={`fas fa-chevron-${expandedCategories.medium ? 'down' : 'right'}`} />
                <i className="fas fa-exclamation-triangle" />
                <span className="ra-category-label">MEDIUM PRIORITY</span>
                <span className="ra-category-count">{grouped.medium.length}</span>
              </button>

              {expandedCategories.medium && (
                <div className="ra-category-content">
                  {grouped.medium.map(action => renderActionItem(action))}
                </div>
              )}
            </div>
          )}

          {/* LOW PRIORITY */}
          {grouped.low.length > 0 && (
            <div className="ra-category ra-category-low">
              <button
                className="ra-category-header"
                onClick={() => toggleCategory('low')}
                aria-expanded={expandedCategories.low}
              >
                <i className={`fas fa-chevron-${expandedCategories.low ? 'down' : 'right'}`} />
                <i className="fas fa-info-circle" />
                <span className="ra-category-label">LOW PRIORITY</span>
                <span className="ra-category-count">{grouped.low.length}</span>
              </button>

              {expandedCategories.low && (
                <div className="ra-category-content">
                  {grouped.low.map(action => renderActionItem(action))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Summary */}
        <div className="ra-summary">
          <div className="ra-summary-box">
            <i className="fas fa-lightbulb" />
            <div className="ra-summary-content">
              <strong>Ready to Proceed?</strong>
              <p>
                {grouped.critical.length === 0
                  ? 'No critical blockers detected. You can proceed to Step 3 (Mapping).'
                  : `Address ${grouped.critical.length} critical issue(s) first, then proceed to Step 3.`}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
