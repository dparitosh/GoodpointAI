# IXDF Expert Review: Migration Wizard Steps 2 & 3

**Reviewer**: IXDF UX Expert  
**Date**: April 20, 2026  
**Scope**: Step 2 (Discovery) & Step 3 (Field Mapping)  
**URL**: `http://127.0.0.1:5174/#/migration?step=2` and `?step=3`

---

## Executive Summary

**Overall Assessment**: Steps 2 and 3 demonstrate good technical architecture but suffer from **cognitive overload**, **inconsistent information hierarchy**, and **unclear workflows**. Critical UX issues prevent users from understanding what actions to take and in what order.

### Severity Breakdown
- 🔴 **Critical Issues**: 4
- 🟡 **Major Issues**: 6  
- 🟢 **Minor Issues**: 3

**Priority**: Address critical issues before user testing.

---

## 🔍 Step 2: Discovery Agent - Detailed Analysis

### ✅ What Works Well

1. **Clear Primary Actions**
   - Two well-labeled buttons: "Run Discovery" and "Accept Discovery"
   - Distinct visual hierarchy with primary/success button styling
   - Loading states indicated ("Running Discovery...")

2. **Progressive Disclosure of Results**
   - Results only appear after discovery runs
   - Panels are visually separated with proper spacing
   - Conditional rendering prevents UI clutter

3. **Data Quality Integration**
   - SODA quality gate prominently displayed
   - Score percentage, status, and issue count clearly shown
   - Color-coded severity (success/warning)

### 🔴 Critical Issues

#### Issue 2.1: Unclear Workflow Sequence
**IXDF Principle Violated**: Visibility of System Status

**Problem**: Users don't understand the required action sequence:
```
1. Click "Run Discovery" → Wait for results
2. Review results → Understand quality metrics
3. Click "Accept Discovery" → Enable Next button
```

**Current UI**:
```
[Run Discovery]  [Accept Discovery]
```

**Why it's confusing**:
- Both buttons shown simultaneously with no indication of order
- "Accept Discovery" is enabled before discovery runs (disabled state not obvious)
- No visual indicator showing "Step 1 → Step 2" flow

**Evidence from Code** (lines 1214-1227):
```jsx
<button className="btn btn-primary" onClick={runDiscovery}>
  Run Discovery
</button>
<button className="btn btn-success" onClick={acceptDiscovery}
  disabled={wizardData.discoveryStatus !== 'completed' || wizardData.discoveryAccepted}>
  Accept Discovery
</button>
```

**Fix Required**:
```jsx
{/* Show sequential numbering and helper text */}
<div className="discovery-actions">
  <div className="action-group">
    <span className="step-number">1</span>
    <button className="btn btn-primary" onClick={runDiscovery}>
      <i className="fas fa-search" /> Run Discovery
    </button>
    <p className="action-help">Analyze data and generate quality insights</p>
  </div>
  
  {wizardData.discoveryStatus === 'completed' && (
    <div className="action-group">
      <span className="step-number">2</span>
      <button className="btn btn-success" onClick={acceptDiscovery}>
        <i className="fas fa-check" /> Accept & Continue
      </button>
      <p className="action-help">Review results above, then accept to proceed</p>
    </div>
  )}
</div>
```

**Impact**: 🔴 Users abandon workflow due to confusion about next action.

---

#### Issue 2.2: Overwhelming Information Density
**IXDF Principle Violated**: Miller's Law (7±2 items in working memory)

**Problem**: Too many panels/sections displayed simultaneously after discovery:
1. Discovery run ID meta box
2. SODA quality insights card
3. Detected issues card (if any)
4. Recommendations card (if any)
5. Inferred source fields panel
6. Sample records table
7. Mapping hints panel
8. "View full discovery catalogue" link

**8 distinct information blocks** — exceeds cognitive capacity.

**Evidence from Code**: Lines 1230-1329 show 8 sequential panels with no prioritization.

**Fix Required**: Use progressive disclosure with collapsible sections:

```jsx
<div className="discovery-results-summary">
  {/* Primary insight - always visible */}
  <div className="discovery-insight featured">
    <div className="insight-icon">🛡️</div>
    <div className="insight-content">
      <h4>Data Quality Gate (SODA)</h4>
      <div className="quality-score large">
        <span className="score-value">100%</span>
        <span className="score-label">PASS</span>
      </div>
      <p>{sodaResult.issues_count} issues detected</p>
    </div>
  </div>

  {/* Secondary details - collapsible */}
  <details className="discovery-details-section">
    <summary>
      <i className="fas fa-columns" /> Inferred Source Fields 
      <span className="badge">{fields.length}</span>
    </summary>
    <div className="ddp-chips">{/* field chips */}</div>
  </details>

  <details className="discovery-details-section">
    <summary>
      <i className="fas fa-table" /> Sample Data Preview
      <span className="badge">{sampleRows.length} records</span>
    </summary>
    <table className="ddp-table">{/* sample table */}</table>
  </details>

  <details className="discovery-details-section" open>
    <summary>
      <i className="fas fa-random" /> AI Mapping Suggestions
      <span className="badge">{suggestions.length}</span>
    </summary>
    <div className="ddp-mappings">{/* mapping hints */}</div>
  </details>
</div>
```

**Impact**: 🔴 Users experience cognitive overload, miss important quality issues.

---

#### Issue 2.3: Missing Success Confirmation
**IXDF Principle Violated**: Feedback & Visibility

**Problem**: After clicking "Accept Discovery", no confirmation that action succeeded.

**Current Behavior**:
- Button text changes to "Discovery Accepted"
- Button becomes disabled
- **No toast notification**
- **No visual celebration/checkmark**
- **Next button silently enables**

**Expected Behavior** (E-commerce checkout analogy):
```
✅ Discovery Accepted!
   Your quality score: 100% (PASS)
   4 fields discovered
   4 mapping suggestions ready

   [Proceed to Mapping →]
```

**Fix Required**:
```jsx
const acceptDiscovery = useCallback(() => {
  setWizardData(prev => ({
    ...prev,
    discoveryAccepted: true
  }));
  
  // Show success toast
  showToast({
    type: 'success',
    title: 'Discovery Accepted!',
    message: `Quality score: ${scorePct}% (${status}). Ready to proceed to field mapping.`,
    duration: 5000
  });
  
  // Auto-advance option
  setTimeout(() => {
    if (autoAdvance) nextStep();
  }, 2000);
}, []);
```

**Impact**: 🔴 Users uncertain if action worked, don't notice "Next" button enabled.

---

### 🟡 Major Issues

#### Issue 2.4: Discovery Run ID Placement
**Problem**: Run ID shown in small gray box, easy to miss, but critical for support/debugging.

**Current** (line 1230):
```jsx
<div className="discovery-meta">
  Discovery run: <strong>{wizardData.discoveryRunId}</strong>
</div>
```

**Fix**: Move to page header as persistent reference:
```jsx
<div className="step-header">
  <div className="step-title">
    <h3>Discovery Agent</h3>
    {wizardData.discoveryRunId && (
      <span className="run-id-badge" title="Copy Run ID">
        <i className="fas fa-fingerprint" /> {wizardData.discoveryRunId.slice(0, 8)}...
        <button onClick={() => copyToClipboard(discoveryRunId)}>
          <i className="fas fa-copy" />
        </button>
      </span>
    )}
  </div>
  <p className="step-description">...</p>
</div>
```

**Impact**: 🟡 Support requests delayed due to missing run IDs.

---

#### Issue 2.5: Sample Data Table Lacks Context
**Problem**: Sample records shown with no explanation of source or purpose.

**Current** (lines 1271-1297):
- Table shows 5 rows
- Header says "synthetic" vs "live source" (unclear what this means)
- No explanation why sample is shown

**Fix**: Add contextual help:
```jsx
<div className="discovery-data-panel">
  <div className="ddp-header">
    <i className="fas fa-table" /> Sample Data Preview
    <span className="ddp-badge">{sampleRows.length} of {total}</span>
    <span className="ddp-source-tag">
      {stagedFrom === 'source' ? '✓ Live Data' : '⚠️ Mock Data'}
    </span>
  </div>
  <p className="panel-help">
    {stagedFrom === 'source' 
      ? 'Preview of actual source data for validation'
      : 'Synthetic data generated for testing (configure source connection for real data)'}
  </p>
  <div className="ddp-table-wrap">...</div>
</div>
```

**Impact**: 🟡 Users confused whether they're seeing real or fake data.

---

#### Issue 2.6: Mapping Hints Disconnected from Step 3
**Problem**: Mapping hints shown in Step 2 but not explained how they're used in Step 3.

**Current** (lines 1312-1318):
```jsx
<span className="ddp-note">Carry over to Step 3</span>
```

**Issue**: "Carry over" is vague — how? Automatically? Manually?

**Fix**: Add explicit preview + action:
```jsx
<div className="ddp-header">
  <i className="fas fa-random" /> AI Mapping Suggestions
  <span className="ddp-badge">{suggestions.length}</span>
</div>
<div className="ddp-mappings">...</div>
<div className="mapping-preview-actions">
  <p className="preview-note">
    <i className="fas fa-info-circle" /> These suggestions will automatically populate Step 3 (Field Mapping)
  </p>
  <button className="btn btn-sm btn-secondary" onClick={() => setCurrentStep(3)}>
    <i className="fas fa-eye" /> Preview in Mapping Editor
  </button>
</div>
```

**Impact**: 🟡 Users don't understand connection between steps, re-enter mappings manually.

---

### 🟢 Minor Issues

#### Issue 2.7: No Empty State Guidance
**Current placeholder** (line 1247):
```jsx
<p className="placeholder">
  Run Discovery to generate insights. You must accept discovery before continuing.
</p>
```

**Better Empty State**:
```jsx
<div className="empty-state">
  <div className="empty-state-icon">
    <i className="fas fa-search fa-3x" />
  </div>
  <h4>Ready to Discover Your Data</h4>
  <p>Click "Run Discovery" to:</p>
  <ul className="benefits-list">
    <li><i className="fas fa-check" /> Analyze data quality with SODA</li>
    <li><i className="fas fa-check" /> Detect field types automatically</li>
    <li><i className="fas fa-check" /> Generate AI mapping suggestions</li>
    <li><i className="fas fa-check" /> Preview sample records</li>
  </ul>
  <button className="btn btn-primary btn-lg" onClick={runDiscovery}>
    <i className="fas fa-rocket" /> Start Discovery
  </button>
</div>
```

---

## 🗺️ Step 3: Field Mapping - Detailed Analysis

### ✅ What Works Well

1. **AI Assistance Prominent**
   - "Get AI Suggestions" button clearly visible
   - Suggestions panel well-formatted with confidence scores
   - "Apply All" quick action available

2. **Template Support**
   - Dropdown allows quick template application
   - Reduces manual mapping effort

3. **Field Reference Panels**
   - Source and target fields shown side-by-side
   - Counts displayed (helpful for validation)

### 🔴 Critical Issues

#### Issue 3.1: Overwhelming Visual Complexity
**IXDF Principle Violated**: Hick's Law (decision time increases with choices)

**Problem**: Users see 6 major UI sections simultaneously:
1. Discovery introspect panel (with JSON dump)
2. Sample preview panel (with JSON dump)
3. Help alert
4. Mapping tools row (buttons + template dropdown)
5. Available fields reference (2 columns)
6. AI suggestions panel
7. Current mappings table

**Evidence from Code**: Lines 1335-1550 render all sections at once.

**Critical Flaw**: **RAW JSON DUMPS** in production UI (lines 1355-1372):
```jsx
<pre className="schema-preview">
  {JSON.stringify(wizardData.discoveryIntrospect, null, 2)}
</pre>
<pre className="schema-preview">
  {JSON.stringify(wizardData.discoverySample.records.slice(0, 8), null, 2)}
</pre>
```

**Why This is Terrible UX**:
- JSON is for developers, not end users
- Takes up huge vertical space
- Unreadable for non-technical users
- Violates "recognition over recall" principle

**Fix Required**: REMOVE JSON dumps entirely or hide in collapsible debug panel:
```jsx
{process.env.NODE_ENV === 'development' && (
  <details className="debug-panel">
    <summary>🛠️ Developer Debug Info</summary>
    <pre>{JSON.stringify(discoveryIntrospect, null, 2)}</pre>
  </details>
)}
```

**Replace introspect panel with visual summary**:
```jsx
<div className="discovery-summary-card">
  <div className="summary-header">
    <i className="fas fa-microscope" /> Discovery Results
    <span className="run-badge">{discoveryRunId.slice(0, 8)}</span>
  </div>
  <div className="summary-metrics">
    <div className="metric">
      <span className="metric-value">{inferredFields.length}</span>
      <span className="metric-label">Fields Detected</span>
    </div>
    <div className="metric">
      <span className="metric-value">{scorePct}%</span>
      <span className="metric-label">Quality Score</span>
    </div>
    <div className="metric">
      <span className="metric-value">{suggestions.length}</span>
      <span className="metric-label">AI Suggestions</span>
    </div>
  </div>
  <a href="#/data-discovery" className="view-details-link">
    View Full Discovery Report →
  </a>
</div>
```

**Impact**: 🔴 **CRITICAL** — Non-technical users completely blocked by JSON.

---

#### Issue 3.2: Unclear Mapping Workflow
**IXDF Principle Violated**: User Control & Freedom

**Problem**: Users have 4 different ways to create mappings, with no guidance on which to use:
1. Click field tags in "Available Fields" panel
2. Click "Get AI Suggestions" → Click individual "+ buttons
3. Click "Apply All" in AI suggestions
4. Click "Add Mapping" at bottom of table → Manual entry
5. Apply template from dropdown

**No explanation of pros/cons** of each method.

**Fix**: Add step-by-step wizard within Step 3:

```jsx
<div className="mapping-workflow-guide">
  <h4>How to Create Mappings</h4>
  <div className="workflow-steps">
    <div className="workflow-step recommended">
      <span className="step-badge">Recommended</span>
      <div className="step-content">
        <h5><i className="fas fa-magic" /> 1. Use AI Suggestions</h5>
        <p>Let AI analyze your data and suggest intelligent mappings</p>
        <button className="btn btn-sm btn-primary" onClick={getAIMappingSuggestions}>
          Get AI Suggestions
        </button>
      </div>
    </div>
    <div className="workflow-step">
      <div className="step-content">
        <h5><i className="fas fa-file-alt" /> 2. Apply Template</h5>
        <p>Use pre-configured mappings for common scenarios</p>
        <select onChange={applyTemplate}>
          <option>Select template...</option>
          {/* templates */}
        </select>
      </div>
    </div>
    <div className="workflow-step">
      <div className="step-content">
        <h5><i className="fas fa-hand-pointer" /> 3. Manual Mapping</h5>
        <p>Click field tags or use table rows to map individually</p>
      </div>
    </div>
  </div>
</div>
```

**Impact**: 🔴 Users waste time trying different methods, create duplicate mappings.

---

### 🟡 Major Issues

#### Issue 3.3: Field Tag Interaction Unclear
**Problem**: Field tags look clickable but don't clearly indicate what happens on click.

**Current** (lines 1433-1437):
```jsx
<span className="field-tag source" 
  title="Click to add mapping" 
  onClick={() => addFieldMapping({...})}>
  {field}
</span>
```

**Issues**:
- Tooltip only visible on hover
- No cursor change to `pointer`
- Action result (adding table row) happens off-screen

**Fix**: Make interaction obvious:
```jsx
<button 
  className="field-tag source interactive"
  onClick={() => {
    addFieldMapping({ source_field: field, target_field: '', transformation: null });
    scrollToMappingTable();
    highlightNewRow();
  }}
  title="Click to start mapping this field"
>
  <i className="fas fa-plus-circle" />
  {field}
</button>

{/* CSS */}
.field-tag.interactive {
  cursor: pointer;
  transition: all 0.2s;
}
.field-tag.interactive:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(0,0,0,0.2);
  background: var(--accent-color);
}
```

**Impact**: 🟡 Users don't discover field tag shortcut, resort to manual table entry.

---

#### Issue 3.4: AI Suggestions Not Persistent
**Problem**: If user navigates away and returns to Step 3, AI suggestions are lost.

**Evidence**: `aiSuggestedMappings` stored in local component state, not persisted.

**Fix**: Store in wizard data with persistence:
```jsx
// Load from localStorage on mount
useEffect(() => {
  const saved = localStorage.getItem(`wizard_${workflowName}_step3`);
  if (saved) {
    const data = JSON.parse(saved);
    setWizardData(prev => ({
      ...prev,
      aiSuggestedMappings: data.aiSuggestedMappings,
      fieldMappings: data.fieldMappings
    }));
  }
}, []);

// Save on change
useEffect(() => {
  if (wizardData.aiSuggestedMappings.length > 0) {
    localStorage.setItem(`wizard_${workflowName}_step3`, JSON.stringify({
      aiSuggestedMappings: wizardData.aiSuggestedMappings,
      fieldMappings: wizardData.fieldMappings
    }));
  }
}, [wizardData.aiSuggestedMappings, wizardData.fieldMappings]);
```

**Impact**: 🟡 Users lose work if they navigate to review discovery results.

---

#### Issue 3.5: Transformation Input Too Freeform
**Problem**: Transformation field is text input with only placeholder hint: "e.g., UPPER, TRIM"

**Current** (lines 1525-1535):
```jsx
<input 
  type="text" 
  value={mapping.transformation || ''}
  placeholder="e.g., UPPER, TRIM"
  onChange={...}
/>
```

**Issues**:
- No validation
- No autocomplete
- Users don't know available functions
- Typos cause runtime errors

**Fix**: Use dropdown with common transformations:
```jsx
<select 
  value={mapping.transformation || ''}
  onChange={...}
  className="transformation-select"
>
  <option value="">None</option>
  <optgroup label="String">
    <option value="UPPER">UPPER - Convert to uppercase</option>
    <option value="LOWER">LOWER - Convert to lowercase</option>
    <option value="TRIM">TRIM - Remove whitespace</option>
    <option value="CONCAT">CONCAT - Combine fields</option>
  </optgroup>
  <optgroup label="Numeric">
    <option value="ROUND">ROUND - Round decimal</option>
    <option value="ABS">ABS - Absolute value</option>
  </optgroup>
  <optgroup label="Date">
    <option value="DATE_FORMAT">DATE_FORMAT - Format date</option>
    <option value="NOW">NOW - Current timestamp</option>
  </optgroup>
  <option value="CUSTOM">⚙️ Custom Expression...</option>
</select>

{mapping.transformation === 'CUSTOM' && (
  <input 
    type="text" 
    placeholder="Enter custom transformation"
    className="custom-transformation-input"
  />
)}
```

**Impact**: 🟡 Invalid transformations cause pipeline failures at execution time.

---

#### Issue 3.6: No Mapping Validation
**Problem**: Users can create invalid mappings (e.g., same source mapped to multiple targets) with no warning.

**Fix**: Real-time validation with visual indicators:
```jsx
const validateMappings = (mappings) => {
  const errors = [];
  const sourceFields = mappings.map(m => m.source_field);
  const duplicates = sourceFields.filter((f, i) => sourceFields.indexOf(f) !== i);
  
  if (duplicates.length > 0) {
    errors.push({
      type: 'warning',
      message: `Duplicate source fields: ${duplicates.join(', ')}`
    });
  }
  
  const emptyTargets = mappings.filter(m => !m.target_field);
  if (emptyTargets.length > 0) {
    errors.push({
      type: 'error',
      message: `${emptyTargets.length} mappings missing target field`
    });
  }
  
  return errors;
};

// In render:
{mappingErrors.length > 0 && (
  <div className="mapping-validation-panel">
    <h5><i className="fas fa-exclamation-triangle" /> Validation Errors</h5>
    {mappingErrors.map((error, i) => (
      <div key={i} className={`validation-error ${error.type}`}>
        {error.message}
      </div>
    ))}
  </div>
)}
```

**Impact**: 🟡 Invalid mappings cause execution failures.

---

### 🟢 Minor Issues

#### Issue 3.7: Table Headers Not Descriptive
**Current headers**: "Source Field", "Target Field", "Transformation", "Actions"

**Better headers** with help icons:
```jsx
<th>
  Source Field 
  <HelpTooltip content="The field name from your source system" />
</th>
<th>
  Target Field 
  <HelpTooltip content="The field name in your target system" />
</th>
<th>
  Transformation
  <HelpTooltip content="Optional data transformation (e.g., UPPER, TRIM, DATE_FORMAT)" />
</th>
```

---

## 📊 Prioritized Fixes (Implementation Order)

### Sprint 1: Critical UX Blockers

1. **Remove JSON Dumps from Step 3** (Issue 3.1)
   - Replace with visual summary cards
   - Hide raw JSON in dev-only debug panel
   - **Effort**: 2 hours | **Impact**: Critical

2. **Add Sequential Action Flow to Step 2** (Issue 2.1)
   - Number the actions (1. Run Discovery, 2. Accept)
   - Show "Accept" button only after completion
   - Add helper text explaining each action
   - **Effort**: 3 hours | **Impact**: Critical

3. **Add Success Confirmation to "Accept Discovery"** (Issue 2.3)
   - Toast notification with summary
   - Visual checkmark/celebration
   - Optional auto-advance to Step 3
   - **Effort**: 2 hours | **Impact**: Critical

4. **Add Mapping Workflow Guide to Step 3** (Issue 3.2)
   - Step-by-step wizard showing 3 methods
   - Recommend AI suggestions first
   - **Effort**: 4 hours | **Impact**: Critical

### Sprint 2: Major Improvements

5. **Implement Collapsible Sections in Step 2** (Issue 2.2)
   - Use `<details>` elements for secondary info
   - Keep quality score always visible
   - **Effort**: 3 hours | **Impact**: High

6. **Replace Transformation Text Input with Dropdown** (Issue 3.5)
   - Predefined transformation functions
   - Grouped by category (String, Numeric, Date)
   - Custom option for advanced users
   - **Effort**: 3 hours | **Impact**: High

7. **Add Real-time Mapping Validation** (Issue 3.6)
   - Check for duplicates, empty fields, conflicts
   - Show validation panel with errors
   - **Effort**: 4 hours | **Impact**: High

8. **Improve Field Tag Interactions** (Issue 3.3)
   - Add `+` icon to clickable tags
   - Scroll to table row after click
   - Highlight newly added row
   - **Effort**: 2 hours | **Impact**: Medium

### Sprint 3: Polish & Persistence

9. **Add Workflow State Persistence** (Issue 3.4)
   - LocalStorage for AI suggestions
   - Save/restore on page reload
   - **Effort**: 2 hours | **Impact**: Medium

10. **Improve Empty States** (Issue 2.7)
    - Benefits list for discovery
    - Visual empty state graphics
    - **Effort**: 2 hours | **Impact**: Low

---

## 🎯 IXDF Principles Summary

| Principle | Step 2 Grade | Step 3 Grade | Key Issue |
|-----------|--------------|--------------|-----------|
| **Visibility of System Status** | C | D | No clear workflow sequence |
| **User Control & Freedom** | B | C | Too many unmapped options |
| **Consistency & Standards** | B | C | Inconsistent interaction patterns |
| **Error Prevention** | C | D | No validation, JSON dumps |
| **Recognition Over Recall** | B | D | Must remember transformation syntax |
| **Flexibility & Efficiency** | A | B | Good AI assistance, but slow manual path |
| **Aesthetic & Minimalist** | C | F | Information overload, JSON dumps |
| **Help Users Recover from Errors** | C | C | Generic error messages |

**Overall UX Maturity**: **C-** (Below Average)

---

## 🚀 Quick Wins (< 1 hour each)

1. Remove JSON dumps from Step 3 production build
2. Add "Discovery Accepted!" toast notification
3. Change "Carry over to Step 3" to "These suggestions will auto-populate Step 3"
4. Add `cursor: pointer` to clickable field tags
5. Move discovery run ID to page header

---

## 📖 References

- **IXDF - Interaction Design**: https://www.interaction-design.org/literature/topics/interaction-design
- **Nielsen's 10 Usability Heuristics**: https://www.nngroup.com/articles/ten-usability-heuristics/
- **Miller's Law (Chunking)**: https://www.nngroup.com/articles/chunking/
- **Hick's Law (Choice Paralysis)**: https://www.interaction-design.org/literature/article/hick-s-law-making-the-choice-easier-for-users

---

**Next Steps**: Schedule stakeholder review to prioritize Sprint 1 critical fixes before next user testing session.
