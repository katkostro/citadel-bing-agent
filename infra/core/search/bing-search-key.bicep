@description('Name of the Bing Search resource')
param bingSearchName string

// Reference the existing Bing Search resource
resource bingSearch 'Microsoft.CognitiveServices/accounts@2023-05-01' existing = {
  name: bingSearchName
}

@description('The primary API key for the Bing Search resource')
output apiKey string = bingSearch.listKeys().key1

@description('The endpoint for the Bing Search resource')
output endpoint string = bingSearch.properties.endpoint
