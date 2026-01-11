import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { WORKFLOW_STAGES } from '@config/api-config.js';
import workflowService from '@services/workflow-service.js';
import './WorkflowProgress.css';

const WorkflowProgress = ({ currentPage, showDetails = true, showNavigation = true }) => {
  const [workflowStatus, setWorkflowStatus] = useState({ status: 'not_started' });
  const [isExpanded, setIsExpanded] = useState(false);

  useEffect(() => {
    // Initialize workflow if not started
    if (workflowStatus.status === 'not_started') {
      workflowService.initializeWorkflow({
        name: 'E2E Data Analytics Workflow',
        autoAdvance: false,
        validateStages: true
      });
    }

    // Update status
    const updateStatus = () => {
      setWorkflowStatus(workflowService.getWorkflowStatus());
    };

    // Event listeners
    workflowService.addEventListener('stage:completed', updateStatus);
    workflowService.addEventListener('workflow:advancing', updateStatus);
    workflowService.addEventListener('workflow:completed', updateStatus);

    updateStatus();

    return () => {
      workflowService.removeEventListener('stage:completed', updateStatus);
      workflowService.removeEventListener('workflow:advancing', updateStatus);
      workflowService.removeEventListener('workflow:completed', updateStatus);
    };
  }, [workflowStatus.status]);

  const getStageInfo = (stage) => {
    const stageMap = {
      [WORKFLOW_STAGES.DATA_CONFIGURATION]: {
        title: 'Data Configuration',
        icon: 'fas fa-cog',
        description: 'Set up data sources, schema, and quality rules',
        route: '/admin',
        pages: ['/admin', '/analytics']
      },
      [WORKFLOW_STAGES.DATA_PIPELINES]: {
        title: 'Data Pipelines',
        icon: 'fas fa-sync-alt',
        description: 'Configure ETL processes and mappings',
        route: '/migration',
        pages: ['/migration', '/analytics']
      },
      [WORKFLOW_STAGES.DATA_FLOW]: {
        title: 'Data Flow',
        icon: 'fas fa-stream',
        description: 'Visualize and monitor data flow through the system',
        route: '/',
        pages: ['/', '/graph-explorer', '/observability']
      },
      [WORKFLOW_STAGES.REPORTING]: {
        title: 'Reporting',
        icon: 'fas fa-chart-pie',
        description: 'Generate reports, dashboards, and export data',
        route: '/reporting',
        pages: ['/reporting', '/export']
      }
    };

    return stageMap[stage] || {};
  };

  const getStageStatus = (stage) => {
    if (!workflowStatus.workflow) return 'pending';
    
    const { completedStages, currentStage } = workflowStatus.workflow;
    
    if (completedStages.includes(stage)) return 'completed';
    if (currentStage === stage) return 'active';
    return 'pending';
  };

  const progressPercentage = workflowStatus.progress?.progress || 0;

  if (!showDetails && !showNavigation) {
    return (
      <div className="workflow-progress-minimal">
        <div className="progress-bar">
          <div 
            className="progress-fill" 
            style={{ width: `${progressPercentage}%` }}
          ></div>
        </div>
        <span className="progress-text">{progressPercentage}% Complete</span>
      </div>
    );
  }

  return (
    <div className={`workflow-progress-container ${isExpanded ? 'expanded' : 'collapsed'}`}>
      <div className="workflow-header" onClick={() => setIsExpanded(!isExpanded)}>
        <div className="workflow-title">
          <i className="fas fa-route"></i>
          <span>Workflow Progress</span>
          <div className="progress-indicator">
            {progressPercentage}%
          </div>
        </div>
        <button className="expand-toggle">
          <i className={`fas fa-chevron-${isExpanded ? 'up' : 'down'}`}></i>
        </button>
      </div>

      {isExpanded && (
        <div className="workflow-content">
          <div className="workflow-stages">
            {Object.values(WORKFLOW_STAGES).map((stage, index) => {
              const stageInfo = getStageInfo(stage);
              const status = getStageStatus(stage);
              const isCurrentPage = stageInfo.pages?.includes(currentPage);

              return (
                <div key={stage} className={`workflow-stage ${status} ${isCurrentPage ? 'current-page' : ''}`}>
                  <div className="stage-connector">
                    {index > 0 && <div className="connector-line"></div>}
                  </div>
                  
                  <div className="stage-content">
                    <div className="stage-icon">
                      {status === 'completed' ? (
                        <i className="fas fa-check-circle"></i>
                      ) : status === 'active' ? (
                        <i className="fas fa-play-circle"></i>
                      ) : (
                        <span>{stageInfo.icon}</span>
                      )}
                    </div>
                    
                    <div className="stage-info">
                      <h4 className="stage-title">{stageInfo.title}</h4>
                      {showDetails && (
                        <p className="stage-description">{stageInfo.description}</p>
                      )}
                      
                      {showNavigation && (
                        <div className="stage-actions">
                          <Link 
                            to={stageInfo.route} 
                            className={`stage-link ${status}`}
                          >
                            {status === 'completed' ? 'Review' : 
                             status === 'active' ? 'Continue' : 'Start'}
                          </Link>
                          
                          {status === 'active' && isCurrentPage && (
                            <span className="current-indicator">
                              <i className="fas fa-location-arrow"></i>
                              You are here
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="workflow-summary">
            <div className="summary-progress">
              <div className="progress-bar-full">
                <div 
                  className="progress-fill-full" 
                  style={{ width: `${progressPercentage}%` }}
                ></div>
              </div>
              <div className="progress-stats">
                <span>{workflowStatus.workflow?.completedStages.length || 0} of 4 stages completed</span>
                <span className="progress-percentage">{progressPercentage}%</span>
              </div>
            </div>

            {workflowStatus.status === 'completed' && (
              <div className="completion-message">
                <i className="fas fa-trophy"></i>
                <span>Workflow Complete! Your data analytics pipeline is ready.</span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default WorkflowProgress;
