metadata description = 'Creates a Bing Search connection in an existing Azure AI Project.'

@description('The AI Service account name.')
param aiServiceName string

@description('The Bing Search resource ID')
param bingSearchResourceId string

@description('The Bing Search connection name.')
param bingConnectionName string = 'bing-search-connection'

@description('The AI Project name (extracted from resource ID).')
param projectName string = ''

// Reference the existing AI Services account
resource existingAIService 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' existing = {
  name: aiServiceName
}

// Reference the existing AI Project (if projectName is provided)
resource existingProject 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' existing = if (!empty(projectName)) {
  name: projectName
  parent: existingAIService
}

// Create the Bing Search connection in the existing AI Project (not the AI Services account)
resource bingSearchConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview' = if (!empty(projectName)) {
  name: bingConnectionName
  parent: existingProject
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

// CRITICAL: Account capability host enables the AI Services account to support agents
resource accountCapabilityHost 'Microsoft.CognitiveServices/accounts/capabilityHosts@2025-04-01-preview' = {
  name: '${aiServiceName}-caphost'
  parent: existingAIService
  properties: {
    capabilityHostKind: 'Agents'
  }
}

// CRITICAL: Project capability host enables the project to use tools and connections
resource projectCapabilityHost 'Microsoft.CognitiveServices/accounts/projects/capabilityHosts@2025-04-01-preview' = if (!empty(projectName)) {
  name: '${projectName}-caphost'
  parent: existingProject
  properties: {
    capabilityHostKind: 'Agents'
  }
  dependsOn: [
    accountCapabilityHost
    bingSearchConnection
  ]
}

output bingConnectionId string = (!empty(projectName)) ? bingSearchConnection.id : ''
output bingConnectionName string = (!empty(projectName)) ? bingSearchConnection.name : ''
