#!/bin/bash

# Azure Container Apps Deployment Script
# This script deploys the Service Bus Event Generator to Azure Container Apps

set -e

# Configuration
RESOURCE_GROUP="${RESOURCE_GROUP:-service-bus-event-generator-rg}"
LOCATION="${LOCATION:-eastus}"
CONTAINER_APP_NAME="${CONTAINER_APP_NAME:-service-bus-event-generator}"
CONTAINER_APP_ENVIRONMENT="${CONTAINER_APP_ENVIRONMENT:-service-bus-event-generator-env}"
CONTAINER_REGISTRY="${CONTAINER_REGISTRY:-your-registry.azurecr.io}"
IMAGE_NAME="${IMAGE_NAME:-service-bus-event-generator}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Azure CLI is installed
check_azure_cli() {
    if ! command -v az &> /dev/null; then
        log_error "Azure CLI is not installed. Please install it first."
        exit 1
    fi
    
    # Check if logged in
    if ! az account show &> /dev/null; then
        log_error "Not logged in to Azure CLI. Please run 'az login' first."
        exit 1
    fi
    
    log_info "Azure CLI is installed and authenticated"
}

# Check if Docker is installed
check_docker() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install it first."
        exit 1
    fi
    
    log_info "Docker is installed"
}

# Build and push Docker image
build_and_push_image() {
    log_info "Building Docker image..."
    
    # Build the image
    docker build -t ${CONTAINER_REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG} .
    
    log_info "Pushing image to registry..."
    
    # Login to Azure Container Registry
    az acr login --name $(echo ${CONTAINER_REGISTRY} | cut -d'.' -f1)
    
    # Push the image
    docker push ${CONTAINER_REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}
    
    log_info "Image pushed successfully"
}

# Create resource group
create_resource_group() {
    log_info "Creating resource group: ${RESOURCE_GROUP}"
    
    if az group show --name ${RESOURCE_GROUP} &> /dev/null; then
        log_warn "Resource group ${RESOURCE_GROUP} already exists"
    else
        az group create --name ${RESOURCE_GROUP} --location ${LOCATION}
        log_info "Resource group created"
    fi
}

# Deploy using Bicep template
deploy_infrastructure() {
    log_info "Deploying infrastructure using Bicep template..."
    
    az deployment group create \
        --resource-group ${RESOURCE_GROUP} \
        --template-file deploy-aca.bicep \
        --parameters \
            containerAppName=${CONTAINER_APP_NAME} \
            containerAppEnvironmentName=${CONTAINER_APP_ENVIRONMENT} \
            containerImage=${CONTAINER_REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG} \
            location=${LOCATION} \
        --output table
    
    log_info "Infrastructure deployed successfully"
}

# Get deployment outputs
get_deployment_outputs() {
    log_info "Getting deployment outputs..."
    
    CONTAINER_APP_URL=$(az deployment group show \
        --resource-group ${RESOURCE_GROUP} \
        --name deploy-aca \
        --query properties.outputs.containerAppUrl.value \
        --output tsv)
    
    SERVICE_BUS_NAMESPACE=$(az deployment group show \
        --resource-group ${RESOURCE_GROUP} \
        --name deploy-aca \
        --query properties.outputs.serviceBusNamespace.value \
        --output tsv)
    
    log_info "Container App URL: ${CONTAINER_APP_URL}"
    log_info "Service Bus Namespace: ${SERVICE_BUS_NAMESPACE}"
}

# Test the deployment
test_deployment() {
    log_info "Testing deployment..."
    
    if [ -z "${CONTAINER_APP_URL}" ]; then
        log_error "Container App URL not found"
        return 1
    fi
    
    # Test health endpoint
    log_info "Testing health endpoint..."
    curl -f "${CONTAINER_APP_URL}/health" || {
        log_error "Health check failed"
        return 1
    }
    
    # Test API endpoint (with API key)
    log_info "Testing API endpoint..."
    curl -f -X POST "${CONTAINER_APP_URL}/events" \
        -H "Content-Type: application/json" \
        -H "X-API-Key: dev-api-key-123" \
        -d '{
            "event_type": "test_event",
            "data": {"message": "test"},
            "source": "deployment_test"
        }' || {
        log_error "API test failed"
        return 1
    }
    
    log_info "Deployment test successful"
}

# Main deployment function
main() {
    log_info "Starting Azure Container Apps deployment..."
    
    # Load environment variables
    if [ -f .env ]; then
        export $(cat .env | grep -v '^#' | xargs)
        log_info "Environment variables loaded from .env"
    fi
    
    # Run deployment steps
    check_azure_cli
    check_docker
    create_resource_group
    build_and_push_image
    deploy_infrastructure
    get_deployment_outputs
    test_deployment
    
    log_info "Deployment completed successfully!"
    log_info "Your application is available at: ${CONTAINER_APP_URL}"
    log_info "API documentation: ${CONTAINER_APP_URL}/docs"
}

# Run main function
main "$@"
