import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import React from 'react';
import { RouterProvider } from 'react-router-dom';
import { E2ETraceThemeProvider } from './contexts/e2etrace-theme-context.jsx';
import { E2ETraceLayoutProvider } from './contexts/e2etrace-layout-context.jsx';
import { GraphFilterProvider } from './contexts/e2etrace-graph-filter-context.jsx';
import ErrorBoundary from './components/ErrorBoundary.jsx';
import ToastContainer from './components/ToastContainer.jsx';
import router from './routes';
import './i18n/index.js';

// Ensure refresh/direct navigation preserves the current page.
// This app uses a hash router; if the browser URL is path-based (e.g. /processing)
// with no hash, React Router will treat it as the index route. Convert such URLs to
// their hash equivalents so refresh lands on the same page.
(() => {
  const { hash, pathname, search } = window.location;
  if (hash && hash !== '#') return;

  const baseUrl = (import.meta.env.BASE_URL || '/').replace(/\/?$/, '/');
  const routePath = pathname.startsWith(baseUrl)
    ? pathname.slice(baseUrl.length - 1)
    : pathname;

  if (routePath === '/' || routePath === '/index.html') return;
  if (routePath.startsWith('/api')) return;

  window.location.replace(`${baseUrl}#${routePath}${search || ''}`);
})();

// Stylesheets - Global styles for consistency
import './styles/global.css';
import './styles/buttons.css';
import './e2etrace-global.css';
import './styles/xstate-design-system.css';

function App() {
  return (
    <ErrorBoundary>
      <E2ETraceThemeProvider>
        <E2ETraceLayoutProvider>
          <GraphFilterProvider>
            <RouterProvider router={router} />
            <ToastContainer />
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
