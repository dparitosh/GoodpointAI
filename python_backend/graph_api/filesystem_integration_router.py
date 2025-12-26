"""
File System Integration Router
Handles local files, network shares, XML, JSON, CSV processing
Includes folder monitoring and batch file operations
"""
import logging
from typing import Any, List, Dict, Optional
from datetime import datetime
from pathlib import Path
import os
import json
import shutil
from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks, Query, Response
from pydantic import BaseModel, Field
import xmltodict  # type: ignore[import-untyped]
import pandas as pd  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/filesystem", tags=["File System Integration"])


# ============================================================================
# MODELS
# ============================================================================

class FileInfo(BaseModel):
    name: str
    path: str
    size: int
    created: str
    modified: str
    extension: str
    is_directory: bool


class DirectoryListRequest(BaseModel):
    path: str = Field(..., description="Directory path to list")
    recursive: bool = False
    filter_extension: Optional[str] = None


class FileUploadResponse(BaseModel):
    status: str
    message: str
    file_name: str
    file_path: str
    size: int


class XMLParseRequest(BaseModel):
    file_path: str = Field(..., description="Path to XML file")
    namespace_map: Optional[Dict[str, str]] = {}


class JSONProcessRequest(BaseModel):
    file_path: str = Field(..., description="Path to JSON file")
    schema_validate: bool = False
    json_schema: Optional[Dict] = None


class CSVProcessRequest(BaseModel):
    file_path: str = Field(..., description="Path to CSV file")
    delimiter: str = ","
    encoding: str = "utf-8"
    header_row: int = 0


class BatchFileOperation(BaseModel):
    operation: str = Field(..., description="copy, move, delete")
    source_pattern: str = Field(..., description="Glob pattern for files")
    destination: Optional[str] = None


class FolderMonitorConfig(BaseModel):
    watch_path: str
    file_patterns: List[str] = ["*.*"]
    action: str = Field(..., description="process, move, notify")
    destination_path: Optional[str] = None


# ============================================================================
# DIRECTORY OPERATIONS
# ============================================================================

@router.post("/list")
async def list_directory(
    request: DirectoryListRequest,
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """List files and directories"""
    try:
        from core.external_config import filesystem_config
        
        # Resolve path
        if request.path.startswith("./"):
            base_path = Path(filesystem_config.data_root)
            full_path = base_path / request.path[2:]
        else:
            full_path = Path(request.path)
        
        if not full_path.exists():
            raise HTTPException(status_code=404, detail=f"Path not found: {request.path}")
        
        if not full_path.is_dir():
            raise HTTPException(status_code=400, detail="Path is not a directory")
        
        files = []
        
        if request.recursive:
            pattern = f"**/*.{request.filter_extension}" if request.filter_extension else "**/*"
            paths = full_path.glob(pattern)
        else:
            pattern = f"*.{request.filter_extension}" if request.filter_extension else "*"
            paths = full_path.glob(pattern)
        
        for path in paths:
            if path.is_file() or path.is_dir():
                stat = path.stat()
                files.append({
                    "name": path.name,
                    "path": str(path),
                    "size": stat.st_size if path.is_file() else 0,
                    "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "extension": path.suffix,
                    "is_directory": path.is_dir()
                })
        
        response.headers["X-Total-Count"] = str(len(files))
        paged_files = files[skip : skip + limit]
        return {
            "status": "success",
            "path": str(full_path),
            "count": len(paged_files),
            "files": paged_files
        }
        
    except Exception as e:
        logger.error("Error listing directory: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    destination_path: Optional[str] = None
):
    """Upload file to server"""
    try:
        from core.external_config import filesystem_config
        
        # Determine destination
        if destination_path:
            dest_dir = Path(destination_path)
        else:
            dest_dir = Path(filesystem_config.upload_dir)
        
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        if not file.filename:
            raise HTTPException(status_code=400, detail="Missing upload filename")

        filename = file.filename
        file_path = dest_dir / filename
        
        # Check file size
        content = await file.read()
        file_size_mb = len(content) / (1024 * 1024)
        
        if file_size_mb > filesystem_config.max_upload_size_mb:
            raise HTTPException(
                status_code=413,
                detail=f"File too large: {file_size_mb:.2f}MB (max: {filesystem_config.max_upload_size_mb}MB)"
            )
        
        # Write file
        with open(file_path, "wb") as f:
            f.write(content)
        
        logger.info("Uploaded file: %s", file_path)
        
        return {
            "status": "success",
            "message": "File uploaded successfully",
            "file_name": filename,
            "file_path": str(file_path),
            "size": len(content)
        }
        
    except Exception as e:
        logger.error("Error uploading file: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/download/{file_path:path}")
async def download_file(file_path: str):
    """Download file from server"""
    try:
        from fastapi.responses import FileResponse
        
        path = Path(file_path)
        
        if not path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        
        if not path.is_file():
            raise HTTPException(status_code=400, detail="Path is not a file")
        
        return FileResponse(
            path=str(path),
            filename=path.name,
            media_type="application/octet-stream"
        )
        
    except Exception as e:
        logger.error("Error downloading file: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/delete/{file_path:path}")
async def delete_file(file_path: str):
    """Delete file from server"""
    try:
        path = Path(file_path)
        
        if not path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        
        if path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)
        
        return {
            "status": "success",
            "message": "File deleted",
            "path": file_path
        }
        
    except Exception as e:
        logger.error("Error deleting file: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


# ============================================================================
# XML FILE PROCESSING
# ============================================================================

@router.post("/xml/parse")
async def parse_xml_file(request: XMLParseRequest):
    """Parse XML file and convert to JSON"""
    try:
        file_path = Path(request.file_path)
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="XML file not found")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            xml_content = f.read()
        
        # Parse XML to dict
        parsed_data = xmltodict.parse(
            xml_content,
            process_namespaces=True,
            namespaces=request.namespace_map
        )
        
        return {
            "status": "success",
            "file": str(file_path),
            "data": parsed_data,
            "size": len(xml_content)
        }
        
    except Exception as e:
        logger.error("Error parsing XML: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e  # noqa: B904


@router.post("/xml/validate")
async def validate_xml_file(file_path: str, schema_path: Optional[str] = None):
    """Validate XML file against XSD schema"""
    try:
        from lxml import etree  # type: ignore[import-untyped]
        
        xml_path = Path(file_path)
        if not xml_path.exists():
            raise HTTPException(status_code=404, detail="XML file not found")
        
        # Parse XML
        xml_doc = etree.parse(str(xml_path))
        
        is_valid = True
        errors = []
        
        if schema_path:
            schema_file = Path(schema_path)
            if schema_file.exists():
                schema_doc = etree.parse(str(schema_file))
                schema = etree.XMLSchema(schema_doc)
                
                is_valid = schema.validate(xml_doc)
                if not is_valid:
                    errors = [str(err) for err in schema.error_log]
        
        return {
            "status": "success",
            "file": str(xml_path),
            "is_valid": is_valid,
            "errors": errors
        }
        
    except Exception as e:
        logger.error("Error validating XML: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


# ============================================================================
# JSON FILE PROCESSING
# ============================================================================

@router.post("/json/parse")
async def parse_json_file(request: JSONProcessRequest):
    """Parse and validate JSON file"""
    try:
        file_path = Path(request.file_path)
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="JSON file not found")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
        
        validation_result: Dict[str, Any] = {"validated": False, "errors": []}
        
        if request.schema_validate and request.json_schema:
            from jsonschema import validate, ValidationError  # type: ignore[import-untyped]
            try:
                validate(instance=json_data, schema=request.json_schema)
                validation_result = {"validated": True, "errors": []}
            except ValidationError as ve:
                validation_result = {"validated": False, "errors": [str(ve)]}
        
        return {
            "status": "success",
            "file": str(file_path),
            "data": json_data,
            "validation": validation_result
        }
        
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}") from e
    except Exception as e:
        logger.error("Error parsing JSON: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/json/merge")
async def merge_json_files(file_paths: List[str], output_path: str):
    """Merge multiple JSON files into one"""
    try:
        merged_data = []
        
        for file_path in file_paths:
            path = Path(file_path)
            if path.exists():
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        merged_data.extend(data)
                    else:
                        merged_data.append(data)
        
        # Write merged file
        output = Path(output_path)
        with open(output, 'w', encoding='utf-8') as f:
            json.dump(merged_data, f, indent=2)
        
        return {
            "status": "success",
            "message": "JSON files merged",
            "input_files": len(file_paths),
            "output_file": str(output),
            "records": len(merged_data)
        }
        
    except Exception as e:
        logger.error("Error merging JSON files: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


# ============================================================================
# CSV FILE PROCESSING
# ============================================================================

@router.post("/csv/parse")
async def parse_csv_file(request: CSVProcessRequest):
    """Parse CSV file and return data"""
    try:
        file_path = Path(request.file_path)
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="CSV file not found")
        
        # Read CSV
        df = pd.read_csv(
            file_path,
            delimiter=request.delimiter,
            encoding=request.encoding,
            header=request.header_row
        )
        
        # Convert to records
        records = df.to_dict('records')
        
        return {
            "status": "success",
            "file": str(file_path),
            "rows": len(df),
            "columns": list(df.columns),
            "data": records[:100],  # Limit to first 100 rows
            "total_rows": len(df)
        }
        
    except Exception as e:
        logger.error("Error parsing CSV: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/csv/to-json")
async def convert_csv_to_json(
    csv_path: str,
    json_path: str,
    delimiter: str = ",",
    encoding: str = "utf-8"
):
    """Convert CSV file to JSON"""
    try:
        csv_file = Path(csv_path)
        if not csv_file.exists():
            raise HTTPException(status_code=404, detail="CSV file not found")
        
        df = pd.read_csv(csv_file, delimiter=delimiter, encoding=encoding)
        records = df.to_dict('records')
        
        json_file = Path(json_path)
        json_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(records, f, indent=2, default=str)
        
        return {
            "status": "success",
            "message": "CSV converted to JSON",
            "csv_file": str(csv_file),
            "json_file": str(json_file),
            "records": len(records)
        }
        
    except Exception as e:
        logger.error("Error converting CSV to JSON: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e  # noqa: B904


# ============================================================================
# BATCH FILE OPERATIONS
# ============================================================================

@router.post("/batch/operation")
async def batch_file_operation(request: BatchFileOperation):
    """Perform batch file operations (copy, move, delete)"""
    try:
        from glob import glob
        
        # Find matching files
        files = glob(request.source_pattern, recursive=True)
        
        file_results: List[Dict[str, Any]] = []
        results: Dict[str, Any] = {
            "operation": request.operation,
            "pattern": request.source_pattern,
            "found_files": len(files),
            "processed": 0,
            "failed": 0,
            "files": file_results,
        }
        
        for file_path in files:
            try:
                src = Path(file_path)
                
                if request.operation == "copy" and request.destination:
                    dest = Path(request.destination) / src.name
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dest)
                    file_results.append({"src": str(src), "dest": str(dest), "status": "copied"})
                    
                elif request.operation == "move" and request.destination:
                    dest = Path(request.destination) / src.name
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(src, dest)
                    file_results.append({"src": str(src), "dest": str(dest), "status": "moved"})
                    
                elif request.operation == "delete":
                    src.unlink()
                    file_results.append({"src": str(src), "status": "deleted"})
                
                results["processed"] += 1
                
            except (OSError, shutil.Error) as e:
                results["failed"] += 1
                file_results.append({"src": str(src), "status": "failed", "error": str(e)})
                logger.error("Error processing %s: %s", src, e)
        
        return {
            "status": "success",
            "results": results
        }
        
    except Exception as e:
        logger.error("Error in batch operation: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


# ============================================================================
# FOLDER MONITORING
# ============================================================================

@router.post("/watch/start")
async def start_folder_monitoring(config: FolderMonitorConfig, _background_tasks: BackgroundTasks):
    """Start monitoring a folder for file changes"""
    try:
        watch_path = Path(config.watch_path)
        
        if not watch_path.exists():
            watch_path.mkdir(parents=True, exist_ok=True)
        
        # In production, use watchdog library for file system monitoring
        # For now, return configuration
        
        monitor_id = f"monitor_{datetime.utcnow().timestamp()}"
        
        return {
            "status": "success",
            "message": "Folder monitoring configured",
            "monitor_id": monitor_id,
            "config": {
                "watch_path": str(watch_path),
                "patterns": config.file_patterns,
                "action": config.action,
                "destination": config.destination_path
            },
            "note": "Implement watchdog library for production monitoring"
        }
        
    except Exception as e:
        logger.error("Error starting folder monitoring: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


# ============================================================================
# HEALTH CHECK
# ============================================================================

@router.get("/health")
async def filesystem_health_check():
    """Check file system accessibility"""
    from core.external_config import filesystem_config
    
    directories_status = {}
    
    for dir_name in ["data_root", "upload_dir", "temp_dir", "export_dir", "log_dir"]:
        dir_path = getattr(filesystem_config, dir_name)
        path = Path(dir_path)
        directories_status[dir_name] = {
            "path": str(path),
            "exists": path.exists(),
            "writable": os.access(path, os.W_OK) if path.exists() else False
        }
    
    return {
        "status": "healthy",
        "directories": directories_status,
        "timestamp": datetime.utcnow().isoformat()
    }
