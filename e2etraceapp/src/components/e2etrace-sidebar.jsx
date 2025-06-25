import React from 'react';
import { NavLink } from 'react-router-dom';
import './e2etrace-sidebar.css';

/**
 * E2ETraceSidebar component for application navigation.
 */
export const E2ETraceSidebar = () => {
  return (
    <aside className="e2etrace-sidebar">
      <nav className="e2etrace-sidebar-nav">
        <ul>
          <li>
            <NavLink to="/" className={({ isActive }) => isActive ? 'active' : ''} end>
              <i className="fas fa-home"></i>
              <span>Home</span>
            </NavLink>
          </li>
          <li>
            <NavLink to="/dashboard" className={({ isActive }) => isActive ? 'active' : ''}>
              <i className="fas fa-chart-line"></i>
              <span>Dashboard</span>
            </NavLink>
          </li>
          <li>
            <NavLink to="/settings" className={({ isActive }) => isActive ? 'active' : ''}>
              <i className="fas fa-cog"></i>
              <span>Settings</span>
            </NavLink>
          </li>
          {/* Add more navigation links here */}
          {/* Example: <li><NavLink to="/reports"><i className="fas fa-file-alt"></i><span>Reports</span></NavLink></li> */}
        </ul>
      </nav>
      {/* Optional: Add footer or version info here */}
      <div className="e2etrace-sidebar-footer">v1.0.0</div>
    </aside>
  );
};