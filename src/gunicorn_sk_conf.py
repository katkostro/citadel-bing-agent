# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license.
# See LICENSE file in the project root for full license information.

import asyncio
import logging
import multiprocessing
import os
from typing import Optional

# Semantic Kernel imports for plugins and chat
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from azure.ai.projects import AIProjectClient
from azure.ai.agents.models import BingGroundingTool
from azure.identity import get_bearer_token_provider

# Import the internal knowledge plugin
from plugins.internal_knowledge_plugin import InternalKnowledgePlugin

from azure.identity.aio import DefaultAzureCredential
from dotenv import load_dotenv
from logging_config import configure_logging

load_dotenv()

logger = configure_logging(os.getenv("APP_LOG_FILE", ""))

# Global variables to store both SK and Azure AI components
kernel: Optional[Kernel] = None
chat_service: Optional[AzureChatCompletion] = None
internal_plugin: Optional[InternalKnowledgePlugin] = None
ai_project_client = None
agent = None


async def create_hybrid_system():
    """Create hybrid system with Semantic Kernel plugins + Azure AI Projects agents"""
    global kernel, chat_service, internal_plugin, ai_project_client, agent
    
    try:
        # Get environment variables - using the correct names from infrastructure
        project_connection_string = os.environ.get("AZURE_AI_PROJECT_CONNECTION_STRING")
        project_resource_id = os.environ.get("AZURE_EXISTING_AIPROJECT_RESOURCE_ID")
        project_endpoint = os.environ.get("AZURE_EXISTING_AIPROJECT_ENDPOINT")
        bing_connection_id = os.environ.get("BING_CONNECTION_ID")
        bing_connection_name = os.environ.get("BING_CONNECTION_NAME", "bing-search-connection")  # Default from infra
        bing_search_endpoint = os.environ.get("BING_SEARCH_ENDPOINT")
        model_deployment = os.environ.get("AZURE_AI_AGENT_DEPLOYMENT_NAME", "gpt-4o-mini")
        
        # Azure OpenAI configuration for SK - try different possible variable names
        azure_openai_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT") or project_endpoint
        azure_openai_api_key = os.environ.get("AZURE_OPENAI_API_KEY")
        
        logger.info(f"sk: Project Connection String: {'Set' if project_connection_string else 'Not Set'}")
        logger.info(f"sk: Project Resource ID: {'Set' if project_resource_id else 'Not Set'}")
        logger.info(f"sk: Project Endpoint: {project_endpoint}")
        logger.info(f"sk: Bing Connection ID: {bing_connection_id}")
        logger.info(f"sk: Bing Connection Name: {bing_connection_name}")
        logger.info(f"sk: Bing Search Endpoint: {'Set' if bing_search_endpoint else 'Not Set'}")
        logger.info(f"sk: Model Deployment: {model_deployment}")
        logger.info(f"sk: Azure OpenAI Endpoint: {azure_openai_endpoint}")
        
        # Debug logging for environment variables
        logger.info(f"sk: DEBUG - All Bing vars - ID: {bing_connection_id}, Name: {bing_connection_name}, Endpoint: {bing_search_endpoint}")
        logger.info(f"sk: DEBUG - Connection check: {bool(bing_connection_id or bing_connection_name or bing_search_endpoint)}")
        
        # Create SK Kernel with internal plugins
        kernel = Kernel()
        
        # Add internal knowledge plugin to kernel
        internal_plugin = InternalKnowledgePlugin()
        kernel.add_plugin(internal_plugin, plugin_name="internal_knowledge")
        logger.info("sk: ✅ Added internal knowledge plugin to kernel")
        
        # Add Azure OpenAI chat service to kernel if available
        if azure_openai_endpoint:
            try:
                if azure_openai_api_key:
                    chat_service = AzureChatCompletion(
                        deployment_name=model_deployment,
                        endpoint=azure_openai_endpoint,
                        api_key=azure_openai_api_key
                    )
                else:
                    # Use managed identity for Container Apps with correct scope
                    from azure.identity import DefaultAzureCredential
                    # Container Apps need specific credential configuration
                    credential = DefaultAzureCredential(
                        exclude_environment_credential=True,
                        exclude_shared_token_cache_credential=True,
                        exclude_visual_studio_code_credential=True,
                        exclude_cli_credential=True,
                        exclude_powershell_credential=True,
                        exclude_interactive_browser_credential=True
                    )
                    chat_service = AzureChatCompletion(
                        deployment_name=model_deployment,
                        endpoint=azure_openai_endpoint,
                        azure_ad_token_provider=get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")
                    )
                
                kernel.add_service(chat_service)
                logger.info("sk: ✅ Added Azure OpenAI service to kernel")
            except Exception as e:
                logger.warning(f"sk: Could not add Azure OpenAI to kernel: {e}")
                logger.info("sk: Continuing without Azure OpenAI for internal plugins")
        
        # Create Azure AI Projects client for agents with Bing
        if project_connection_string or project_endpoint:
            try:
                # Use explicit credential configuration for Azure AI Projects
                from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
                
                # Try managed identity first, then default credential for Container Apps
                try:
                    # Container Apps managed identity configuration
                    from azure.identity import DefaultAzureCredential
                    credential = DefaultAzureCredential(
                        exclude_environment_credential=True,
                        exclude_shared_token_cache_credential=True,
                        exclude_visual_studio_code_credential=True,
                        exclude_cli_credential=True,
                        exclude_powershell_credential=True,
                        exclude_interactive_browser_credential=True
                    )
                    logger.info("sk: Using Container Apps DefaultAzureCredential for AI Projects")
                except Exception as e:
                    logger.warning(f"sk: Container Apps credential failed: {e}")
                    from azure.identity import ManagedIdentityCredential
                    credential = ManagedIdentityCredential()
                    logger.info("sk: Using ManagedIdentityCredential for AI Projects")
                
                # Try different methods to create AI Project client
                if project_connection_string:
                    ai_project_client = AIProjectClient.from_connection_string(
                        credential=credential, 
                        conn_str=project_connection_string
                    )
                    logger.info("sk: ✅ Created AI Project client from connection string")
                elif project_endpoint:
                    ai_project_client = AIProjectClient(
                        endpoint=project_endpoint,
                        credential=credential
                    )
                    logger.info("sk: ✅ Created AI Project client from endpoint")
                
                # Create agent with Bing grounding if search is available
                if bing_connection_id or bing_connection_name or bing_search_endpoint:
                    try:
                        logger.info(f"sk: 🔍 Attempting to create agent with Bing search")
                        logger.info(f"sk: - Connection ID: {'Yes' if bing_connection_id else 'No'} ({len(bing_connection_id or '') if bing_connection_id else 0} chars)")
                        logger.info(f"sk: - Connection Name: {bing_connection_name}")
                        logger.info(f"sk: - Search Endpoint: {'Yes' if bing_search_endpoint else 'No'}")
                        
                        # Get the Bing connection using the connection name
                        bing_grounding = None
                        if bing_connection_name:
                            # Use the connection name to get the connection from the AI Project
                            try:
                                logger.info(f"sk: 📡 Getting Bing connection by name: {bing_connection_name}")
                                
                                # Try different approaches to get the connection
                                bing_connection = None
                                try:
                                    # Method 1: Try by connection name
                                    bing_connection = ai_project_client.connections.get(connection_name=bing_connection_name)
                                    logger.info(f"sk: ✅ Found connection via name: {bing_connection.id}")
                                except Exception as e1:
                                    logger.warning(f"sk: ⚠️ Method 1 (by name) failed: {e1}")
                                    
                                    # Method 2: Try listing all connections and find by name
                                    try:
                                        logger.info("sk: 📋 Listing all connections to find Bing connection...")
                                        connections = ai_project_client.connections.list()
                                        for conn in connections:
                                            logger.info(f"sk: - Found connection: {conn.name} (id: {conn.id})")
                                            if conn.name == bing_connection_name:
                                                bing_connection = conn
                                                logger.info(f"sk: ✅ Found connection via list: {bing_connection.id}")
                                                break
                                        if not bing_connection:
                                            logger.error(f"sk: ❌ Connection '{bing_connection_name}' not found in list")
                                    except Exception as e2:
                                        logger.error(f"sk: ❌ Method 2 (list) also failed: {e2}")
                                
                                if bing_connection:
                                    # Create Bing grounding tool with the connection ID from the project
                                    bing_grounding = BingGroundingTool(connection_id=bing_connection.id)
                                    logger.info(f"sk: ✅ Created Bing grounding tool with project connection")
                                else:
                                    logger.error(f"sk: ❌ Could not retrieve connection '{bing_connection_name}' by any method")
                                
                            except Exception as conn_e:
                                logger.error(f"sk: ❌ Failed to get project connection '{bing_connection_name}': {conn_e}")
                                logger.error(f"sk: ❌ Connection error type: {type(conn_e).__name__}")
                                bing_grounding = None
                        else:
                            logger.warning("sk: ⚠️ No Bing connection name available")
                        
                        if bing_grounding:
                            # Create agent with Bing grounding tool
                            agent = ai_project_client.agents.create_agent(
                                model=model_deployment,
                                name="hybrid-outdoor-assistant",
                                instructions=(
                                    "You are a helpful outdoor gear assistant with access to real-time web information via Bing search. "
                                    "IMPORTANT: When users ask about current events, weather, news, stock prices, or any real-time information, "
                                    "you MUST use your Bing search tools to get the latest information from the internet. "
                                    "Do not say you cannot access the internet - you have Bing search capabilities. "
                                    "Always search for current information when requested and include citations/sources. "
                                    "For product and gear questions, internal knowledge is available through separate systems."
                                ),
                                tools=bing_grounding.definitions
                            )
                            logger.info(f"sk: ✅ Successfully created Azure AI agent with Bing search: {agent.id}")
                        else:
                            raise Exception("Could not create Bing grounding tool")
                            
                    except Exception as e:
                        logger.error(f"sk: ❌ Failed to create agent with Bing: {str(e)}")
                        logger.error(f"sk: ❌ Exception type: {type(e).__name__}")
                        # Try to create agent without Bing
                        try:
                            agent = ai_project_client.agents.create_agent(
                                model=model_deployment,
                                name="outdoor-assistant-no-bing",
                                instructions="You are a helpful outdoor gear assistant. Provide helpful responses based on your training knowledge."
                            )
                            logger.info(f"sk: ✅ Created Azure AI agent without Bing: {agent.id}")
                        except Exception as e2:
                            logger.error(f"sk: ❌ Could not create agent at all: {e2}")
                            agent = None
                else:
                    logger.warning("sk: No Bing connection - creating agent without web search")
                    try:
                        agent = ai_project_client.agents.create_agent(
                            model=model_deployment,
                            name="banking-assistant-no-bing",
                            instructions="You are a helpful banking assistant. Provide helpful responses based on your training knowledge."
                        )
                        logger.info(f"sk: ✅ Created Azure AI agent without Bing: {agent.id}")
                    except Exception as e:
                        logger.error(f"sk: Could not create agent: {e}")
                        agent = None
                    
            except Exception as e:
                logger.error(f"sk: Could not create AI Project client: {e}")
                ai_project_client = None
                agent = None
        
        logger.info("sk: ✅ Hybrid system initialized successfully")
        logger.info(f"sk: - Semantic Kernel: {'✅' if kernel else '❌'}")
        logger.info(f"sk: - Internal Plugin: {'✅' if internal_plugin else '❌'}")  
        logger.info(f"sk: - Chat Service: {'✅' if chat_service else '❌'}")
        logger.info(f"sk: - AI Project Client: {'✅' if ai_project_client else '❌'}")
        logger.info(f"sk: - Agent with Bing: {'✅' if agent else '❌'}")
        
        return kernel
        
    except Exception as e:
        logger.error(f"sk: Error creating hybrid system: {e}", exc_info=True)
        raise RuntimeError(f"Failed to create hybrid system: {e}")


async def initialize_resources():
    """Initialize hybrid resources"""
    global kernel
    
    try:
        logger.info("sk: Initializing hybrid Semantic Kernel + Azure AI Projects system")
        kernel = await create_hybrid_system()
        logger.info("sk: Successfully initialized hybrid system")
        
    except Exception as e:
        logger.error(f"sk: Error initializing resources: {e}", exc_info=True)
        raise RuntimeError(f"Failed to initialize resources: {e}")


def on_starting(server):
    """This code runs once before the workers will start."""
    asyncio.get_event_loop().run_until_complete(initialize_resources())


# Gunicorn configuration
max_requests = 1000
max_requests_jitter = 50
log_file = "-"
bind = "0.0.0.0:50505"

if not os.getenv("RUNNING_IN_PRODUCTION"):
    reload = True

# Load application code before the worker processes are forked.
preload_app = True
num_cpus = multiprocessing.cpu_count()
workers = (num_cpus * 2) + 1
worker_class = "uvicorn.workers.UvicornWorker"

timeout = 120

if __name__ == "__main__":
    print("Running initialize_resources directly...")
    asyncio.run(initialize_resources())
    print("initialize_resources finished.")
