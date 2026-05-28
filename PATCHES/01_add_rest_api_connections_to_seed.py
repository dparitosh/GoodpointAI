"""
PATCH 01: Add REST API Connection Types to Seed Script
========================================================

File: agentic-restored/python_backend/scripts/seed_admin_configs.py

Description:
- Adds REST API example connections to the seed script
- Includes common REST API service types: api, rest_api, webapi, openapi, odata
- Provides configuration templates for each type
- Enables users to add REST API connections from admin panel

Deployment:
1. Apply this patch to seed_admin_configs.py
2. Run: python -m scripts.seed_admin_configs
3. Restart backend to reload seed data
"""

# PATCH INSTRUCTIONS:
# Find the seed_connections() function around line 307
# Locate the last connection in the connections list (soda_external_runner)
# Add these REST API connection templates AFTER soda_external_runner

REST_API_CONNECTIONS = [
    {
        "id": "generic_rest_api",
        "connection_type": "rest_api",
        "name": "Generic REST API Template",
        "description": "Template for connecting to generic REST API services",
        "connection_string": "https://api.example.com/v1",
        "extra_options": {
            "auth_type": "none",
            "test_path": "/health",
            "timeout_s": 10.0,
            "headers_json": "{}"
        },
        "status": "inactive",
        "is_default": False
    },
    {
        "id": "salesforce_api",
        "connection_type": "rest_api",
        "name": "Salesforce REST API",
        "description": "Salesforce REST API with Bearer token authentication",
        "connection_string": "https://yourdomain.salesforce.com/services/data/v59.0",
        "extra_options": {
            "auth_type": "bearer",
            "test_path": "/sobjects",
            "timeout_s": 15.0,
            "headers_json": "{\"Sforce-Call-Options\": \"client=MyApp\"}"
        },
        "status": "inactive",
        "is_default": False
    },
    {
        "id": "custom_api_key",
        "connection_type": "api",
        "name": "Custom API with API Key",
        "description": "Template for APIs using API Key authentication",
        "connection_string": "https://api.yourservice.com",
        "extra_options": {
            "auth_type": "api_key",
            "api_key_header": "X-API-Key",
            "test_path": "/api/health",
            "timeout_s": 10.0,
            "headers_json": "{}"
        },
        "status": "inactive",
        "is_default": False
    },
    {
        "id": "openapi_service",
        "connection_type": "openapi",
        "name": "OpenAPI/Swagger Service",
        "description": "OpenAPI specification endpoint (auto-discovers /openapi.json)",
        "connection_string": "https://api.example.com",
        "extra_options": {
            "auth_type": "none",
            "test_path": "/openapi.json",
            "timeout_s": 10.0,
            "headers_json": "{}"
        },
        "status": "inactive",
        "is_default": False
    },
    {
        "id": "odata_service",
        "connection_type": "odata",
        "name": "OData Service",
        "description": "OData protocol endpoint (auto-discovers /$metadata)",
        "connection_string": "https://services.odata.org/V4/Northwind",
        "extra_options": {
            "auth_type": "none",
            "test_path": "/$metadata",
            "timeout_s": 10.0,
            "headers_json": "{}"
        },
        "status": "inactive",
        "is_default": False
    },
    {
        "id": "oauth2_service",
        "connection_type": "rest_api",
        "name": "OAuth2 Protected API",
        "description": "REST API with OAuth2 bearer token",
        "connection_string": "https://api.oauth.example.com/v2",
        "extra_options": {
            "auth_type": "oauth2",
            "test_path": "/api/user",
            "timeout_s": 15.0,
            "headers_json": "{}"
        },
        "status": "inactive",
        "is_default": False
    },
    {
        "id": "basic_auth_api",
        "connection_type": "webapi",
        "name": "Web API with Basic Auth",
        "description": "Web API using Basic (username/password) authentication",
        "connection_string": "https://api.basicauth.example.com",
        "username": "api_user",  # Example - should be empty in seed
        "extra_options": {
            "auth_type": "basic",
            "test_path": "/api/status",
            "timeout_s": 10.0,
            "headers_json": "{}"
        },
        "status": "inactive",
        "is_default": False
    },
]

# CODE PATCH:
# Replace this line in seed_admin_configs.py seed_connections() function:
#
#   db.commit()
#   logger.info(f"Created {created_count} connection configurations")
#
# WITH this implementation:

"""
    # Add REST API connection templates
    rest_api_count = 0
    for conn in REST_API_CONNECTIONS:
        existing = db.query(ConnectionConfig).filter(ConnectionConfig.id == conn["id"]).first()
        if not existing:
            db_conn = ConnectionConfig(**conn)
            db.add(db_conn)
            rest_api_count += 1
    
    db.commit()
    total_created = created_count + rest_api_count
    logger.info(f"Created {created_count} core connection configurations")
    logger.info(f"Created {rest_api_count} REST API connection templates")
    logger.info(f"Total: {total_created} connection configurations")
"""
