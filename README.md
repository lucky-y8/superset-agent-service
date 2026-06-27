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
- **PostgreSQL + asyncpg**：持久化 Agent Run Trace，开发和生产使用同一套迁移流程

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
| `api/router.py` | 聚合 health、agents、runs、admin、mcp、rag 路由 |
| `api/health.py` | 健康检查接口 `/api/v1/health` |

### `auth`

| 文件 | 说明 |
| --- | --- |
| `auth/__init__.py` | 认证包标记 |
| `auth/schemas.py` | `PermissionContext`，描述当前用户、租户、角色、可用工具和 MCP Bearer Token |
| `auth/dependencies.py` | 生产模式从 Superset Agent Token 构造权限上下文，本地开发可使用请求头兜底 |
| `auth/superset_token.py` | 调用 Superset Token 校验接口，获取真实用户身份、工具范围和 MCP Token |

### `agents`

| 文件 | 说明 |
| --- | --- |
| `agents/__init__.py` | Agent 包标记 |
| `agents/api.py` | Agent 对话接口 `/api/v1/agents/chat` 和 WebSocket 接口 `/api/v1/agents/ws` |
| `agents/schemas.py` | Agent 请求和响应模型 |
| `agents/service.py` | Agent 应用服务，负责创建 run、调用 runtime、处理完成和失败 |
| `agents/runtime.py` | LangGraph Runtime，负责模型推理、MCP 工具调用、SQL Guard、Policy Guard 和 RAG 检索 |

### `runs`

| 文件 | 说明 |
| --- | --- |
| `runs/__init__.py` | Run trace 包标记 |
| `runs/api.py` | Run trace 查询接口 `/api/v1/runs/{run_id}` |
| `runs/schemas.py` | `RunEvent` 和 `RunTrace` 数据模型 |
| `runs/service.py` | 基于 PostgreSQL/SQLAlchemy 的 Run Trace 持久化服务，记录生命周期、事件、耗时和 Token |

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
| `rag/api.py` | 知识库上传、文档列表和语义检索接口 `/api/v1/rag/*` |
| `rag/schemas.py` | 知识库文档、上传结果和检索结果的数据模型 |
| `rag/models.py` | `knowledge_documents`、`knowledge_chunks` ORM 模型 |
| `rag/service.py` | 协调 OSS、PostgreSQL、通义 Embedding 和 Qdrant 的入库/检索服务 |
| `rag/text.py` | TXT、Markdown、CSV、Excel、Word、PDF 文本解析和切片 |
| `rag/embedding.py` | 通义 `text-embedding-v4` 向量生成客户端 |
| `rag/storage.py` | 阿里云 OSS 原始文件存储适配器 |
| `rag/vector_store.py` | Qdrant 向量写入和权限过滤检索适配器 |
| `rag/retriever.py` | Runtime 使用的 RAG 检索边界，未开启 RAG 时不会触网 |

### `memory`

| 文件 | 说明 |
| --- | --- |
| `memory/__init__.py` | 长期记忆包标记 |
| `memory/api.py` | 长期记忆查询、写入和删除接口 `/api/v1/memories` |
| `memory/schemas.py` | 长期记忆 API 数据模型 |
| `memory/models.py` | `agent_memories` ORM 模型 |
| `memory/service.py` | 保留的结构化长期记忆服务，用于手动记忆和兼容 API |
| `memory/semantic.py` | 基于通义 Embedding + Qdrant 的对话语义长期记忆，Runtime 当前使用这一套 |

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
- PostgreSQL 14+，用于持久化 Agent Run Trace
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

# 格式：postgresql+asyncpg://用户名:密码@主机:端口/数据库名
DATABASE_URL=postgresql+asyncpg://postgres:your-password@127.0.0.1:5432/superset_agent_service

SUPERSET_MCP_URL=http://127.0.0.1:9009/mcp
SUPERSET_MCP_TOKEN=

SUPERSET_AGENT_TOKEN_VERIFY_URL=http://127.0.0.1:8088/api/v1/agent/token/verify
SUPERSET_AGENT_SERVICE_KEY=

OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_API_KEY=
OPENAI_MODEL=deepseek-chat

MAX_AGENT_STEPS=24
MAX_RUN_SECONDS=240
MAX_SQL_ROWS=1000
AGENT_GUIDED_MODE=false
AGENT_DELEGATE_AUTH_TO_MCP=true

RAG_ENABLED=false
RAG_TOP_K=5
RAG_CHUNK_SIZE=900
RAG_CHUNK_OVERLAP=120

EMBEDDING_PROVIDER=dashscope
EMBEDDING_MODEL=text-embedding-v4
EMBEDDING_DIM=1024
DASHSCOPE_API_KEY=
DASHSCOPE_EMBEDDING_URL=https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings

QDRANT_URL=http://127.0.0.1:6333
QDRANT_COLLECTION=superset_agent_knowledge
QDRANT_MEMORY_COLLECTION=superset_agent_memory
QDRANT_API_KEY=
SEMANTIC_MEMORY_TOP_K=5

OSS_REGION=cn-hangzhou
OSS_ENDPOINT=
OSS_BUCKET=
OSS_ACCESS_KEY_ID=
OSS_ACCESS_KEY_SECRET=
OSS_PREFIX=superset-agent-knowledge
```

其中：

- `DATABASE_URL`：Agent Service 自己使用的数据库连接，用于保存运行状态和事件。
- `SUPERSET_MCP_URL`：Superset MCP 的 Streamable HTTP 地址。
- `SUPERSET_MCP_TOKEN`：MCP 开启 Bearer Token 认证时填写；未开启可留空。
- `SUPERSET_AGENT_TOKEN_VERIFY_URL`：Agent Service 调用 Superset 校验短期 Agent Token 的接口地址。配置后，HTTP 和 WebSocket Agent 请求都不再信任前端传入的 `user_id`、`roles`。
- `SUPERSET_AGENT_SERVICE_KEY`：Agent Service 调 Superset 校验接口时携带的服务间密钥；如果 Superset 后端暂未校验该请求头，可以先留空。
- `OPENAI_BASE_URL`：OpenAI 兼容模型接口地址，当前使用 DeepSeek。
- `OPENAI_API_KEY`：模型 API Key，只写入本地 `.env`，不要提交到 Git。
- `OPENAI_MODEL`：模型名称，当前使用 `deepseek-chat`。
- `RAG_ENABLED`：是否启用知识库检索。未启用时 Runtime 不会连接 Qdrant 或 Embedding 服务。
- `DASHSCOPE_API_KEY`：通义 Embedding API Key，只写入本地 `.env`，不要提交到 Git。
- `QDRANT_URL` / `QDRANT_COLLECTION`：Qdrant 向量库地址和集合名称。
- `QDRANT_MEMORY_COLLECTION`：长期语义记忆使用的 Qdrant 集合，默认 `superset_agent_memory`。
- `SEMANTIC_MEMORY_TOP_K`：每次 Agent 推理前检索多少条相似历史对话。
- `OSS_REGION` / `OSS_BUCKET`：阿里云 OSS Bucket 地域和名称，用于保存上传原始文件。
- `OSS_ACCESS_KEY_ID` / `OSS_ACCESS_KEY_SECRET`：OSS 访问凭证，建议使用 RAM 子账号最小权限。

### 4. 创建 PostgreSQL 数据库

先确认 PostgreSQL 服务已经启动，然后通过 Navicat、psql 或其他数据库工具执行：

```sql
CREATE DATABASE superset_agent_service;
```

这条命令只创建空数据库。项目表结构由 Alembic 管理，不需要手动创建
`agent_runs`、`agent_run_events`、`knowledge_documents`、`knowledge_chunks`
或 `agent_memories` 表。

### 5. 使用 Alembic 创建和迁移表结构

以下命令都需要在项目根目录 `D:\ai_agent\superset-agent-service` 中执行。

#### 首次建表或升级到最新版本

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

用途：

- 读取 `.env` 中的 `DATABASE_URL` 并连接 PostgreSQL。
- 按顺序执行尚未执行的迁移脚本。
- 首次执行时创建 `alembic_version`、`agent_runs`、`agent_run_events`、
  `knowledge_documents`、`knowledge_chunks` 和 `agent_memories`。
- `head` 表示升级到当前代码包含的最新迁移版本。

#### 查看数据库当前迁移版本

```powershell
.\.venv\Scripts\python.exe -m alembic current
```

用途：查看数据库已经执行到哪个版本。当前项目正常应显示：

```text
20260622_0004 (head)
```

#### 查看全部迁移历史

```powershell
.\.venv\Scripts\python.exe -m alembic history
```

用途：按顺序查看项目已有的迁移版本及其说明，排查数据库版本差异时使用。

#### ORM 模型变化后生成新迁移

```powershell
.\.venv\Scripts\python.exe -m alembic revision --autogenerate -m "add run duration"
```

用途：比较 SQLAlchemy ORM 模型与当前数据库结构，自动生成一个新的迁移文件。
生成后必须人工检查 `alembic/versions/` 中的脚本，再执行：

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

注意：修改 ORM 模型后不要重复修改已有迁移，应新增迁移版本。

#### 回退最近一次迁移

```powershell
.\.venv\Scripts\python.exe -m alembic downgrade -1
```

用途：撤销最近执行的一次迁移。回退可能删除表或字段并造成数据丢失，执行前应先备份数据库。

#### 只生成 SQL，不实际修改数据库

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head --sql
```

用途：输出 Alembic 即将执行的 SQL，适合上线前审查；该命令不会连接或修改数据库。

### 6. 启动应用

```powershell
.\.venv\Scripts\python.exe -m uvicorn superset_agent_service.main:app --host 127.0.0.1 --port 30000 --reload
```

访问：

- Agent 调试页面：http://127.0.0.1:30000/debug
- API 文档：http://127.0.0.1:30000/docs
- OpenAPI JSON：http://127.0.0.1:30000/api/v1/openapi.json
- 健康检查：http://127.0.0.1:30000/api/v1/health

### 7. 测试前端页面

项目内置了一个本地测试前端页面：

```text
http://127.0.0.1:30000/debug
```

这个页面用于调试 Agent 对话、WebSocket 实时推送、执行步骤、Run Trace 摘要和历史会话恢复。
页面代码在：

- `superset_agent_service/static/debug.html`
- `superset_agent_service/static/debug.css`
- `superset_agent_service/static/debug.js`

当前 `/debug` 页面主要覆盖 Agent 对话测试，还没有加入 RAG 文件上传控件。
RAG 上传和检索第一版先通过 `/api/v1/rag/documents`、`/api/v1/rag/search`
接口测试；后续可以把知识库上传、文档列表和检索结果展示集成到该页面或 Superset 前端页面。

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
Authorization: Bearer <superset-issued-agent-token>

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

生产环境中，`Authorization` 里的 Token 由 Superset 后端
`/api/v1/agent/token/` 接口签发。Agent Service 收到请求后，会调用
`SUPERSET_AGENT_TOKEN_VERIFY_URL` 指向的 Superset 校验接口获取真实用户身份，
不会信任前端传入的 `user_id` 或 `roles`。

WebSocket 请求建议每次运行时在消息体中携带 Token：

```json
{
  "type": "run",
  "token": "<superset-issued-agent-token>",
  "request": {
    "question": "请查询 Superset 中现有的仪表盘，返回前 5 个仪表盘的 ID、标题和发布状态。",
    "filters": {}
  }
}
```

也兼容字段名 `agent_token` 或 `access_token`。不建议把 Token 放在 URL query
里，因为 query 更容易进入代理或服务日志。

响应：

```json
{
  "run_id": "generated-run-id",
  "answer": "Agent runtime scaffold is ready. Next step: connect Superset MCP tools and replace this placeholder with a LangGraph workflow.",
  "status": "completed"
}
```

### RAG 知识库

RAG 功能默认通过 `RAG_ENABLED` 控制。开启后，上传文件会保存原始文件到阿里云 OSS，
把解析后的文本切片写入 PostgreSQL，并把通义 `text-embedding-v4` 生成的向量写入
Qdrant。Agent Runtime 在回答前会按当前用户身份检索知识库，把相关片段放入模型上下文。

#### 上传知识文档

```http
POST /api/v1/rag/documents
Authorization: Bearer <superset-issued-agent-token>
Content-Type: multipart/form-data

file=@需求说明.docx
```

支持的第一批文件类型：

- `.txt`
- `.md`
- `.csv`
- `.xlsx`
- `.xlsm`
- `.docx`
- `.pdf`

响应：

```json
{
  "document": {
    "document_id": "generated-document-id",
    "filename": "需求说明.docx",
    "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "status": "indexed",
    "owner_user_id": "4",
    "access_scope": "owner",
    "chunk_count": 12,
    "error_message": null,
    "created_at": "2026-06-22T12:00:00Z",
    "updated_at": "2026-06-22T12:00:03Z"
  },
  "message": "Document indexed with 12 chunks."
}
```

#### 查询当前用户文档

```http
GET /api/v1/rag/documents
Authorization: Bearer <superset-issued-agent-token>
```

#### 语义检索知识库

```http
POST /api/v1/rag/search
Authorization: Bearer <superset-issued-agent-token>
Content-Type: application/json

{
  "query": "这个项目的权限认证流程是什么？",
  "limit": 5
}
```

检索结果会按当前用户 `owner_user_id` 过滤，避免不同用户之间互相检索知识文档。

### 长期记忆

长期记忆和 RAG 不同：

- RAG 存外部知识文档，例如 Word、Excel、PDF、业务说明。
- 长期记忆存用户和 Agent 的历史对话，用于跨会话语义回忆。

当前 Runtime 使用的是企业更常见的语义记忆方案：

```text
用户问题 + Agent 回答
  -> 通义 text-embedding-v4 向量化
  -> 写入 Qdrant 集合 superset_agent_memory
  -> 下次提问前按 user_id + tenant_id 过滤并语义检索
  -> 放入 long_term_memory.semantic_conversations
```

Runtime 会自动做两件事：

1. 每次推理前，用当前问题去 Qdrant 检索当前用户的相似历史对话。
2. 最终回答生成后，把本轮 `question + answer` 向量化写入 Qdrant。

Qdrant payload 会保存：

- `memory_type=conversation`
- `user_id`
- `tenant_id`
- `run_id`
- `question`
- `answer`
- `text`
- `created_at`

#### 结构化记忆兼容接口

项目仍保留 `/api/v1/memories` 结构化记忆接口，用于手动记忆、偏好或后续兼容。
但 Runtime 当前主路径不再依赖 `agent_memories` 表，而是使用 Qdrant 语义记忆。

查询结构化记忆：

```http
GET /api/v1/memories?limit=50
Authorization: Bearer <superset-issued-agent-token>
```

也可以按类型过滤：

```http
GET /api/v1/memories?memory_type=resource_ref
Authorization: Bearer <superset-issued-agent-token>
```

常见 `memory_type`：

- `preference`：用户偏好，例如默认图表语言、常用图表类型
- `note`：人工保存的重要备注
- `resource_ref`：兼容旧结构化资源引用

手动写入或更新结构化记忆：

```http
POST /api/v1/memories
Authorization: Bearer <superset-issued-agent-token>
Content-Type: application/json

{
  "memory_type": "preference",
  "memory_key": "chart_language",
  "memory_value": {
    "value": "zh-CN"
  },
  "source": "manual",
  "confidence": 1.0,
  "description": "用户希望图表名称优先使用中文。"
}
```

删除结构化记忆：

```http
DELETE /api/v1/memories/{memory_id}
Authorization: Bearer <superset-issued-agent-token>
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
2. 已接入 Superset MCP tool list 和 tool call
3. 已实现 DeepSeek + LangGraph 工具调用 workflow
4. 已记录 plan、tool_call、run_completed 等运行事件
5. 已使用 SQLAlchemy + Alembic 持久化 Run Trace

### 阶段 2：可观测性

1. 新增 `agent_runs` 和 `agent_run_events` 表
2. 新增 token、cost、latency 采集
3. 新增 Superset Usage Dashboard
4. 新增错误中心和慢调用分析

### 阶段 3：安全治理

1. 接老系统登录或 Superset SSO
2. 完善 RBAC 和 tenant 隔离
3. 已使用 `sqlglot` AST 强化 SQL Guard，并限制最大返回行数
4. 增加高风险工具审批
5. 增加审计日志持久化

### 阶段 4：智能能力

1. 已接入第一版 RAG：通义 `text-embedding-v4`、Qdrant、PostgreSQL、阿里云 OSS
2. 已接入长期语义记忆：每轮对话通过通义 `text-embedding-v4` 向量化，按用户写入 Qdrant `superset_agent_memory` 集合
3. 已接入建图任务专项策略：Runtime 会识别查询、RAG、建图、建看板任务，并为建图任务注入 `chart_context`
4. 加 Reflection 节点
5. 加 Planner 节点
6. 加模型路由和 fallback
7. 加评估数据集和自动测试

## 开发备注

- 当前 `legacy_user_service/` 是从旧项目改名保留下来的代码，后续可以迁移其中的用户注册、登录、JWT 能力。
- 当前 `auth/dependencies.py` 在配置 `SUPERSET_AGENT_TOKEN_VERIFY_URL` 后会通过 Superset 校验 Agent Token；未配置时才使用请求头作为本地开发兜底。
- 当前 `runs/service.py` 已异步写入数据库；生产环境应使用 PostgreSQL，并在部署前执行 `alembic upgrade head`。
- 当前 `SQLGuard` 已使用 `sqlglot` 进行 AST 解析，可拒绝写操作、多语句和动态 LIMIT。
- 当前 `MCPClient` 已支持 Streamable HTTP / SSE 解析和 Bearer Token 传递；生产环境需要保证 Superset MCP 能正确识别当前用户。
- 当前 RAG 第一版按上传用户隔离文档；企业版后续可扩展部门、角色、项目空间、文档级 ACL 和审批流程。
- 当前 Runtime 使用 Qdrant 语义长期记忆，按 `user_id + tenant_id` 过滤历史对话；`agent_memories` 表和 `/api/v1/memories` 作为结构化记忆兼容接口保留。
- 当前 Runtime 对建图任务使用更高步数预算和建图专用 Prompt；如果用户说“刚生成的数据集”，会优先从语义记忆和请求上下文抽取最近的 `dataset_id`，找不到时要求用户补充数据集 ID 或名称。
- 当前 Runtime 会在调用 `generate_chart` 前规范化常见建图参数：从请求上下文补 `dataset_id`，把 `title/chart_name` 映射为 `slice_name`，把 `chart_type` 映射为 `viz_type`，并记录 `chart_arguments_normalized` 事件。
- 当前 `AGENT_GUIDED_MODE=false` 默认关闭；改为 `true` 后，创建数据集、图表、看板会先进入独立 Planner 节点。Planner 会生成结构化计划和缺失信息列表，缺少数据库连接、数据来源、图表类型、看板名称等必要信息时先提问，信息齐全后才进入 ReAct 工具执行。
- 当前 `AGENT_DELEGATE_AUTH_TO_MCP=true` 默认开启，业务工具权限交给 Superset MCP 判断；Agent Service 仍校验 Token、执行 SQLGuard/Reflection，但不再把 Token verify 返回的 `allowed_tools` 当作 MCP 工具白名单，避免“工具可见但 Agent 自己拒绝调用”。
- 当前 Runtime 已接入 Reflection 节点：每轮工具执行后会检查 observation，权限错误和危险 SQL 会立即停止，可恢复的参数/工具错误会交回模型进行一次修正。
- Runtime 相关单测可使用 `D:\App\python3.13\python.exe -B -m unittest discover -s test -p 'test_agent_runtime.py' -v` 运行。

