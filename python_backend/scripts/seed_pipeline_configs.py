"""
Seed Pipeline Configurations to PostgreSQL

This script reads the unstructured_workflows.json fixture and populates
the PostgreSQL database with file patterns, pipeline templates, search
configurations, and index configurations.
"""

import sys
from pathlib import Path
from typing import Dict, List, Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from core.db_session import SessionLocal, init_db
from models.pipeline_config_models import (
    FilePatternConfig,
    PipelineTemplate,
    SearchConfiguration,
    IndexConfiguration,
    Neo4jSchemaConfig,
)


# Default file patterns by category
DEFAULT_FILE_PATTERNS: Dict[str, List[Dict[str, Any]]] = {
    "document": [
        {"pattern": "*.pdf", "description": "PDF documents", "mime_type": "application/pdf", "parser_hint": "pdf_parser"},
        {"pattern": "*.doc", "description": "Microsoft Word (legacy)", "mime_type": "application/msword", "parser_hint": "word_parser"},
        {"pattern": "*.docx", "description": "Microsoft Word", "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "parser_hint": "word_parser"},
        {"pattern": "*.xls", "description": "Microsoft Excel (legacy)", "mime_type": "application/vnd.ms-excel", "parser_hint": "excel_parser"},
        {"pattern": "*.xlsx", "description": "Microsoft Excel", "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "parser_hint": "excel_parser"},
        {"pattern": "*.ppt", "description": "Microsoft PowerPoint (legacy)", "mime_type": "application/vnd.ms-powerpoint", "parser_hint": "ppt_parser"},
        {"pattern": "*.pptx", "description": "Microsoft PowerPoint", "mime_type": "application/vnd.openxmlformats-officedocument.presentationml.presentation", "parser_hint": "ppt_parser"},
        {"pattern": "*.rtf", "description": "Rich Text Format", "mime_type": "application/rtf", "parser_hint": "rtf_parser"},
        {"pattern": "*.odt", "description": "OpenDocument Text", "mime_type": "application/vnd.oasis.opendocument.text", "parser_hint": "odt_parser"},
    ],
    "cad": [
        {"pattern": "*.stp", "description": "STEP file", "mime_type": "application/step", "parser_hint": "step_parser"},
        {"pattern": "*.step", "description": "STEP file (alternative)", "mime_type": "application/step", "parser_hint": "step_parser"},
        {"pattern": "*.igs", "description": "IGES file", "mime_type": "model/iges", "parser_hint": "iges_parser"},
        {"pattern": "*.iges", "description": "IGES file (alternative)", "mime_type": "model/iges", "parser_hint": "iges_parser"},
        {"pattern": "*.dxf", "description": "AutoCAD DXF", "mime_type": "image/vnd.dxf", "parser_hint": "dxf_parser"},
        {"pattern": "*.dwg", "description": "AutoCAD DWG", "mime_type": "image/vnd.dwg", "parser_hint": "dwg_parser"},
        {"pattern": "*.stl", "description": "STL 3D model", "mime_type": "model/stl", "parser_hint": "stl_parser"},
        {"pattern": "*.obj", "description": "OBJ 3D model", "mime_type": "model/obj", "parser_hint": "obj_parser"},
        {"pattern": "*.3ds", "description": "3DS Max file", "mime_type": "model/3ds", "parser_hint": "3ds_parser"},
        {"pattern": "*.catpart", "description": "CATIA Part", "mime_type": "application/catia", "parser_hint": "catia_parser"},
        {"pattern": "*.catproduct", "description": "CATIA Product", "mime_type": "application/catia", "parser_hint": "catia_parser"},
        {"pattern": "*.cgr", "description": "CATIA CGR", "mime_type": "application/catia", "parser_hint": "catia_parser"},
        {"pattern": "*.sldprt", "description": "SolidWorks Part", "mime_type": "application/solidworks", "parser_hint": "solidworks_parser"},
        {"pattern": "*.sldasm", "description": "SolidWorks Assembly", "mime_type": "application/solidworks", "parser_hint": "solidworks_parser"},
        {"pattern": "*.prt", "description": "NX/Creo Part", "mime_type": "application/nx", "parser_hint": "nx_parser"},
        {"pattern": "*.asm", "description": "NX/Creo Assembly", "mime_type": "application/nx", "parser_hint": "nx_parser"},
        {"pattern": "*.jt", "description": "JT Open CAD", "mime_type": "model/jt", "parser_hint": "jt_parser"},
        {"pattern": "*.x_t", "description": "Parasolid Text", "mime_type": "model/parasolid", "parser_hint": "parasolid_parser"},
        {"pattern": "*.x_b", "description": "Parasolid Binary", "mime_type": "model/parasolid", "parser_hint": "parasolid_parser"},
        {"pattern": "*.sat", "description": "ACIS SAT", "mime_type": "model/acis", "parser_hint": "acis_parser"},
        {"pattern": "*.sab", "description": "ACIS Binary", "mime_type": "model/acis", "parser_hint": "acis_parser"},
        {"pattern": "*.ipt", "description": "Inventor Part", "mime_type": "application/inventor", "parser_hint": "inventor_parser"},
        {"pattern": "*.iam", "description": "Inventor Assembly", "mime_type": "application/inventor", "parser_hint": "inventor_parser"},
    ],
    "simulation": [
        {"pattern": "*.nas", "description": "NASTRAN Input", "mime_type": "application/nastran", "parser_hint": "nastran_parser"},
        {"pattern": "*.bdf", "description": "NASTRAN Bulk Data", "mime_type": "application/nastran", "parser_hint": "nastran_parser"},
        {"pattern": "*.dat", "description": "NASTRAN/ABAQUS Data", "mime_type": "application/simulation", "parser_hint": "simulation_parser"},
        {"pattern": "*.inp", "description": "ABAQUS Input", "mime_type": "application/abaqus", "parser_hint": "abaqus_parser"},
        {"pattern": "*.cdb", "description": "ANSYS CDB", "mime_type": "application/ansys", "parser_hint": "ansys_parser"},
        {"pattern": "*.rst", "description": "ANSYS Results", "mime_type": "application/ansys", "parser_hint": "ansys_parser"},
        {"pattern": "*.odb", "description": "ABAQUS Output Database", "mime_type": "application/abaqus", "parser_hint": "abaqus_parser"},
    ],
    "data": [
        {"pattern": "*.xml", "description": "XML file", "mime_type": "application/xml", "parser_hint": "xml_parser"},
        {"pattern": "*.json", "description": "JSON file", "mime_type": "application/json", "parser_hint": "json_parser"},
        {"pattern": "*.yaml", "description": "YAML file", "mime_type": "application/yaml", "parser_hint": "yaml_parser"},
        {"pattern": "*.yml", "description": "YAML file (alternative)", "mime_type": "application/yaml", "parser_hint": "yaml_parser"},
        {"pattern": "*.csv", "description": "CSV file", "mime_type": "text/csv", "parser_hint": "csv_parser"},
        {"pattern": "*.tsv", "description": "TSV file", "mime_type": "text/tab-separated-values", "parser_hint": "csv_parser"},
    ],
    "text": [
        {"pattern": "*.txt", "description": "Plain text", "mime_type": "text/plain", "parser_hint": "text_parser"},
        {"pattern": "*.log", "description": "Log file", "mime_type": "text/plain", "parser_hint": "log_parser"},
        {"pattern": "*.md", "description": "Markdown", "mime_type": "text/markdown", "parser_hint": "markdown_parser"},
        {"pattern": "*.rst", "description": "reStructuredText", "mime_type": "text/x-rst", "parser_hint": "rst_parser"},
    ],
    "image": [
        {"pattern": "*.png", "description": "PNG image", "mime_type": "image/png", "parser_hint": "image_parser"},
        {"pattern": "*.jpg", "description": "JPEG image", "mime_type": "image/jpeg", "parser_hint": "image_parser"},
        {"pattern": "*.jpeg", "description": "JPEG image (alternative)", "mime_type": "image/jpeg", "parser_hint": "image_parser"},
        {"pattern": "*.tiff", "description": "TIFF image", "mime_type": "image/tiff", "parser_hint": "image_parser"},
        {"pattern": "*.bmp", "description": "BMP image", "mime_type": "image/bmp", "parser_hint": "image_parser"},
        {"pattern": "*.gif", "description": "GIF image", "mime_type": "image/gif", "parser_hint": "image_parser"},
        {"pattern": "*.svg", "description": "SVG vector image", "mime_type": "image/svg+xml", "parser_hint": "svg_parser"},
    ],
    "video": [
        {"pattern": "*.mp4", "description": "MP4 video", "mime_type": "video/mp4", "parser_hint": "video_parser"},
        {"pattern": "*.avi", "description": "AVI video", "mime_type": "video/x-msvideo", "parser_hint": "video_parser"},
        {"pattern": "*.mov", "description": "QuickTime video", "mime_type": "video/quicktime", "parser_hint": "video_parser"},
        {"pattern": "*.mkv", "description": "MKV video", "mime_type": "video/x-matroska", "parser_hint": "video_parser"},
    ],
    "archive": [
        {"pattern": "*.zip", "description": "ZIP archive", "mime_type": "application/zip", "parser_hint": "archive_parser"},
        {"pattern": "*.tar", "description": "TAR archive", "mime_type": "application/x-tar", "parser_hint": "archive_parser"},
        {"pattern": "*.gz", "description": "GZIP archive", "mime_type": "application/gzip", "parser_hint": "archive_parser"},
        {"pattern": "*.7z", "description": "7-Zip archive", "mime_type": "application/x-7z-compressed", "parser_hint": "archive_parser"},
        {"pattern": "*.rar", "description": "RAR archive", "mime_type": "application/x-rar-compressed", "parser_hint": "archive_parser"},
    ],
    "binary": [
        {"pattern": "*.bin", "description": "Binary file", "mime_type": "application/octet-stream", "parser_hint": "binary_parser"},
        {"pattern": "*.raw", "description": "Raw binary data", "mime_type": "application/octet-stream", "parser_hint": "binary_parser"},
    ],
}


def seed_file_patterns(db: Session, force: bool = False) -> int:
    """Seed default file patterns into database."""
    if not force:
        existing_count = db.query(FilePatternConfig).count()
        if existing_count > 0:
            print(f"  File patterns already exist ({existing_count}). Skipping...")
            return 0
    
    count = 0
    for category, patterns in DEFAULT_FILE_PATTERNS.items():
        for pattern_info in patterns:
            # Check if already exists
            existing = db.query(FilePatternConfig).filter(
                FilePatternConfig.category == category,
                FilePatternConfig.pattern == pattern_info["pattern"]
            ).first()
            
            if existing and not force:
                continue
            
            if existing and force:
                # Update existing
                existing.description = pattern_info.get("description")
                existing.mime_type = pattern_info.get("mime_type")
                existing.parser_hint = pattern_info.get("parser_hint")
            else:
                # Create new
                db_pattern = FilePatternConfig(
                    category=category,
                    pattern=pattern_info["pattern"],
                    description=pattern_info.get("description"),
                    mime_type=pattern_info.get("mime_type"),
                    parser_hint=pattern_info.get("parser_hint"),
                    enabled=True,
                    created_by="system"
                )
                db.add(db_pattern)
            count += 1
    
    db.commit()
    print(f"  Seeded {count} file patterns")
    return count


def seed_pipeline_templates(db: Session, force: bool = False) -> int:
    """Seed default pipeline templates into database."""
    if not force:
        existing_count = db.query(PipelineTemplate).count()
        if existing_count > 0:
            print(f"  Pipeline templates already exist ({existing_count}). Skipping...")
            return 0
    
    templates = [
        {
            "id": "unstructured-opensearch",
            "name": "Unstructured Data Pipeline - OpenSearch",
            "description": "Generic unstructured data pipeline for ingesting files (CAD, documents, logs) into OpenSearch for full-text and semantic search",
            "data_type": "unstructured",
            "pipeline_type": "search_index",
            "source_type": "filesystem",
            "source_config_schema": {
                "base_path": {"type": "string", "required": True, "description": "Base directory path for file scanning"},
                "recursive": {"type": "boolean", "default": True},
                "file_patterns": {"type": "array", "description": "File patterns to include"},
            },
            "target_type": "opensearch",
            "target_config_schema": {
                "url": {"type": "string", "required": True, "description": "OpenSearch URL"},
                "index_prefix": {"type": "string", "default": "unstructured_"},
                "bulk_size": {"type": "integer", "default": 100},
            },
            "file_patterns": ["document", "cad", "simulation", "data", "text", "image"],
            "extra_metadata": {"search_modes": ["semantic", "vector", "hybrid"]},
            "icon": "search",
            "color": "#4CAF50",
            "is_system": True,
        },
        {
            "id": "unstructured-neo4j",
            "name": "Unstructured Data Pipeline - Neo4j Graph",
            "description": "Generic unstructured data pipeline for extracting entities and relationships into Neo4j knowledge graph",
            "data_type": "unstructured",
            "pipeline_type": "knowledge_graph",
            "source_type": "filesystem",
            "source_config_schema": {
                "base_path": {"type": "string", "required": True},
                "file_patterns": {"type": "array"},
                "entity_types": {"type": "array", "default": ["Product", "Part", "Assembly", "Document", "Person", "Organization"]},
            },
            "target_type": "neo4j",
            "target_config_schema": {
                "uri": {"type": "string", "required": True},
                "database": {"type": "string", "default": "neo4j"},
                "batch_size": {"type": "integer", "default": 500},
            },
            "file_patterns": ["document", "cad", "data"],
            "extra_metadata": {"graph_type": "entity_relationship"},
            "icon": "graph",
            "color": "#2196F3",
            "is_system": True,
        },
        {
            "id": "structured-database",
            "name": "Structured Data Pipeline - Database Migration",
            "description": "Generic structured data pipeline for migrating relational data between databases with schema mapping",
            "data_type": "structured",
            "pipeline_type": "database_migration",
            "source_type": "database",
            "source_config_schema": {
                "connection_string": {"type": "string", "required": True, "secret": True},
                "schema": {"type": "string", "default": "public"},
                "tables": {"type": "array"},
                "incremental": {"type": "boolean", "default": True},
            },
            "target_type": "database",
            "target_config_schema": {
                "connection_string": {"type": "string", "required": True, "secret": True},
                "schema": {"type": "string", "default": "public"},
                "batch_size": {"type": "integer", "default": 1000},
            },
            "file_patterns": [],
            "extra_metadata": {},
            "icon": "database",
            "color": "#FF9800",
            "is_system": True,
        },
        {
            "id": "structured-plm-graph",
            "name": "Structured Data Pipeline - PLM to Graph",
            "description": "Generic structured data pipeline for migrating PLM/ERP system data to Neo4j graph with BOM relationships",
            "data_type": "structured",
            "pipeline_type": "plm_graph_sync",
            "source_type": "plm",
            "source_config_schema": {
                "endpoint": {"type": "string", "required": True},
                "auth_type": {"type": "string", "enum": ["oauth2", "basic", "api_key"]},
                "entity_types": {"type": "array", "default": ["Part", "Assembly", "Document", "ChangeOrder"]},
                "include_bom": {"type": "boolean", "default": True},
            },
            "target_type": "neo4j",
            "target_config_schema": {
                "uri": {"type": "string", "required": True},
                "database": {"type": "string", "default": "neo4j"},
                "preserve_history": {"type": "boolean", "default": True},
            },
            "file_patterns": [],
            "extra_metadata": {},
            "icon": "share",
            "color": "#9C27B0",
            "is_system": True,
        },
    ]
    
    count = 0
    for template_data in templates:
        existing = db.query(PipelineTemplate).filter(PipelineTemplate.id == template_data["id"]).first()
        
        if existing and not force:
            continue
        
        if existing and force:
            for key, value in template_data.items():
                if key != "id":
                    setattr(existing, key, value)
        else:
            db_template = PipelineTemplate(
                **template_data,
                enabled=True,
                created_by="system"
            )
            db.add(db_template)
        count += 1
    
    db.commit()
    print(f"  Seeded {count} pipeline templates")
    return count


def seed_search_configs(db: Session, force: bool = False) -> int:
    """Seed default search configurations."""
    if not force:
        existing_count = db.query(SearchConfiguration).count()
        if existing_count > 0:
            print(f"  Search configs already exist ({existing_count}). Skipping...")
            return 0
    
    configs = [
        {
            "id": "semantic-default",
            "name": "Semantic Search",
            "description": "Full-text semantic search using BM25 and query expansion",
            "search_mode": "semantic",
            "enabled": True,
            "is_default": True,
            "config": {
                "analyzer": "standard",
                "boost_title": 2.0,
                "boost_content": 1.0,
                "fuzziness": "AUTO",
                "minimum_should_match": "75%",
            },
            "model_name": None,
            "vector_dimension": None,
            "similarity_threshold": 0.5,
        },
        {
            "id": "vector-default",
            "name": "Vector Search",
            "description": "Dense vector similarity search using sentence embeddings",
            "search_mode": "vector",
            "enabled": True,
            "is_default": True,
            "config": {
                "k": 10,
                "ef_search": 100,
                "space_type": "cosinesimil",
                "engine": "nmslib",
            },
            "model_name": "sentence-transformers/all-MiniLM-L6-v2",
            "vector_dimension": 384,
            "similarity_threshold": 0.7,
        },
        {
            "id": "hybrid-default",
            "name": "Hybrid Search",
            "description": "Combines semantic and vector search with configurable weights",
            "search_mode": "hybrid",
            "enabled": True,
            "is_default": True,
            "config": {
                "text_weight": 0.5,
                "vector_weight": 0.5,
                "normalize_scores": True,
                "reciprocal_rank_fusion": False,
            },
            "model_name": "sentence-transformers/all-MiniLM-L6-v2",
            "vector_dimension": 384,
            "similarity_threshold": 0.6,
        },
    ]
    
    count = 0
    for config_data in configs:
        existing = db.query(SearchConfiguration).filter(SearchConfiguration.id == config_data["id"]).first()
        
        if existing and not force:
            continue
        
        if existing and force:
            for key, value in config_data.items():
                if key != "id":
                    setattr(existing, key, value)
        else:
            db_config = SearchConfiguration(**config_data, created_by="system")
            db.add(db_config)
        count += 1
    
    db.commit()
    print(f"  Seeded {count} search configurations")
    return count


def seed_index_configs(db: Session, force: bool = False) -> int:
    """Seed default OpenSearch index configurations."""
    if not force:
        existing_count = db.query(IndexConfiguration).count()
        if existing_count > 0:
            print(f"  Index configs already exist ({existing_count}). Skipping...")
            return 0
    
    configs = [
        {
            "id": "unstructured_documents",
            "name": "Unstructured Documents Index",
            "description": "Index for storing unstructured document content with vector embeddings",
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
                "index.knn": True,
            },
            "mappings": {
                "properties": {
                    "doc_id": {"type": "keyword"},
                    "title": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                    "content": {"type": "text"},
                    "content_vector": {
                        "type": "knn_vector",
                        "dimension": 384,
                        "method": {"name": "hnsw", "space_type": "cosinesimil", "engine": "nmslib"}
                    },
                    "source_file": {"type": "keyword"},
                    "file_type": {"type": "keyword"},
                    "created_at": {"type": "date"},
                    "extra_metadata": {"type": "object", "enabled": True},
                    "entities": {"type": "keyword"},
                    "chunk_index": {"type": "integer"},
                }
            },
            "knn_enabled": True,
            "vector_field": "content_vector",
            "vector_dimension": 384,
            "is_system": True,
        },
        {
            "id": "unstructured_entities",
            "name": "Unstructured Entities Index",
            "description": "Index for storing extracted entities from unstructured data",
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
            },
            "mappings": {
                "properties": {
                    "entity_id": {"type": "keyword"},
                    "name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                    "type": {"type": "keyword"},
                    "description": {"type": "text"},
                    "source_documents": {"type": "keyword"},
                    "related_entities": {"type": "keyword"},
                    "properties": {"type": "object", "enabled": True},
                    "created_at": {"type": "date"},
                }
            },
            "knn_enabled": False,
            "is_system": True,
        },
    ]
    
    count = 0
    for config_data in configs:
        existing = db.query(IndexConfiguration).filter(IndexConfiguration.id == config_data["id"]).first()
        
        if existing and not force:
            continue
        
        if existing and force:
            for key, value in config_data.items():
                if key != "id":
                    setattr(existing, key, value)
        else:
            db_config = IndexConfiguration(**config_data, enabled=True)
            db.add(db_config)
        count += 1
    
    db.commit()
    print(f"  Seeded {count} index configurations")
    return count


def seed_neo4j_schema(db: Session, force: bool = False) -> int:
    """Seed Neo4j schema configurations."""
    if not force:
        existing_count = db.query(Neo4jSchemaConfig).count()
        if existing_count > 0:
            print(f"  Neo4j schema configs already exist ({existing_count}). Skipping...")
            return 0
    
    schema_items = [
        # Constraints
        {"schema_type": "constraint", "name": "doc_id_unique", "cypher_statement": "CREATE CONSTRAINT doc_id IF NOT EXISTS FOR (d:Document) REQUIRE d.doc_id IS UNIQUE", "description": "Unique constraint on Document.doc_id"},
        {"schema_type": "constraint", "name": "entity_id_unique", "cypher_statement": "CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE", "description": "Unique constraint on Entity.entity_id"},
        {"schema_type": "constraint", "name": "part_id_unique", "cypher_statement": "CREATE CONSTRAINT part_id IF NOT EXISTS FOR (p:Part) REQUIRE p.part_id IS UNIQUE", "description": "Unique constraint on Part.part_id"},
        {"schema_type": "constraint", "name": "assembly_id_unique", "cypher_statement": "CREATE CONSTRAINT assembly_id IF NOT EXISTS FOR (a:Assembly) REQUIRE a.assembly_id IS UNIQUE", "description": "Unique constraint on Assembly.assembly_id"},
        # Indexes
        {"schema_type": "index", "name": "doc_title_idx", "cypher_statement": "CREATE INDEX doc_title IF NOT EXISTS FOR (d:Document) ON (d.title)", "description": "Index on Document.title"},
        {"schema_type": "index", "name": "entity_name_idx", "cypher_statement": "CREATE INDEX entity_name IF NOT EXISTS FOR (e:Entity) ON (e.name)", "description": "Index on Entity.name"},
        {"schema_type": "index", "name": "part_name_idx", "cypher_statement": "CREATE INDEX part_name IF NOT EXISTS FOR (p:Part) ON (p.name)", "description": "Index on Part.name"},
    ]
    
    count = 0
    for item in schema_items:
        existing = db.query(Neo4jSchemaConfig).filter(Neo4jSchemaConfig.name == item["name"]).first()
        
        if existing and not force:
            continue
        
        if existing and force:
            existing.cypher_statement = item["cypher_statement"]
            existing.description = item.get("description")
        else:
            db_item = Neo4jSchemaConfig(
                **item,
                enabled=True,
                is_system=True
            )
            db.add(db_item)
        count += 1
    
    db.commit()
    print(f"  Seeded {count} Neo4j schema configurations")
    return count


def seed_all(force: bool = False) -> Dict[str, int]:
    """Seed all configurations to PostgreSQL."""
    print("\n🌱 Seeding Pipeline Configurations to PostgreSQL...")
    
    # Initialize database tables
    init_db()
    
    db = SessionLocal()
    try:
        results = {
            "file_patterns": seed_file_patterns(db, force),
            "pipeline_templates": seed_pipeline_templates(db, force),
            "search_configs": seed_search_configs(db, force),
            "index_configs": seed_index_configs(db, force),
            "neo4j_schema": seed_neo4j_schema(db, force),
        }
        
        total = sum(results.values())
        print(f"\n✅ Seeding complete! Total items: {total}")
        return results
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Seed pipeline configurations to PostgreSQL")
    parser.add_argument("--force", action="store_true", help="Force update existing records")
    args = parser.parse_args()
    
    seed_all(force=args.force)
