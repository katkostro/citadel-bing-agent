@description('The AI Services resource name')
param ai_services string = 'aiServices'

@description('The project name')
param project_name string = 'project'

@description('Project description')
param projectDescription string = 'Azure AI Agent Basic Setup with Bing Search'

@description('Project display name')
param display_name string = 'AI Agent with Bing Search'

@description('The Azure region for deployment')
param location string = resourceGroup().location

@description('Model name to deploy')
param modelName string = 'gpt-4o'

@description('Model format')
param modelFormat string = 'OpenAI'

@description('Model version')
param modelVersion string = '2024-05-13'

@description('Model SKU name')
param modelSkuName string = 'GlobalStandard'

@description('Model capacity')
param modelCapacity int = 1

@description('Resource token for unique naming')
param resourceToken string = ''

// Create a short, unique suffix that will be unique to each resource group
param deploymentTimestamp string = utcNow('yyyyMMddHHmmss')
var uniqueSuffix = !empty(resourceToken) ? resourceToken : substring(uniqueString('${resourceGroup().id}-${deploymentTimestamp}'), 0, 13)
var account_name = toLower('${ai_services}${uniqueSuffix}')
var full_project_name = toLower('${project_name}${uniqueSuffix}')

/*
  Step 1: Create a Cognitive Services Account and deploy an agent compatible model
  
  - Note: Only public networking is supported.
*/ 
module aiAccount 'modules/ai-account-keys.bicep' = {
  name: 'ai-${account_name}-${uniqueSuffix}-deployment'
  params: {
    // workspace organization
    account_name: account_name
    location: location

    modelName: modelName
    modelFormat: modelFormat
    modelVersion: modelVersion
    modelSkuName: modelSkuName
    modelCapacity: modelCapacity
  }
}

/*
  Step 2: Create a Cognitive Services Project
  
  - Note: Only public networking is supported.
*/
module aiProject 'modules/ai-project-keys.bicep' = {
  name: 'ai-${full_project_name}-${uniqueSuffix}-deployment'
  params: {
    // workspace organization
    project_name: full_project_name
    description: projectDescription
    display_name: display_name
    location: location

    // dependent resources
    account_name: aiAccount.outputs.account_name
  }
}

/*
  Step 3: Create Bing Search connection for enhanced agent capabilities
*/
module bingConnection 'modules/add-bing-search-tool.bicep' = {
  name: 'ai-${full_project_name}-${uniqueSuffix}-bing-connection'
  params: {
    // dependent resources
    account_name: aiAccount.outputs.account_name
  }
}

// Outputs for the application
output AZURE_OPENAI_ENDPOINT string = aiAccount.outputs.aiServicesTarget
output AZURE_OPENAI_API_VERSION string = '2024-10-21'
output AZURE_OPENAI_CHAT_DEPLOYMENT string = modelName
output AZURE_AI_PROJECT_NAME string = aiProject.outputs.project_name
output AZURE_RESOURCE_GROUP string = resourceGroup().name
