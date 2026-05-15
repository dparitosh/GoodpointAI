/**
 * MappingIntelligence — Confidence-tiered field mappings with explanations
 * Shows: Strong → Review → Weak mappings with AI confidence reasoning
 */

import React, { useState, useMemo } from 'react';
import { tierMappings, CONFIDENCE_EXPLANATIONS, parsePct, confidenceTier } from './discoveryUtils.js';

export default function MappingIntelligence({ mappings }) {
  const [expandedTiers, setExpandedTiers] = useState({ strong: true, review: true, weak: true });

  const tiers = useMemo(() => tierMappings(mappings), [mappings]);

  const toggleTier = (tier) => {
    setExpandedTiers(prev => ({ ...prev, [tier]: !prev[tier] }));
  };

  const renderMappingItem = (mapping, idx) => {
    const conf = parsePct(mapping.confidence);
    const tier = confidenceTier(conf);

    return (
      <div key={`${mapping.sourceField}-${idx}`} className={`mi-mapping-item mi-mapping-${tier}`}>
        <div className="mi-mapping-source">
          <code className="mi-field-code">{mapping.sourceField}</code>
          {mapping.transformation && (
            <span className="mi-transform-badge" title={`Transformation: ${mapping.transformation}`}>
              <i className="fas fa-magic" /> {mapping.transformation}
            </span>
          )}
        </div>

        <div className="mi-mapping-arrow">
          <i className="fas fa-arrow-right" />
        </div>

        <div className="mi-mapping-target">
          <code className="mi-field-code">{mapping.targetField}</code>
          {mapping.targetRole && (
            <span className="mi-target-role" title={`Semantic role: ${mapping.targetRole}`}>
              {mapping.targetRole}
            </span>
          )}
        </div>

        <div className="mi-mapping-confidence">
          <div className="mi-confidence-bar">
            <div
              className={`mi-confidence-fill mi-confidence-${tier}`}
              style={{ width: `${conf}%` }}
              role="progressbar"
              aria-valuenow={conf}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label={`Confidence: ${conf}%`}
            />
          </div>
          <span className="mi-confidence-pct">{conf}%</span>
        </div>

        <div className="mi-confidence-tooltip">
          <span>{CONFIDENCE_EXPLANATIONS[tier]}</span>
        </div>
      </div>
    );
  };

  return (
    <div className="mi-root">
      <div className="mi-container">
        {/* Header */}
        <div className="mi-header">
          <h3 className="mi-title">AI Field Mapping Intelligence</h3>
          <p className="mi-description">
            Detection method: Semantic analysis + pattern matching. AI compares field names, data types, and business
            semantics to find best matches.
          </p>
        </div>

        {/* Summary Stats */}
        <div className="mi-summary">
          <div className="mi-summary-item mi-summary-strong">
            <span className="mi-summary-count">{tiers.strong.length}</span>
            <span className="mi-summary-label">Strong (80%+)</span>
            <span className="mi-summary-sub">Name + type + role align</span>
          </div>
          <div className="mi-summary-item mi-summary-review">
            <span className="mi-summary-count">{tiers.review.length}</span>
            <span className="mi-summary-label">Review (60-80%)</span>
            <span className="mi-summary-sub">Check type compatibility</span>
          </div>
          <div className="mi-summary-item mi-summary-weak">
            <span className="mi-summary-count">{tiers.weak.length}</span>
            <span className="mi-summary-label">Weak (&lt;60%)</span>
            <span className="mi-summary-sub">Manual selection required</span>
          </div>
        </div>

        {/* Mapping Tiers */}
        <div className="mi-tiers">
          {/* STRONG */}
          {tiers.strong.length > 0 && (
            <div className="mi-tier mi-tier-strong">
              <button
                className="mi-tier-header"
                onClick={() => toggleTier('strong')}
                aria-expanded={expandedTiers.strong}
              >
                <i className={`fas fa-chevron-${expandedTiers.strong ? 'down' : 'right'}`} />
                <i className="fas fa-check-circle" />
                <span className="mi-tier-label">STRONG MATCHES</span>
                <span className="mi-tier-count">{tiers.strong.length}</span>
              </button>

              {expandedTiers.strong && (
                <div className="mi-tier-content">
                  <p className="mi-tier-guidance">
                    ✅ These mappings are high-confidence. Field names, types, and semantic roles align well. Ready to
                    accept.
                  </p>
                  {tiers.strong.map((mapping, idx) => renderMappingItem(mapping, idx))}
                </div>
              )}
            </div>
          )}

          {/* REVIEW */}
          {tiers.review.length > 0 && (
            <div className="mi-tier mi-tier-review">
              <button
                className="mi-tier-header"
                onClick={() => toggleTier('review')}
                aria-expanded={expandedTiers.review}
              >
                <i className={`fas fa-chevron-${expandedTiers.review ? 'down' : 'right'}`} />
                <i className="fas fa-exclamation-triangle" />
                <span className="mi-tier-label">REVIEW MATCHES</span>
                <span className="mi-tier-count">{tiers.review.length}</span>
              </button>

              {expandedTiers.review && (
                <div className="mi-tier-content">
                  <p className="mi-tier-guidance">
                    ⚠️ Field names match but verify data type compatibility before proceeding. AI suggests these targets
                    but recommends review.
                  </p>
                  {tiers.review.map((mapping, idx) => renderMappingItem(mapping, idx))}
                </div>
              )}
            </div>
          )}

          {/* WEAK */}
          {tiers.weak.length > 0 && (
            <div className="mi-tier mi-tier-weak">
              <button
                className="mi-tier-header"
                onClick={() => toggleTier('weak')}
                aria-expanded={expandedTiers.weak}
              >
                <i className={`fas fa-chevron-${expandedTiers.weak ? 'down' : 'right'}`} />
                <i className="fas fa-times-circle" />
                <span className="mi-tier-label">WEAK MATCHES</span>
                <span className="mi-tier-count">{tiers.weak.length}</span>
              </button>

              {expandedTiers.weak && (
                <div className="mi-tier-content">
                  <p className="mi-tier-guidance">
                    🔴 AI found partial similarity but confidence is low. You will need to manually select targets for
                    these fields in Step 3 (Mapping).
                  </p>
                  {tiers.weak.map((mapping, idx) => renderMappingItem(mapping, idx))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Recommendation */}
        <div className="mi-recommendation">
          <div className="mi-rec-icon">
            <i className="fas fa-lightbulb" />
          </div>
          <div className="mi-rec-content">
            <strong>AI Recommendation:</strong>
            <p>
              Proceed to Step 3 with <strong>{tiers.strong.length}</strong> strong-confidence mappings. Review the{' '}
              <strong>{tiers.review.length}</strong> review matches for type compatibility. Be prepared to manually select
              targets for <strong>{tiers.weak.length}</strong> weak matches.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
