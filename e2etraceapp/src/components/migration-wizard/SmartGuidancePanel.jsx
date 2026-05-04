import React, { useState, useEffect, useCallback } from 'react';
import { API_CONFIG } from '../../config/api-config.js';
import './SmartGuidancePanel.css';

/**
 * SmartGuidancePanel — "Assistant Mode"
 *
 * Shown when the user is unsure what to do. Calls /api/agentic/smart-guidance
 * with dataset context and displays a business-friendly first-step recommendation:
 *   - What to do first  (Discovery / Profiling / Quality)
 *   - Why it matters
 *   - Expected outcome
 *   - Actionable next-step list
 *
 * Props:
 *   sourceSystem   { id, name, type } | null   — currently selected source
 *   fileCount      number | null
 *   fileTypes      string[] | null              — e.g. ['CSV','XML']
 *   previousRuns   boolean                      — any profiling/discovery done before?
 *   userRole       'business' | 'technical'
 *   onAction       fn(action: 'discovery'|'profiling'|'quality') => void
 *   onDismiss      fn() => void
 */
const RECOMMENDATION_META = {
  discovery: {
    icon: 'fa-compass',
    label: 'Discovery',
    actionLabel: 'Start with Discovery',
    actionIcon: 'fa-search',
  },
  profiling: {
    icon: 'fa-microscope',
    label: 'Profiling',
    actionLabel: 'Start Semantic Analysis',
    actionIcon: 'fa-dna',
  },
  quality: {
    icon: 'fa-shield-alt',
    label: 'Quality Check',
    actionLabel: 'Start Quality Scan',
    actionIcon: 'fa-check-circle',
  },
};

const SmartGuidancePanel = ({
  sourceSystem = null,
  fileCount = null,
  fileTypes = null,
  previousRuns = false,
  userRole = 'business',
  onAction,
  onDismiss,
}) => {
  const [loading, setLoading] = useState(true);
  const [guidance, setGuidance] = useState(null);
  const [error, setError] = useState(null);

  const fetchGuidance = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const baseUrl = API_CONFIG?.API_BASE_URL || '';
      const endpoint = `${baseUrl}${API_CONFIG.ENDPOINTS.AGENTIC_SMART_GUIDANCE}`;

      const body = {
        source_name: sourceSystem?.name || null,
        source_id:   sourceSystem?.id   || null,
        file_count:  typeof fileCount === 'number' ? fileCount : null,
        file_types:  Array.isArray(fileTypes) ? fileTypes : null,
        previous_runs: Boolean(previousRuns),
        user_role:   userRole,
      };

      const resp = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      }

      const data = await resp.json();
      setGuidance(data);
    } catch (err) {
      // Show a friendly static fallback rather than an error state.
      setGuidance(
        previousRuns
          ? {
              recommendation: 'profiling',
              headline: 'Run Data Profiling',
              reason:
                'Discovery is done. Profiling goes deeper — it reads each column and checks for patterns, blanks, and unexpected values.',
              expected_outcome:
                'A column-by-column quality report and automatic classification of your data.',
              next_steps: [
                "Click 'Run Semantic Analysis'",
                'Review the column quality report',
                'Proceed to Field Mapping',
              ],
              complexity: 'low',
              estimated_time: '3-8 minutes',
              tips: ['Profiling uses your existing discovery results — no extra setup needed'],
              llm_powered: false,
            }
          : {
              recommendation: 'discovery',
              headline: 'Start with Discovery',
              reason:
                "Your data hasn't been scanned yet. Discovery gives you a quick, safe look at what files you have and flags any obvious issues.",
              expected_outcome:
                'A clear summary of your files, record counts, and an initial list of data issues.',
              next_steps: [
                "Click 'Run Discovery' to scan your data",
                'Review the insights that appear',
                'Accept discovery and move to Profiling',
              ],
              complexity: 'low',
              estimated_time: '2-5 minutes',
              tips: [
                "Discovery is read-only — it won't change your data",
                'You can re-run it any time to refresh the results',
              ],
              llm_powered: false,
            }
      );
    } finally {
      setLoading(false);
    }
  }, [sourceSystem, fileCount, fileTypes, previousRuns, userRole]);

  useEffect(() => {
    fetchGuidance();
  }, [fetchGuidance]);

  const handleAction = () => {
    if (guidance?.recommendation && onAction) {
      onAction(guidance.recommendation);
    }
  };

  const meta = guidance ? (RECOMMENDATION_META[guidance.recommendation] || RECOMMENDATION_META.discovery) : null;

  return (
    <div className="smart-guidance-panel" role="region" aria-label="Smart Guidance">
      {/* ── Header ── */}
      <div className="sgp-header">
        <div className="sgp-header-left">
          <div className="sgp-icon">
            <i className="fas fa-lightbulb" />
          </div>
          <span className="sgp-title">Smart Guidance</span>
        </div>
        {onDismiss && (
          <button
            className="sgp-dismiss"
            onClick={onDismiss}
            title="Dismiss guidance"
            aria-label="Dismiss guidance"
          >
            <i className="fas fa-times" />
          </button>
        )}
      </div>

      {/* ── Loading ── */}
      {loading && (
        <div className="sgp-loading" aria-busy="true" aria-label="Loading guidance">
          <div className="sgp-skeleton" style={{ width: '55%' }} />
          <div className="sgp-skeleton" style={{ width: '85%' }} />
          <div className="sgp-skeleton" style={{ width: '70%' }} />
          <div className="sgp-skeleton" style={{ width: '45%', marginTop: 4 }} />
        </div>
      )}

      {/* ── Recommendation ── */}
      {!loading && guidance && (
        <div className="sgp-recommendation">
          {/* Headline + badge */}
          <div>
            <p className="sgp-headline">{guidance.headline}</p>
            <span className={`sgp-badge ${guidance.recommendation}`}>
              <i className={`fas ${meta.icon}`} />
              {meta.label}
            </span>
          </div>

          {/* Info grid */}
          <div className="sgp-info-grid">
            <div className="sgp-info-card">
              <div className="sgp-info-label">
                <i className="fas fa-question-circle" /> Why this first?
              </div>
              <p className="sgp-info-text">{guidance.reason}</p>
            </div>

            <div className="sgp-info-card">
              <div className="sgp-info-label">
                <i className="fas fa-flag-checkered" /> What you'll get
              </div>
              <p className="sgp-info-text">{guidance.expected_outcome}</p>
            </div>

            {guidance.next_steps?.length > 0 && (
              <div className="sgp-info-card full">
                <div className="sgp-info-label">
                  <i className="fas fa-list-ol" /> How it works
                </div>
                <ol className="sgp-next-steps">
                  {guidance.next_steps.map((step, i) => (
                    <li key={i}>
                      <span className="sgp-step-num">{i + 1}</span>
                      {step}
                    </li>
                  ))}
                </ol>
              </div>
            )}
          </div>

          {/* Meta row */}
          <div className="sgp-meta">
            {guidance.estimated_time && (
              <span className="sgp-meta-item">
                <i className="fas fa-clock" />
                {guidance.estimated_time}
              </span>
            )}
            {guidance.complexity && (
              <span className="sgp-meta-item">
                <span className={`sgp-complexity-dot ${guidance.complexity}`} />
                {guidance.complexity.charAt(0).toUpperCase() + guidance.complexity.slice(1)} effort
              </span>
            )}
          </div>

          {/* Tips */}
          {guidance.tips?.length > 0 && (
            <div className="sgp-tips">
              {guidance.tips.map((tip, i) => (
                <span key={i} className="sgp-tip">
                  <i className="fas fa-lightbulb" />
                  {tip}
                </span>
              ))}
            </div>
          )}

          {/* Actions */}
          <div className="sgp-actions">
            <button className="sgp-btn-primary" onClick={handleAction}>
              <i className={`fas ${meta.actionIcon}`} />
              {meta.actionLabel}
            </button>
            {onDismiss && (
              <button className="sgp-btn-secondary" onClick={onDismiss}>
                I'll choose manually
              </button>
            )}
            {guidance.llm_powered && (
              <span className="sgp-powered-badge">
                <i className="fas fa-robot" />
                AI-powered
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default SmartGuidancePanel;
