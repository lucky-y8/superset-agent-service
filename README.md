# Superset Agent Service 项目文档

## 项目概述

**Superset Agent Service** 是一个基于 FastAPI 的 Agent Sidecar 服务骨架，用于在 Apache Superset 或已有业务系统旁边增加一个受控的 AI Agent 层。

它的目标不是替代 Superset，而是作为一个独立的智能编排服务，负责接收用户问题、理解当前页面上下文、调用 Superset MCP 或其他工具、执行 RAG 检索、记录运行链路，并把 token、成本、延迟、错误等使用情况结构化沉淀下来，后续可接入 Superset Dashboard 做监控分析。

### 核心定位

- 为 Superset / 老系统提供 Assistant 能力
- 作为独立 FastAPI 服务部署，不侵入老系统核心代码
- 通过 MCP Client 调用 Superset MCP Server
- 通过 LangGraph 承载 Plan + ReAct + Reflection 工作流
- 通过 Skills 层封装 Dashboard 解释、指标归因、Text-to-SQL 等业务能力
- 通过 Run Trace 记录每次 Agent 执行过程
- 通过 Metrics / Audit 支撑成本分析、故障排查和审计
- 通过 SQL Guard / Policy Guard 控制工具和查询边界

## 架构类型

这个项目采用的是：

```text
MCP-enabled Agent Sidecar Architecture
```

中文可以理解为：

```text
基于 MCP 的 Agent 旁路服务架构
```

它的核心思想是：老系统继续负责原有业务和权限，Agent Service 作为旁路智能层接入老系统能力，并负责工具编排、安全治理、可观测性和运行记录。

更完整地说，本项目由两层概念组成：

```text
架构层：MCP-enabled Agent Sidecar Architecture
执行层：Plan + ReAct + Reflection Hybrid Workflow
```

二者不是同一个层级：

- **MCP-enabled Agent Sidecar Architecture** 描述服务怎么部署、怎么接入 Superset / 老系统、怎么治理工具和数据。
- **Plan + ReAct + Reflection Hybrid Workflow** 描述一次 Agent 请求内部怎么思考、怎么调用工具、怎么自检和修正。

## 架构设计详解

### MCP-enabled

MCP-enabled 表示 Agent Service 通过 MCP 协议接入外部系统能力。对于 Superset 场景，Superset MCP Server 可以暴露 Dashboard、Dataset、Chart、SQL 等工具能力。

在这个项目里，MCP 不直接暴露给前端，而是由 FastAPI Agent Service 中的 MCP Client 调用：

```text
Superset UI
    -> FastAPI Agent Service
        -> MCP Client
            -> Superset MCP Server
```

这样设计的好处是：

- 前端不直接接触高权限工具
- Agent Service 可以统一做权限控制
- 所有工具调用都能进入 trace、metrics 和 audit
- 后续可以同时接多个 MCP Server
- 可以在 MCP 之上增加 Policy Guard 和 SQL Guard

### Agent Sidecar

Sidecar 表示 Agent Service 是老系统旁边的独立服务，而不是直接嵌进老系统内部。

```text
老系统 / Superset：继续负责已有业务、页面、账号和权限
Agent Service：负责 AI 编排、工具调用、RAG、治理、审计和监控
```

这样适合老系统改造，因为它降低了侵入性：

- 不需要重写 Superset 或老系统
- Agent 服务可以独立部署和扩容
- Agent 出问题不会直接影响核心业务
- 可以先做小场景 MVP，再逐步扩大能力

### Agent Service 的职责

Agent Service 不是一个普通 chat API，它承担的是企业级 Agent 中间层职责：

- 接收用户问题和页面上下文
- 解析用户身份、租户、角色和权限
- 选择合适的 Agent workflow
- 选择合适的业务 Skill
- 调用 Superset MCP 或自定义工具
- 执行 RAG 检索
- 对 SQL 和工具调用做安全检查
- 记录每次 run 的完整执行链路
- 采集模型、token、成本、延迟和错误
- 写入审计日志
- 提供管理员配置入口

## 执行模式详解

本项目建议采用：

```text
Plan + ReAct + Reflection Hybrid Workflow
```

也就是：

```text
先规划，再边执行边观察，最后自检和修正
```

### Plan

Plan 阶段负责把用户问题转成可执行步骤。

例如用户问：

```text
为什么这个 Dashboard 本周成本上涨？
```

Agent 可以先生成计划：

```text
1. 获取当前 dashboard 元数据
2. 获取相关 chart 和 dataset 信息
3. 检查当前筛选条件和时间范围
4. 查询本周和上周成本趋势
5. 按业务维度拆解异常来源
6. 总结上涨原因并给出证据
```

Plan 阶段适合企业场景，因为它让复杂任务更可控，后续也方便审计和展示。

### ReAct

ReAct 表示：

```text
Reason -> Act -> Observe -> Reason -> Act -> Observe
```

Agent 不只是一次性回答，而是在执行过程中反复思考、调用工具、观察结果，再决定下一步。

Superset Assistant 场景示例：

```text
Reason: 需要知道当前 dashboard 有哪些图表
Act: 调用 Superset MCP 获取 dashboard metadata
Observe: dashboard 包含成本趋势、部门成本、云厂商成本图表

Reason: 成本趋势图显示本周异常，需要查部门维度
Act: 调用安全 SQL 工具查询部门维度
Observe: AI 平台部门成本上涨最多

Reason: 需要进一步拆分模型维度
Act: 查询模型使用明细
Observe: gpt-4.1 调用少但成本占比高
```

ReAct 适合工具调用密集型任务，尤其是需要多次查询 Superset、RAG、SQL 或外部 API 的场景。

### Reflection

Reflection 表示 Agent 在关键节点进行自检和修正。

它可以检查：

- 回答是否真正回答了用户问题
- 是否有数据证据
- 是否引用了正确的 dashboard / chart / dataset
- SQL 是否安全
- 工具结果是否足够
- 是否需要补充检索
- 成本是否过高
- 是否应该降级模型或停止执行

示例：

```text
初步回答：本周成本上涨主要来自 AI 平台部门。

Reflection:
- 检查是否有同比/环比数据：有
- 检查是否有维度拆解：有部门维度，但缺少模型维度
- 检查证据是否足够：不足
- 决策：继续查询模型维度后再生成最终回答
```

Reflection 不建议默认每一步都开启，因为它会增加 token 和延迟。推荐策略：

```text
on_failure
on_low_confidence
before_final_answer
on_sensitive_tool_call
```

### Hybrid Workflow 总结

三者的关系是：

```text
Plan：先定路线
ReAct：执行过程中动态调用工具和观察结果
Reflection：关键节点自检、纠错和决定是否重试
```

放到本项目里：

```text
FastAPI Agent Service
        |
        v
LangGraph Runtime
        |
        +-- Context Intake
        +-- Skill Routing
        +-- Plan Node
        +-- ReAct Tool Loop
        +-- SQL / Policy Guard
        +-- RAG Retrieval
        +-- Reflection Node
        +-- Final Answer Node
        +-- Trace / Metrics / Audit
```

## Skills 设计

### 为什么需要 Skills

在企业级 Agent 服务里，Tool 只能表示“能做什么动作”，但不能表达“要完成什么业务任务”。

因此本项目增加 `skills/` 层，用来封装可复用的业务能力：

```text
Skill = 面向业务目标的一组 Agent 流程
Tool = 一个具体、受控、可审计的动作
```

例如：

```text
Tool:
- get_dashboard_metadata
- run_safe_sql
- search_metric_definition
- call_superset_mcp_tool

Skill:
- dashboard_explainer
- metric_investigator
- text_to_sql
- cost_monitor
```

`Skill` 会组合多个 `Tool`，并在 LangGraph workflow 中控制步骤、检查权限、记录 trace、触发 Reflection。

### Skill 和 Tool 的区别

| 维度 | Skill | Tool |
| --- | --- | --- |
| 抽象层级 | 高层业务能力 | 低层动作能力 |
| 目标 | 完成用户任务 | 执行一个具体操作 |
| 示例 | 分析指标为什么上涨 | 调用 SQL 查询 |
| 是否可组合 | 可以组合多个 Tool | 通常是单个动作 |
| 是否需要流程 | 通常需要 Plan / ReAct / Reflection | 通常只需要输入输出 |
| 记录方式 | 记录 skill_selected、skill_completed | 记录 tool_call、tool_result |

### 当前预置 Skills

当前 `skills/registry.py` 先预置三个能力，作为后续实现入口：

```text
dashboard_explainer
  目标：解释当前 Superset dashboard 或 chart
  典型问题：这个 dashboard 说明了什么？这个图表怎么看？
  风险等级：low

metric_investigator
  目标：分析某个指标为什么上涨、下降或异常波动
  典型问题：为什么本周成本上涨？这个指标为什么下降？
  风险等级：medium

text_to_sql
  目标：把自然语言问题转换成受 SQL Guard 保护的查询
  典型问题：帮我查本周各部门成本，生成 SQL
  风险等级：high
```

后续可以继续增加：

```text
chart_recommender
  根据用户问题推荐图表类型和可视化方式

report_summarizer
  总结 dashboard、dataset 或周期性报表

cost_monitor
  分析 Agent 模型调用成本、token 和用户使用情况

error_investigator
  分析 Agent run 为什么慢、为什么贵、为什么失败
```

### Skill Routing

`SkillRouter` 负责根据用户问题选择合适 Skill。

MVP 阶段可以使用简单规则：

```text
包含 SQL / 查询 -> text_to_sql
包含 为什么 / 异常 -> metric_investigator
默认 -> dashboard_explainer
```

后续可以升级为：

```text
LLM Intent Classifier
        |
        v
SkillMatch
- skill_name
- confidence
- reason
```

当置信度低时，可以让 Agent 反问用户，或走默认 `dashboard_explainer`。

### Skill 在执行链路中的位置

```text
用户问题
        |
        v
Context Intake
        |
        v
Skill Router
        |
        v
Skill Workflow
        |
        +-- Plan
        +-- ReAct Tool Loop
        +-- RAG Retrieval
        +-- SQL / Policy Guard
        +-- Reflection
        +-- Final Answer
        |
        v
Trace / Metrics / Audit
```

### Skills 流程图

![Skills 业务能力图](docs/images/skills.png)

## 总体架构

![Superset Agent Service 架构图](docs/images/architecture.png)

```text
Superset UI / Legacy System UI
        |
        | 用户问题 + 页面上下文 + 登录身份
        v
FastAPI Agent Service
        |
        +-- Auth / Permission Context
        +-- LangGraph Runtime
        +-- Skill Registry / Skill Router
        +-- Superset MCP Client
        +-- Tool Registry
        +-- RAG Retriever
        +-- SQL / Policy Guard
        +-- Audit Logger
        +-- Metrics Collector
        +-- Run / Trace Store
        +-- Admin Config
        |
        +-- Superset MCP Server
        +-- Vector DB
        +-- LLM Gateway
        +-- Usage DB
        +-- Legacy System API
```

### 执行流程图

![执行流程图](docs/images/workflow.png)

## 图表索引

本项目 README 使用项目内 SVG 图片描述架构，GitHub 可直接渲染，便于后续维护和导出。

| 图 | 说明 |
| --- | --- |
| 总体架构图 | Agent Sidecar、MCP、RAG、LLM、Usage DB 的整体关系 |
| 执行流程图 | 一次用户提问从 UI 到 LangGraph、工具、Reflection、回答的完整时序 |
| Skills 流程图 | Skill Router 如何选择业务能力并调用工具 |
| 模块依赖图 | FastAPI 包内各模块之间的依赖边界 |
| 数据模型 ER 图 | 后续持久化表的关系设计 |
| 部署集成图 | Superset、Agent Service、MCP、数据库、LLM 的部署关系 |
| 权限治理图 | 登录身份、权限上下文、Policy Guard、SQL Guard 的检查链路 |
| 可观测性链路图 | Run Trace、Metrics、Audit、Superset Usage Dashboard 的数据流 |
| 演进路线图 | MVP 到可观测性、安全治理、智能能力的路线 |

### 模块依赖图

![模块依赖图](docs/images/modules.png)

### 数据模型 ER 图

![数据模型 ER 图](docs/images/data-model.png)

### 部署集成图

![部署集成图](docs/images/deployment.png)

### 权限治理图

![权限治理图](docs/images/governance.png)

### 可观测性链路图

![可观测性链路图](docs/images/observability.png)

### 演进路线图

![演进路线图](docs/images/roadmap.png)

## 核心执行流程

```text
1. 用户在 Superset 或老系统页面发起问题
2. 前端把 question、dashboard_id、chart_id、filters、time_range 传给 Agent Service
3. Agent Service 创建 run_id，并记录 run_started 事件
4. Auth 模块生成 Permission Context
5. LangGraph Runtime 选择 Skill、制定计划并选择工具
6. Skill 层编排业务流程，Tool Registry 调用 Superset MCP、RAG、SQL Guard 等工具
7. Reflection 节点检查回答质量、证据和风险
8. Agent 返回最终回答
9. Run / Metrics / Audit 模块记录执行链路、token、成本、延迟和错误
10. Superset 可读取 usage 数据做监控看板
```

当前版本已经搭好第 1 版骨架：可以创建 run、记录基础事件、返回占位回答、查询 run trace。Superset MCP、LangGraph、真实 LLM、持久化数据库和登录体系还没有正式接入。

## 技术栈

### 后端框架

- **FastAPI**：Web API 框架
- **Pydantic v2**：请求响应模型和配置校验
- **Uvicorn**：ASGI 运行服务

### 数据和迁移

- **SQLAlchemy Async**：异步数据库访问边界
- **Alembic**：数据库迁移工具
- **SQLite / PostgreSQL**：开发环境默认 SQLite，生产建议 PostgreSQL

### Agent 能力

- **LangGraph**：未来用于 Plan + ReAct + Reflection 工作流
- **Skills Layer**：封装 Dashboard 解释、指标归因、Text-to-SQL、成本分析等业务能力
- **LangChain Core**：未来用于模型和工具抽象
- **Superset MCP**：未来用于调用 Superset Dashboard、Dataset、SQL、Chart 等能力

### 安全和治理

- **Policy Guard**：工具调用权限控制
- **SQL Guard**：SQL 安全检查边界
- **Audit Logger**：审计记录边界
- **Metrics Collector**：token、成本、延迟、模型调用统计边界

## 项目结构

```text
superset-agent-service/
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── superset_agent_service/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── router.py
│   │   └── health.py
│   │
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── schemas.py
│   │   └── dependencies.py
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── api.py
│   │   ├── schemas.py
│   │   ├── service.py
│   │   └── runtime.py
│   │
│   ├── runs/
│   │   ├── __init__.py
│   │   ├── api.py
│   │   ├── schemas.py
│   │   └── service.py
│   │
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── registry.py
│   │   ├── mcp_client.py
│   │   └── superset_mcp.py
│   │
│   ├── skills/
│   │   ├── __init__.py
│   │   ├── registry.py
│   │   ├── router.py
│   │   └── schemas.py
│   │
│   ├── rag/
│   │   ├── __init__.py
│   │   └── retriever.py
│   │
│   ├── guards/
│   │   ├── __init__.py
│   │   ├── sql_guard.py
│   │   └── policy_guard.py
│   │
│   ├── audit/
│   │   ├── __init__.py
│   │   └── logger.py
│   │
│   ├── metrics/
│   │   ├── __init__.py
│   │   └── collector.py
│   │
│   ├── admin/
│   │   ├── __init__.py
│   │   ├── api.py
│   │   └── schemas.py
│   │
│   └── db/
│       ├── __init__.py
│       ├── base.py
│       └── session.py
│
└── legacy_user_service/
    └── 原 listening_ripples 改名后的旧用户服务代码，后续可迁移登录注册能力
```

## 文件说明

### 根目录文件

| 文件 | 说明 |
| --- | --- |
| `README.md` | 项目说明、架构设计、运行方式、API 示例和后续路线 |
| `requirements.txt` | Python 依赖列表 |
| `.env.example` | 环境变量示例 |
| `.gitignore` | 忽略虚拟环境、缓存、数据库文件和本地配置 |
| `LICENSE` | 项目许可证文件 |

### `superset_agent_service`

| 文件 | 说明 |
| --- | --- |
| `__init__.py` | 标记 Python 包 |
| `main.py` | FastAPI 应用入口，注册中间件和 API 路由 |
| `config.py` | 读取 `.env` 配置，集中管理服务名、数据库、Superset MCP、模型和运行限制 |

### `api`

| 文件 | 说明 |
| --- | --- |
| `api/__init__.py` | API 包标记 |
| `api/router.py` | 聚合 health、agents、runs、admin 路由 |
| `api/health.py` | 健康检查接口 `/api/v1/health` |

### `auth`

| 文件 | 说明 |
| --- | --- |
| `auth/__init__.py` | 认证包标记 |
| `auth/schemas.py` | `PermissionContext`，描述当前用户、租户、角色和可用工具 |
| `auth/dependencies.py` | 从请求头构造临时权限上下文，未来替换为 SSO / JWT / Superset 登录校验 |

### `agents`

| 文件 | 说明 |
| --- | --- |
| `agents/__init__.py` | Agent 包标记 |
| `agents/api.py` | Agent 对话接口 `/api/v1/agents/chat` |
| `agents/schemas.py` | Agent 请求和响应模型 |
| `agents/service.py` | Agent 应用服务，负责创建 run、调用 runtime、处理完成和失败 |
| `agents/runtime.py` | LangGraph Runtime 边界，未来放 Plan + ReAct + Reflection 工作流 |

### `runs`

| 文件 | 说明 |
| --- | --- |
| `runs/__init__.py` | Run trace 包标记 |
| `runs/api.py` | Run trace 查询接口 `/api/v1/runs/{run_id}` |
| `runs/schemas.py` | `RunEvent` 和 `RunTrace` 数据模型 |
| `runs/service.py` | 当前内存版 run 存储和生命周期事件记录，未来替换为数据库持久化 |

### `tools`

| 文件 | 说明 |
| --- | --- |
| `tools/__init__.py` | 工具包标记 |
| `tools/registry.py` | 工具注册表，统一管理工具名称、描述、权限和 handler |
| `tools/mcp_client.py` | 通用 MCP Client，用于调用 MCP Server tool |
| `tools/superset_mcp.py` | Superset MCP Client 工厂，读取配置创建 MCP 调用客户端 |

### `skills`

| 文件 | 说明 |
| --- | --- |
| `skills/__init__.py` | 业务能力包标记 |
| `skills/schemas.py` | `SkillDefinition` 和 `SkillMatch`，描述业务能力定义和路由结果 |
| `skills/registry.py` | Skill 注册表，当前预置 Dashboard 解释、指标归因、Text-to-SQL 三个能力 |
| `skills/router.py` | Skill 路由器占位，根据用户问题选择合适业务能力，未来可替换为 LLM intent classifier |

### `rag`

| 文件 | 说明 |
| --- | --- |
| `rag/__init__.py` | RAG 包标记 |
| `rag/retriever.py` | 检索器边界，未来接向量库、指标口径、Dashboard 文档和业务知识库 |

### `guards`

| 文件 | 说明 |
| --- | --- |
| `guards/__init__.py` | 安全护栏包标记 |
| `guards/sql_guard.py` | SQL 安全检查，当前只做基础 SELECT 和危险关键字拦截，未来建议接 `sqlglot` |
| `guards/policy_guard.py` | 工具调用权限检查，根据 `PermissionContext` 判断用户是否可用某个工具 |

### `audit`

| 文件 | 说明 |
| --- | --- |
| `audit/__init__.py` | 审计包标记 |
| `audit/logger.py` | 审计日志边界，用于记录谁在什么时间对什么资源执行了什么操作 |

### `metrics`

| 文件 | 说明 |
| --- | --- |
| `metrics/__init__.py` | 指标采集包标记 |
| `metrics/collector.py` | 模型调用指标采集边界，未来记录 token、成本、延迟、模型和状态 |

### `admin`

| 文件 | 说明 |
| --- | --- |
| `admin/__init__.py` | 管理配置包标记 |
| `admin/api.py` | 管理接口 `/api/v1/admin/runtime-config` |
| `admin/schemas.py` | 管理配置响应模型 |

### `db`

| 文件 | 说明 |
| --- | --- |
| `db/__init__.py` | 数据库包标记 |
| `db/base.py` | SQLAlchemy Declarative Base |
| `db/session.py` | 异步数据库 engine 和 session 依赖 |

## 安装与配置

### 1. 环境要求

- Python 3.10+
- pip
- PostgreSQL，可选，生产建议使用
- Superset 5.0+ MCP Server，可选，接入 Superset 时需要

### 2. 安装依赖

```bash
cd D:\ai_agent\superset-agent-service
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 3. 创建配置文件

```bash
copy .env.example .env
```

`.env.example` 内容：

```env
PROJECT_NAME=superset-agent-service
ENVIRONMENT=local
SECRET_KEY=change-me

DATABASE_URL=sqlite+aiosqlite:///./superset_agent_service.db

SUPERSET_MCP_URL=
SUPERSET_MCP_TOKEN=

DEFAULT_MODEL_PROVIDER=openai
DEFAULT_MODEL_NAME=gpt-4.1-mini

MAX_AGENT_STEPS=12
MAX_RUN_SECONDS=120
MAX_SQL_ROWS=1000
```

接入 Superset MCP 时，配置：

```env
SUPERSET_MCP_URL=http://localhost:5008/mcp
SUPERSET_MCP_TOKEN=your-token
```

### 4. 启动应用

```bash
uvicorn superset_agent_service.main:app --host 0.0.0.0 --port 8000 --reload
```

访问：

- API 文档：http://localhost:8000/docs
- OpenAPI JSON：http://localhost:8000/api/v1/openapi.json
- 健康检查：http://localhost:8000/api/v1/health

## API 文档

### 健康检查

```http
GET /api/v1/health
```

响应：

```json
{
  "status": "ok",
  "service": "superset-agent-service"
}
```

### Agent 对话

```http
POST /api/v1/agents/chat
Content-Type: application/json
X-User-Id: alice
X-Tenant-Id: demo
X-Roles: admin

{
  "question": "解释这个 dashboard 为什么成本上涨",
  "dashboard_id": "12",
  "chart_id": "88",
  "filters": {
    "region": "east"
  },
  "time_range": "last 7 days"
}
```

响应：

```json
{
  "run_id": "generated-run-id",
  "answer": "Agent runtime scaffold is ready. Next step: connect Superset MCP tools and replace this placeholder with a LangGraph workflow.",
  "status": "completed"
}
```

### 查询 Run Trace

```http
GET /api/v1/runs/{run_id}
```

响应：

```json
{
  "run_id": "generated-run-id",
  "user_id": "alice",
  "status": "completed",
  "events": [
    {
      "event_type": "run_started",
      "payload": {
        "user_id": "alice",
        "question": "解释这个 dashboard 为什么成本上涨"
      },
      "created_at": "2026-06-05T12:00:00"
    }
  ]
}
```

### 查询运行配置

```http
GET /api/v1/admin/runtime-config
```

响应：

```json
{
  "default_model_provider": "openai",
  "default_model_name": "gpt-4.1-mini",
  "max_agent_steps": 12,
  "max_run_seconds": 120
}
```

## 当前版本能力

当前版本已经具备：

- FastAPI 应用入口
- API 路由聚合
- 环境变量配置
- 临时用户权限上下文
- Agent chat 接口
- Run 创建和事件记录
- Run trace 查询
- Tool Registry 边界
- Skills 业务能力层边界
- MCP Client 边界
- Superset MCP Client 工厂
- RAG Retriever 边界
- SQL Guard 初版
- Policy Guard 初版
- Audit Logger 边界
- Metrics Collector 边界
- Admin Runtime Config 接口

当前版本尚未具备：

- 真实登录注册
- 真实 Superset MCP tool 调用
- 真实 LangGraph 工作流
- 真实 Skill workflow 实现
- 真实 LLM 模型调用
- RAG 向量库接入
- Run / Event 数据库持久化
- Usage Superset Dashboard
- 完整 RBAC / SSO / JWT
- 单元测试和集成测试

## 数据模型规划

后续建议持久化以下核心表：

```text
agent_runs
- id
- user_id
- tenant_id
- agent_id
- status
- started_at
- completed_at
- total_tokens
- total_cost_usd
- latency_ms
- error_message

agent_run_events
- id
- run_id
- event_type
- sequence_no
- payload_json
- status
- latency_ms
- created_at

agent_model_calls
- id
- run_id
- provider
- model
- input_tokens
- output_tokens
- total_tokens
- cost_usd
- latency_ms
- status
- error_code
- created_at

agent_tool_calls
- id
- run_id
- tool_name
- input_json
- output_json
- status
- latency_ms
- error_message
- created_at

agent_audit_logs
- id
- user_id
- action
- resource_type
- resource_id
- metadata_json
- created_at
```

这些表可以直接作为 Superset Dashboard 的数据源，用来分析：

- 哪个用户用得最多
- 哪个模型最贵
- 哪个 Agent 最慢
- 哪类错误最多
- Reflection 是否提升成功率
- token 和成本的日趋势

## Superset 集成建议

建议分两层：

```text
系统内 Agent 页面
- 展示单次 run trace
- 展示执行时间线
- 展示工具调用、模型调用、错误和 Reflection

Superset Dashboard
- 展示长期趋势
- 展示模型占比
- 展示用户排行
- 展示成本和 token
- 展示失败率和延迟
```

Superset MCP 负责提供 Superset 工具能力，Agent Service 负责：

- 用户身份和权限上下文
- LangGraph 编排
- RAG 和业务知识
- SQL / Tool 安全控制
- Audit 和 Metrics
- Run Trace

## 推荐演进路线

### 阶段 1：MVP

1. 保留当前骨架
2. 接入 Superset MCP tool list 和 tool call
3. 把 `LangGraphRuntime.invoke()` 替换成简单 LangGraph workflow
4. 记录 model_call、tool_call、run_completed 事件
5. 把 run trace 从内存改成数据库

### 阶段 2：可观测性

1. 新增 `agent_runs` 和 `agent_run_events` 表
2. 新增 token、cost、latency 采集
3. 新增 Superset Usage Dashboard
4. 新增错误中心和慢调用分析

### 阶段 3：安全治理

1. 接老系统登录或 Superset SSO
2. 完善 RBAC 和 tenant 隔离
3. 用 `sqlglot` 强化 SQL Guard
4. 增加高风险工具审批
5. 增加审计日志持久化

### 阶段 4：智能能力

1. 接 RAG 向量库
2. 加 Reflection 节点
3. 加 Planner 节点
4. 加模型路由和 fallback
5. 加评估数据集和自动测试

## 开发备注

- 当前 `legacy_user_service/` 是从旧项目改名保留下来的代码，后续可以迁移其中的用户注册、登录、JWT 能力。
- 当前 `auth/dependencies.py` 通过请求头模拟登录用户，不适合生产。
- 当前 `runs/service.py` 用内存字典存储 trace，服务重启后数据会丢失。
- 当前 `SQLGuard` 只是基础字符串检查，生产环境必须改为 AST 解析。
- 当前 `MCPClient` 是最小占位实现，正式接入 Superset MCP 时要根据实际协议和认证方式调整。

