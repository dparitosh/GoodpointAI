# Discovery Step 2 (DiscoveryResults) - Refactoring Plan
## World-Class UI Restructuring

---

## 📋 CURRENT ISSUES IDENTIFIED

### 1. **Redundancy & Cognitive Load**
- **KPI Strip** shows basic counts (10 files, 30 fields, 100% quality, 30 mappings, 124 records)
- **Source File Inventory** repeats file/field counts + quality
- **Data Quality Report** repeats field-level metrics again
- **Field Intelligence** shows individual field mappings separately
- **Sample data** shown at bottom with pagination

**Problem:** User must scan 4+ sections to understand data. No clear narrative flow.

---

### 2. **Missing Intelligence & Insights**
- No anomaly detection (unusual vs. usual patterns)
- No data health readiness assessment (unless user clicks separate button)
- No actionable recommendations based on quality gaps
- Field mappings show confidence % but no explanation of WHY
- No risk assessment (low completeness, high nulls, duplicates)
- Sample records shown raw — not contextualized with quality issues

---

### 3. **Poor Information Hierarchy**
- All 5 KPIs given equal visual weight (should prioritize Pass/Fail status)
- File inventory table lacks context (why should user care about specific rows?)
- Data quality table is only expanded on demand (collapsed by default) — key info hidden
- Field Intelligence buried below Data Quality section
- No clear "next steps" guidance

---

### 4. **Lack of Storytelling**
- UI jumps between file-level → field-level → sample → mapping views
- No connection between quality metrics and mapping confidence
- Null counts and duplicates shown in table but not explained or contextualized
- No "risk heat map" showing problematic fields at a glance

---

### 5. **End-User Unfriendliness**
- Technical jargon: "completeness %", "null values", "duplicate rows" 
- Users see "98% quality" but don't know: Is this good? What caused the 2% loss?
- Field mappings shown with confidence but no explanation of mapping logic
- Export options exist but no guidance on when to use CSV vs. Excel
- No "drill-down" capability: Click metric → see affected fields/records

---

## 🎯 REFACTORING GOALS

| Goal | Approach |
|------|----------|
| **Reduce Cognitive Load** | Consolidate related metrics; use progressive disclosure |
| **Add Intelligence** | Show AI insights first; anomalies before raw metrics |
| **Improve Hierarchy** | Status (PASS/WARNING/FAIL) prominently; detail on demand |
| **Tell a Story** | Flow: Health → Issues → Fields → Sample → Next Steps |
| **Add Context** | Explain metrics in plain English; show impact |
| **Enable Action** | Clear recommended actions; drill-down to problematic data |

---

## 🏗️ PROPOSED NEW STRUCTURE

### **Section 1: DISCOVERY STATUS CARD (Consolidated Overview)**
**Currently:** Scattered across KPI strip + insights + actions
**New:** Single unified status card showing:
- **Overall Status**: PASS ✅ | REVIEW ⚠️ | ATTENTION ❌
- **Readiness Score** (0-100): How ready is this data to migrate?
- **Key Metrics at a Glance**:
  - ✅ 10 files scanned | 30 fields | 124 sample records
  - ⚠️ 98% avg quality | 14 null values | 2 duplicate files
- **Quick Health Indicators** (traffic light icons):
  - 🟢 Files scanned: All (10/10)
  - 🟡 Data completeness: 98% (2% gap)
  - 🔴 Duplicate rows: 2 files affected
- **Recommended Next Action**: "Review 2 files with low completeness before mapping"

---

### **Section 2: DATA QUALITY HEALTH INSIGHTS (Risk-Based)**
**New section replacing scattered insights**
**Shows:**

#### **2a. Quality Scorecard**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 Data Quality Summary
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Overall Quality Score: 98%
├─ SODA Gate: ✅ PASS
├─ Completeness: 98% (3 fields <70%)
├─ Uniqueness: 89% (no excessive duplicates)
└─ Freshness: ✅ Current (uploaded today)

⚠️ ISSUES DETECTED:
├─ 2 fields with >10% nulls (bearing, records)
├─ 42 duplicate rows in 2 files (bearing exports)
└─ 3 fields with mixed type formats (needs transformation)

🟢 READY TO MIGRATE? YES, with warnings
   → Next: Review 3 problematic fields in "Data Quality Details"
```

#### **2b. Anomaly Detection**
```
🤖 ANOMALY DETECTION (AI-Powered Insights)

⚠️ UNUSUAL PATTERNS DETECTED:

1. "bearing" fields (JSON files)
   ├─ Status: EMPTY (0 records staged)
   └─ Action: Source file unreadable or incorrectly sampled
   
2. "manufacturer" field (Supplier entity)
   ├─ Pattern: Mixed case (NexPeria, NEXPERIA, nexperia)
   └─ Recommendation: Add UPPERCASE() transformation to mapping
   
3. "export" files (2023 vs 2022 variants)
   ├─ Pattern: Same schema, different record counts (40 vs 20 records)
   └─ Recommendation: These should be merged or deduplicated during mapping

💡 CONFIDENCE: HIGH (94% certainty on all 3)
```

---

### **Section 3: DATA QUALITY DETAILS (Expandable, Risk-Sorted)**
**Currently:** Large table, only expanded on demand, shown by file
**New:** Compact risk-based view

```
📋 FIELD-LEVEL QUALITY BREAKDOWN

[Filter by Risk] [Export CSV] [Export Excel Report]

HIGH RISK (3 fields):
┌─ bearing (JSON files) ─────────────────────────────
│  Quality: — (empty source) | Nulls: 0 | Completeness: N/A
│  🔴 ISSUE: Source not readable — JSON parsing failed?
│  ACTION: Check source file format or sampling config
│
├─ records (JSON files) ───────────────────────────────
│  Quality: — (empty source) | Nulls: 0 | Completeness: N/A
│  🔴 ISSUE: Source not readable — JSON parsing failed?
│  ACTION: Check source file format or sampling config
│
└─ manufacturer (Supplier) ────────────────────────────
   Quality: 98% | Nulls: 0 | Completeness: 100%
   ⚠️ WARNING: Mixed case values detected (3 variants)
   ACTION: Add UPPERCASE() transformation in Step 3 mapping
   Sample values: [nexperia] [NEXPERIA] [NexPeria] ...

MEDIUM RISK (4 fields):
...

LOW RISK (23 fields): ✅ All pass quality gates
```

---

### **Section 4: MAPPING INTELLIGENCE (Instead of Field Intelligence)**
**Currently:** Fields grouped by entity/role, individual mappings shown below
**New:** Mapping-focused view with confidence explained

```
🎯 FIELD MAPPING INSIGHTS

Detection Method: AI-powered semantic analysis + pattern matching
Confidence Breakdown:
├─ 3 STRONG matches (80%+): Name, entity type, AND data type all align
├─ 13 REVIEW matches (60-80%): Name similar; check data type compatibility  
└─ 14 WEAK matches (<60%): Partial similarity; manual review required

🟢 STRONG MATCHES (3) — Ready to Accept:
├─ id → part_number (95% confidence) [Unique Identifier]
├─ labels(n) → name (75% confidence, TRIM applied) [Name/Label]
└─ manufacturer → manufacturer_URL (50% confidence) [Path/URL]

🟡 REVIEW MATCHES (13) — Verify Before Proceeding:
├─ n.name → name (75% confidence) [Name/Label, requires TRIM]
├─ n.`_name` → name (75% confidence) [Name/Label, requires TRIM]
└─ [+10 more] ...

🔴 WEAK MATCHES (14) — Manual Mapping Required:
├─ complex_type fields (no high-confidence target)
├─ activity_method (ambiguous role detection)
└─ [+12 more] ...

💡 AI RECOMMENDATION: 
   "Proceed with Strong matches, manually review Medium tier before Step 3"
```

---

### **Section 5: SAMPLE DATA PREVIEW (Smart, Contextualized)**
**Currently:** Raw paginated table at bottom
**New:** Smart preview linked to quality issues

```
📊 SAMPLE DATA PREVIEW

Showing: ap242_tag_export (20 records) | [Change file]
Quality Status: ✅ 100% | Nulls: 0 | Duplicates: 0

[Table showing first 5 rows with quality context]

┌─────────┬──────────────┬──────────────┬────────────┐
│ id      │ name         │ type         │ quality    │
├─────────┼──────────────┼──────────────┼────────────┤
│ XmlTag  │ complexType  │ ✅ No nulls  │ ✅ PASS    │
│ element │ element      │ ✅ No nulls  │ ✅ PASS    │
│ ...     │ ...          │ ...          │ ...        │
└─────────┴──────────────┴──────────────┴────────────┘

⚠️ CONTEXT: These 5 rows are representative of the 20 total records.
            Click [View All 20 →] to see complete sample with quality flags.
```

---

### **Section 6: RECOMMENDED NEXT STEPS**
**New section** replacing generic "Agent-recommended actions"

```
🚀 RECOMMENDED NEXT STEPS

Based on Discovery analysis, here's what to do before mapping:

1️⃣  OPTIONAL: Examine 2 files with empty/unreadable source
    → If needed, adjust source connection in Step 1
    
2️⃣  REVIEW: Check 3 weak-confidence field mappings
    → These will require manual selection in Step 3
    
3️⃣  TRANSFORM: 1 field needs data normalization
    → manufacturer: Apply UPPERCASE() during mapping
    
4️⃣  PROCEED: 26/30 fields are confidence-ranked for mapping
    → Ready to continue to Step 3 (Mapping)

[Accept & Continue to Step 3] [Re-run Discovery] [Export Report]
```

---

## 🎨 UI/UX IMPROVEMENTS

### **1. Visual Hierarchy Fixes**
- Use color-coded risk levels consistently: 🟢 Pass | 🟡 Warning | 🔴 Fail
- Collapse low-risk sections by default; expand high-risk automatically
- Make status card prominent (top, larger font, icon-heavy)

### **2. Information Density**
- Group related metrics: Don't show files AND fields AND quality separately
- Use summary rows that expand on click
- Replace large tables with risk-prioritized lists

### **3. Storytelling Flow**
```
1. Status (Are we good to go?)
   ↓
2. Issues (What's broken?)
   ↓
3. Details (Show me the data)
   ↓
4. Actions (What do I do next?)
```

### **4. Accessibility**
- Explain every % in plain English (not just "98%")
- Define technical terms on hover (tooltip: "Completeness = % of non-null values")
- Provide context for numbers ("14 null values = 0.3% of total")

### **5. Actionability**
- Every metric should link to: Why this matters + What to do about it
- Use consistent CTAs: [Review] [Fix] [Accept] [Next]
- Show "blocked" vs. "unblocked" states clearly

---

## 📊 COMPONENT SPLIT RECOMMENDATION

Instead of one 1000+ line DiscoveryResults.jsx:

```
DiscoveryResults/
├─ DiscoveryStatusCard.jsx         (Overall health + readiness score)
├─ DataQualityInsights.jsx         (Quality metrics + anomalies)
├─ FieldQualityDetail.jsx          (Risk-sorted field breakdown)
├─ MappingIntelligence.jsx         (Confidence-tiered mappings)
├─ SampleDataPreview.jsx           (Linked to quality issues)
├─ RecommendedActions.jsx          (Next steps guidance)
└─ DiscoveryResults.css            (Unified styling)
```

---

## 🔧 IMPLEMENTATION PRIORITY

| Phase | Components | Effort |
|-------|-----------|--------|
| **1 (High Impact)** | DiscoveryStatusCard, RecommendedActions | Low |
| **2 (Core UX)** | DataQualityInsights, FieldQualityDetail | Medium |
| **3 (Polish)** | MappingIntelligence improvements, visual fixes | Medium |
| **4 (Optional)** | Component splitting, animation refinements | Low |

---

## ✅ SUCCESS CRITERIA (World-Class)

- [ ] User can understand data quality status in **<10 seconds** (vs. current 30+ sec)
- [ ] Risk issues are **highlighted automatically** (no table scanning needed)
- [ ] Mapping confidence is **explained in plain English** (not just %)
- [ ] Every metric has **actionable next steps** (not just "info")
- [ ] UI follows **progressive disclosure** (overview → details)
- [ ] Anomalies are **AI-powered, not manual** (detect unusual patterns)
- [ ] Data quality **flows naturally** to mapping step
- [ ] No **redundant information** (each metric shown once, in best context)
- [ ] Color coding is **consistent** across all sections (🟢🟡🔴)
- [ ] User feels **guided**, not overwhelmed by data

---
