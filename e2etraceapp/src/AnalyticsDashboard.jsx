import React, { useState, useEffect, useMemo } from 'react';
import { Pie } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
  ArcElement,
} from 'chart.js';

import './AnalyticsDashboard.css';

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
  ArcElement
);

const AnalyticsDashboard = () => {
  // In a real app, this data would come from API calls or context
  // For now, let's simulate fetching or receiving graphData
  const [analyticsData, setAnalyticsData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    // Simulate fetching data that App.jsx would fetch
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        // This simulates fetching the same data App.jsx gets
        // Ideally, you'd have a dedicated analytics endpoint
        const response = await fetch('/api/graph');
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        const rawGraphData = await response.json();

        // Process data for analytics
        const nodes = rawGraphData.nodes || [];
        const edges = rawGraphData.edges || [];

        const nodeLabels = nodes.reduce((acc, node) => {
          const label = node.group || 'Unknown';
          acc[label] = (acc[label] || 0) + 1;
          return acc;
        }, {});

        const edgeTypes = edges.reduce((acc, edge) => {
          const type = edge.label || 'Unknown';
          acc[type] = (acc[type] || 0) + 1;
          return acc;
        }, {});

        setAnalyticsData({
          totalNodes: nodes.length,
          totalEdges: edges.length,
          nodeLabelDistribution: nodeLabels,
          edgeTypeDistribution: edgeTypes,
        });
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const nodeLabelChartData = useMemo(() => {
    if (!analyticsData) return null;
    return {
      labels: Object.keys(analyticsData.nodeLabelDistribution),
      datasets: [{
        label: 'Nodes by Label',
        data: Object.values(analyticsData.nodeLabelDistribution),
        backgroundColor: ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40'],
      }],
    };
  }, [analyticsData]);

  if (loading) return <div className="dashboard-loading">Loading analytics...</div>;
  if (error) return <div className="dashboard-error"><p>Error loading analytics: {error}</p></div>;
  if (!analyticsData) return <div className="dashboard-nodata"><p>No analytics data available.</p></div>;

  return (
    <div className="analytics-dashboard-container">
      <h1 className="dashboard-title">Graph Analytics Dashboard</h1>
      <div className="kpi-grid">
        <div className="card kpi-card"> {/* Reverted from Fluent UI Card */}
          <div className="card-header"><h3>Total Nodes</h3></div>
          <div className="card-body"><p className="kpi-value">{analyticsData.totalNodes}</p></div>
        </div>
        <div className="card kpi-card"> {/* Reverted from Fluent UI Card */}
          <div className="card-header"><h3>Total Edges</h3></div>
          <div className="card-body"><p className="kpi-value">{analyticsData.totalEdges}</p></div>
        </div>
      </div>

      <div className="charts-grid">
        <div className="card chart-card"> {/* Reverted from Fluent UI Card */}
          <div className="card-header"><h3>Node Distribution by Label</h3></div>
          <div className="card-body">
            {nodeLabelChartData && <Pie data={nodeLabelChartData} />}
          </div>
        </div>
        {/* Add more charts here, e.g., for edge types */}
      </div>
    </div>
  );
};

export default AnalyticsDashboard;