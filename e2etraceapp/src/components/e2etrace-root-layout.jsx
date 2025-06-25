import React from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { E2ETraceBreadcrumbs } from './e2etrace-breadcrumbs';
import './e2etrace-root-layout.css';

/**
 * E2ETraceRootLayout component serves as the main application shell.
 * It includes a header, a sidebar for navigation, breadcrumbs, and a main content area.
 */
export const E2ETraceRootLayout = () => {
  return (
    <div className="e2etrace-app-container">
      {/* Header Section */}
      <header className="e2etrace-app-header">
        <div className="e2etrace-app-logo">
          <i className="fas fa-project-diagram"></i> E2ETrace
        </div>
        <nav className="e2etrace-header-nav">
          {/* Add any global navigation items here if needed */}
        </nav>
      </header>

      {/* Main Content Area */}
      <div className="e2etrace-main-content-wrapper">
        <aside className="e2etrace-sidebar">
          <nav className="e2etrace-sidebar-nav">
            <ul>
              {/* The landing page is now Analytics */}
              <li><NavLink to="/">Analytics</NavLink></li>
              {/* The dashboard is now the Graph Explorer */}
              <li><NavLink to="/graphexplorer">Graph Explorer</NavLink></li>
              {/* Other top-level pages */}
              <li><NavLink to="/quickactions">Quick Actions</NavLink></li>
              <li><NavLink to="/nifi">NiFi</NavLink></li>
              <li><NavLink to="/etl">ETL Overview</NavLink></li>
              <li><NavLink to="/settings">Settings</NavLink></li>
            </ul>
          </nav>
        </aside>
        <div className="e2etrace-content-area">
          <E2ETraceBreadcrumbs />
          <main className="e2etrace-page-content">
            <Outlet /> {/* Renders the matched child route component */}
          </main>
        </div>
      </div>
    </div>
  );
};