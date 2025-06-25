import React, { useState } from 'react';
import './e2etrace-tabs.css';

export function E2ETraceTabs({ tabs, initialTab = 0, onTabChange }) {
  const [activeTab, setActiveTab] = useState(initialTab);

  const handleTabClick = (index) => {
    setActiveTab(index);
    if (onTabChange) {
      onTabChange(index);
    }
  };

  return (
    <div className="e2etrace-tabs-container">
      <div className="e2etrace-tab-headers">
        {tabs.map((tab, index) => (
          <button
            key={tab.label}
            className={`e2etrace-tab-header ${activeTab === index ? 'active' : ''}`}
            onClick={() => handleTabClick(index)}
            aria-selected={activeTab === index}
            role="tab"
            id={`tab-header-${index}`}
            aria-controls={`tab-panel-${index}`}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div className="e2etrace-tab-content">
        {tabs.map((tab, index) => (
          <div
            key={tab.label}
            className={`e2etrace-tab-panel ${activeTab === index ? 'active' : ''}`}
            role="tabpanel"
            id={`tab-panel-${index}`}
            aria-labelledby={`tab-header-${index}`}
            hidden={activeTab !== index}
          >
            {tab.content}
          </div>
        ))}
      </div>
    </div>
  );
}