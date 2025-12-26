"""
AWS Cloud Services Integration Router
Handles S3, DynamoDB, SQS, Lambda, API Gateway
"""
import logging
from typing import Dict, Optional, Any, cast
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, Response, UploadFile, File
from pydantic import BaseModel, Field
import importlib
import json

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/aws", tags=["AWS Integration"])


def _import_boto3() -> Any:
    return cast(Any, importlib.import_module("boto3"))


# ============================================================================
# MODELS
# ============================================================================

class S3UploadRequest(BaseModel):
    bucket_name: str = Field(..., description="S3 bucket name")
    key: str = Field(..., description="Object key (path)")
    metadata: Optional[Dict[str, str]] = {}


class DynamoDBPutRequest(BaseModel):
    table_name: str = Field(..., description="DynamoDB table name")
    item: Dict[str, Any] = Field(..., description="Item to put")


class DynamoDBQueryRequest(BaseModel):
    table_name: str = Field(..., description="DynamoDB table name")
    key_condition_expression: str = Field(..., description="Key condition")
    expression_attribute_values: Dict[str, Any]


class SQSMessageRequest(BaseModel):
    queue_url: str = Field(..., description="SQS queue URL")
    message_body: Dict[str, Any] = Field(..., description="Message payload")
    message_attributes: Optional[Dict[str, Any]] = {}


class LambdaInvokeRequest(BaseModel):
    function_name: str = Field(..., description="Lambda function name")
    payload: Dict[str, Any] = Field(default={}, description="Function payload")
    invocation_type: str = Field(default="RequestResponse", description="RequestResponse, Event, DryRun")


# ============================================================================
# AWS S3 ENDPOINTS
# ============================================================================

@router.post("/s3/upload")
async def upload_to_s3(
    file: UploadFile = File(...),
    bucket_name: Optional[str] = None,
    key: Optional[str] = None
):
    """Upload file to S3"""
    try:
        from core.external_config import aws_config
        boto3 = _import_boto3()
        
        s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_config.access_key_id,
            aws_secret_access_key=aws_config.secret_access_key,
            region_name=aws_config.region
        )
        
        bucket = bucket_name or aws_config.s3_bucket_name
        object_key = key or f"{aws_config.s3_prefix}{file.filename}"
        
        content = await file.read()
        
        s3_client.put_object(
            Bucket=bucket,
            Key=object_key,
            Body=content,
            ContentType=file.content_type
        )
        
        logger.info("Uploaded to S3: %s/%s", bucket, object_key)
        
        return {
            "status": "success",
            "message": "File uploaded to S3",
            "bucket": bucket,
            "key": object_key,
            "size": len(content),
            "url": f"s3://{bucket}/{object_key}"
        }
        
    except Exception as e:
        logger.error("Error uploading to S3: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/s3/list/{bucket_name}")
async def list_s3_objects(
    bucket_name: str,
    http_response: Response,
    prefix: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """List objects in S3 bucket"""
    try:
        from core.external_config import aws_config
        boto3 = _import_boto3()
        
        s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_config.access_key_id,
            aws_secret_access_key=aws_config.secret_access_key,
            region_name=aws_config.region
        )
        
        params = {'Bucket': bucket_name}
        if prefix:
            params['Prefix'] = prefix
        
        s3_response = cast(Dict[str, Any], s3_client.list_objects_v2(**params))
        
        objects = []
        if "Contents" in s3_response:
            for obj in s3_response["Contents"]:
                objects.append({
                    "key": obj["Key"],
                    "size": obj["Size"],
                    "last_modified": obj["LastModified"].isoformat(),
                    "etag": obj["ETag"],
                })
        
        total_count = len(objects)
        http_response.headers["X-Total-Count"] = str(total_count)
        objects_page = objects[skip : skip + limit]

        return {
            "status": "success",
            "bucket": bucket_name,
            "prefix": prefix,
            "count": len(objects_page),
            "objects": objects_page,
        }
        
    except Exception as e:
        logger.error("Error listing S3 objects: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/s3/download/{bucket_name}/{key:path}")
async def download_from_s3(bucket_name: str, key: str):
    """Download file from S3"""
    try:
        from core.external_config import aws_config
        boto3 = _import_boto3()
        from fastapi.responses import StreamingResponse
        import io
        
        s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_config.access_key_id,
            aws_secret_access_key=aws_config.secret_access_key,
            region_name=aws_config.region
        )
        
        response = s3_client.get_object(Bucket=bucket_name, Key=key)
        content = response['Body'].read()
        
        filename = key.split('/')[-1]
        
        return StreamingResponse(
            io.BytesIO(content),
            media_type=response.get('ContentType', 'application/octet-stream'),
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        logger.error("Error downloading from S3: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/s3/delete/{bucket_name}/{key:path}")
async def delete_from_s3(bucket_name: str, key: str):
    """Delete object from S3"""
    try:
        from core.external_config import aws_config
        boto3 = _import_boto3()
        
        s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_config.access_key_id,
            aws_secret_access_key=aws_config.secret_access_key,
            region_name=aws_config.region
        )
        
        s3_client.delete_object(Bucket=bucket_name, Key=key)
        
        return {
            "status": "success",
            "message": "Object deleted from S3",
            "bucket": bucket_name,
            "key": key
        }
        
    except Exception as e:
        logger.error("Error deleting from S3: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


# ============================================================================
# AWS DYNAMODB ENDPOINTS
# ============================================================================

@router.post("/dynamodb/put")
async def put_dynamodb_item(request: DynamoDBPutRequest):
    """Put item into DynamoDB table"""
    try:
        from core.external_config import aws_config
        boto3 = _import_boto3()
        
        dynamodb = boto3.resource(
            'dynamodb',
            aws_access_key_id=aws_config.access_key_id,
            aws_secret_access_key=aws_config.secret_access_key,
            region_name=aws_config.region
        )
        
        table = dynamodb.Table(request.table_name)
        
        response = table.put_item(Item=request.item)
        
        return {
            "status": "success",
            "message": "Item inserted into DynamoDB",
            "table": request.table_name,
            "response": response
        }
        
    except Exception as e:
        logger.error("Error putting DynamoDB item: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/dynamodb/query")
async def query_dynamodb(request: DynamoDBQueryRequest):
    """Query DynamoDB table"""
    try:
        from core.external_config import aws_config
        boto3 = _import_boto3()
        
        dynamodb = boto3.resource(
            'dynamodb',
            aws_access_key_id=aws_config.access_key_id,
            aws_secret_access_key=aws_config.secret_access_key,
            region_name=aws_config.region
        )
        
        table = dynamodb.Table(request.table_name)
        
        response = table.query(
            KeyConditionExpression=request.key_condition_expression,
            ExpressionAttributeValues=request.expression_attribute_values
        )
        
        return {
            "status": "success",
            "table": request.table_name,
            "count": response['Count'],
            "items": response['Items']
        }
        
    except Exception as e:
        logger.error("Error querying DynamoDB: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/dynamodb/scan/{table_name}")
async def scan_dynamodb_table(table_name: str, limit: int = 100):
    """Scan DynamoDB table"""
    try:
        from core.external_config import aws_config
        boto3 = _import_boto3()
        
        dynamodb = boto3.resource(
            'dynamodb',
            aws_access_key_id=aws_config.access_key_id,
            aws_secret_access_key=aws_config.secret_access_key,
            region_name=aws_config.region
        )
        
        table = dynamodb.Table(table_name)
        
        response = table.scan(Limit=limit)
        
        return {
            "status": "success",
            "table": table_name,
            "count": response['Count'],
            "items": response['Items']
        }
        
    except Exception as e:
        logger.error("Error scanning DynamoDB: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


# ============================================================================
# AWS SQS ENDPOINTS
# ============================================================================

@router.post("/sqs/send")
async def send_sqs_message(request: SQSMessageRequest):
    """Send message to SQS queue"""
    try:
        from core.external_config import aws_config
        boto3 = _import_boto3()
        
        sqs = boto3.client(
            'sqs',
            aws_access_key_id=aws_config.access_key_id,
            aws_secret_access_key=aws_config.secret_access_key,
            region_name=aws_config.region
        )
        
        response = sqs.send_message(
            QueueUrl=request.queue_url,
            MessageBody=json.dumps(request.message_body),
            MessageAttributes=request.message_attributes
        )
        
        return {
            "status": "success",
            "message": "Message sent to SQS",
            "message_id": response['MessageId'],
            "queue_url": request.queue_url
        }
        
    except Exception as e:
        logger.error("Error sending SQS message: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/sqs/receive/{queue_url:path}")
async def receive_sqs_messages(queue_url: str, max_messages: int = 10):
    """Receive messages from SQS queue"""
    try:
        from core.external_config import aws_config
        boto3 = _import_boto3()
        
        sqs = boto3.client(
            'sqs',
            aws_access_key_id=aws_config.access_key_id,
            aws_secret_access_key=aws_config.secret_access_key,
            region_name=aws_config.region
        )
        
        response = sqs.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=max_messages,
            WaitTimeSeconds=5
        )
        
        messages = response.get('Messages', [])
        
        return {
            "status": "success",
            "queue_url": queue_url,
            "count": len(messages),
            "messages": messages
        }
        
    except Exception as e:
        logger.error("Error receiving SQS messages: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


# ============================================================================
# AWS LAMBDA ENDPOINTS
# ============================================================================

@router.post("/lambda/invoke")
async def invoke_lambda(request: LambdaInvokeRequest):
    """Invoke AWS Lambda function"""
    try:
        from core.external_config import aws_config
        boto3 = _import_boto3()
        
        lambda_client = boto3.client(
            'lambda',
            aws_access_key_id=aws_config.access_key_id,
            aws_secret_access_key=aws_config.secret_access_key,
            region_name=aws_config.region
        )
        
        response = lambda_client.invoke(
            FunctionName=request.function_name,
            InvocationType=request.invocation_type,
            Payload=json.dumps(request.payload)
        )
        
        result = {}
        if 'Payload' in response:
            result = json.loads(response['Payload'].read())
        
        return {
            "status": "success",
            "message": "Lambda invoked",
            "function_name": request.function_name,
            "status_code": response['StatusCode'],
            "result": result
        }
        
    except Exception as e:
        logger.error("Error invoking Lambda: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


# ============================================================================
# HEALTH CHECK
# ============================================================================

@router.get("/health")
async def aws_health_check():
    """Check AWS service connectivity"""
    from core.external_config import aws_config
    
    health = {
        "status": "healthy",
        "services": {
            "s3": aws_config.s3_bucket_name != "",
            "dynamodb": aws_config.dynamodb_table_name != "",
            "sqs": aws_config.sqs_queue_url != "",
            "lambda": aws_config.lambda_function_arn != ""
        },
        "region": aws_config.region,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    return health
