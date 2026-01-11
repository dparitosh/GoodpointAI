import React, { useRef, useEffect } from 'react';
import './EventPanel.css';

/**
 * Event Panel Component for XState Visualizer
 * Displays migration events, validation results, and system actions
 */
export const EventPanel = ({ events = [], onEventClick, theme = 'light' }) => {
  const contentRef = useRef(null);

  // Auto-scroll to bottom when new events arrive
  useEffect(() => {
    if (contentRef.current) {
      contentRef.current.scrollTop = contentRef.current.scrollHeight;
    }
  }, [events]);

  const getEventIcon = (type) => {
    const iconMap = {
      'migration': 'fa-arrow-right',
      'validation': 'fa-check',
      'error': 'fa-times',
      'warning': 'fa-exclamation',
      'info': 'fa-info',
      'success': 'fa-check',
      'failure': 'fa-times',
      'processing': 'fa-spinner fa-spin',
      'completed': 'fa-check-circle'
    };
    return iconMap[type] || 'fa-circle';
  };

  const getEventClass = (type) => {
    return `event-panel__event--${type}`;
  };

  const formatTimestamp = (timestamp) => {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    return date.toLocaleTimeString('en-US', { 
      hour: '2-digit', 
      minute: '2-digit', 
      second: '2-digit',
      hour12: false 
    });
  };

  return (
    <div className={`event-panel event-panel--${theme}`}>
      <div className="event-panel__toolbar">
        <button className="event-panel__clear-btn" title="Clear all events">
          Clear
        </button>
        <button className="event-panel__export-btn" title="Export events">
          Export
        </button>
      </div>

      <div className="event-panel__content" ref={contentRef}>
        {events.length > 0 ? (
          events.map((event, index) => (
            <div
              key={event.id || index}
              className={`event-panel__event ${getEventClass(event.type)}`}
              onClick={() => onEventClick && onEventClick(event)}
            >
              <div className="event-panel__event-icon">
                {getEventIcon(event.type)}
              </div>
              
              <div className="event-panel__event-content">
                <div className="event-panel__event-header">
                  <span className="event-panel__event-title">{event.title || event.message}</span>
                  <span className="event-panel__event-timestamp">
                    {formatTimestamp(event.timestamp)}
                  </span>
                </div>
                
                {event.details && (
                  <div className="event-panel__event-details">{event.details}</div>
                )}
                
                {event.affectedNodes && event.affectedNodes.length > 0 && (
                  <div className="event-panel__event-nodes">
                    Affected nodes: {event.affectedNodes.join(', ')}
                  </div>
                )}
              </div>
            </div>
          ))
        ) : (
          <div className="event-panel__empty">
            <span className="event-panel__empty-icon"><i className="fas fa-inbox" aria-hidden="true" /></span>
            <p>No events to display</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default EventPanel;
