# Deployment Guide

This guide walks you through deploying the Azure Service Bus Event Generator to Azure Container Apps.

## Prerequisites

1. **Azure CLI** installed and authenticated
2. **Docker** installed
3. **Azure subscription** with appropriate permissions
4. **Azure Container Registry** (optional, for custom images)

## Quick Deployment

### 1. Configure Environment

```bash
# Copy the example environment file
cp env.example .env

# Edit the configuration
nano .env
```

Update the following key values in `.env`:

```bash
# Azure Configuration
RESOURCE_GROUP=your-resource-group-name
LOCATION=eastus
CONTAINER_REGISTRY=your-registry.azurecr.io

# Service Bus Configuration
SERVICE_BUS_NAMESPACE=your-service-bus-namespace
```

### 2. Deploy Everything

```bash
# Make the deployment script executable
chmod +x deploy.sh

# Run the deployment
./deploy.sh
```

This script will:
- Create a resource group
- Build and push the Docker image
- Deploy all Azure resources using Bicep
- Configure Service Bus with proper permissions
- Set up the Container App with managed identity

### 3. Test the Deployment

```bash
# Install test dependencies
pip install httpx

# Run the test script
python test_api.py
```

## Manual Deployment Steps

If you prefer to deploy manually:

### 1. Create Resource Group

```bash
az group create \
  --name your-resource-group \
  --location eastus
```

### 2. Build and Push Docker Image

```bash
# Build the image
docker build -t your-registry.azurecr.io/service-bus-event-generator:latest .

# Login to Azure Container Registry
az acr login --name your-registry

# Push the image
docker push your-registry.azurecr.io/service-bus-event-generator:latest
```

### 3. Deploy Infrastructure

```bash
az deployment group create \
  --resource-group your-resource-group \
  --template-file deploy-aca.bicep \
  --parameters \
    containerAppName=service-bus-event-generator \
    containerAppEnvironmentName=service-bus-event-generator-env \
    containerImage=your-registry.azurecr.io/service-bus-event-generator:latest \
    location=eastus
```

### 4. Get Application URL

```bash
az containerapp show \
  --name service-bus-event-generator \
  --resource-group your-resource-group \
  --query properties.configuration.ingress.fqdn \
  --output tsv
```

## Configuration Options

### Service Bus Setup

The application supports two Service Bus configurations:

#### Option 1: Queue (Default)
```bash
SERVICE_BUS_QUEUE_NAME=events
SERVICE_BUS_TOPIC_NAME=  # Leave empty
```

#### Option 2: Topic
```bash
SERVICE_BUS_QUEUE_NAME=  # Leave empty
SERVICE_BUS_TOPIC_NAME=events-topic
```

### Authentication Methods

#### Managed Identity (Recommended for ACA)
```bash
USE_MANAGED_IDENTITY=true
SERVICE_BUS_NAMESPACE=your-namespace
```

#### Connection String (Development)
```bash
USE_MANAGED_IDENTITY=false
SERVICE_BUS_CONNECTION_STRING=Endpoint=sb://...
```

### Scaling Configuration

Adjust scaling in the Bicep template:

```bicep
scale: {
  minReplicas: 1
  maxReplicas: 10
  rules: [
    {
      name: 'http-scaling'
      http: {
        metadata: {
          concurrentRequests: '30'
        }
      }
    }
  ]
}
```

## Security Configuration

### API Keys

The application comes with default API keys for testing:

- **Development**: `dev-api-key-123`
- **Monitoring**: `monitoring-key-456`

**Important**: Change these keys in production!

### Rate Limiting

Default rate limits:
- `/events`: 100 requests/minute
- `/events/batch`: 10 requests/minute
- `/health`: 1000 requests/minute

### IP Filtering

Configure IP whitelist in `dpar-config.yaml`:

```yaml
ip-whitelist:
  rules:
    - path: "/events*"
      allowed_ips: ["203.0.113.0/24", "198.51.100.0/24"]
```

## Monitoring and Troubleshooting

### View Logs

```bash
# Container App logs
az containerapp logs show \
  --name service-bus-event-generator \
  --resource-group your-resource-group \
  --follow

# Service Bus metrics
az monitor metrics list \
  --resource your-service-bus-namespace \
  --metric "IncomingMessages"
```

### Health Checks

The application provides health check endpoints:

- **Liveness**: `/health` - Application is running
- **Readiness**: `/health` - Application is ready

### Common Issues

1. **Service Bus Connection Failed**
   - Check managed identity permissions
   - Verify namespace configuration
   - Ensure Service Bus resources exist

2. **Container App Won't Start**
   - Check health probe configuration
   - Verify environment variables
   - Review container logs

3. **Rate Limit Exceeded**
   - Check API key configuration
   - Verify rate limit settings
   - Monitor request patterns

## Production Considerations

### Security

1. **Change default API keys**
2. **Configure IP whitelist**
3. **Enable HTTPS only**
4. **Use Azure Key Vault for secrets**
5. **Enable Azure Monitor**

### Performance

1. **Configure appropriate scaling rules**
2. **Monitor Service Bus quotas**
3. **Set up alerts for failures**
4. **Use Premium Service Bus for high throughput**

### Cost Optimization

1. **Use Standard Service Bus tier for development**
2. **Configure appropriate scaling limits**
3. **Monitor resource usage**
4. **Use Azure Cost Management**

## Cleanup

To remove all resources:

```bash
az group delete \
  --name your-resource-group \
  --yes \
  --no-wait
```

## Support

For issues and questions:

1. Check the troubleshooting section
2. Review Azure Container Apps documentation
3. Open an issue in the repository
