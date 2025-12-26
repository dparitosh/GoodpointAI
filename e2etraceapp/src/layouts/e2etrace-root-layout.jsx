import React from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { E2ETraceBreadcrumbs } from '../components/e2etrace-breadcrumbs';
import WorkflowProgress from '../components/WorkflowProgress';
import goodPointLogo from '../assets/goodpoint-logo.svg';
import './e2etrace-root-layout.css';

export const E2ETraceRootLayout = () => {
  const location = useLocation();

  // Some pages (like the Landing hero and the interactive state flow) are designed
  // to be full-bleed and should not be wrapped in the standard padded card.
  const isFullBleedPage = location.pathname === '/' || location.pathname === '/interactive-state-flow';
  
  return (
    <div className="e2etrace-app-container">
      <header className="e2etrace-app-header">
        <div className="e2etrace-app-logo">
          <img src={goodPointLogo} alt="GoodPoint" className="goodpoint-logo-img" />
          <div className="e2etrace-branding">
            <span className="e2etrace-title">GoodPoint AgenticAI</span>
            <span className="e2etrace-subtitle">PLM Data Migration Platform</span>
          </div>
        </div>
      </header>

      <div className="e2etrace-main-content-wrapper">
        <aside className="e2etrace-sidebar">
          <nav className="e2etrace-sidebar-nav">
            <div className="nav-section">
              <h3 className="nav-section-title">Home</h3>
              <ul>
                <li><NavLink to="/">Overview</NavLink></li>
              </ul>
            </div>

            <div className="nav-section">
              <h3 className="nav-section-title">Workflow Management</h3>
              <ul>
                <li><NavLink to="/workflow-manager">Workflow Manager</NavLink></li>
                <li><NavLink to="/interactive-state-flow">Interactive State Flow</NavLink></li>
                <li><NavLink to="/self-healing">Self-Healing Monitor</NavLink></li>
                <li><NavLink to="/multimodal">Multi-Modal Analyzer</NavLink></li>
              </ul>
            </div>
            
            <div className="nav-section">
              <h3 className="nav-section-title">Data Operations</h3>
              <ul>
                <li><NavLink to="/graphexplorer">Graph Explorer</NavLink></li>
                <li><NavLink to="/lineage">Data Lineage</NavLink></li>
              </ul>
            </div>
            
            <div className="nav-section">
              <h3 className="nav-section-title">Quality & Monitoring</h3>
              <ul>
                <li><NavLink to="/data-quality">Data Quality (SODA)</NavLink></li>
                <li><NavLink to="/observability">Observability</NavLink></li>
                <li><NavLink to="/analytics">Analytics</NavLink></li>
                <li><NavLink to="/reporting">Reports & Dashboards</NavLink></li>
                <li><NavLink to="/api-docs">API Docs (OpenAPI/Swagger)</NavLink></li>
              </ul>
            </div>
          </nav>
        </aside>
        <div className={`e2etrace-content-area ${isFullBleedPage ? 'full-bleed' : ''}`}>
          {!isFullBleedPage ? (
            <>
              <E2ETraceBreadcrumbs />
              <WorkflowProgress 
                currentPage={location.pathname}
                showDetails={false}
                showNavigation={true}
              />
            </>
          ) : null}
          <main className={isFullBleedPage ? 'e2etrace-page-content-full' : 'e2etrace-page-content'}>
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  );
};