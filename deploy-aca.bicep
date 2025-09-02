// Azure Container Apps Bicep template for Service Bus Event Generator
// This template creates the necessary Azure resources for the application

@description('The name of the Container App')
param containerAppName string = 'service-bus-event-generator'

@description('The name of the Container App Environment')
param containerAppEnvironmentName string = 'service-bus-event-generator-env'

@description('The name of the Log Analytics workspace')
param logAnalyticsWorkspaceName string = 'service-bus-event-generator-logs'

@description('The name of the Service Bus namespace')
param serviceBusNamespaceName string = 'service-bus-event-generator-sb'

@description('The name of the Service Bus queue')
param serviceBusQueueName string = 'events'

@description('The name of the Service Bus topic (optional)')
param serviceBusTopicName string = ''

@description('The location for all resources')
param location string = resourceGroup().location

@description('The container image to deploy')
param containerImage string = 'your-registry.azurecr.io/service-bus-event-generator:latest'

@description('The number of replicas')
param replicaCount int = 2

@description('The CPU and memory resources')
param cpuRequests string = '0.25'
param memoryRequests string = '0.5Gi'
param cpuLimits string = '0.5'
param memoryLimits string = '1Gi'

// Log Analytics Workspace
resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: logAnalyticsWorkspaceName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

// Service Bus Namespace
resource serviceBusNamespace 'Microsoft.ServiceBus/namespaces@2022-01-01-preview' = {
  name: serviceBusNamespaceName
  location: location
  sku: {
    name: 'Standard'
    tier: 'Standard'
  }
  properties: {
    minimumTlsVersion: '1.2'
  }
}

// Service Bus Queue
resource serviceBusQueue 'Microsoft.ServiceBus/namespaces/queues@2022-01-01-preview' = {
  parent: serviceBusNamespace
  name: serviceBusQueueName
  properties: {
    maxSizeInMegabytes: 1024
    defaultMessageTimeToLive: 'P14D'
    lockDuration: 'PT5M'
    enableDeadLetteringOnMessageExpiration: true
    enableBatchedOperations: true
  }
}

// Service Bus Topic (optional)
resource serviceBusTopic 'Microsoft.ServiceBus/namespaces/topics@2022-01-01-preview' = if (!empty(serviceBusTopicName)) {
  parent: serviceBusNamespace
  name: serviceBusTopicName
  properties: {
    maxSizeInMegabytes: 1024
    defaultMessageTimeToLive: 'P14D'
    enableBatchedOperations: true
  }
}

// Container App Environment
resource containerAppEnvironment 'Microsoft.App/managedEnvironments@2022-10-01' = {
  name: containerAppEnvironmentName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsWorkspace.properties.customerId
        sharedKey: logAnalyticsWorkspace.listKeys().primarySharedKey
      }
    }
  }
}

// Container App
resource containerApp 'Microsoft.App/containerApps@2022-10-01' = {
  name: containerAppName
  location: location
  properties: {
    managedEnvironmentId: containerAppEnvironment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8000
        allowInsecure: false
        traffic: [
          {
            weight: 100
            latestRevision: true
          }
        ]
      }
      secrets: [
        {
          name: 'service-bus-namespace'
          value: serviceBusNamespace.name
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'service-bus-event-generator'
          image: containerImage
          resources: {
            cpu: json(parseFloat(cpuRequests))
            memory: memoryRequests
          }
          env: [
            {
              name: 'HOST'
              value: '0.0.0.0'
            }
            {
              name: 'PORT'
              value: '8000'
            }
            {
              name: 'LOG_LEVEL'
              value: 'info'
            }
            {
              name: 'ENVIRONMENT'
              value: 'production'
            }
            {
              name: 'USE_MANAGED_IDENTITY'
              value: 'true'
            }
            {
              name: 'SERVICE_BUS_NAMESPACE'
              secretRef: 'service-bus-namespace'
            }
            {
              name: 'SERVICE_BUS_QUEUE_NAME'
              value: serviceBusQueueName
            }
            {
              name: 'SERVICE_BUS_TOPIC_NAME'
              value: serviceBusTopicName
            }
          ]
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/health'
                port: 8000
              }
              initialDelaySeconds: 30
              periodSeconds: 10
            }
            {
              type: 'Readiness'
              httpGet: {
                path: '/health'
                port: 8000
              }
              initialDelaySeconds: 5
              periodSeconds: 5
            }
          ]
        }
      ]
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
    }
  }
  identity: {
    type: 'SystemAssigned'
  }
}

// Role assignment for Service Bus access
resource serviceBusRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(containerApp.id, 'Azure Service Bus Data Sender')
  scope: serviceBusNamespace
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '69a216fc-b8fb-44d8-bc22-a1e3a5f0ae69') // Azure Service Bus Data Sender
    principalId: containerApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// Outputs
output containerAppName string = containerApp.name
output containerAppUrl string = 'https://${containerApp.properties.configuration.ingress.fqdn}'
output serviceBusNamespace string = serviceBusNamespace.name
output serviceBusQueueName string = serviceBusQueue.name
output serviceBusTopicName string = serviceBusTopicName
output logAnalyticsWorkspaceId string = logAnalyticsWorkspace.id
