# Azure Container Apps Deployment Script (PowerShell)
# This script deploys the Service Bus Event Generator to Azure Container Apps

param(
    [string]$ResourceGroup = "service-bus-event-generator-rg",
    [string]$Location = "eastus",
    [string]$ContainerAppName = "service-bus-event-generator",
    [string]$ContainerAppEnvironment = "service-bus-event-generator-env",
    [string]$ContainerRegistry = "your-registry.azurecr.io",
    [string]$ImageName = "service-bus-event-generator",
    [string]$ImageTag = "latest"
)

# Error handling
$ErrorActionPreference = "Stop"

# Logging functions
function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Green
}

function Write-Warn {
    param([string]$Message)
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

# Check if Azure CLI is installed
function Test-AzureCLI {
    try {
        $null = Get-Command az -ErrorAction Stop
        Write-Info "Azure CLI is installed"
        
        # Check if logged in
        $account = az account show 2>$null | ConvertFrom-Json
        if (-not $account) {
            throw "Not logged in to Azure CLI"
        }
        Write-Info "Azure CLI is authenticated"
    }
    catch {
        Write-Error "Azure CLI is not installed or not authenticated. Please install Azure CLI and run 'az login'"
        exit 1
    }
}

# Check if Docker is installed
function Test-Docker {
    try {
        $null = Get-Command docker -ErrorAction Stop
        Write-Info "Docker is installed"
    }
    catch {
        Write-Error "Docker is not installed. Please install Docker first"
        exit 1
    }
}

# Build and push Docker image
function Build-AndPush-Image {
    Write-Info "Building Docker image..."
    
    # Build the image
    docker build -t "${ContainerRegistry}/${ImageName}:${ImageTag}" .
    if ($LASTEXITCODE -ne 0) {
        throw "Docker build failed"
    }
    
    Write-Info "Pushing image to registry..."
    
    # Login to Azure Container Registry
    $registryName = $ContainerRegistry.Split('.')[0]
    az acr login --name $registryName
    if ($LASTEXITCODE -ne 0) {
        throw "Azure Container Registry login failed"
    }
    
    # Push the image
    docker push "${ContainerRegistry}/${ImageName}:${ImageTag}"
    if ($LASTEXITCODE -ne 0) {
        throw "Docker push failed"
    }
    
    Write-Info "Image pushed successfully"
}

# Create resource group
function New-ResourceGroup {
    Write-Info "Creating resource group: $ResourceGroup"
    
    $existingRG = az group show --name $ResourceGroup 2>$null
    if ($existingRG) {
        Write-Warn "Resource group $ResourceGroup already exists"
    }
    else {
        az group create --name $ResourceGroup --location $Location
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to create resource group"
        }
        Write-Info "Resource group created"
    }
}

# Deploy using Bicep template
function Deploy-Infrastructure {
    Write-Info "Deploying infrastructure using Bicep template..."
    
    az deployment group create `
        --resource-group $ResourceGroup `
        --template-file deploy-aca.bicep `
        --parameters `
            containerAppName=$ContainerAppName `
            containerAppEnvironmentName=$ContainerAppEnvironment `
            containerImage="${ContainerRegistry}/${ImageName}:${ImageTag}" `
            location=$Location `
        --output table
    
    if ($LASTEXITCODE -ne 0) {
        throw "Infrastructure deployment failed"
    }
    
    Write-Info "Infrastructure deployed successfully"
}

# Get deployment outputs
function Get-DeploymentOutputs {
    Write-Info "Getting deployment outputs..."
    
    $deployment = az deployment group show `
        --resource-group $ResourceGroup `
        --name deploy-aca `
        --query properties.outputs `
        --output json | ConvertFrom-Json
    
    $script:ContainerAppUrl = $deployment.containerAppUrl.value
    $script:ServiceBusNamespace = $deployment.serviceBusNamespace.value
    
    Write-Info "Container App URL: $ContainerAppUrl"
    Write-Info "Service Bus Namespace: $ServiceBusNamespace"
}

# Test the deployment
function Test-Deployment {
    Write-Info "Testing deployment..."
    
    if (-not $ContainerAppUrl) {
        throw "Container App URL not found"
    }
    
    # Test health endpoint
    Write-Info "Testing health endpoint..."
    try {
        $response = Invoke-RestMethod -Uri "$ContainerAppUrl/health" -Method Get
        Write-Info "Health check passed: $($response.status)"
    }
    catch {
        Write-Error "Health check failed: $_"
        return $false
    }
    
    # Test API endpoint (with API key)
    Write-Info "Testing API endpoint..."
    try {
        $headers = @{
            "Content-Type" = "application/json"
            "X-API-Key" = "dev-api-key-123"
        }
        $body = @{
            event_type = "test_event"
            data = @{
                message = "test"
            }
            source = "deployment_test"
        } | ConvertTo-Json
        
        $response = Invoke-RestMethod -Uri "$ContainerAppUrl/events" -Method Post -Headers $headers -Body $body
        Write-Info "API test passed: $($response.message)"
    }
    catch {
        Write-Error "API test failed: $_"
        return $false
    }
    
    Write-Info "Deployment test successful"
    return $true
}

# Main deployment function
function Main {
    Write-Info "Starting Azure Container Apps deployment..."
    
    # Load environment variables from .env file if it exists
    if (Test-Path ".env") {
        Write-Info "Loading environment variables from .env"
        Get-Content ".env" | ForEach-Object {
            if ($_ -match "^([^#][^=]+)=(.*)$") {
                [Environment]::SetEnvironmentVariable($matches[1], $matches[2], "Process")
            }
        }
    }
    
    # Run deployment steps
    Test-AzureCLI
    Test-Docker
    New-ResourceGroup
    Build-AndPush-Image
    Deploy-Infrastructure
    Get-DeploymentOutputs
    $testResult = Test-Deployment
    
    if ($testResult) {
        Write-Info "Deployment completed successfully!"
        Write-Info "Your application is available at: $ContainerAppUrl"
        Write-Info "API documentation: $ContainerAppUrl/docs"
    }
    else {
        Write-Error "Deployment completed but tests failed"
        exit 1
    }
}

# Run main function
try {
    Main
}
catch {
    Write-Error "Deployment failed: $_"
    exit 1
}
