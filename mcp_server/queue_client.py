import json
import logging
import asyncio
from typing import Optional, Callable, Any, Dict

try:
    from azure.servicebus.aio import ServiceBusClient, ServiceBusSender, ServiceBusReceiver
    from azure.servicebus import ServiceBusMessage
    _AZURE_SB_AVAILABLE = True
except ImportError:
    ServiceBusClient = ServiceBusSender = ServiceBusReceiver = ServiceBusMessage = Any  # type: ignore
    _AZURE_SB_AVAILABLE = False

from .config import Settings

logger = logging.getLogger(__name__)

class MessageQueueClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client: Optional[ServiceBusClient] = None
        self.sender: Optional[ServiceBusSender] = None
        self.receiver: Optional[ServiceBusReceiver] = None
        self.is_connected = False

    async def connect(self):
        """Initialize connection to Azure Service Bus"""
        if not _AZURE_SB_AVAILABLE:
            logger.warning("azure-servicebus package not installed. Queue disabled.")
            self.is_connected = False
            return

        if not self.settings.AZURE_SERVICE_BUS_CONNECTION_STRING:
            logger.warning("No Azure Service Bus connection string provided. Queue disabled.")
            return

        try:
            self.client = ServiceBusClient.from_connection_string(
                self.settings.AZURE_SERVICE_BUS_CONNECTION_STRING
            )
            
            # Initialize sender/receiver if queue name is configured
            if self.settings.MCP_QUEUE_NAME:
                self.sender = self.client.get_queue_sender(self.settings.MCP_QUEUE_NAME)
                # For receiving, we might want a separate process or worker, but we can init here
                self.receiver = self.client.get_queue_receiver(self.settings.MCP_QUEUE_NAME)
            
            self.is_connected = True
            logger.info("Connected to Azure Service Bus")
        except Exception as e:
            logger.error(f"Failed to connect to Azure Service Bus: {e}")
            self.is_connected = False

    async def close(self):
        """Close connections"""
        if self.sender:
            await self.sender.close()
        if self.receiver:
            await self.receiver.close()
        if self.client:
            await self.client.close()
        self.is_connected = False

    async def publish_message(self, message: Dict[str, Any], correlation_id: Optional[str] = None):
        """Publish a message to the queue"""
        if not self.is_connected or not self.sender:
            logger.warning("Queue not connected. Message dropped: %s", message.keys())
            return

        try:
            body = json.dumps(message)
            msg = ServiceBusMessage(body, correlation_id=correlation_id)
            await self.sender.send_messages(msg)
            logger.debug(f"Message published: {correlation_id}")
        except Exception as e:
            logger.error(f"Failed to publish message: {e}")
            raise

    async def start_listening(self, callback: Callable[[Dict[str, Any]], Any]):
        """Start listening for messages (blocking loop)"""
        if not self.is_connected or not self.receiver:
            logger.warning("Queue not configured for listening.")
            return

        logger.info("Starting to listen on queue: %s", self.settings.MCP_QUEUE_NAME)
        async with self.receiver:
            async for msg in self.receiver:
                try:
                    body = str(msg)
                    data = json.loads(body)
                    logger.debug("Received message: %s", msg.correlation_id)
                    
                    # Process message
                    await callback(data)
                    
                    # Complete message
                    await self.receiver.complete_message(msg)
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    # Dead-letter or abandon depending on policy
                    await self.receiver.abandon_message(msg)

