# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

import json
import logging
import os
from typing import Dict, List, Optional, Any
import aiohttp
import asyncio
from azure.cognitiveservices.search.websearch import WebSearchClient
from azure.cognitiveservices.search.websearch.models import SafeSearch
from msrest.authentication import CognitiveServicesCredentials

logger = logging.getLogger(__name__)


class BingGroundingTool:
    """
    A tool for performing web searches using Bing Search API and providing grounded information.
    
    Note: This implementation currently uses Bing.Grounding resources which have
    limited API access. The tool will provide helpful guidance when API calls fail.
    """

    def __init__(self, subscription_key: str, endpoint: str = "https://api.bing.microsoft.com/"):
        """
        Initialize the Bing Grounding Tool.
        
        Args:
            subscription_key: Bing Search API subscription key (from Bing.Grounding resource)
            endpoint: Bing Search API endpoint
        """
        self.subscription_key = subscription_key
        self.endpoint = endpoint.rstrip('/')
        logger.info("BingGroundingTool initialized with Bing.Grounding resource - may have limited API access")
        self.client = WebSearchClient(endpoint=endpoint, credentials=CognitiveServicesCredentials(subscription_key))

    async def search_web_async(self, query: str, count: int = 5, market: str = "en-US") -> List[Dict[str, Any]]:
        """
        Perform an async web search using Bing Search API.
        
        Args:
            query: The search query
            count: Number of results to return (max 50)
            market: Market code for localization
            
        Returns:
            List of search results with title, url, snippet, and display_url
        """
        try:
            # Try the standard Bing Search API first
            headers = {
                'Ocp-Apim-Subscription-Key': self.subscription_key,
                'User-Agent': 'Mozilla/5.0 (compatible; AzureAI-Agent/1.0)'
            }
            
            params = {
                'q': query,
                'count': min(count, 50),
                'mkt': market,
                'safeSearch': 'Moderate',
                'textDecorations': 'false',
                'textFormat': 'Raw'
            }
            
            async with aiohttp.ClientSession() as session:
                # Try Bing Grounding API endpoint first (for Bing.Grounding resources)
                grounding_url = f"{self.endpoint}/v7.0/grounding/search"
                
                async with session.get(grounding_url, headers=headers, params=params) as response:
                    if response.status == 200:
                        try:
                            data = await response.json()
                            if data:  # If we got actual data
                                return self._parse_grounding_results(data)
                        except:
                            pass  # Empty response or invalid JSON, try standard endpoint
                
                # Fall back to standard Bing Search v7 endpoint
                search_url = f"{self.endpoint}/v7.0/search"
                
                async with session.get(search_url, headers=headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return self._parse_search_results(data)
                    elif response.status == 401:
                        logger.warning(f"Bing API authentication failed. Status: {response.status}")
                        # Return a helpful error result instead of failing
                        return self._create_fallback_results(query)
                    else:
                        logger.error(f"Bing API request failed. Status: {response.status}, Response: {await response.text()}")
                        return self._create_fallback_results(query)
                        
        except Exception as e:
            logger.error(f"Error performing web search: {e}", exc_info=True)
            return self._create_fallback_results(query)

    def _create_fallback_results(self, query: str) -> List[Dict[str, Any]]:
        """
        Create fallback search results when Bing API is not available.
        
        Args:
            query: The original search query
            
        Returns:
            List with helpful guidance for finding current information
        """
        return [
            {
                'title': f'Search Issue: "{query}"',
                'url': 'https://www.bing.com/search?q=' + query.replace(' ', '+'),
                'snippet': f'I attempted to search for current information about "{query}" but encountered authentication issues with the Bing Search API. The current Azure resource is configured as "Bing.Grounding" (SKU: G1) which has limited API access and is not compatible with standard Bing Search v7 endpoints. This resource type is designed for AI grounding scenarios rather than general web search.',
                'display_url': 'API Configuration Issue',
                'date_last_crawled': '2025-08-24',
                'language': 'en'
            },
            {
                'title': 'Recommended Solutions',
                'url': 'https://learn.microsoft.com/en-us/bing/search-apis/',
                'snippet': 'To enable web search functionality, you would need a proper Bing Search v7 API resource. However, Microsoft has discontinued creating new Bing Search v7 resources. Alternative solutions include: 1) Using Azure AI Search with web indexing, 2) Implementing custom web scraping with proper compliance, or 3) Using other search APIs like Google Custom Search.',
                'display_url': 'Technical Solutions',
                'date_last_crawled': '2025-08-24',
                'language': 'en'
            },
            {
                'title': 'Manual Search Resources',
                'url': 'https://www.google.com/search?q=' + query.replace(' ', '+'),
                'snippet': 'For immediate information needs, please search manually using: Bing.com, Google.com, or specialized sources. For financial data: Bloomberg, Yahoo Finance. For technology: TechCrunch, GitHub. For news: Reuters, AP News, BBC.',
                'display_url': 'Alternative Search Options',
                'date_last_crawled': '2025-08-24',
                'language': 'en'
            }
        ]

    def _parse_grounding_results(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse Bing Grounding API response into standardized format.
        
        Args:
            data: Raw response from Bing Grounding API
            
        Returns:
            List of parsed grounding results
        """
        results = []
        logger.info(f"Parsing Bing Grounding API response: {data}")
        
        # Bing Grounding API may have different response structure
        # Try to parse various possible formats
        if isinstance(data, dict):
            if 'results' in data:
                for item in data['results']:
                    result = self._parse_grounding_item(item)
                    if result:
                        results.append(result)
            elif 'webPages' in data and 'value' in data['webPages']:
                for item in data['webPages']['value']:
                    result = self._parse_grounding_item(item)
                    if result:
                        results.append(result)
            elif 'value' in data:
                for item in data['value']:
                    result = self._parse_grounding_item(item)
                    if result:
                        results.append(result)
        
        logger.info(f"Bing Grounding API returned {len(results)} results")
        return results
    
    def _parse_grounding_item(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse a single grounding result item."""
        try:
            return {
                'title': item.get('name') or item.get('title', ''),
                'url': item.get('url') or item.get('link', ''),
                'snippet': item.get('snippet') or item.get('description', ''),
                'display_url': item.get('displayUrl') or item.get('url', ''),
                'date_last_crawled': item.get('dateLastCrawled', ''),
                'language': item.get('language', 'en')
            }
        except Exception as e:
            logger.warning(f"Failed to parse grounding item: {e}")
            return None

    def _parse_search_results(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse Bing search API response into standardized format.
        
        Args:
            data: Raw response from Bing Search API
            
        Returns:
            List of parsed search results
        """
        results = []
        
        if 'webPages' in data and 'value' in data['webPages']:
            for item in data['webPages']['value']:
                result = {
                    'title': item.get('name', ''),
                    'url': item.get('url', ''),
                    'snippet': item.get('snippet', ''),
                    'display_url': item.get('displayUrl', ''),
                    'date_last_crawled': item.get('dateLastCrawled', ''),
                    'language': item.get('language', 'en')
                }
                results.append(result)
        
        logger.info(f"Bing search returned {len(results)} results")
        return results

    def format_search_results(self, results: List[Dict[str, Any]], max_results: int = 5) -> str:
        """
        Format search results for use in agent responses.
        
        Args:
            results: List of search results
            max_results: Maximum number of results to include
            
        Returns:
            Formatted string of search results
        """
        if not results:
            return "No search results found."
        
        formatted_results = []
        for i, result in enumerate(results[:max_results], 1):
            formatted_result = f"""
**Result {i}:**
- **Title:** {result.get('title', 'N/A')}
- **URL:** {result.get('url', 'N/A')}
- **Summary:** {result.get('snippet', 'N/A')}
- **Display URL:** {result.get('display_url', 'N/A')}
"""
            formatted_results.append(formatted_result.strip())
        
        return "\n\n".join(formatted_results)

    async def get_grounded_information(self, query: str, context: str = "") -> Dict[str, Any]:
        """
        Get grounded information by searching the web and combining results.
        
        Args:
            query: The search query
            context: Additional context to help with the search
            
        Returns:
            Dictionary containing search results and grounded information
        """
        try:
            # Enhance query with context if provided
            enhanced_query = f"{query} {context}".strip() if context else query
            
            # Perform web search
            search_results = await self.search_web_async(enhanced_query, count=5)
            
            # Format results for agent consumption
            formatted_results = self.format_search_results(search_results)
            
            # Create grounded information response
            grounded_info = {
                'query': query,
                'enhanced_query': enhanced_query,
                'search_results': search_results,
                'formatted_results': formatted_results,
                'sources_count': len(search_results),
                'timestamp': asyncio.get_event_loop().time()
            }
            
            logger.info(f"Generated grounded information for query: {query}")
            return grounded_info
            
        except Exception as e:
            logger.error(f"Error generating grounded information: {e}", exc_info=True)
            return {
                'query': query,
                'error': str(e),
                'search_results': [],
                'formatted_results': "Error retrieving search results.",
                'sources_count': 0
            }


def create_bing_grounding_function_definition() -> Dict[str, Any]:
    """
    Create the function definition for Bing Grounding tool for use with Azure AI Agents.
    
    Returns:
        Function definition dictionary
    """
    return {
        "name": "bing_web_search",
        "description": "Search the web using Bing to find current, relevant information about any topic. Use this when you need up-to-date information, current events, recent developments, or information not available in your knowledge base.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to find information on the web. Be specific and include relevant keywords."
                },
                "context": {
                    "type": "string",
                    "description": "Optional additional context to help refine the search (e.g., specific time period, location, or domain)."
                }
            },
            "required": ["query"]
        }
    }


async def execute_bing_search_function(function_call: Dict[str, Any], bing_tool: BingGroundingTool) -> str:
    """
    Execute the Bing search function call.
    
    Args:
        function_call: The function call from the agent
        bing_tool: The BingGroundingTool instance
        
    Returns:
        JSON string with search results
    """
    try:
        arguments = json.loads(function_call.get('arguments', '{}'))
        query = arguments.get('query', '')
        context = arguments.get('context', '')
        
        if not query:
            return json.dumps({'error': 'Query parameter is required'})
        
        grounded_info = await bing_tool.get_grounded_information(query, context)
        return json.dumps(grounded_info, indent=2)
        
    except Exception as e:
        logger.error(f"Error executing Bing search function: {e}", exc_info=True)
        return json.dumps({'error': f'Failed to execute search: {str(e)}'})
