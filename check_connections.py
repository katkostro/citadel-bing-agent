#!/usr/bin/env python3
"""
Script to list existing connections in your Azure AI Foundry project
"""

import os
import asyncio
from azure.ai.projects.aio import AIProjectClient
from azure.identity.aio import DefaultAzureCredential
from dotenv import load_dotenv

async def list_project_connections():
    """List all connections in the Azure AI Foundry project"""
    
    # Get project endpoint from environment
    project_endpoint = os.getenv('AZURE_EXISTING_AIPROJECT_ENDPOINT')
    if not project_endpoint:
        print("Error: AZURE_EXISTING_AIPROJECT_ENDPOINT not found in environment")
        return
    
    try:
        async with DefaultAzureCredential(exclude_shared_token_cache_credential=True) as credential:
            async with AIProjectClient(
                credential=credential,
                endpoint=project_endpoint
            ) as ai_project:
                
                print(f"📁 Connected to Azure AI Foundry project: {project_endpoint}")
                print("\n🔗 Existing connections:")
                print("-" * 50)
                
                connections_list = []
                async for connection in ai_project.connections.list():
                    connections_list.append(connection)
                
                if not connections_list:
                    print("   No connections found")
                else:
                    for conn in connections_list:
                        connection_type = getattr(conn, 'connection_type', getattr(conn, 'type', 'unknown'))
                        print(f"   📌 Name: {conn.name}")
                        print(f"      ID: {conn.id}")
                        print(f"      Type: {connection_type}")
                        if hasattr(conn, 'target'):
                            print(f"      Target: {conn.target}")
                        print()
                
                # Check if any Bing connections exist
                bing_connections = [c for c in connections_list if 'bing' in str(getattr(c, 'connection_type', '')).lower() or 'bing' in c.name.lower()]
                
                if bing_connections:
                    print("✅ Found existing Bing connections!")
                    for conn in bing_connections:
                        print(f"   🔍 Bing connection: {conn.name} (ID: {conn.id})")
                else:
                    print("❌ No Bing connections found")
                    print("\n💡 To add Bing search capability:")
                    print("   1. Go to https://ai.azure.com")
                    print("   2. Select your project")
                    print("   3. Navigate to Management → Connections")
                    print("   4. Create a new Bing Search connection")
                    
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    # Load environment variables
    load_dotenv()
    
    asyncio.run(list_project_connections())
