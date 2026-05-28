# Root Cause Analysis: Recurring WATCH_FOLDERS Error (4 Releases)

## Executive Summary

**Problem:** The application fails to start with `pydantic_settings.exceptions.SettingsError: error parsing value for field "watch_folders"` in the last 4 releases.

**Root Cause:** Pydantic environment variable parsing attempts JSON deserialization on an unset/empty `WATCH_FOLDERS` environment variable, which causes `json.decoder.JSONDecodeError`.

**Status:** This is a **deployment environment configuration issue**, not a code bug.

---

## Error Details

### Stack Trace Analysis

```
json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
    ↓
pydantic_settings.exceptions.SettingsError: error parsing value for field 
"watch_folders" from source "EnvSettingsSource"
    ↓
FileSystemConfig.__init__() @ core/external_config.py:279
```

### Error Flow

1. **Application Start** → `core/external_config.py:279`
   ```python
   filesystem_config = FileSystemConfig()  # Module-level initialization
   ```

2. **Pydantic Field Detection**
   ```python
   watch_folders: List[str] = Field(
       default_factory=lambda: ["./data/watch"],
       validation_alias="WATCH_FOLDERS"
   )
   ```

3. **Environment Variable Processing**
   - Pydantic checks if `WATCH_FOLDERS` environment variable exists
   - Field type is `List[str]` (complex type)
   - Pydantic **must** deserialize it from JSON
   - Gets empty string or no value
   - Tries: `json.loads("")` → Error!

4. **Validation Error**
   - Calls field_validator `parse_watch_folders` 
   - But **validator never runs** because JSON parsing fails first
   - Exception propagates up

---

## Why It's Recurring

### Root Causes in Order of Impact

#### 1. **Environment Variable Not Set in Deployment** (Primary)
In production deployments:
- `.env` file is **gitignored** (by design - contains secrets)
- `WATCH_FOLDERS` environment variable is NOT set in deployment configs
- Application tries to parse `None` or empty value from environment

**Affected Deployments:**
- Docker containers without `WATCH_FOLDERS` env var
- Windows Service installations
- CI/CD pipelines without environment setup
- Cloud deployments (AWS, Azure, GCP) without .env equivalents

#### 2. **Pydantic Version Behavior** (Contributing)
Pydantic v2 (pydantic-settings 2.14.1) has strict JSON parsing:
- For complex types (List, Dict, etc.), it **requires** valid JSON
- Does NOT fall through to field_validator until JSON parse succeeds
- No graceful degradation for missing/empty values

#### 3. **Field Configuration Incomplete** (Design Issue)
```python
# Current (line 178 in external_config.py)
watch_folders: List[str] = Field(
    default_factory=lambda: ["./data/watch"],
    validation_alias="WATCH_FOLDERS"
)
```

**Problem:**
- `default_factory` is only used if field is **completely missing** from all sources
- If env var exists but is empty, Pydantic tries to parse it
- `default_factory` never gets called

---

## Why Field Validator Doesn't Help

The current field validator at line 192:

```python
@field_validator("watch_folders", mode="before")
@classmethod
def parse_watch_folders(cls, v):
    """Parse watch_folders from string, JSON, or list format"""
    if isinstance(v, list):
        return v
    if not v or not isinstance(v, str):
        return ["./data/watch"]
    # ... JSON/semicolon/comma parsing ...
```

**Why it fails:**
1. Validator runs in `mode="before"` (before Pydantic's default parsing)
2. But Pydantic first tries to decode as JSON (for complex types)
3. JSON decode fails → Exception raised
4. Validator never gets a chance to run

---

## Deployment Scenarios Where This Occurs

| Scenario | WATCH_FOLDERS Status | Error? | Notes |
|----------|----------------------|--------|-------|
| Local dev with .env | `["./data/watch"]` (set) | ❌ No | Works fine |
| Docker without env var | Not set | ✅ **Yes** | No .env in container |
| CI/CD without setup | Empty string | ✅ **Yes** | Set to "" by mistake |
| Windows Service | Not set | ✅ **Yes** | Environment not propagated |
| Production (no .env) | Not set | ✅ **Yes** | Only in installed deployments |

---

## Solution

### Option 1: Fix Pydantic Configuration (Recommended)

**File:** `core/external_config.py` (around line 178)

```python
# BEFORE (current - breaks on unset env var)
watch_folders: List[str] = Field(
    default_factory=lambda: ["./data/watch"],
    validation_alias="WATCH_FOLDERS"
)

# AFTER (fix - allows validator to run first)
watch_folders: List[str] = Field(
    default="./data/watch",  # String default, not list
    validation_alias="WATCH_FOLDERS"
)
```

**Why it works:**
- When env var is unset, uses string default: `"./data/watch"`
- Field validator runs **before** JSON parsing (with `mode="before"`)
- Validator converts string to list: `["./data/watch"]`
- JSON parsing never happens

### Option 2: Use Optional Field

```python
watch_folders: Optional[List[str]] = Field(
    default=None,
    validation_alias="WATCH_FOLDERS"
)

@field_validator("watch_folders", mode="before")
@classmethod
def parse_watch_folders(cls, v):
    if v is None:
        return ["./data/watch"]
    # ... existing logic ...
```

### Option 3: Add Environment Variable Check (Workaround)

In `.env.example` or deployment documentation:

```bash
# In all deployment environments, set:
WATCH_FOLDERS=["./data/watch"]
```

---

## Implementation Plan

### Priority: **CRITICAL** (Blocks 4 consecutive releases)

### Step 1: Fix the Field Definition
- Update `watch_folders` field to use string default instead of `default_factory`
- Update field_validator to handle both string and list inputs

### Step 2: Add Environment Variable Documentation
- Create `.env.example` with proper `WATCH_FOLDERS` format
- Update deployment guides (Docker, systemd, cloud)

### Step 3: Improve Error Messages
- Add validation error handler to give clear guidance
- Log which environment variables are unset/invalid

### Step 4: Add Tests
- Test with WATCH_FOLDERS unset
- Test with WATCH_FOLDERS=""
- Test with WATCH_FOLDERS='["./data/watch"]'
- Test with WATCH_FOLDERS="./data/watch;./other"

---

## Testing Verification

### Before Fix (Current - should fail)
```bash
$ unset WATCH_FOLDERS
$ python -m uvicorn main:app
# Error: pydantic_settings.exceptions.SettingsError
```

### After Fix (should succeed)
```bash
$ unset WATCH_FOLDERS
$ python -m uvicorn main:app
# Success: Uvicorn running on http://0.0.0.0:8011

$ WATCH_FOLDERS="" python -m uvicorn main:app
# Success: Uvicorn running (uses default)

$ WATCH_FOLDERS='["./custom/watch"]' python -m uvicorn main:app
# Success: Uvicorn running (uses custom value)
```

---

## Files to Modify

1. **`python_backend/core/external_config.py`** (Line ~178-192)
   - Fix FileSystemConfig.watch_folders field definition
   - Update field_validator to handle edge cases

2. **`.env.example`** (Create if not exists)
   - Add proper WATCH_FOLDERS example

3. **`python_backend/requirements.txt`** (Documentation)
   - Add note about environment variable format

4. **Deployment Docs**
   - Docker: Update Dockerfile to set WATCH_FOLDERS
   - Systemd: Update service file templates
   - Cloud: Update IaC templates (CloudFormation, Terraform, etc.)

---

## Why This Keeps Recurring

1. **.env is gitignored** → Not in repository
2. **Developers test locally** (have .env) → Works fine
3. **Deployments don't have .env** → Env var unset
4. **Pydantic tries JSON parsing** → Fails on empty/unset
5. **Field validator never runs** → Error propagates
6. **Release cycle restarts** → Same issue in next release

---

## Prevention

### Going Forward

1. **Require WATCH_FOLDERS in production deployments**
   - Add to deployment checklists
   - Add startup validation

2. **Improve environment variable handling**
   - Use string defaults instead of factory defaults for complex types
   - Add explicit checks for required env vars
   - Better error messages with remediation steps

3. **Add CI/CD test**
   - Test startup without .env file
   - Test with various WATCH_FOLDERS formats
   - Include in pre-release validation

4. **Documentation**
   - Clearly document environment variable format
   - Provide deployment configuration templates
   - Add troubleshooting guide

---

## Summary Table

| Aspect | Current | Issue | Fix |
|--------|---------|-------|-----|
| **Field Definition** | `default_factory=lambda: [...]` | Doesn't apply if env var set to empty | Use string default |
| **Env Var Parsing** | Tries JSON parsing first | Fails on unset/empty | Handle in validator |
| **Validator Timing** | Runs after JSON parsing | Validator never called | Use `mode="before"` |
| **Error Message** | Generic Pydantic error | Not actionable | Add helpful context |
| **Documentation** | Sparse | Unclear format | Add examples |
| **Testing** | No env var tests | Misses real scenario | Add integration tests |

---

## Commits Required

```
1. Fix FileSystemConfig field definition
   - Change watch_folders default handling
   - Update field_validator logic
   - Add comprehensive documentation

2. Add environment variable example/template
   - Create .env.example with proper format
   - Document all required env vars

3. Update deployment documentation
   - Docker: Set WATCH_FOLDERS in Dockerfile
   - Cloud: Update IaC templates
   - Systemd: Update service templates

4. Add integration tests
   - Test startup scenarios
   - Test env var parsing
   - Test error handling
```

---

**Severity:** 🔴 **CRITICAL** - Blocks production deployments  
**Recurring Issues:** 4 releases  
**Root Cause:** Deployment environment configuration + Pydantic behavior  
**Fix Effort:** ~2 hours (1 code change + 1 test + documentation)  
**Prevention:** Environment variable validation + tests
