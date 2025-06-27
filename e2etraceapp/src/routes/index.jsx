import { createHashRouter } from 'react-router-dom';
import { E2ETraceRootLayout } from '../layouts/e2etrace-root-layout.jsx';
import { E2ETraceAnalyticsPage } from '../pages/analytics/analytics/e2etrace-analytics-page.jsx';
import { E2ETraceETLOverviewPage } from '../pages/etl/etl/e2etrace-etl-overview-page.jsx';
import E2ETraceMainDashboard from '../pages/dashboard/e2etrace-main-dashboard.jsx';
import E2ETracePropertyPalette from '../pages/settings/settings/e2etrace-property-palette.jsx';
import { E2ETraceNiFiMain } from '../pages/dashboard/components/e2etrace-nifi-main.jsx';
import ReportingPage from '../pages/reporting/ReportingPage.jsx';
import EChartsSpreadsheetPage from '../pages/spreadsheet/EChartsSpreadsheetPage.jsx';
import DataConfigPage from '../pages/data-config/DataConfigPage.jsx';
import DataMappingPage from '../pages/data-mapping/DataMappingPage.jsx';
import MonitoringPage from '../pages/monitoring/MonitoringPage.jsx';
import DataExportPage from '../pages/export/DataExportPage.jsx';
import DataProcessingHubPage from '../pages/processing/DataProcessingHubPage.jsx';

const router = createHashRouter([
  {
    path: '/',
    element: <E2ETraceRootLayout />,
    handle: { crumb: 'Home' },
    children: [
      // Data Flow Visualization (Home)
      { index: true, element: <E2ETraceMainDashboard />, handle: { crumb: 'Flow Visualization' } },
      
      // Data Configuration Section
      {
        path: 'data-config',
        element: <DataConfigPage />,
        handle: { crumb: 'Data Configuration' },
      },
      {
        path: 'spreadsheet',
        element: <EChartsSpreadsheetPage />, 
        handle: { crumb: 'Data Spreadsheet' },
      },
      {
        path: 'analytics',
        element: <E2ETraceAnalyticsPage />,
        handle: { crumb: 'Analytics & Quality' },
      },
      
      // Data Pipelines Section
      {
        path: 'processing',
        element: <DataProcessingHubPage />,
        handle: { crumb: 'Data Processing Hub' },
      },
      {
        path: 'nifi',
        element: <E2ETraceNiFiMain/>,
        handle: { crumb: 'NiFi Pipelines' },
      },
      {
        path: 'etl',
        element: <E2ETraceETLOverviewPage />,
        handle: { crumb: 'ETL Processes' },
      },
      {
        path: 'data-mapping',
        element: <DataMappingPage />,
        handle: { crumb: 'Data Mapping' },
      },
      
      // Data Flow Section
      {
        path: 'graphexplorer',
        element: <E2ETraceMainDashboard />,
        handle: { crumb: 'Graph Explorer' },
      },
      {
        path: 'monitoring',
        element: <MonitoringPage />,
        handle: { crumb: 'Flow Monitoring' },
      },
      
      // Reporting Section
      {
        path: 'reporting',
        element: <ReportingPage />, 
        handle: { crumb: 'Reports & Dashboards' },
      },
      {
        path: 'export',
        element: <DataExportPage />,
        handle: { crumb: 'Data Export' },
      },
      
      // System Section
      {
        path: 'settings',
        element: <E2ETracePropertyPalette />,
        handle: { crumb: 'Settings' },
      },
    ],
  },
]);

export default router;
