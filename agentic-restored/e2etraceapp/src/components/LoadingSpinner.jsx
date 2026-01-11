/**
 * Reusable Loading Spinner Component
 * Provides consistent loading indicators across the application
 */
import React from 'react';
import './LoadingSpinner.css';

/**
 * Loading spinner variants
 */
export const SPINNER_VARIANTS = {
  DEFAULT: 'default',
  SMALL: 'small',
  LARGE: 'large',
  INLINE: 'inline',
  OVERLAY: 'overlay'
};

/**
 * LoadingSpinner component
 * @param {Object} props
 * @param {string} [props.variant='default'] - Size variant: 'default', 'small', 'large', 'inline', 'overlay'
 * @param {string} [props.message] - Optional loading message
 * @param {boolean} [props.show=true] - Whether to show the spinner
 * @param {string} [props.className] - Additional CSS classes
 */
export function LoadingSpinner({ 
  variant = SPINNER_VARIANTS.DEFAULT, 
  message = '',
  show = true,
  className = ''
}) {
  if (!show) return null;

  const spinnerClass = `loading-spinner loading-spinner--${variant} ${className}`.trim();

  if (variant === SPINNER_VARIANTS.OVERLAY) {
    return (
      <div className="loading-spinner-overlay">
        <div className="loading-spinner-overlay-content">
          <div className={spinnerClass}>
            <div className="spinner-circle"></div>
          </div>
          {message && <p className="loading-spinner-message">{message}</p>}
        </div>
      </div>
    );
  }

  if (variant === SPINNER_VARIANTS.INLINE) {
    return (
      <span className={spinnerClass}>
        <span className="spinner-dot"></span>
        <span className="spinner-dot"></span>
        <span className="spinner-dot"></span>
        {message && <span className="loading-spinner-message-inline">{message}</span>}
      </span>
    );
  }

  return (
    <div className={spinnerClass}>
      <div className="spinner-circle"></div>
      {message && <p className="loading-spinner-message">{message}</p>}
    </div>
  );
}

/**
 * Loading button wrapper - shows spinner when loading
 * @param {Object} props
 * @param {boolean} props.loading - Whether the button is in loading state
 * @param {React.ReactNode} props.children - Button content
 * @param {boolean} [props.disabled] - Whether the button is disabled
 * @param {string} [props.loadingText] - Text to show while loading
 * @param {Function} [props.onClick] - Click handler
 * @param {string} [props.className] - Additional CSS classes
 * @param {string} [props.type] - Button type
 */
export function LoadingButton({ 
  loading, 
  children, 
  disabled, 
  loadingText = 'Loading...',
  onClick,
  className = '',
  type = 'button',
  ...props 
}) {
  return (
    <button
      type={type}
      className={`loading-button ${loading ? 'loading-button--loading' : ''} ${className}`.trim()}
      disabled={disabled || loading}
      onClick={onClick}
      {...props}
    >
      {loading ? (
        <>
          <LoadingSpinner variant={SPINNER_VARIANTS.INLINE} />
          <span className="loading-button-text">{loadingText}</span>
        </>
      ) : (
        children
      )}
    </button>
  );
}

/**
 * Skeleton loader for content placeholders
 * @param {Object} props
 * @param {number} [props.lines=3] - Number of skeleton lines
 * @param {string} [props.className] - Additional CSS classes
 */
export function SkeletonLoader({ lines = 3, className = '' }) {
  return (
    <div className={`skeleton-loader ${className}`.trim()}>
      {Array.from({ length: lines }).map((_, index) => (
        <div 
          key={index} 
          className="skeleton-line"
          style={{ 
            width: index === lines - 1 ? '60%' : '100%',
            animationDelay: `${index * 0.1}s`
          }}
        />
      ))}
    </div>
  );
}

/**
 * Full page loading state
 * @param {Object} props
 * @param {string} [props.message='Loading...'] - Loading message
 */
export function PageLoader({ message = 'Loading...' }) {
  return (
    <div className="page-loader">
      <LoadingSpinner variant={SPINNER_VARIANTS.LARGE} message={message} />
    </div>
  );
}

export default LoadingSpinner;
