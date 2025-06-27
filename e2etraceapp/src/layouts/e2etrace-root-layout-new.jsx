import React, { useState, useEffect } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { E2ETraceBreadcrumbs } from '../components/e2etrace-breadcrumbs';
import { validateWorkflowStep } from '../config/api-config.js';
import './e2etrace-root-layout.css';

export const E2ETraceRootLayout = () => {
  const location = useLocation();
  const [workflowStatus, setWorkflowStatus] = useState({
    'data-config': { valid: null, message: '' },
    'data-pipelines': { valid: null, message: '' },
    'data-flow': { valid: null, message: '' },
  });

  useEffect(() => {
    // Validate workflow steps periodically
    const validateSteps = async () => {
      const steps = ['data-config', 'data-pipelines', 'data-flow'];
      const statuses = {};
      
      for (const step of steps) {
        try {
          statuses[step] = await validateWorkflowStep(step);
        } catch (error) {
          statuses[step] = { valid: false, message: 'Validation failed' };
        }
      }
      
      setWorkflowStatus(statuses);
    };

    validateSteps();
    const interval = setInterval(validateSteps, 30000); // Check every 30s
    
    return () => clearInterval(interval);
  }, []);

  const getWorkflowIcon = (stepKey) => {
    const status = workflowStatus[stepKey];
    if (status.valid === null) return '⏳';
    if (status.valid) return '✅';
    return '⚠️';
  };

  const getCurrentWorkflowStep = () => {
    const path = location.pathname;
    if (path.includes('data-config') || path.includes('spreadsheet') || path.includes('analytics')) {
      return 'data-config';
    }
    if (path.includes('nifi') || path.includes('etl') || path.includes('data-mapping')) {
      return 'data-pipelines';
    }
    if (path === '/' || path.includes('graphexplorer') || path.includes('monitoring')) {
      return 'data-flow';
    }
    return null;
  };

  return (
    <div className="e2etrace-app-container">
      <header className="e2etrace-app-header">
        <div className="e2etrace-app-logo">
          <i className="fas fa-project-diagram"></i> E2ETrace
        </div>
        <div className="workflow-indicator">
          <div className="workflow-steps">
            <div className={`workflow-step ${getCurrentWorkflowStep() === 'data-config' ? 'active' : ''}`}>
              <span className="step-icon">{getWorkflowIcon('data-config')}</span>
              <span className="step-text">Config</span>
            </div>
            <div className="workflow-arrow">→</div>
            <div className={`workflow-step ${getCurrentWorkflowStep() === 'data-pipelines' ? 'active' : ''}`}>
              <span className="step-icon">{getWorkflowIcon('data-pipelines')}</span>
              <span className="step-text">Pipelines</span>
            </div>
            <div className="workflow-arrow">→</div>
            <div className={`workflow-step ${getCurrentWorkflowStep() === 'data-flow' ? 'active' : ''}`}>
              <span className="step-icon">{getWorkflowIcon('data-flow')}</span>
              <span className="step-text">Flow</span>
            </div>
          </div>
        </div>
      </header>

      <div className="e2etrace-main-content-wrapper">
        <aside className="e2etrace-sidebar">
          <nav className="e2etrace-sidebar-nav">
            <div className="nav-section">
              <h3 className="nav-section-title">
                📊 Data Configuration 
                <span className="section-status">{getWorkflowIcon('data-config')}</span>
              </h3>
              <ul>
                <li><NavLink to="/data-config">🔌 Data Sources & Schema</NavLink></li>
                <li><NavLink to="/spreadsheet">📋 Data Spreadsheet</NavLink></li>
                <li><NavLink to="/analytics">📈 Analytics & Quality</NavLink></li>
              </ul>
            </div>
            
            <div className="nav-section">
              <h3 className="nav-section-title">
                🔄 Data Pipelines 
                <span className="section-status">{getWorkflowIcon('data-pipelines')}</span>
              </h3>
              <ul>
                <li><NavLink to="/nifi">⚡ NiFi Pipelines</NavLink></li>
                <li><NavLink to="/etl">🔧 ETL Processes</NavLink></li>
                <li><NavLink to="/data-mapping">🗺️ Data Mapping</NavLink></li>
              </ul>
            </div>
            
            <div className="nav-section">
              <h3 className="nav-section-title">
                🌊 Data Flow 
                <span className="section-status">{getWorkflowIcon('data-flow')}</span>
              </h3>
              <ul>
                <li><NavLink to="/">🎯 Flow Visualization</NavLink></li>
                <li><NavLink to="/graphexplorer">🔍 Graph Explorer</NavLink></li>
                <li><NavLink to="/monitoring">📊 Flow Monitoring</NavLink></li>
              </ul>
            </div>
            
            <div className="nav-section">
              <h3 className="nav-section-title">📋 Reporting & Export</h3>
              <ul>
                <li><NavLink to="/reporting">📄 Reports & Dashboards</NavLink></li>
                <li><NavLink to="/export">📤 Data Export</NavLink></li>
              </ul>
            </div>
            
            <div className="nav-section">
              <h3 className="nav-section-title">⚙️ System</h3>
              <ul>
                <li><NavLink to="/settings">Settings</NavLink></li>
              </ul>
            </div>
          </nav>
        </aside>
        <div className="e2etrace-content-area">
          <E2ETraceBreadcrumbs />
          <main className="e2etrace-page-content">
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  );
};
