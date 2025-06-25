import React from 'react';
import { HashRouter, Routes, Route } from 'react-router-dom';

// Context Providers
import { E2ETraceThemeProvider } from './contexts/e2etrace-theme-context.jsx';
import { E2ETraceLayoutProvider } from './contexts/e2etrace-layout-context.jsx';

// Page/Feature Components
import E2ETraceAnalyticsDashboard from './features/analytics/e2etrace-analytics-dashboard.jsx';
import E2ETraceMainDashboard from './features/dashboard/e2etrace-main-dashboard.jsx';
import E2ETracePropertyPalette from './features/settings/e2etrace-property-palette.jsx';

// Stylesheets - Import global styles first, then alphabetically
import './e2etrace-global.css';
import './components/e2etrace-data-table.css';
import './features/analytics/e2etrace-analytics-dashboard.css';
import './features/dashboard/e2etrace-main-dashboard.css';
import './features/settings/e2etrace-property-palette.css';

function App() {
  return (
    <E2ETraceThemeProvider>
      <E2ETraceLayoutProvider>
        <HashRouter>
          <Routes>
            <Route path="/" element={<E2ETraceMainDashboard />} />
            <Route path="/settings" element={<E2ETracePropertyPalette />} />
            <Route path="/analytics" element={<E2ETraceAnalyticsDashboard />} />
          </Routes>
        </HashRouter>
      </E2ETraceLayoutProvider>
    </E2ETraceThemeProvider>
  );
}

export default App;