"""
Pipeline Configuration Router

API endpoints for managing pipeline configurations, file patterns,
and search settings stored in PostgreSQL.
"""

from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from core.db_session import get_db
from models.pipeline_config_models import (
    # ORM Models
    FilePatternConfig,
    PipelineTemplate,
    SearchConfiguration,
    IndexConfiguration,
    # Pydantic Models
    FilePatternCreate,
    FilePatternUpdate,
    FilePatternResponse,
    PipelineTemplateCreate,
    PipelineTemplateUpdate,
    PipelineTemplateResponse,
    SearchConfigCreate,
    SearchConfigUpdate,
    SearchConfigResponse,
    IndexConfigCreate,
    IndexConfigUpdate,
    IndexConfigResponse,
    AllConfigurationsResponse,
    FilePatternsByCategory,
)

router = APIRouter(prefix="/config", tags=["Pipeline Configuration"])


# ============================================================
# File Patterns API
# ============================================================

@router.get("/file-patterns", response_model=List[FilePatternResponse])
async def list_file_patterns(
    category: Optional[str] = Query(None, description="Filter by category"),
    enabled_only: bool = Query(True, description="Only return enabled patterns"),
    db: Session = Depends(get_db)
):
    """List all file patterns, optionally filtered by category."""
    query = db.query(FilePatternConfig)
    
    if category:
        query = query.filter(FilePatternConfig.category == category)
    if enabled_only:
        query = query.filter(FilePatternConfig.enabled == True)
    
    return query.order_by(FilePatternConfig.category, FilePatternConfig.pattern).all()


@router.get("/file-patterns/by-category", response_model=List[FilePatternsByCategory])
async def get_file_patterns_by_category(
    enabled_only: bool = Query(True),
    db: Session = Depends(get_db)
):
    """Get file patterns grouped by category."""
    query = db.query(FilePatternConfig)
    if enabled_only:
        query = query.filter(FilePatternConfig.enabled == True)
    
    patterns = query.order_by(FilePatternConfig.category, FilePatternConfig.pattern).all()
    
    # Group by category
    categories: Dict[str, List[FilePatternConfig]] = {}
    for pattern in patterns:
        if pattern.category not in categories:
            categories[pattern.category] = []
        categories[pattern.category].append(pattern)
    
    return [
        FilePatternsByCategory(
            category=cat,
            patterns=[FilePatternResponse.model_validate(p) for p in patterns_list],
            count=len(patterns_list)
        )
        for cat, patterns_list in sorted(categories.items())
    ]


@router.get("/file-patterns/{pattern_id}", response_model=FilePatternResponse)
async def get_file_pattern(pattern_id: int, db: Session = Depends(get_db)):
    """Get a specific file pattern by ID."""
    pattern = db.query(FilePatternConfig).filter(FilePatternConfig.id == pattern_id).first()
    if not pattern:
        raise HTTPException(status_code=404, detail="File pattern not found")
    return pattern


@router.post("/file-patterns", response_model=FilePatternResponse, status_code=status.HTTP_201_CREATED)
async def create_file_pattern(
    pattern: FilePatternCreate,
    db: Session = Depends(get_db)
):
    """Create a new file pattern."""
    # Check for duplicate
    existing = db.query(FilePatternConfig).filter(
        FilePatternConfig.category == pattern.category,
        FilePatternConfig.pattern == pattern.pattern
    ).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Pattern '{pattern.pattern}' already exists in category '{pattern.category}'"
        )
    
    db_pattern = FilePatternConfig(**pattern.model_dump())
    db.add(db_pattern)
    db.commit()
    db.refresh(db_pattern)
    return db_pattern


@router.post("/file-patterns/bulk", response_model=List[FilePatternResponse], status_code=status.HTTP_201_CREATED)
async def create_file_patterns_bulk(
    patterns: List[FilePatternCreate],
    skip_duplicates: bool = Query(True, description="Skip patterns that already exist"),
    db: Session = Depends(get_db)
):
    """Create multiple file patterns at once."""
    created = []
    for pattern in patterns:
        existing = db.query(FilePatternConfig).filter(
            FilePatternConfig.category == pattern.category,
            FilePatternConfig.pattern == pattern.pattern
        ).first()
        
        if existing:
            if skip_duplicates:
                continue
            raise HTTPException(
                status_code=400,
                detail=f"Pattern '{pattern.pattern}' already exists in category '{pattern.category}'"
            )
        
        db_pattern = FilePatternConfig(**pattern.model_dump())
        db.add(db_pattern)
        created.append(db_pattern)
    
    db.commit()
    for p in created:
        db.refresh(p)
    return created


@router.put("/file-patterns/{pattern_id}", response_model=FilePatternResponse)
async def update_file_pattern(
    pattern_id: int,
    pattern: FilePatternUpdate,
    db: Session = Depends(get_db)
):
    """Update an existing file pattern."""
    db_pattern = db.query(FilePatternConfig).filter(FilePatternConfig.id == pattern_id).first()
    if not db_pattern:
        raise HTTPException(status_code=404, detail="File pattern not found")
    
    update_data = pattern.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_pattern, field, value)
    
    db.commit()
    db.refresh(db_pattern)
    return db_pattern


@router.delete("/file-patterns/{pattern_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file_pattern(pattern_id: int, db: Session = Depends(get_db)):
    """Delete a file pattern."""
    db_pattern = db.query(FilePatternConfig).filter(FilePatternConfig.id == pattern_id).first()
    if not db_pattern:
        raise HTTPException(status_code=404, detail="File pattern not found")
    
    db.delete(db_pattern)
    db.commit()


# ============================================================
# Pipeline Templates API
# ============================================================

@router.get("/pipeline-templates", response_model=List[PipelineTemplateResponse])
async def list_pipeline_templates(
    data_type: Optional[str] = Query(None, description="Filter by data_type: structured or unstructured"),
    pipeline_type: Optional[str] = Query(None, description="Filter by pipeline_type"),
    enabled_only: bool = Query(True),
    db: Session = Depends(get_db)
):
    """List all pipeline templates."""
    query = db.query(PipelineTemplate)
    
    if data_type:
        query = query.filter(PipelineTemplate.data_type == data_type)
    if pipeline_type:
        query = query.filter(PipelineTemplate.pipeline_type == pipeline_type)
    if enabled_only:
        query = query.filter(PipelineTemplate.enabled == True)
    
    return query.order_by(PipelineTemplate.data_type, PipelineTemplate.name).all()


@router.get("/pipeline-templates/{template_id}", response_model=PipelineTemplateResponse)
async def get_pipeline_template(template_id: str, db: Session = Depends(get_db)):
    """Get a specific pipeline template by ID."""
    template = db.query(PipelineTemplate).filter(PipelineTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Pipeline template not found")
    return template


@router.post("/pipeline-templates", response_model=PipelineTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_pipeline_template(
    template: PipelineTemplateCreate,
    db: Session = Depends(get_db)
):
    """Create a new pipeline template."""
    existing = db.query(PipelineTemplate).filter(
        or_(PipelineTemplate.id == template.id, PipelineTemplate.name == template.name)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Template with this ID or name already exists")
    
    db_template = PipelineTemplate(**template.model_dump())
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    return db_template


@router.put("/pipeline-templates/{template_id}", response_model=PipelineTemplateResponse)
async def update_pipeline_template(
    template_id: str,
    template: PipelineTemplateUpdate,
    db: Session = Depends(get_db)
):
    """Update an existing pipeline template."""
    db_template = db.query(PipelineTemplate).filter(PipelineTemplate.id == template_id).first()
    if not db_template:
        raise HTTPException(status_code=404, detail="Pipeline template not found")
    
    if db_template.is_system:
        # Allow limited updates on system templates
        allowed_fields = {'enabled', 'file_patterns', 'metadata'}
        update_data = template.model_dump(exclude_unset=True)
        for field in list(update_data.keys()):
            if field not in allowed_fields:
                del update_data[field]
    else:
        update_data = template.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(db_template, field, value)
    
    db.commit()
    db.refresh(db_template)
    return db_template


@router.delete("/pipeline-templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pipeline_template(template_id: str, db: Session = Depends(get_db)):
    """Delete a pipeline template."""
    db_template = db.query(PipelineTemplate).filter(PipelineTemplate.id == template_id).first()
    if not db_template:
        raise HTTPException(status_code=404, detail="Pipeline template not found")
    
    if db_template.is_system:
        raise HTTPException(status_code=400, detail="Cannot delete system templates")
    
    db.delete(db_template)
    db.commit()


# ============================================================
# Search Configuration API
# ============================================================

@router.get("/search-configs", response_model=List[SearchConfigResponse])
async def list_search_configs(
    search_mode: Optional[str] = Query(None),
    enabled_only: bool = Query(True),
    db: Session = Depends(get_db)
):
    """List all search configurations."""
    query = db.query(SearchConfiguration)
    
    if search_mode:
        query = query.filter(SearchConfiguration.search_mode == search_mode)
    if enabled_only:
        query = query.filter(SearchConfiguration.enabled == True)
    
    return query.order_by(SearchConfiguration.search_mode, SearchConfiguration.name).all()


@router.get("/search-configs/{config_id}", response_model=SearchConfigResponse)
async def get_search_config(config_id: str, db: Session = Depends(get_db)):
    """Get a specific search configuration."""
    config = db.query(SearchConfiguration).filter(SearchConfiguration.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Search configuration not found")
    return config


@router.post("/search-configs", response_model=SearchConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_search_config(
    config: SearchConfigCreate,
    db: Session = Depends(get_db)
):
    """Create a new search configuration."""
    existing = db.query(SearchConfiguration).filter(SearchConfiguration.id == config.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Search config with this ID already exists")
    
    # If setting as default, unset other defaults for same search_mode
    if config.is_default:
        db.query(SearchConfiguration).filter(
            SearchConfiguration.search_mode == config.search_mode,
            SearchConfiguration.is_default == True
        ).update({SearchConfiguration.is_default: False})
    
    db_config = SearchConfiguration(**config.model_dump())
    db.add(db_config)
    db.commit()
    db.refresh(db_config)
    return db_config


@router.put("/search-configs/{config_id}", response_model=SearchConfigResponse)
async def update_search_config(
    config_id: str,
    config: SearchConfigUpdate,
    db: Session = Depends(get_db)
):
    """Update an existing search configuration."""
    db_config = db.query(SearchConfiguration).filter(SearchConfiguration.id == config_id).first()
    if not db_config:
        raise HTTPException(status_code=404, detail="Search configuration not found")
    
    update_data = config.model_dump(exclude_unset=True)
    
    # Handle default flag
    if update_data.get('is_default'):
        search_mode = update_data.get('search_mode', db_config.search_mode)
        db.query(SearchConfiguration).filter(
            SearchConfiguration.search_mode == search_mode,
            SearchConfiguration.is_default == True,
            SearchConfiguration.id != config_id
        ).update({SearchConfiguration.is_default: False})
    
    for field, value in update_data.items():
        setattr(db_config, field, value)
    
    db.commit()
    db.refresh(db_config)
    return db_config


@router.delete("/search-configs/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_search_config(config_id: str, db: Session = Depends(get_db)):
    """Delete a search configuration."""
    db_config = db.query(SearchConfiguration).filter(SearchConfiguration.id == config_id).first()
    if not db_config:
        raise HTTPException(status_code=404, detail="Search configuration not found")
    
    db.delete(db_config)
    db.commit()


# ============================================================
# Index Configuration API
# ============================================================

@router.get("/index-configs", response_model=List[IndexConfigResponse])
async def list_index_configs(
    knn_only: bool = Query(False, description="Only return KNN-enabled indexes"),
    enabled_only: bool = Query(True),
    db: Session = Depends(get_db)
):
    """List all index configurations."""
    query = db.query(IndexConfiguration)
    
    if knn_only:
        query = query.filter(IndexConfiguration.knn_enabled == True)
    if enabled_only:
        query = query.filter(IndexConfiguration.enabled == True)
    
    return query.order_by(IndexConfiguration.name).all()


@router.get("/index-configs/{config_id}", response_model=IndexConfigResponse)
async def get_index_config(config_id: str, db: Session = Depends(get_db)):
    """Get a specific index configuration."""
    config = db.query(IndexConfiguration).filter(IndexConfiguration.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Index configuration not found")
    return config


@router.post("/index-configs", response_model=IndexConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_index_config(
    config: IndexConfigCreate,
    db: Session = Depends(get_db)
):
    """Create a new index configuration."""
    existing = db.query(IndexConfiguration).filter(IndexConfiguration.id == config.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Index config with this ID already exists")
    
    db_config = IndexConfiguration(**config.model_dump())
    db.add(db_config)
    db.commit()
    db.refresh(db_config)
    return db_config


@router.put("/index-configs/{config_id}", response_model=IndexConfigResponse)
async def update_index_config(
    config_id: str,
    config: IndexConfigUpdate,
    db: Session = Depends(get_db)
):
    """Update an existing index configuration."""
    db_config = db.query(IndexConfiguration).filter(IndexConfiguration.id == config_id).first()
    if not db_config:
        raise HTTPException(status_code=404, detail="Index configuration not found")
    
    if db_config.is_system:
        allowed_fields = {'enabled', 'settings', 'mappings'}
        update_data = config.model_dump(exclude_unset=True)
        for field in list(update_data.keys()):
            if field not in allowed_fields:
                del update_data[field]
    else:
        update_data = config.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(db_config, field, value)
    
    db.commit()
    db.refresh(db_config)
    return db_config


@router.delete("/index-configs/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_index_config(config_id: str, db: Session = Depends(get_db)):
    """Delete an index configuration."""
    db_config = db.query(IndexConfiguration).filter(IndexConfiguration.id == config_id).first()
    if not db_config:
        raise HTTPException(status_code=404, detail="Index configuration not found")
    
    if db_config.is_system:
        raise HTTPException(status_code=400, detail="Cannot delete system index configurations")
    
    db.delete(db_config)
    db.commit()


# ============================================================
# Aggregated API
# ============================================================

@router.get("/all", response_model=AllConfigurationsResponse)
async def get_all_configurations(
    enabled_only: bool = Query(True),
    db: Session = Depends(get_db)
):
    """Get all configurations in a single response."""
    file_patterns_query = db.query(FilePatternConfig)
    templates_query = db.query(PipelineTemplate)
    search_query = db.query(SearchConfiguration)
    index_query = db.query(IndexConfiguration)
    
    if enabled_only:
        file_patterns_query = file_patterns_query.filter(FilePatternConfig.enabled == True)
        templates_query = templates_query.filter(PipelineTemplate.enabled == True)
        search_query = search_query.filter(SearchConfiguration.enabled == True)
        index_query = index_query.filter(IndexConfiguration.enabled == True)
    
    return AllConfigurationsResponse(
        file_patterns=[FilePatternResponse.model_validate(p) for p in file_patterns_query.all()],
        pipeline_templates=[PipelineTemplateResponse.model_validate(t) for t in templates_query.all()],
        search_configs=[SearchConfigResponse.model_validate(s) for s in search_query.all()],
        index_configs=[IndexConfigResponse.model_validate(i) for i in index_query.all()]
    )


@router.get("/categories", response_model=Dict[str, List[str]])
async def get_available_categories():
    """Get available values for various configuration categories."""
    return {
        "file_categories": ["document", "cad", "simulation", "data", "text", "image", "video", "archive", "binary", "other"],
        "data_types": ["structured", "unstructured"],
        "pipeline_types": ["search_index", "knowledge_graph", "database_migration", "plm_graph_sync"],
        "search_modes": ["semantic", "vector", "hybrid"],
        "source_types": ["filesystem", "database", "plm", "api", "s3", "azure_blob"],
        "target_types": ["opensearch", "neo4j", "database", "warehouse", "datalake", "s3", "azure_blob"]
    }
