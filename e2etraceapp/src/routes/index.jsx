import { Navigate, createHashRouter } from 'react-router-dom';
import { E2ETraceRootLayout } from '../layouts/e2etrace-root-layout.jsx';
import XStateLandingPage from '../pages/xstate-landing/XStateLandingPage.jsx';
import LandingPage from '../pages/landing/LandingPage.jsx';
import GraphExplorerPage from '../pages/graph-explorer/GraphExplorerPage.jsx';
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
import E2ETracePropertyPalette from '../pages/settings/settings/e2etrace-property-palette.jsx';
import DataProcessingHubPage from '../pages/processing/DataProcessingHubPage.jsx';
import RouteErrorPage from '../pages/errors/RouteErrorPage.jsx';
import NotFoundPage from '../pages/errors/NotFoundPage.jsx';

const router = createHashRouter([
  {
    path: '/',
    element: <E2ETraceRootLayout />,
    errorElement: <RouteErrorPage />,
    handle: { crumb: 'nav.home' },
    children: [
      // Default route - Hero / Platform overview
      {
        index: true,
        element: <LandingPage />,
        handle: { crumb: 'nav.overview' }
      },

      // Interactive State Flow (XState)
      {
        path: 'interactive-state-flow',
        element: <XStateLandingPage />,
        handle: { crumb: 'nav.interactiveStateFlow' }
      },

      // Data Configuration (used by Landing "Get Started" and WorkflowProgress)
      {
        path: 'data-config',
        element: <DataConfigPage />,
        handle: { crumb: 'nav.dataConfig' },
      },

      // ECharts Spreadsheet (used by WorkflowProgress)
      {
        path: 'spreadsheet',
        element: <EChartsSpreadsheetPage />,
        handle: { crumb: 'nav.spreadsheet' },
      },

      // Data Processing Hub
      {
        path: 'processing',
        element: <DataProcessingHubPage />,
        handle: { crumb: 'nav.dataProcessingHub' },
      },

      // Settings
      {
        path: 'settings',
        element: <E2ETracePropertyPalette />,
        handle: { crumb: 'nav.settings' },
      },
      
      // Graph Explorer (Graph Features)
      {
        path: 'graph-explorer',
        element: <GraphExplorerPage />,
        handle: { crumb: 'nav.graphExplorer' },
      },

      // Legacy alias (clean-env compatibility)
      {
        path: 'graphexplorer',
        element: <Navigate to="/graph-explorer" replace />,
      },

      // Reports & Dashboards (clean-env compatibility)
      {
        path: 'reporting',
        element: <ReportingPage />,
        handle: { crumb: 'nav.reporting' },
      },
      
      // Data Quality Dashboard (SODA)
      {
        path: 'data-quality',
        element: <DataQualityDashboard />,
        handle: { crumb: 'nav.dataQuality' },
      },

      // Legacy alias
      {
        path: 'dataquality',
        element: <Navigate to="/data-quality" replace />,
      },
      
      // Observability Dashboard
      {
        path: 'observability',
        element: <ObservabilityDashboard />,
        handle: { crumb: 'nav.observability' },
      },

      // Legacy alias (older UI links)
      {
        path: 'monitoring',
        element: <Navigate to="/observability" replace />,
      },

      // Analytics Dashboard
      {
        path: 'analytics',
        element: <E2ETraceAnalyticsPage />,
        handle: { crumb: 'nav.analytics' },
      },
      
      // Workflow Manager - Multi-instance workflow management
      {
        path: 'workflow-manager',
        element: <WorkflowManagerPage />,
        handle: { crumb: 'nav.workflowManager' },
      },
      
      // Workflow Detail - Individual workflow instance view
      {
        path: 'workflow/:workflowId',
        element: <WorkflowDetailPage />,
        handle: { crumb: 'nav.workflowDetail' },
      },
      
      // Data Lineage Visualizer
      {
        path: 'lineage',
        element: <LineageVisualizerPage />,
        handle: { crumb: 'nav.dataLineage' },
      },
      
      // Self-Healing Orchestration Monitor
      {
        path: 'self-healing',
        element: <SelfHealingMonitorPage />,
        handle: { crumb: 'nav.selfHealingMonitor' },
      },
      
      // Multi-Modal Data Analyzer
      {
        path: 'multimodal',
        element: <MultiModalAnalyzerPage />,
        handle: { crumb: 'nav.multiModalAnalyzer' },
      },

      // API Docs (OpenAPI/Swagger)
      {
        path: 'api-docs',
        element: <OpenApiDocsPage />,
        handle: { crumb: 'nav.apiDocs' },
      },

      // Catch-all (prevents React Router default 404 overlay)
      {
        path: '*',
        element: <NotFoundPage />,
        handle: { crumb: 'errors.notFound' },
      },
    ],
  },
]);

export default router;
