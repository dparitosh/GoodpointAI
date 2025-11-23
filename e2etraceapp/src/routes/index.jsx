import { createHashRouter } from 'react-router-dom';
import { E2ETraceRootLayout } from '../layouts/e2etrace-root-layout.jsx';
import DataProcessingHubPage from '../pages/processing/DataProcessingHubPage.jsx';
import PLMMigrationVisualizerPage from '../pages/plm/PLMMigrationVisualizerPage.jsx';

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
    ],
  },
]);

export default router;
