/**
 * Data Quality Export Utilities - Excel/CSV export helpers for discovery results
 */

/**
 * Build pivot rows for file summary in Excel export
 * @param {Array} files - Array of file objects with metadata
 * @returns {Array} Formatted rows for Excel file
 */
export function buildFilePivotRows(files = []) {
  if (!files || !Array.isArray(files)) return [];
  
  return files.map((file, idx) => ({
    '#': idx + 1,
    'File Name': file.name || 'Unknown',
    'File Type': file.type || 'Unknown',
    'Total Records': file.recordCount || 0,
    'Tables Found': file.tableCount || 0,
    'Confidence': `${Math.round((file.confidence || 0) * 100)}%`,
    'Status': file.status || 'Pending',
    'Last Scan': new Date(file.scanDate || new Date()).toLocaleDateString(),
  }));
}

/**
 * Build issue entries for Excel export
 * @param {Array} issues - Array of quality issues/problems
 * @returns {Array} Formatted issue rows
 */
export function buildIssueEntries(issues = []) {
  if (!issues || !Array.isArray(issues)) return [];
  
  return issues.map((issue) => ({
    'Issue ID': issue.id || `issue_${Math.random().toString(36).substr(2, 9)}`,
    'Type': issue.type || 'Unknown',
    'Severity': issue.severity || 'Medium',
    'Resource': issue.resource || 'Unknown',
    'Description': issue.description || 'No description',
    'Count': issue.count || 0,
    'Resolution': issue.resolution || 'Needs review',
    'Assigned To': issue.assignedTo || 'Unassigned',
  }));
}

/**
 * Build pivot rows for issue summary in Excel export
 * @param {Array} issues - Array of issues
 * @returns {Array} Pivot summary rows
 */
export function buildIssuePivotRows(issues = []) {
  if (!issues || !Array.isArray(issues)) return [];
  
  // Group issues by type and severity
  const grouped = {};
  
  issues.forEach((issue) => {
    const key = `${issue.type || 'Unknown'}_${issue.severity || 'Medium'}`;
    if (!grouped[key]) {
      grouped[key] = {
        type: issue.type || 'Unknown',
        severity: issue.severity || 'Medium',
        count: 0,
      };
    }
    grouped[key].count += (issue.count || 1);
  });
  
  return Object.values(grouped).map((group, idx) => ({
    '#': idx + 1,
    'Issue Type': group.type,
    'Severity': group.severity,
    'Count': group.count,
    'Percentage': `${Math.round((group.count / Math.max(1, issues.length)) * 100)}%`,
  }));
}

/**
 * Helper to format date consistently
 * @param {Date|string|number} date - Date value to format
 * @returns {string} Formatted date string
 */
export function formatDate(date) {
  if (!date) return 'N/A';
  const d = new Date(date);
  return d.toLocaleDateString('en-US', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  });
}

/**
 * Helper to format percentage values
 * @param {number} value - Value between 0-1 or 0-100
 * @returns {string} Formatted percentage
 */
export function formatPercentage(value) {
  if (typeof value !== 'number') return '0%';
  const pct = value > 1 ? value : value * 100;
  return `${Math.round(pct)}%`;
}

/**
 * Create Excel workbook structure from discovery data
 * @param {Object} discoveryData - Complete discovery results
 * @returns {Object} Workbook schema for write-excel-file
 */
export function createDiscoveryWorkbook(discoveryData) {
  const {
    files = [],
    issues = [],
    tables = [],
    mappings = [],
    timestamp = new Date(),
  } = discoveryData;
  
  return {
    sheets: [
      {
        name: 'Summary',
        rows: [
          [
            { value: 'Discovery Summary Report', style: { fontSize: 14, bold: true } },
          ],
          [],
          [
            { value: 'Generated:', bold: true },
            { value: formatDate(timestamp) },
          ],
          [
            { value: 'Total Files:', bold: true },
            { value: files.length },
          ],
          [
            { value: 'Total Tables:', bold: true },
            { value: tables.length },
          ],
          [
            { value: 'Quality Issues:', bold: true },
            { value: issues.length },
          ],
          [],
        ],
      },
      {
        name: 'Files',
        rows: [
          ['File Name', 'Type', 'Records', 'Tables', 'Confidence', 'Status', 'Scan Date'],
          ...buildFilePivotRows(files).map((file) =>
            Object.values(file)
          ),
        ],
      },
      {
        name: 'Issues',
        rows: [
          ['Issue ID', 'Type', 'Severity', 'Resource', 'Description', 'Count', 'Resolution', 'Assigned To'],
          ...buildIssueEntries(issues).map((issue) =>
            Object.values(issue)
          ),
        ],
      },
      {
        name: 'Issue Summary',
        rows: [
          ['#', 'Type', 'Severity', 'Count', 'Percentage'],
          ...buildIssuePivotRows(issues).map((row) =>
            Object.values(row)
          ),
        ],
      },
    ],
  };
}

/**
 * Export discovery data to CSV format (simple)
 * @param {Array} rows - Row data to export
 * @param {string} filename - Output filename
 * @returns {string} CSV formatted string
 */
export function exportToCSV(rows = [], filename = 'export.csv') {
  if (!Array.isArray(rows) || rows.length === 0) return '';
  
  // Get headers from first row
  const headers = Object.keys(rows[0]);
  const csvContent = [
    headers.join(','),
    ...rows.map((row) =>
      headers.map((header) => {
        const value = row[header];
        // Escape CSV values that contain commas or quotes
        if (typeof value === 'string' && (value.includes(',') || value.includes('"'))) {
          return `"${value.replace(/"/g, '""')}"`;
        }
        return value;
      }).join(',')
    ),
  ].join('\n');
  
  return csvContent;
}

export default {
  buildFilePivotRows,
  buildIssueEntries,
  buildIssuePivotRows,
  formatDate,
  formatPercentage,
  createDiscoveryWorkbook,
  exportToCSV,
};
