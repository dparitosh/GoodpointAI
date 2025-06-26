import React, { useState } from 'react';
import './e2etrace-advanced-search.css';

export function E2ETraceAdvancedSearch({ onSearch }) {
  const [query, setQuery] = useState('');

  const handleChange = (e) => {
    setQuery(e.target.value);
    if (onSearch) onSearch(e.target.value);
  };

  const handleClear = () => {
    setQuery('');
    if (onSearch) onSearch('');
  };

  return (
    <div className="advanced-search-bar" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
      <input
        type="text"
        placeholder="Search nodes, edges, properties..."
        value={query}
        onChange={handleChange}
        aria-label="Advanced Search"
        style={{ padding: '0.4rem 0.75rem', borderRadius: 6, border: '1px solid #c0c6d1', minWidth: 180 }}
      />
      {query && (
        <button
          aria-label="Clear Search"
          title="Clear Search"
          onClick={handleClear}
          style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '1.2rem', color: '#888' }}
        >✕</button>
      )}
    </div>
  );
}
