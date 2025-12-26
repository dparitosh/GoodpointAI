"""
Azure Cloud Services Integration Router
Handles Azure Blob Storage, Data Lake, Cosmos DB, Service Bus, Event Hub
"""
import logging
from typing import List, Dict, Optional, Any, cast
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, Response, UploadFile, File
from pydantic import BaseModel, Field
from uuid import UUID

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/azure", tags=["Azure Integration"])


ServiceBusAppPropertyValue = int | float | bytes | bool | str | UUID


# ============================================================================
# MODELS
# ============================================================================

class AzureBlobUploadRequest(BaseModel):
    container_name: str = Field(default="plm-data", description="Container name")
    blob_name: str = Field(..., description="Name of the blob to upload")
    content_type: Optional[str] = "application/octet-stream"
    metadata: Optional[Dict[str, str]] = {}


class AzureBlobListResponse(BaseModel):
    blobs: List[Dict[str, Any]]
    container: str
    count: int


class CosmosDocumentRequest(BaseModel):
    container_id: str = Field(..., description="Cosmos container ID")
    document: Dict[str, Any] = Field(..., description="Document to insert/update")
    partition_key: str = Field(..., description="Partition key value")


class ServiceBusMessageRequest(BaseModel):
    queue_name: str = Field(..., description="Service Bus queue name")
    message_body: Dict[str, Any] = Field(..., description="Message payload")
    properties: Optional[Dict[str | bytes, ServiceBusAppPropertyValue]] = None


class EventHubEventRequest(BaseModel):
    event_hub_name: str = Field(..., description="Event Hub name")
    events: List[Dict[str, Any]] = Field(..., description="Events to send")
    partition_key: Optional[str] = None


# ============================================================================
# AZURE BLOB STORAGE ENDPOINTS
# ============================================================================

@router.post("/blob/upload")
async def upload_blob(
    file: UploadFile = File(...),
    container_name: str = "plm-data",
    blob_name: Optional[str] = None
):
    """
    Upload a file to Azure Blob Storage
    
    Example:
    ```python
    from azure.storage.blob import BlobServiceClient
    
    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
    
    content = await file.read()
    blob_client.upload_blob(content, overwrite=True)
    ```
    """
    try:
        from core.external_config import azure_config
        from azure.storage.blob import BlobServiceClient
        
        if not azure_config.storage_connection_string:
            raise HTTPException(status_code=500, detail="Azure Storage not configured")
        
        blob_service_client = BlobServiceClient.from_connection_string(
            azure_config.storage_connection_string
        )
        
        # Use provided blob name or file filename
        resolved_blob_name = blob_name or file.filename
        if not resolved_blob_name:
            raise HTTPException(status_code=400, detail="blob_name is required")
        resolved_blob_name = cast(str, resolved_blob_name)
        
        # Get blob client
        blob_client = blob_service_client.get_blob_client(
            container=container_name,
            blob=resolved_blob_name
        )
        
        # Upload file
        content = await file.read()
        blob_client.upload_blob(content, overwrite=True, content_settings={
            'content_type': file.content_type
        })
        
        logger.info("Uploaded blob: %s to container: %s", resolved_blob_name, container_name)
        
        return {
            "status": "success",
            "message": "File uploaded successfully",
            "blob_name": resolved_blob_name,
            "container": container_name,
            "size": len(content),
            "url": blob_client.url
        }
        
    except Exception as e:
        logger.error("Error uploading to Azure Blob: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/blob/list/{container_name}")
async def list_blobs(
    container_name: str,
    response: Response,
    prefix: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """List all blobs in a container"""
    try:
        from core.external_config import azure_config
        from azure.storage.blob import BlobServiceClient
        
        blob_service_client = BlobServiceClient.from_connection_string(
            azure_config.storage_connection_string
        )
        
        container_client = blob_service_client.get_container_client(container_name)
        
        blobs = []
        for blob in container_client.list_blobs(name_starts_with=prefix):
            blobs.append({
                "name": blob.name,
                "size": blob.size,
                "last_modified": blob.last_modified.isoformat(),
                "content_type": blob.content_settings.content_type if blob.content_settings else None,
                "etag": blob.etag
            })
        
        total_count = len(blobs)
        response.headers["X-Total-Count"] = str(total_count)
        blobs_page = blobs[skip : skip + limit]

        return {
            "status": "success",
            "container": container_name,
            "prefix": prefix,
            "count": len(blobs_page),
            "blobs": blobs_page,
        }
        
    except Exception as e:
        logger.error("Error listing Azure blobs: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/blob/download/{container_name}/{blob_name:path}")
async def download_blob(container_name: str, blob_name: str):
    """Download a blob from Azure Storage"""
    try:
        from core.external_config import azure_config
        from azure.storage.blob import BlobServiceClient
        from fastapi.responses import StreamingResponse
        import io
        
        blob_service_client = BlobServiceClient.from_connection_string(
            azure_config.storage_connection_string
        )
        
        blob_client = blob_service_client.get_blob_client(
            container=container_name,
            blob=blob_name
        )
        
        download_stream = blob_client.download_blob()
        content = download_stream.readall()
        
        return StreamingResponse(
            io.BytesIO(content),
            media_type="application/octet-stream",
            headers={"Content-Disposition": f"attachment; filename={blob_name}"}
        )
        
    except Exception as e:
        logger.error("Error downloading Azure blob: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/blob/delete/{container_name}/{blob_name:path}")
async def delete_blob(container_name: str, blob_name: str):
    """Delete a blob from Azure Storage"""
    try:
        from core.external_config import azure_config
        from azure.storage.blob import BlobServiceClient
        
        blob_service_client = BlobServiceClient.from_connection_string(
            azure_config.storage_connection_string
        )
        
        blob_client = blob_service_client.get_blob_client(
            container=container_name,
            blob=blob_name
        )
        
        blob_client.delete_blob()
        
        return {
            "status": "success",
            "message": "Blob deleted successfully",
            "blob_name": blob_name,
            "container": container_name
        }
        
    except Exception as e:
        logger.error("Error deleting Azure blob: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


# ============================================================================
# AZURE DATA LAKE ENDPOINTS
# ============================================================================

@router.post("/datalake/upload")
async def upload_to_datalake(
    file: UploadFile = File(...),
    file_system: str = "raw-data",
    directory_path: str = "",
    file_name: Optional[str] = None
):
    """Upload file to Azure Data Lake Gen2"""
    try:
        from core.external_config import azure_config
        from azure.storage.filedatalake import DataLakeServiceClient
        
        service_client = DataLakeServiceClient(
            account_url=f"https://{azure_config.storage_account_name}.dfs.core.windows.net",
            credential=azure_config.storage_account_key
        )
        
        file_system_client = service_client.get_file_system_client(file_system)
        
        resolved_file_name = file_name or file.filename
        if not resolved_file_name:
            raise HTTPException(status_code=400, detail="file_name is required")
        resolved_file_name = cast(str, resolved_file_name)
        file_path = f"{directory_path}/{resolved_file_name}" if directory_path else resolved_file_name
        
        file_client = file_system_client.get_file_client(file_path)
        
        content = await file.read()
        file_client.upload_data(content, overwrite=True)
        
        return {
            "status": "success",
            "message": "File uploaded to Data Lake",
            "file_system": file_system,
            "path": file_path,
            "size": len(content)
        }
        
    except Exception as e:
        logger.error("Error uploading to Data Lake: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


# ============================================================================
# AZURE COSMOS DB ENDPOINTS
# ============================================================================

@router.post("/cosmos/document")
async def create_cosmos_document(request: CosmosDocumentRequest):
    """Create or update a document in Cosmos DB"""
    try:
        from core.external_config import azure_config
        from azure.cosmos import CosmosClient
        
        client = CosmosClient(azure_config.cosmos_endpoint, azure_config.cosmos_key)
        database = client.get_database_client(azure_config.cosmos_database)
        container = database.get_container_client(request.container_id)
        
        # Ensure document has an id
        if 'id' not in request.document:
            request.document['id'] = f"{datetime.utcnow().timestamp()}"
        
        result = container.upsert_item(request.document)
        
        return {
            "status": "success",
            "message": "Document created/updated",
            "document_id": result['id'],
            "container": request.container_id
        }
        
    except Exception as e:
        logger.error("Error creating Cosmos document: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/cosmos/documents/{container_id}")
async def query_cosmos_documents(
    container_id: str,
    response: Response,
    query: Optional[str] = None,
    partition_key: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """Query documents from Cosmos DB"""
    try:
        from core.external_config import azure_config
        from azure.cosmos import CosmosClient
        
        client = CosmosClient(azure_config.cosmos_endpoint, azure_config.cosmos_key)
        database = client.get_database_client(azure_config.cosmos_database)
        container = database.get_container_client(container_id)
        
        # Default query to select all
        query = query or "SELECT * FROM c"
        
        items = list(container.query_items(
            query=query,
            enable_cross_partition_query=(partition_key is None)
        ))

        total_count = len(items)
        response.headers["X-Total-Count"] = str(total_count)
        documents_page = items[skip : skip + limit]
        
        return {
            "status": "success",
            "container": container_id,
            "count": len(documents_page),
            "documents": documents_page,
        }
        
    except Exception as e:
        logger.error("Error querying Cosmos DB: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


# ============================================================================
# AZURE SERVICE BUS ENDPOINTS
# ============================================================================

@router.post("/servicebus/send")
async def send_service_bus_message(request: ServiceBusMessageRequest):
    """Send message to Azure Service Bus queue"""
    try:
        from core.external_config import azure_config
        from azure.servicebus import ServiceBusClient, ServiceBusMessage
        import json
        
        client = ServiceBusClient.from_connection_string(
            azure_config.servicebus_connection_string
        )
        
        with client:
            sender = client.get_queue_sender(queue_name=request.queue_name)
            with sender:
                application_properties = cast(Optional[Dict[str | bytes, Any]], request.properties)
                message = ServiceBusMessage(
                    json.dumps(request.message_body),
                    application_properties=application_properties
                )
                sender.send_messages(message)
        
        return {
            "status": "success",
            "message": "Message sent to Service Bus",
            "queue": request.queue_name
        }
        
    except Exception as e:
        logger.error("Error sending to Service Bus: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


# ============================================================================
# AZURE EVENT HUB ENDPOINTS
# ============================================================================

@router.post("/eventhub/send")
async def send_event_hub_events(request: EventHubEventRequest):
    """Send events to Azure Event Hub"""
    try:
        from core.external_config import azure_config
        from azure.eventhub import EventHubProducerClient, EventData
        import json
        
        producer = EventHubProducerClient.from_connection_string(
            conn_str=azure_config.eventhub_connection_string,
            eventhub_name=request.event_hub_name
        )
        
        with producer:
            event_data_batch = producer.create_batch(partition_key=request.partition_key)
            
            for event in request.events:
                event_data_batch.add(EventData(json.dumps(event)))
            
            producer.send_batch(event_data_batch)
        
        return {
            "status": "success",
            "message": "Events sent to Event Hub",
            "event_hub": request.event_hub_name,
            "event_count": len(request.events)
        }
        
    except Exception as e:
        logger.error("Error sending to Event Hub: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


# ============================================================================
# HEALTH CHECK
# ============================================================================

@router.get("/health")
async def azure_health_check():
    """Check Azure service connectivity"""
    from core.external_config import azure_config
    
    health = {
        "status": "healthy",
        "services": {
            "blob_storage": azure_config.storage_connection_string != "",
            "cosmos_db": azure_config.cosmos_endpoint != "",
            "service_bus": azure_config.servicebus_connection_string != "",
            "event_hub": azure_config.eventhub_connection_string != ""
        },
        "timestamp": datetime.utcnow().isoformat()
    }
    
    return health
