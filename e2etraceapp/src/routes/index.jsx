import { createHashRouter } from 'react-router-dom';
import { E2ETraceRootLayout } from '../layouts/e2etrace-root-layout.jsx';
import { E2ETraceAnalyticsPage } from '../pages/analytics/analytics/e2etrace-analytics-page.jsx';
import { E2ETraceETLOverviewPage } from '../pages/etl/etl/e2etrace-etl-overview-page.jsx';
import E2ETraceMainDashboard from '../pages/dashboard/e2etrace-main-dashboard.jsx';
import E2ETracePropertyPalette from '../pages/settings/settings/e2etrace-property-palette.jsx';
import { E2ETraceNiFiMain } from '../pages/dashboard/components/e2etrace-nifi-main.jsx';
import { E2ETraceQuickActions } from '../pages/dashboard/components/e2etrace-quick-actions.jsx';

const router = createHashRouter([
  {
    path: '/',
    element: <E2ETraceRootLayout />,
    handle: { crumb: 'Home' },
    children: [
      { index: true, element: <E2ETraceAnalyticsPage /> },
      {
        path: 'graphexplorer',
        element: <E2ETraceMainDashboard />,
        handle: { crumb: 'Graph Explorer' },
      },
      {
        path: 'quickactions',
        element: <E2ETraceQuickActions/>,
        handle: { crumb: 'Quick Actions' },
      },
       {
        path: 'nifi',
        element: <E2ETraceNiFiMain/>,
        handle: { crumb: 'NiFi' },
      },
      {
        path: 'etl',
        element: <E2ETraceETLOverviewPage />,
        handle: { crumb: 'ETL Overview' },
      },
      {
        path: 'settings',
        element: <E2ETracePropertyPalette />,
        handle: { crumb: 'Settings' },
      },
    ],
  },
]);

export default router;
