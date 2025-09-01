import httpx
import os
from typing import Optional

async def tavily_web_search(query: str, api_key: str) -> str:
    """Perform web search using Tavily API"""
    if not api_key:
        return f"🔍 Web search API key not configured. Add your Tavily API key to search for: {query}"
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": api_key,
                    "query": query,
                    "search_depth": "basic",
                    "include_answer": True,
                    "max_results": 3
                }
            )
            
            if response.status_code != 200:
                return f"🔍 Web search failed for: {query}"
            
            data = response.json()
            answer = data.get("answer", "")
            results = data.get("results", [])
            
            # Format search results
            search_context = []
            if answer:
                search_context.append(f"🔍 Quick Answer: {answer}")
            
            for result in results[:3]:
                title = result.get("title", "")
                snippet = result.get("content", "")[:200]
                if title and snippet:
                    search_context.append(f"📄 {title}: {snippet}...")
            
            return "\n".join(search_context) if search_context else f"🔍 No search results found for: {query}"
            
    except Exception as e:
        return f"🔍 Web search error for '{query}': Network issue, please try again."
