import React from 'react';
import { Link, useRouteError, isRouteErrorResponse } from 'react-router-dom';

export default function RouteErrorPage() {
  const error = useRouteError();

  const title = isRouteErrorResponse(error)
    ? `${error.status} ${error.statusText}`
    : 'Something went wrong';

  const details = isRouteErrorResponse(error)
    ? error.data?.message || error.data || null
    : error instanceof Error
      ? error.message
      : null;

  return (
    <div style={{ padding: 24 }}>
      <h1 style={{ margin: 0 }}>{title}</h1>
      <p style={{ marginTop: 12, opacity: 0.8 }}>
        The page hit a routing error. Use the links below to recover.
      </p>
      {details ? (
        <pre style={{ marginTop: 12, padding: 12, overflow: 'auto', background: 'var(--color-bg-secondary)', borderRadius: 8 }}>
          {String(details)}
        </pre>
      ) : null}
      <div style={{ marginTop: 16, display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        <Link to="/" style={{ color: 'var(--tcs-blue-primary)' }}>Go Home</Link>
        <Link to="/graphexplorer" style={{ color: 'var(--tcs-blue-primary)' }}>Graph Explorer</Link>
      </div>
    </div>
  );
}
