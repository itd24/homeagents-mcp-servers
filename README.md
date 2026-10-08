# HomeAgents MCP servers

Two [Model Context Protocol](https://modelcontextprotocol.io) servers written for
the HomeAgents platform. Each folder is a self-contained Python service with its
own `Dockerfile` and no dependency on the other one.

| Folder | Server | Port | Tools |
|---|---|---|---|
| `qdrant/` | `qdrant-mcp` | 8765 | `memory_store`, `memory_search`, `memory_delete`, `memory_stats` |
| `websearch/` | `web-search-mcp` | 8000 | `web_search`, `tavily_search`, `tavily_extract`, `tavily_map`, `tavily_crawl` |

## Build

The compose files in `homeagents-core` consume these images by tag, so build and
tag them first:

```bash
docker build -t qdrant-mcp:latest        qdrant
docker build -t web-search-mcp:latest    websearch
```

## qdrant-mcp

Long-term memory on top of a single Qdrant collection (`memory` by default).
Every point carries a `domain` payload field and every tool accepts an optional
`domain` argument. Several profiles can therefore share one collection without
reading each other's memories.

Embeddings come from a local Text Embeddings Inference service (`BAAI/bge-m3`,
1024 dimensions). Indexing costs CPU time instead of API calls.

| Variable | Default |
|---|---|
| `QDRANT_URL` | `http://qdrant:6333` |
| `EMBEDDINGS_URL` | `http://embeddings:80` |
| `COLLECTION_NAME` | `memory` |

The collection is created on first use, so a fresh machine works even if a setup
step was skipped.

```bash
docker run --rm -p 8765:8765 \
  -e QDRANT_URL=http://host.docker.internal:6333 \
  qdrant-mcp:latest
```

Health check: `GET /health`. MCP endpoint: `/mcp`.

## web-search-mcp

Two search providers behind one MCP server:

* `web_search` uses the self-hosted SearXNG instance. It needs no API key and
  never falls back to Tavily.
* `tavily_search`, `tavily_extract`, `tavily_map` and `tavily_crawl` use Tavily.

When `TAVILY_API_KEY` is empty, the Tavily tools return a configuration error
and `web_search` keeps working.

| Variable | Default |
|---|---|
| `SEARXNG_URL` | `http://searxng:8080` |
| `SEARXNG_MAX_RESULTS` | `8` |
| `SEARXNG_TIMEOUT` | `15` |
| `TAVILY_API_KEY` | not set |
| `TAVILY_TIMEOUT` | `120` |

```bash
docker run --rm -p 8000:8000 -e TAVILY_API_KEY=... web-search-mcp:latest
```

MCP endpoint: `http://<host>:8000/mcp`.

## What the agents get

Both servers are tool providers, so the model on the other end does the thinking.
`qdrant-mcp` embeds memory text with a local model, TEI serving `BAAI/bge-m3`, so
recall is semantic but never leaves the machine. `web-search-mcp` runs no model
of its own: it hands back page titles, links and snippets for the calling model to
read.

## Design notes

* Both servers speak MCP over streamable HTTP. The web-search server runs in
  stateless HTTP mode, so a restart does not break connected clients.
* Each folder is standalone, including its MCP library: `qdrant-mcp` is built on
  FastMCP, `web-search-mcp` on the official MCP Python SDK. Pick whichever fits a
  new server; neither imports the other.
* Dependencies carry lower and upper bounds in each `requirements.txt`, so a
  later rebuild cannot silently jump a major version.
* Neither server stores secrets. Everything arrives through environment
  variables.
