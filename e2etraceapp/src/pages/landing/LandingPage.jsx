import React from 'react';
import { Link } from 'react-router-dom';
import goodPointLogo from '../assets/goodpoint-logo.svg';
import './LandingPage.css';

const LandingPage = () => {
  const features = [
    {
      icon: 'fas fa-database',
      title: 'Data Configuration',
      description: 'Configure data sources, schemas, and connections with Neo4j, SQL, and more',
      link: '/data-config',
      color: '#0066CC'
    },
    {
      icon: 'fas fa-cogs',
      title: 'Data Processing',
      description: 'ETL workflows, data transformation, and quality assessment',
      link: '/processing',
      color: '#6929C4'
    },
    {
      icon: 'fas fa-project-diagram',
      title: 'Graph Explorer',
      description: 'Visualize and explore graph relationships with interactive tools',
      link: '/graph-explorer',
      color: '#24A148'
    },
    {
      icon: 'fas fa-exchange-alt',
      title: 'Migration Visualizer',
      description: 'Track PLM migration progress with state machine visualization',
      link: '/plm-migration-visualizer',
      color: '#FF832B'
    },
    {
      icon: 'fas fa-sitemap',
      title: 'XState Visualizer',
      description: 'Visualize state machines and workflows with interactive diagrams',
      link: '/xstate-visualizer',
      color: '#DA1E28'
    }
  ];

  return (
    <div className="landing-page">
      {/* Hero Section */}
      <section className="hero-section">
        <div className="hero-content">
          <div className="hero-badge">
            <span className="badge-icon"><i className="fas fa-robot"></i></span>
            <span className="badge-text">AI-Powered Migration Platform</span>
          </div>
          <div className="hero-logo">
            <img src={goodPointLogo} alt="GoodPoint Logo" className="hero-logo-img" />
          </div>
          <h1 className="hero-title">
            Welcome to <span className="brand-highlight">GoodPoint AgenticAI</span>
          </h1>
          <p className="hero-subtitle">
            Intelligent PLM Data Migration Platform
          </p>
          <p className="hero-description">
            AI-powered solution for seamless Product Lifecycle Management data migration, 
            transformation, and integration with enterprise-grade reliability and visualization.
          </p>
          <div className="hero-actions">
            <Link to="/data-config" className="btn btn-primary">
              Get Started
              <span className="btn-icon">→</span>
            </Link>
            <Link to="/graph-explorer" className="btn btn-secondary">
              Explore Features
              <span className="btn-icon"><i className="fas fa-search"></i></span>
            </Link>
          </div>
        </div>
        <div className="hero-visual">
          <div className="floating-card card-1">
            <div className="card-icon"><i className="fas fa-chart-bar"></i></div>
            <div className="card-label">Analytics</div>
          </div>
          <div className="floating-card card-2">
            <div className="card-icon"><i className="fas fa-sync-alt"></i></div>
            <div className="card-label">ETL Pipeline</div>
          </div>
          <div className="floating-card card-3">
            <div className="card-icon"><i className="fas fa-network-wired"></i></div>
            <div className="card-label">Graph DB</div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="features-section">
        <div className="section-header">
          <h2 className="section-title">Platform Capabilities</h2>
          <p className="section-description">
            Comprehensive tools for modern data engineering and analytics
          </p>
        </div>
        
        <div className="features-grid">
          {features.map((feature, index) => (
            <Link 
              to={feature.link} 
              key={index} 
              className="feature-card"
              style={{ '--accent-color': feature.color }}
            >
              <div className="feature-icon"><i className={feature.icon}></i></div>
              <h3 className="feature-title">{feature.title}</h3>
              <p className="feature-description">{feature.description}</p>
              <div className="feature-link-arrow">→</div>
            </Link>
          ))}
        </div>
      </section>

      {/* Stats Section */}
      <section className="stats-section">
        <div className="stats-grid">
          <div className="stat-item">
            <div className="stat-value">100+</div>
            <div className="stat-label">Data Sources</div>
          </div>
          <div className="stat-item">
            <div className="stat-value">1M+</div>
            <div className="stat-label">Records Processed</div>
          </div>
          <div className="stat-item">
            <div className="stat-value">99.9%</div>
            <div className="stat-label">Uptime</div>
          </div>
          <div className="stat-item">
            <div className="stat-value">50TB+</div>
            <div className="stat-label">Data Managed</div>
          </div>
        </div>
      </section>

      {/* Tech Stack Section */}
      <section className="tech-stack-section">
        <div className="section-header">
          <h2 className="section-title">Powered By</h2>
        </div>
        <div className="tech-badges">
          <div className="tech-badge">Neo4j</div>
          <div className="tech-badge">React</div>
          <div className="tech-badge">FastAPI</div>
          <div className="tech-badge">Cytoscape</div>
          <div className="tech-badge">XState</div>
          <div className="tech-badge">Python</div>
        </div>
      </section>
    </div>
  );
};

export default LandingPage;
