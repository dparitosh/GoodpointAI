import React, { useState, useEffect } from 'react';
import './DataQualityDashboard.css';

/**
 * SODA-Style Data Quality Dashboard
 * Complete UI for data quality monitoring, scanning, and rule management
 */
export const DataQualityDashboard = () => {
  const [activeTab, setActiveTab] = useState('dashboard'); // dashboard, scans, rules, reports
  const [dashboardData, setDashboardData] = useState(null);
  const [qualityReports, setQualityReports] = useState([]);
  const [qualityRules, setQualityRules] = useState([]);
  const [scans, setScans] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedReport, setSelectedReport] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [newScanForm, setNewScanForm] = useState({
    table_name: '',
    data_source: 'neo4j',
    rules: []
  });

  // Fetch dashboard data
  const fetchDashboard = async () => {
    try {
      setLoading(true);
      const response = await fetch('http://localhost:8000/api/analytics/quality/dashboard');
      if (!response.ok) throw new Error('Failed to fetch dashboard data');
      const data = await response.json();
      setDashboardData(data);
      setError(null);
    } catch (err) {
      setError(err.message);
      console.error('Dashboard fetch error:', err);
    } finally {
      setLoading(false);
    }
  };

  // Fetch quality reports
  const fetchReports = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/analytics/quality/reports');
      if (!response.ok) throw new Error('Failed to fetch reports');
      const data = await response.json();
      setQualityReports(data);
    } catch (err) {
      console.error('Reports fetch error:', err);
    }
  };

  // Fetch quality rules
  const fetchRules = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/analytics/quality/rules?enabled_only=false');
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
      const response = await fetch(`http://localhost:8000/api/analytics/quality/scan/${newScanForm.table_name}`, {
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
        fetchReports();
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
      const response = await fetch(`http://localhost:8000/api/analytics/quality/rules/${ruleId}/toggle`, {
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
    fetchReports();
    fetchRules();
  }, []);

  // Auto-refresh dashboard
  useEffect(() => {
    if (activeTab === 'dashboard') {
      const interval = setInterval(fetchDashboard, 30000); // 30 seconds
      return () => clearInterval(interval);
    }
  }, [activeTab]);

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
          <h1>🔍 Data Quality Management</h1>
          <p className="quality-subtitle">SODA-Style Quality Monitoring & Validation</p>
        </div>
        <button 
          className="btn-primary btn-scan"
          onClick={() => setIsModalOpen(true)}
        >
          ▶ Run Quality Scan
        </button>
      </div>

      {/* Tabs */}
      <div className="quality-tabs">
        <button 
          className={`quality-tab ${activeTab === 'dashboard' ? 'active' : ''}`}
          onClick={() => setActiveTab('dashboard')}
        >
          📊 Dashboard
        </button>
        <button 
          className={`quality-tab ${activeTab === 'reports' ? 'active' : ''}`}
          onClick={() => setActiveTab('reports')}
        >
          📋 Reports
        </button>
        <button 
          className={`quality-tab ${activeTab === 'rules' ? 'active' : ''}`}
          onClick={() => setActiveTab('rules')}
        >
          ⚙️ Rules
        </button>
      </div>

      {error && (
        <div className="quality-error">
          ⚠️ {error}
        </div>
      )}

      {/* Dashboard Tab */}
      {activeTab === 'dashboard' && dashboardData && (
        <div className="quality-content">
          {/* Summary Cards */}
          <div className="quality-summary-cards">
            <div className="quality-card summary-card">
              <div className="card-icon">📊</div>
              <div className="card-content">
                <h3>{dashboardData.summary.total_tables_scanned}</h3>
                <p>Tables Scanned</p>
              </div>
            </div>

            <div className="quality-card summary-card">
              <div className="card-icon" style={{ color: getScoreColor(dashboardData.summary.average_quality_score / 100) }}>
                {dashboardData.summary.average_quality_score >= 90 ? '✓' : '⚠'}
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
                ⚠
              </div>
              <div className="card-content">
                <h3 style={{ color: dashboardData.summary.critical_issues > 0 ? '#dc3545' : '#6c757d' }}>
                  {dashboardData.summary.critical_issues}
                </h3>
                <p>Critical Issues</p>
              </div>
            </div>

            <div className="quality-card summary-card">
              <div className="card-icon">🔧</div>
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
                            const report = qualityReports.find(r => r.table_name === scan.table_name);
                            if (report) {
                              setSelectedReport(report);
                              setActiveTab('reports');
                            }
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

      {/* Reports Tab */}
      {activeTab === 'reports' && (
        <div className="quality-content">
          <div className="quality-section">
            <h2 className="section-title">Quality Reports</h2>
            
            {selectedReport ? (
              <div className="report-detail">
                <button 
                  className="btn-back"
                  onClick={() => setSelectedReport(null)}
                >
                  ← Back to Reports
                </button>
                
                <div className="report-header">
                  <h3>{selectedReport.table_name}</h3>
                  <div className="report-meta">
                    <span>Scan ID: {selectedReport.scan_id}</span>
                    <span>Date: {new Date(selectedReport.scan_date).toLocaleString()}</span>
                    <span>Rows: {selectedReport.row_count.toLocaleString()}</span>
                    <span>Columns: {selectedReport.column_count}</span>
                  </div>
                </div>

                {/* Quality Scores */}
                <div className="report-scores">
                  <div className="score-card">
                    <h4>Completeness</h4>
                    <div className="score-circle" style={{ borderColor: getScoreColor(selectedReport.completeness_score) }}>
                      {(selectedReport.completeness_score * 100).toFixed(1)}%
                    </div>
                  </div>
                  <div className="score-card">
                    <h4>Accuracy</h4>
                    <div className="score-circle" style={{ borderColor: getScoreColor(selectedReport.accuracy_score) }}>
                      {(selectedReport.accuracy_score * 100).toFixed(1)}%
                    </div>
                  </div>
                  <div className="score-card">
                    <h4>Consistency</h4>
                    <div className="score-circle" style={{ borderColor: getScoreColor(selectedReport.consistency_score) }}>
                      {(selectedReport.consistency_score * 100).toFixed(1)}%
                    </div>
                  </div>
                  <div className="score-card">
                    <h4>Validity</h4>
                    <div className="score-circle" style={{ borderColor: getScoreColor(selectedReport.validity_score) }}>
                      {(selectedReport.validity_score * 100).toFixed(1)}%
                    </div>
                  </div>
                  <div className="score-card overall">
                    <h4>Overall Score</h4>
                    <div className="score-circle large" style={{ borderColor: getScoreColor(selectedReport.overall_score) }}>
                      {(selectedReport.overall_score * 100).toFixed(1)}%
                    </div>
                  </div>
                </div>

                {/* Issues */}
                {selectedReport.issues.length > 0 && (
                  <div className="report-issues">
                    <h4>Quality Issues ({selectedReport.issues.length})</h4>
                    {selectedReport.issues.map((issue, idx) => (
                      <div key={idx} className="issue-card">
                        <div className="issue-header">
                          <span className={`severity-badge ${getSeverityClass(issue.severity)}`}>
                            {issue.severity.toUpperCase()}
                          </span>
                          <span className="issue-description">{issue.description}</span>
                        </div>
                        <div className="issue-details">
                          <span>Affected Rows: {issue.affected_rows}</span>
                          <span>Columns: {issue.affected_columns.join(', ')}</span>
                        </div>
                        <div className="issue-suggestion">
                          💡 {issue.suggestion}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Recommendations */}
                {selectedReport.recommendations.length > 0 && (
                  <div className="report-recommendations">
                    <h4>Recommendations</h4>
                    <ul>
                      {selectedReport.recommendations.map((rec, idx) => (
                        <li key={idx}>{rec}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ) : (
              <div className="reports-list">
                {qualityReports.map((report, idx) => (
                  <div 
                    key={idx} 
                    className="report-card"
                    onClick={() => setSelectedReport(report)}
                  >
                    <div className="report-card-header">
                      <h3>{report.table_name}</h3>
                      <div className="report-score" style={{ backgroundColor: getScoreColor(report.overall_score) }}>
                        {(report.overall_score * 100).toFixed(0)}%
                      </div>
                    </div>
                    <div className="report-card-body">
                      <div className="report-stat">
                        <span className="stat-label">Issues:</span>
                        <span className="stat-value">{report.issues.length}</span>
                      </div>
                      <div className="report-stat">
                        <span className="stat-label">Rows:</span>
                        <span className="stat-value">{report.row_count.toLocaleString()}</span>
                      </div>
                      <div className="report-stat">
                        <span className="stat-label">Scanned:</span>
                        <span className="stat-value">{new Date(report.scan_date).toLocaleDateString()}</span>
                      </div>
                    </div>
                  </div>
                ))}
                {qualityReports.length === 0 && (
                  <div className="empty-state">
                    <p>No quality reports yet. Run a scan to generate reports.</p>
                  </div>
                )}
              </div>
            )}
          </div>
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
