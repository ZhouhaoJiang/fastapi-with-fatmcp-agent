# FastMCP Integration Application Demo

**[中文说明 (Chinese Documentation)](README_zh.md)**

This project demonstrates a modular application built with FastMCP, integrating an MCP server, a FastAPI interface, and LLM Agent capabilities.

## Project Architecture

The project utilizes a modular design, separating different functionalities into distinct packages:

```
app/
├── __init__.py
├── api/                 # FastAPI Application Layer
│   ├── __init__.py
│   ├── main.py          # FastAPI main application entry point
│   └── routers/         # API route definitions
│       ├── __init__.py
│       ├── agent.py       # Agent mode routes
│       ├── mcp_resources.py # MCP resource routes
│       └── mcp_tools.py     # MCP tool routes
├── llm/                 # LLM (Large Language Model) Processing Layer
│   ├── __init__.py
│   ├── base.py          # Base LLM class
│   └── openai.py        # OpenAI implementation
└── mcp_server/          # MCP Server Definition Layer
    ├── __init__.py
    ├── base.py          # Base MCP Server class
    ├── run.py           # Script for internal Client connection or direct execution
    └── simple.py        # Simple MCP Server implementation (with tools & resources)
main.py                  # Main entry point (runs API or MCP server)
```

**Core Workflow (API Mode):**

1.  **Run MCP Server Independently**: Start a separate MCP server process using `python main.py --mode mcp`, listening on a specified port (default: 8001) with SSE transport.
2.  **Run API Server**: Start the FastAPI server using `python main.py --mode api` (listens on 8080).
3.  **Connection**: The `mcp_client` within the FastAPI server connects to the independently running MCP server via SSE.
4.  **Request Handling**: Frontend or other clients interact with the application through the HTTP API provided by FastAPI.
5.  **Tool/Resource/Agent Calls**: FastAPI routes forward requests to the `mcp_client` (communicating with the MCP server) or the `llm` module (communicating with the LLM API).

## Features

-   **Modular Design**: Clear separation of concerns (API, LLM, MCP) for easy extension and maintenance.
-   **Dual Run Modes**:
    -   `api` mode: Runs the FastAPI server, requires a **separately running** MCP server.
    -   `mcp` mode: Runs the MCP server directly for testing or connection by other clients.
-   **LLM Integration**: Supports using OpenAI (or other extensible LLMs) to process tool outputs or execute in Agent mode.
-   **Agent Mode**: Provides an `/api/agent/process` endpoint for the LLM to autonomously select and call MCP tools.
-   **Complete API**: Offers RESTful endpoints for MCP tools, resources, and Agent functionality via FastAPI.
-   **Persistent Connection**: The API server maintains a long-lived SSE connection to the MCP server for efficiency.

## Installation

1.  **Clone the repository** (if needed).
2.  **Install dependencies** (using uv or pip):

    ```bash
    # Recommended: use uv
    uv pip install -e .

    # Alternatively, use pip
    # pip install -e .
    ```
3.  **Set Environment Variables**:
    -   The `OPENAI_API_KEY` environment variable is required to use LLM features.
    -   You can create a `.env` file in the project root and define it there:
        ```dotenv
        OPENAI_API_KEY=sk-...
        ```

## Usage

### Running the API Server (Recommended)

This mode requires **first starting the standalone MCP server**.

1.  **Start the MCP Server (in one terminal)**:

    ```bash
    # Uses SSE transport, listening on 127.0.0.1:8001 (default)
    python main.py --mode mcp

    # Or specify a different host and port
    # python main.py --mode mcp --mcp-host 0.0.0.0 --mcp-port 8002
    ```

2.  **Start the API Server (in another terminal)**:

    ```bash
    # Listens on 0.0.0.0:8080 (default)
    python main.py --mode api

    # Use a different port or enable hot-reloading (for development)
    # python main.py --mode api --port 9000 --reload
    ```

    The API server is now accessible at `http://localhost:8080` (or your specified port). It will automatically connect to the MCP server started in step 1 (default connection: `http://localhost:8001/sse`).

### Running the MCP Server Directly

If you only need to run the MCP server (e.g., for direct connection by other FastMCP clients):

```bash
# Default: Use SSE transport, listening on 127.0.0.1:8001
python main.py --mode mcp

# Use Standard I/O (stdio) transport
# python main.py --mode mcp --mcp-transport stdio
```

## API Endpoints (Accessed via API Server)

The API server runs on `http://localhost:8080` (default).

-   **MCP Tools** (`/api/tools`):
    -   `GET /`: List all available tools and their parameters.
    -   `POST /{tool_name}`: Call a specific tool. Example request body: `{"params": {"a": 5, "b": 3}, "use_llm": true, "system_message": "Explain the result"}`
-   **MCP Resources** (`/api/resources`):
    -   `GET /`: List all available resource URIs and their types.
    -   `GET /{resource_path:path}`: Get the content of a specific resource (e.g., `GET /api/resources/example/greeting`).
-   **Agent Mode** (`/api/agent`):
    -   `POST /process`: Let the LLM autonomously handle a user request, potentially calling tools. Example request body: `{"prompt": "What is 5 plus 3?"}`
-   **Health Checks**:
    -   `GET /health`: Check if the API server is running.
    -   `GET /api/tools/health`: Check the connection status between the API server and the MCP server.

## Extending the Application

### Adding New Tools

1.  Extend `BaseMCPServer` in `app/mcp_server/simple.py` (or create a new server file).
2.  Define new tools using the `@self.mcp.tool()` decorator within the `_register_tools` method.
3.  If you created a new server file, import and instantiate it in `app/mcp_server/run.py`.

### Adding New LLM Providers

1.  Create a new Python file in the `app/llm/` directory (e.g., `anthropic.py`).
2.  Create a new class inheriting from `app.llm.base.BaseLLM`.
3.  Implement the `generate` and `generate_with_tools` methods.
4.  Import and use the new LLM class where needed (e.g., in `agent.py`).

## Development

Enable hot-reloading when running the API server for development:

```bash
# Ensure the standalone MCP server is still running
python main.py --mode api --reload
```
