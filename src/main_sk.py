# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

import asyncio
import logging
import os
import contextlib
from typing import AsyncGenerator, Dict, Optional

import fastapi
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

from logging_config import configure_logging

load_dotenv()

# Global variables for the hybrid system - import from gunicorn_sk_conf
# (Will be imported after initialization)
kernel = None
internal_plugin = None
chat_service = None
ai_project_client = None
agent = None

# Thread tracking for agent conversations
chat_threads: Dict[str, str] = {}

def serialize_sse_event(data: Dict) -> str:
    """Serialize data as Server-Sent Event"""
    import json
    return f"data: {json.dumps(data)}\n\n"

# Models for request/response
class Message(BaseModel):
    message: str
    session_state: dict = {}

class ChatResponse(BaseModel):
    message: str
    annotations: list = []

enable_trace = False
logger = configure_logging(os.getenv("APP_LOG_FILE", ""))

@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the hybrid system on startup"""
    global kernel, internal_plugin, chat_service, ai_project_client, agent
    
    try:
        # Import the hybrid initialization from gunicorn_sk_conf
        from gunicorn_sk_conf import initialize_resources
        
        # Initialize the hybrid system (this sets globals in gunicorn_sk_conf)
        await initialize_resources()
        
        # Import the initialized globals from gunicorn_sk_conf
        import gunicorn_sk_conf
        kernel = gunicorn_sk_conf.kernel
        internal_plugin = gunicorn_sk_conf.internal_plugin
        chat_service = gunicorn_sk_conf.chat_service
        ai_project_client = gunicorn_sk_conf.ai_project_client
        agent = gunicorn_sk_conf.agent
        
        logger.info("FastAPI startup: Hybrid system initialization complete")
        logger.info(f"FastAPI startup: Agent ID: {getattr(agent, 'id', None) if agent else None}")
            
    except Exception as e:
        logger.error(f"FastAPI startup error: {e}")
        # Continue without hybrid system - will use fallbacks
    
    yield
    
    # Cleanup on shutdown
    logger.info("FastAPI shutdown: Cleaning up resources")

# Create FastAPI app
app = FastAPI(lifespan=lifespan)

# Authentication dependency placeholder 
auth_dependency = None

# Mount static files
app.mount("/static", StaticFiles(directory="api/static", html=True), name="static")

@app.get("/health")
async def health():
    """Health check endpoint"""
    global agent, ai_project_client, kernel, internal_plugin, chat_service
    
    return JSONResponse(content={
        "status": "healthy",
        "framework": "hybrid_sk_plus_azure_ai_projects",
        "agent_id": getattr(agent, 'id', None) if agent else None,
        "ai_project_client_enabled": ai_project_client is not None,
        "bing_grounding_enabled": agent is not None,
        "internal_knowledge_enabled": internal_plugin is not None,
        "semantic_kernel_enabled": kernel is not None,
        "chat_service_enabled": chat_service is not None
    })

@app.get("/internal-knowledge")  
async def internal_knowledge(request: Request, _ = auth_dependency):
    """Internal knowledge endpoint"""
    global internal_plugin
    
    if not internal_plugin:
        raise HTTPException(status_code=503, detail="Internal knowledge plugin not available")
    
    return JSONResponse(content={
        "status": "available",
        "plugin_name": "internal_knowledge",
        "description": "Access to banking policies, procedures, and product information"
    })

@app.get("/")
async def index(request: Request):
    """Serve the main page"""
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="api/templates")
    return templates.TemplateResponse(
        "index.html", 
        {"request": request}
    )


@app.get("/agent")
async def get_chat_agent(request: Request, _ = auth_dependency):
    """Get agent information"""
    global agent, internal_plugin
    if agent:
        return JSONResponse(content={
            "id": agent.id,
            "name": getattr(agent, 'name', 'Hybrid Outdoor Gear Assistant'),
            "model": os.environ.get("AZURE_AI_AGENT_DEPLOYMENT_NAME", "gpt-4o-mini"),
            "instructions": getattr(agent, 'instructions', 'Outdoor gear and camping assistant with web search and internal product knowledge capabilities'),
            "type": "hybrid_azure_ai_agent",
            "tools": ["bing_grounding", "internal_knowledge"] if agent and internal_plugin else ["bing_grounding"] if agent else []
        })
    else:
        raise HTTPException(status_code=500, detail="Hybrid Azure AI Agent not initialized")


@app.get("/chat/history")
async def history(request: Request, _ = auth_dependency):
    """Get chat history"""
    # For now, return empty history as Azure AI Agent manages conversation state
    return JSONResponse(content=[])


async def stream_agent_response(user_message: str, thread_id: str = None) -> AsyncGenerator[str, None]:
    """Stream response from hybrid system (SK plugins + Azure AI Projects agents)"""
    global ai_project_client, agent, kernel, internal_plugin, chat_service
    
    try:
        # Create or get thread ID
        if not thread_id:
            thread_id = f"thread_{int(asyncio.get_event_loop().time())}"
        
        logger.info(f"sk: Processing hybrid message: {user_message} (Thread: {thread_id})")
        
        # Initialize response collection
        responses = []
        internal_response = None
        agent_response = None
        
        # Step 1: Try internal knowledge plugin first (if available)
        if internal_plugin and kernel:
            try:
                # Only search internal knowledge for relevant queries (not weather/news/current events)
                external_info_keywords = ["weather", "temperature", "forecast", "news", "current", "today", "now", "latest", "recent", "stock", "price", "market"]
                is_external_query = any(keyword in user_message.lower() for keyword in external_info_keywords)
                
                logger.info(f"sk: Query analysis - External keywords found: {[k for k in external_info_keywords if k in user_message.lower()]}")
                logger.info(f"sk: Is external query: {is_external_query}")
                
                if not is_external_query:
                    # Use semantic kernel for internal knowledge 
                    logger.info("sk: Searching internal knowledge for product/policy query")
                    internal_context = internal_plugin.search_internal_knowledge(user_message)
                    if internal_context and "not found" not in internal_context.lower():
                        internal_response = internal_context
                        logger.info("sk: ✅ Got internal knowledge response")
                else:
                    logger.info("sk: Skipping internal knowledge for external info query")
            except Exception as e:
                logger.warning(f"sk: Internal knowledge error: {e}")
        
        # Step 2: Try Azure AI Projects agent for web search/current info or when internal knowledge didn't help
        needs_web_search = any(keyword in user_message.lower() for keyword in 
                              ["weather", "current", "today", "now", "latest", "recent", "news", "stock", "price", "forecast", "temperature"])
        
        if agent and ai_project_client and (needs_web_search or not internal_response):
            try:
                logger.info("sk: Attempting to use Azure AI Projects agent")
                
                # Prepare the message for the agent
                enhanced_message = user_message
                if internal_response and "not found" not in internal_response.lower():
                    enhanced_message = f"""User question: {user_message}

I have relevant internal outdoor gear information:
{internal_response}

Please provide a comprehensive answer. If you need current web information, use your Bing search capability and include citations. Combine both internal and web information appropriately."""
                else:
                    # For external queries like weather, be very explicit about using Bing search
                    enhanced_message = f"""User question: {user_message}

You have access to a Bing search tool. Please use it to search for current information to answer this question. Do not say you cannot provide real-time information - instead, use your Bing search capability to find the most up-to-date information and provide it to the user with proper citations.

IMPORTANT: Use the Bing search tool to get current, real-time information for this query."""
                
                
                # Use create_thread_and_run instead of separate steps
                logger.info("sk: Using create_thread_and_run for simpler API call")
                
                run_result = ai_project_client.agents.create_thread_and_run(
                    agent_id=agent.id,
                    thread={
                        "messages": [
                            {
                                "role": "user", 
                                "content": enhanced_message
                            }
                        ]
                    }
                )
                logger.info(f"sk: Created thread and run: {run_result.id}")
                
                # Wait for completion properly by checking run status
                import time
                max_wait_time = 30  # 30 seconds max wait for Bing search
                wait_interval = 2   # Check every 2 seconds
                elapsed_time = 0
                
                while elapsed_time < max_wait_time:
                    try:
                        # Check run status using the correct API call
                        current_run = ai_project_client.agents.runs.get(
                            thread_id=run_result.thread_id, 
                            run_id=run_result.id
                        )
                        logger.info(f"sk: Run status: {current_run.status}")
                        
                        if current_run.status in ["completed", "failed", "expired", "cancelled"]:
                            logger.info(f"sk: Run finished with status: {current_run.status}")
                            break
                            
                        time.sleep(wait_interval)
                        elapsed_time += wait_interval
                        
                    except Exception as status_error:
                        logger.warning(f"sk: Error checking run status: {status_error}")
                        # If status checking fails, just wait a bit and continue
                        time.sleep(wait_interval)
                        elapsed_time += wait_interval
                        break
                
                if elapsed_time >= max_wait_time:
                    logger.warning("sk: Run did not complete within timeout period")
                
                # Get messages from the thread with better error handling
                try:
                    messages = ai_project_client.agents.messages.list(thread_id=run_result.thread_id)
                    logger.info(f"sk: Retrieved messages object: {type(messages)}")
                    
                    # Convert iterator to list since messages.list() returns ItemPaged iterator
                    messages_list = list(messages)
                    logger.info(f"sk: Messages list length: {len(messages_list)}")
                    
                    # Extract the latest assistant message
                    if messages_list:
                        logger.info(f"sk: Processing {len(messages_list)} messages")
                        for i, message in enumerate(messages_list):
                            logger.info(f"sk: Message {i}: role={getattr(message, 'role', 'unknown')}")
                            if message.role == "assistant" and message.content:
                                logger.info(f"sk: Found assistant message with {len(message.content)} content items")
                                for j, content_item in enumerate(message.content):
                                    logger.info(f"sk: Content item {j}: type={type(content_item)}")
                                    if hasattr(content_item, 'text') and content_item.text:
                                        agent_response = content_item.text.value
                                        logger.info(f"sk: Extracted response: {len(agent_response)} chars")
                                        break
                                if agent_response:
                                    break
                    else:
                        logger.warning("sk: No messages found in the thread")
                        
                except Exception as msg_error:
                    logger.error(f"sk: Error retrieving messages: {msg_error}")
                    messages_list = []
                
                if agent_response:
                    responses.append(f"**AI Assistant with Bing:** {agent_response}")
                    logger.info("sk: ✅ Got agent response with Bing search")
                else:
                    logger.warning("sk: Agent executed but no response content found")
                    
            except Exception as e:
                logger.error(f"sk: Error getting agent response: {e}")
                # Continue to fallback options
        
        # Step 3: If we have internal knowledge response, use it
        if internal_response and not responses:
            responses.append(f"**Internal Knowledge:** {internal_response}")
            logger.info("sk: ✅ Using internal knowledge response")
        
        # Step 4: Fallback to Semantic Kernel chat if available
        if not responses and chat_service and kernel:
            try:
                logger.info("sk: Using SK chat service for response")
                # Note: This would normally use SK's chat completion
                # For now, we'll skip since we don't have working Azure OpenAI auth
                pass
                    
            except Exception as e:
                logger.error(f"sk: SK chat service failed: {e}")
        
        # Step 5: Final fallback - helpful outdoor gear assistant response
        if not responses:
            fallback_response = """Hello! I'm your outdoor gear assistant. I'm currently operating with limited capabilities, but I can still help you with:

• Information about camping equipment and outdoor gear
• Product details about tents, backpacks, hiking boots, and camping supplies
• General outdoor activity guidance and tips
• Equipment recommendations based on your needs

For weather information, current news, or other external information, I may need my web search capabilities to be working properly.

What outdoor gear or camping questions can I help you with?"""
            responses.append(fallback_response)
            logger.info("sk: Using fallback outdoor gear response")
        
        # Combine responses
        final_response = "\n\n".join(responses) if responses else "I apologize, but I'm unable to process your request at the moment."
        
        # Send the complete response at once (no character-by-character streaming)
        logger.info(f"sk: Sending complete response: {len(final_response)} characters")
        yield serialize_sse_event({'content': final_response, 'annotations': [], 'type': "completed_message"})
        logger.info("sk: Sending stream_end event")
        yield serialize_sse_event({'type': "stream_end"})
        
    except Exception as e:
        logger.error(f"sk: Stream error: {e}")
        error_message = "I'm sorry, I couldn't generate a response. Please try again."
        # Send the complete error message at once
        yield serialize_sse_event({'content': error_message, 'annotations': [], 'type': "completed_message"})
        yield serialize_sse_event({'type': "stream_end"})


@app.post("/chat")
async def chat_stream(request: Message, _ = auth_dependency):
    """Stream chat responses from the hybrid system"""
    
    # Log the incoming request
    logger.info(f"sk: Received chat request: {request.message}")
    
    try:
        # Stream the response
        return StreamingResponse(
            stream_agent_response(request.message, request.session_state.get("thread_id")),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive", 
                "Content-Type": "text/event-stream"
            }
        )
        
    except Exception as e:
        logger.error(f"sk: Chat endpoint error: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Failed to process chat request"}
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
