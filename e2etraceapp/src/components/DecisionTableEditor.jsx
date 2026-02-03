/**
 * DecisionTableEditor.jsx
 * 
 * Enterprise spreadsheet-like editor for Decision Table rules.
 * Provides a tabular IF/THEN interface for complex rule definitions.
 * 
 * Features:
 * - Spreadsheet-style grid editing
 * - Condition columns (IF) and Action columns (THEN)
 * - Row-based rule entries
 * - Excel import/export
 * - Copy/paste support
 * - Keyboard navigation
 */

import { useState, useCallback, useMemo, useRef, useEffect } from 'react';
import { readExcelArrayBufferToAoa } from '../utils/spreadsheet-utils.js';
import writeXlsxFile from 'write-excel-file';
import './DecisionTableEditor.css';

// Default column definitions for a decision table
const DEFAULT_CONDITION_COLUMNS = [
  { id: 'c1', name: 'Condition 1', type: 'condition', field: '', operator: 'equals' },
  { id: 'c2', name: 'Condition 2', type: 'condition', field: '', operator: 'equals' },
];

const DEFAULT_ACTION_COLUMNS = [
  { id: 'a1', name: 'Action', type: 'action', actionType: 'log' },
  { id: 'a2', name: 'Message', type: 'result', field: 'message' },
];

const OPERATORS = [
  { value: 'equals', label: '=' },
  { value: 'not_equals', label: '≠' },
  { value: 'greater_than', label: '>' },
  { value: 'less_than', label: '<' },
  { value: 'greater_equal', label: '≥' },
  { value: 'less_equal', label: '≤' },
  { value: 'contains', label: 'contains' },
  { value: 'starts_with', label: 'starts with' },
  { value: 'ends_with', label: 'ends with' },
  { value: 'is_empty', label: 'is empty' },
  { value: 'is_not_empty', label: 'is not empty' },
  { value: 'matches', label: 'regex' },
  { value: 'any', label: '*' },
];

const ACTION_TYPES = [
  { value: 'log', label: '📝 Log' },
  { value: 'warn', label: '⚠️ Warn' },
  { value: 'quarantine', label: '🔒 Quarantine' },
  { value: 'reject', label: '❌ Reject' },
  { value: 'transform', label: '🔄 Transform' },
  { value: 'escalate', label: '📢 Escalate' },
  { value: 'approve', label: '✅ Approve' },
];

/**
 * DecisionTableEditor Component
 * 
 * @param {Object} props
 * @param {Array} props.conditionColumns - Column definitions for IF conditions
 * @param {Array} props.actionColumns - Column definitions for THEN actions  
 * @param {Array} props.rows - Decision table rows (rules)
 * @param {Function} props.onChange - Callback when table changes
 * @param {boolean} props.readOnly - Whether the table is read-only
 */
export default function DecisionTableEditor({ 
  conditionColumns = DEFAULT_CONDITION_COLUMNS,
  actionColumns = DEFAULT_ACTION_COLUMNS,
  rows = [],
  onChange,
  readOnly = false,
  tableName = 'Decision Table'
}) {
  const [columns, setColumns] = useState([...conditionColumns, ...actionColumns]);
  const [tableRows, setTableRows] = useState(rows.length ? rows : [createEmptyRow(columns)]);
  const [selectedCell, setSelectedCell] = useState(null);
  const [editingCell, setEditingCell] = useState(null);
  const [editValue, setEditValue] = useState('');
  const [showColumnConfig, setShowColumnConfig] = useState(false);
  const [configColumn, setConfigColumn] = useState(null);
  
  const tableRef = useRef(null);
  const inputRef = useRef(null);

  // Create empty row based on columns
  function createEmptyRow(cols) {
    const row = { id: `row_${Date.now()}_${Math.random().toString(36).substr(2, 9)}` };
    cols.forEach(col => {
      row[col.id] = col.type === 'action' ? 'log' : '';
    });
    return row;
  }

  // Update parent when rows change
  useEffect(() => {
    if (onChange) {
      onChange({ columns, rows: tableRows });
    }
  }, [columns, tableRows, onChange]);

  // Focus input when editing starts
  useEffect(() => {
    if (editingCell && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [editingCell]);

  // Memoized column groups
  const conditionCols = useMemo(() => columns.filter(c => c.type === 'condition'), [columns]);
  const actionCols = useMemo(() => columns.filter(c => c.type !== 'condition'), [columns]);

  // Cell click handler
  const handleCellClick = useCallback((rowIndex, colId) => {
    if (readOnly) return;
    setSelectedCell({ rowIndex, colId });
  }, [readOnly]);

  // Cell double-click to edit
  const handleCellDoubleClick = useCallback((rowIndex, colId) => {
    if (readOnly) return;
    const row = tableRows[rowIndex];
    const value = row ? row[colId] : '';
    setEditingCell({ rowIndex, colId });
    setEditValue(value || '');
  }, [readOnly, tableRows]);

  // Update cell value
  const updateCell = useCallback((rowIndex, colId, value) => {
    setTableRows(prev => {
      const updated = [...prev];
      if (updated[rowIndex]) {
        updated[rowIndex] = { ...updated[rowIndex], [colId]: value };
      }
      return updated;
    });
  }, []);

  // Finish editing
  const finishEdit = useCallback(() => {
    if (editingCell) {
      updateCell(editingCell.rowIndex, editingCell.colId, editValue);
      setEditingCell(null);
      setEditValue('');
    }
  }, [editingCell, editValue, updateCell]);

  // Cancel editing
  const cancelEdit = useCallback(() => {
    setEditingCell(null);
    setEditValue('');
  }, []);

  // Key handler for cell editing
  const handleKeyDown = useCallback((e) => {
    if (editingCell) {
      if (e.key === 'Enter') {
        e.preventDefault();
        finishEdit();
      } else if (e.key === 'Escape') {
        e.preventDefault();
        cancelEdit();
      } else if (e.key === 'Tab') {
        e.preventDefault();
        finishEdit();
        // Move to next cell
        const colIndex = columns.findIndex(c => c.id === editingCell.colId);
        if (colIndex < columns.length - 1) {
          handleCellDoubleClick(editingCell.rowIndex, columns[colIndex + 1].id);
        } else if (editingCell.rowIndex < tableRows.length - 1) {
          handleCellDoubleClick(editingCell.rowIndex + 1, columns[0].id);
        }
      }
    } else if (selectedCell) {
      if (e.key === 'Enter' || e.key === 'F2') {
        e.preventDefault();
        handleCellDoubleClick(selectedCell.rowIndex, selectedCell.colId);
      } else if (e.key === 'Delete' || e.key === 'Backspace') {
        e.preventDefault();
        updateCell(selectedCell.rowIndex, selectedCell.colId, '');
      } else if (e.key.length === 1 && !e.ctrlKey && !e.metaKey) {
        // Start typing
        handleCellDoubleClick(selectedCell.rowIndex, selectedCell.colId);
        setEditValue(e.key);
      }
      // Arrow key navigation
      if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.key)) {
        e.preventDefault();
        const colIndex = columns.findIndex(c => c.id === selectedCell.colId);
        let newRow = selectedCell.rowIndex;
        let newCol = colIndex;
        
        switch (e.key) {
          case 'ArrowUp': newRow = Math.max(0, newRow - 1); break;
          case 'ArrowDown': newRow = Math.min(tableRows.length - 1, newRow + 1); break;
          case 'ArrowLeft': newCol = Math.max(0, newCol - 1); break;
          case 'ArrowRight': newCol = Math.min(columns.length - 1, newCol + 1); break;
        }
        
        setSelectedCell({ rowIndex: newRow, colId: columns[newCol].id });
      }
    }
  }, [editingCell, selectedCell, columns, tableRows, finishEdit, cancelEdit, handleCellDoubleClick, updateCell]);

  // Add new row
  const addRow = useCallback(() => {
    setTableRows(prev => [...prev, createEmptyRow(columns)]);
  }, [columns]);

  // Delete row
  const deleteRow = useCallback((rowIndex) => {
    if (tableRows.length <= 1) return; // Keep at least one row
    setTableRows(prev => prev.filter((_, i) => i !== rowIndex));
  }, [tableRows.length]);

  // Duplicate row
  const duplicateRow = useCallback((rowIndex) => {
    const row = tableRows[rowIndex];
    if (row) {
      const newRow = { ...row, id: `row_${Date.now()}_${Math.random().toString(36).substr(2, 9)}` };
      setTableRows(prev => {
        const updated = [...prev];
        updated.splice(rowIndex + 1, 0, newRow);
        return updated;
      });
    }
  }, [tableRows]);

  // Add condition column
  const addConditionColumn = useCallback(() => {
    const newCol = {
      id: `c_${Date.now()}`,
      name: `Condition ${conditionCols.length + 1}`,
      type: 'condition',
      field: '',
      operator: 'equals'
    };
    setColumns(prev => {
      const condIdx = prev.filter(c => c.type === 'condition').length;
      const updated = [...prev];
      updated.splice(condIdx, 0, newCol);
      return updated;
    });
    // Add empty value to all rows
    setTableRows(prev => prev.map(row => ({ ...row, [newCol.id]: '' })));
  }, [conditionCols.length]);

  // Add action column
  const addActionColumn = useCallback(() => {
    const newCol = {
      id: `a_${Date.now()}`,
      name: `Output ${actionCols.length + 1}`,
      type: 'result',
      field: ''
    };
    setColumns(prev => [...prev, newCol]);
    setTableRows(prev => prev.map(row => ({ ...row, [newCol.id]: '' })));
  }, [actionCols.length]);

  // Delete column
  const deleteColumn = useCallback((colId) => {
    if (columns.length <= 2) return; // Keep at least 2 columns
    setColumns(prev => prev.filter(c => c.id !== colId));
    setTableRows(prev => prev.map(row => {
      const { [colId]: _, ...rest } = row;
      return rest;
    }));
  }, [columns.length]);

  // Configure column
  const openColumnConfig = useCallback((col) => {
    setConfigColumn(col);
    setShowColumnConfig(true);
  }, []);

  // Save column config
  const saveColumnConfig = useCallback((updatedCol) => {
    setColumns(prev => prev.map(c => c.id === updatedCol.id ? updatedCol : c));
    setShowColumnConfig(false);
    setConfigColumn(null);
  }, []);

  // Export to Excel
  const exportToExcel = useCallback(async () => {
    const schema = columns.map(col => ({
      column: col.name,
      type: String,
      value: row => row[col.id] || ''
    }));

    await writeXlsxFile(tableRows, {
      schema,
      fileName: `${tableName.replace(/\s+/g, '_')}_DecisionTable.xlsx`
    });
  }, [columns, tableRows, tableName]);

  // Import from Excel
  const importFromExcel = useCallback(async (file) => {
    try {
      const arrayBuffer = await file.arrayBuffer();
      const aoa = await readExcelArrayBufferToAoa(arrayBuffer);
      
      if (aoa.length < 2) {
        alert('Excel file must have a header row and at least one data row');
        return;
      }

      // First row is headers
      const headers = aoa[0];
      
      // Create columns from headers
      const newColumns = headers.map((header, idx) => {
        const isCondition = idx < Math.ceil(headers.length / 2);
        return {
          id: `col_${idx}`,
          name: header || `Column ${idx + 1}`,
          type: isCondition ? 'condition' : 'result',
          field: header?.toLowerCase().replace(/\s+/g, '_') || '',
          operator: 'equals'
        };
      });

      // Create rows from data
      const newRows = aoa.slice(1).map((rowData, rowIdx) => {
        const row = { id: `row_${rowIdx}` };
        headers.forEach((_, colIdx) => {
          row[`col_${colIdx}`] = rowData[colIdx] || '';
        });
        return row;
      });

      setColumns(newColumns);
      setTableRows(newRows.length ? newRows : [createEmptyRow(newColumns)]);
    } catch (err) {
      console.error('Import error:', err);
      alert('Failed to import Excel file');
    }
  }, []);

  // File input handler
  const handleFileSelect = useCallback((e) => {
    const file = e.target.files?.[0];
    if (file) {
      importFromExcel(file);
      e.target.value = '';
    }
  }, [importFromExcel]);

  // Render cell content
  const renderCell = (row, col, rowIndex) => {
    const isSelected = selectedCell?.rowIndex === rowIndex && selectedCell?.colId === col.id;
    const isEditing = editingCell?.rowIndex === rowIndex && editingCell?.colId === col.id;
    const value = row[col.id] || '';

    if (isEditing) {
      // For action columns, show select
      if (col.type === 'action') {
        return (
          <select
            ref={inputRef}
            className="cell-select"
            value={editValue}
            onChange={e => setEditValue(e.target.value)}
            onBlur={finishEdit}
            onKeyDown={handleKeyDown}
          >
            {ACTION_TYPES.map(at => (
              <option key={at.value} value={at.value}>{at.label}</option>
            ))}
          </select>
        );
      }
      return (
        <input
          ref={inputRef}
          type="text"
          className="cell-input"
          value={editValue}
          onChange={e => setEditValue(e.target.value)}
          onBlur={finishEdit}
          onKeyDown={handleKeyDown}
        />
      );
    }

    // Display value
    let displayValue = value;
    if (col.type === 'action') {
      const actionType = ACTION_TYPES.find(a => a.value === value);
      displayValue = actionType ? actionType.label : value;
    }

    return (
      <div 
        className={`cell-content ${isSelected ? 'selected' : ''}`}
        onClick={() => handleCellClick(rowIndex, col.id)}
        onDoubleClick={() => handleCellDoubleClick(rowIndex, col.id)}
      >
        {displayValue || <span className="placeholder">—</span>}
      </div>
    );
  };

  return (
    <div className="decision-table-editor" tabIndex={0} onKeyDown={handleKeyDown} ref={tableRef}>
      {/* Toolbar */}
      <div className="dt-toolbar">
        <div className="toolbar-left">
          <h4 className="dt-title">
            <i className="fas fa-table"></i>
            {tableName}
          </h4>
          <span className="dt-stats">
            {tableRows.length} rules • {conditionCols.length} conditions • {actionCols.length} outputs
          </span>
        </div>
        <div className="toolbar-right">
          <button className="btn-tool" onClick={addConditionColumn} title="Add Condition Column">
            <i className="fas fa-plus-circle"></i> Condition
          </button>
          <button className="btn-tool" onClick={addActionColumn} title="Add Output Column">
            <i className="fas fa-plus-square"></i> Output
          </button>
          <div className="toolbar-divider"></div>
          <button className="btn-tool" onClick={addRow} title="Add Row">
            <i className="fas fa-plus"></i> Row
          </button>
          <div className="toolbar-divider"></div>
          <label className="btn-tool btn-import">
            <i className="fas fa-file-excel"></i> Import
            <input type="file" accept=".xlsx,.xls" onChange={handleFileSelect} hidden />
          </label>
          <button className="btn-tool" onClick={exportToExcel} title="Export to Excel">
            <i className="fas fa-download"></i> Export
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="dt-table-wrapper">
        <table className="dt-table">
          <thead>
            {/* Column Group Headers */}
            <tr className="group-header-row">
              <th className="row-number-header" rowSpan={2}>#</th>
              <th className="group-header condition-group" colSpan={conditionCols.length}>
                <i className="fas fa-code-branch"></i> IF (Conditions)
              </th>
              <th className="group-header action-group" colSpan={actionCols.length}>
                <i className="fas fa-bolt"></i> THEN (Actions)
              </th>
              <th className="row-actions-header" rowSpan={2}>Actions</th>
            </tr>
            {/* Column Headers */}
            <tr className="column-header-row">
              {columns.map(col => (
                <th 
                  key={col.id} 
                  className={`column-header ${col.type === 'condition' ? 'condition-col' : 'action-col'}`}
                >
                  <div className="column-header-content">
                    <span className="col-name">{col.name}</span>
                    {col.type === 'condition' && col.field && (
                      <span className="col-field">{col.field}</span>
                    )}
                    <div className="col-actions">
                      <button 
                        className="col-btn" 
                        onClick={() => openColumnConfig(col)}
                        title="Configure Column"
                      >
                        <i className="fas fa-cog"></i>
                      </button>
                      <button 
                        className="col-btn col-btn-delete" 
                        onClick={() => deleteColumn(col.id)}
                        title="Delete Column"
                      >
                        <i className="fas fa-times"></i>
                      </button>
                    </div>
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {tableRows.map((row, rowIndex) => (
              <tr key={row.id} className={selectedCell?.rowIndex === rowIndex ? 'selected-row' : ''}>
                <td className="row-number">{rowIndex + 1}</td>
                {columns.map(col => (
                  <td 
                    key={col.id} 
                    className={`dt-cell ${col.type === 'condition' ? 'condition-cell' : 'action-cell'}`}
                  >
                    {renderCell(row, col, rowIndex)}
                  </td>
                ))}
                <td className="row-actions">
                  <button 
                    className="row-btn" 
                    onClick={() => duplicateRow(rowIndex)}
                    title="Duplicate Row"
                  >
                    <i className="fas fa-copy"></i>
                  </button>
                  <button 
                    className="row-btn row-btn-delete" 
                    onClick={() => deleteRow(rowIndex)}
                    title="Delete Row"
                    disabled={tableRows.length <= 1}
                  >
                    <i className="fas fa-trash"></i>
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Add Row Button */}
      <div className="dt-footer">
        <button className="btn-add-row" onClick={addRow}>
          <i className="fas fa-plus"></i> Add Rule Row
        </button>
      </div>

      {/* Column Configuration Modal */}
      {showColumnConfig && configColumn && (
        <ColumnConfigModal
          column={configColumn}
          onSave={saveColumnConfig}
          onClose={() => setShowColumnConfig(false)}
        />
      )}
    </div>
  );
}

/**
 * Column Configuration Modal
 */
function ColumnConfigModal({ column, onSave, onClose }) {
  const [form, setForm] = useState({ ...column });

  const handleSave = () => {
    onSave(form);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content modal-small" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>Configure Column</h3>
          <button className="modal-close" onClick={onClose}>
            <i className="fas fa-times"></i>
          </button>
        </div>
        <div className="modal-body">
          <div className="form-group">
            <label>Column Name</label>
            <input
              type="text"
              value={form.name}
              onChange={e => setForm(prev => ({ ...prev, name: e.target.value }))}
              className="form-input"
            />
          </div>
          
          {form.type === 'condition' && (
            <>
              <div className="form-group">
                <label>Field/Attribute</label>
                <input
                  type="text"
                  value={form.field || ''}
                  onChange={e => setForm(prev => ({ ...prev, field: e.target.value }))}
                  placeholder="e.g., lifecycle_state"
                  className="form-input"
                />
              </div>
              <div className="form-group">
                <label>Operator</label>
                <select
                  value={form.operator || 'equals'}
                  onChange={e => setForm(prev => ({ ...prev, operator: e.target.value }))}
                  className="form-select"
                >
                  {OPERATORS.map(op => (
                    <option key={op.value} value={op.value}>{op.label} ({op.value})</option>
                  ))}
                </select>
              </div>
            </>
          )}
          
          <div className="form-group">
            <label>Column Type</label>
            <select
              value={form.type}
              onChange={e => setForm(prev => ({ ...prev, type: e.target.value }))}
              className="form-select"
            >
              <option value="condition">Condition (IF)</option>
              <option value="action">Action Type (THEN)</option>
              <option value="result">Output/Message</option>
            </select>
          </div>
        </div>
        <div className="modal-footer">
          <button className="btn-secondary" onClick={onClose}>Cancel</button>
          <button className="btn-primary" onClick={handleSave}>Save</button>
        </div>
      </div>
    </div>
  );
}

export { DecisionTableEditor };
