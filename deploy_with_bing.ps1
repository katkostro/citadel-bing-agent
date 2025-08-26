#!/usr/bin/env powershell
# Test script to deploy with Bing Search enabled

Write-Host "🚀 Deploying AI Agent with Bing Search Integration" -ForegroundColor Green
Write-Host "=" * 60

# Check if we have a Bing API key
$bingKey = $env:BING_SEARCH_API_KEY
if ([string]::IsNullOrEmpty($bingKey)) {
    Write-Host "❌ BING_SEARCH_API_KEY environment variable not set!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please set your Bing Search API key:" -ForegroundColor Yellow
    Write-Host "  `$env:BING_SEARCH_API_KEY = 'your-bing-api-key-here'" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Get your Bing Search API key from:" -ForegroundColor Yellow
    Write-Host "  1. Go to Azure Portal (https://portal.azure.com)" -ForegroundColor White
    Write-Host "  2. Create 'Bing Search v7' resource" -ForegroundColor White
    Write-Host "  3. Copy API key from 'Keys and Endpoint' page" -ForegroundColor White
    Write-Host ""
    exit 1
}

# Set Bing Search to enabled
$env:ENABLE_BING_SEARCH = "true"

Write-Host "✅ Configuration:" -ForegroundColor Green
Write-Host "  • Bing Search: ENABLED" -ForegroundColor White
Write-Host "  • API Key: $($bingKey.Substring(0, 8))..." -ForegroundColor White
Write-Host "  • Connection Name: $($env:BING_CONNECTION_NAME ?? 'bing-search-connection')" -ForegroundColor White
Write-Host ""

Write-Host "🏗️ Starting deployment with azd up..." -ForegroundColor Blue
Write-Host ""

# Run azd up
azd up

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✅ Deployment completed successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "🔍 Verifying Bing Search connection..." -ForegroundColor Blue
    python check_connections.py
    
    Write-Host ""
    Write-Host "🎉 Your AI agent now has web search capabilities!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Test web search with queries like:" -ForegroundColor Yellow
    Write-Host "  • 'What are the latest Microsoft news?'" -ForegroundColor White
    Write-Host "  • 'What's the current weather in Seattle?'" -ForegroundColor White
    Write-Host "  • 'What are today's top technology headlines?'" -ForegroundColor White
} else {
    Write-Host ""
    Write-Host "❌ Deployment failed with exit code $LASTEXITCODE" -ForegroundColor Red
    Write-Host ""
    Write-Host "💡 Troubleshooting tips:" -ForegroundColor Yellow
    Write-Host "  1. Check your Bing API key is valid" -ForegroundColor White
    Write-Host "  2. Ensure you have proper Azure permissions" -ForegroundColor White
    Write-Host "  3. Check azd logs for more details" -ForegroundColor White
}
