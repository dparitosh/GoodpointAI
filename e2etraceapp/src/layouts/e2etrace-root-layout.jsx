import React from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { E2ETraceBreadcrumbs } from '../components/e2etrace-breadcrumbs';
import WorkflowProgress from '../components/WorkflowProgress';
import './e2etrace-root-layout.css';

export const E2ETraceRootLayout = () => {
  const location = useLocation();
  
  return (
    <div className="e2etrace-app-container">
      <header className="e2etrace-app-header">
        <div className="e2etrace-app-logo">
          <i className="fas fa-project-diagram"></i> E2ETrace
        </div>
      </header>

      <div className="e2etrace-main-content-wrapper">
        <aside className="e2etrace-sidebar">
          <nav className="e2etrace-sidebar-nav">
            <div className="nav-section">
              <h3 className="nav-section-title">📊 Data Configuration</h3>
              <ul>
                <li><NavLink to="/data-config">Data Sources & Schema</NavLink></li>
                <li><NavLink to="/spreadsheet">📋 Data Spreadsheet</NavLink></li>
                <li><NavLink to="/analytics">📈 Analytics & Quality</NavLink></li>
              </ul>
            </div>
            
            <div className="nav-section">
              <h3 className="nav-section-title">🔄 Data Pipelines</h3>
              <ul>
                <li><NavLink to="/processing">🏭 Processing Hub</NavLink></li>
                <li><NavLink to="/nifi">NiFi Pipelines</NavLink></li>
                <li><NavLink to="/etl">ETL Processes</NavLink></li>
                <li><NavLink to="/data-mapping">Data Mapping</NavLink></li>
              </ul>
            </div>
            
            <div className="nav-section">
              <h3 className="nav-section-title">🌊 Data Flow</h3>
              <ul>
                <li><NavLink to="/">Flow Visualization</NavLink></li>
                <li><NavLink to="/graphexplorer">Graph Explorer</NavLink></li>
                <li><NavLink to="/monitoring">Flow Monitoring</NavLink></li>
              </ul>
            </div>
            
            <div className="nav-section">
              <h3 className="nav-section-title">📋 Reporting</h3>
              <ul>
                <li><NavLink to="/reporting">Reports & Dashboards</NavLink></li>
                <li><NavLink to="/export">Data Export</NavLink></li>
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
          <WorkflowProgress 
            currentPage={location.pathname}
            showDetails={false}
            showNavigation={true}
          />
          <main className="e2etrace-page-content">
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  );
};