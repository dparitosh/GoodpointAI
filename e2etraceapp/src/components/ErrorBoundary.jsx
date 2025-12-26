import React from 'react';

/**
 * Error Boundary Component
 * 
 * Catches React errors and prevents the entire application from crashing.
 * Displays a fallback UI when an error occurs.
 */
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { 
      hasError: false, 
      error: null, 
      errorInfo: null 
    };
  }

  static getDerivedStateFromError() {
    // Update state so the next render will show the fallback UI
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    // Log the error to console (in production, send to error tracking service)
    console.error('Error caught by ErrorBoundary:', error, errorInfo);
    
    this.setState({
      error: error,
      errorInfo: errorInfo
    });

    // TODO: Send to error tracking service (Sentry, LogRocket, etc.)
    // if (window.Sentry) {
    //   window.Sentry.captureException(error, { contexts: { react: errorInfo } });
    // }
  }

  handleReset = () => {
    this.setState({ 
      hasError: false, 
      error: null, 
      errorInfo: null 
    });
    
    // Optionally reload the page or navigate to home
    if (this.props.onReset) {
      this.props.onReset();
    }
  };

  render() {
    if (this.state.hasError) {
      // Custom fallback UI
      return (
        <div style={{
          padding: '40px',
          maxWidth: '800px',
          margin: '100px auto',
          textAlign: 'center',
          backgroundColor: '#fff',
          borderRadius: '8px',
          boxShadow: '0 2px 8px rgba(0,0,0,0.1)'
        }}>
          <h1 style={{ color: '#d32f2f', marginBottom: '20px' }}>
            ! Something went wrong
          </h1>
          <p style={{ color: '#666', marginBottom: '30px', fontSize: '16px' }}>
            We're sorry for the inconvenience. The application encountered an unexpected error.
          </p>
          
          {import.meta.env.MODE === 'development' && this.state.error && (
            <details style={{ 
              textAlign: 'left', 
              backgroundColor: '#f5f5f5', 
              padding: '20px', 
              borderRadius: '4px',
              marginBottom: '20px',
              maxHeight: '300px',
              overflow: 'auto'
            }}>
              <summary style={{ cursor: 'pointer', fontWeight: 'bold', marginBottom: '10px' }}>
                Error Details (Development Mode)
              </summary>
              <pre style={{ 
                fontSize: '12px', 
                color: '#d32f2f',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word'
              }}>
                {this.state.error.toString()}
                {this.state.errorInfo && this.state.errorInfo.componentStack}
              </pre>
            </details>
          )}
          
          <div style={{ display: 'flex', gap: '10px', justifyContent: 'center' }}>
            <button 
              onClick={this.handleReset}
              style={{
                padding: '12px 24px',
                fontSize: '16px',
                backgroundColor: '#1976d2',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer'
              }}
            >
              Try Again
            </button>
            <button 
              onClick={() => window.location.replace('/#/')}
              style={{
                padding: '12px 24px',
                fontSize: '16px',
                backgroundColor: '#fff',
                color: '#1976d2',
                border: '1px solid #1976d2',
                borderRadius: '4px',
                cursor: 'pointer'
              }}
            >
              Go to Home
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
