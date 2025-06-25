import React from 'react';

/**
 * A generic Panel component that applies the global .ui-panel styling.
 * It accepts children and any additional HTML attributes like className for E2ETrace.
 */
export function E2ETraceUIPanel({ children, className, ...rest }) {
  return (
    <div className={`ui-panel ${className || ''}`} {...rest}>
      {children}
    </div>
  );
}