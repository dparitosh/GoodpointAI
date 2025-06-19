import { createRoot } from 'react-dom/client'
import React, { StrictMode } from 'react';
import { HashRouter, Routes, Route } from 'react-router-dom';
import App from './App.jsx'
import PropertyPalette from './PropertyPalette.jsx';
import AnalyticsDashboard from './AnalyticsDashboard.jsx'; // Import the new dashboard component
import { LayoutProvider } from './LayoutContext';
import './style.css' // Import your global styles (formerly from neoboi)
import './PropertyPalette.css'; // Import styles for the new page

const root = createRoot(document.getElementById('root'));
root.render(
  <StrictMode>
      <LayoutProvider>
        <HashRouter>
          <Routes>
            <Route path="/" element={<App />} />
            <Route path="/layout-settings" element={<PropertyPalette />} />
            <Route path="/analytics" element={<AnalyticsDashboard />} />
          </Routes>
        </HashRouter>
      </LayoutProvider>
  </StrictMode>,
)