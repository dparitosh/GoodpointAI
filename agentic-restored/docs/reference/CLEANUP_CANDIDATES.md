# Cleanup Candidates (Implemented)

Goal: reduce root-level Markdown sprawl for release.

Status:
- Moves/archives are **completed**.
- **No deletions** were performed.
- Root-level stub files were left in place to avoid breaking existing links.

Date: 2026-01-11

## Proposed policy

- Keep a small set of **user-facing docs** (or redirect stubs) easy to find.
- Move deep technical references under `docs/reference/`.
- Move historical reports (bug/implementation trackers) to an `archive/` folder or keep them under `docs/reference/` if you want them shipped.

## Root-level Markdown inventory (agentic-restored/)

| File | Category | Recommendation |
|---|---|---|
| `QUICK_START.md` | User-facing | Keep (already exists); add pointer to `docs/` (done) |
| `INSTALLATION.md` | User-facing | Keep as legacy; pointer to `docs/` (done) |
| `README-WINDOWS.md` | User-facing | Keep as legacy; pointer to `docs/` (done) |
| `BUSINESS_USER_GUIDE.md` | User-facing | Moved to `docs/user-guide/` + stub left |
| `MANUAL_TESTING_GUIDE.md` | Engineering | Moved to `docs/reference/` + stub left |
| `DATA_LINEAGE_QUICK_START.md` | Reference | Moved to `docs/reference/` + stub left |
| `EXTERNAL_INTEGRATIONS_QUICK_START.md` | Reference | Moved to `docs/reference/` + stub left |
| `EXTERNAL_INTEGRATIONS_API_REFERENCE.md` | Reference | Moved to `docs/reference/` + stub left |
| `EXTERNAL_INTEGRATIONS_IMPLEMENTATION_SUMMARY.md` | Engineering | Moved to `docs/reference/` + stub left |
| `ETL_Architecture_Summary.md` | Engineering | Moved to `docs/reference/` + stub left |
| `ARCHITECTURE_REFERENCE_RECIPE_MODERN.md` | Engineering | Moved to `docs/reference/` + stub left |
| `ARCHITECTURE_REFERENCE_RECIPE_MODERN_TRACKER.md` | Engineering | Archived to `docs/reference/archive/reports/` + stub left |
| `PAGE_REQUIREMENTS_SPECIFICATIONS.md` | Reference | Moved to `docs/reference/` + stub left |
| `GRAPH_FEATURES_LOW_LEVEL_REQUIREMENTS.md` | Engineering | Moved to `docs/reference/` + stub left |
| `GRAPH_FEATURES_IMPLEMENTATION_SUMMARY.md` | Engineering | Moved to `docs/reference/` + stub left |
| `SODA_DATA_QUALITY_DASHBOARD.md` | Reference | Moved to `docs/reference/` + stub left |
| `SPARK_NEO4J_OPENCYPHER_RECIPE.md` | Engineering | Moved to `docs/reference/` + stub left |
| `XSTATE_VISUALIZER_DEMO_GUIDE.md` | Reference | Moved to `docs/reference/` + stub left |
| `XSTATE_VISUALIZER_COMPLETION.md` | Engineering | Archived to `docs/reference/archive/xstate/` + stub left |
| `WORLD_CLASS_XSTATE_VISUALIZER_REPORT.md` | Engineering | Archived to `docs/reference/archive/xstate/` + stub left |
| `NAVIGATION_REDESIGN_REPORT.md` | Engineering | Archived to `docs/reference/archive/reports/` + stub left |
| `TASK_COMPLETION_VERIFICATION.md` | Engineering | Archived to `docs/reference/archive/tasks/` + stub left |
| `TASK_1_DATA_LINEAGE_IMPLEMENTATION_REPORT.md` | Engineering | Archived to `docs/reference/archive/tasks/` + stub left |
| `BUG_TRACKER.md` | Engineering | Archived to `docs/reference/archive/reports/` + stub left |
| `BUG_FIXES_REPORT.md` | Engineering | Archived to `docs/reference/archive/reports/` + stub left |
| `BUGS_ANALYSIS_REPORT.md` | Engineering | Archived to `docs/reference/archive/reports/` + stub left |
| `COMPREHENSIVE_BUG_REPORT.md` | Engineering | Archived to `docs/reference/archive/reports/` + stub left |
| `FINAL_IMPLEMENTATION_REPORT.md` | Engineering | Archived to `docs/reference/archive/reports/` + stub left |
| `CAUSE_EFFECT_ANALYSIS.md` | Engineering | Archived to `docs/reference/archive/reports/` + stub left |
| `INSTALLATION_ISSUES_REPORT.md` | Engineering | Archived to `docs/reference/archive/reports/` + stub left |
| `INSTALLATION_VALIDATION_REPORT.md` | Engineering | Archived to `docs/reference/archive/reports/` + stub left |
| `PEST_CONTROL_CHECKLIST.md` | Other | Archived to `docs/reference/archive/misc/` + stub left |
| `PEST_CONTROL_SUMMARY.md` | Other | Archived to `docs/reference/archive/misc/` + stub left |

## Next steps (optional)

- If you want a stricter release surface, we can also move these remaining root docs (they are still user-facing/reference today):
	- `BUSINESS_USER_GUIDE.md`
	- `DATA_LINEAGE_QUICK_START.md`
	- `EXTERNAL_INTEGRATIONS_*`
	- `SODA_DATA_QUALITY_DASHBOARD.md`
	- `XSTATE_VISUALIZER_DEMO_GUIDE.md`

- If you want a minimal repo root, we can replace those with stubs too and point everything into `docs/`.
