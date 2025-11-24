import { createHashRouter } from 'react-router-dom';
import { E2ETraceRootLayout } from '../layouts/e2etrace-root-layout.jsx';
import DataProcessingHubPage from '../pages/processing/DataProcessingHubPage.jsx';
import PLMMigrationVisualizerPage from '../pages/plm/PLMMigrationVisualizerPage.jsx';
import GraphExplorerPage from '../pages/graph-explorer/GraphExplorerPage.jsx';
import { DataQualityDashboard } from '../pages/quality/DataQualityDashboard.jsx';
import { ObservabilityDashboard } from '../pages/observability/ObservabilityDashboard.jsx';

const router = createHashRouter([
  {
    path: '/',
    element: <E2ETraceRootLayout />,
    handle: { crumb: 'Home' },
    children: [
      // Default route - Data Processing Hub
      { 
        index: true, 
        element: <DataProcessingHubPage />, 
        handle: { crumb: 'Data Processing Hub' } 
      },
      
      // Data Processing
      {
        path: 'processing',
        element: <DataProcessingHubPage />,
        handle: { crumb: 'Data Processing Hub' },
      },
      
      // PLM Migration Visualizer (T-04)
      {
        path: 'plm-migration-visualizer',
        element: <PLMMigrationVisualizerPage />,
        handle: { crumb: 'PLM Migration Visualizer' },
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
    ],
  },
]);

export default router;
