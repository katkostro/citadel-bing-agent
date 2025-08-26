#!/usr/bin/env python3
"""
Script to create a Bing Search connection in Azure AI Foundry project using SDK
"""

import os
import asyncio
from azure.ai.projects.aio import AIProjectClient
from azure.identity.aio import DefaultAzureCredential
from azure.ai.projects.models import ConnectionType

async def create_bing_connection():
    """Create Bing Search connection in Azure AI Foundry project"""
    
    # Get project endpoint from environment or set it directly
    project_endpoint = "https://aoai-fwcesjjk2tcxa.services.ai.azure.com/api/projects/proj-fwcesjjk2tcxa"
    
    # Get Bing API key - you'll need to provide this
    bing_api_key = input("Enter your Bing Search API Key (from earlier setup): ").strip()
    if not bing_api_key:
        print("❌ Error: Bing API key is required")
        return
    
    try:
        async with DefaultAzureCredential(exclude_shared_token_cache_credential=True) as credential:
            async with AIProjectClient(
                credential=credential,
                endpoint=project_endpoint
            ) as ai_project:
                
                print(f"📁 Connected to Azure AI Foundry project")
                print(f"   Endpoint: {project_endpoint}")
                
                # Try multiple approaches to create the connection
                connection_name = "bing-search-connection"
                
                print(f"\n🔧 Attempting to create Bing connection: {connection_name}")
                
                # Method 1: Try the direct connection creation approach
                try:
                    print("   Trying Method 1: Direct connection creation...")
                    
                    connection_config = {
                        "name": connection_name,
                        "type": "custom",
                        "target": "https://api.bing.microsoft.com/",
                        "credentials": {
                            "type": "api_key",
                            "api_key": bing_api_key
                        },
                        "metadata": {
                            "description": "Bing Search connection for real-time web search",
                            "connection_type": "bing_search"
                        }
                    }
                    
                    # Try using the connections.create method
                    connection = await ai_project.connections.create(**connection_config)
                    print(f"✅ Success! Created connection using Method 1")
                    print(f"   Connection ID: {connection.id}")
                    print(f"   Connection Name: {connection.name}")
                    return connection
                    
                except Exception as e1:
                    print(f"   ❌ Method 1 failed: {e1}")
                
                # Method 2: Try alternative connection format
                try:
                    print("   Trying Method 2: Alternative format...")
                    
                    from azure.ai.projects.models import ConnectionAuthType
                    
                    connection_data = {
                        "connection_name": connection_name,
                        "connection_type": "custom",
                        "target": "https://api.bing.microsoft.com/",
                        "auth_type": ConnectionAuthType.API_KEY,
                        "credentials": {
                            "key": bing_api_key
                        }
                    }
                    
                    connection = await ai_project.connections.create_connection(**connection_data)
                    print(f"✅ Success! Created connection using Method 2")
                    print(f"   Connection ID: {connection.id}")
                    return connection
                    
                except Exception as e2:
                    print(f"   ❌ Method 2 failed: {e2}")
                
                # Method 3: Try using the REST API approach through the SDK
                try:
                    print("   Trying Method 3: REST API approach...")
                    
                    # This uses the underlying REST client
                    rest_client = ai_project._client
                    
                    connection_payload = {
                        "properties": {
                            "category": "CustomKeys",
                            "target": "https://api.bing.microsoft.com/",
                            "authType": "ApiKey",
                            "credentials": {
                                "keys": {
                                    "key": bing_api_key
                                }
                            },
                            "metadata": {
                                "description": "Bing Search connection",
                                "connectionType": "BingSearch"
                            }
                        }
                    }
                    
                    # Note: This is a lower-level approach and may need adjustment
                    print(f"   REST API approach would require manual HTTP calls")
                    print(f"   This method needs manual implementation")
                    
                except Exception as e3:
                    print(f"   ❌ Method 3 setup failed: {e3}")
                
                print(f"\n❌ All automatic methods failed.")
                print(f"💡 Recommended next steps:")
                print(f"   1. Go to Azure AI Foundry: https://ai.azure.com")
                print(f"   2. Find your project: proj-fwcesjjk2tcxa")
                print(f"   3. Navigate to Management → Connections")
                print(f"   4. Click 'New connection'")
                print(f"   5. Select 'Custom' or 'API Key' connection type")
                print(f"   6. Fill in:")
                print(f"      - Name: {connection_name}")
                print(f"      - Target: https://api.bing.microsoft.com/")
                print(f"      - API Key: {bing_api_key[:10]}...")
                
    except Exception as e:
        print(f"❌ Error connecting to AI Foundry project: {e}")

async def check_sdk_methods():
    """Check what connection methods are available in the SDK"""
    print("🔍 Checking available SDK methods...")
    
    try:
        from azure.ai.projects.aio import AIProjectClient
        from azure.ai.projects.models import ConnectionType
        
        print(f"✅ Azure AI Projects SDK imported successfully")
        
        # Check available connection types
        connection_types = [attr for attr in dir(ConnectionType) if not attr.startswith('_')]
        print(f"� Available connection types: {connection_types}")
        
        # Check AIProjectClient methods
        client_methods = [method for method in dir(AIProjectClient) if 'connection' in method.lower()]
        print(f"🔧 Connection-related methods: {client_methods}")
        
    except ImportError as e:
        print(f"❌ SDK import failed: {e}")

if __name__ == "__main__":
    print("🚀 Azure AI Foundry Bing Connection Creator")
    print("=" * 50)
    
    choice = input("Choose option:\n1. Check SDK capabilities\n2. Create Bing connection\nEnter (1 or 2): ").strip()
    
    if choice == "1":
        asyncio.run(check_sdk_methods())
    elif choice == "2":
        asyncio.run(create_bing_connection())
    else:
        print("Invalid choice. Please run again and choose 1 or 2.")
