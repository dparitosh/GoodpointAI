import React from 'react';
import { Link, useMatches } from 'react-router-dom';
import { E2ETraceUIPanel } from './e2etrace-ui-panel';
import './e2etrace-breadcrumbs.css';

export const E2ETraceBreadcrumbs = () => {
  const matches = useMatches();

  // Filter out non-route matches (e.g., root layout without a specific path)
  // and routes without a handle.crumb or path
  const crumbs = matches
    .filter(match => Boolean(match.handle?.crumb))
    .map((match, index, array) => {
      const isLast = index === array.length - 1;
      const path = match.pathname; // Use full pathname for linking
      const crumbText = match.handle.crumb;
      // Create unique key by combining path and index to avoid duplicate key warnings
      const uniqueKey = `${path}-${index}`;

      return (
        <span key={uniqueKey} className="e2etrace-breadcrumb-item">
          {isLast ? (
            <span className="e2etrace-breadcrumb-current">{crumbText}</span>
          ) : (
            <Link to={path} className="e2etrace-breadcrumb-link">{crumbText}</Link>
          )}
          {!isLast && <span className="e2etrace-breadcrumb-separator">&rsaquo;</span>}
        </span>
      );
    });

  return (
    <nav className="e2etrace-breadcrumbs-panel" aria-label="breadcrumb">{crumbs}</nav>
  );
};