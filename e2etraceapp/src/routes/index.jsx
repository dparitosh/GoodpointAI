import { createHashRouter } from 'react-router-dom';
import { E2ETraceRootLayout } from '../layouts/e2etrace-root-layout.jsx';
import XStateLandingPage from '../pages/xstate-landing/XStateLandingPage.jsx';
import LandingPage from '../pages/landing/LandingPage.jsx';
import GraphExplorerPage from '../pages/graph-explorer/GraphExplorerPage.jsx';
import E2ETraceMainDashboard from '../pages/dashboard/e2etrace-main-dashboard.jsx';
import { DataQualityDashboard } from '../pages/quality/DataQualityDashboard.jsx';
import { ObservabilityDashboard } from '../pages/observability/ObservabilityDashboard.jsx';
import WorkflowManagerPage from '../pages/workflow-manager/WorkflowManagerPage.jsx';
import WorkflowDetailPage from '../pages/workflow-manager/WorkflowDetailPage.jsx';
import LineageVisualizerPage from '../pages/lineage/LineageVisualizerPage.jsx';
import SelfHealingMonitorPage from '../pages/self-healing/SelfHealingMonitorPage.jsx';
import MultiModalAnalyzerPage from '../pages/multimodal/MultiModalAnalyzerPage.jsx';
import OpenApiDocsPage from '../pages/api-docs/OpenApiDocsPage.jsx';
import { E2ETraceAnalyticsPage } from '../pages/analytics/analytics/e2etrace-analytics-page.jsx';
import ReportingPage from '../pages/reporting/ReportingPage.jsx';
import DataConfigPage from '../pages/data-config/DataConfigPage.jsx';
import EChartsSpreadsheetPage from '../pages/spreadsheet/EChartsSpreadsheetPage.jsx';
import RouteErrorPage from '../pages/errors/RouteErrorPage.jsx';
import NotFoundPage from '../pages/errors/NotFoundPage.jsx';

const router = createHashRouter([
  {
    path: '/',
    element: <E2ETraceRootLayout />,
    errorElement: <RouteErrorPage />,
    handle: { crumb: 'Home' },
    children: [
      // Default route - Hero / Platform overview
      {
        index: true,
        element: <LandingPage />,
        handle: { crumb: 'Home' }
      },

      // Interactive State Flow (XState)
      {
        path: 'interactive-state-flow',
        element: <XStateLandingPage />,
        handle: { crumb: 'Interactive State Flow' }
      },

      // Data Configuration (used by Landing "Get Started" and WorkflowProgress)
      {
        path: 'data-config',
        element: <DataConfigPage />,
        handle: { crumb: 'Data Configuration' },
      },

      // ECharts Spreadsheet (used by WorkflowProgress)
      {
        path: 'spreadsheet',
        element: <EChartsSpreadsheetPage />,
        handle: { crumb: 'Spreadsheet' },
      },
      
      // Graph Explorer (Graph Features)
      {
        path: 'graph-explorer',
        element: <GraphExplorerPage />,
        handle: { crumb: 'Graph Explorer' },
      },

      // Legacy alias (clean-env compatibility)
      {
        path: 'graphexplorer',
        element: <E2ETraceMainDashboard />,
        handle: { crumb: 'Graph Explorer' },
      },

      // Reports & Dashboards (clean-env compatibility)
      {
        path: 'reporting',
        element: <ReportingPage />,
        handle: { crumb: 'Reports & Dashboards' },
      },
      
      // Data Quality Dashboard (SODA)
      {
        path: 'data-quality',
        element: <DataQualityDashboard />,
        handle: { crumb: 'Data Quality' },
      },

      // Legacy alias
      {
        path: 'dataquality',
        element: <DataQualityDashboard />,
        handle: { crumb: 'Data Quality' },
      },
      
      // Observability Dashboard
      {
        path: 'observability',
        element: <ObservabilityDashboard />,
        handle: { crumb: 'Observability' },
      },

      // Analytics Dashboard
      {
        path: 'analytics',
        element: <E2ETraceAnalyticsPage />,
        handle: { crumb: 'Analytics' },
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

      // API Docs (OpenAPI/Swagger)
      {
        path: 'api-docs',
        element: <OpenApiDocsPage />,
        handle: { crumb: 'API Docs' },
      },

      // Catch-all (prevents React Router default 404 overlay)
      {
        path: '*',
        element: <NotFoundPage />,
        handle: { crumb: 'Not Found' },
      },
    ],
  },
]);

export default router;
