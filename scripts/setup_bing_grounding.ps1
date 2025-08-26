# Script to configure Bing Search API key for AI Agent
# This script helps set up the Bing Search API key as a container app secret

param(
    [string]$ResourceGroupName = $env:AZURE_RESOURCE_GROUP,
    [string]$ContainerAppName = $env:SERVICE_API_NAME,
    [string]$BingApiKey = ""
)

Write-Host "🔍 Bing Grounding Configuration Script" -ForegroundColor Blue
Write-Host "This script will help you configure the Bing Search API key for web grounding."
Write-Host

# Get required values
if ([string]::IsNullOrWhiteSpace($ResourceGroupName)) {
    $ResourceGroupName = Read-Host "Please enter your Azure Resource Group name"
}

if ([string]::IsNullOrWhiteSpace($ContainerAppName)) {
    $ContainerAppName = Read-Host "Please enter your Container App name"
}

if ([string]::IsNullOrWhiteSpace($BingApiKey)) {
    $SecureApiKey = Read-Host "Please enter your Bing Search API key" -AsSecureString
    $BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureApiKey)
    $BingApiKey = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)
    [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($BSTR)
}

if ([string]::IsNullOrWhiteSpace($BingApiKey)) {
    Write-Host "❌ Bing Search API key cannot be empty" -ForegroundColor Red
    exit 1
}

Write-Host
Write-Host "📝 Configuration Summary:" -ForegroundColor Blue
Write-Host "  Resource Group: $ResourceGroupName"
Write-Host "  Container App: $ContainerAppName"
Write-Host "  API Key: [HIDDEN]"
Write-Host

$confirmation = Read-Host "Proceed with configuration? (y/N)"
if ($confirmation -ne 'y' -and $confirmation -ne 'Y') {
    Write-Host "⏹️ Configuration cancelled" -ForegroundColor Yellow
    exit 0
}

Write-Host "⏳ Setting up Bing Search API key..." -ForegroundColor Blue

try {
    # Set the secret
    Write-Host "Setting container app secret..."
    az containerapp secret set `
        --name $ContainerAppName `
        --resource-group $ResourceGroupName `
        --secrets "bing-search-api-key=$BingApiKey" `
        --output none

    if ($LASTEXITCODE -ne 0) {
        throw "Failed to set container app secret"
    }

    # Update environment variable
    Write-Host "Updating environment variable..."
    az containerapp update `
        --name $ContainerAppName `
        --resource-group $ResourceGroupName `
        --set-env-vars BING_SEARCH_API_KEY=secretref:bing-search-api-key `
        --output none

    if ($LASTEXITCODE -ne 0) {
        throw "Failed to update environment variable"
    }

    # Get the active revision name
    Write-Host "Finding active revision..."
    $activeRevision = az containerapp revision list `
        --name $ContainerAppName `
        --resource-group $ResourceGroupName `
        --query "[?properties.active==true].name" `
        --output tsv

    if ([string]::IsNullOrWhiteSpace($activeRevision)) {
        throw "No active revision found"
    }

    # Restart the active revision
    Write-Host "Restarting revision $activeRevision..."
    az containerapp revision restart `
        --name $ContainerAppName `
        --resource-group $ResourceGroupName `
        --revision $activeRevision `
        --output none

    if ($LASTEXITCODE -ne 0) {
        throw "Failed to restart revision"
    }

    Write-Host
    Write-Host "✅ Bing Grounding configuration completed successfully!" -ForegroundColor Green
    Write-Host
    Write-Host "🔍 Testing:" -ForegroundColor Blue
    Write-Host "Try asking your agent questions about current events or recent news."
    Write-Host "Examples:"
    Write-Host "  - 'What's the latest news about artificial intelligence?'"
    Write-Host "  - 'Find current information about Microsoft Azure updates'"
    Write-Host "  - 'What happened in the tech world this week?'"
    Write-Host
    Write-Host "📚 For more information, see:" -ForegroundColor Blue
    Write-Host "  docs/bing_grounding_setup.md"

} catch {
    Write-Host "❌ Error: $_" -ForegroundColor Red
    exit 1
} finally {
    # Clear the API key from memory
    if ($BingApiKey) {
        $BingApiKey = $null
    }
}
