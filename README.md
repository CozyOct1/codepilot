# CodePilot

CodePilot 是一个面向私有代码仓库的智能开发助手 MVP。项目提供 CLI 和 FastAPI 服务，用于完成代码仓库索引、自然语言任务创建、仓库上下文检索、安全工具执行、任务记录持久化和 Prometheus 指标暴露。

项目面向单机私有仓库工作流，默认采用保守执行策略：对模糊需求优先生成计划并记录任务；对文件和 Shell 等高风险操作，通过工具层安全规则进行限制。

## 功能特性

- **命令行工作流**：支持仓库初始化、索引构建、项目问答、编辑任务创建、测试执行、Diff 查看、任务列表和远程 API 调用。
- **HTTP API**：支持会话创建、任务创建/查询、聊天任务、仓库索引、健康检查和指标暴露。
- **Agent 工作流**：基于 LangGraph 串联仓库检索、计划生成和安全执行阶段。
- **仓库索引**：基于 Chroma 为源码和文档文件构建本地索引。
- **任务持久化**：使用 SQLModel/SQLAlchemy 记录会话、消息、任务、工具调用和文件变更。
- **安全工具层**：文件访问限制在目标仓库内；Shell 命令使用白名单，并阻断高风险 token。
- **可观测性**：通过 Prometheus 暴露任务数量、工具调用次数和工具延迟指标。
- **本地部署**：提供 Redis、Prometheus、Grafana 和可选 Nginx 反向代理的 Docker Compose 配置。
- **离线兜底**：未配置 `OPENAI_API_KEY` 时，仍可使用确定性兜底计划，保证本地演示和测试可运行。

## 架构

```text
CLI / HTTP Client
      |
      v
FastAPI Agent Server
      |
      +-- SQLite task/session store
      +-- Prometheus metrics
      |
      v
LangGraph workflow
      |
      +-- Chroma repository search
      +-- Planner
      +-- Safe tools: filesystem / shell / git
      |
      v
Task summary and persisted result
```

## 技术栈

| 模块 | 技术 |
| --- | --- |
| CLI | Typer, Rich |
| API | FastAPI, Pydantic |
| Agent 编排 | LangGraph, LangChain OpenAI |
| 仓库索引 | Chroma |
| 数据存储 | SQLite, SQLModel, SQLAlchemy |
| 指标监控 | prometheus-client |
| 部署组件 | Docker Compose, Redis, Prometheus, Grafana, Nginx |
| 测试 | pytest |

## 环境要求

- Python 3.10+
- uv
- Docker 和 Docker Compose，可选，用于 Redis/Prometheus/Grafana/Nginx
- 项目依赖由 `pyproject.toml` 和 `uv.lock` 管理

## 安装与检查

进入项目根目录：

```bash
cd /data/niewenjie/CodePilot
uv sync --locked
uv run pytest
uv run codepilot --help
```

`uv sync --locked` 会根据 `uv.lock` 创建或更新本地虚拟环境，后续命令统一通过 `uv run` 执行。

## 配置

CodePilot 会读取项目根目录下 `.env` 中的环境变量。

常用配置：

```env
OPENAI_API_KEY=
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=codepilot
LANGSMITH_TRACING=false
CODEPILOT_HOST=0.0.0.0
CODEPILOT_PORT=8001
CODEPILOT_DATABASE_URL=sqlite:///./.codepilot/codepilot.db
CODEPILOT_REDIS_URL=redis://localhost:6379/0
CODEPILOT_CHROMA_PATH=./storage/chroma
```

`OPENAI_API_KEY` 不是本地兜底模式的必需项。未配置时，工作流仍会创建确定性计划，并可以执行测试、Diff 等安全本地命令。

## CLI 使用

初始化仓库：

```bash
uv run codepilot init --repo . --name CodePilot
```

构建本地索引：

```bash
uv run codepilot index --repo .
```

询问仓库信息：

```bash
uv run codepilot ask "请概括当前项目模块" --repo .
```

创建编辑类任务：

```bash
uv run codepilot edit "请运行测试并总结失败原因" --repo .
```

通过安全 Shell 工具运行测试：

```bash
uv run codepilot test --repo .
```

查看 Git Diff：

```bash
uv run codepilot diff --repo .
```

查看任务历史：

```bash
uv run codepilot tasks --repo .
```

## API 使用

启动 API 服务：

```bash
uv run codepilot serve --host 0.0.0.0 --port 8001
```

健康检查：

```bash
curl http://127.0.0.1:8001/health
```

查看指标：

```bash
curl http://127.0.0.1:8001/metrics
```

创建任务但不执行 Agent：

```bash
curl -X POST http://127.0.0.1:8001/api/tasks \
  -H "Content-Type: application/json" \
  -d '{"repo_path":"/data/niewenjie/CodePilot","user_request":"请解释这个项目","run":false}'
```

创建并执行任务：

```bash
curl -X POST http://127.0.0.1:8001/api/tasks \
  -H "Content-Type: application/json" \
  -d '{"repo_path":"/data/niewenjie/CodePilot","user_request":"请运行测试并总结结果","run":true}'
```

查看最近任务：

```bash
curl http://127.0.0.1:8001/api/tasks
```

通过 API 构建索引：

```bash
curl -X POST "http://127.0.0.1:8001/api/index?repo_path=/data/niewenjie/CodePilot"
```

## MCP 工具

启动 MCP Server：

```bash
uv run python -m codepilot.mcp_server.server
```

当前暴露的工具：

```text
filesystem_list_dir
filesystem_read_file
filesystem_write_file
filesystem_search_text
shell_run_command
git_status
git_diff
```

安全约束：

- 文件系统工具会将路径解析限制在目标仓库内。
- Shell 命令必须以允许的命令前缀开头。
- 阻断 `sudo`、`rm`、`curl`、`wget` 等高风险 token。

## 部署

启动 Redis、Prometheus 和 Grafana：

```bash
docker compose --env-file .env \
  -f deploy/docker-compose.yml \
  -f deploy/docker-compose.local.yml \
  up -d redis prometheus grafana
```

启动可选 Nginx 反向代理：

```bash
docker compose --env-file .env \
  -f deploy/docker-compose.yml \
  -f deploy/docker-compose.local.yml \
  --profile proxy \
  up -d nginx
```

默认本地端口：

| 服务 | 端口 |
| --- | ---: |
| CodePilot API | 8001 |
| Redis | 6379 |
| Prometheus | 9090 |
| Grafana | 3000 |
| Nginx | 8080 |

Grafana 本地默认账号：

```text
admin / admin
```

如果 Docker Hub 访问较慢，`deploy/docker-compose.local.yml` 已为本地部署镜像配置 `docker.m.daocloud.io` 镜像代理。

## 压测

项目内置轻量本地 HTTP 压测脚本：

```bash
uv run python scripts/load_test.py --endpoint health --requests 1000 --concurrency 50
uv run python scripts/load_test.py --endpoint metrics --requests 300 --concurrency 20
uv run python scripts/load_test.py --endpoint tasks --requests 300 --concurrency 20
```

`tasks` 压测默认使用 `run=false`，只测试 HTTP 处理和 SQLite 任务创建，不包含完整 Agent 执行链路。

当前本地环境实测结果：

| 接口 | 请求数 | 并发 | 成功率 | 吞吐 | P50 | P95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `GET /health` | 1000 | 50 | 100% | 261.16 req/s | 39.35ms | 459.34ms |
| `GET /metrics` | 300 | 20 | 100% | 208.53 req/s | 12.96ms | 959.42ms |
| `POST /api/tasks` | 300 | 20 | 100% | 146.09 req/s | 112.73ms | 667.83ms |

SQLite 写入链路优化前后，`POST /api/tasks` 在 `20` 并发、`300` 请求下的结果：

| 指标 | 优化前 | 优化后 |
| --- | ---: | ---: |
| 成功率 | 0% | 100% |
| 吞吐 | 1.96 req/s | 146.09 req/s |
| P95 延迟 | 10542.14ms | 667.83ms |

相关优化：

- 启用 SQLite `journal_mode=WAL`
- 设置 SQLite `busy_timeout=30000`
- 调整 SQLAlchemy 连接池和溢出连接数
- 在 SQLite 写操作周围增加短进程内写锁
- CLI 服务入口关闭 Uvicorn access log

## 开发

运行测试：

```bash
uv run pytest
```

当前测试状态：

```text
8 passed
```

对主要模块进行编译检查：

```bash
uv run python -m py_compile \
  codepilot/core/database.py \
  codepilot/cli/main.py \
  scripts/load_test.py
```

## 项目结构

```text
codepilot/
  agent/          LangGraph 工作流
  cli/            Typer CLI
  core/           配置、数据库、指标、Redis 辅助模块
  indexer/        仓库索引与检索
  mcp_server/     MCP 工具服务
  server/         FastAPI 应用和请求模型
  tools/          文件系统、Shell、Git、安全工具
  workers/        Worker 入口
deploy/           Docker Compose、Nginx、Prometheus 配置
scripts/          本地工具脚本
skills/           本地 Agent Skill prompt 资源
tests/            pytest 测试
```

## 当前限制

- SQLite 适合当前单机 MVP。更高写入并发建议迁移到 PostgreSQL 或其他服务端数据库。
- `run=true` 任务会进入 Agent 执行链路，可能包含检索、Shell 命令、测试和外部 LLM 调用。稳定压测建议使用 `run=false`。
- 当前索引使用确定性本地 embedding，适合离线运行。更高质量的语义检索需要接入真实 embedding 模型。
- 默认执行策略偏保守，不会自动进行大范围代码重写。

## 许可证

当前仓库未包含 License 文件。
