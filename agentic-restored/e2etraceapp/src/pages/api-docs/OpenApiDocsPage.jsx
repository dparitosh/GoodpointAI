import React from 'react';

const OpenApiDocsPage = () => {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, height: '100%' }}>
      <div>
        <h1 style={{ margin: 0 }}>API Docs (OpenAPI/Swagger)</h1>
        <p style={{ margin: '6px 0 0 0' }}>
          This page shows the backend OpenAPI schema and Swagger UI via the app&apos;s `/api` proxy.
        </p>
        <div style={{ display: 'flex', gap: 12, marginTop: 8, flexWrap: 'wrap' }}>
          <a href="/api/docs" target="_blank" rel="noreferrer">Open Swagger UI in new tab</a>
          <a href="/api/openapi.json" target="_blank" rel="noreferrer">Open OpenAPI JSON</a>
        </div>
      </div>

      <div style={{ flex: 1, minHeight: 500, border: '1px solid rgba(255,255,255,0.08)', borderRadius: 8, overflow: 'hidden' }}>
        <iframe
          title="Swagger UI"
          src="/api/docs"
          style={{ width: '100%', height: '100%', border: 0 }}
        />
      </div>
    </div>
  );
};

export default OpenApiDocsPage;
