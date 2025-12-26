from fastapi import APIRouter, HTTPException, BackgroundTasks, Query, Response
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import uuid
from datetime import datetime, timezone
from pathlib import Path
import csv
import json
import xml.etree.ElementTree as ET
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/analytics/quality", tags=["Analytics - Quality"])

# --- Pydantic Models ---

class DataQualityReport(BaseModel):
    table_name: str
    scan_id: str
    completeness_score: float
    accuracy_score: float
    consistency_score: float
    validity_score: float
    overall_score: float
    issues: List[Dict[str, Any]]
    recommendations: List[str]
    scan_date: datetime
    row_count: int
    column_count: int

class QualityRule(BaseModel):
    id: str
    name: str
    description: str
    rule_type: str  # "completeness", "accuracy", "consistency", "validity"
    condition: str
    severity: str  # "low", "medium", "high", "critical"
    enabled: bool = True

class QualityIssue(BaseModel):
    issue_id: str
    rule_id: str
    severity: str
    description: str
    affected_rows: int
    affected_columns: List[str]
    sample_values: List[Any]
    suggestion: str

class QualityScanRequest(BaseModel):
    table_name: str
    data_source: str
    rules: List[str] = []  # Rule IDs to apply, empty means all enabled rules
    sample_size: Optional[int] = None

# --- In-memory storage (replace with database in production) ---
quality_reports: Dict[str, DataQualityReport] = {}
quality_rules: Dict[str, QualityRule] = {}
quality_scans: Dict[str, Dict[str, Any]] = {}

# Initialize default quality rules
def initialize_default_rules():
    default_rules = [
        QualityRule(
            id="completeness_001",
            name="No Null Values",
            description="Check for null/empty values in required fields",
            rule_type="completeness",
            condition="IS NOT NULL",
            severity="high"
        ),
        QualityRule(
            id="accuracy_001", 
            name="Email Format",
            description="Validate email address format",
            rule_type="accuracy",
            condition="REGEX_MATCH(email, '^[\\w\\.-]+@[\\w\\.-]+\\.\\w+$')",
            severity="medium"
        ),
        QualityRule(
            id="consistency_001",
            name="Date Range",
            description="Ensure dates are within expected range",
            rule_type="consistency", 
            condition="date_field BETWEEN '1900-01-01' AND CURRENT_DATE",
            severity="high"
        ),
        QualityRule(
            id="validity_001",
            name="Positive Numbers",
            description="Numeric fields should be positive where applicable",
            rule_type="validity",
            condition="numeric_field > 0",
            severity="medium"
        )
    ]
    
    for rule in default_rules:
        quality_rules[rule.id] = rule

# Initialize rules on startup
initialize_default_rules()

# --- Quality Reports ---

@router.get("/reports", response_model=List[DataQualityReport])
async def get_quality_reports(
    response: Response,
    table_name: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
):
    """Get data quality reports (paged)."""
    reports = list(quality_reports.values())
    
    if table_name:
        reports = [r for r in reports if r.table_name == table_name]
    
    # Sort by scan date, most recent first
    reports.sort(key=lambda x: x.scan_date, reverse=True)

    total_count = len(reports)
    response.headers["X-Total-Count"] = str(total_count)
    return reports[skip:skip + limit]

@router.get("/reports/{scan_id}", response_model=DataQualityReport)
async def get_quality_report(scan_id: str):
    """Get specific quality report"""
    if scan_id not in quality_reports:
        raise HTTPException(status_code=404, detail="Quality report not found")
    
    return quality_reports[scan_id]

@router.post("/scan/{table_name}")
async def scan_table_quality(table_name: str, scan_request: QualityScanRequest, background_tasks: BackgroundTasks):
    """Scan a table for data quality issues"""
    scan_id = str(uuid.uuid4())
    
    # Store scan request
    quality_scans[scan_id] = {
        "scan_id": scan_id,
        "table_name": table_name,
        "status": "running",
        "created_at": datetime.now().isoformat(),
        "request": scan_request.dict()
    }
    
    # Start scan in background
    background_tasks.add_task(execute_quality_scan, scan_id, table_name, scan_request)
    
    logger.info("Started quality scan %s for table %s", scan_id, table_name)
    return {
        "scan_id": scan_id,
        "message": f"Quality scan started for table {table_name}",
        "status": "running"
    }

@router.get("/scan/{scan_id}/status")
async def get_scan_status(scan_id: str):
    """Get scan status"""
    if scan_id not in quality_scans:
        raise HTTPException(status_code=404, detail="Scan not found")
    
    return quality_scans[scan_id]

# --- Quality Rules Management ---

@router.get("/rules", response_model=List[QualityRule])
async def get_quality_rules(
    response: Response,
    rule_type: Optional[str] = None,
    enabled_only: bool = True,
    skip: int = Query(0, ge=0),
    limit: int = Query(1000, ge=1, le=5000),
):
    """Get configured quality rules (paged)."""
    rules = list(quality_rules.values())
    
    if rule_type:
        rules = [r for r in rules if r.rule_type == rule_type]
    
    if enabled_only:
        rules = [r for r in rules if r.enabled]

    total_count = len(rules)
    response.headers["X-Total-Count"] = str(total_count)
    return rules[skip:skip + limit]

@router.post("/rules", response_model=QualityRule)
async def create_quality_rule(rule: QualityRule):
    """Create a new quality rule"""
    if rule.id in quality_rules:
        raise HTTPException(status_code=400, detail="Rule ID already exists")
    
    quality_rules[rule.id] = rule
    logger.info("Created quality rule %s: %s", rule.id, rule.name)
    return rule

@router.put("/rules/{rule_id}", response_model=QualityRule)
async def update_quality_rule(rule_id: str, rule: QualityRule):
    """Update an existing quality rule"""
    if rule_id not in quality_rules:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    rule.id = rule_id  # Ensure ID consistency
    quality_rules[rule_id] = rule
    logger.info("Updated quality rule %s", rule_id)
    return rule

@router.delete("/rules/{rule_id}")
async def delete_quality_rule(rule_id: str):
    """Delete a quality rule"""
    if rule_id not in quality_rules:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    del quality_rules[rule_id]
    logger.info("Deleted quality rule %s", rule_id)
    return {"message": f"Rule {rule_id} deleted"}

@router.put("/rules/{rule_id}/toggle")
async def toggle_quality_rule(rule_id: str):
    """Enable/disable a quality rule"""
    if rule_id not in quality_rules:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    rule = quality_rules[rule_id]
    rule.enabled = not rule.enabled
    
    status = "enabled" if rule.enabled else "disabled"
    logger.info("Quality rule %s %s", rule_id, status)
    return {"message": f"Rule {rule_id} {status}", "enabled": rule.enabled}

# --- Quality Monitoring ---

@router.get("/dashboard")
async def quality_dashboard():
    """Get quality dashboard data"""
    total_reports = len(quality_reports)
    
    if total_reports == 0:
        return {
            "summary": {
                "total_tables_scanned": 0,
                "average_quality_score": 0,
                "critical_issues": 0,
                "total_issues": 0
            },
            "recent_scans": [],
            "quality_trends": [],
            "top_issues": []
        }
    
    reports = list(quality_reports.values())
    avg_score = sum(r.overall_score for r in reports) / len(reports)
    
    # Count issues by severity
    all_issues = []
    for report in reports:
        all_issues.extend(report.issues)
    
    critical_issues = len([i for i in all_issues if i.get("severity") == "critical"])
    
    # Recent scans (last 5)
    recent_reports = sorted(reports, key=lambda x: x.scan_date, reverse=True)[:5]
    
    return {
        "summary": {
            "total_tables_scanned": len(set(r.table_name for r in reports)),
            "average_quality_score": round(avg_score, 2),
            "critical_issues": critical_issues,
            "total_issues": len(all_issues),
            "active_rules": len([r for r in quality_rules.values() if r.enabled])
        },
        "recent_scans": [
            {
                "table_name": r.table_name,
                "overall_score": r.overall_score,
                "scan_date": r.scan_date.isoformat(),
                "issues_count": len(r.issues)
            } for r in recent_reports
        ],
        "quality_trends": [
            {
                "date": r.scan_date.isoformat()[:10],
                "score": r.overall_score
            } for r in sorted(reports, key=lambda x: x.scan_date)[-30:]  # Last 30 scans
        ],
        "top_issues": [
            {
                "rule_name": rule.name,
                "severity": rule.severity,
                "occurrences": len([i for i in all_issues if i.get("rule_id") == rule.id])
            } for rule in quality_rules.values()
        ][:10]
    }

# --- Background Scan Execution ---

async def execute_quality_scan(scan_id: str, table_name: str, _scan_request: QualityScanRequest):
    """Background task to execute quality scan"""
    try:
        scan_request = _scan_request
        data_source = str(scan_request.data_source or "").strip()

        issues: List[Dict[str, Any]] = []
        recommendations: List[str] = []

        def _mk_issue(
            rule_id: str,
            severity: str,
            description: str,
            affected_rows: int = 0,
            affected_columns: Optional[List[str]] = None,
            sample_values: Optional[List[Any]] = None,
            suggestion: str = "",
        ) -> Dict[str, Any]:
            return {
                "issue_id": str(uuid.uuid4()),
                "rule_id": rule_id,
                "severity": severity,
                "description": description,
                "affected_rows": int(affected_rows),
                "affected_columns": affected_columns or [],
                "sample_values": sample_values or [],
                "suggestion": suggestion,
            }

        def _resolve_path(candidate: str) -> Optional[Path]:
            if not candidate:
                return None
            try:
                p = Path(candidate)
            except TypeError:
                return None
            return p if p.exists() else None

        def _safe_xml_parse(path: Path) -> bool:
            try:
                ET.parse(str(path))
                return True
            except OSError as e:
                issues.append(
                    _mk_issue(
                        rule_id="validity_001",
                        severity="high",
                        description=f"XML read failed: {path.name}: {e}",
                        affected_rows=1,
                        suggestion="Check file permissions/path and try again",
                    )
                )
                return False
            except ET.ParseError as e:
                issues.append(
                    _mk_issue(
                        rule_id="validity_001",
                        severity="high",
                        description=f"XML parse failed: {path.name}: {e}",
                        affected_rows=1,
                        suggestion="Fix malformed XML or encoding issues",
                    )
                )
                return False

        def _safe_json_load(path: Path) -> Optional[Any]:
            try:
                with path.open("r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError as e:
                issues.append(
                    _mk_issue(
                        rule_id="validity_001",
                        severity="high",
                        description=f"JSON parse failed: {path.name}: {e}",
                        affected_rows=1,
                        suggestion="Fix malformed JSON",
                    )
                )
                return None
            except UnicodeDecodeError as e:
                issues.append(
                    _mk_issue(
                        rule_id="validity_001",
                        severity="high",
                        description=f"JSON decode failed (encoding): {path.name}: {e}",
                        affected_rows=1,
                        suggestion="Ensure the file is UTF-8 encoded",
                    )
                )
                return None
            except OSError as e:
                issues.append(
                    _mk_issue(
                        rule_id="validity_001",
                        severity="high",
                        description=f"JSON read failed: {path.name}: {e}",
                        affected_rows=1,
                        suggestion="Check file permissions/path and try again",
                    )
                )
                return None

        def _safe_csv_sample(path: Path, max_rows: int) -> Optional[Dict[str, Any]]:
            try:
                with path.open("r", encoding="utf-8", newline="") as f:
                    reader = csv.reader(f)
                    rows: List[List[str]] = []
                    for idx, row in enumerate(reader):
                        rows.append(row)
                        if idx + 1 >= max_rows:
                            break
                return {"rows": rows}
            except csv.Error as e:
                issues.append(
                    _mk_issue(
                        rule_id="validity_001",
                        severity="high",
                        description=f"CSV parse failed: {path.name}: {e}",
                        affected_rows=1,
                        suggestion="Fix delimiter/quoting issues",
                    )
                )
                return None
            except UnicodeDecodeError as e:
                issues.append(
                    _mk_issue(
                        rule_id="validity_001",
                        severity="high",
                        description=f"CSV decode failed (encoding): {path.name}: {e}",
                        affected_rows=1,
                        suggestion="Ensure the file is UTF-8 encoded",
                    )
                )
                return None
            except OSError as e:
                issues.append(
                    _mk_issue(
                        rule_id="validity_001",
                        severity="high",
                        description=f"CSV read failed: {path.name}: {e}",
                        affected_rows=1,
                        suggestion="Check file permissions/path and try again",
                    )
                )
                return None

        parsed_ok = 0
        parsed_total = 0
        row_count = 0
        column_count = 0

        p = _resolve_path(data_source)
        if p and p.is_file():
            ext = p.suffix.lower().lstrip(".")
            parsed_total = 1

            if ext in ("xml", "xsd"):
                parsed_ok = 1 if _safe_xml_parse(p) else 0
                row_count = 1
                column_count = 0
            elif ext == "json":
                obj = _safe_json_load(p)
                if obj is not None:
                    parsed_ok = 1
                    if isinstance(obj, list):
                        row_count = len(obj)
                        first = obj[0] if obj else None
                        column_count = len(first) if isinstance(first, dict) else 0
                    elif isinstance(obj, dict):
                        row_count = 1
                        column_count = len(obj)
            elif ext == "csv":
                max_rows = int(scan_request.sample_size or 200)
                max_rows = max(1, min(5000, max_rows))
                sample = _safe_csv_sample(p, max_rows=max_rows)
                if sample is not None:
                    parsed_ok = 1
                    rows = sample.get("rows") or []
                    row_count = len(rows)
                    column_count = max((len(r) for r in rows), default=0)
            else:
                issues.append(
                    _mk_issue(
                        rule_id="validity_001",
                        severity="medium",
                        description=f"Unsupported file type for deterministic scan: .{ext or '(none)'}",
                        affected_rows=1,
                        suggestion="Provide a CSV/JSON/XML/XSD file or a directory path",
                    )
                )
        elif p and p.is_dir():
            # Folder-based verification scan (matches earlier 'folder + file type' constraint)
            allowed_exts = {"xml", "xsd", "json", "csv", "zip", "stp", "step"}
            extension_counts: Dict[str, int] = {}

            xml_count = 0
            xsd_count = 0

            for child in p.rglob("*"):
                if not child.is_file():
                    continue

                ext = child.suffix.lower().lstrip(".") or "(none)"
                extension_counts[ext] = extension_counts.get(ext, 0) + 1

                if ext == "xml":
                    xml_count += 1
                if ext == "xsd":
                    xsd_count += 1

                # Only lightweight parseability checks (no schema validation)
                if ext in ("xml", "xsd"):
                    parsed_total += 1
                    if _safe_xml_parse(child):
                        parsed_ok += 1
                elif ext == "json":
                    parsed_total += 1
                    if _safe_json_load(child) is not None:
                        parsed_ok += 1
                elif ext == "csv":
                    parsed_total += 1
                    if _safe_csv_sample(child, max_rows=50) is not None:
                        parsed_ok += 1
                elif ext not in allowed_exts and ext != "(none)":
                    issues.append(
                        _mk_issue(
                            rule_id="validity_001",
                            severity="low",
                            description=f"Unexpected file type found: .{ext}",
                            affected_rows=1,
                            suggestion="Review whether this file belongs in the import folder",
                        )
                    )

            row_count = sum(extension_counts.values())
            column_count = len(extension_counts)

            if xml_count > 0 and xsd_count == 0:
                issues.append(
                    _mk_issue(
                        rule_id="consistency_001",
                        severity="medium",
                        description="XML files found but no XSD files present for schema validation",
                        affected_rows=xml_count,
                        suggestion="Add XSD files or validate XML structure at source",
                    )
                )
        else:
            issues.append(
                _mk_issue(
                    rule_id="validity_001",
                    severity="high",
                    description="data_source must be a valid local file or directory path for deterministic scans",
                    affected_rows=0,
                    suggestion="Set data_source to a path accessible by the backend runtime",
                )
            )

        parse_success_rate = (parsed_ok / parsed_total) if parsed_total > 0 else 0.0
        high_issues = sum(1 for i in issues if i.get("severity") == "high")
        medium_issues = sum(1 for i in issues if i.get("severity") == "medium")
        low_issues = sum(1 for i in issues if i.get("severity") == "low")

        completeness_score = 1.0 if row_count > 0 else 0.0
        accuracy_score = max(0.0, min(1.0, parse_success_rate))
        consistency_score = 1.0 if medium_issues == 0 else max(0.6, 1.0 - 0.1 * medium_issues)
        if high_issues > 0:
            validity_score = max(0.0, 1.0 - 0.25 * high_issues)
        elif low_issues > 0:
            validity_score = max(0.8, 1.0 - 0.02 * low_issues)
        else:
            validity_score = 1.0

        overall_score = (completeness_score + accuracy_score + consistency_score + validity_score) / 4

        if high_issues > 0:
            recommendations.append("Fix parse/format errors in the source artifacts.")
        if any("XSD" in str(i.get("description")) for i in issues):
            recommendations.append("Add XSD schema files to validate XML payloads.")
        if any(i.get("severity") == "low" for i in issues):
            recommendations.append("Review unexpected file types and clean the import folder.")
        if not recommendations:
            recommendations.append("No issues detected. Continue periodic scans.")

        report = DataQualityReport(
            table_name=table_name,
            scan_id=scan_id,
            completeness_score=round(float(completeness_score), 3),
            accuracy_score=round(float(accuracy_score), 3),
            consistency_score=round(float(consistency_score), 3),
            validity_score=round(float(validity_score), 3),
            overall_score=round(float(overall_score), 3),
            issues=issues,
            recommendations=recommendations,
            scan_date=datetime.now(timezone.utc),
            row_count=int(row_count),
            column_count=int(column_count),
        )
        
        quality_reports[scan_id] = report
        quality_scans[scan_id]["status"] = "completed"
        quality_scans[scan_id]["completed_at"] = datetime.now().isoformat()
        
        logger.info("Quality scan %s completed for table %s", scan_id, table_name)
        
    except (OSError, KeyError, RuntimeError) as e:
        quality_scans[scan_id]["status"] = "failed"
        quality_scans[scan_id]["error"] = str(e)
        quality_scans[scan_id]["completed_at"] = datetime.now().isoformat()
        
        logger.error("Quality scan %s failed: %s", scan_id, str(e))

# --- Health Check ---

@router.get("/health")
async def quality_health():
    """Health check for quality module"""
    return {
        "status": "healthy",
        "module": "data_quality",
        "total_reports": len(quality_reports),
        "active_rules": len([r for r in quality_rules.values() if r.enabled]),
        "running_scans": len([s for s in quality_scans.values() if s["status"] == "running"]),
        "timestamp": datetime.now().isoformat()
    }
