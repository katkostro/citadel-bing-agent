param account_name string
param bingSearchName string = 'bingsearch-${account_name}'

#disable-next-line BCP081
resource account_name_resource 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' existing = {
  name: account_name
  scope: resourceGroup()
}

#disable-next-line BCP081
resource bingSearch 'Microsoft.Bing/accounts@2020-06-10' = {
  name: bingSearchName
  location: 'global'
  sku: {
    name: 'G1'
  }
  kind: 'Bing.Grounding'
}

#disable-next-line BCP081
resource bing_search_account_connection 'Microsoft.CognitiveServices/accounts/connections@2025-04-01-preview' = {
  name: '${account_name}-bingsearchconnection'
  parent: account_name_resource
  properties: {
    category: 'ApiKey'
    target: 'https://api.bing.microsoft.com/'
    authType: 'ApiKey'
    credentials: {
      key: bingSearch.listKeys('2020-06-10').key1
    }
    isSharedToAll: true
    metadata: {
      ApiType: 'Azure'
      Location: bingSearch.location
      ResourceId: bingSearch.id
    }
  }
}

output bingSearchResourceId string = bingSearch.id
output bingConnectionId string = bing_search_account_connection.id
