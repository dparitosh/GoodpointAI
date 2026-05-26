/**
 * Format API error responses to user-friendly messages
 */
export const formatApiError = (errPayload) => {
  const detail = errPayload?.detail;
  if (!detail) return errPayload?.message || errPayload?.error || null;
  
  if (typeof detail === 'string') return detail;
  
  if (Array.isArray(detail)) {
    const parts = detail.map(d => {
      const locArr = Array.isArray(d?.loc) ? d.loc : [];
      // FastAPI loc is usually ["body", "field", ...]
      const loc = locArr.slice(1).join('.') || 'field';
      const msg = d?.msg || 'invalid value';
      return `${loc}: ${msg}`;
    });
    return parts.join('; ');
  }
  
  return String(detail);
};
