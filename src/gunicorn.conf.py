# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license.
# See LICENSE file in the project root for full license information.
from typing import Dict, List

import asyncio
import csv
import json
import logging
import multiprocessing
import os
import sys

# Semantic Kernel imports
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.azure_ai_agent import AzureAIAgentService
from semantic_kernel.connectors.ai.azure_ai_agent.models import BingGroundingToolDefinition
from semantic_kernel.connectors.ai.azure_openai import AzureOpenAIChatCompletion
from azure.identity.aio import DefaultAzureCredential
from azure.core.credentials_async import AsyncTokenCredential

from dotenv import load_dotenv

from logging_config import configure_logging

load_dotenv()

logger = configure_logging(os.getenv("APP_LOG_FILE", ""))


agentID = os.environ.get("AZURE_EXISTING_AGENT_ID") if os.environ.get(
    "AZURE_EXISTING_AGENT_ID") else os.environ.get(
        "AZURE_AI_AGENT_ID")
    
proj_endpoint = os.environ.get("AZURE_EXISTING_AIPROJECT_ENDPOINT")

def list_files_in_files_directory() -> List[str]:    
    # Get the absolute path of the 'files' directory
    files_directory = os.path.abspath(os.path.join(os.path.dirname(__file__), 'files'))
    
    # List all files in the 'files' directory
    files = [f for f in os.listdir(files_directory) if os.path.isfile(os.path.join(files_directory, f))]
    
    return files

FILES_NAMES = list_files_in_files_directory()


async def create_index_maybe(
        ai_client: AIProjectClient, creds: AsyncTokenCredential) -> None:
    """
    Create the index and upload documents if the index does not exist.

    This code is executed only once, when called on_starting hook is being
    called. This code ensures that the index is being populated only once.
    rag.create_index return True if the index was created, meaning that this
    docker node have started first and must populate index.

    :param ai_client: The project client to be used to create an index.
    :param creds: The credentials, used for the index.
    """
    from api.search_index_manager import SearchIndexManager
    endpoint = os.environ.get('AZURE_AI_SEARCH_ENDPOINT')
    embedding = os.getenv('AZURE_AI_EMBED_DEPLOYMENT_NAME')    
    if endpoint and embedding:
        try:
            aoai_connection = await ai_client.connections.get_default(
                connection_type=ConnectionType.AZURE_OPEN_AI, include_credentials=True)
        except ValueError as e:
            logger.error("Error creating index: {e}")
            return
        
        embed_api_key = None
        if aoai_connection.credentials and isinstance(aoai_connection.credentials, ApiKeyCredentials):
            embed_api_key = aoai_connection.credentials.api_key

        search_mgr = SearchIndexManager(
            endpoint=endpoint,
            credential=creds,
            index_name=os.getenv('AZURE_AI_SEARCH_INDEX_NAME'),
            dimensions=None,
            model=embedding,
            deployment_name=embedding,
            embedding_endpoint=aoai_connection.target,
            embed_api_key=embed_api_key
        )
        # If another application instance already have created the index,
        # do not upload the documents.
        if await search_mgr.create_index(
            vector_index_dimensions=int(
                os.getenv('AZURE_AI_EMBED_DIMENSIONS'))):
            embeddings_path = os.path.join(
                os.path.dirname(__file__), 'data', 'embeddings.csv')

            assert embeddings_path, f'File {embeddings_path} not found.'
            await search_mgr.upload_documents(embeddings_path)
            await search_mgr.close()


def _get_file_path(file_name: str) -> str:
    """
    Get absolute file path.

    :param file_name: The file name.
    """
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__),
                     'files',
                     file_name))


async def get_available_tool(
        project_client: AIProjectClient,
        creds: AsyncTokenCredential) -> tuple[list[Tool], bool]:
    """
    Get the toolset and tool definitions for the agent.

    :param ai_client: The project client to be used to create an index.
    :param creds: The credentials, used for the index.
    :return: Tuple of (List of tools available based on the environment, boolean indicating if Bing tool was added)
    """
    import os
    tools = []
    
    # File name -> {"id": file_id, "path": file_path}
    file_ids: List[str] = []
    # First try to get an index search.
    conn_id = ""
    if os.environ.get('AZURE_AI_SEARCH_INDEX_NAME'):
        conn_list = project_client.connections.list()
        async for conn in conn_list:
            if conn.type == ConnectionType.AZURE_AI_SEARCH:
                conn_id = conn.id
                break

    if conn_id:
        await create_index_maybe(project_client, creds)
        tools.append(AzureAISearchTool(
            index_connection_id=conn_id,
            index_name=os.environ.get('AZURE_AI_SEARCH_INDEX_NAME')))
    else:
        logger.info(
            "agent: index was not initialized, falling back to file search.")
        
        # Upload files for file search
        for file_name in FILES_NAMES:
            file_path = _get_file_path(file_name)
            file = await project_client.agents.files.upload_and_poll(
                file_path=file_path, purpose=FilePurpose.AGENTS)
            # Store both file id and the file path using the file name as key.
            file_ids.append(file.id)

        # Create the vector store using the file IDs.
        vector_store = await project_client.agents.vector_stores.create_and_poll(
            file_ids=file_ids,
            name="sample_store"
        )
        logger.info("agent: file store and vector store success")
        tools.append(FileSearchTool(vector_store_ids=[vector_store.id]))

    # Add Bing Grounding tool using Semantic Kernel
    bing_tool_added = False
    try:
        # Check if there are any Bing connections available
        connections_list = []
        async for connection in project_client.connections.list():
            connections_list.append(connection)
        
        # Look for Bing connection
        bing_connection = None
        for conn in connections_list:
            conn_name = str(getattr(conn, 'name', ''))
            if ('bing' in conn_name.lower() or conn_name == 'bing-search-connection'):
                bing_connection = conn
                break
        
        if bing_connection:
            logger.info(f"agent: Found Bing connection: {bing_connection.name} (ID: {bing_connection.id})")
            
            # Try using Semantic Kernel's BingGroundingToolDefinition
            try:
                from semantic_kernel.connectors.ai.azure_ai_agent.models import BingGroundingToolDefinition
                
                # Create Bing grounding tool using Semantic Kernel approach
                bing_grounding_tool = BingGroundingToolDefinition(
                    connection_list=[{"id": bing_connection.id}]
                )
                tools.append(bing_grounding_tool)
                logger.info("agent: Successfully added Semantic Kernel BingGroundingToolDefinition")
                bing_tool_added = True
                
            except ImportError as e1:
                logger.warning(f"agent: Semantic Kernel BingGroundingToolDefinition not available: {e1}")
                # Fall back to custom function approach
                logger.info("agent: Falling back to custom Bing search function")
                
                # Create custom Bing search function tool
                async def search_web(query: str) -> str:
                    """Search the web for current information using Bing Search API.
                    
                    Args:
                        query: The search query to find current information about
                        
                    Returns:
                        Search results with current information
                    """
                    try:
                        import aiohttp
                        import json
                        
                        # Get Bing API key from environment
                        bing_api_key = os.getenv('BING_SEARCH_API_KEY')
                        if not bing_api_key:
                            return "Bing Search API key not configured"
                        
                        bing_endpoint = os.getenv('BING_SEARCH_ENDPOINT', 'https://api.bing.microsoft.com/') 
                        search_url = f"{bing_endpoint.rstrip('/')}/v7.0/search"
                        
                        headers = {
                            'Ocp-Apim-Subscription-Key': bing_api_key,
                            'Content-Type': 'application/json'
                        }
                        
                        params = {
                            'q': query,
                            'count': 5,
                            'offset': 0,
                            'mkt': 'en-US',
                            'safesearch': 'Moderate'
                        }
                        
                        async with aiohttp.ClientSession() as session:
                            async with session.get(search_url, headers=headers, params=params) as response:
                                if response.status == 200:
                                    data = await response.json()
                                    
                                    results = []
                                    if 'webPages' in data and 'value' in data['webPages']:
                                        for item in data['webPages']['value'][:3]:
                                            results.append({
                                                'title': item.get('name', ''),
                                                'snippet': item.get('snippet', ''),
                                                'url': item.get('url', '')
                                            })
                                    
                                    if results:
                                        formatted_results = []
                                        for r in results:
                                            formatted_results.append(f"**{r['title']}**\n{r['snippet']}\nSource: {r['url']}\n")
                                        return "Here are the current search results:\n\n" + "\n".join(formatted_results)
                                    else:
                                        return "No search results found for the query."
                                else:
                                    return f"Bing Search API error: HTTP {response.status}"
                                    
                    except Exception as e:
                        logger.error(f"Error in search_web function: {e}")
                        return f"Error performing web search: {str(e)}"
                
                # Create the AsyncFunctionTool as fallback
                search_tool = AsyncFunctionTool(search_web)
                tools.append(search_tool)
                bing_tool_added = True
                logger.info("agent: Successfully added custom Bing search function tool as fallback")
                
            except Exception as e2:
                logger.error(f"agent: Failed to create Semantic Kernel BingGroundingToolDefinition: {e2}")
                logger.warning("agent: Bing grounding functionality unavailable")
            
        else:
            logger.info("agent: No Bing connection found in AI project")
            
    except Exception as e:
        logger.error(f"agent: Failed to initialize Bing search tool: {e}", exc_info=True)
        logger.warning("agent: Continuing without Bing search functionality")
    
    return bing_tool_added

    return tools, bing_tool_added


async def update_existing_agent_with_tools(ai_client: AIProjectClient, agent_id: str, creds: AsyncTokenCredential) -> Agent:
    """Update an existing agent with new tools"""
    logger.info(f"Updating existing agent {agent_id} with tools")
    
    tools, bing_tool_added = await get_available_tool(ai_client, creds)
    toolset = AsyncToolSet()
    
    # Add all tools to the toolset
    for tool in tools:
        toolset.add(tool)
        logger.info(f"agent: Added tool of type: {type(tool).__name__}")
    
    logger.info(f"agent: Total tools added: {len(tools)}")
    
    # Check if we have search tools for enhanced instructions
    has_ai_search = any(isinstance(tool, AzureAISearchTool) for tool in tools)
    has_file_search = any(isinstance(tool, FileSearchTool) for tool in tools)
    # Use the boolean returned from get_available_tool
    has_bing_search = bing_tool_added or any(hasattr(tool, '_func') and 'search_web' in str(tool._func) for tool in tools)

    instructions_parts = ["You are a helpful assistant that helps customers with their banking and financial questions."]
    
    if has_ai_search:
        instructions_parts.append("Use AI Search for knowledge retrieval from the indexed documents.")
    elif has_file_search:
        instructions_parts.append("Use File Search for knowledge retrieval from uploaded files.")
    
    if has_bing_search:
        instructions_parts.append("IMPORTANT: For any questions about current events, weather, news, market data, or real-time information, you have access to web search functionality.")
        instructions_parts.append("Use the search_web function to get current information from the internet.")
        instructions_parts.append("Always use web search for weather, news, stock prices, current events, and real-time data.")
        instructions_parts.append("Never say you cannot provide real-time information - always use the search_web function first.")
        logger.info("agent: Bing search tool detected and web search instructions added")
    else:
        logger.info("agent: No Bing search tool found in available tools")
    
    instructions_parts.append("Always prioritize accuracy and cite your sources appropriately.")
    instructions_parts.append("Be concise and direct.")
    
    instructions = " ".join(instructions_parts)
    
    # Update the existing agent
    agent = await ai_client.agents.update_agent(
        agent_id=agent_id,
        model=os.environ["AZURE_AI_AGENT_DEPLOYMENT_NAME"],
        name=os.environ["AZURE_AI_AGENT_NAME"],
        instructions=instructions,
        toolset=toolset
    )
    logger.info(f"Updated agent {agent_id} with {len(tools)} tools")
    return agent


async def create_agent(ai_client: AIProjectClient,
                       creds: AsyncTokenCredential) -> Agent:
    logger.info("Creating new agent with resources")
    tools, bing_tool_added = await get_available_tool(ai_client, creds)
    toolset = AsyncToolSet()
    
    # Add all tools to the toolset
    for tool in tools:
        toolset.add(tool)
        logger.info(f"agent: Added tool of type: {type(tool).__name__}")
    
    logger.info(f"agent: Total tools added: {len(tools)}")
    
    # Create enhanced instructions based on available tools
    instructions_parts = []
    
    # Check if we have search tools
    has_ai_search = any(isinstance(tool, AzureAISearchTool) for tool in tools)
    has_file_search = any(isinstance(tool, FileSearchTool) for tool in tools)
    # Use the boolean returned from get_available_tool
    has_bing_search = bing_tool_added or any(hasattr(tool, '_func') and 'search_web' in str(tool._func) for tool in tools)
    has_bing_search = any('BingGroundingTool' in str(type(tool)) or 
                         'bing' in str(type(tool)).lower() or
                         'BingGroundingToolDefinition' in str(type(tool)) for tool in tools)
    
    if has_ai_search:
        instructions_parts.append("Use AI Search for knowledge retrieval from the indexed documents.")
    elif has_file_search:
        instructions_parts.append("Use File Search for knowledge retrieval from uploaded files.")
    
    if has_bing_search:
        instructions_parts.append("IMPORTANT: For any questions about current events, weather, news, market data, or real-time information, you have access to web search functionality.")
        instructions_parts.append("Use the search_web function to get current information from the internet.")
        instructions_parts.append("Always use web search for weather, news, stock prices, current events, and real-time data.")
        instructions_parts.append("Never say you cannot provide real-time information - always use the search_web function first.")
        logger.info("agent: Bing grounding tool detected and web search instructions added")
    else:
        logger.info("agent: No Bing grounding tool found in available tools")
    
    instructions_parts.append("Always prioritize accuracy and cite your sources appropriately.")
    instructions_parts.append("Avoid using base knowledge when specific tools are available.")
    
    instructions = " ".join(instructions_parts)
    
    agent = await ai_client.agents.create_agent(
        model=os.environ["AZURE_AI_AGENT_DEPLOYMENT_NAME"],
        name=os.environ["AZURE_AI_AGENT_NAME"],
        instructions=instructions,
        toolset=toolset
    )
    return agent

async def verify_agent_tools(ai_client: AIProjectClient, agent_id: str, creds: AsyncTokenCredential) -> None:
    """Verify presence of bing_web_search tool; attempt one update if missing."""
    try:
        agent = await ai_client.agents.get_agent(agent_id)
        possible_attrs = ["toolset", "tools", "_toolset"]
        tool_names = []
        has_bing = False
        for attr in possible_attrs:
            if hasattr(agent, attr):
                obj = getattr(agent, attr)
                iterable = []
                if isinstance(obj, list):
                    iterable = obj
                elif hasattr(obj, "tools"):
                    iterable = getattr(obj, "tools") or []
                elif hasattr(obj, "__iter__"):
                    try:
                        iterable = list(obj)
                    except Exception:
                        pass
                for t in iterable:
                    name = getattr(t, "name", getattr(t, "_name", type(t).__name__))
                    tool_names.append(name)
                    # Check for Bing grounding tool
                    if name == "bing_grounding" or 'BingGroundingTool' in name or 'bing' in name.lower():
                        has_bing = True
        if tool_names:
            logger.info(f"agent verify: tool names discovered: {tool_names}")
        else:
            logger.info("agent verify: no tools enumerated from agent object")
        if not has_bing:
            logger.warning("agent verify: Bing grounding tool missing; attempting re-update")
            try:
                await update_existing_agent_with_tools(ai_client, agent_id, creds)
            except Exception as e:  # pragma: no cover
                logger.error(f"agent verify: re-update failed: {e}")
        else:
            logger.info("agent verify: Bing grounding tool present")
    except Exception as e:  # pragma: no cover
        logger.error(f"agent verify: failed to verify tools for agent {agent_id}: {e}")


async def initialize_resources():
    try:
        async with DefaultAzureCredential(
                exclude_shared_token_cache_credential=True) as creds:
            async with AIProjectClient(
                credential=creds,
                endpoint=proj_endpoint
            ) as ai_client:
                # If the environment already has AZURE_AI_AGENT_ID or AZURE_EXISTING_AGENT_ID, try
                # updating that agent with tools
                if agentID is not None:
                    try:
                        agent = await ai_client.agents.get_agent(agentID)
                        logger.info(f"Found existing agent by ID: {agent.id}")
                        
                        # Check if we need to update with tools
                        tools, bing_tool_added = await get_available_tool(ai_client, creds)
                        if tools:
                            logger.info(f"Updating agent {agent.id} with {len(tools)} tools")
                            updated_agent = await update_existing_agent_with_tools(ai_client, agent.id, creds)
                            logger.info(f"Successfully updated agent {updated_agent.id} with tools")
                        else:
                            logger.info(f"No tools to add to agent {agent.id}")
                        # Verify tool presence before returning
                        await verify_agent_tools(ai_client, agent.id, creds)
                        return
                    except Exception as e:
                        logger.warning(
                            "Could not retrieve agent by AZURE_EXISTING_AGENT_ID = "
                            f"{agentID}, error: {e}")

                # Check if an agent with the same name already exists
                agent_list = ai_client.agents.list_agents()
                if agent_list:
                    async for agent_object in agent_list:
                        if agent_object.name == os.environ[
                                "AZURE_AI_AGENT_NAME"]:
                            logger.info(
                                "Found existing agent named "
                                f"'{agent_object.name}'"
                                f", ID: {agent_object.id}")
                            
                            # Update the existing agent with tools
                            tools, bing_tool_added = await get_available_tool(ai_client, creds)
                            if tools:
                                logger.info(f"Updating existing agent {agent_object.id} with {len(tools)} tools")
                                updated_agent = await update_existing_agent_with_tools(ai_client, agent_object.id, creds)
                                logger.info(f"Successfully updated agent {updated_agent.id} with tools")
                            # Verify after update
                            await verify_agent_tools(ai_client, agent_object.id, creds)
                            os.environ["AZURE_EXISTING_AGENT_ID"] = agent_object.id
                            return
                        
                # Create a new agent
                logger.info("Creating new agent...")
                agent = await create_agent(ai_client, creds)
                os.environ["AZURE_EXISTING_AGENT_ID"] = agent.id
                logger.info(f"Created agent, agent ID: {agent.id}")
                await verify_agent_tools(ai_client, agent.id, creds)

    except Exception as e:
        logger.error(f"Error creating agent: {e}", exc_info=True)
        raise RuntimeError(f"Failed to create the agent: {e}")


def on_starting(server):
    """This code runs once before the workers will start."""
    asyncio.get_event_loop().run_until_complete(initialize_resources())


max_requests = 1000
max_requests_jitter = 50
log_file = "-"
bind = "0.0.0.0:50505"

if not os.getenv("RUNNING_IN_PRODUCTION"):
    reload = True

# Load application code before the worker processes are forked.
# Needed to execute on_starting.
# Please see the documentation on gunicorn
# https://docs.gunicorn.org/en/stable/settings.html
preload_app = True
num_cpus = multiprocessing.cpu_count()
workers = (num_cpus * 2) + 1
worker_class = "uvicorn.workers.UvicornWorker"

timeout = 120

if __name__ == "__main__":
    print("Running initialize_resources directly...")
    asyncio.run(initialize_resources())
    print("initialize_resources finished.")