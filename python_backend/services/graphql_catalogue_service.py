"""
GraphQL Catalogue Service - Manages persisted queries and schema cache.
Provides CRUD operations for query registry with unique name constraints.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import importlib
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError


def _utcnow() -> datetime:
    # Keep naive UTC timestamps (previous behavior) without using deprecated datetime.now(timezone.utc).replace(tzinfo=None).
    return datetime.now(timezone.utc).replace(tzinfo=None)

_graphql_models = importlib.import_module("models.graphql_models")
PersistedGraphQLQueryModel: Any = getattr(_graphql_models, "PersistedGraphQLQueryModel")
SchemaCacheModel: Any = getattr(_graphql_models, "SchemaCacheModel")


class GraphQLCatalogueService:
    """
    Service for managing GraphQL catalogue - persisted queries and schema cache.
    Enforces unique name constraint and provides ordering by updated_at.
    """
    
    def __init__(self, db_session: Session):
        """
        Initialize catalogue service with database session.
        
        Args:
            db_session: SQLAlchemy database session
        """
        self.db = db_session
    
    # Persisted Query Operations
    
    def list_queries(self, limit: int = 100, offset: int = 0, query_format: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List persisted queries ordered by updated_at descending.
        
        Args:
            limit: Maximum number of queries to return
            offset: Number of queries to skip
            query_format: Optional filter by format ('xml' or 'json')
            
        Returns:
            List of query dictionaries
        """
        query = self.db.query(PersistedGraphQLQueryModel)
        
        if query_format:
            query = query.filter(PersistedGraphQLQueryModel.format == query_format)
        
        queries = query.order_by(PersistedGraphQLQueryModel.updated_at.desc()) \
                       .limit(limit) \
                       .offset(offset) \
                       .all()
        
        return [q.to_dict() for q in queries]
    
    def get_query(self, query_id: Optional[int] = None, name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get a specific persisted query by ID or name.
        
        Args:
            query_id: Query ID
            name: Query name (unique)
            
        Returns:
            Query dictionary or None if not found
        """
        if query_id:
            query = self.db.query(PersistedGraphQLQueryModel).filter(
                PersistedGraphQLQueryModel.id == query_id
            ).first()
        elif name:
            query = self.db.query(PersistedGraphQLQueryModel).filter(
                PersistedGraphQLQueryModel.name == name
            ).first()
        else:
            return None
        
        return query.to_dict() if query else None
    
    def create_query(self, name: str, query: str, description: Optional[str] = None,
                    variables: Optional[Dict] = None, query_format: str = "json",
                    created_by: Optional[str] = None, tags: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Create a new persisted query.
        
        Args:
            name: Unique query name
            query: Query string
            description: Optional description
            variables: Optional query variables
            query_format: Query format ('xml' or 'json')
            created_by: Optional creator identifier
            tags: Optional tags for categorization
            
        Returns:
            Created query dictionary
            
        Raises:
            ValueError: If query with same name already exists
        """
        try:
            new_query = PersistedGraphQLQueryModel(
                name=name,
                query=query,
                description=description,
                variables=variables or {},
                format=query_format,
                created_by=created_by,
                tags=tags or []
            )
            
            self.db.add(new_query)
            self.db.commit()
            self.db.refresh(new_query)
            
            return new_query.to_dict()
        
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError(f"Query with name '{name}' already exists") from exc
    
    def update_query(self, query_id: int, **updates) -> Optional[Dict[str, Any]]:
        """
        Update an existing persisted query.
        
        Args:
            query_id: Query ID to update
            **updates: Fields to update
            
        Returns:
            Updated query dictionary or None if not found
        """
        query = self.db.query(PersistedGraphQLQueryModel).filter(
            PersistedGraphQLQueryModel.id == query_id
        ).first()
        
        if not query:
            return None
        
        # Update allowed fields
        for key, value in updates.items():
            if hasattr(query, key) and key not in ['id', 'created_at']:
                setattr(query, key, value)
        
        query.updated_at = _utcnow()
        
        try:
            self.db.commit()
            self.db.refresh(query)
            return query.to_dict()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("Update failed: duplicate name constraint") from exc
    
    def delete_query(self, query_id: int) -> bool:
        """
        Delete a persisted query.
        
        Args:
            query_id: Query ID to delete
            
        Returns:
            True if deleted, False if not found
        """
        query = self.db.query(PersistedGraphQLQueryModel).filter(
            PersistedGraphQLQueryModel.id == query_id
        ).first()
        
        if not query:
            return False
        
        self.db.delete(query)
        self.db.commit()
        return True
    
    # Schema Cache Operations
    
    def get_cached_schema(self, name: Optional[str] = None, 
                         schema_hash: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get cached schema by name or hash.
        
        Args:
            name: Schema name
            schema_hash: Schema content hash
            
        Returns:
            Schema dictionary or None if not found
        """
        query = self.db.query(SchemaCacheModel)
        
        if name:
            query = query.filter(SchemaCacheModel.name == name)
        elif schema_hash:
            query = query.filter(SchemaCacheModel.schema_hash == schema_hash)
        else:
            return None
        
        schema = query.first()
        
        if schema:
            # Update access tracking
            schema.access_count += 1
            schema.last_accessed_at = _utcnow()
            self.db.commit()
            self.db.refresh(schema)
        
        return schema.to_dict() if schema else None
    
    def cache_schema(self, name: str, schema_format: str, schema_hash: str,
                    fields: Dict, types: Dict, metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Cache a schema introspection result.
        
        Args:
            name: Schema name
            schema_format: Schema format ('xml' or 'json')
            schema_hash: Content hash
            fields: Field definitions
            types: Type definitions
            metadata: Optional metadata
            
        Returns:
            Cached schema dictionary
        """
        # Check if schema already exists
        existing = self.db.query(SchemaCacheModel).filter(
            SchemaCacheModel.name == name
        ).first()
        
        if existing:
            # Update existing
            existing.format = schema_format
            existing.schema_hash = schema_hash
            existing.fields = fields
            existing.types = types
            existing.metadata = metadata or {}
            existing.updated_at = _utcnow()
            self.db.commit()
            self.db.refresh(existing)
            return existing.to_dict()
        else:
            # Create new
            new_schema = SchemaCacheModel(
                name=name,
                format=schema_format,
                schema_hash=schema_hash,
                fields=fields,
                types=types,
                metadata=metadata or {}
            )
            self.db.add(new_schema)
            self.db.commit()
            self.db.refresh(new_schema)
            return new_schema.to_dict()
    
    def list_schemas(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        List cached schemas ordered by updated_at descending.
        
        Args:
            limit: Maximum number of schemas to return
            offset: Number of schemas to skip
            
        Returns:
            List of schema dictionaries
        """
        schemas = self.db.query(SchemaCacheModel) \
                         .order_by(SchemaCacheModel.updated_at.desc()) \
                         .limit(limit) \
                         .offset(offset) \
                         .all()
        
        return [s.to_dict() for s in schemas]
    
    def delete_schema(self, schema_id: int) -> bool:
        """
        Delete a cached schema.
        
        Args:
            schema_id: Schema ID to delete
            
        Returns:
            True if deleted, False if not found
        """
        schema = self.db.query(SchemaCacheModel).filter(
            SchemaCacheModel.id == schema_id
        ).first()
        
        if not schema:
            return False
        
        self.db.delete(schema)
        self.db.commit()
        return True
