"""
File Batch Processor Service
==============================
Handles large-scale (thousands / lakhs of files) processing through the
multi-modal pipeline with:

- **Discovery**: walk a directory tree and classify every file by type.
- **Parallel ingestion**: `asyncio.Semaphore`-bounded concurrent processing
  (default 8 workers) so the event loop is never saturated.
- **Batch DB writes**: results flushed to Postgres in configurable chunks.
- **Genealogy / lineage**: one Neo4j `:BatchJob` node → many `:ProcessedFile`
  nodes written in a single batched Cypher UNWIND call after each flush.
- **Reports**: an aggregate summary written back to Postgres on completion.

The service is intentionally library-agnostic: it delegates single-file
analysis to `MultiModalService` (already in `multimodal_router.py`).
"""

import asyncio
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Supported extensions (mirror MultiModalService)
# ---------------------------------------------------------------------------
_IMAGE_EXT  = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}
_PDF_EXT    = {".pdf"}
_CAD_EXT    = {".dwg", ".dxf", ".step", ".stp", ".iges", ".igs"}
_EXCEL_EXT  = {".xlsx", ".xls", ".xlsm", ".csv"}
_WORD_EXT   = {".docx", ".doc"}
_VIDEO_EXT  = {".mp4", ".avi", ".mov", ".mkv"}

ALL_SUPPORTED = _IMAGE_EXT | _PDF_EXT | _CAD_EXT | _EXCEL_EXT | _WORD_EXT | _VIDEO_EXT


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class FileRecord:
    path: Path
    ext: str
    size_bytes: int
    file_type: str


@dataclass
class FileResult:
    path: str
    file_type: str
    success: bool
    text_content: Optional[str]
    metadata: Dict[str, Any]
    extracted_data: Dict[str, Any]
    error: Optional[str]
    processing_time_ms: int


@dataclass
class BatchReport:
    job_id: str
    started_at: datetime
    completed_at: Optional[datetime]
    total_files: int
    processed: int
    succeeded: int
    failed: int
    skipped: int           # unsupported extensions
    results: List[FileResult] = field(default_factory=list)
    errors_summary: List[Dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Discovery helpers
# ---------------------------------------------------------------------------

def discover_files(root: Path, recursive: bool = True, include_unsupported: bool = False) -> List[FileRecord]:
    """Walk *root* and return a list of :class:`FileRecord` for every file.

    Args:
        root: Directory to walk.
        recursive: When True (default) walk all subdirectories.
        include_unsupported: Also return records for files with unsupported
            extensions (marked ``file_type="unknown"``).
    """
    records: List[FileRecord] = []
    glob_pattern = "**/*" if recursive else "*"

    for p in root.glob(glob_pattern):
        if not p.is_file():
            continue
        ext = p.suffix.lower()
        file_type = _classify_ext(ext)
        if file_type == "unknown" and not include_unsupported:
            continue
        try:
            size = p.stat().st_size
        except OSError:
            size = 0
        records.append(FileRecord(path=p, ext=ext, size_bytes=size, file_type=file_type))

    return records


def _classify_ext(ext: str) -> str:
    if ext in _IMAGE_EXT:
        return "image"
    if ext in _PDF_EXT:
        return "pdf"
    if ext in _CAD_EXT:
        return "cad"
    if ext in _EXCEL_EXT:
        return "excel"
    if ext in _WORD_EXT:
        return "word"
    if ext in _VIDEO_EXT:
        return "video"
    return "unknown"


# ---------------------------------------------------------------------------
# Batch processor
# ---------------------------------------------------------------------------

class FileBatchProcessor:
    """Process a large list of files through the multi-modal pipeline.

    Args:
        concurrency: Maximum number of files processed simultaneously.
        db_flush_size: Number of results to accumulate before flushing to Postgres.
        neo4j_driver: Optional open :class:`neo4j.AsyncDriver` for lineage writes.
        db_session_factory: Callable that returns a SQLAlchemy :class:`Session`.
    """

    def __init__(
        self,
        concurrency: int = 8,
        db_flush_size: int = 50,
        neo4j_driver=None,
        db_session_factory=None,
    ):
        self.concurrency = concurrency
        self.db_flush_size = db_flush_size
        self.neo4j_driver = neo4j_driver
        self.db_session_factory = db_session_factory

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def process_directory(
        self,
        root: str,
        *,
        recursive: bool = True,
        extraction_method: str = "hybrid",
        vision_model: str = "llava:latest",
        ollama_host: Optional[str] = None,
        job_id: Optional[str] = None,
    ) -> BatchReport:
        """Discover and process all supported files under *root*.

        Returns a :class:`BatchReport` with per-file results and aggregated stats.
        """
        root_path = Path(root).expanduser().resolve()
        if not root_path.is_dir():
            raise ValueError(f"Not a directory: {root_path}")

        job_id = job_id or uuid.uuid4().hex
        records = discover_files(root_path, recursive=recursive)

        return await self.process_records(
            records,
            job_id=job_id,
            extraction_method=extraction_method,
            vision_model=vision_model,
            ollama_host=ollama_host,
        )

    async def process_records(
        self,
        records: List[FileRecord],
        *,
        job_id: Optional[str] = None,
        extraction_method: str = "hybrid",
        vision_model: str = "llava:latest",
        ollama_host: Optional[str] = None,
    ) -> BatchReport:
        """Process an explicit list of :class:`FileRecord` objects in parallel.

        Uses an :class:`asyncio.Semaphore` to cap concurrency at
        ``self.concurrency`` and flushes results to Postgres/Neo4j every
        ``self.db_flush_size`` files.
        """
        from graph_api.multimodal_router import service as mm_service, ExtractionMethod

        job_id = job_id or uuid.uuid4().hex
        started = datetime.now(timezone.utc)

        report = BatchReport(
            job_id=job_id,
            started_at=started,
            completed_at=None,
            total_files=len(records),
            processed=0,
            succeeded=0,
            failed=0,
            skipped=0,
        )

        sem = asyncio.Semaphore(self.concurrency)
        pending_flush: List[FileResult] = []

        # Map string to enum (fall back to HYBRID)
        try:
            em = ExtractionMethod(extraction_method)
        except ValueError:
            em = ExtractionMethod.HYBRID

        async def _process_one(record: FileRecord) -> FileResult:
            async with sem:
                t0 = datetime.now(timezone.utc)
                try:
                    content = await asyncio.to_thread(record.path.read_bytes)
                    analysis = await mm_service.analyze_file(
                        file_content=content,
                        filename=record.path.name,
                        extraction_method=em,
                        vision_model=vision_model,
                        extract_metadata=True,
                        extract_text=True,
                        extract_images=False,
                        ocr_language="eng",
                        ollama_host=ollama_host,
                    )
                    ms = int((datetime.now(timezone.utc) - t0).total_seconds() * 1000)
                    return FileResult(
                        path=str(record.path),
                        file_type=record.file_type,
                        success=analysis.success,
                        text_content=analysis.text_content,
                        metadata=analysis.metadata,
                        extracted_data=analysis.extracted_data,
                        error=analysis.error,
                        processing_time_ms=ms,
                    )
                except Exception as exc:  # pylint: disable=broad-except
                    logger.error("Batch error on %s: %s", record.path, exc)
                    ms = int((datetime.now(timezone.utc) - t0).total_seconds() * 1000)
                    return FileResult(
                        path=str(record.path),
                        file_type=record.file_type,
                        success=False,
                        text_content=None,
                        metadata={},
                        extracted_data={},
                        error=str(exc),
                        processing_time_ms=ms,
                    )

        # Launch all tasks; flush periodically to avoid unbounded memory usage
        tasks = [asyncio.create_task(_process_one(r)) for r in records]
        for coro in asyncio.as_completed(tasks):
            result: FileResult = await coro
            report.processed += 1
            if result.success:
                report.succeeded += 1
            else:
                report.failed += 1
                report.errors_summary.append({"path": result.path, "error": result.error})

            report.results.append(result)
            pending_flush.append(result)

            if len(pending_flush) >= self.db_flush_size:
                await self._flush(job_id, pending_flush)
                pending_flush.clear()

        # Flush remainder
        if pending_flush:
            await self._flush(job_id, pending_flush)

        report.completed_at = datetime.now(timezone.utc)
        await self._write_report(report)
        return report

    # ------------------------------------------------------------------
    # Postgres flush
    # ------------------------------------------------------------------

    async def _flush(self, job_id: str, results: List[FileResult]) -> None:
        """Persist a batch of results to Postgres and write lineage to Neo4j."""
        await asyncio.gather(
            self._pg_insert_results(job_id, results),
            self._neo4j_write_lineage(job_id, results),
        )

    async def _pg_insert_results(self, job_id: str, results: List[FileResult]) -> None:
        if not self.db_session_factory:
            return
        try:
            from sqlalchemy import text as sa_text
            rows = [
                {
                    "job_id": job_id,
                    "file_path": r.path,
                    "file_type": r.file_type,
                    "success": r.success,
                    "text_content": (r.text_content or "")[:4000],  # guard column width
                    "error": r.error,
                    "processing_time_ms": r.processing_time_ms,
                    "processed_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
                }
                for r in results
            ]
            insert_sql = sa_text(
                """
                INSERT INTO file_batch_results
                    (job_id, file_path, file_type, success, text_content,
                     error, processing_time_ms, processed_at)
                VALUES
                    (:job_id, :file_path, :file_type, :success, :text_content,
                     :error, :processing_time_ms, :processed_at)
                ON CONFLICT DO NOTHING
                """
            )
            db = self.db_session_factory()
            try:
                db.execute(insert_sql, rows)
                db.commit()
            finally:
                db.close()
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("PG flush failed (batch will continue): %s", exc)

    # ------------------------------------------------------------------
    # Neo4j lineage (genealogy)
    # ------------------------------------------------------------------

    async def _neo4j_write_lineage(self, job_id: str, results: List[FileResult]) -> None:
        """Bulk-write file lineage nodes to Neo4j in a single UNWIND call."""
        if not self.neo4j_driver:
            return
        try:
            rows = [
                {
                    "job_id": job_id,
                    "file_path": r.path,
                    "file_type": r.file_type,
                    "success": r.success,
                    "error": r.error or "",
                    "processing_time_ms": r.processing_time_ms,
                    "processed_at": datetime.now(timezone.utc).isoformat(),
                }
                for r in results
            ]
            cypher = """
            UNWIND $rows AS row
            MERGE (j:BatchJob {job_id: row.job_id})
            CREATE (f:ProcessedFile {
                file_path:          row.file_path,
                file_type:          row.file_type,
                success:            row.success,
                error:              row.error,
                processing_time_ms: row.processing_time_ms,
                processed_at:       datetime(row.processed_at)
            })
            CREATE (j)-[:PROCESSED_FILE]->(f)
            """
            await self.neo4j_driver.execute_query(cypher, {"rows": rows})
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("Neo4j lineage write failed (batch will continue): %s", exc)

    # ------------------------------------------------------------------
    # Report record
    # ------------------------------------------------------------------

    async def _write_report(self, report: BatchReport) -> None:
        """Write the aggregate batch report to Postgres."""
        if not self.db_session_factory:
            return
        try:
            from sqlalchemy import text as sa_text
            sql = sa_text(
                """
                INSERT INTO file_batch_jobs
                    (job_id, started_at, completed_at, total_files,
                     processed, succeeded, failed, skipped)
                VALUES
                    (:job_id, :started_at, :completed_at, :total_files,
                     :processed, :succeeded, :failed, :skipped)
                ON CONFLICT (job_id) DO UPDATE SET
                    completed_at = EXCLUDED.completed_at,
                    processed    = EXCLUDED.processed,
                    succeeded    = EXCLUDED.succeeded,
                    failed       = EXCLUDED.failed
                """
            )
            db = self.db_session_factory()
            try:
                db.execute(sql, {
                    "job_id":       report.job_id,
                    "started_at":   report.started_at.replace(tzinfo=None).isoformat(),
                    "completed_at": report.completed_at.replace(tzinfo=None).isoformat() if report.completed_at else None,
                    "total_files":  report.total_files,
                    "processed":    report.processed,
                    "succeeded":    report.succeeded,
                    "failed":       report.failed,
                    "skipped":      report.skipped,
                })
                db.commit()
            finally:
                db.close()
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("Report write failed: %s", exc)


# ---------------------------------------------------------------------------
# Schema bootstrap helper (call once from init_db_schema)
# ---------------------------------------------------------------------------

_CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS file_batch_jobs (
    job_id          TEXT        PRIMARY KEY,
    started_at      TIMESTAMP   NOT NULL,
    completed_at    TIMESTAMP,
    total_files     INTEGER     NOT NULL DEFAULT 0,
    processed       INTEGER     NOT NULL DEFAULT 0,
    succeeded       INTEGER     NOT NULL DEFAULT 0,
    failed          INTEGER     NOT NULL DEFAULT 0,
    skipped         INTEGER     NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS file_batch_results (
    id                  SERIAL      PRIMARY KEY,
    job_id              TEXT        NOT NULL REFERENCES file_batch_jobs(job_id) ON DELETE CASCADE,
    file_path           TEXT        NOT NULL,
    file_type           TEXT,
    success             BOOLEAN     NOT NULL DEFAULT FALSE,
    text_content        TEXT,
    error               TEXT,
    processing_time_ms  INTEGER,
    processed_at        TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_file_batch_results_job ON file_batch_results(job_id);
CREATE INDEX IF NOT EXISTS idx_file_batch_results_type ON file_batch_results(file_type);
"""


def ensure_schema(engine) -> None:
    """Create batch processing tables if they don't exist. Safe to call repeatedly."""
    from sqlalchemy import text as sa_text
    with engine.connect() as conn:
        conn.execute(sa_text(_CREATE_TABLES_SQL))
        conn.commit()
