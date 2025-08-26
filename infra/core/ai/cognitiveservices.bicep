metadata description = 'Creates an Azure Cognitive Services instance.'
param aiServiceName string
param aiProjectName string
param location string = resourceGroup().location
param tags object = {}
@description('The custom subdomain name used to access the API. Defaults to the value of the name parameter.')
param customSubDomainName string = aiServiceName
param disableLocalAuth bool = true
param deployments array = []
param appInsightsId string
param appInsightConnectionString string
param appInsightConnectionName string
param aoaiConnectionName string
param storageAccountId string
param storageAccountConnectionName string
@description('Enable Bing Search connection for web search capabilities')
param enableBingSearch bool = false
@description('The Bing Search resource ID for BingGrounding connection')
param bingSearchResourceId string = ''
@description('The Bing Search connection name.')
param bingConnectionName string = 'bing-search-connection'

@allowed([ 'Enabled', 'Disabled' ])
param publicNetworkAccess string = 'Enabled'
param sku object = {
  name: 'S0'
}

param allowedIpRules array = []
param networkAcls object = empty(allowedIpRules) ? {
  defaultAction: 'Allow'
} : {
  ipRules: allowedIpRules
  defaultAction: 'Deny'
}

resource account 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' = {
  name: aiServiceName
  location: location
  sku: sku
  kind: 'AIServices'
  identity: {
    type: 'SystemAssigned'
  }
  tags: tags
  properties: {
    allowProjectManagement: true
    customSubDomainName: customSubDomainName
    networkAcls: networkAcls
    publicNetworkAccess: publicNetworkAccess
    disableLocalAuth: disableLocalAuth 
  }
}

resource aiServiceConnection 'Microsoft.CognitiveServices/accounts/connections@2025-04-01-preview' = {
  name: aoaiConnectionName
  parent: account
  properties: {
    category: 'AzureOpenAI'
    authType: 'AAD'
    isSharedToAll: true
    target: account.properties.endpoints['OpenAI Language Model Instance API']
    metadata: {
      ApiType: 'azure'
      ResourceId: account.id
    }
  }
}


// Creates the Azure Foundry connection to your Azure App Insights resource
resource appInsightConnection 'Microsoft.CognitiveServices/accounts/connections@2025-04-01-preview' = {
  name: appInsightConnectionName
  parent: account
  properties: {
    category: 'AppInsights'
    target: appInsightsId
    authType: 'ApiKey'
    isSharedToAll: true
    credentials: {
      key: appInsightConnectionString
    }
    metadata: {
      ApiType: 'Azure'
      ResourceId: appInsightsId
    }
  }
}

// Creates the Azure Foundry connection to your Azure Storage resource
resource storageAccountConnection 'Microsoft.CognitiveServices/accounts/connections@2025-04-01-preview' = {
  name: storageAccountConnectionName
  parent: account
  properties: {
    category: 'AzureStorageAccount'
    target: storageAccountId
    authType: 'AAD'
    isSharedToAll: true    
    metadata: {
      ApiType: 'Azure'
      ResourceId: storageAccountId
    }
  }
}

// Creates the Azure Foundry connection to Bing Search (conditional) - as a project-level connection with ApiKey auth
resource bingSearchConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview' = if (enableBingSearch) {
  name: bingConnectionName
  parent: aiProject
  properties: {
    category: 'ApiKey'
    target: 'https://api.bing.microsoft.com/'
    authType: 'ApiKey'
    isSharedToAll: true
    credentials: {
      key: listKeys(bingSearchResourceId, '2020-06-10').key1
    }
    metadata: {
      ApiType: 'Azure'
      ResourceId: bingSearchResourceId
      description: 'Bing Search connection for real-time web search'
    }
  }
}

resource aiProject 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' = {
  parent: account
  name: aiProjectName
  location: location
  tags: tags  
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    description: aiProjectName
    displayName: aiProjectName
  }
}

// CRITICAL: Capability hosts enable agents to actually use tools
// Account capability host enables the AI Services account to support agents
resource accountCapabilityHost 'Microsoft.CognitiveServices/accounts/capabilityHosts@2025-04-01-preview' = {
  name: '${aiServiceName}-caphost'
  parent: account
  properties: {
    capabilityHostKind: 'Agents'
  }
  dependsOn: [
    aiProject
  ]
}

// Project capability host enables the project to use tools and connections
resource projectCapabilityHost 'Microsoft.CognitiveServices/accounts/projects/capabilityHosts@2025-04-01-preview' = {
  name: '${aiProjectName}-caphost'
  parent: aiProject
  properties: {
    capabilityHostKind: 'Agents'
  }
  dependsOn: [
    accountCapabilityHost
  ]
}

@batchSize(1)
resource aiServicesDeployments 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = [for deployment in deployments: {
  parent: account
  name: deployment.name
  properties: {
    model: deployment.model
    raiPolicyName: contains(deployment, 'raiPolicyName') ? deployment.raiPolicyName : null
  }
  sku: contains(deployment, 'sku') ? deployment.sku : {
    name: 'Standard'
    capacity: 20
  }
}]



output endpoint string = account.properties.endpoint
output endpoints object = account.properties.endpoints
output id string = account.id
output name string = account.name
output projectResourceId string = aiProject.id
output projectName string = aiProject.name
output serviceName string = account.name
output projectEndpoint string = aiProject.properties.endpoints['AI Foundry API']
output PrincipalId string = account.identity.principalId
output accountPrincipalId string = account.identity.principalId
output projectPrincipalId string = aiProject.identity.principalId
output bingConnectionId string = enableBingSearch ? bingSearchConnection.id : ''
