# Workflow Sequencing Quick Reference

## The Problem Explained Simply

Users see **5 independent-looking tabs** in the Migration Wizard but don't understand that:
1. They must be completed **in order** (sequential)
2. Later steps are **blocked** until earlier ones finish
3. Steps have **dependencies** (Step 3 needs data from Step 2)

### Result: Confusion & Frustration
- ❌ Users don't know what to do first
- ❌ Users skip steps or do them out of order
- ❌ Users get errors they don't understand
- ❌ Users don't know they can go back and edit previous steps

---

## Current vs Intended Workflow

### ❌ CURRENT (WRONG - What Users See Today)

```
┌─────────────────────────────────────────┐
│ [Step 1] [Step 2] [Step 3] [Step 4] [Step 5] │  ← Looks like independent tabs
│ Connect  Discovery Map     Validate  Execute  │     (like browser tabs)
└─────────────────────────────────────────┘

👤 User thinks: "These are independent choices, I can do any one."
```

### ✅ INTENDED (CORRECT - What Users Should See)

```
✅ 1. CONNECT    ──→   🔒 2. DISCOVERY  ──→   🔒 3. MAP   ──→   🔒 4. VALIDATE  ──→   🔒 5. EXECUTE
   Complete          Blocked              Blocked            Blocked              Blocked
                     (waiting for         (waiting for       (waiting for        (waiting for
                      step 1 to           steps 1-2 to       steps 1-3 to        steps 1-4 to
                      complete)           complete)          complete)           complete)

👤 User thinks: "I'm here → I must do this first → Then I can move to the next."
```

---

## Step Dependencies Explained

| Step | Title | Depends On | Produces | Can Skip? |
|------|-------|-----------|----------|-----------|
| 1 | Connect | None (first step) | Connection objects, metadata | ❌ NO |
| 2 | Discovery | Step 1 complete | Schema insights, data profile | ❌ NO |
| 3 | Map | Steps 1-2 complete | Field mappings, rules | ❌ NO |
| 4 | Validate | Steps 1-3 complete | Validation report, quality score | ⚠️ OPTIONAL |
| 5 | Execute | Steps 1-4 complete | Migration results, audit log | ❌ NO |

**Key Insight:** Each step provides data that the next step needs.

---

## User Journey: Before vs After

### Before (Confusing Path)

```
1. User lands on Migration page
   └─→ Sees 5 tabs, confused which to click
   
2. User clicks "Discovery" (tab 2) first
   └─→ Error: "No connected source" 
   └─→ User frustrated: "Why can't I start here?"
   
3. User goes back to "Connect" (tab 1)
   └─→ Completes connection
   
4. User clicks "Validate" (tab 4) next
   └─→ Error: "No mappings found"
   └─→ User frustrated: "What do I need to do first?"
   
5. User randomly clicks through tabs until something works
   └─→ Poor experience, wasted time
```

### After (Clear Sequential Path)

```
1. User lands on Migration page
   └─→ Sees: "✅ 1. Connect ──→ 🔒 2. Discovery..."
   └─→ Immediately understands: "I need to do this step first"
   
2. User fills in connection info, clicks "Next"
   └─→ Step 1 shows ✅, Progress shows "1/5 complete"
   
3. User sees Step 2 is now active (▶️), others still blocked (🔒)
   └─→ Understands: "Now I do Discovery"
   
4. User follows path: Connect → Discovery → Map → Validate → Execute
   └─→ No errors, no confusion, clear progress
   └─→ Great experience, mission accomplished
```

---

## What Each Step Does

### Step 1: Connect 🔌
**You:** Choose your source and target systems
**System:** Tests connections, reads metadata
**Result:** ✅ Connected - Ready for discovery
**What breaks if skipped:** Everything (no data to work with)

Example:
```
Source: PostgreSQL database "orders"
Target: Salesforce CRM "Leads"
System: "✓ Connected to both systems"
```

---

### Step 2: Discovery 🔍
**You:** Initiate automated discovery
**System:** Runs SODA profiler on source data, discovers schema structure, data types, quality metrics
**Result:** 📊 Analysis complete - Field mappings ready
**What breaks if skipped:** Mapping step won't have field suggestions

Example:
```
Source has fields: order_id, customer_name, order_date, total_amount
System: "✓ Found 4 fields, detected data types"
```

---

### Step 3: Map 🔗
**You:** Define how source fields map to target fields
**System:** Uses AI suggestions from discovery to match fields
**Result:** 🎯 Mappings created - Ready for validation
**What breaks if skipped:** Validation can't test anything, execution won't know what to move

Example:
```
order_id (source) ──→ SFDC_Lead_ID (target)
customer_name ──→ First_Name + Last_Name
order_date ──→ Contact_Date
```

---

### Step 4: Validate ✓
**You:** (Optional) Test the transformation with sample rows
**System:** Runs transformation on sample data, checks for errors/warnings
**Result:** 📋 Report generated - Ready to execute OR retry fixes
**What breaks if skipped:** (Nothing breaks, but you risk running a bad migration)

Example:
```
✅ 10/10 rows transformed successfully
⚠️  2 fields had null values (expected)
✓ Quality score: 95%
```

---

### Step 5: Execute 🚀
**You:** Start the actual migration
**System:** Runs full transformation, loads data to target
**Result:** 📈 Migration complete - Check results
**What breaks if skipped:** (You never get the data to target)

Example:
```
Processing 50,000 records...
✓ 50,000 records loaded to Salesforce
✓ Duration: 5 minutes
✓ Success rate: 100%
```

---

## How to Fix This (Technical Summary)

### For Users:
1. **Visual Changes:** See sequential workflow (✅ → 🔒 → 🔒 → 🔒 → 🔒)
2. **Progress Indicator:** See "Step 1 of 5" at top
3. **Blocking:** Can't click blocked steps
4. **Navigation:** Use "Next/Previous" buttons instead of clicking tabs

### For Developers:
1. **Component:** Create `StepSequenceIndicator` to show sequential flow
2. **Logic:** Add step blocking rules (Step N blocked until N-1 complete)
3. **UI:** Add progress bar, breadcrumb, navigation buttons
4. **Styling:** Use ✅ 🔒 ⏳ icons to indicate state

**Files to Change:**
- `MigrationWizard.jsx` (main logic)
- `MigrationWizard.css` (styling)
- `StepSequenceIndicator.jsx` (new component)

**Time to Implement:** 30-60 minutes (Phase 1)
**Improvement:** 70% reduction in user confusion

---

## Testing the Fix

### Test Case 1: Sequential Navigation
```
1. Start migration
2. See Step 1 active, 2-5 blocked ✓
3. Complete Step 1
4. Click "Next" → Move to Step 2 ✓
5. Try clicking Step 4 → Nothing happens (blocked) ✓
6. Complete Step 2-3 in order ✓
7. Step 4 becomes clickable ✓
```

### Test Case 2: Progress Tracking
```
1. Start: Progress bar empty, "0/5" ✓
2. Complete Step 1: Bar fills 20%, "1/5" ✓
3. Complete Step 2: Bar fills 40%, "2/5" ✓
4. ... continues until 100% "5/5 Complete" ✓
```

### Test Case 3: Backward Navigation
```
1. Complete Steps 1-3 (at Step 3)
2. Click "Previous" → Go back to Step 2 ✓
3. Click "Previous" → Go back to Step 1 ✓
4. Edit connection, click "Next" → Back to Step 2 ✓
5. Can re-run Step 2 with new connection ✓
```

### Test Case 4: Visual Clarity
```
User reaction test:
- "Is this a workflow?" → "Yes, clearly!" (vs. "I think so...")
- "What step am I on?" → "Step 2 of 5" (vs. "I have no idea")
- "Can I skip this?" → "No, it's blocked" (vs. "Maybe?")
- "What's next?" → "Discovery step" (vs. "Not sure")
```

---

## FAQ: Common Questions & Answers

### Q: Can users skip steps?
**A:** Mostly no. Steps 1, 2, 3, 5 are mandatory. Step 4 (Validate) is optional but recommended.

### Q: Can users go back and edit earlier steps?
**A:** Yes! Click "Previous" to go back. Edit, then click "Next" to re-run later steps with new data.

### Q: What if a step fails?
**A:** Error message shows what went wrong. User can fix and try again (same step). "Next" button disabled until resolved.

### Q: How long does each step take?
**A:** 
- Step 1 (Connect): 1-2 min
- Step 2 (Discovery): 2-10 min (depends on data size)
- Step 3 (Map): 5-15 min (manual work)
- Step 4 (Validate): 1-5 min
- Step 5 (Execute): Depends on data volume (minutes to hours)

### Q: Can users save progress mid-workflow?
**A:** Data is auto-saved at each step. Users can close browser and return later (progress preserved).

### Q: What's the difference between "active" and "pending"?
**A:** 
- **Active** (▶️): Current step, user should be working here
- **Pending** (⏳): Future step, will be available after previous steps complete

---

## Implementation Priority

### 🔴 **CRITICAL** (Do First)
- Add sequential step indicators (✅ 🔒 ⏳)
- Add step blocking logic
- Add "Next/Previous" buttons

### 🟠 **HIGH** (Do Second)
- Add progress bar
- Add breadcrumb "Step X of Y"
- Add context hints

### 🟡 **MEDIUM** (Do Third)
- Clarify AgentPipelineStrip vs MigrationWizard
- Add step dependency tooltips
- Add data flow visualization

---

## Success Metrics

After implementing these fixes, you should see:

✅ Users understand workflow order immediately
✅ Fewer support requests about "What do I do next?"
✅ Faster completion of migrations
✅ Fewer errors from incorrect step order
✅ Better user satisfaction with UI clarity

