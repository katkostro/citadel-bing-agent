@description('Name of the Bing Search resource')
param name string

@description('Tags to apply to the resource')
param tags object = {}

resource bingSearch 'Microsoft.Bing/accounts@2020-06-10' = {
  name: name
  location: 'global'
  tags: tags
  kind: 'Bing.Grounding'
  sku: {
    name: 'G1'
  }
}

@description('The endpoint for the Bing Search resource')
output endpoint string = 'https://api.bing.microsoft.com/'

@description('The name of the Bing Search resource')
output name string = bingSearch.name

@description('The resource ID of the Bing Search resource')
output resourceId string = bingSearch.id
