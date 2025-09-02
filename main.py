"""
Azure Service Bus Event Generator API
A FastAPI application that receives REST API payloads and generates events in Azure Service Bus.
Designed to run on Azure Container Apps (ACA) with DPAR support.
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

import structlog
from azure.identity import DefaultAzureCredential
from azure.servicebus import ServiceBusClient, ServiceBusMessage
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from middleware.security import security_check

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Initialize FastAPI app
app = FastAPI(
    title="Azure Service Bus Event Generator",
    description="API to receive payloads and generate events in Azure Service Bus",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add security middleware
app.middleware("http")(security_check)

# Pydantic models
class EventPayload(BaseModel):
    """Model for incoming event payload"""
    event_type: str = Field(..., description="Type of event")
    data: Dict[str, Any] = Field(..., description="Event data payload")
    source: Optional[str] = Field(None, description="Source of the event")
    correlation_id: Optional[str] = Field(None, description="Correlation ID for tracking")
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow, description="Event timestamp")

class EventResponse(BaseModel):
    """Model for API response"""
    success: bool
    message: str
    event_id: Optional[str] = None
    correlation_id: Optional[str] = None

class HealthResponse(BaseModel):
    """Model for health check response"""
    status: str
    timestamp: datetime
    service_bus_connected: bool

# Global variables for Azure Service Bus
service_bus_client: Optional[ServiceBusClient] = None
service_bus_sender = None

# Configuration
SERVICE_BUS_CONNECTION_STRING = os.getenv("SERVICE_BUS_CONNECTION_STRING")
SERVICE_BUS_QUEUE_NAME = os.getenv("SERVICE_BUS_QUEUE_NAME", "events")
SERVICE_BUS_TOPIC_NAME = os.getenv("SERVICE_BUS_TOPIC_NAME")
USE_MANAGED_IDENTITY = os.getenv("USE_MANAGED_IDENTITY", "false").lower() == "true"
SERVICE_BUS_NAMESPACE = os.getenv("SERVICE_BUS_NAMESPACE")

async def initialize_service_bus():
    """Initialize Azure Service Bus connection"""
    global service_bus_client, service_bus_sender
    
    try:
        if USE_MANAGED_IDENTITY and SERVICE_BUS_NAMESPACE:
            # Use managed identity for authentication (recommended for ACA)
            credential = DefaultAzureCredential()
            service_bus_client = ServiceBusClient(
                fully_qualified_namespace=f"{SERVICE_BUS_NAMESPACE}.servicebus.windows.net",
                credential=credential
            )
            logger.info("Service Bus client initialized with managed identity", namespace=SERVICE_BUS_NAMESPACE)
        elif SERVICE_BUS_CONNECTION_STRING:
            # Use connection string
            service_bus_client = ServiceBusClient.from_connection_string(SERVICE_BUS_CONNECTION_STRING)
            logger.info("Service Bus client initialized with connection string")
        else:
            logger.error("No Service Bus configuration found")
            return False
        
        # Initialize sender based on configuration
        if SERVICE_BUS_TOPIC_NAME:
            service_bus_sender = service_bus_client.get_topic_sender(topic_name=SERVICE_BUS_TOPIC_NAME)
            logger.info("Service Bus topic sender initialized", topic=SERVICE_BUS_TOPIC_NAME)
        else:
            service_bus_sender = service_bus_client.get_queue_sender(queue_name=SERVICE_BUS_QUEUE_NAME)
            logger.info("Service Bus queue sender initialized", queue=SERVICE_BUS_QUEUE_NAME)
        
        return True
    except Exception as e:
        logger.error("Failed to initialize Service Bus", error=str(e))
        return False

async def send_event_to_service_bus(payload: EventPayload) -> str:
    """Send event to Azure Service Bus"""
    try:
        # Create event message
        event_data = {
            "event_type": payload.event_type,
            "data": payload.data,
            "source": payload.source,
            "correlation_id": payload.correlation_id,
            "timestamp": payload.timestamp.isoformat() if payload.timestamp else datetime.utcnow().isoformat(),
            "message_id": f"evt_{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}"
        }
        
        # Create Service Bus message
        message = ServiceBusMessage(
            body=json.dumps(event_data).encode('utf-8'),
            content_type="application/json"
        )
        
        # Add custom properties
        message.application_properties = {
            "event_type": payload.event_type,
            "source": payload.source or "api",
            "correlation_id": payload.correlation_id or event_data["message_id"],
            "timestamp": event_data["timestamp"]
        }
        
        # Send message
        async with service_bus_sender:
            await service_bus_sender.send_messages(message)
        
        logger.info(
            "Event sent to Service Bus successfully",
            event_type=payload.event_type,
            correlation_id=payload.correlation_id,
            message_id=event_data["message_id"]
        )
        
        return event_data["message_id"]
        
    except Exception as e:
        logger.error(
            "Failed to send event to Service Bus",
            error=str(e),
            event_type=payload.event_type,
            correlation_id=payload.correlation_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send event to Service Bus: {str(e)}"
        )

@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    logger.info("Starting Azure Service Bus Event Generator API")
    
    # Initialize Service Bus connection
    success = await initialize_service_bus()
    if not success:
        logger.warning("Service Bus initialization failed - API will start but events cannot be sent")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown"""
    global service_bus_client
    if service_bus_client:
        await service_bus_client.close()
    logger.info("Azure Service Bus Event Generator API shutdown complete")

@app.get("/", response_model=Dict[str, str])
async def root():
    """Root endpoint"""
    return {
        "message": "Azure Service Bus Event Generator API",
        "version": "1.0.0",
        "docs": "/docs"
    }

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    service_bus_connected = service_bus_client is not None and service_bus_sender is not None
    
    return HealthResponse(
        status="healthy" if service_bus_connected else "degraded",
        timestamp=datetime.utcnow(),
        service_bus_connected=service_bus_connected
    )

@app.post("/events", response_model=EventResponse)
async def create_event(payload: EventPayload, request: Request):
    """
    Create and send an event to Azure Service Bus
    
    This endpoint receives a payload and generates an event in Azure Service Bus.
    The event will be sent to either a queue or topic based on configuration.
    """
    try:
        # Log incoming request
        logger.info(
            "Received event creation request",
            event_type=payload.event_type,
            source=payload.source,
            correlation_id=payload.correlation_id,
            client_ip=request.client.host
        )
        
        # Validate Service Bus connection
        if not service_bus_client or not service_bus_sender:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service Bus connection not available"
            )
        
        # Send event to Service Bus
        event_id = await send_event_to_service_bus(payload)
        
        return EventResponse(
            success=True,
            message="Event created and sent to Service Bus successfully",
            event_id=event_id,
            correlation_id=payload.correlation_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Unexpected error creating event",
            error=str(e),
            event_type=payload.event_type,
            correlation_id=payload.correlation_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while creating event"
        )

@app.post("/events/batch", response_model=Dict[str, Any])
async def create_events_batch(payloads: list[EventPayload], request: Request):
    """
    Create and send multiple events to Azure Service Bus in batch
    
    This endpoint receives multiple payloads and generates events in Azure Service Bus.
    """
    try:
        # Log incoming request
        logger.info(
            "Received batch event creation request",
            count=len(payloads),
            client_ip=request.client.host
        )
        
        # Validate Service Bus connection
        if not service_bus_client or not service_bus_sender:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service Bus connection not available"
            )
        
        # Process events
        results = []
        successful_count = 0
        failed_count = 0
        
        for i, payload in enumerate(payloads):
            try:
                event_id = await send_event_to_service_bus(payload)
                results.append({
                    "index": i,
                    "success": True,
                    "event_id": event_id,
                    "correlation_id": payload.correlation_id
                })
                successful_count += 1
            except Exception as e:
                results.append({
                    "index": i,
                    "success": False,
                    "error": str(e),
                    "correlation_id": payload.correlation_id
                })
                failed_count += 1
        
        return {
            "success": failed_count == 0,
            "message": f"Processed {len(payloads)} events: {successful_count} successful, {failed_count} failed",
            "total_count": len(payloads),
            "successful_count": successful_count,
            "failed_count": failed_count,
            "results": results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error creating batch events", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while creating batch events"
        )

if __name__ == "__main__":
    import uvicorn
    
    # Get configuration from environment
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    log_level = os.getenv("LOG_LEVEL", "info")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        log_level=log_level,
        reload=os.getenv("ENVIRONMENT", "production") == "development"
    )
