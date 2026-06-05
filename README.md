# Listening-to-Waves 项目文档

## 项目概述

**Listening-to-Waves（倾听波澜）** 是一个智能公共舆情监控与分析系统，提供实时的公众情绪观察、早期风险预警以及舆情智能控制能力。

### 核心功能
- 🔍 智能公共舆情监控
- 📊 公众情绪深度分析
- ⚠️ 早期风险预警
- 🎯 有效响应和引导

## 技术栈

### 后端框架
- **FastAPI** - 现代、高性能的 Web 框架
- **Python 3.9+** - 编程语言
- **SQLAlchemy (Async)** - 异步 ORM
- **PostgreSQL** - 关系型数据库

### 安全与认证
- **JWT (JSON Web Token)** - 身份认证
- **Passlib + Bcrypt** - 密码加密
- **python-jose** - JWT 处理

### 其他工具
- **Pydantic** - 数据验证
- **Uvicorn** - ASGI 服务器
- **Sentry** - 错误监控（可选）

## 项目结构

```
listening-to-waves/
├── README.md
├── listening_ripples/
│   ├── __init__.py
│   ├── main.py                    # 应用入口
│   ├── config.py                  # 配置管理
│   │
│   ├── initialization/            # 路由初始化
│   │   └── __init__.py
│   │
│   ├── extensions/                # 扩展模块
│   │   ├── __init__.py
│   │   └── db_extension.py        # 数据库异步扩展
│   │
│   ├── models/                    # 数据模型
│   │   ├── __init__.py
│   │   ├── helpers.py             # 模型辅助类
│   │   └── users.py               # 用户模型
│   │
│   ├── users/                     # 用户模块
│   │   ├── __init__.py
│   │   ├── api.py                 # API 路由
│   │   ├── crud.py                # 数据库操作
│   │   ├── schemas.py             # 数据模式
│   │   ├── security.py            # 安全功能
│   │   ├── dependencies.py        # 依赖注入
│   │   └── exceptions.py          # 自定义异常
│   │
│   ├── core/                      # 核心功能（待开发）
│   ├── utilities/                 # 工具函数（待开发）
│   └── workers/                   # 后台任务（待开发）
│
└── .env                           # 环境变量配置
```

## 安装与配置

### 1. 环境要求

- Python 3.9+
- PostgreSQL 12+
- pip 或 poetry

### 2. 安装依赖

```bash
pip install fastapi uvicorn sqlalchemy asyncpg pydantic pydantic-settings
pip install python-jose[cryptography] passlib[bcrypt]
pip install sentry-sdk
```

### 3. 配置环境变量

创建 `.env` 文件：

```env
# 数据库配置
POSTGRES_SERVER=127.0.0.1
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
POSTGRES_DB=listening_ripples

# 安全配置
SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=11520

# 应用配置
ENVIRONMENT=local
FRONTEND_HOST=http://localhost:5173
BACKEND_CORS_ORIGINS=["http://localhost:5173"]

# 初始管理员
FIRST_SUPERUSER=admin@example.com
FIRST_SUPERUSER_PASSWORD=your_admin_password

# Sentry（可选）
SENTRY_DSN=
```

### 4. 初始化数据库

```python
# 在 Python 环境中运行
from listening_ripples.extensions.db_extension import async_db

# 创建数据库表
await async_db.create_db_and_tables()
```

### 5. 启动应用

```bash
# 开发模式
python listening_ripples/main.py

# 或使用 uvicorn
uvicorn listening_ripples.main:app --host 0.0.0.0 --port 30011 --reload
```

访问：
- API 文档：http://localhost:30011/docs
- OpenAPI JSON：http://localhost:30011/api/v1/openapi.json

## API 文档

### 用户认证

#### 用户注册
```http
POST /api/v1/users/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "password123",
  "name": "张三",
  "phone_number": "13800138000",
  "bio": "用户简介"
}
```

**响应：**
```json
{
  "id": 1,
  "email": "user@example.com",
  "name": "张三",
  "phone_number": "13800138000",
  "bio": "用户简介",
  "is_active": true,
  "login_count": 0,
  "last_login_at": null,
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T00:00:00"
}
```

#### 用户登录
```http
POST /api/v1/users/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "password123"
}
```

**响应：**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "email": "user@example.com",
    "name": "张三",
    ...
  }
}
```

### 用户管理

#### 获取当前用户信息
```http
GET /api/v1/users/me
Authorization: Bearer <access_token>
```

#### 更新当前用户信息
```http
PUT /api/v1/users/me
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "name": "李四",
  "phone_number": "13900139000",
  "bio": "更新后的简介"
}
```

#### 获取用户列表
```http
GET /api/v1/users/?skip=0&limit=100&active_only=true
Authorization: Bearer <access_token>
```

#### 获取指定用户
```http
GET /api/v1/users/{user_id}
Authorization: Bearer <access_token>
```

#### 停用用户
```http
PATCH /api/v1/users/{user_id}/deactivate
Authorization: Bearer <access_token>
```

#### 激活用户
```http
PATCH /api/v1/users/{user_id}/activate
Authorization: Bearer <access_token>
```

## 数据模型

### User 模型

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键，用户唯一ID |
| email | String | 邮箱（唯一，必填） |
| phone_number | String | 手机号（唯一，可选） |
| name | String | 用户名称（可选） |
| hashed_password | String | 密码哈希值 |
| is_active | Boolean | 账户状态（默认 true） |
| login_count | Integer | 登录次数 |
| last_login_at | DateTime | 上次登录时间 |
| created_at | DateTime | 创建时间 |
| updated_at | DateTime | 更新时间 |
| bio | Text | 个人简介 |
| created_on | DateTime | 审计：创建时间 |
| changed_on | DateTime | 审计：修改时间 |
| created_by | Relationship | 审计：创建人 |
| changed_by | Relationship | 审计：修改人 |

## 安全机制

### JWT 认证流程

1. 用户使用邮箱和密码登录
2. 系统验证凭据并生成 JWT token
3. 客户端在后续请求中携带 token（Header: `Authorization: Bearer <token>`）
4. 系统验证 token 并返回用户信息

### 密码安全

- 使用 bcrypt 算法进行密码哈希
- 密码最小长度：6 位
- 不存储明文密码

### Token 配置

- 默认有效期：8 天（11520 分钟）
- 算法：HS256
- 可在配置文件中自定义

## 配置说明

### Settings 类主要配置项

```python
# API 配置
API_V1_STR = "/api/v1"

# 安全配置
SECRET_KEY = "随机生成的密钥"
ACCESS_TOKEN_EXPIRE_MINUTES = 11520  # 8天

# 前端配置
FRONTEND_HOST = "http://localhost:5173"

# 环境
ENVIRONMENT = "local" | "staging" | "production"

# CORS
BACKEND_CORS_ORIGINS = ["http://localhost:5173"]

# 数据库
POSTGRES_SERVER = "127.0.0.1"
POSTGRES_PORT = 5432
POSTGRES_USER = "postgres"
POSTGRES_PASSWORD = "your_password"
POSTGRES_DB = "listening_ripples"

# 邮件配置（可选）
SMTP_TLS = True
SMTP_PORT = 587
SMTP_HOST = "smtp.example.com"
SMTP_USER = "user"
SMTP_PASSWORD = "password"
EMAILS_FROM_EMAIL = "noreply@example.com"
```

## 开发指南

### 添加新的数据模型

1. 在 `models/` 目录下创建模型文件
2. 继承 `Base` 类
3. 定义表结构和字段
4. 在 `__init__.py` 中导入

```python
from listening_ripples.extensions.db_extension import Base
from sqlalchemy import Column, Integer, String

class NewModel(Base):
    __tablename__ = "new_table"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
```

### 添加新的 API 路由

1. 在相应模块下创建 `api.py`
2. 定义 APIRouter
3. 在 `initialization/__init__.py` 中注册路由

```python
from fastapi import APIRouter

router = APIRouter(prefix="/new-module", tags=["new-module"])

@router.get("/")
async def get_items():
    return {"items": []}
```

### 数据库迁移

建议使用 Alembic 进行数据库迁移：

```bash
# 安装 Alembic
pip install alembic

# 初始化
alembic init alembic

# 创建迁移
alembic revision --autogenerate -m "description"

# 执行迁移
alembic upgrade head
```

## 测试

### 使用 Pytest 进行测试

```bash
# 安装测试依赖
pip install pytest pytest-asyncio httpx

# 运行测试
pytest
```

### 测试示例

```python
import pytest
from httpx import AsyncClient
from listening_ripples.main import app

@pytest.mark.asyncio
async def test_register_user():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/users/register",
            json={
                "email": "test@example.com",
                "password": "password123"
            }
        )
    assert response.status_code == 201
```

## 部署

### Docker 部署

创建 `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY listening_ripples/ ./listening_ripples/

CMD ["uvicorn", "listening_ripples.main:app", "--host", "0.0.0.0", "--port", "30011"]
```

创建 `docker-compose.yml`:

```yaml
version: '3.8'

services:
  db:
    image: postgres:14
    environment:
      POSTGRES_DB: listening_ripples
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data

  app:
    build: .
    ports:
      - "30011:30011"
    depends_on:
      - db
    environment:
      POSTGRES_SERVER: db
      POSTGRES_PORT: 5432

volumes:
  postgres_data:
```

### 生产环境建议

1. 使用 Gunicorn + Uvicorn workers
2. 配置 Nginx 作为反向代理
3. 启用 HTTPS
4. 配置日志收集
5. 设置监控告警（Sentry）
6. 定期备份数据库

## 故障排查

### 常见问题

**数据库连接失败**
- 检查 PostgreSQL 是否运行
- 验证连接字符串配置
- 确认防火墙设置

**JWT Token 无效**
- 检查 SECRET_KEY 配置
- 验证 token 是否过期
- 确认请求头格式正确

**CORS 错误**
- 在 `BACKEND_CORS_ORIGINS` 中添加前端域名
- 检查请求方法是否允许

## 后续开发计划

- [ ] 舆情数据采集模块
- [ ] 情感分析引擎
- [ ] 风险预警系统
- [ ] 数据可视化面板
- [ ] 实时监控推送
- [ ] 报告生成功能
- [ ] 多租户支持
- [ ] 权限管理系统

## 贡献指南

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 许可证

本项目采用 MIT 许可证。

## 联系方式

- 项目主页：listening-to-waves
- 问题反馈：提交 Issue
- 技术支持：联系开发团队

---

**版本：** 0.1.0  
**更新日期：** 2024-12-23