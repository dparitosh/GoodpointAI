import React from 'react';

export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }
  componentDidCatch(error, errorInfo) {
    // Optionally log errorInfo
  }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{ color: '#b00020', background: '#fff0f0', padding: '1.5rem', borderRadius: 8, margin: '1rem 0' }}>
          <strong>Something went wrong:</strong>
          <pre style={{ whiteSpace: 'pre-wrap', marginTop: 8 }}>{this.state.error?.toString()}</pre>
        </div>
      );
    }
    return this.props.children;
  }
}

export function Skeleton({ style = {}, className = '' }) {
  return <div className={`skeleton-loader ${className}`} style={{ background: 'linear-gradient(90deg, #f4f7fb 25%, #e6f0fa 50%, #f4f7fb 75%)', borderRadius: 6, minHeight: 32, ...style, animation: 'skeleton-pulse 1.2s infinite linear' }} />;
}

// Add to your global CSS:
// @keyframes skeleton-pulse {
//   0% { background-position: -200px 0; }
//   100% { background-position: calc(200px + 100%) 0; }
// }
