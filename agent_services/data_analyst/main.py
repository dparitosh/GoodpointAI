import sys
import os
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from fastapi import FastAPI

# Add parent directory to path to allow importing base
# We assume we are running from the agent_services/data_analyst directory or root
# but this ensures we can find 'agent_services' package if we run as python -m agent_services.data_analyst.main
# or python agent_services/data_analyst/main.py
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

# Load environment variables from backend .env
# This allows us to share credentials with the main backend
env_path = Path(__file__).resolve().parent.parent.parent / "python_backend" / ".env"
load_dotenv(dotenv_path=env_path)

from neo4j import AsyncGraphDatabase
import asyncpg
from agent_services.base.agent_service import AgentService
from agent_services.base.models import AgentCapability, AgentTaskRequest, AgentType

class DataAnalystAgent(AgentService):
    def __init__(self):
        super().__init__(
            agent_type=AgentType.DATA_ANALYST,
            agent_name="Data Analyst Agent",
            port=8020
        )
        self.neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        self.neo4j_password = os.getenv("NEO4J_PASSWORD", "")
        self.neo4j_driver = None
        
        # Postgres Config
        self.pg_host = "localhost" # Default, often overridden by env or DB URL
        self.pg_db = "graphtrace"
        self.pg_user = "postgres"
        self.pg_pass = os.getenv("POSTGRES_PASSWORD", "")
        self.pg_port = int(os.getenv("POSTGRES_PORT", "5432"))
        
        # Parse DATABASE_URL if present
        db_url = os.getenv("DATABASE_URL")
        if db_url and db_url.startswith("postgres"):
            # Simple parsing for postgresql://user:pass@host:port/dbname
            try:
                # Remove prefix
                if db_url.startswith("postgresql://"):
                    rest = db_url[13:]
                elif db_url.startswith("postgres://"):
                    rest = db_url[11:]
                else:
                    rest = db_url
                
                if "@" in rest:
                    creds, location = rest.split("@")
                    self.pg_user, self.pg_pass = creds.split(":")
                    if "/" in location:
                        host_port, self.pg_db = location.split("/")
                    else:
                        host_port = location
                    
                    if ":" in host_port:
                        self.pg_host, self.pg_port = host_port.split(":")
                        self.pg_port = int(self.pg_port)
                    else:
                        self.pg_host = host_port
            except Exception as e:
                print(f"Error parsing DATABASE_URL: {e}")

        self.pg_pool = None

    @asynccontextmanager
    async def _lifespan(self, _app: FastAPI):
        # Initialize Neo4j
        logger_name = f"{self.agent_name}.lifespan"
        print(f"[{logger_name}] Initializing Neo4j driver for {self.neo4j_uri}...")
        
        try:
            self.neo4j_driver = AsyncGraphDatabase.driver(
                self.neo4j_uri, 
                auth=(self.neo4j_user, self.neo4j_password)
            )
            await self.neo4j_driver.verify_connectivity()
            print(f"[{logger_name}] Neo4j connectivity verified.")
        except Exception as e:
            print(f"[{logger_name}] WARNING: Neo4j connectivity failed: {e}")

        # Initialize Postgres
        print(f"[{logger_name}] Initializing Postgres pool for {self.pg_host}:{self.pg_port}/{self.pg_db}...")
        try:
            self.pg_pool = await asyncpg.create_pool(
                user=self.pg_user,
                password=self.pg_pass,
                database=self.pg_db,
                host=self.pg_host,
                port=self.pg_port,
                min_size=1,
                max_size=5
            )
            async with self.pg_pool.acquire() as conn:
                await conn.execute("SELECT 1")
            print(f"[{logger_name}] Postgres connectivity verified.")
        except Exception as e:
            print(f"[{logger_name}] WARNING: Postgres connectivity failed: {e}")

        # Chain upstream registration logic
        async with super()._lifespan(_app):
            yield
        
        # Cleanup
        print(f"[{logger_name}] Closing drivers...")
        if self.neo4j_driver:
            await self.neo4j_driver.close()
        if self.pg_pool:
            await self.pg_pool.close()

    def get_capabilities(self):
        return [
            AgentCapability(name="data_analysis", description="Analyze graph patterns and node distributions"),
            AgentCapability(name="graph_query", description="Execute read-only queries against Neo4j"),
            AgentCapability(name="sql_query", description="Execute read-only queries against Postgres"),
            AgentCapability(name="execute_cypher_queries", description="Execute Cypher graph queries and return structured results"),
            AgentCapability(name="generate_insights", description="Generate analytical insights from graph and relational data"),
            AgentCapability(name="statistical_analysis", description="Perform statistical analysis on datasets"),
        ]

    async def process_task(self, task: AgentTaskRequest):
        caps = set(task.payload.get("required_capabilities", []))

        # Route execute_cypher_queries / graph_query to Neo4j handler
        if (
            "execute_cypher_queries" in caps
            or task.payload.get("analysis_type") == "cypher_query"
            or "cypher_query" in task.payload
        ):
            if not self.neo4j_driver:
                return {"error": "Neo4j driver not initialized"}
            query = task.payload.get("cypher_query") or task.payload.get("query")
            if not query:
                return {"error": "No cypher_query provided in payload"}
            # Security: only allow read-only clauses
            stripped = query.strip().upper()
            if not any(stripped.startswith(kw) for kw in ("MATCH", "RETURN", "WITH", "CALL", "SHOW")):
                return {"error": "Only read-only Cypher queries (MATCH/RETURN/WITH/CALL) are permitted"}
            try:
                async with self.neo4j_driver.session() as session:
                    result = await session.run(query)
                    records = [dict(r) async for r in result]
                    return {
                        "analysis_type": "cypher_query",
                        "row_count": len(records),
                        "data": records[:200],
                    }
            except Exception as e:
                return {"error": f"Cypher execution failed: {str(e)}"}

        # Handle SQL tasks
        if task.payload.get("analysis_type") == "sql_query" or "sql_query" in task.payload:
            if not self.pg_pool:
                return {"error": "Postgres driver not initialized"}
            
            query = task.payload.get("sql_query")
            if not query:
                return {"error": "No sql_query provided in payload"}

            # Security: only allow SELECT statements
            stripped = query.strip().lstrip("(").upper()
            if not stripped.startswith("SELECT"):
                return {"error": "Only SELECT queries are permitted"}

            # Enforce a row limit to prevent unbounded memory usage
            safe_query = f"SELECT * FROM ({query}) _q LIMIT 1000"

            try:
                async with self.pg_pool.acquire() as conn:
                    rows = await conn.fetch(safe_query)
                    result_data = [dict(row) for row in rows]
                    return {
                        "analysis_type": "sql_query",
                        "row_count": len(result_data),
                        "data": result_data[:100]  # Return first 100 rows
                    }
            except Exception as e:
                return {"error": f"Postgres execution failed: {str(e)}"}

        # Handle Neo4j tasks
        driver = self.neo4j_driver
        if not driver:
            return {"error": "Neo4j driver not initialized"}
        
        # Determine analysis type from payload
        analysis_type = task.payload.get("analysis_type", "simple_pattern")
        limit = task.payload.get("limit", 10)
        
        try:
            async with driver.session() as session:
                
                if analysis_type == "connectivity":
                     # Pareto Query: Focus on most connected nodes (20% that drive 80% of connections)
                    query = """
                    MATCH (n)
                    WITH n, COUNT { (n)--() } as degree
                    WHERE degree > 0
                    RETURN n.id as nodeId, labels(n) as labels, n as properties, degree
                    ORDER BY degree DESC
                    LIMIT $limit
                    """
                    result = await session.run(query, limit=limit)
                    records = [record async for record in result]
                    
                    data = []
                    for r in records:
                        data.append({
                            "nodeId": r.get("nodeId"), 
                            "labels": r.get("labels"), 
                            "degree": r.get("degree")
                        })
                    return {"analysis_type": "connectivity", "data": data}

                elif analysis_type == "centrality":
                    # Betweenness centrality approximation
                    query = """
                    MATCH (n)
                    OPTIONAL MATCH (n)-[r1]-(m)-[r2]-(o)
                    WHERE n <> o
                    WITH n, count(DISTINCT m) as betweenness_approx
                    RETURN n.id as nodeId, labels(n) as labels, betweenness_approx
                    ORDER BY betweenness_approx DESC
                    LIMIT $limit
                    """
                    result = await session.run(query, limit=limit)
                    records = [record async for record in result]
                    
                    data = []
                    for r in records:
                        data.append({
                            "nodeId": r.get("nodeId"), 
                            "score": r.get("betweenness_approx")
                        })
                    return {"analysis_type": "centrality", "data": data}

                else:
                    # Default: Simple Pattern
                    query = """
                    MATCH (n)
                    RETURN labels(n) as labels, count(n) as count
                    ORDER BY count DESC
                    LIMIT $limit
                    """
                    result = await session.run(query, limit=limit)
                    records = [record async for record in result]

                    patterns = []
                    for record in records:
                        labels = record["labels"]
                        count = record["count"]
                        if labels:
                            patterns.append(f"Found {count} nodes with label '{labels[0]}'")
                    
                    return {
                        "patterns": patterns,
                        "analysis": f"Analyzed {len(patterns)} node types",
                        "timestamp": datetime.now().isoformat()
                    }
        except Exception as e:
            # Log error here
            return {"error": f"Neo4j execution failed: {str(e)}"}

agent = DataAnalystAgent()
app = agent.app

if __name__ == "__main__":
    agent.start()
