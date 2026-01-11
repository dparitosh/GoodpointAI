import React from 'react';
import MigrationWizard from '../../components/migration-wizard/MigrationWizard.jsx';
import './MigrationPage.css';

/**
 * MigrationPage - Dedicated PLM Data Migration Wizard Page
 * 
 * This is the primary entry point for end-to-end data migration.
 * It provides a streamlined 5-step wizard workflow:
 * 1. Connect - Select source and target data sources
 * 2. Schema - Review and configure data structures
 * 3. Map - Define field mappings with AI assistance
 * 4. Validate - Run quality checks and test transformations
 * 5. Execute - Run migration and monitor progress
 */
const MigrationPage = () => {
  const handleMigrationComplete = (results) => {
    console.log('Migration completed:', results);
  };

  return (
    <div className="migration-page">
      <div className="page-header">
        <div className="header-content">
          <div className="header-icon">
            <i className="fas fa-exchange-alt" />
          </div>
          <div className="header-text">
            <h1>PLM Data Migration</h1>
            <p>End-to-end data migration with AI-powered mapping and validation</p>
          </div>
        </div>
        <div className="header-badges">
          <span className="badge ai-powered">
            <i className="fas fa-robot" /> AI-Powered
          </span>
          <span className="badge graphql">
            <i className="fas fa-project-diagram" /> GraphQL
          </span>
        </div>
      </div>
      
      <div className="wizard-container">
        <MigrationWizard onComplete={handleMigrationComplete} />
      </div>
    </div>
  );
};

export default MigrationPage;
