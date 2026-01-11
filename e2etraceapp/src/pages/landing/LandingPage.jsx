import React from 'react';
import { Link } from 'react-router-dom';
import goodPointLogo from '../../assets/goodpoint-logo.svg';
import { XStateVisualizer } from '../../components/xstate-visualizer/XStateVisualizer';
import { getSampleInteractiveStateFlow } from '../../data/sampleInteractiveStateFlow';
import './LandingPage.css';

const LandingPage = () => {
  // Organized by PLM Data Migration workflow stages
  const migrationSteps = [
    {
      step: 1,
      icon: 'fas fa-plug',
      title: 'Connect',
      description: 'Configure source and target data connections',
      action: 'Set up connections',
      link: '/migration'
    },
    {
      step: 2,
      icon: 'fas fa-sitemap',
      title: 'Schema',
      description: 'Review and map data structures',
      action: 'Explore schemas',
      link: '/migration'
    },
    {
      step: 3,
      icon: 'fas fa-arrows-alt-h',
      title: 'Map',
      description: 'AI-assisted field mapping',
      action: 'Create mappings',
      link: '/migration'
    },
    {
      step: 4,
      icon: 'fas fa-check-double',
      title: 'Validate',
      description: 'Quality checks & transformations',
      action: 'Run validation',
      link: '/migration'
    },
    {
      step: 5,
      icon: 'fas fa-play-circle',
      title: 'Execute',
      description: 'Run migration & monitor',
      action: 'Start migration',
      link: '/migration'
    }
  ];

  const toolCards = [
    {
      icon: 'fas fa-exchange-alt',
      title: 'Migration Wizard',
      description: 'End-to-end guided data migration with AI-powered mapping and validation',
      link: '/migration',
      color: 'var(--accent-color)',
      primary: true
    },
    {
      icon: 'fas fa-project-diagram',
      title: 'Graph Explorer',
      description: 'Visualize and explore data relationships',
      link: '/graph-explorer',
      color: 'var(--success-color)'
    },
    {
      icon: 'fas fa-stream',
      title: 'Data Lineage',
      description: 'Track data flow and transformations',
      link: '/lineage',
      color: 'var(--info-color)'
    },
    {
      icon: 'fas fa-clipboard-check',
      title: 'Rule Engine',
      description: 'Data quality rules and validation',
      link: '/rule-engine',
      color: 'var(--warning-color)'
    },
    {
      icon: 'fas fa-chart-line',
      title: 'Analytics',
      description: 'Insights and performance metrics',
      link: '/analytics',
      color: 'var(--primary-light)'
    }
  ];

  return (
    <div className="landing-page">
      {/* Hero Section */}
      <section className="hero-section">
        <div className="hero-content">
          <div className="hero-badge">
            <span className="badge-icon"><i className="fas fa-robot" aria-hidden="true" /></span>
            <span className="badge-text">AI-Powered Migration Platform</span>
          </div>
          <div className="hero-logo">
            <img src={goodPointLogo} alt="GoodPoint Logo" className="hero-logo-img" />
          </div>
          <h1 className="hero-title">
            <span className="brand-highlight">GoodPoint</span> AgenticAI
          </h1>
          <p className="hero-subtitle">
            Intelligent PLM Data Migration
          </p>
          <p className="hero-description">
            Streamlined data migration with AI-powered schema mapping, quality validation, 
            and enterprise-grade transformation capabilities.
          </p>
          <div className="hero-actions">
            <Link to="/migration" className="btn btn-primary btn-lg">
              <i className="fas fa-rocket" aria-hidden="true" />
              Start Migration
            </Link>
            <Link to="/admin" className="btn btn-secondary">
              <i className="fas fa-cog" aria-hidden="true" />
              Admin Settings
            </Link>
          </div>
        </div>
        <div className="hero-visual">
          <XStateVisualizer
            graphData={getSampleInteractiveStateFlow()}
            embedded
            enabledViewModes={['graph']}
            uiVariant="graph-only"
          />
        </div>
      </section>

      {/* Migration Workflow Steps */}
      <section className="workflow-section">
        <div className="section-header">
          <h2 className="section-title">Migration Workflow</h2>
          <p className="section-description">
            Simple 5-step process for end-to-end PLM data migration
          </p>
        </div>
        
        <div className="workflow-steps">
          {migrationSteps.map((step, index) => (
            <Link to={`${step.link}?step=${step.step}`} key={step.step} className="workflow-step">
              <div className="step-number">{step.step}</div>
              <div className="step-icon">
                <i className={step.icon} aria-hidden="true" />
              </div>
              <h3 className="step-title">{step.title}</h3>
              <p className="step-description">{step.description}</p>
              {index < migrationSteps.length - 1 && (
                <div className="step-connector">
                  <i className="fas fa-chevron-right" aria-hidden="true" />
                </div>
              )}
            </Link>
          ))}
        </div>
        
        <div className="workflow-cta">
          <Link to="/migration" className="btn btn-primary">
            <i className="fas fa-play" aria-hidden="true" />
            Launch Migration Wizard
          </Link>
        </div>
      </section>

      {/* Tool Cards */}
      <section className="tools-section">
        <div className="section-header">
          <h2 className="section-title">Platform Tools</h2>
          <p className="section-description">
            Comprehensive toolkit for data engineering and analytics
          </p>
        </div>
        
        <div className="tools-grid">
          {toolCards.map((tool, index) => (
            <Link 
              to={tool.link} 
              key={index} 
              className={`tool-card ${tool.primary ? 'primary' : ''}`}
              style={{ '--card-color': tool.color }}
            >
              <div className="tool-icon">
                <i className={tool.icon} aria-hidden="true" />
              </div>
              <div className="tool-content">
                <h3 className="tool-title">{tool.title}</h3>
                <p className="tool-description">{tool.description}</p>
              </div>
              <div className="tool-arrow">
                <i className="fas fa-arrow-right" aria-hidden="true" />
              </div>
            </Link>
          ))}
        </div>
      </section>

      {/* Quick Stats */}
      <section className="stats-section">
        <div className="stats-grid">
          <div className="stat-item">
            <div className="stat-value">5</div>
            <div className="stat-label">Migration Steps</div>
          </div>
          <div className="stat-item">
            <div className="stat-value">AI</div>
            <div className="stat-label">Powered Mapping</div>
          </div>
          <div className="stat-item">
            <div className="stat-value">100%</div>
            <div className="stat-label">GraphQL Native</div>
          </div>
          <div className="stat-item">
            <div className="stat-value">Real-time</div>
            <div className="stat-label">Validation</div>
          </div>
        </div>
      </section>

      {/* Tech Stack */}
      <section className="tech-stack-section">
        <div className="section-header">
          <h2 className="section-title">Technology Stack</h2>
        </div>
        <div className="tech-badges">
          <div className="tech-badge"><i className="fas fa-brain" /> GraphRAG</div>
          <div className="tech-badge"><i className="fas fa-database" /> Neo4j</div>
          <div className="tech-badge"><i className="fas fa-code-branch" /> GraphQL</div>
          <div className="tech-badge"><i className="fas fa-robot" /> Agentic AI</div>
          <div className="tech-badge"><i className="fab fa-react" /> React</div>
          <div className="tech-badge"><i className="fab fa-python" /> FastAPI</div>
        </div>
      </section>
    </div>
  );
};

export default LandingPage;
