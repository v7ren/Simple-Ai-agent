"""Search tool: web search via DuckDuckGo."""

from typing import Dict, Any


async def search_tool(query: str, max_results: int = 5) -> Dict[str, Any]:
    """Search the web via DuckDuckGo. Use for current events, facts, or anything online."""
    try:
        from duckduckgo_search import DDGS

        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        return {
            "query": query,
            "results": [
                {"title": r.get("title", ""), "url": r.get("href", ""), "snippet": r.get("body", "")}
                for r in results
            ],
            "total": len(results),
        }
    except Exception as e:
        return {
            "query": query,
            "results": [],
            "total": 0,
            "error": str(e),
            "hint": "Install duckduckgo-search: pip install duckduckgo-search",
        }


TOOL = {
    "name": "search",
    "description": "Search the web for current information, facts, or documentation. Use when you need up-to-date or external information.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query (e.g. 'Python asyncio tutorial', 'weather Tokyo')",
            },
            "max_results": {
                "type": "integer",
                "description": "Max number of results to return (default 5)",
                "default": 5,
            },
        },
        "required": ["query"],
    },
    "handler": search_tool,
}
