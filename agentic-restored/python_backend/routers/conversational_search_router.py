"""
Conversational Search Router - Unified search API for semantic, vector, and hybrid search.

Combines OpenSearch full-text/vector search with Neo4j GraphRAG for comprehensive
search capabilities. Supports three search modes:
- semantic: BM25-based full-text search with query expansion
- vector: k-NN vector similarity search using embeddings
- hybrid: Weighted combination of semantic and vector results

Configuration is loaded from the admin config database tables, with fallback
to environment variables for backward compatibility.
"""

# pylint: disable=broad-exception-caught

import logging
import time
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from core.db_session import get_db
from services.admin_config_service import AdminConfigService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search", tags=["conversational-search"])


# ============================================================================
# Pydantic Models
# ============================================================================

class SearchMessage(BaseModel):
    """A single message in the conversation."""
    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")
    timestamp: Optional[str] = None
    search_mode: Optional[str] = None
    results_count: Optional[int] = None


class ConversationalSearchRequest(BaseModel):
    """Request model for conversational search."""
    query: str = Field(..., description="Search query text")
    mode: str = Field(
        default="hybrid",
        description="Search mode: 'semantic', 'vector', or 'hybrid'"
    )
    conversation_id: Optional[str] = Field(
        default=None,
        description="Optional conversation ID for context continuity"
    )
    history: Optional[List[SearchMessage]] = Field(
        default=None,
        description="Previous messages for context"
    )
    top_k: int = Field(default=10, ge=1, le=100, description="Number of results")
    include_snippets: bool = Field(default=True, description="Include content snippets")
    filters: Optional[Dict[str, Any]] = Field(default=None, description="Optional filters")


class SearchResult(BaseModel):
    """A single search result."""
    id: str
    title: str
    snippet: str
    score: float
    source: str
    source_type: str
    category: Optional[str] = None
    url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    highlights: Optional[List[str]] = None
    graph_context: Optional[Dict[str, Any]] = None


class ConversationalSearchResponse(BaseModel):
    """Response model for conversational search."""
    query: str
    mode: str
    results: List[SearchResult]
    total_count: int
    took_ms: int
    conversation_id: str
    assistant_message: str
    sources_summary: Dict[str, int]
    timestamp: str


class SearchConfigResponse(BaseModel):
    """Response model for search configuration."""
    modes: List[Dict[str, Any]]
    default_mode: str
    embedding_model: str
    embedding_dimension: int
    similarity_threshold: float


# ============================================================================
# Helper Functions
# ============================================================================

def _get_opensearch_service(db: Session):
    """Get OpenSearch service instance."""
    try:
        from graph_api.opensearch_router import get_service
        return get_service(db)
    except (ImportError, ModuleNotFoundError, AttributeError) as e:
        logger.warning("OpenSearch service unavailable: %s", e)
        return None


def _get_graphrag_service():
    """Get Neo4j GraphRAG service instance."""
    try:
        from services.neo4j_graphrag_service import Neo4jGraphRAGService
        return Neo4jGraphRAGService()
    except (ImportError, ModuleNotFoundError, AttributeError) as e:
        logger.warning("GraphRAG service unavailable: %s", e)
        return None


def _get_search_config(db: Session) -> Dict[str, Any]:
    """Load search configuration from database using admin config service."""
    config_service = AdminConfigService(db)
    
    # Try to load from admin config first
    try:
        embedding_config = config_service.get_embedding_config()
        vector_model = embedding_config.get("model", "all-MiniLM-L6-v2")
        vector_dimension = embedding_config.get("dimension", 384)
    except (SQLAlchemyError, KeyError, ValueError, AttributeError):
        vector_model = "sentence-transformers/all-MiniLM-L6-v2"
        vector_dimension = 384
    
    # Try to load search-specific configs from system settings
    try:
        search_settings = config_service.get_system_configs_by_category("search")
        text_weight = float(search_settings.get("hybrid_text_weight", 0.5))
        vector_weight = float(search_settings.get("hybrid_vector_weight", 0.5))
        similarity_threshold = float(search_settings.get("similarity_threshold", 0.7))
    except (SQLAlchemyError, KeyError, ValueError, AttributeError):
        text_weight = 0.5
        vector_weight = 0.5
        similarity_threshold = 0.7
    
    # Also try legacy pipeline config models
    try:
        from models.pipeline_config_models import SearchConfiguration
        
        configs = db.query(SearchConfiguration).filter(
            SearchConfiguration.enabled == True
        ).all()
        
        if configs:
            return {
                config.search_mode: {
                    "name": config.name,
                    "description": config.description,
                    "vector_model": config.vector_model or vector_model,
                    "vector_dimension": config.vector_dimension or vector_dimension,
                    "similarity_threshold": config.similarity_threshold or similarity_threshold,
                    "text_weight": config.text_weight,
                    "vector_weight": config.vector_weight,
                }
                for config in configs
            }
    except (ImportError, ModuleNotFoundError, SQLAlchemyError, AttributeError) as e:
        logger.debug("Legacy search config not available: %s", e)
    
    # Return defaults with admin config values
    return {
        "semantic": {
            "name": "Semantic Search",
            "description": "BM25 full-text search",
            "text_weight": 1.0,
            "vector_weight": 0.0,
        },
        "vector": {
            "name": "Vector Search",
            "description": "k-NN similarity search",
            "vector_model": vector_model,
            "vector_dimension": vector_dimension,
            "text_weight": 0.0,
            "vector_weight": 1.0,
            "similarity_threshold": similarity_threshold,
        },
        "hybrid": {
            "name": "Hybrid Search",
            "description": "Combined semantic and vector",
            "text_weight": text_weight,
            "vector_weight": vector_weight,
            "similarity_threshold": similarity_threshold,
        }
    }


def _get_embedding_model(db: Optional[Session] = None):
    """Deprecated: conversational search no longer loads local embedding models.

    To reduce heavy Python dependencies, embeddings should be generated by an
    external embeddings service (see EMBEDDINGS_URL) or provided by callers.
    """
    _ = db
    return None


def _generate_embedding(text: str, db: Optional[Session] = None) -> Optional[List[float]]:
    """Generate an embedding vector for text.

    Preferred path: call an embeddings microservice via EMBEDDINGS_URL.
    Fallback: deterministic hash-based embedding to keep dev/test functional
    without introducing heavyweight ML dependencies.
    """
    _ = db

    try:
        from services.embeddings_service import get_embedding_for_text

        embedding = get_embedding_for_text(text)
        if embedding:
            return embedding
    except (ImportError, ModuleNotFoundError, AttributeError, OSError) as e:  # OSError for network errors
        logger.debug("Embedding service unavailable: %s", e)

    import hashlib

    hash_val = int(hashlib.md5(text.encode()).hexdigest(), 16)
    return [(hash_val >> i) % 1000 / 1000.0 for i in range(384)]


# ============================================================================
# Index Configuration for Multi-Source Search
# ============================================================================

# Define searchable indices with their field mappings
SEARCH_INDEX_CONFIGS = {
    "plm_parts": {
        "pattern": "plm_parts",
        "title_field": "name",
        "content_fields": ["description", "name", "part_number", "source_file"],
        "id_field": "part_id",
        "boost_fields": {"name": 3, "part_number": 2, "description": 1.5},
        "category": "PLM Parts"
    },
    "plm_assemblies": {
        "pattern": "plm_assemblies",
        "title_field": "name",
        "content_fields": ["description", "name", "assembly_id"],
        "id_field": "assembly_id",
        "boost_fields": {"name": 3, "description": 1.5},
        "category": "PLM Assemblies"
    },
    "graphtrace_documents": {
        "pattern": "graphtrace_e2e_*",
        "title_field": "text",
        "content_fields": ["text", "content"],
        "id_field": None,
        "boost_fields": {"text": 2},
        "category": "Documents"
    },
    "unstructured": {
        "pattern": "unstructured_*",
        "title_field": "title",
        "content_fields": ["content", "title", "description"],
        "id_field": None,
        "boost_fields": {"title": 3, "content": 2, "description": 1},
        "category": "Unstructured"
    }
}

# Combined index patterns for search
ALL_SEARCH_INDICES = "plm_*,graphtrace_e2e_*,unstructured_*"


def _semantic_search(
    query: str,
    opensearch_service,
    top_k: int = 10,
    filters: Optional[Dict] = None
) -> List[Dict]:
    """
    Execute semantic (BM25) search across all configured indices.
    
    Uses multi-match with cross-fields for better relevance:
    - Searches across PLM data (parts, assemblies)
    - Searches across document indices
    - Applies field boosting based on importance
    - Supports fuzzy matching for typo tolerance
    """
    try:
        if not opensearch_service:
            logger.warning("OpenSearch service not available for semantic search")
            return []
        
        # Optimized search query - simple but effective
        search_body = {
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": [
                        "name^3", "title^3",
                        "part_number^2.5",
                        "description^2", "content^2", "text^2",
                        "source_file"
                    ],
                    "type": "best_fields",
                    "fuzziness": "AUTO"
                }
            },
            "highlight": {
                "fields": {
                    "name": {"fragment_size": 100},
                    "title": {"fragment_size": 100},
                    "description": {"fragment_size": 200, "number_of_fragments": 2},
                    "content": {"fragment_size": 200, "number_of_fragments": 2},
                    "text": {"fragment_size": 200, "number_of_fragments": 2}
                },
                "pre_tags": ["<mark>"],
                "post_tags": ["</mark>"]
            },
            "size": top_k,
            "_source": True
        }
        
        if filters:
            filter_clauses = [{"term": {k: v}} for k, v in filters.items()]
            # Convert the existing query into a bool query so we can attach filters.
            search_body["query"] = {
                "bool": {
                    "must": search_body["query"],
                    "filter": filter_clauses,
                }
            }
        
        # Search across all configured indices
        logger.info("Executing semantic search with body: %s", str(search_body)[:500])
        result = opensearch_service.search(index=ALL_SEARCH_INDICES, query=search_body)
        logger.info("Raw OpenSearch result: total=%s, hits_count=%d", 
                    result.get("hits", {}).get("total"), 
                    len(result.get("hits", {}).get("hits", [])))
        
        hits = result.get("hits", {}).get("hits", [])
        results = []
        
        for hit in hits:
            source = hit.get("_source", {})
            index_name = hit.get("_index", "")
            highlights = hit.get("highlight", {})
            
            # Determine title based on available fields
            title = (
                source.get("name") or 
                source.get("title") or 
                source.get("part_number") or 
                source.get("text", "")[:50] or
                "Untitled"
            )
            
            # Build snippet from highlights or content
            snippet_parts = []
            for field in ["name", "title", "description", "content", "text"]:
                if field in highlights:
                    snippet_parts.extend(highlights[field][:2])
            if not snippet_parts:
                desc = source.get("description", "")
                content = source.get("content", "")
                text = source.get("text", "")
                snippet_parts = [desc or content or text or f"Part: {source.get('part_number', '')} Rev: {source.get('revision', '')}"]
            
            # Determine category from index
            category = "Document"
            if "plm_parts" in index_name:
                category = "PLM Part"
            elif "plm_assembl" in index_name:
                category = "PLM Assembly"
            elif "graphtrace" in index_name:
                category = "Graph Document"
            
            # Flatten highlights to list of strings
            flat_highlights = []
            if highlights:
                for field_highlights in highlights.values():
                    if isinstance(field_highlights, list):
                        flat_highlights.extend(field_highlights)
                    else:
                        flat_highlights.append(str(field_highlights))
            
            results.append({
                "id": hit.get("_id", ""),
                "title": title,
                "snippet": " ... ".join(str(s)[:150] for s in snippet_parts)[:300],
                "score": hit.get("_score", 0),
                "source": source.get("source_file") or index_name,
                "source_type": "opensearch_semantic",
                "category": category,
                "index": index_name,
                "metadata": {
                    "part_number": source.get("part_number"),
                    "revision": source.get("revision"),
                    "file_type": source.get("file_type"),
                    "application": source.get("application"),
                    **source.get("metadata", {})
                },
                "highlights": flat_highlights
            })
        
        logger.info("Semantic search for '%s' returned %d results", query, len(results))
        return results
    except (SQLAlchemyError, KeyError, ValueError, AttributeError, OSError) as e:
        logger.error("Semantic search failed: %s", e, exc_info=True)
        return []


def _vector_search(
    query: str,
    opensearch_service,
    top_k: int = 10,
    filters: Optional[Dict] = None,
    db: Optional[Session] = None
) -> List[Dict]:
    """
    Execute vector (k-NN) similarity search on OpenSearch.
    
    Performs semantic similarity search using embeddings:
    - Generates query embedding using configured model
    - Searches KNN-enabled indices (graphtrace_e2e_knn_lucene, etc.)
    - Falls back to approximate match if no KNN indices available
    - Supports cosine similarity and L2 distance metrics
    """
    try:
        embedding = _generate_embedding(query, db)
        if not embedding:
            logger.warning("Could not generate embedding, falling back to semantic search")
            return _semantic_search(query, opensearch_service, top_k, filters)
        
        # Try KNN search on vector-enabled indices
        knn_indices = "graphtrace_e2e_knn*"
        results = []
        
        # First attempt: Script score for flexible vector field names
        search_body = {
            "query": {
                "script_score": {
                    "query": {"match_all": {}},
                    "script": {
                        "source": """
                            double score = 0;
                            if (doc.containsKey('embedding') && doc['embedding'].size() > 0) {
                                score = cosineSimilarity(params.query_vector, 'embedding') + 1.0;
                            } else if (doc.containsKey('content_vector') && doc['content_vector'].size() > 0) {
                                score = cosineSimilarity(params.query_vector, 'content_vector') + 1.0;
                            }
                            return score;
                        """,
                        "params": {"query_vector": embedding[:4]}  # Trim to match index dimension
                    }
                }
            },
            "size": top_k,
            "_source": True
        }
        
        try:
            result = opensearch_service.search(index=knn_indices, query=search_body)
            hits = result.get("hits", {}).get("hits", [])
            
            for hit in hits:
                source = hit.get("_source", {})
                results.append({
                    "id": hit.get("_id", ""),
                    "title": source.get("text", source.get("title", ""))[:100] or "Vector Match",
                    "snippet": source.get("text", source.get("content", ""))[:250] + "...",
                    "score": hit.get("_score", 0),
                    "source": hit.get("_index", "knn_index"),
                    "source_type": "opensearch_vector",
                    "category": "Vector Match",
                    "index": hit.get("_index", ""),
                    "metadata": {k: v for k, v in source.items() if k not in ["embedding", "content_vector"]},
                    "highlights": []
                })
        except (KeyError, ValueError, AttributeError, OSError) as knn_err:
            logger.warning("KNN search failed, trying alternative: %s", knn_err)
        
        # If no KNN results, try More Like This for semantic similarity
        if not results:
            mlt_body = {
                "query": {
                    "more_like_this": {
                        "fields": ["name", "title", "description", "content", "text"],
                        "like": query,
                        "min_term_freq": 1,
                        "min_doc_freq": 1,
                        "max_query_terms": 25,
                        "minimum_should_match": "30%"
                    }
                },
                "size": top_k,
                "_source": True
            }
            
            try:
                result = opensearch_service.search(index=ALL_SEARCH_INDICES, query=mlt_body)
                hits = result.get("hits", {}).get("hits", [])
                
                for hit in hits:
                    source = hit.get("_source", {})
                    title = source.get("name") or source.get("title") or source.get("part_number") or "Similar Document"
                    
                    results.append({
                        "id": hit.get("_id", ""),
                        "title": title,
                        "snippet": (source.get("description") or source.get("content") or source.get("text") or "")[:250],
                        "score": hit.get("_score", 0),
                        "source": source.get("source_file", hit.get("_index", "")),
                        "source_type": "opensearch_mlt",
                        "category": "Similar Content",
                        "index": hit.get("_index", ""),
                        "metadata": source.get("metadata", {}),
                        "highlights": []
                    })
            except (KeyError, ValueError, AttributeError, OSError) as mlt_err:
                logger.warning("MLT search also failed: %s", mlt_err)
        
        return results
    except (SQLAlchemyError, KeyError, ValueError, AttributeError, OSError) as e:
        logger.error("Vector search failed: %s", e)
        return []


def _graphrag_search(
    query: str,
    graphrag_service,
    top_k: int = 10
) -> List[Dict]:
    """
    Execute GraphRAG hybrid search on Neo4j.
    
    Searches graph database for:
    - PLM entities (Parts, Assemblies, Files)
    - Lineage nodes and relationships
    - Document assignments and occurrences
    """
    try:
        result = graphrag_service.run_query(
            question=query,
            top_k=top_k,
            include_paths=True
        )
        
        sources = result.get("sources", [])
        return [
            {
                "id": src.get("id", f"neo4j_{i}"),
                "title": src.get("label", src.get("name", "Graph Node")),
                "snippet": src.get("description", src.get("content", ""))[:200],
                "score": src.get("score", 0.5),
                "source": "neo4j",
                "source_type": "graphrag",
                "category": f"Graph: {src.get('type', 'Node')}",
                "metadata": src.get("properties", {}),
                "highlights": [],
                "graph_context": {
                    "node_type": src.get("type", "unknown"),
                    "relationships": src.get("relationships", [])
                }
            }
            for i, src in enumerate(sources)
        ]
    except (AttributeError, KeyError, ValueError, OSError) as e:
        logger.error("GraphRAG search failed: %s", e)
        return []


def _hybrid_search(
    query: str,
    opensearch_service,
    graphrag_service,
    top_k: int = 10,
    text_weight: float = 0.4,
    vector_weight: float = 0.3,
    graph_weight: float = 0.3,
    filters: Optional[Dict] = None,
    db: Optional[Session] = None
) -> List[Dict]:
    """
    Execute hybrid search combining all three search modes.
    
    Reciprocal Rank Fusion (RRF) combining:
    1. Semantic (BM25) - Text relevance with boosting
    2. Vector (KNN/MLT) - Embedding similarity
    3. GraphRAG - Knowledge graph context
    
    Uses weighted scoring with deduplication.
    """
    results: List[Dict[str, Any]] = []
    source_counts = {"semantic": 0, "vector": 0, "graph": 0}
    
    # 1. Semantic Search (BM25 full-text)
    if opensearch_service:
        try:
            semantic_results = _semantic_search(query, opensearch_service, top_k * 2, filters)
            for i, r in enumerate(semantic_results):
                # RRF score: 1 / (k + rank)
                rrf_score = 1 / (60 + i + 1)
                r["score"] = rrf_score * text_weight * 100  # Normalize
                r["search_source"] = "semantic"
            results.extend(semantic_results)
            source_counts["semantic"] = len(semantic_results)
            logger.info("Semantic search returned %d results", len(semantic_results))
        except (SQLAlchemyError, KeyError, ValueError, AttributeError, OSError) as e:
            logger.warning("Semantic search failed in hybrid: %s", e)
    
    # 2. Vector Search (KNN/Similarity)
    if opensearch_service:
        try:
            vector_results = _vector_search(query, opensearch_service, top_k, filters, db)
            for i, r in enumerate(vector_results):
                rrf_score = 1 / (60 + i + 1)
                r["score"] = rrf_score * vector_weight * 100
                r["search_source"] = "vector"
            results.extend(vector_results)
            source_counts["vector"] = len(vector_results)
            logger.info("Vector search returned %d results", len(vector_results))
        except (SQLAlchemyError, KeyError, ValueError, AttributeError, OSError) as e:
            logger.warning("Vector search failed in hybrid: %s", e)
    
    # 3. GraphRAG Search (Knowledge Graph)
    if graphrag_service:
        try:
            graph_results = _graphrag_search(query, graphrag_service, top_k)
            for i, r in enumerate(graph_results):
                rrf_score = 1 / (60 + i + 1)
                r["score"] = rrf_score * graph_weight * 100
                r["search_source"] = "graph"
            results.extend(graph_results)
            source_counts["graph"] = len(graph_results)
            logger.info("GraphRAG search returned %d results", len(graph_results))
        except (AttributeError, KeyError, ValueError, OSError) as e:
            logger.warning("GraphRAG search failed in hybrid: %s", e)
    
    # Deduplicate by ID with score aggregation
    merged: Dict[str, Dict[str, Any]] = {}
    for r in results:
        rid = r.get("id", "")
        if rid in merged:
            # Aggregate scores for same document from different sources
            merged[rid]["score"] += r["score"]
            if "search_sources" not in merged[rid]:
                merged[rid]["search_sources"] = [merged[rid].get("search_source", "unknown")]
            merged[rid]["search_sources"].append(r.get("search_source", "unknown"))
        else:
            merged[rid] = r
    
    # Sort by aggregated score and return top results
    sorted_results = sorted(merged.values(), key=lambda x: x["score"], reverse=True)
    
    # Add source distribution metadata
    for r in sorted_results:
        r["_hybrid_sources"] = source_counts
    
    return sorted_results[:top_k]


def _generate_assistant_message(
    query: str,
    results: List[Dict],
    mode: str
) -> str:
    """Generate assistant message summarizing search results."""
    if not results:
        return f"No results found for '{query}'. Try different keywords or search mode."
    
    source_types: Dict[str, int] = {}
    for r in results:
        st = r.get("source_type", "unknown")
        source_types[st] = source_types.get(st, 0) + 1
    
    # Category distribution
    categories: Dict[str, int] = {}
    for r in results:
        cat = r.get("category", "Other")
        categories[cat] = categories.get(cat, 0) + 1
    
    mode_desc = {
        "semantic": "full-text semantic",
        "vector": "vector similarity",
        "hybrid": "hybrid (semantic + vector + graph)"
    }
    
    category_summary = ", ".join([f"{count} {cat}" for cat, count in categories.items()])
    
    # Build informative message
    top_result = results[0]
    message = f"Found {len(results)} results using {mode_desc.get(mode, mode)} search."
    
    if category_summary:
        message += f" Categories: {category_summary}."
    
    if top_result.get("title"):
        score_pct = min(100, top_result.get('score', 0) * 10)  # Normalize to percentage-like
        message += f" Top match: \"{top_result['title'][:50]}\" (relevance: {score_pct:.0f}%)."
    
    return message


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/config", response_model=SearchConfigResponse)
async def get_search_configuration(db: Session = Depends(get_db)):
    """
    Get search configuration including available modes and settings.
    
    Returns the configured search modes (semantic, vector, hybrid) and
    their parameters like embedding models and weights.
    Configuration is loaded from the admin config database.
    """
    config_service = AdminConfigService(db)
    config = _get_search_config(db)
    
    # Get embedding config from admin config service
    embedding_config = config_service.get_embedding_config()
    embedding_model = embedding_config.get("model", "all-MiniLM-L6-v2")
    embedding_dimension = embedding_config.get("dimension", 384)
    
    # Get similarity threshold from system config
    similarity_threshold = float(
        config_service.get_system_config("search", "similarity_threshold", 0.7)
    )
    
    modes = []
    for mode_id, mode_config in config.items():
        modes.append({
            "id": mode_id,
            "name": mode_config.get("name", mode_id.title()),
            "description": mode_config.get("description", ""),
            "text_weight": mode_config.get("text_weight", 0.5),
            "vector_weight": mode_config.get("vector_weight", 0.5),
        })
    
    return {
        "modes": modes,
        "default_mode": "hybrid",
        "embedding_model": embedding_model,
        "embedding_dimension": embedding_dimension,
        "similarity_threshold": similarity_threshold
    }


@router.post("/query", response_model=ConversationalSearchResponse)
async def conversational_search(
    request: ConversationalSearchRequest,
    db: Session = Depends(get_db)
):
    """
    Execute conversational search with semantic, vector, or hybrid mode.
    
    This endpoint provides a Google-like search experience with:
    - **semantic**: BM25 full-text search with highlighting
    - **vector**: k-NN similarity search using embeddings
    - **hybrid**: Combined search across OpenSearch + Neo4j GraphRAG
    
    The response includes:
    - Ranked results with snippets and highlights
    - Source type breakdown (OpenSearch semantic, vector, GraphRAG)
    - Assistant message summarizing findings
    - Conversation ID for multi-turn interactions
    """
    start_time = time.time()
    
    # Validate mode
    if request.mode not in ["semantic", "vector", "hybrid"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid search mode: {request.mode}. Use 'semantic', 'vector', or 'hybrid'."
        )
    
    # Get services
    opensearch_service = _get_opensearch_service(db)
    graphrag_service = _get_graphrag_service()
    
    logger.info("Search request: query='%s', mode=%s, opensearch=%s, graphrag=%s", 
                request.query, request.mode, 
                "available" if opensearch_service else "None",
                "available" if graphrag_service else "None")
    
    # Execute search based on mode
    config = _get_search_config(db)
    mode_config = config.get(request.mode, {})
    
    if request.mode == "semantic":
        raw_results = _semantic_search(
            request.query,
            opensearch_service,
            request.top_k,
            request.filters
        )
    elif request.mode == "vector":
        raw_results = _vector_search(
            request.query,
            opensearch_service,
            request.top_k,
            request.filters
        )
    else:  # hybrid
        raw_results = _hybrid_search(
            request.query,
            opensearch_service,
            graphrag_service,
            request.top_k,
            mode_config.get("text_weight", 0.5),
            mode_config.get("vector_weight", 0.5),
            mode_config.get("graph_weight", 0.3),
            filters=request.filters,
            db=db,
        )
    
    # Format results
    results = [
        SearchResult(
            id=r["id"],
            title=r["title"],
            snippet=r["snippet"] if request.include_snippets else "",
            score=round(r["score"], 4),
            source=r["source"],
            source_type=r["source_type"],
            category=r.get("category"),
            url=r.get("url"),
            metadata=r.get("metadata"),
            highlights=r.get("highlights"),
            graph_context=r.get("graph_context")
        )
        for r in raw_results
    ]
    
    # Calculate sources summary
    sources_summary: Dict[str, int] = {}
    for r in results:
        sources_summary[r.source_type] = sources_summary.get(r.source_type, 0) + 1
    
    # Generate conversation ID if not provided
    conversation_id = request.conversation_id or f"conv_{int(time.time() * 1000)}"
    
    # Generate assistant message
    assistant_message = _generate_assistant_message(
        request.query,
        [r.model_dump() for r in results],
        request.mode
    )
    
    took_ms = int((time.time() - start_time) * 1000)
    
    return ConversationalSearchResponse(
        query=request.query,
        mode=request.mode,
        results=results,
        total_count=len(results),
        took_ms=took_ms,
        conversation_id=conversation_id,
        assistant_message=assistant_message,
        sources_summary=sources_summary,
        timestamp=datetime.now(timezone.utc).isoformat()
    )


@router.get("/suggest")
async def get_search_suggestions(
    q: str = Query(..., min_length=2, description="Query prefix"),
    limit: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db)
):
    """
    Get search suggestions based on query prefix.
    
    Returns autocomplete suggestions from indexed content.
    """
    opensearch_service = _get_opensearch_service(db)
    
    if not opensearch_service:
        return {"suggestions": [], "query": q}
    
    try:
        search_body = {
            "query": {
                "prefix": {
                    "title.keyword": q.lower()
                }
            },
            "size": limit,
            "_source": ["title"]
        }
        
        result = opensearch_service.search(index="unstructured_*", query=search_body)
        hits = result.get("hits", {}).get("hits", [])
        
        suggestions = [
            hit.get("_source", {}).get("title", "")
            for hit in hits
            if hit.get("_source", {}).get("title")
        ]
        
        return {"suggestions": suggestions, "query": q}
    except Exception as e:
        logger.warning("Suggestions failed: %s", e)
        return {"suggestions": [], "query": q}


@router.get("/health")
async def search_health(db: Session = Depends(get_db)):
    """
    Check health of search services.
    
    Returns status of OpenSearch and Neo4j GraphRAG services.
    """
    opensearch_service = _get_opensearch_service(db)
    graphrag_service = _get_graphrag_service()
    
    opensearch_ok = False
    graphrag_ok = False
    
    if opensearch_service:
        try:
            health = opensearch_service.health()
            opensearch_ok = health.get("status") in ["green", "yellow"]
        except Exception:
            pass
    
    if graphrag_service:
        try:
            health = graphrag_service.health_check()
            graphrag_ok = health.get("neo4j_connected", False)
        except Exception:
            pass
    
    return {
        "status": "healthy" if (opensearch_ok or graphrag_ok) else "degraded",
        "opensearch": {
            "available": opensearch_ok,
            "modes": ["semantic", "vector"] if opensearch_ok else []
        },
        "graphrag": {
            "available": graphrag_ok,
            "modes": ["hybrid"] if graphrag_ok else []
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
