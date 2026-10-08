import logging
import os
from typing import Any

import httpx
from mcp.server.mcpserver import MCPServer
from tavily import TavilyClient

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("web-search-mcp")

SEARXNG_URL = os.getenv("SEARXNG_URL", "http://searxng:8080").rstrip("/")
SEARXNG_MAX_RESULTS = int(os.getenv("SEARXNG_MAX_RESULTS", "8"))
SEARXNG_TIMEOUT = float(os.getenv("SEARXNG_TIMEOUT", "15"))
TAVILY_TIMEOUT = float(os.getenv("TAVILY_TIMEOUT", "120"))

tavily_api_key = os.getenv("TAVILY_API_KEY")
tavily = TavilyClient(api_key=tavily_api_key) if tavily_api_key else None

if tavily is None:
    logger.warning(
        "TAVILY_API_KEY is not set. SearXNG search is available; "
        "all Tavily-specific tools will return a configuration error."
    )

mcp = MCPServer("Web Search")


def require_tavily() -> TavilyClient:
    if tavily is None:
        raise RuntimeError(
            "Tavily is not configured. Set TAVILY_API_KEY to use this tool."
        )
    return tavily


@mcp.tool()
def web_search(
    query: str,
    max_results: int = 8,
    language: str = "auto",
    time_range: str | None = None,
) -> dict[str, Any]:
    """
    Search the web with the self-hosted SearXNG instance.

    Use this for normal/cheap web searches. This tool intentionally does NOT
    call Tavily or fall back to Tavily.

    time_range may be: day, week, month, or year.
    """
    max_results = max(1, min(max_results, 20))

    params: dict[str, Any] = {
        "q": query,
        "format": "json",
        "language": language,
    }

    if time_range:
        params["time_range"] = time_range

    logger.info("SearXNG search: %s", query)

    with httpx.Client(timeout=SEARXNG_TIMEOUT) as client:
        response = client.get(f"{SEARXNG_URL}/search", params=params)
        response.raise_for_status()
        data = response.json()

    results = []
    for item in data.get("results", [])[: min(max_results, SEARXNG_MAX_RESULTS)]:
        results.append(
            {
                "title": item.get("title"),
                "url": item.get("url"),
                "content": item.get("content") or item.get("snippet"),
                "engine": item.get("engine"),
                "source": "searxng",
            }
        )

    return {
        "provider": "searxng",
        "query": query,
        "results": results,
    }


@mcp.tool()
def tavily_search(
    query: str,
    max_results: int = 5,
    search_depth: str = "basic",
    topic: str = "general",
    time_range: str | None = None,
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
    include_answer: bool = False,
    include_raw_content: bool = False,
) -> dict[str, Any]:
    """
    Search the web with Tavily.

    Use this explicitly when Tavily's search quality/features are useful.
    This tool is never automatically routed to SearXNG.

    search_depth: basic or advanced.
    topic: general, news, or finance.
    time_range: day, week, month, or year.
    """
    client = require_tavily()
    max_results = max(1, min(max_results, 20))

    logger.info("Tavily search: %s", query)

    return client.search(
        query=query,
        max_results=max_results,
        search_depth=search_depth,
        topic=topic,
        time_range=time_range,
        include_domains=include_domains,
        exclude_domains=exclude_domains,
        include_answer=include_answer,
        include_raw_content=include_raw_content,
        timeout=TAVILY_TIMEOUT,
    )


@mcp.tool()
def tavily_extract(
    urls: list[str],
    include_images: bool = False,
    extract_depth: str = "basic",
    format: str = "markdown",
    query: str | None = None,
) -> dict[str, Any]:
    """
    Extract the contents of one or more URLs with Tavily.

    Use this when the agent already knows which pages it wants to read.
    Tavily supports up to 20 URLs per extraction request.
    """
    client = require_tavily()

    if not urls:
        raise ValueError("At least one URL is required.")
    if len(urls) > 20:
        raise ValueError("A maximum of 20 URLs can be extracted at once.")

    logger.info("Tavily extract: %d URL(s)", len(urls))

    return client.extract(
        urls=urls,
        include_images=include_images,
        extract_depth=extract_depth,
        format=format,
        query=query,
        timeout=TAVILY_TIMEOUT,
    )


@mcp.tool()
def tavily_map(
    url: str,
    max_depth: int = 2,
    max_breadth: int | None = None,
    limit: int = 30,
    instructions: str | None = None,
    select_paths: list[str] | None = None,
    select_domains: list[str] | None = None,
    exclude_paths: list[str] | None = None,
    exclude_domains: list[str] | None = None,
) -> dict[str, Any]:
    """
    Map a website with Tavily.

    Use this to discover the structure and relevant URLs of a website before
    deciding which pages to extract or crawl.
    """
    client = require_tavily()

    logger.info("Tavily map: %s", url)

    return client.map(
        url=url,
        max_depth=max_depth,
        max_breadth=max_breadth,
        limit=limit,
        instructions=instructions,
        select_paths=select_paths,
        select_domains=select_domains,
        exclude_paths=exclude_paths,
        exclude_domains=exclude_domains,
        timeout=TAVILY_TIMEOUT,
    )


@mcp.tool()
def tavily_crawl(
    url: str,
    max_depth: int = 2,
    max_breadth: int | None = None,
    limit: int = 30,
    instructions: str | None = None,
    select_paths: list[str] | None = None,
    select_domains: list[str] | None = None,
    exclude_paths: list[str] | None = None,
    exclude_domains: list[str] | None = None,
    allow_external: bool = False,
    extract_depth: str = "basic",
    format: str = "markdown",
) -> dict[str, Any]:
    """
    Crawl a website with Tavily starting from a URL.

    Use this when multiple related pages need to be discovered and extracted.
    Prefer tavily_map first when you only need to discover site structure.
    """
    client = require_tavily()

    logger.info("Tavily crawl: %s", url)

    return client.crawl(
        url=url,
        max_depth=max_depth,
        max_breadth=max_breadth,
        limit=limit,
        instructions=instructions,
        select_paths=select_paths,
        select_domains=select_domains,
        exclude_paths=exclude_paths,
        exclude_domains=exclude_domains,
        allow_external=allow_external,
        extract_depth=extract_depth,
        format=format,
        timeout=TAVILY_TIMEOUT,
    )


if __name__ == "__main__":
    # LiteLLM can connect over the shared Docker network using:
    # http://web-search-mcp:8000/mcp
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=8000,
        stateless_http=True,
        json_response=True,
    )
