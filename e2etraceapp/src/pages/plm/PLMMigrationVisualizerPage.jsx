/**
 * PLM Migration Visualizer Page
 * Main page for visualizing and controlling PLM database migration
 * Powered by GoodPoint AI
 */
import React, { useState, useEffect, useRef, useCallback } from 'react';
import PLMMigrationStatechartVisualizer from '../../components/plm/PLMMigrationStatechartVisualizer.jsx';
import { MigrationStates, MigrationEvents, getAvailableActions } from '../../machines/plmMigrationMachine.js';
import goodPointLogo from '../../assets/goodpoint-logo.svg';
import './PLMMigrationVisualizerPage.css';

// Configuration
const API_BASE_URL = window.location.hostname === 'localhost' 
  ? 'http://localhost:8000'
  : `${window.location.protocol}//${window.location.hostname}:8000`;

const PLMMigrationVisualizerPage = () => {
  const [sessionId, setSessionId] = useState(null);
  const [currentState, setCurrentState] = useState(MigrationStates.IDLE);
  const [progress, setProgress] = useState(0);
  const [qualityScore, setQualityScore] = useState(0);
  const [errors, setErrors] = useState([]);
  const [isConnected, setIsConnected] = useState(false);
  const [controlsDisabled, setControlsDisabled] = useState(false);
  const [startTime, setStartTime] = useState(null);
  const [elapsedTime, setElapsedTime] = useState(0);
  
  const wsRef = useRef(null);
  const timerRef = useRef(null);

  // Timer for elapsed time
  useEffect(() => {
    if (startTime && currentState !== MigrationStates.COMPLETED && currentState !== MigrationStates.FAILED) {
      timerRef.current = setInterval(() => {
        const elapsed = Math.floor((Date.now() - startTime) / 1000);
        setElapsedTime(elapsed);
      }, 1000);
    } else {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    }

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    };
  }, [startTime, currentState]);

  // WebSocket connection
  const connectWebSocket = useCallback((sid) => {
    if (wsRef.current) {
      wsRef.current.close();
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.hostname === 'localhost' ? 'localhost:8000' : window.location.host;
    const wsUrl = `${protocol}//${host}/api/migration/advanced/ws/${sid}`;

    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log('WebSocket connected');
      setIsConnected(true);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log('WebSocket message:', data);

        if (data.state) {
          setCurrentState(data.state);
        }
        if (data.progress !== undefined) {
          setProgress(data.progress);
        }
        if (data.quality !== undefined) {
          setQualityScore(data.quality);
        }
        if (data.errors) {
          setErrors(data.errors);
        }
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      setIsConnected(false);
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected');
      setIsConnected(false);
    };

    wsRef.current = ws;
  }, []);

  // Cleanup WebSocket on unmount
  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  // Start new migration
  const handleStartMigration = async () => {
    setControlsDisabled(true);

    try {
      const response = await fetch(`${API_BASE_URL}/api/migration/advanced/start`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          sources: [
            {
              type: 'postgresql',
              host: 'source-db.example.com',
              port: 5432,
              database: 'plm_source'
            }
          ],
          target: {
            type: 'postgresql',
            host: 'target-db.example.com',
            port: 5432,
            database: 'plm_target'
          },
          strategy: 'incremental'
        })
      });

      const data = await response.json();

      if (data.status === 'success') {
        const sid = data.session_id;
        setSessionId(sid);
        setStartTime(Date.now());
        connectWebSocket(sid);
      } else {
        console.error('Failed to start migration:', data.message);
        alert('Failed to start migration: ' + data.message);
      }
    } catch (error) {
      console.error('Error starting migration:', error);
      alert('Error starting migration: ' + error.message);
    } finally {
      setControlsDisabled(false);
    }
  };

  // Send control event
  const handleControlEvent = async (event) => {
    if (!sessionId) return;

    setControlsDisabled(true);

    try {
      const response = await fetch(`${API_BASE_URL}/api/migration/advanced/${sessionId}/events`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ event })
      });

      const data = await response.json();

      if (data.status !== 'success') {
        console.error('Control event failed:', data.message);
        alert('Control event failed: ' + data.message);
      }
    } catch (error) {
      console.error('Error sending control event:', error);
      alert('Error sending control event: ' + error.message);
    } finally {
      // Wait for backend acknowledgment before re-enabling
      setTimeout(() => setControlsDisabled(false), 500);
    }
  };

  // Download history
  const handleDownloadHistory = async () => {
    if (!sessionId) return;

    try {
      const response = await fetch(`${API_BASE_URL}/api/migration/advanced/${sessionId}/history?format=csv`);
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `migration_${sessionId}_history.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Error downloading history:', error);
      alert('Error downloading history: ' + error.message);
    }
  };

  // Format elapsed time
  const formatElapsedTime = (seconds) => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;

    if (hours > 0) {
      return `${hours}h ${minutes}m ${secs}s`;
    } else if (minutes > 0) {
      return `${minutes}m ${secs}s`;
    } else {
      return `${secs}s`;
    }
  };

  const availableActions = getAvailableActions(currentState);

  return (
    <div className="plm-migration-visualizer-page">
      <div className="page-header">
        <div className="page-header-content">
          <img src={goodPointLogo} alt="GoodPoint" className="page-logo" />
          <div className="page-title-group">
            <h1>PLM Migration Visualizer</h1>
            <p className="page-subtitle">AI powered PLM Data migration</p>
          </div>
        </div>
        <div className="connection-status">
          <span className={`status-indicator ${isConnected ? 'connected' : 'disconnected'}`}></span>
          <span>{isConnected ? 'Connected' : 'Disconnected'}</span>
        </div>
      </div>

      {/* Control Panel */}
      <div className="control-panel">
        <div className="control-panel-section">
          <h3>Migration Control</h3>
          <div className="control-buttons">
            {!sessionId && (
              <button
                className="btn btn-primary btn-lg"
                onClick={handleStartMigration}
                disabled={controlsDisabled}
              >
                Start Migration
              </button>
            )}

            {sessionId && availableActions.includes('PAUSE') && (
              <button
                className="btn btn-warning"
                onClick={() => handleControlEvent(MigrationEvents.PAUSE)}
                disabled={controlsDisabled}
              >
                Pause
              </button>
            )}

            {sessionId && availableActions.includes('RESUME') && (
              <button
                className="btn btn-success"
                onClick={() => handleControlEvent(MigrationEvents.RESUME)}
                disabled={controlsDisabled}
              >
                Resume
              </button>
            )}

            {sessionId && availableActions.includes('RETRY') && (
              <button
                className="btn btn-info"
                onClick={() => handleControlEvent(MigrationEvents.RETRY)}
                disabled={controlsDisabled}
              >
                Retry
              </button>
            )}

            {sessionId && availableActions.includes('CANCEL') && (
              <button
                className="btn btn-danger"
                onClick={() => handleControlEvent(MigrationEvents.CANCEL)}
                disabled={controlsDisabled}
              >
                Cancel
              </button>
            )}
          </div>
        </div>

        {/* Metrics */}
        {sessionId && (
          <div className="metrics-panel">
            <div className="metric-card">
              <div className="metric-label">Progress</div>
              <div className="metric-value">{progress.toFixed(1)}%</div>
              <div className="progress">
                <div
                  className="progress-bar"
                  role="progressbar"
                  style={{ width: `${progress}%` }}
                  aria-valuenow={progress}
                  aria-valuemin="0"
                  aria-valuemax="100"
                ></div>
              </div>
            </div>

            <div className="metric-card">
              <div className="metric-label">Quality Score</div>
              <div className="metric-value">{qualityScore.toFixed(1)}%</div>
            </div>

            <div className="metric-card">
              <div className="metric-label">Elapsed Time</div>
              <div className="metric-value">{formatElapsedTime(elapsedTime)}</div>
            </div>

            <div className="metric-card">
              <div className="metric-label">Session ID</div>
              <div className="metric-value-small">{sessionId?.substring(0, 8)}...</div>
            </div>
          </div>
        )}
      </div>

      {/* State Machine Visualization */}
      <PLMMigrationStatechartVisualizer
        currentState={currentState}
        onNavigate={(path) => console.log('Navigate to:', path)}
      />

      {/* Errors Panel */}
      {errors.length > 0 && (
        <div className="errors-panel">
          <h3>Errors</h3>
          <ul>
            {errors.map((error, index) => (
              <li key={index} className="error-item">{error}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Export Panel */}
      {sessionId && (currentState === MigrationStates.COMPLETED || currentState === MigrationStates.FAILED) && (
        <div className="export-panel">
          <h3>Export & Reports</h3>
          <div className="export-buttons">
            <button
              className="btn btn-secondary"
              onClick={handleDownloadHistory}
            >
              Download History (CSV)
            </button>
            <button
              className="btn btn-secondary"
              onClick={() => alert('Report generation coming soon')}
            >
              Generate Report
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default PLMMigrationVisualizerPage;
