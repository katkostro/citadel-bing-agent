targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('Name of the the environment which is used to generate a short unique hash used in all resources.')
param environmentName string

@description('Location for all resources')
@allowed([
  'eastus'
  'eastus2'
  'swedencentral'
  'westus'
  'westus3'
])
param location string

@description('Id of the user or app to assign application roles')
param principalId string = ''

@description('Existing AI Project Resource ID')
param azureExistingAIProjectResourceId string

@description('Existing AI Project Endpoint')
param azureExistingAIProjectEndpoint string

@description('Model deployment name')
param chatDeploymentName string = 'gpt-4o'

// Generate a unique token to be used in naming resources
var resourceToken = toLower(uniqueString(subscription().id, environmentName, location))

// Organize resources in a resource group
resource resourceGroup 'Microsoft.Resources/resourceGroups@2021-04-01' = {
  name: '${environmentName}-rg'
  location: location
  tags: {
    'azd-env-name': environmentName
  }
}

// Monitor application with Azure Monitor
module monitoring './core/monitor/monitoring.bicep' = {
  name: 'monitoring'
  scope: resourceGroup
  params: {
    location: location
    tags: {}
    logAnalyticsName: 'log-${resourceToken}'
    applicationInsightsName: 'appi-${resourceToken}'
  }
}

// Container apps environment
module containerAppsEnvironment './core/host/container-apps-environment.bicep' = {
  name: 'container-apps-environment'
  scope: resourceGroup
  params: {
    name: 'cae-${resourceToken}'
    location: location
    tags: {}
    logAnalyticsWorkspaceId: monitoring.outputs.logAnalyticsWorkspaceId
  }
}

// The application frontend
module app './api.bicep' = {
  name: 'app'
  scope: resourceGroup
  params: {
    name: 'app-${resourceToken}'
    location: location
    tags: {}
    applicationInsightsName: monitoring.outputs.applicationInsightsName
    containerAppsEnvironmentId: containerAppsEnvironment.outputs.id
    containerRegistryName: containerAppsEnvironment.outputs.registryName
    containerRegistryId: containerAppsEnvironment.outputs.registryId
    exists: false
    // Connect to external AI project
    azureExistingAIProjectResourceId: azureExistingAIProjectResourceId
    azureExistingAIProjectEndpoint: azureExistingAIProjectEndpoint
    chatDeploymentName: chatDeploymentName
    userAssignedIdentityId: containerAppsEnvironment.outputs.identityId
    userAssignedIdentityClientId: containerAppsEnvironment.outputs.identityClientId
  }
}

// Outputs for the application
output AZURE_LOCATION string = location
output AZURE_TENANT_ID string = tenant().tenantId
output AZURE_RESOURCE_GROUP string = resourceGroup.name

// Application outputs
output SERVICE_API_AND_FRONTEND_URI string = app.outputs.SERVICE_API_AND_FRONTEND_URI

// AI Project connection info (from external backend)
output AZURE_EXISTING_AIPROJECT_RESOURCE_ID string = azureExistingAIProjectResourceId
output AZURE_EXISTING_AIPROJECT_ENDPOINT string = azureExistingAIProjectEndpoint
output AZURE_OPENAI_CHAT_DEPLOYMENT string = chatDeploymentName
output AZURE_OPENAI_API_VERSION string = '2024-10-21'

// Used for passwordless authentication to Cognitive Services
output AZURE_CLIENT_ID string = containerAppsEnvironment.outputs.identityClientId
