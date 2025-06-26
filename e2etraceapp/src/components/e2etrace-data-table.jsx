import React, { useState, useMemo, useRef, useEffect } from "react";
import "./e2etrace-data-table.css";

// Helper to get a value for sorting from a flat object.
const getSortableValue = (item, key) => item[key];

function exportToCSV(data, columns) {
  const csvRows = [columns.join(",")];
  data.forEach((row) => {
    csvRows.push(columns.map((col) => JSON.stringify(row[col] ?? "")).join(","));
  });
  const csvContent = csvRows.join("\n");
  const blob = new Blob([csvContent], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "data-table.csv";
  a.click();
  URL.revokeObjectURL(url);
}

export function E2ETraceDataTable({ tableElements, onRowClick, initialSortKey = "id" }) {
  const [sortConfig, setSortConfig] = useState({ key: initialSortKey, direction: "ascending" });
  const [expandedProperties, setExpandedProperties] = useState(new Set());
  const [filters, setFilters] = useState({ id: "", label: "", element_type: "" });
  const [page, setPage] = useState(1);
  const [showScrollTop, setShowScrollTop] = useState(false);
  const pageSize = 50; // Increased from 25 to show more items per page
  const tableWrapperRef = useRef(null);

  // Handle scroll to show/hide scroll-to-top button
  useEffect(() => {
    const handleScroll = () => {
      if (tableWrapperRef.current) {
        const scrollTop = tableWrapperRef.current.scrollTop;
        setShowScrollTop(scrollTop > 100);
      }
    };

    const tableWrapper = tableWrapperRef.current;
    if (tableWrapper) {
      tableWrapper.addEventListener('scroll', handleScroll);
      return () => tableWrapper.removeEventListener('scroll', handleScroll);
    }
  }, []);

  const scrollToTop = () => {
    if (tableWrapperRef.current) {
      tableWrapperRef.current.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  const togglePropertiesExpansion = (elementId) => {
    setExpandedProperties((prevExpanded) => {
      const newExpanded = new Set(prevExpanded);
      if (newExpanded.has(elementId)) newExpanded.delete(elementId);
      else newExpanded.add(elementId);
      return newExpanded;
    });
  };

  const requestSort = (key) => {
    setSortConfig((prevConfig) => ({
      key,
      direction:
        prevConfig.key === key && prevConfig.direction === "ascending"
          ? "descending"
          : "ascending",
    }));
  };

  const filteredTableElements = useMemo(() => {
    if (!tableElements) return [];
    return tableElements.filter(
      (row) =>
        (!filters.id || String(row.id).toLowerCase().includes(filters.id.toLowerCase())) &&
        (!filters.label || (row.label || "").toLowerCase().includes(filters.label.toLowerCase())) &&
        (!filters.element_type || (row.element_type || "").toLowerCase().includes(filters.element_type.toLowerCase()))
    );
  }, [tableElements, filters]);

  const sortedTableElements = useMemo(() => {
    let sortableItems = [...filteredTableElements];
    if (sortConfig.key) {
      sortableItems.sort((a, b) => {
        const valA = getSortableValue(a, sortConfig.key);
        const valB = getSortableValue(b, sortConfig.key);
        if (valA == null && valB == null) return 0;
        if (valA == null) return sortConfig.direction === "ascending" ? 1 : -1;
        if (valB == null) return sortConfig.direction === "ascending" ? -1 : 1;
        if (typeof valA === "string" && typeof valB === "string") {
          return sortConfig.direction === "ascending"
            ? valA.localeCompare(valB)
            : valB.localeCompare(valA);
        }
        if (valA < valB) return sortConfig.direction === "ascending" ? -1 : 1;
        if (valA > valB) return sortConfig.direction === "ascending" ? 1 : -1;
        return 0;
      });
    }
    return sortableItems;
  }, [filteredTableElements, sortConfig]);

  // Pagination
  const totalPages = Math.ceil(sortedTableElements.length / pageSize);
  const pagedTableElements = useMemo(() => {
    const start = (page - 1) * pageSize;
    return sortedTableElements.slice(start, start + pageSize);
  }, [sortedTableElements, page, pageSize]);

  // Handle keyboard navigation (moved after totalPages calculation)
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (!tableWrapperRef.current) return;
      
      // Page Up/Down for pagination
      if (e.key === 'PageDown' && e.ctrlKey) {
        e.preventDefault();
        setPage(p => Math.min(totalPages, p + 1));
      } else if (e.key === 'PageUp' && e.ctrlKey) {
        e.preventDefault();
        setPage(p => Math.max(1, p - 1));
      }
      // Home/End for first/last page
      else if (e.key === 'Home' && e.ctrlKey) {
        e.preventDefault();
        setPage(1);
      } else if (e.key === 'End' && e.ctrlKey) {
        e.preventDefault();
        setPage(totalPages);
      }
    };

    const tableWrapper = tableWrapperRef.current;
    if (tableWrapper) {
      tableWrapper.addEventListener('keydown', handleKeyDown);
      return () => tableWrapper.removeEventListener('keydown', handleKeyDown);
    }
  }, [totalPages]);

  const columns = ["id", "label", "element_type"];

  return (
    <div className="e2etrace-data-table-container e2etrace-ui-panel">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <button
            onClick={() => exportToCSV(sortedTableElements, columns)}
            style={{
              padding: "0.4rem 1rem",
              borderRadius: 6,
              border: "1px solid #c0c6d1",
              background: "#f4f7fb",
              cursor: "pointer",
              fontSize: "0.85rem"
            }}
          >
            Export CSV
          </button>
          <span style={{ fontSize: "0.85rem", color: "#6c757d" }}>
            Showing {pagedTableElements.length} of {sortedTableElements.length} items
            <span 
              style={{ marginLeft: "8px", cursor: "help" }} 
              title="Keyboard shortcuts: Ctrl+PageUp/PageDown (navigate pages), Ctrl+Home/End (first/last page)"
            >
              ⌨️
            </span>
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <button 
            onClick={() => setPage(1)} 
            disabled={page === 1}
            style={{ padding: "0.3rem 0.6rem", border: "1px solid #dee2e6", background: "#fff", borderRadius: 4, cursor: page === 1 ? "not-allowed" : "pointer" }}
          >
            ««
          </button>
          <button 
            onClick={() => setPage(p => Math.max(1, p - 1))} 
            disabled={page === 1}
            style={{ padding: "0.3rem 0.6rem", border: "1px solid #dee2e6", background: "#fff", borderRadius: 4, cursor: page === 1 ? "not-allowed" : "pointer" }}
          >
            ‹
          </button>
          <span style={{ padding: "0.3rem 0.8rem", fontSize: "0.9rem", fontWeight: "500" }}>
            Page {page} of {totalPages}
          </span>
          <button 
            onClick={() => setPage(p => Math.min(totalPages, p + 1))} 
            disabled={page === totalPages}
            style={{ padding: "0.3rem 0.6rem", border: "1px solid #dee2e6", background: "#fff", borderRadius: 4, cursor: page === totalPages ? "not-allowed" : "pointer" }}
          >
            ›
          </button>
          <button 
            onClick={() => setPage(totalPages)} 
            disabled={page === totalPages}
            style={{ padding: "0.3rem 0.6rem", border: "1px solid #dee2e6", background: "#fff", borderRadius: 4, cursor: page === totalPages ? "not-allowed" : "pointer" }}
          >
            »»
          </button>
        </div>
      </div>
      {(!tableElements || tableElements.length === 0) ? (
        <p>No table data to display.</p>
      ) : (
        <div className="data-table-wrapper" ref={tableWrapperRef} style={{ position: 'relative' }} tabIndex={0}>
          <table>
            <thead>
              <tr>
                {columns.map((headerKey) => {
                  const isSorted = sortConfig.key === headerKey;
                  const sortSymbol = isSorted ? (sortConfig.direction === 'ascending' ? ' ▲' : ' ▼') : ' ↕';
                  return (
                    <th
                      key={headerKey}
                      className={`sortable ${isSorted ? sortConfig.direction : ""}`}
                      onClick={() => requestSort(headerKey)}
                      style={{ cursor: 'pointer', userSelect: 'none' }}
                    >
                      {headerKey.charAt(0).toUpperCase() + headerKey.slice(1).replace("_type", " Type")}
                      <span style={{ fontSize: '0.9em', marginLeft: 4 }}>{sortSymbol}</span>
                    </th>
                  );
                })}
                <th>Properties</th>
              </tr>
              <tr>
                {columns.map((headerKey) => (
                  <th key={headerKey + "-filter"}>
                    <input
                      type="text"
                      value={filters[headerKey]}
                      onChange={(e) => { setPage(1); setFilters((f) => ({ ...f, [headerKey]: e.target.value })); }}
                      placeholder={`Filter ${headerKey}`}
                      style={{
                        width: "90%",
                        padding: "0.2rem",
                        borderRadius: 4,
                        border: "1px solid #e0e4ea",
                      }}
                    />
                  </th>
                ))}
                <th></th>
              </tr>
            </thead>
            <tbody>
              {pagedTableElements.map((el, index) => {
                if (el.id === undefined || el.id === null) {
                  console.warn("Table element is missing an 'id' property. This may lead to non-unique keys.", el);
                }
                const uniqueKey = String(el.id ?? `el-index-${index}`);
                const isExpanded = expandedProperties.has(uniqueKey);
                const properties = { ...el };
                delete properties.id;
                delete properties.label;
                delete properties.element_type;
                delete properties.group;
                delete properties.source;
                delete properties.target;
                const hasProperties = Object.keys(properties).length > 0;
                const displayLabel = el.label || "N/A";
                const displayElementType = el.element_type || "Unknown";
                return (
                  <tr key={uniqueKey} onClick={() => onRowClick && onRowClick(el.id)} className={onRowClick ? "clickable" : ""}>
                    <td>{String(el.id)}</td>
                    <td>{displayLabel}</td>
                    <td>{displayElementType}</td>
                    <td className="properties-cell">
                      {hasProperties ? (
                        <>
                          <button
                            className="e2etrace-properties-toggle"
                            onClick={e => { e.stopPropagation(); togglePropertiesExpansion(uniqueKey); }}
                            aria-expanded={isExpanded}
                            aria-controls={`properties-${uniqueKey}`}
                          >
                            {isExpanded ? "−" : "+"}
                          </button>
                          <span style={{ marginLeft: "5px" }}>{isExpanded ? "Hide Details" : "Show Details"}</span>
                          {isExpanded && (
                            <ul id={`properties-${uniqueKey}`} className="e2etrace-properties-list">
                              {Object.entries(properties).map(([pKey, value]) => (
                                <li key={pKey}>
                                  <strong>{pKey}:</strong> {JSON.stringify(value, null, 2)}
                                </li>
                              ))}
                            </ul>
                          )}
                        </>
                      ) : (
                        "N/A"
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {showScrollTop && (
            <button
              onClick={scrollToTop}
              style={{
                position: 'absolute',
                bottom: '20px',
                right: '20px',
                width: '40px',
                height: '40px',
                borderRadius: '50%',
                background: '#007bff',
                color: 'white',
                border: 'none',
                cursor: 'pointer',
                boxShadow: '0 2px 10px rgba(0,0,0,0.2)',
                fontSize: '1.2rem',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                zIndex: 10,
                transition: 'all 0.3s ease'
              }}
              title="Scroll to top"
            >
              ↑
            </button>
          )}
        </div>
      )}
    </div>
  );
}