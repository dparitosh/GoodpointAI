import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import React from 'react';
import { createHashRouter, RouterProvider } from 'react-router-dom';
import { E2ETraceRootLayout } from './components/e2etrace-root-layout.jsx';

import './components/e2etrace-breadcrumbs.css';
// Component & Feature Styles
import './components/e2etrace-data-table.css';
// Context Providers
import { E2ETraceThemeProvider } from './contexts/e2etrace-theme-context.jsx';
import { E2ETraceLayoutProvider } from './contexts/e2etrace-layout-context.jsx';
import { GraphFilterProvider } from './contexts/e2etrace-graph-filter-context.jsx';
import './components/e2etrace-sidebar.css';

// Page/Feature Components
import { E2ETraceAnalyticsPage } from './features/analytics/e2etrace-analytics-page.jsx';
import E2ETraceETLOverviewPage from './features/etl/e2etrace-etl-overview-page.jsx'; // Import the new ETL Page
import E2ETraceMainDashboard from './features/dashboard/e2etrace-main-dashboard.jsx';
import E2ETracePropertyPalette from './features/settings/e2etrace-property-palette.jsx';
import { E2ETraceNiFiMain } from './features/dashboard/components/e2etrace-nifi-main';
import { E2ETraceQuickActions } from './features/dashboard/components/e2etrace-quick-actions';

// Stylesheets - Import global styles first, then alphabetically
import './e2etrace-global.css';
// New Layout Styles
import './components/e2etrace-root-layout.css';
// Component & Feature Styles
import './components/e2etrace-tabs.css';
import './features/dashboard/components/e2etrace-nifi-main.css';
import './features/etl/e2etrace-etl-overview-page.css'; // Import new ETL Page styles
import './features/analytics/e2etrace-analytics-page.css';
import './features/dashboard/e2etrace-main-dashboard.css';
import './features/settings/e2etrace-property-palette.css';


// Create a data router instance using a route object configuration.
// This enables data-layer APIs like `useMatches` for the breadcrumbs.
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

function App() {
  return (
    <E2ETraceThemeProvider>
      <E2ETraceLayoutProvider>
        <GraphFilterProvider>
          <RouterProvider router={router} />
        </GraphFilterProvider>
      </E2ETraceLayoutProvider>
    </E2ETraceThemeProvider>
  );
}

const container = document.getElementById('root');

if (container) {
  const root = createRoot(container);
  root.render(
    <StrictMode>
      <App />
    </StrictMode>
  );
} else {
  console.error('Failed to find the root element. The application cannot be mounted.');
}