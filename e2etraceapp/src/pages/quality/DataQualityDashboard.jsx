import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import './DataQualityDashboard.css';

/**
 * SODA-Style Data Quality Dashboard
 * Complete UI for data quality monitoring, scanning, and rule management
 */
export const DataQualityDashboard = () => {
  const [activeTab, setActiveTab] = useState('dashboard'); // dashboard, rules
  const [dashboardData, setDashboardData] = useState(null);
  const [qualityRules, setQualityRules] = useState([]);
  const [scans, setScans] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [newScanForm, setNewScanForm] = useState({
    table_name: '',
    data_source: 'neo4j',
    rules: []
  });

  const navigate = useNavigate();

  const dashboardFetchInFlightRef = useRef(false);
  const dashboardAbortRef = useRef(null);

  // Fetch dashboard data
  const fetchDashboard = useCallback(async ({ silent = false } = {}) => {
    if (dashboardFetchInFlightRef.current) {
      return;
    }
    dashboardFetchInFlightRef.current = true;

    if (dashboardAbortRef.current) {
      try {
        dashboardAbortRef.current.abort();
      } catch {
        // ignore
      }
    }
    const controller = new AbortController();
    dashboardAbortRef.current = controller;

    try {
      if (!silent) setLoading(true);
      const response = await fetch('/api/analytics/quality/dashboard', { signal: controller.signal });
      if (!response.ok) throw new Error('Failed to fetch dashboard data');
      const data = await response.json();
      setDashboardData(data);
      setError(null);
    } catch (err) {
      if (err?.name === 'AbortError') {
        return;
      }
      setError(err.message);
      console.error('Dashboard fetch error:', err);
    } finally {
      dashboardFetchInFlightRef.current = false;
      if (!silent) setLoading(false);
    }
  }, []);

  // Fetch quality rules
  const fetchRules = async () => {
    try {
      const response = await fetch('/api/analytics/quality/rules?enabled_only=false');
      if (!response.ok) throw new Error('Failed to fetch rules');
      const data = await response.json();
      setQualityRules(data);
    } catch (err) {
      console.error('Rules fetch error:', err);
    }
  };

  // Start a new quality scan
  const startQualityScan = async () => {
    if (!newScanForm.table_name) {
      alert('Please enter a table name');
      return;
    }

    try {
      setLoading(true);
      const response = await fetch(`/api/analytics/quality/scan/${newScanForm.table_name}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newScanForm)
      });
      
      if (!response.ok) throw new Error('Failed to start scan');
      const result = await response.json();
      
      alert(`Scan started: ${result.scan_id}`);
      setIsModalOpen(false);
      setNewScanForm({ table_name: '', data_source: 'neo4j', rules: [] });
      
      // Refresh data after a delay to show results
      setTimeout(() => {
        fetchDashboard();
      }, 3000);
      
    } catch (err) {
      alert('Error starting scan: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  // Toggle rule enabled/disabled
  const toggleRule = async (ruleId) => {
    try {
      const response = await fetch(`/api/analytics/quality/rules/${ruleId}/toggle`, {
        method: 'PUT'
      });
      if (!response.ok) throw new Error('Failed to toggle rule');
      fetchRules();
    } catch (err) {
      alert('Error toggling rule: ' + err.message);
    }
  };

  // Initial data load
  useEffect(() => {
    fetchDashboard();
    fetchRules();
    return () => {
      if (dashboardAbortRef.current) {
        try {
          dashboardAbortRef.current.abort();
        } catch {
          // ignore
        }
      }
    };
  }, [fetchDashboard]);

  // Auto-refresh dashboard
  useEffect(() => {
    if (activeTab === 'dashboard') {
      const interval = setInterval(() => fetchDashboard({ silent: true }), 60000); // 60 seconds
      return () => clearInterval(interval);
    }
  }, [activeTab, fetchDashboard]);

  // Get quality score color
  const getScoreColor = (score) => {
    if (score >= 0.9) return '#28a745';
    if (score >= 0.7) return '#ffc107';
    return '#dc3545';
  };

  // Get severity badge class
  const getSeverityClass = (severity) => {
    const classes = {
      critical: 'severity-critical',
      high: 'severity-high',
      medium: 'severity-medium',
      low: 'severity-low'
    };
    return classes[severity] || 'severity-default';
  };

  if (loading && !dashboardData) {
    return (
      <div className="quality-dashboard">
        <div className="quality-loading">
          <div className="loading-spinner"></div>
          <p>Loading data quality dashboard...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="quality-dashboard">
      {/* Header */}
      <div className="quality-header">
        <div className="quality-header-content">
          <h1>Data Quality Management</h1>
          <p className="quality-subtitle">SODA-Style Quality Monitoring & Validation</p>
        </div>
        <button 
          className="btn-primary btn-scan"
          onClick={() => setIsModalOpen(true)}
        >
          <i className="fas fa-play" aria-hidden="true" /> Run Quality Scan
        </button>
      </div>

      {/* Tabs */}
      <div className="quality-tabs">
        <button 
          className={`quality-tab ${activeTab === 'dashboard' ? 'active' : ''}`}
          onClick={() => setActiveTab('dashboard')}
        >
          <i className="fas fa-tachometer-alt" aria-hidden="true" /> Dashboard
        </button>
        <button 
          className={`quality-tab ${activeTab === 'rules' ? 'active' : ''}`}
          onClick={() => setActiveTab('rules')}
        >
          <i className="fas fa-list-check" aria-hidden="true" /> Rules
        </button>
      </div>

      {error && (
        <div className="quality-error">
          ! {error}
        </div>
      )}

      {/* Dashboard Tab */}
      {activeTab === 'dashboard' && dashboardData && (
        <div className="quality-content">
          {/* Summary Cards */}
          <div className="quality-summary-cards">
            <div className="quality-card summary-card">
              <div className="card-icon"><i className="fas fa-table" aria-hidden="true" /></div>
              <div className="card-content">
                <h3>{dashboardData.summary.total_tables_scanned}</h3>
                <p>Tables Scanned</p>
              </div>
            </div>

            <div className="quality-card summary-card">
              <div className="card-icon" style={{ color: getScoreColor(dashboardData.summary.average_quality_score / 100) }}>
                <i
                  className={`fas ${dashboardData.summary.average_quality_score >= 90 ? 'fa-check-circle' : 'fa-exclamation-triangle'}`}
                  aria-hidden="true"
                />
              </div>
              <div className="card-content">
                <h3 style={{ color: getScoreColor(dashboardData.summary.average_quality_score / 100) }}>
                  {dashboardData.summary.average_quality_score}%
                </h3>
                <p>Average Quality Score</p>
              </div>
            </div>

            <div className="quality-card summary-card">
              <div className="card-icon" style={{ color: dashboardData.summary.critical_issues > 0 ? '#dc3545' : '#6c757d' }}>
                <i className="fas fa-exclamation-circle" aria-hidden="true" />
              </div>
              <div className="card-content">
                <h3 style={{ color: dashboardData.summary.critical_issues > 0 ? '#dc3545' : '#6c757d' }}>
                  {dashboardData.summary.critical_issues}
                </h3>
                <p>Critical Issues</p>
              </div>
            </div>

            <div className="quality-card summary-card">
              <div className="card-icon"><i className="fas fa-cog" aria-hidden="true" /></div>
              <div className="card-content">
                <h3>{dashboardData.summary.active_rules}</h3>
                <p>Active Rules</p>
              </div>
            </div>
          </div>

          {/* Recent Scans */}
          <div className="quality-section">
            <h2 className="section-title">Recent Quality Scans</h2>
            <div className="quality-table-wrapper">
              <table className="quality-table">
                <thead>
                  <tr>
                    <th>Table Name</th>
                    <th>Overall Score</th>
                    <th>Issues</th>
                    <th>Scan Date</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {dashboardData.recent_scans.map((scan, idx) => (
                    <tr key={idx}>
                      <td className="table-name">{scan.table_name}</td>
                      <td>
                        <div className="score-badge" style={{ backgroundColor: getScoreColor(scan.overall_score) }}>
                          {(scan.overall_score * 100).toFixed(1)}%
                        </div>
                      </td>
                      <td>
                        <span className={`issue-count ${scan.issues_count > 0 ? 'has-issues' : ''}`}>
                          {scan.issues_count}
                        </span>
                      </td>
                      <td className="scan-date">{new Date(scan.scan_date).toLocaleString()}</td>
                      <td>
                        <button 
                          className="btn-small btn-view"
                          onClick={() => {
                            navigate(`/reporting?qualityTable=${encodeURIComponent(scan.table_name)}`);
                          }}
                        >
                          View Details
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Quality Trends */}
          {dashboardData.quality_trends.length > 0 && (
            <div className="quality-section">
              <h2 className="section-title">Quality Score Trends</h2>
              <div className="quality-trends-chart">
                {dashboardData.quality_trends.slice(-10).map((trend, idx) => (
                  <div key={idx} className="trend-bar">
                    <div 
                      className="trend-bar-fill" 
                      style={{ 
                        height: `${trend.score * 100}%`,
                        backgroundColor: getScoreColor(trend.score)
                      }}
                    ></div>
                    <span className="trend-label">{new Date(trend.date).toLocaleDateString()}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Rules Tab */}
      {activeTab === 'rules' && (
        <div className="quality-content">
          <div className="quality-section">
            <h2 className="section-title">Quality Rules</h2>
            
            <div className="rules-grid">
              {qualityRules.map((rule) => (
                <div key={rule.id} className={`rule-card ${!rule.enabled ? 'disabled' : ''}`}>
                  <div className="rule-header">
                    <h3>{rule.name}</h3>
                    <label className="toggle-switch">
                      <input 
                        type="checkbox" 
                        checked={rule.enabled}
                        onChange={() => toggleRule(rule.id)}
                      />
                      <span className="toggle-slider"></span>
                    </label>
                  </div>
                  <p className="rule-description">{rule.description}</p>
                  <div className="rule-details">
                    <span className={`rule-type ${rule.rule_type}`}>
                      {rule.rule_type}
                    </span>
                    <span className={`severity-badge ${getSeverityClass(rule.severity)}`}>
                      {rule.severity}
                    </span>
                  </div>
                  <div className="rule-condition">
                    <code>{rule.condition}</code>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* New Scan Modal */}
      {isModalOpen && (
        <div className="modal-overlay" onClick={() => setIsModalOpen(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Run Quality Scan</h2>
              <button className="modal-close" onClick={() => setIsModalOpen(false)}>×</button>
            </div>
            <div className="modal-body">
              <div className="form-group">
                <label>Table Name *</label>
                <input 
                  type="text"
                  placeholder="Enter table name"
                  value={newScanForm.table_name}
                  onChange={(e) => setNewScanForm({...newScanForm, table_name: e.target.value})}
                />
              </div>
              <div className="form-group">
                <label>Data Source</label>
                <select 
                  value={newScanForm.data_source}
                  onChange={(e) => setNewScanForm({...newScanForm, data_source: e.target.value})}
                >
                  <option value="neo4j">Neo4j</option>
                  <option value="postgresql">PostgreSQL</option>
                  <option value="oracle">Oracle</option>
                  <option value="sqlserver">SQL Server</option>
                </select>
              </div>
              <div className="form-group">
                <label>Select Rules (leave empty for all enabled rules)</label>
                <div className="rules-checkboxes">
                  {qualityRules.filter(r => r.enabled).map(rule => (
                    <label key={rule.id} className="checkbox-label">
                      <input 
                        type="checkbox"
                        checked={newScanForm.rules.includes(rule.id)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setNewScanForm({...newScanForm, rules: [...newScanForm.rules, rule.id]});
                          } else {
                            setNewScanForm({...newScanForm, rules: newScanForm.rules.filter(r => r !== rule.id)});
                          }
                        }}
                      />
                      {rule.name}
                    </label>
                  ))}
                </div>
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn-secondary" onClick={() => setIsModalOpen(false)}>
                Cancel
              </button>
              <button className="btn-primary" onClick={startQualityScan} disabled={loading}>
                {loading ? 'Starting...' : 'Start Scan'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
