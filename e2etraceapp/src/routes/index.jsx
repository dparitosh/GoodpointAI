/**
 * Application Routes - GraphTrace Enterprise
 * Clean routing structure with TCS corporate pages
 */
import { Navigate, Outlet, createHashRouter } from 'react-router-dom';
import { E2ETraceRootLayout } from '../layouts/e2etrace-root-layout.jsx';
import E2ETraceMainDashboard from '../pages/dashboard/e2etrace-main-dashboard.jsx';
import LandingPage from '../pages/landing/LandingPage.jsx';
import MigrationPage from '../pages/migration/MigrationPage.jsx';
import GraphExplorerPage from '../pages/graph-explorer/GraphExplorerPage.jsx';
import { ObservabilityDashboard } from '../pages/observability/ObservabilityDashboard.jsx';
import WorkflowDetailPage from '../pages/workflow-manager/WorkflowDetailPage.jsx';
import LineageVisualizerPage from '../pages/lineage/LineageVisualizerPage.jsx';
import SelfHealingMonitorPage from '../pages/self-healing/SelfHealingMonitorPage.jsx';
import MultiModalAnalyzerPage from '../pages/multimodal/MultiModalAnalyzerPage.jsx';
import FileBatchProcessorPage from '../pages/batch-processor/FileBatchProcessorPage.jsx';
import OpenApiDocsPage from '../pages/api-docs/OpenApiDocsPage.jsx';
import EnterpriseAnalyticsHub from '../pages/analytics/EnterpriseAnalyticsHub.jsx';
import DQScanDashboard from '../pages/dq-dashboard/DQScanDashboard.jsx';
import ConversationalSearchPage from '../pages/search/ConversationalSearchPage.jsx';
import E2ETracePropertyPalette from '../pages/settings/settings/e2etrace-property-palette.jsx';
import AdminSettingsPage from '../pages/settings/AdminSettingsPage.jsx';
import RuleEnginePage from '../pages/rule-engine/RuleEnginePage.jsx';
import DataDiscoveryPage from '../pages/data-discovery/DataDiscoveryPage.jsx';
import ReportingHubPage from '../pages/reporting-hub/ReportingHubPage.jsx';
import RouteErrorPage from '../pages/errors/RouteErrorPage.jsx';
import NotFoundPage from '../pages/errors/NotFoundPage.jsx';

const router = createHashRouter([
  {
    path: '/',
    element: <E2ETraceRootLayout />,
    errorElement: <RouteErrorPage />,
    handle: { crumb: 'nav.home' },
    children: [
      // Default route - Main Dashboard with Graph Visualization
      {
        index: true,
        element: <E2ETraceMainDashboard />,
        handle: { crumb: 'nav.overview' }
      },

      // Landing Page - Platform overview (alternative entry)
      {
        path: 'landing',
        element: <LandingPage />,
        handle: { crumb: 'nav.landing' }
      },

      // Conversational Search - AI-powered search across all data sources
      {
        path: 'search',
        element: <ConversationalSearchPage />,
        handle: { crumb: 'nav.search' },
      },

      // PLM Data Migration Wizard - Primary workflow entry point
      {
        path: 'migration',
        element: <MigrationPage />,
        handle: { crumb: 'nav.migration' },
      },

      // Settings
      {
        path: 'settings',
        element: <E2ETracePropertyPalette />,
        handle: { crumb: 'nav.settings' },
      },
      
      // Admin Configuration Center
      {
        path: 'admin',
        element: <AdminSettingsPage />,
        handle: { crumb: 'nav.adminSettings' },
      },
      
      // Graph Explorer (Graph Features)
      {
        path: 'graph-explorer',
        element: <Outlet />,
        handle: { crumb: 'nav.graphExplorer' },
        children: [
          {
            index: true,
            element: <GraphExplorerPage />,
          },
          {
            path: 'workflow/:workflowId',
            element: <WorkflowDetailPage />,
            handle: { crumb: 'nav.workflowDetail' },
          },
        ],
      },

      // Observability Dashboard
      {
        path: 'observability',
        element: <ObservabilityDashboard />,
        handle: { crumb: 'nav.observability' },
      },

      // Analytics Dashboard - Enterprise Hub with GraphQL Query Builder
      {
        path: 'analytics',
        element: <EnterpriseAnalyticsHub />,
        handle: { crumb: 'nav.analytics' },
      },

      // Data Quality Scan Dashboard
      {
        path: 'dq-dashboard',
        element: <DQScanDashboard />,
        handle: { crumb: 'Data Quality Dashboard' },
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

      // Batch File Processor - large-scale parallel ingestion
      {
        path: 'batch-processor',
        element: <FileBatchProcessorPage />,
        handle: { crumb: 'nav.batchProcessor' },
      },

      // PLM Rule Engine - Data Quality & ETL Rules
      {
        path: 'rule-engine',
        element: <RuleEnginePage />,
        handle: { crumb: 'nav.ruleEngine' },
      },

      // Data Discovery - profile and catalog folder data sources via MCP
      {
        path: 'data-discovery',
        element: <DataDiscoveryPage />,
        handle: { crumb: 'Data Discovery' },
      },

      // Reporting Hub - unified view of all saved reports
      {
        path: 'reporting-hub',
        element: <ReportingHubPage />,
        handle: { crumb: 'Reporting Hub' },
      },

      // API Docs (OpenAPI/Swagger)
      {
        path: 'api-docs',
        element: <OpenApiDocsPage />,
        handle: { crumb: 'nav.apiDocs' },
      },

      // ── Legacy redirects (one per target) ──
      // Keep old bookmarks working without duplicating destinations.
      { path: 'data-mapping',    element: <Navigate to="/migration" replace /> },
      { path: 'processing',      element: <Navigate to="/analytics?tab=quality-reports" replace /> },
      { path: 'reporting',       element: <Navigate to="/analytics?tab=quality-reports" replace /> },
      { path: 'data-quality',    element: <Navigate to="/analytics?tab=quality-reports" replace /> },
      { path: 'dataquality',     element: <Navigate to="/analytics?tab=quality-reports" replace /> },
      { path: 'graphexplorer',   element: <Navigate to="/graph-explorer" replace /> },
      { path: 'monitoring',      element: <Navigate to="/observability" replace /> },
      { path: 'workflow-manager', element: <Navigate to="/analytics" replace /> },
      { path: 'settings/admin',  element: <Navigate to="/admin" replace /> },

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
