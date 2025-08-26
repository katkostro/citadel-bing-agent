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
from azure.ai.agents.models import ToolConnection, BingGroundingToolDefinition

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
        # Get environment variables
        project_connection_string = os.environ.get("AZURE_AI_PROJECT_CONNECTION_STRING")
        bing_connection_id = os.environ.get("BING_CONNECTION_ID")
        model_deployment = os.environ.get("AZURE_AI_AGENT_DEPLOYMENT_NAME", "gpt-4o-mini")
        
        # Azure OpenAI configuration for SK
        azure_openai_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
        azure_openai_api_key = os.environ.get("AZURE_OPENAI_API_KEY")
        
        logger.info(f"sk: Project Connection String: {'Set' if project_connection_string else 'Not Set'}")
        logger.info(f"sk: Bing Connection ID: {bing_connection_id}")
        logger.info(f"sk: Model Deployment: {model_deployment}")
        logger.info(f"sk: Azure OpenAI Endpoint: {azure_openai_endpoint}")
        
        # Create SK Kernel with internal plugins
        kernel = Kernel()
        
        # Add internal knowledge plugin to kernel
        internal_plugin = InternalKnowledgePlugin()
        kernel.add_plugin(internal_plugin, plugin_name="internal_knowledge")
        logger.info("sk: ✅ Added internal knowledge plugin to kernel")
        
        # Add Azure OpenAI chat service to kernel if available
        if azure_openai_endpoint:
            if azure_openai_api_key:
                chat_service = AzureChatCompletion(
                    deployment_name=model_deployment,
                    endpoint=azure_openai_endpoint,
                    api_key=azure_openai_api_key
                )
            else:
                # Use managed identity
                credential = DefaultAzureCredential(exclude_shared_token_cache_credential=True)
                chat_service = AzureChatCompletion(
                    deployment_name=model_deployment,
                    endpoint=azure_openai_endpoint,
                    credential=credential
                )
            
            kernel.add_service(chat_service)
            logger.info("sk: ✅ Added Azure OpenAI service to kernel")
        
        # Create Azure AI Projects client for agents with Bing
        if project_connection_string:
            try:
                credential = DefaultAzureCredential(exclude_shared_token_cache_credential=True)
                ai_project_client = AIProjectClient.from_connection_string(
                    credential=credential, 
                    conn_str=project_connection_string
                )
                
                # Create agent with Bing grounding if connection is available
                if bing_connection_id:
                    try:
                        # Create Bing grounding tool
                        bing_tool = BingGroundingToolDefinition()
                        
                        # Create agent
                        agent = ai_project_client.agents.create_agent(
                            model=model_deployment,
                            name="hybrid-banking-assistant",
                            instructions=(
                                "You are a helpful banking assistant with access to real-time web information via Bing search. "
                                "Use Bing grounding for current events, weather, news, stock prices, or any real-time information. "
                                "Always include citations when using web search results. "
                                "For internal banking questions, indicate that internal knowledge is available through separate systems."
                            ),
                            tools=[bing_tool]
                        )
                        
                        logger.info(f"sk: ✅ Created Azure AI agent with Bing: {agent.id}")
                    except Exception as e:
                        logger.error(f"sk: Could not create agent with Bing: {e}")
                        # Try to create agent without Bing
                        agent = ai_project_client.agents.create_agent(
                            model=model_deployment,
                            name="banking-assistant-no-bing",
                            instructions="You are a helpful banking assistant. Provide helpful responses based on your training knowledge."
                        )
                        logger.info(f"sk: ✅ Created Azure AI agent without Bing: {agent.id}")
                else:
                    logger.warning("sk: No Bing connection ID - creating agent without web search")
                    agent = ai_project_client.agents.create_agent(
                        model=model_deployment,
                        name="banking-assistant-no-bing",
                        instructions="You are a helpful banking assistant. Provide helpful responses based on your training knowledge."
                    )
                    logger.info(f"sk: ✅ Created Azure AI agent without Bing: {agent.id}")
                    
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
