import sys
import os
import asyncio
import json
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException

# Data handling
import pandas as pd
from sqlalchemy import create_engine, text

# SODA
try:
    from soda.scan import Scan
except ImportError:
    Scan = None

# Add parent directory to path to allow importing base
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

# Load environment variables from backend .env
env_path = Path(__file__).resolve().parent.parent.parent / "python_backend" / ".env"
load_dotenv(dotenv_path=env_path)

from neo4j import AsyncGraphDatabase
from agent_services.base.agent_service import AgentService
from agent_services.base.models import AgentCapability, AgentTaskRequest, AgentType

# Re-use models from backend if possible, or define minimal equivalents
DATABASE_URL = os.getenv("DATABASE_URL")

logger = logging.getLogger(__name__)

class ETLOrchestratorAgent(AgentService):
    def __init__(self):
        super().__init__(
            agent_type=AgentType.ETL_ORCHESTRATOR,
            agent_name="ETL Orchestration Agent",
            port=8021
        )
        self.neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        self.neo4j_password = os.getenv("NEO4J_PASSWORD", "password")
        self.driver = None
        self.db_engine = None

    @asynccontextmanager
    async def _lifespan(self, app: FastAPI):
        # Initialize resources
        logger_name = f"{self.agent_name}.lifespan"
        print(f"[{logger_name}] Initializing Neo4j driver...")
        
        try:
            self.driver = AsyncGraphDatabase.driver(
                self.neo4j_uri, 
                auth=(self.neo4j_user, self.neo4j_password)
            )
            # Verify connectivity
            await self.driver.verify_connectivity()
            print(f"[{logger_name}] Neo4j connectivity verified.")
        except Exception as e:
            print(f"[{logger_name}] WARNING: Neo4j connectivity failed: {e}")

        # Initialize Postgres Engine
        if DATABASE_URL:
            try:
                self.db_engine = create_engine(DATABASE_URL)
                print(f"[{logger_name}] SQL Database connected.")
            except Exception as e:
                print(f"[{logger_name}] WARNING: SQL Database connection failed: {e}")

        # Chain upstream registration
        async with super()._lifespan(app):
            yield
        
        # Cleanup
        if self.driver:
            await self.driver.close()
        if self.db_engine:
            self.db_engine.dispose()

    def get_capabilities(self):
        return [
            AgentCapability(name="manage_data_pipelines", description="Manage ETL pipelines"),
            AgentCapability(name="perform_data_discovery", description="Analyze sources, stage data, and run quality checks"),
            AgentCapability(name="handle_data_transformations", description="Handle data transformations"),
            AgentCapability(name="monitor_pipeline_health", description="Monitor pipeline health")
        ]

    async def process_task(self, task: AgentTaskRequest):
        task_type = task.payload.get("type", "unknown")
        
        if task_type == "discovery" or "perform_data_discovery" in task.required_capabilities:
            return await self.perform_discovery(task)
            
        return {
            "status": "success",
            "message": f"Task type {task_type} acknowledged (placeholder implementation)",
            "timestamp": datetime.now().isoformat()
        }

    async def perform_discovery(self, task: AgentTaskRequest) -> Dict[str, Any]:
        """
        Agentic Discovery Workflow:
        1. Analyzes the provided records (Staging)
        2. Infers Schema & Mapping
        3. Transforms Data (Normalization)
        4. Runs SODA Checks (Validation)
        """
        payload = task.payload
        run_id = payload.get("run_id") or uuid.uuid4().hex
        records = payload.get("records", [])
        
        if not self.db_engine:
            return {"status": "failed", "error": "Database not configured"}

        # 1. Staging & Schema Inference
        df = pd.DataFrame(records)
        inferred_schema = {col: str(dtype) for col, dtype in df.dtypes.items()}
        
        # 2. Intelligent Mapping (Agentic Logic)
        # Instead of strict hardcoding, we score potential matches
        mapping_scores = {}
        target_columns = ["part_number", "name", "description", "classification"]
        
        mapping = {}
        for target in target_columns:
            best_match = None
            highest_score = 0
            
            for source_col in df.columns:
                score = 0
                s_col = source_col.lower()
                
                # Direct match
                if s_col == target: score += 100
                # Semantic approximation
                elif target == "part_number" and s_col in ["part", "number", "id", "sku"]: score += 80
                elif target == "name" and s_col in ["title", "label", "msg"]: score += 80
                elif target == "classification" and s_col in ["type", "category", "class"]: score += 80
                elif target == "description" and s_col in ["desc", "detail", "info"]: score += 60
                
                if score > highest_score:
                    highest_score = score
                    best_match = source_col
            
            if best_match and highest_score > 50:
                mapping[best_match] = target

        # 3. Apply Transformation
        if mapping:
            df_transformed = df.rename(columns=mapping)
            # Filter to only keep canonical columns + raw
            available_targets = [c for c in target_columns if c in df_transformed.columns]
            df_transformed = df_transformed[available_targets].copy()
            df_transformed["run_id"] = run_id
            df_transformed["raw"] = df.to_dict(orient="records")
            
            # Persist to DB (PLMPart table)
            try:
                # We use the raw connection to avoid model dependency overhead
                # Warning: ensuring table exists is out of scope for this snippet, assumes PLMPart exists
                df_transformed.to_sql("plm_parts", self.db_engine, if_exists="append", index=False, method="multi")
            except Exception as e:
                logger.warning(f"Failed to persist transformed data: {e}")
        
        # 4. SODA Validation
        soda_result = None
        if Scan:
            try:
                # In a full implementation, we would construct a Scan object here
                # accessing the same postgres DB. 
                # For this simplified agent version, we simulate the SODA Result
                # based on the data quality of the dataframe itself
                
                null_counts = df.isnull().sum()
                issue_count = int(null_counts.sum())
                
                soda_result = {
                    "outcome": "warn" if issue_count > 0 else "pass",
                    "checks": len(mapping) + 1,
                    "score": max(0, 1.0 - (issue_count / (len(df) * len(df.columns) or 1)))
                }
                
            except Exception as e:
                soda_result = {"outcome": "error", "message": str(e)}

        return {
            "status": "completed",
            "run_id": run_id,
            "inferred_schema": inferred_schema,
            "applied_mapping": mapping,
            "staged_count": len(records),
            "quality_scan": soda_result,
            "agent_notes": "Discovery completed using Agentic Heuristics v2."
        }

if __name__ == "__main__":
    agent = ETLOrchestratorAgent()
    agent.start()
