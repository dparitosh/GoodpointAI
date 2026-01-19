/**
 * Application Routes - GraphTrace Enterprise
 * Clean routing structure with TCS corporate pages
 */
import { Navigate, Outlet, createHashRouter } from 'react-router-dom';
import { E2ETraceRootLayout } from '../layouts/e2etrace-root-layout.jsx';
import LandingPage from '../pages/landing/LandingPage.jsx';
import MigrationPage from '../pages/migration/MigrationPage.jsx';
import GraphExplorerPage from '../pages/graph-explorer/GraphExplorerPage.jsx';
import { ObservabilityDashboard } from '../pages/observability/ObservabilityDashboard.jsx';
import WorkflowDetailPage from '../pages/workflow-manager/WorkflowDetailPage.jsx';
import WorkflowManagerPage from '../pages/workflow-manager/WorkflowManagerPage.jsx';
import LineageVisualizerPage from '../pages/lineage/LineageVisualizerPage.jsx';
import SelfHealingMonitorPage from '../pages/self-healing/SelfHealingMonitorPage.jsx';
import MultiModalAnalyzerPage from '../pages/multimodal/MultiModalAnalyzerPage.jsx';
import OpenApiDocsPage from '../pages/api-docs/OpenApiDocsPage.jsx';
import EnterpriseAnalyticsHub from '../pages/analytics/EnterpriseAnalyticsHub.jsx';
import ConversationalSearchPage from '../pages/search/ConversationalSearchPage.jsx';
import E2ETracePropertyPalette from '../pages/settings/settings/e2etrace-property-palette.jsx';
import AdminSettingsPage from '../pages/settings/AdminSettingsPage.jsx';
import RuleEnginePage from '../pages/rule-engine/RuleEnginePage.jsx';
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
        element: <Navigate to="/" replace />,
        handle: { crumb: 'nav.overview' }
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


      // Data Mapping - now consolidated into Migration Wizard (Step 3)
      {
        path: 'data-mapping',
        element: <Navigate to="/migration" replace />,
        handle: { crumb: 'nav.dataMapping' },
      },



      // Processing Hub - Redirects to Analytics (SODA merged)
      {
        path: 'processing',
        element: <Navigate to="/analytics?tab=quality-reports" replace />,
        handle: { crumb: 'nav.analytics' },
      },

      // Settings
      {
        path: 'settings',
        element: <E2ETracePropertyPalette />,
        handle: { crumb: 'nav.settings' },
      },
      
      // Settings/Admin alias (for nested URL structure)
      {
        path: 'settings/admin',
        element: <AdminSettingsPage />,
        handle: { crumb: 'nav.adminSettings' },
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

      // Legacy alias (clean-env compatibility)
      {
        path: 'graphexplorer',
        element: <Navigate to="/graph-explorer" replace />,
      },

      // Reports & Dashboards - Merged into Enterprise Analytics Hub
      {
        path: 'reporting',
        element: <Navigate to="/analytics?tab=quality-reports" replace />,
        handle: { crumb: 'nav.analytics' },
      },
      
      // Data Quality Dashboard (SODA) - Now in Analytics
      {
        path: 'data-quality',
        element: <Navigate to="/analytics?tab=quality-reports" replace />,
        handle: { crumb: 'nav.analytics' },
      },

      // Legacy alias
      {
        path: 'dataquality',
        element: <Navigate to="/analytics?tab=quality-reports" replace />,
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

      // Analytics Dashboard - Enterprise Hub with GraphQL Query Builder
      {
        path: 'analytics',
        element: <EnterpriseAnalyticsHub />,
        handle: { crumb: 'nav.analytics' },
      },
      
      // Workflow Manager - redirects to Analytics
      {
        path: 'workflow-manager',
        element: <WorkflowManagerPage />,
        handle: { crumb: 'nav.workflowManagement' },
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

      // PLM Rule Engine - Data Quality & ETL Rules
      {
        path: 'rule-engine',
        element: <RuleEnginePage />,
        handle: { crumb: 'nav.ruleEngine' },
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
