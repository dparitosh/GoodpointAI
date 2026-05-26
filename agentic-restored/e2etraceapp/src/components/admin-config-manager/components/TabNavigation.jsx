/**
 * Tab Navigation Component
 */
import React from 'react';

export function TabNavigation({ tabs, activeTab, onTabChange }) {
  return (
    <div className="admin-tab-nav">
      {tabs.map(tab => (
        <button
          key={tab.id}
          className={`admin-tab-btn ${activeTab === tab.id ? 'active' : ''}`}
          onClick={() => onTabChange(tab.id)}
        >
          <span className="tab-icon"><i className={tab.icon}></i></span>
          <span className="tab-label">{tab.label}</span>
          {tab.count > 0 && <span className="tab-count">{tab.count}</span>}
        </button>
      ))}
    </div>
  );
}

export default TabNavigation;
