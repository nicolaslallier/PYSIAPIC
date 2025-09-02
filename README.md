# Azure Service Bus Event Generator

A FastAPI application that receives REST API payloads and generates events in Azure Service Bus. Designed to run on Azure Container Apps (ACA) with DPAR (Dynamic Policy and Access Rules) support.

## Features

- **REST API**: FastAPI-based endpoints for receiving event payloads
- **Azure Service Bus Integration**: Sends events to Azure Service Bus queues or topics
- **Container Apps Ready**: Optimized for Azure Container Apps deployment
- **DPAR Security**: Built-in security policies and access rules
- **Managed Identity**: Supports Azure Managed Identity for secure authentication
- **Rate Limiting**: Configurable rate limiting and IP blocking
- **Health Checks**: Built-in health monitoring endpoints
- **Structured Logging**: JSON-based logging with correlation IDs
- **Batch Processing**: Support for batch event creation

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Client App    │───▶│   FastAPI App    │───▶│  Azure Service  │
│                 │    │  (Container App) │    │     Bus         │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌──────────────────┐
                       │   DPAR Security  │
                       │   - Rate Limiting│
                       │   - API Keys     │
                       │   - IP Filtering │
                       └──────────────────┘
```

## Quick Start

### Prerequisites

- Azure CLI installed and authenticated
- Docker installed
- Azure subscription with appropriate permissions
- Azure Container Registry (optional, for custom images)

### 1. Clone and Setup

```bash
git clone <your-repo>
cd PYSIAPIC
cp .env.example .env
# Edit .env with your configuration
```

### 2. Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally
python main.py
```

The API will be available at `http://localhost:8000`

### 3. Deploy to Azure Container Apps

```bash
# Make deployment script executable
chmod +x deploy.sh

# Deploy (this will create all Azure resources)
./deploy.sh
```

## API Endpoints

### Health Check
```http
GET /health
```

### Create Event
```http
POST /events
Content-Type: application/json
X-API-Key: your-api-key

{
  "event_type": "user_action",
  "data": {
    "user_id": "123",
    "action": "login"
  },
  "source": "web_app",
  "correlation_id": "req-123"
}
```

### Create Batch Events
```http
POST /events/batch
Content-Type: application/json
X-API-Key: your-api-key

[
  {
    "event_type": "user_action",
    "data": {"user_id": "123", "action": "login"}
  },
  {
    "event_type": "system_event",
    "data": {"event": "startup", "timestamp": "2024-01-01T00:00:00Z"}
  }
]
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `HOST` | Application host | `0.0.0.0` |
| `PORT` | Application port | `8000` |
| `LOG_LEVEL` | Logging level | `info` |
| `USE_MANAGED_IDENTITY` | Use Azure Managed Identity | `true` |
| `SERVICE_BUS_NAMESPACE` | Service Bus namespace | Required |
| `SERVICE_BUS_QUEUE_NAME` | Service Bus queue name | `events` |
| `SERVICE_BUS_TOPIC_NAME` | Service Bus topic name | Optional |

### Service Bus Configuration

The application supports two authentication methods:

1. **Managed Identity (Recommended for ACA)**:
   ```bash
   USE_MANAGED_IDENTITY=true
   SERVICE_BUS_NAMESPACE=your-namespace
   ```

2. **Connection String (Development)**:
   ```bash
   SERVICE_BUS_CONNECTION_STRING=Endpoint=sb://...
   ```

## Security (DPAR)

The application includes built-in security features:

### Rate Limiting
- `/events`: 100 requests/minute
- `/events/batch`: 10 requests/minute
- `/health`: 1000 requests/minute

### API Key Authentication
- Required for event creation endpoints
- Optional for health checks
- Configurable permissions per key

### IP Filtering
- Automatic IP blocking on rate limit violations
- Configurable whitelist/blacklist

### Security Headers
- X-Content-Type-Options: nosniff
- X-Frame-Options: DENY
- X-XSS-Protection: 1; mode=block
- Strict-Transport-Security

## Deployment

### Azure Container Apps

The application is designed to run on Azure Container Apps with:

- **Auto-scaling**: 1-10 replicas based on HTTP traffic
- **Health Checks**: Liveness and readiness probes
- **Managed Identity**: Secure Service Bus access
- **Logging**: Integration with Azure Monitor

### Bicep Template

Deploy using the provided Bicep template:

```bash
az deployment group create \
  --resource-group your-rg \
  --template-file deploy-aca.bicep \
  --parameters containerAppName=your-app
```

### Docker

Build and run locally:

```bash
docker build -t service-bus-event-generator .
docker run -p 8000:8000 \
  -e SERVICE_BUS_CONNECTION_STRING="your-connection-string" \
  service-bus-event-generator
```

## Monitoring

### Health Checks

The application provides health check endpoints:

- **Liveness**: `/health` - Application is running
- **Readiness**: `/health` - Application is ready to serve requests

### Logging

Structured JSON logging with:

- Request correlation IDs
- Event tracking
- Error details
- Performance metrics

### Metrics

Key metrics to monitor:

- Request rate and latency
- Service Bus message send success/failure
- Rate limit violations
- Authentication failures

## Development

### Project Structure

```
├── main.py                 # FastAPI application
├── middleware/
│   └── security.py        # DPAR security implementation
├── requirements.txt       # Python dependencies
├── Dockerfile            # Container configuration
├── deploy-aca.bicep      # Azure deployment template
├── dpar-config.yaml      # Security policies
├── deploy.sh            # Deployment script
└── README.md            # This file
```

### Adding New Features

1. **New Endpoints**: Add to `main.py`
2. **Security Policies**: Update `dpar-config.yaml`
3. **Middleware**: Extend `middleware/security.py`
4. **Configuration**: Add to `.env.example`

### Testing

```bash
# Run tests (when implemented)
pytest

# Test API locally
curl -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-api-key-123" \
  -d '{"event_type": "test", "data": {"message": "hello"}}'
```

## Troubleshooting

### Common Issues

1. **Service Bus Connection Failed**
   - Check managed identity permissions
   - Verify namespace configuration
   - Ensure Service Bus resources exist

2. **Rate Limit Exceeded**
   - Check API key configuration
   - Verify rate limit settings
   - Monitor request patterns

3. **Container App Won't Start**
   - Check health probe configuration
   - Verify environment variables
   - Review container logs

### Logs

View application logs:

```bash
# Azure Container Apps
az containerapp logs show --name your-app --resource-group your-rg

# Local Docker
docker logs your-container-id
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions:

1. Check the troubleshooting section
2. Review Azure Container Apps documentation
3. Open an issue in the repository
