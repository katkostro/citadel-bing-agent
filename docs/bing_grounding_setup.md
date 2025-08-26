# Bing Grounding Setup for AI Agent

This document explains how to set up Bing Grounding functionality for the AI Agent to enable web search capabilities.

## Overview

Bing Grounding allows the AI agent to search the web for current, up-to-date information when:
- Users ask about recent events or news
- Information is not available in the knowledge base or uploaded files
- Users specifically request web search or current information
- You need to verify or supplement information with current data

## Setup Steps

### 1. Deploy with Bing Grounding Enabled

The infrastructure is configured to optionally deploy a Bing Search resource. Bing Grounding is enabled by default.

To deploy with Bing Grounding:
```bash
azd up
```

To deploy without Bing Grounding:
```bash
azd up --set enableBingGrounding=false
```

### 2. Configure Bing Search API Key

After deployment, you need to manually set the Bing Search API key.

#### Option 1: Use the Setup Script (Recommended)

We provide scripts to automate the API key configuration:

**For Linux/macOS:**
```bash
./scripts/setup_bing_grounding.sh
```

**For Windows PowerShell:**
```powershell
.\scripts\setup_bing_grounding.ps1
```

#### Option 2: Manual Configuration

1. Get the Bing Search API key from the Azure portal:
   - Navigate to your resource group
   - Find the Bing Search resource (named `bing-{resourceToken}`)
   - Go to "Keys and Endpoint"
   - Copy "Key 1"

2. Set the API key as a container app secret:
   ```bash
   az containerapp secret set \
     --name <your-container-app-name> \
     --resource-group <your-resource-group> \
     --secrets bing-search-api-key=<your-bing-api-key>
   ```

3. Update the container app environment variable:
   ```bash
   az containerapp update \
     --name <your-container-app-name> \
     --resource-group <your-resource-group> \
     --set-env-vars BING_SEARCH_API_KEY=secretref:bing-search-api-key
   ```

4. Restart the container app:
   ```bash
   az containerapp restart \
     --name <your-container-app-name> \
     --resource-group <your-resource-group>
   ```

### 3. Verify Setup

To verify Bing Grounding is working:

1. Access your deployed AI agent web application
2. Ask a question about current events or recent news
3. The agent should use web search to find current information

Example queries that will trigger Bing search:
- "What's the latest news about [topic]?"
- "What happened today in [location]?"
- "Find current information about [company/technology/event]"

## Environment Variables

The following environment variables control Bing Grounding behavior:

- `BING_SEARCH_API_KEY`: Required. Your Bing Search API subscription key
- `BING_SEARCH_ENDPOINT`: Optional. Bing Search API endpoint (defaults to `https://api.bing.microsoft.com/`)
- `BING_SEARCH_MARKET`: Optional. Market for search results (defaults to `en-US`)
- `BING_SEARCH_RESULTS_COUNT`: Optional. Number of results to return (defaults to 5, max 50)

## Local Development

For local development, create a `.env` file in the `src` directory:

```bash
# Copy from the template
cp bing-grounding.env.template src/.env

# Edit src/.env and add your Bing Search API key
BING_SEARCH_API_KEY=your_bing_search_api_key_here
```

## Troubleshooting

### Bing Search Not Working

1. **Check API Key**: Ensure the `BING_SEARCH_API_KEY` environment variable is set correctly
2. **Check Resource**: Verify the Bing Search resource was deployed successfully
3. **Check Logs**: Look at the container app logs for any error messages related to Bing search

### API Key Issues

1. **Invalid Key**: Ensure you copied the correct API key from the Azure portal
2. **Resource Region**: Some Bing Search features may vary by region
3. **Quota Limits**: Check if you've exceeded your Bing Search API quota

### Query Not Triggering Search

The agent will use Bing search when:
- The query asks for recent/current information
- The information is not available in the knowledge base
- The user explicitly requests web search

If the agent isn't using web search, try rephrasing your query to be more explicit about wanting current information.

## Cost Considerations

- **Free Tier (F1)**: 1,000 transactions per month at no charge
- **Standard Tier (S1)**: Pay-per-use pricing for higher volumes

The infrastructure defaults to the F1 (free) tier. You can change this by setting the `bingSearchSku` parameter during deployment:

```bash
azd up --set bingSearchSku=S1
```

## Security Notes

- API keys are stored as container app secrets
- The Bing Search API key should never be committed to source code
- Access to the Bing Search resource is controlled through Azure RBAC
