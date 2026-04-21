import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import './ResumeMigration.css';

/**
 * Resume Migration Button Component
 * Shows a persistent button when there's an active migration in progress
 * Allows users to quickly return to their workflow from anywhere in the app
 */
export const ResumeMigration = () => {
  const [migrationProgress, setMigrationProgress] = useState(null);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    // Check for active migration on mount and when location changes
    const checkMigrationProgress = () => {
      try {
        const stored = localStorage.getItem('migration_in_progress');
        if (!stored) {
          setMigrationProgress(null);
          return;
        }

        const progress = JSON.parse(stored);
        
        // Check if data is not too old (24 hours max)
        const age = Date.now() - new Date(progress.timestamp).getTime();
        if (age > 24 * 60 * 60 * 1000) {
          localStorage.removeItem('migration_in_progress');
          setMigrationProgress(null);
          return;
        }

        setMigrationProgress(progress);
      } catch (error) {
        console.error('Error loading migration progress:', error);
        setMigrationProgress(null);
      }
    };

    checkMigrationProgress();

    // Re-check when localStorage changes (e.g., from another tab or component)
    const handleStorageChange = (e) => {
      if (e.key === 'migration_in_progress') {
        checkMigrationProgress();
      }
    };

    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, [location]);

  // Don't show on migration page itself
  if (!migrationProgress || location.pathname === '/migration') {
    return null;
  }

  const handleResume = () => {
    navigate(`/migration?step=${migrationProgress.step}`);
  };

  const handleDismiss = () => {
    localStorage.removeItem('migration_in_progress');
    setMigrationProgress(null);
  };

  const getStepName = (step) => {
    const stepNames = {
      1: 'Connect',
      2: 'Discovery',
      3: 'Map',
      4: 'Validate',
      5: 'Execute'
    };
    return stepNames[step] || `Step ${step}`;
  };

  return (
    <div className="resume-migration-banner">
      <div className="resume-migration-content">
        <i className="fas fa-exchange-alt" aria-hidden="true" />
        <div className="resume-migration-text">
          <strong>Migration in Progress:</strong>
          <span className="resume-migration-workflow">
            {migrationProgress.workflowName || 'Untitled Workflow'}
          </span>
          <span className="resume-migration-step">
            at {getStepName(migrationProgress.step)}
          </span>
          {migrationProgress.sourceSystem && (
            <span className="resume-migration-systems">
              ({migrationProgress.sourceSystem} → {migrationProgress.targetSystem})
            </span>
          )}
        </div>
      </div>
      <div className="resume-migration-actions">
        <button
          type="button"
          className="btn btn-sm btn-primary resume-migration-btn"
          onClick={handleResume}
        >
          <i className="fas fa-play-circle" /> Resume
        </button>
        <button
          type="button"
          className="btn btn-sm btn-outline-secondary resume-migration-dismiss"
          onClick={handleDismiss}
          aria-label="Dismiss migration banner"
        >
          <i className="fas fa-times" />
        </button>
      </div>
    </div>
  );
};
