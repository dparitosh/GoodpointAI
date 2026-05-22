import React from 'react';
import DOMPurify from 'dompurify';

/**
 * SafeHTML Component
 * 
 * Securely renders HTML by sanitizing it with DOMPurify.
 * Prevents XSS attacks from malicious HTML content.
 * 
 * @param {Object} props
 * @param {string} props.html - The HTML string to render
 * @param {Object} props.sanitizeConfig - DOMPurify configuration
 * @param {string} props.className - CSS class
 * @param {string} props.tag - HTML tag to use (default: 'div')
 * 
 * @example
 * <SafeHTML 
 *   html="<p>Found: <mark>result</mark></p>"
 *   sanitizeConfig={{
 *     ALLOWED_TAGS: ['mark', 'p'],
 *     ALLOWED_ATTR: ['class']
 *   }}
 * />
 */
export const SafeHTML = ({
  html,
  sanitizeConfig = {
    ALLOWED_TAGS: ['mark', 'strong', 'em', 'u', 'br', 'p', 'span', 'div'],
    ALLOWED_ATTR: ['class', 'data-test'],
    KEEP_CONTENT: true
  },
  className = '',
  tag: Tag = 'div'
}) => {
  if (!html) return null;

  // Sanitize HTML to remove XSS attack vectors
  const cleanHTML = DOMPurify.sanitize(html, sanitizeConfig);

  return (
    <Tag
      className={className}
      dangerouslySetInnerHTML={{ __html: cleanHTML }}
      role="region"
    />
  );
};

export default SafeHTML;
