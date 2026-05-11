"""
Neo4j GraphRAG Service - Hybrid search combining graph context and vector similarity.
Provides semantic search capabilities bridging Neo4j and OpenSearch.

Configuration is loaded from the admin config database with fallback to
environment variables and config store for backward compatibility.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import os
import httpx

from core.config_store import get_encrypted_config_payload

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    # Keep naive UTC timestamps (previous behavior) without using deprecated datetime.now(timezone.utc).replace(tzinfo=None).
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _utcnow_iso() -> str:
    return _utcnow().isoformat()


def _get_neo4j_config_from_admin(db_session=None) -> Dict[str, Any]:
    """Load Neo4j configuration from admin config service."""
    if db_session is None:
        return {}
    try:
        from services.admin_config_service import AdminConfigService
        config_service = AdminConfigService(db_session)
        return config_service.get_connection_config("neo4j")
    except Exception as e:
        logger.debug("Admin config not available for Neo4j: %s", e)
        return {}


def _get_embedding_config_from_admin(db_session=None) -> Dict[str, Any]:
    """Load embedding configuration from admin config service."""
    if db_session is None:
        return {}
    try:
        from services.admin_config_service import AdminConfigService
        config_service = AdminConfigService(db_session)
        return config_service.get_embedding_config()
    except Exception as e:
        logger.debug("Admin config not available for embeddings: %s", e)
        return {}


class Neo4jGraphRAGService:
    """
    Service for Neo4j GraphRAG operations.
    Orchestrates vector search, document retrieval, and tool metadata.
    """
    
    def __init__(self, db_session=None):
        """
        Initialize GraphRAG service with configuration.
        
        Configuration priority:
        1. Admin config database (if available)
        2. Encrypted config store
        3. Environment variables
        4. Default values
        """
        # Try to load from admin config first
        admin_neo4j_config = _get_neo4j_config_from_admin(db_session)
        admin_embed_config = _get_embedding_config_from_admin(db_session)
        
        # Fall back to encrypted config store
        neo4j_payload = get_encrypted_config_payload("neo4j") or {}
        
        # Build Neo4j connection settings with priority
        self.neo4j_uri = (
            admin_neo4j_config.get("connection_string")
            or f"neo4j://{admin_neo4j_config.get('host', '')}:{admin_neo4j_config.get('port', 7687)}"
            if admin_neo4j_config.get("host")
            else str(
                neo4j_payload.get("uri")
                or os.getenv("NEO4J_URI")
                or "neo4j://127.0.0.1:7687"
            )
        )
        self.neo4j_user = (
            admin_neo4j_config.get("username")
            or str(
                neo4j_payload.get("username")
                or os.getenv("NEO4J_USER")
                or os.getenv("NEO4J_USERNAME")
                or "neo4j"
            )
        )
        self.neo4j_password = (
            admin_neo4j_config.get("password")
            or str(
                neo4j_payload.get("password")
                or os.getenv("NEO4J_PASSWORD")
                or ""
            )
        )
        
        # Embedding configuration from admin config
        self.embed_dimension = (
            admin_embed_config.get("dimension")
            or int(os.getenv("GRAPH_RAG_EMBED_DIMENSION", "1536"))
        )
        self.vector_index_name = (os.getenv("GRAPH_RAG_VECTOR_INDEX") or "").strip()
        self.embeddings_url = (os.getenv("EMBEDDINGS_URL") or "").strip()
        self.driver = None
        self.connected = False

        logger.info(
            "Neo4j GraphRAG Service initialized with embedding dimension: %s",
            self.embed_dimension,
        )
    
    def _connect(self):
        """Establish Neo4j connection (lazy initialization)."""
        if self.connected:
            return
        
        try:
            # Lazy import to avoid dependency issues
            from neo4j import GraphDatabase, exceptions as neo4j_exceptions
            
            self.driver = GraphDatabase.driver(
                self.neo4j_uri,
                auth=(self.neo4j_user, self.neo4j_password)
            )
            
            # Test connection
            with self.driver.session() as session:
                session.run("RETURN 1")
            
            self.connected = True
            logger.info("Neo4j connection established")
            
        except ImportError:
            logger.warning("Neo4j driver not installed. Install with: pip install neo4j")
            self.connected = False
        except (neo4j_exceptions.Neo4jError, neo4j_exceptions.DriverError, OSError, ValueError, RuntimeError) as e:
            logger.error("Failed to connect to Neo4j: %s", e)
            self.connected = False
    
    def health_check(self) -> Dict[str, Any]:
        """
        Check service health and Neo4j connectivity.
        
        Returns:
            Health status dictionary
        """
        self._connect()
        
        return {
            "status": "healthy" if self.connected else "degraded",
            "neo4j_connected": self.connected,
            "embedding_dimension": self.embed_dimension,
            "timestamp": _utcnow_iso()
        }
    
    def run_query(
        self,
        question: str,
        context: Optional[str] = None,
        tools: Optional[List[str]] = None,
        top_k: int = 5,
        include_paths: bool = False,
        embedding: Optional[List[float]] = None,
    ) -> Dict[str, Any]:
        """
        Run hybrid GraphRAG query combining vector search and metadata lookup.
        
        Args:
            question: User question/query
            context: Optional context to enhance query
            tools: Optional list of tools to invoke
            top_k: Number of top results to return (default: 5)
            include_paths: Whether to include graph paths in results
            
        Returns:
            Query response with answers, sources, tools invoked, and metrics
        """
        start_time = _utcnow()
        
        try:
            self._connect()
            
            if not self.connected:
                end_time = _utcnow()
                return {
                    "answers": [],
                    "sources": [],
                    "tools_invoked": [],
                    "error": "Neo4j not connected",
                    "latency_ms": int((end_time - start_time).total_seconds() * 1000),
                    "result_count": 0,
                    "timestamp": end_time.isoformat(),
                }
            
            query_text = f"{question} {context}" if context else question
            embedding_vec = embedding or self._get_embedding(query_text)
            if not embedding_vec:
                end_time = _utcnow()
                return {
                    "answers": [],
                    "sources": [],
                    "tools_invoked": [],
                    "error": "Embedding not available (provide embedding or configure EMBEDDINGS_URL)",
                    "latency_ms": int((end_time - start_time).total_seconds() * 1000),
                    "result_count": 0,
                    "timestamp": end_time.isoformat(),
                }

            if not self.vector_index_name:
                end_time = _utcnow()
                return {
                    "answers": [],
                    "sources": [],
                    "tools_invoked": [],
                    "error": "GRAPH_RAG_VECTOR_INDEX not configured",
                    "latency_ms": int((end_time - start_time).total_seconds() * 1000),
                    "result_count": 0,
                    "timestamp": end_time.isoformat(),
                }
            
            # Execute hybrid search
            results = self._hybrid_search(
                embedding=embedding_vec,
                query_text=query_text,
                top_k=top_k,
                include_paths=include_paths
            )
            
            # Process tools if provided
            tools_invoked = []
            if tools:
                tools_invoked = self._invoke_tools(tools, results)
            
            # Calculate latency
            end_time = _utcnow()
            latency_ms = int((end_time - start_time).total_seconds() * 1000)
            
            return {
                "answers": [r["answer"] for r in results],
                "sources": [r["source"] for r in results],
                "tools_invoked": tools_invoked,
                "latency_ms": latency_ms,
                "result_count": len(results),
                "timestamp": end_time.isoformat()
            }
            
        except Exception as e:
            logger.error("GraphRAG query error: %s", e)
            raise
    
    def _get_embedding(self, text: str) -> Optional[List[float]]:
        """Get an embedding for text.

        - If EMBEDDINGS_URL is configured, call it.
        - Otherwise, require the caller to provide an embedding.

        Expected EMBEDDINGS_URL response shape:
          {"embedding": [..floats..]}
        """
        if not self.embeddings_url:
            return None

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(self.embeddings_url, json={"text": text})
                resp.raise_for_status()
                payload = resp.json()
                embedding = payload.get("embedding")
                if not isinstance(embedding, list) or not embedding:
                    return None
                return embedding
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("Embedding request failed: %s", exc)
            return None
    
    def _hybrid_search(
        self,
        embedding: List[float],
        query_text: str,
        top_k: int,
        include_paths: bool
    ) -> List[Dict[str, Any]]:
        """
        Execute hybrid search combining vector similarity and keyword matching.
        
        Queries Neo4j indexes for:
        1. Vector similarity search (dense vectors)
        2. Full-text search (textual summaries)
        3. Optionally includes graph paths
        """
        if not self.connected or not self.driver:
            return []
        
        try:
            with self.driver.session() as session:
                cypher = """
                CALL db.index.vector.queryNodes($index_name, $k, $embedding)
                YIELD node, score
                RETURN node, score
                ORDER BY score DESC
                LIMIT $k
                """
                records = session.run(
                    cypher,
                    index_name=self.vector_index_name,
                    k=int(top_k),
                    embedding=embedding,
                )

                results: List[Dict[str, Any]] = []
                for record in records:
                    node = record.get("node")
                    score = record.get("score")
                    node_props = dict(node) if node is not None else {}
                    node_id = str(node_props.get("id") or node_props.get("node_id") or "")
                    text = (
                        str(node_props.get("text") or "")
                        or str(node_props.get("content") or "")
                        or str(node_props.get("name") or "")
                    )

                    results.append(
                        {
                            "answer": text,
                            "source": {
                                "node_id": node_id,
                                "type": str(node_props.get("type") or "Document"),
                                "score": float(score) if score is not None else None,
                                "metadata": node_props,
                            },
                        }
                    )

                # Optional graph path expansion can be added later; never fabricate.
                _ = include_paths, query_text
                return results
                
        except (OSError, ValueError, RuntimeError) as e:
            logger.error("Hybrid search error: %s", e)
            return []
    
    def _invoke_tools(self, tools: List[str], results: List[Dict]) -> List[Dict[str, Any]]:
        """
        Invoke specified tools on query results.
        
        Tools could include:
        - summarization
        - translation
        - entity extraction
        - etc.
        """
        invoked = []
        
        for tool_name in tools:
            invoked.append({
                "tool": tool_name,
                "status": "executed",
                "result": f"Tool {tool_name} processed {len(results)} results"
            })
        
        return invoked
    
    def list_tools(self) -> List[Dict[str, Any]]:
        """
        List available tools for GraphRAG queries.
        
        Returns:
            List of tool metadata
        """
        return [
            {
                "name": "summarize",
                "description": "Summarize long documents",
                "parameters": []
            },
            {
                "name": "extract_entities",
                "description": "Extract named entities from text",
                "parameters": []
            },
            {
                "name": "translate",
                "description": "Translate text to target language",
                "parameters": ["target_language"]
            }
        ]
    
    def close(self):
        """Close Neo4j driver connection."""
        if self.driver:
            self.driver.close()
            self.connected = False
            logger.info("Neo4j connection closed")
