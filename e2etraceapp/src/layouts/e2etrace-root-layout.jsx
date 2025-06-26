import React from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { E2ETraceBreadcrumbs } from '../components/e2etrace-breadcrumbs';
import './e2etrace-root-layout.css';

export const E2ETraceRootLayout = () => {
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
            <ul>
              <li><NavLink to="/">Analytics</NavLink></li>
              <li><NavLink to="/graphexplorer">Graph Explorer</NavLink></li>
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
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  );
};