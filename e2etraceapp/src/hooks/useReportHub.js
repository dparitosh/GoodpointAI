import { useState, useCallback } from 'react';
import { API_CONFIG } from '../config/api-config.js';

export function useReportHub() {
  const [saving, setSaving] = useState(false);
  const [saved,  setSaved]  = useState(false);
  const [error,  setError]  = useState(null);

  const saveReport = useCallback(async (payload) => {
    setSaving(true);
    setSaved(false);
    setError(null);
    try {
      const url = `${API_CONFIG.API_BASE_URL}${API_CONFIG.ENDPOINTS.REPORT_HUB}`;
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setSaved(true);
      // reset "saved" checkmark after 3s
      setTimeout(() => setSaved(false), 3000);
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }, []);

  return { saveReport, saving, saved, error };
}
