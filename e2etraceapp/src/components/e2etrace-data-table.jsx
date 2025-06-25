import React, { useState, useMemo } from "react";

// Helper to get a value for sorting, checking for properties on the root object or a nested 'data' object.
const getSortableValue = (item, key) => {
  if (item.hasOwnProperty(key)) return item[key];
  if (item.data && item.data.hasOwnProperty(key)) return item.data[key];
  return undefined;
};

export function E2ETraceDataTable({ tableElements, initialSortKey = "id" }) {
  const [sortConfig, setSortConfig] = useState({
    key: initialSortKey,
    direction: "ascending",
  });
  const [expandedProperties, setExpandedProperties] = useState(new Set());

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

  const sortedTableElements = useMemo(() => {
    if (!tableElements) return [];
    let sortableItems = [...tableElements];
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
  }, [tableElements, sortConfig]);

  return (
    <div className="e2etrace-data-table-container e2etrace-ui-panel"> {/* Corrected class name */}
      <h3>Data Table</h3>
      {(!tableElements || tableElements.length === 0) ? (
        <p>No table data to display.</p>
      ) : (
        <div className="data-table-wrapper">
          <table>
            <thead>
              <tr>
                {["id", "label", "element_type"].map((headerKey) => (
                  <th
                    key={headerKey}
                    className={`sortable ${
                      sortConfig.key === headerKey ? sortConfig.direction : ""
                    }`}
                    onClick={() => requestSort(headerKey)}
                  >
                    {headerKey.charAt(0).toUpperCase() +
                      headerKey.slice(1).replace("_type", " Type")}
                  </th>
                ))}
                <th>Properties</th>
              </tr>
            </thead>
            <tbody>
              {sortedTableElements.map((el) => {
                // Warn if ID is missing, as it's crucial for unique keys
                if (el.id === undefined || el.id === null) {
                  console.warn("Table element is missing an 'id' property. This may lead to non-unique keys.", el);
                }
                const uniqueKey = String(
                  el.id ||
                    `el-${el.element_type || 'unknown'}-${Math.random()
                      .toString(36)
                      .substr(2, 9)}`
                );
                const isExpanded = expandedProperties.has(uniqueKey);
                const properties =
                  el.properties || (el.data && el.data.properties) || {};
                const hasProperties = Object.keys(properties).length > 0;
                const displayLabel =
                  el.label || (el.data && el.data.label) || "N/A";
                const displayElementType =
                  el.element_type ||
                  (el.data && (el.data.source ? "Edge" : "Node")) ||
                  "Unknown";

                return (
                  <tr key={uniqueKey}>
                    <td>{String(el.id)}</td>
                    <td>{displayLabel}</td>
                    <td>{displayElementType}</td>
                    <td className="properties-cell">
                      {hasProperties ? (
                        <>
                          <button
                            className="e2etrace-properties-toggle"
                            onClick={() => togglePropertiesExpansion(uniqueKey)}
                            aria-expanded={isExpanded}
                            aria-controls={`properties-${uniqueKey}`}
                          >
                            {isExpanded ? "−" : "+"}
                          </button>
                          <span style={{ marginLeft: "5px" }}>
                            {isExpanded ? "Hide Details" : "Show Details"}
                          </span>
                          {isExpanded && (
                            <ul // Corrected class name
                              id={`properties-${uniqueKey}`}
                              className="e2etrace-properties-list"
                            >
                              {Object.entries(properties).map(
                                ([pKey, value]) => (
                                  <li key={pKey}>
                                    <strong>{pKey}:</strong>{" "}
                                    {JSON.stringify(value, null, 2)}
                                  </li>
                                )
                              )}
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
        </div>
      )}
    </div>
  );
}