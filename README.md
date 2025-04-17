# FastMCP 集成应用

一个基于FastMCP的模块化应用，集成了MCP服务器、FastAPI接口和LLM Agent 处理能力的 demo。

## 项目架构

本项目采用模块化设计，将不同功能分离到独立的包中：

```
app/
├── __init__.py
├── api/                 # FastAPI 应用层
│   ├── __init__.py
│   ├── main.py          # FastAPI 主应用入口
│   └── routers/         # API 路由定义
│       ├── __init__.py
│       ├── agent.py       # Agent 模式路由
│       ├── mcp_resources.py # MCP 资源路由
│       └── mcp_tools.py     # MCP 工具路由
├── llm/                 # LLM (大语言模型) 处理层
│   ├── __init__.py
│   ├── base.py          # LLM 基类
│   └── openai.py        # OpenAI 实现
└── mcp_server/          # MCP 服务器定义层
    ├── __init__.py
    ├── base.py          # MCP 服务器基类
    ├── run.py           # 用于内部Client连接的脚本或直接运行
    └── simple.py        # 简单 MCP 服务器实现 (包含工具和资源)
main.py                  # 主程序入口 (运行API或MCP服务器)
```

**核心流程 (API模式):**

1.  **独立运行 MCP 服务器**: 使用 `python main.py --mode mcp` 启动一个独立的 MCP 服务器进程，监听指定端口（默认为 8001）并使用 SSE 传输。
2.  **运行 API 服务器**: 使用 `python main.py --mode api` 启动 FastAPI 服务器（监听在 8080）。
3.  **连接**: FastAPI 服务器内部的 `mcp_client` 通过 SSE 连接到独立运行的 MCP 服务器。
4.  **请求处理**: 前端或其他客户端通过 FastAPI 提供的 HTTP API 与应用交互。
5.  **工具/资源/Agent 调用**: FastAPI 路由将请求转发给 `mcp_client` (与 MCP 服务器通信) 或 `llm` 模块 (与 LLM API 通信)。

## 功能特点

-   **模块化设计**: 清晰的职责分离（API、LLM、MCP），易于扩展和维护。
-   **双模式运行**: 
    -   `api` 模式: 运行 FastAPI 服务器，需要**单独运行**的 MCP 服务器。
    -   `mcp` 模式: 直接运行 MCP 服务器，用于测试或被其他客户端连接。
-   **LLM 集成**: 支持使用 OpenAI (或其他可扩展的 LLM) 处理工具输出或执行 Agent 模式。
-   **Agent 模式**: 提供 `/api/agent/process` 接口，让 LLM 自主选择和调用 MCP 工具。
-   **完整 API**: 通过 FastAPI 提供 MCP 工具、资源和 Agent 功能的 RESTful 接口。
-   **持久连接**: API 服务器通过 SSE 维持与 MCP 服务器的长连接，提高效率。

## 安装

1.  **克隆仓库** (如果需要)
2.  **安装依赖** (使用 uv 或 pip):

    ```bash
    # 推荐使用 uv
    uv pip install -e .
    
    # 或者使用 pip
    # pip install -e .
    ```
3.  **设置环境变量**: 
    -   需要设置 `OPENAI_API_KEY` 环境变量才能使用 LLM 功能。
    -   可以创建一个 `.env` 文件并在其中定义：
        ```
        OPENAI_API_KEY=sk-...
        ```

## 使用方法

### 运行 API 服务器 (推荐方式)

这种方式需要**先启动独立的 MCP 服务器**。

1.  **启动 MCP 服务器 (在一个终端中)**:

    ```bash
    # 使用 SSE 传输，监听在 127.0.0.1:8001 (默认)
    python main.py --mode mcp 
    
    # 或者指定不同的端口和主机
    # python main.py --mode mcp --mcp-host 0.0.0.0 --mcp-port 8002
    ```

2.  **启动 API 服务器 (在另一个终端中)**:

    ```bash
    # 默认监听在 0.0.0.0:8080
    python main.py --mode api 
    
    # 使用不同端口或启用热重载 (开发)
    # python main.py --mode api --port 9000 --reload
    ```

    API 服务器现在可以通过 `http://localhost:8080` (或您指定的端口) 访问。它会自动连接到步骤 1 中启动的 MCP 服务器 (默认连接 `http://localhost:8001/sse`)。

### 直接运行 MCP 服务器

如果您只想运行 MCP 服务器（例如，被其他 FastMCP 客户端直接连接），可以使用：

```bash
# 默认使用 SSE 传输，监听在 127.0.0.1:8001
python main.py --mode mcp

# 使用标准输入/输出 (stdio) 传输
# python main.py --mode mcp --mcp-transport stdio 
```

## API 端点 (通过 API 服务器访问)

API 服务器运行在 `http://localhost:8080` (默认)。

-   **MCP 工具** (`/api/tools`):
    -   `GET /`: 获取所有可用工具及其参数。
    -   `POST /{tool_name}`: 调用指定工具。请求体示例: `{"params": {"a": 5, "b": 3}, "use_llm": true, "system_message": "请解释结果"}`
-   **MCP 资源** (`/api/resources`):
    -   `GET /`: 获取所有可用资源 URI 及其类型。
    -   `GET /{resource_path:path}`: 获取指定资源的内容 (例如: `GET /api/resources/example/greeting`)。
-   **Agent 模式** (`/api/agent`):
    -   `POST /process`: 让 LLM 自主处理用户请求，可调用工具。请求体示例: `{"prompt": "5加3等于多少？"}`
-   **健康检查**:
    -   `GET /health`: 检查 API 服务器是否运行。
    -   `GET /api/tools/health`: 检查 API 服务器与 MCP 服务器的连接状态。

## 高级用法和扩展

### 添加新工具

1.  在 `app/mcp_server/simple.py` (或创建新的服务器文件) 中，继承 `BaseMCPServer`。
2.  在 `_register_tools` 方法中使用 `@self.mcp.tool()` 装饰器定义新工具。
3.  如果创建了新文件，请在 `app/mcp_server/run.py` 中导入并实例化它。

### 添加新的 LLM 提供商

1.  在 `app/llm/` 目录下创建新的 Python 文件 (例如 `anthropic.py`)。
2.  创建新类，继承 `app.llm.base.BaseLLM`。
3.  实现 `generate` 和 `generate_with_tools` 方法。
4.  在需要的地方 (例如 `agent.py`) 导入并使用新的 LLM 类。

## 开发

在开发 API 服务器时启用热重载：

```bash
# 确保独立的 MCP 服务器仍在运行
python main.py --mode api --reload
```
