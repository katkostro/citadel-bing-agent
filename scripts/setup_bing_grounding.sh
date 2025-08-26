#!/bin/bash

# Script to configure Bing Search API key for AI Agent
# This script helps set up the Bing Search API key as a container app secret

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔍 Bing Grounding Configuration Script${NC}"
echo "This script will help you configure the Bing Search API key for web grounding."
echo

# Get required values
if [ -z "$AZURE_RESOURCE_GROUP" ]; then
    echo -e "${YELLOW}Please enter your Azure Resource Group name:${NC}"
    read -r AZURE_RESOURCE_GROUP
fi

if [ -z "$SERVICE_API_NAME" ]; then
    echo -e "${YELLOW}Please enter your Container App name:${NC}"
    read -r SERVICE_API_NAME
fi

echo -e "${YELLOW}Please enter your Bing Search API key:${NC}"
read -rs BING_API_KEY

if [ -z "$BING_API_KEY" ]; then
    echo -e "${RED}❌ Bing Search API key cannot be empty${NC}"
    exit 1
fi

echo
echo -e "${BLUE}📝 Configuration Summary:${NC}"
echo "  Resource Group: $AZURE_RESOURCE_GROUP"
echo "  Container App: $SERVICE_API_NAME"
echo "  API Key: [HIDDEN]"
echo

read -p "Proceed with configuration? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}⏹️ Configuration cancelled${NC}"
    exit 0
fi

echo -e "${BLUE}⏳ Setting up Bing Search API key...${NC}"

# Set the secret
echo "Setting container app secret..."
az containerapp secret set \
    --name "$SERVICE_API_NAME" \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --secrets bing-search-api-key="$BING_API_KEY" \
    --output none

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Failed to set container app secret${NC}"
    exit 1
fi

# Update environment variable
echo "Updating environment variable..."
az containerapp update \
    --name "$SERVICE_API_NAME" \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --set-env-vars BING_SEARCH_API_KEY=secretref:bing-search-api-key \
    --output none

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Failed to update environment variable${NC}"
    exit 1
fi

# Get the active revision name
echo "Finding active revision..."
ACTIVE_REVISION=$(az containerapp revision list \
    --name "$SERVICE_API_NAME" \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --query "[?properties.active==true].name" \
    --output tsv)

if [ -z "$ACTIVE_REVISION" ]; then
    echo -e "${RED}❌ No active revision found${NC}"
    exit 1
fi

# Restart the active revision
echo "Restarting revision $ACTIVE_REVISION..."
az containerapp revision restart \
    --name "$SERVICE_API_NAME" \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --revision "$ACTIVE_REVISION" \
    --output none

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Failed to restart revision${NC}"
    exit 1
fi

echo
echo -e "${GREEN}✅ Bing Grounding configuration completed successfully!${NC}"
echo
echo -e "${BLUE}🔍 Testing:${NC}"
echo "Try asking your agent questions about current events or recent news."
echo "Examples:"
echo "  - 'What's the latest news about artificial intelligence?'"
echo "  - 'Find current information about Microsoft Azure updates'"
echo "  - 'What happened in the tech world this week?'"
echo
echo -e "${BLUE}📚 For more information, see:${NC}"
echo "  docs/bing_grounding_setup.md"
