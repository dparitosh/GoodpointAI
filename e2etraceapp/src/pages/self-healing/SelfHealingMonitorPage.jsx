/**
 * Self-Healing Orchestration Monitor
 * ======================================
 * 
 * Real-time monitoring dashboard for self-healing orchestration with:
 * - Live task execution status
 * - Circuit breaker status
 * - Retry metrics and trends
 * - Dead letter queue management
 * - Error classification analytics
 * - Performance metrics
 * 
 * Features:
 * - WebSocket real-time updates
 * - Execute test tasks
 * - Manage DLQ messages
 * - Circuit breaker controls
 */

import React, { useState, useEffect, useRef } from 'react';
import './SelfHealingMonitorPage.css';

const SelfHealingMonitorPage = () => {
  const [metrics, setMetrics] = useState({
    total_tasks: 0,
    successful_tasks: 0,
    failed_tasks: 0,
    retried_tasks: 0,
    circuit_breaker_trips: 0,
    alternative_routes_used: 0,
    dlq_messages: 0,
    active_tasks: 0,
    dlq_size: 0,
    circuit_breakers: 0
  });

  const [circuitBreakers, setCircuitBreakers] = useState([]);
  const [dlqMessages, setDlqMessages] = useState([]);
  const [taskResults, setTaskResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);
  const wsRef = useRef(null);

  // Connect to WebSocket for real-time metrics
  useEffect(() => {
    const connectWebSocket = () => {
      const ws = new WebSocket('ws://localhost:8000/api/self-healing/ws/monitor');

      ws.onopen = () => {

      };

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        setMetrics(data);
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        setWsConnected(false);
      };

      ws.onclose = () => {
        console.log('WebSocket disconnected');
        setWsConnected(false);
        // Reconnect after 5 seconds
        setTimeout(connectWebSocket, 5000);
      };

      wsRef.current = ws;
    };

    connectWebSocket();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  // Load circuit breakers
  const loadCircuitBreakers = async () => {
    try {
      const response = await fetch('/api/self-healing/circuit-breakers');
      const data = await response.json();
      setCircuitBreakers(data);
    } catch (error) {
      console.error('Error loading circuit breakers:', error);
    }
  };

  // Load DLQ messages
  const loadDLQ = async () => {
    try {
      const response = await fetch('/api/self-healing/dead-letter-queue');
      const data = await response.json();
      setDlqMessages(data);
    } catch (error) {
      console.error('Error loading DLQ:', error);
    }
  };

  // Execute test task
  const executeTestTask = async (simulateFailure = false) => {
    setLoading(true);
    try {
      const execution = {
        task_id: `task_${Date.now()}`,
        workflow_id: `wf_${Date.now()}`,
        route: {
          id: 'primary_route',
          name: 'Primary Database',
          endpoint: '/api/data',
          successRate: 0.9,
          averageLatency: 100,
          priority: 1
        },
        alternative_routes: [
          {
            id: 'backup_route_1',
            name: 'Backup Database 1',
            endpoint: 'http://localhost:8001/api/data',
            successRate: 0.85,
            averageLatency: 150,
            priority: 2
          },
          {
            id: 'backup_route_2',
            name: 'Backup Database 2',
            endpoint: 'http://localhost:8002/api/data',
            successRate: 0.8,
            averageLatency: 200,
            priority: 3
          }
        ],
        max_retries: 5,
        validation_enabled: true,
        metadata: {
          source: 'test_monitor',
          timestamp: new Date().toISOString()
        }
      };

      const response = await fetch(
        `/api/self-healing/execute?simulate_failure=${simulateFailure}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(execution)
        }
      );

      const result = await response.json();
      setTaskResults(prev => [result, ...prev].slice(0, 10));
      
      // Reload circuit breakers and DLQ
      await loadCircuitBreakers();
      await loadDLQ();
    } catch (error) {
      console.error('Error executing task:', error);
      alert('Failed to execute task');
    } finally {
      setLoading(false);
    }
  };

  // Retry DLQ message
  const retryDLQMessage = async (taskId) => {
    try {
      await fetch(`/api/self-healing/dead-letter-queue/${taskId}/retry`, {
        method: 'POST'
      });
      await loadDLQ();
      alert(`Task ${taskId} removed from DLQ and ready for retry`);
    } catch (error) {
      console.error('Error retrying DLQ message:', error);
      alert('Failed to retry task');
    }
  };

  // Remove DLQ message
  const removeDLQMessage = async (taskId) => {
    if (!confirm(`Are you sure you want to remove task ${taskId} from DLQ?`)) {
      return;
    }

    try {
      await fetch(`/api/self-healing/dead-letter-queue/${taskId}`, {
        method: 'DELETE'
      });
      await loadDLQ();
    } catch (error) {
      console.error('Error removing DLQ message:', error);
      alert('Failed to remove task');
    }
  };

  // Load data on mount
  useEffect(() => {
    loadCircuitBreakers();
    loadDLQ();
  }, []);

  // Calculate success rate
  const successRate = metrics.total_tasks > 0
    ? ((metrics.successful_tasks / metrics.total_tasks) * 100).toFixed(1)
    : 0;

  const retryRate = metrics.total_tasks > 0
    ? ((metrics.retried_tasks / metrics.total_tasks) * 100).toFixed(1)
    : 0;

  return (
    <div className="self-healing-monitor-page">
      <div className="monitor-header">
        <h1>⟲ Self-Healing Orchestration Monitor</h1>
        <div className="ws-status">
          <span className={`ws-indicator ${wsConnected ? 'connected' : 'disconnected'}`}>
            {wsConnected ? '● Live' : '● Disconnected'}
          </span>
        </div>
      </div>

      {/* Metrics Dashboard */}
      <div className="metrics-dashboard">
        <div className="metric-card">
          <div className="metric-icon">▣</div>
          <div className="metric-value">{metrics.total_tasks}</div>
          <div className="metric-label">Total Tasks</div>
        </div>

        <div className="metric-card success">
          <div className="metric-icon">✓</div>
          <div className="metric-value">{metrics.successful_tasks}</div>
          <div className="metric-label">Successful ({successRate}%)</div>
        </div>

        <div className="metric-card warning">
          <div className="metric-icon">⟲</div>
          <div className="metric-value">{metrics.retried_tasks}</div>
          <div className="metric-label">Retried ({retryRate}%)</div>
        </div>

        <div className="metric-card danger">
          <div className="metric-icon">✗</div>
          <div className="metric-value">{metrics.failed_tasks}</div>
          <div className="metric-label">Failed</div>
        </div>

        <div className="metric-card info">
          <div className="metric-icon">⇄</div>
          <div className="metric-value">{metrics.alternative_routes_used}</div>
          <div className="metric-label">Alt Routes Used</div>
        </div>

        <div className="metric-card alert">
          <div className="metric-icon">⊗</div>
          <div className="metric-value">{metrics.circuit_breaker_trips}</div>
          <div className="metric-label">Circuit Breaker Trips</div>
        </div>

        <div className="metric-card">
          <div className="metric-icon">⊞</div>
          <div className="metric-value">{metrics.dlq_size}</div>
          <div className="metric-label">DLQ Messages</div>
        </div>

        <div className="metric-card active">
          <div className="metric-icon">⚙</div>
          <div className="metric-value">{metrics.active_tasks}</div>
          <div className="metric-label">Active Tasks</div>
        </div>
      </div>

      {/* Test Controls */}
      <div className="test-controls">
        <h2>Test Execution</h2>
        <div className="control-buttons">
          <button 
            onClick={() => executeTestTask(false)} 
            disabled={loading}
            className="btn-success"
          >
            ✓ Execute Success Task
          </button>
          <button 
            onClick={() => executeTestTask(true)} 
            disabled={loading}
            className="btn-warning"
          >
            ! Execute Failing Task (Test Retry)
          </button>
          <button 
            onClick={loadCircuitBreakers}
            className="btn-info"
          >
            ⟲ Refresh Circuit Breakers
          </button>
          <button 
            onClick={loadDLQ}
            className="btn-info"
          >
            ⊞ Refresh DLQ
          </button>
        </div>
      </div>

      {/* Recent Task Results */}
      <div className="task-results-section">
        <h2>Recent Task Results</h2>
        {taskResults.length === 0 ? (
          <div className="empty-state">
            <p>No task results yet. Execute a test task to see results.</p>
          </div>
        ) : (
          <div className="task-results-list">
            {taskResults.map((result, index) => (
              <div key={index} className={`task-result-card status-${result.status}`}>
                <div className="result-header">
                  <span className="result-task-id">{result.task_id}</span>
                  <span className={`result-status badge-${result.status}`}>
                    {result.status}
                  </span>
                </div>
                <div className="result-details">
                  <div><strong>Route:</strong> {result.route_used}</div>
                  <div><strong>Retries:</strong> {result.retry_count}</div>
                  <div><strong>Duration:</strong> {result.duration_ms}ms</div>
                  {result.error && (
                    <div className="result-error">
                      <strong>Error:</strong> {result.error}
                    </div>
                  )}
                </div>
                {result.error_history && result.error_history.length > 0 && (
                  <div className="result-error-history">
                    <strong>Error History ({result.error_history.length}):</strong>
                    <div className="error-history-list">
                      {result.error_history.slice(0, 3).map((err, i) => (
                        <div key={i} className="error-history-item">
                          Attempt {err.attempt}: {err.error}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="monitor-grid">
        {/* Circuit Breakers */}
        <div className="monitor-section">
          <h2>⊙ Circuit Breakers</h2>
          {circuitBreakers.length === 0 ? (
            <div className="empty-state">
              <p>No circuit breakers active</p>
            </div>
          ) : (
            <div className="circuit-breakers-list">
              {circuitBreakers.map((cb, index) => (
                <div key={index} className={`circuit-breaker-card state-${cb.state}`}>
                  <div className="cb-header">
                    <span className="cb-route">{cb.route_id}</span>
                    <span className={`cb-state badge-${cb.state}`}>
                      {cb.state.toUpperCase()}
                    </span>
                  </div>
                  <div className="cb-metrics">
                    <div className="cb-metric">
                      <span className="cb-metric-label">Failures:</span>
                      <span className="cb-metric-value">{cb.failure_count}</span>
                    </div>
                    <div className="cb-metric">
                      <span className="cb-metric-label">Successes:</span>
                      <span className="cb-metric-value">{cb.success_count}</span>
                    </div>
                  </div>
                  {cb.last_failure && (
                    <div className="cb-last-failure">
                      Last Failure: {new Date(cb.last_failure).toLocaleString()}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Dead Letter Queue */}
        <div className="monitor-section">
          <h2>⊞ Dead Letter Queue</h2>
          {dlqMessages.length === 0 ? (
            <div className="empty-state">
              <p>No messages in DLQ</p>
            </div>
          ) : (
            <div className="dlq-messages-list">
              {dlqMessages.map((msg, index) => (
                <div key={index} className="dlq-message-card">
                  <div className="dlq-header">
                    <span className="dlq-task-id">{msg.task_id}</span>
                    <span className="dlq-workflow-id">{msg.workflow_id}</span>
                  </div>
                  <div className="dlq-details">
                    <div><strong>Route:</strong> {msg.original_route}</div>
                    <div><strong>Retries:</strong> {msg.retry_count}</div>
                    <div className="dlq-error">
                      <strong>Error:</strong> {msg.error}
                    </div>
                    <div className="dlq-timestamp">
                      {new Date(msg.timestamp).toLocaleString()}
                    </div>
                  </div>
                  <div className="dlq-actions">
                    <button 
                      onClick={() => retryDLQMessage(msg.task_id)}
                      className="btn-retry"
                    >
                      ⟲ Retry
                    </button>
                    <button 
                      onClick={() => removeDLQMessage(msg.task_id)}
                      className="btn-remove"
                    >
                      ✗ Remove
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Info Section */}
      <div className="info-section">
        <h3>About Self-Healing Orchestration</h3>
        <div className="info-grid">
          <div className="info-card">
            <h4>⟲ Exponential Backoff</h4>
            <p>Automatic retry with increasing delays (1s → 2s → 4s → 8s → 16s) plus jitter to prevent thundering herd</p>
          </div>
          <div className="info-card">
            <h4>⊙ Circuit Breaker</h4>
            <p>Trips after 5 consecutive failures, opens for 60s, then tries again (half-open state)</p>
          </div>
          <div className="info-card">
            <h4>⇄ Alternative Routing</h4>
            <p>Automatically switches to backup routes when primary fails or circuit breaker trips</p>
          </div>
          <div className="info-card">
            <h4>✓ Validation Checkpoints</h4>
            <p>Data quality validation after execution to catch issues early</p>
          </div>
          <div className="info-card">
            <h4>⊞ Dead Letter Queue</h4>
            <p>Failed tasks after all retries go to DLQ for manual intervention</p>
          </div>
          <div className="info-card">
            <h4>⊚ Lineage Tracking</h4>
            <p>Integrated with Data Lineage for failure root cause analysis</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SelfHealingMonitorPage;
