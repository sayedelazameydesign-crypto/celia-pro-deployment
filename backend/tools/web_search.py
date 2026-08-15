"""
NovaMind Web Search Tool
========================
Search the web for information using multiple search strategies.
"""

from .base import BaseTool
from typing import Dict, Any, List, Optional
import aiohttp
import json
import logging

logger = logging.getLogger(__name__)


class WebSearchTool(BaseTool):
    """Web search tool with multiple search strategies."""

    name = "web_search"
    description = "Search the web for current information, news, facts, and data. Returns relevant results with titles, URLs, and snippets."
    category = "research"
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query to look up"
            },
            "num_results": {
                "type": "integer",
                "description": "Number of results to return (1-10)",
                "default": 5
            },
            "search_type": {
                "type": "string",
                "enum": ["general", "news", "academic", "code"],
                "description": "Type of search to perform",
                "default": "general"
            }
        },
        "required": ["query"]
    }

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.search_engines = {
            "general": self._search_general,
            "news": self._search_news,
            "academic": self._search_academic,
            "code": self._search_code,
        }

    async def execute(self, query: str, num_results: int = 5, search_type: str = "general", **kwargs) -> str:
        """Execute web search."""
        search_func = self.search_engines.get(search_type, self._search_general)
        results = await search_func(query, num_results)
        return self._format_results(results)

    async def _search_general(self, query: str, num_results: int) -> List[Dict]:
        """General web search using DuckDuckGo (no API key needed)."""
        results = []
        try:
            async with aiohttp.ClientSession() as session:
                # Using DuckDuckGo Instant Answer API
                url = "https://api.duckduckgo.com/"
                params = {
                    "q": query,
                    "format": "json",
                    "no_html": 1,
                    "skip_disambig": 1
                }
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        # Extract results
                        if data.get("Abstract"):
                            results.append({
                                "title": data.get("Heading", query),
                                "url": data.get("AbstractURL", ""),
                                "snippet": data.get("Abstract", "")[:300]
                            })
                        for topic in data.get("RelatedTopics", [])[:num_results]:
                            if isinstance(topic, dict) and "Text" in topic:
                                results.append({
                                    "title": topic.get("Text", "")[:80],
                                    "url": topic.get("FirstURL", ""),
                                    "snippet": topic.get("Text", "")[:200]
                                })
        except Exception as e:
            logger.warning(f"DuckDuckGo search failed: {e}")
            # Fallback demo results
            results = self._demo_results(query)
        return results[:num_results]

    async def _search_news(self, query: str, num_results: int) -> List[Dict]:
        """News-specific search."""
        return await self._search_general(f"news {query}", num_results)

    async def _search_academic(self, query: str, num_results: int) -> List[Dict]:
        """Academic search."""
        return await self._search_general(f"research paper {query}", num_results)

    async def _search_code(self, query: str, num_results: int) -> List[Dict]:
        """Code-specific search."""
        return await self._search_general(f"github {query} code example", num_results)

    def _demo_results(self, query: str) -> List[Dict]:
        """Fallback demo results for when no API is available."""
        return [
            {
                "title": f"NovaMind Search: Results for '{query}'",
                "url": f"https://example.com/search?q={query.replace(' ', '+')}",
                "snippet": f"This is a simulated search result for the query: {query}. In production, this would return real search results from configured search APIs."
            }
        ]

    def _format_results(self, results: List[Dict]) -> str:
        """Format search results as readable text."""
        if not results:
            return "No results found for this query."
        formatted = []
        for i, r in enumerate(results, 1):
            formatted.append(
                f"[{i}] {r.get('title', 'No title')}\n"
                f"    URL: {r.get('url', 'N/A')}\n"
                f"    {r.get('snippet', 'No description')}"
            )
        return "\n\n".join(formatted)
