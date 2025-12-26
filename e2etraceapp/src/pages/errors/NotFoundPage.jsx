import React from 'react';
import { Link, useLocation } from 'react-router-dom';

export default function NotFoundPage() {
  const location = useLocation();

  return (
    <div style={{ padding: 24 }}>
      <h1 style={{ margin: 0 }}>404 Not Found</h1>
      <p style={{ marginTop: 12, opacity: 0.8 }}>
        No route matches <strong>{location.pathname}</strong>.
      </p>
      <div style={{ marginTop: 16, display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        <Link to="/" style={{ color: 'var(--tcs-blue-primary)' }}>Go Home</Link>
        <Link to="/interactive-state-flow" style={{ color: 'var(--tcs-blue-primary)' }}>Interactive State Flow</Link>
        <Link to="/graphexplorer" style={{ color: 'var(--tcs-blue-primary)' }}>Graph Explorer</Link>
      </div>
    </div>
  );
}
