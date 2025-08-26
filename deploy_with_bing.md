# Deploy with Bing Search Integration

This guide explains how to deploy the application with Bing Search functionality enabled using the enhanced Bicep templates.

## Prerequisites

1. **Bing Search API Key**: You need a Bing Search v7 API key from Azure Portal
   - Go to [Azure Portal](https://portal.azure.com)
   - Create a new "Bing Search v7" resource
   - Copy the API key from the Keys and Endpoint page

## Deployment Options

### Option 1: Deploy with Bing Search Enabled

To deploy the application with Bing Search functionality:

```powershell
# Set the Bing Search API key
$env:BING_SEARCH_API_KEY = "YOUR_BING_API_KEY_HERE"

# Enable Bing Search
$env:ENABLE_BING_SEARCH = "true"

# Deploy using azd
azd up
```

### Option 2: Deploy without Bing Search (Default)

To deploy without Bing Search (current behavior):

```powershell
# Deploy using azd (Bing Search disabled by default)
azd up
```

### Option 3: Add Bing Search to Existing Deployment

If you already have a deployment and want to add Bing Search:

```powershell
# Set the Bing Search API key
$env:BING_SEARCH_API_KEY = "YOUR_BING_API_KEY_HERE"

# Enable Bing Search
$env:ENABLE_BING_SEARCH = "true"

# Update the deployment
azd up
```

## Environment Variables

The following environment variables control Bing Search integration:

- `ENABLE_BING_SEARCH`: Set to "true" to enable Bing Search connection (default: "false")
- `BING_SEARCH_API_KEY`: Your Bing Search v7 API key (required when enabling Bing Search)
- `BING_CONNECTION_NAME`: Name for the Bing connection (default: "bing-search-connection")

## What Gets Created

When `ENABLE_BING_SEARCH=true`, the deployment will:

1. **Create a Bing Search Connection** in your Azure AI Foundry project
   - Connection name: `bing-search-connection` (configurable)
   - Target endpoint: `https://api.bing.microsoft.com/`
   - Authentication: API Key
   - Shared to all users in the project

2. **Configure the Application** to automatically detect and use the Bing connection
   - The application code in `gunicorn.conf.py` already includes logic to detect Bing connections
   - When a Bing connection is found, web search functionality will be automatically enabled

## Verification

After deployment, you can verify the Bing connection was created:

```powershell
# Check connections in your AI Foundry project
python check_connections.py
```

You should see output similar to:
```
📋 Found 4 connections:
1. stfwcesjjk2tcxa (AzureStorageAccount)
2. aoai-connection (AzureOpenAI)
3. appinsights-connection (AppInsights)
4. bing-search-connection (CustomKeys) ✨ Bing Search enabled!
```

## Testing Web Search

Once deployed with Bing Search enabled, you can test web search functionality by asking questions like:

- "What are the latest news about Microsoft?"
- "What's the current weather in Seattle?"
- "What are the stock prices of major tech companies?"

The AI agent will automatically use Bing Search to provide real-time, up-to-date information.

## Security Notes

- The Bing Search API key is stored securely in the Azure AI Foundry connection
- The key is marked as a secure parameter in Bicep and will not appear in deployment logs
- Access to the connection is controlled through Azure RBAC

## Troubleshooting

If Bing Search isn't working:

1. **Check the connection exists**:
   ```powershell
   python check_connections.py
   ```

2. **Verify the API key is valid**:
   - Test the key directly against Bing Search API
   - Ensure the key has not expired

3. **Check application logs**:
   ```powershell
   az containerapp logs show --name "ca-api-{YOUR_RESOURCE_TOKEN}" --resource-group "rg-{YOUR_ENV_NAME}" --tail 50
   ```

4. **Restart the application** (if needed):
   ```powershell
   azd deploy
   ```
