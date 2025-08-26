param accountName string
param projectName string
param accountCapHost string = '${accountName}-caphost'
param projectCapHost string = '${projectName}-caphost'

resource account 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' existing = {
  name: accountName
}

resource project 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' existing = {
  name: projectName
  parent: account
}

// Set the account capability host
resource accountCapabilityHost 'Microsoft.CognitiveServices/accounts/capabilityHosts@2025-04-01-preview' = {
  name: accountCapHost
  parent: account
  properties: {
    capabilityHostKind: 'Agents'
  }
}

// Set the project capability host
resource projectCapabilityHost 'Microsoft.CognitiveServices/accounts/projects/capabilityHosts@2025-04-01-preview' = {
  name: projectCapHost
  parent: project
  properties: {
    capabilityHostKind: 'Agents'
  }
  dependsOn: [
    accountCapabilityHost
  ]
}

output accountCapabilityHostName string = accountCapabilityHost.name
output projectCapabilityHostName string = projectCapabilityHost.name
