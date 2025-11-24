from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import uuid
from datetime import datetime
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
async def get_quality_reports(table_name: Optional[str] = None, limit: int = 10):
    """Get data quality reports"""
    reports = list(quality_reports.values())
    
    if table_name:
        reports = [r for r in reports if r.table_name == table_name]
    
    # Sort by scan date, most recent first
    reports.sort(key=lambda x: x.scan_date, reverse=True)
    
    return reports[:limit]

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
    
    logger.info(f"Started quality scan {scan_id} for table {table_name}")
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
async def get_quality_rules(rule_type: Optional[str] = None, enabled_only: bool = True):
    """Get configured quality rules"""
    rules = list(quality_rules.values())
    
    if rule_type:
        rules = [r for r in rules if r.rule_type == rule_type]
    
    if enabled_only:
        rules = [r for r in rules if r.enabled]
    
    return rules

@router.post("/rules", response_model=QualityRule)
async def create_quality_rule(rule: QualityRule):
    """Create a new quality rule"""
    if rule.id in quality_rules:
        raise HTTPException(status_code=400, detail="Rule ID already exists")
    
    quality_rules[rule.id] = rule
    logger.info(f"Created quality rule {rule.id}: {rule.name}")
    return rule

@router.put("/rules/{rule_id}", response_model=QualityRule)
async def update_quality_rule(rule_id: str, rule: QualityRule):
    """Update an existing quality rule"""
    if rule_id not in quality_rules:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    rule.id = rule_id  # Ensure ID consistency
    quality_rules[rule_id] = rule
    logger.info(f"Updated quality rule {rule_id}")
    return rule

@router.delete("/rules/{rule_id}")
async def delete_quality_rule(rule_id: str):
    """Delete a quality rule"""
    if rule_id not in quality_rules:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    del quality_rules[rule_id]
    logger.info(f"Deleted quality rule {rule_id}")
    return {"message": f"Rule {rule_id} deleted"}

@router.put("/rules/{rule_id}/toggle")
async def toggle_quality_rule(rule_id: str):
    """Enable/disable a quality rule"""
    if rule_id not in quality_rules:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    rule = quality_rules[rule_id]
    rule.enabled = not rule.enabled
    
    status = "enabled" if rule.enabled else "disabled"
    logger.info(f"Quality rule {rule_id} {status}")
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

async def execute_quality_scan(scan_id: str, table_name: str, scan_request: QualityScanRequest):
    """Background task to execute quality scan"""
    try:
        # Simulate quality scanning
        import random
        
        # Generate mock quality scores
        completeness_score = random.uniform(0.7, 1.0)
        accuracy_score = random.uniform(0.6, 0.95)
        consistency_score = random.uniform(0.8, 1.0)
        validity_score = random.uniform(0.75, 0.98)
        
        overall_score = (completeness_score + accuracy_score + consistency_score + validity_score) / 4
        
        # Generate mock issues
        issues = []
        recommendations = []
        
        if completeness_score < 0.9:
            issues.append({
                "issue_id": str(uuid.uuid4()),
                "rule_id": "completeness_001",
                "severity": "high",
                "description": f"Found null values in {int((1-completeness_score)*100)}% of rows",
                "affected_rows": int(1000 * (1-completeness_score)),
                "affected_columns": ["email", "phone"],
                "sample_values": [None, "", "NULL"],
                "suggestion": "Consider making these fields required or providing default values"
            })
            recommendations.append("Implement data validation at input level")
        
        if accuracy_score < 0.85:
            issues.append({
                "issue_id": str(uuid.uuid4()),
                "rule_id": "accuracy_001",
                "severity": "medium",
                "description": f"Invalid email format in {int((1-accuracy_score)*100)}% of email fields",
                "affected_rows": int(800 * (1-accuracy_score)),
                "affected_columns": ["email"],
                "sample_values": ["invalid-email", "test@", "@domain.com"],
                "suggestion": "Add email format validation"
            })
            recommendations.append("Implement regex validation for email fields")
        
        # Create quality report
        report = DataQualityReport(
            table_name=table_name,
            scan_id=scan_id,
            completeness_score=round(completeness_score, 3),
            accuracy_score=round(accuracy_score, 3),
            consistency_score=round(consistency_score, 3),
            validity_score=round(validity_score, 3),
            overall_score=round(overall_score, 3),
            issues=issues,
            recommendations=recommendations,
            scan_date=datetime.now(),
            row_count=random.randint(1000, 10000),
            column_count=random.randint(5, 20)
        )
        
        quality_reports[scan_id] = report
        quality_scans[scan_id]["status"] = "completed"
        quality_scans[scan_id]["completed_at"] = datetime.now().isoformat()
        
        logger.info(f"Quality scan {scan_id} completed for table {table_name}")
        
    except Exception as e:
        quality_scans[scan_id]["status"] = "failed"
        quality_scans[scan_id]["error"] = str(e)
        quality_scans[scan_id]["completed_at"] = datetime.now().isoformat()
        
        logger.error(f"Quality scan {scan_id} failed: {str(e)}")

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
