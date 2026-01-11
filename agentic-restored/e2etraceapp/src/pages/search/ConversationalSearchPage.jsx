/**
 * Conversational Search Page
 * 
 * Dedicated page for AI-powered conversational search with
 * hybrid search configuration (File Patterns, Pipelines, Search, Indexes)
 */
import React, { useState } from 'react';
import ConversationalSearchUI from '../../components/conversational-search-ui.jsx';
import PipelineConfigManager from '../../components/pipeline-config-manager.jsx';
import './ConversationalSearchPage.css';

const ConversationalSearchPage = () => {
  const [activeTab, setActiveTab] = useState('search');

  const tabs = [
    { id: 'search', label: 'Search', icon: 'fas fa-comments' },
    { id: 'config', label: 'Configuration', icon: 'fas fa-cog' },
  ];

  return (
    <div className="conversational-search-page">
      <header className="search-page-header">
        <div className="header-content">
          <h1><i className="fas fa-comments"></i> Conversational Search</h1>
          <p>AI-powered search across PostgreSQL, Neo4j Graph, and OpenSearch</p>
        </div>
        <nav className="search-page-tabs">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              className={`search-tab ${activeTab === tab.id ? 'active' : ''}`}
              onClick={() => setActiveTab(tab.id)}
            >
              <i className={tab.icon}></i>
              <span>{tab.label}</span>
            </button>
          ))}
        </nav>
      </header>

      <main className="search-page-content">
        {activeTab === 'search' && (
          <div className="search-container">
            <ConversationalSearchUI />
          </div>
        )}

        {activeTab === 'config' && (
          <div className="config-container">
            <PipelineConfigManager />
          </div>
        )}
      </main>
    </div>
  );
};

export default ConversationalSearchPage;
