import { createHashRouter } from 'react-router-dom';
import { E2ETraceRootLayout } from '../layouts/e2etrace-root-layout.jsx';
import XStateLandingPage from '../pages/xstate-landing/XStateLandingPage.jsx';
import GraphExplorerPage from '../pages/graph-explorer/GraphExplorerPage.jsx';
import { DataQualityDashboard } from '../pages/quality/DataQualityDashboard.jsx';
import { ObservabilityDashboard } from '../pages/observability/ObservabilityDashboard.jsx';
import WorkflowManagerPage from '../pages/workflow-manager/WorkflowManagerPage.jsx';
import WorkflowDetailPage from '../pages/workflow-manager/WorkflowDetailPage.jsx';
import LineageVisualizerPage from '../pages/lineage/LineageVisualizerPage.jsx';
import SelfHealingMonitorPage from '../pages/self-healing/SelfHealingMonitorPage.jsx';
import MultiModalAnalyzerPage from '../pages/multimodal/MultiModalAnalyzerPage.jsx';

const router = createHashRouter([
  {
    path: '/',
    element: <E2ETraceRootLayout />,
    handle: { crumb: 'Home' },
    children: [
      // Default route - XState Interactive Visualizer
      { 
        index: true, 
        element: <XStateLandingPage />, 
        handle: { crumb: 'Interactive State Flow' } 
      },
      
      // Graph Explorer (Graph Features)
      {
        path: 'graph-explorer',
        element: <GraphExplorerPage />,
        handle: { crumb: 'Graph Explorer' },
      },
      
      // Data Quality Dashboard (SODA)
      {
        path: 'data-quality',
        element: <DataQualityDashboard />,
        handle: { crumb: 'Data Quality' },
      },
      
      // Observability Dashboard
      {
        path: 'observability',
        element: <ObservabilityDashboard />,
        handle: { crumb: 'Observability' },
      },
      
      // Workflow Manager - Multi-instance workflow management
      {
        path: 'workflow-manager',
        element: <WorkflowManagerPage />,
        handle: { crumb: 'Workflow Manager' },
      },
      
      // Workflow Detail - Individual workflow instance view
      {
        path: 'workflow/:workflowId',
        element: <WorkflowDetailPage />,
        handle: { crumb: 'Workflow Detail' },
      },
      
      // Data Lineage Visualizer
      {
        path: 'lineage',
        element: <LineageVisualizerPage />,
        handle: { crumb: 'Data Lineage' },
      },
      
      // Self-Healing Orchestration Monitor
      {
        path: 'self-healing',
        element: <SelfHealingMonitorPage />,
        handle: { crumb: 'Self-Healing Monitor' },
      },
      
      // Multi-Modal Data Analyzer
      {
        path: 'multimodal',
        element: <MultiModalAnalyzerPage />,
        handle: { crumb: 'Multi-Modal Analyzer' },
      },
    ],
  },
]);

export default router;
