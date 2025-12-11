import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import React from 'react';
import { RouterProvider } from 'react-router-dom';
import { E2ETraceThemeProvider } from './contexts/e2etrace-theme-context.jsx';
import { E2ETraceLayoutProvider } from './contexts/e2etrace-layout-context.jsx';
import { GraphFilterProvider } from './contexts/e2etrace-graph-filter-context.jsx';
import ErrorBoundary from './components/ErrorBoundary.jsx';
import router from './routes';

// Stylesheets
import './e2etrace-global.css';
import './styles/xstate-design-system.css';

function App() {
  return (
    <ErrorBoundary>
      <E2ETraceThemeProvider>
        <E2ETraceLayoutProvider>
          <GraphFilterProvider>
            <RouterProvider router={router} />
          </GraphFilterProvider>
        </E2ETraceLayoutProvider>
      </E2ETraceThemeProvider>
    </ErrorBoundary>
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
