# AI Quant Terminal

面向美股、港股和 A 股的量化研究与模拟交易课程项目，采用前后端分离的 Monorepo 结构。Python 负责确定性计算，LLM 负责解释结构化证据；不接入真实资金交易，不构成投资建议。

## 页面与当前边界

| 页面 | 主要内容 |
| --- | --- |
| 市场总览 | 指数、走势、自选列表、市场宽度和行业表现 |
| 个股研究 | 标的搜索、价格与成交量、基本面、估值、新闻及量化指标 |
| AI 研究 | 研究问题、标的、公开执行轨迹、工具调用、证据和摘要 |
| 策略实验室 | 自然语言解析、人工调整条件、策略草案与保存 |
| 回测中心 | 回测任务、绩效指标、权益曲线、基准比较和模拟成交 |
| 模拟组合 | 本地模拟账户、持仓估值、模拟订单、成交和风险检查 |
| 实时监控 | 监控快照、信号、事件及其时间与数据来源 |

项目仍在迭代，不是所有区域都已接入真实数据。YahooFinance 路径可读取公开行情，但可能延迟、限流或不可用；基本面、行业数据、历史任务和 seed 记录仍可能为 Mock。监控的 REST 轮询不等同于 WebSocket 行情推送，数据库中的回测快照也不代表真实历史回测已验收。请逐项检查页面的 `source`、`data_status`、数据时间和回退提示，不要仅凭顶部标签判断整页真实性。

## 技术与目录

当前运行依赖以 `front/package.json` 和 `backend/pyproject.toml` 为准：

- 前端：React、TypeScript、Ant Design Pro / Ant Design、Umi Max、React Query、Day.js、Vitest。
- 后端：Python 3.12+、FastAPI、Pydantic v2、SQLAlchemy 2、PyMySQL、pytest。
- 数据库：MySQL；百炼 LLM 与 Tavily / SerpAPI 搜索为可选外部服务。
- Redis、Celery、LangGraph 等规划技术不属于本说明中的最小启动前提。

```text
backend/
  app/api/        HTTP 路由
  app/core/       配置、市场上下文和基础规则
  app/schemas/    API 数据结构
  app/models/     数据库模型
  app/db/         数据库会话、Repository、初始化和 seed
  app/providers/  外部行情与搜索适配
  app/services/   业务编排
  app/quant/      确定性量化计算
  app/agents/     研究编排与 LLM 客户端
  app/tools/      Agent 工具
  tests/          后端测试
front/            前端应用，源码位于 src/，代理配置位于 config/
```

本机 `docs/`、`front/docs/` 和 `Process/` 为开发文档、UI 参考及课程过程材料，不随源码仓库提交；新克隆环境的启动说明以本 README 为入口。

## 最小本地启动（Windows PowerShell）

准备 Python 3.12+、Node.js 22+、npm。以下命令从项目根目录开始，前后端分别使用一个终端。此路径默认 Mock，无需数据库或 API Key。

### 1. 后端

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".\backend[dev]"
# 仅首次缺少 backend/.env 时复制；不要覆盖已有密钥和数据库配置。
if (-not (Test-Path backend\.env)) { Copy-Item backend\.env.example backend\.env }
Set-Location backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

配置由 `app.core.config.Settings` 读取**当前工作目录**的 `.env`。按上述方式运行，生效的是 `backend/.env`，根目录 `.env` 不会自动合并。两份 `.env.example` 参数一致，仅为无真实凭证的模板；修改生效配置后需重启后端。

- 健康检查：<http://localhost:8001/health>，预期 `{"status":"ok"}`。
- API 文档：<http://localhost:8001/docs>。
- 健康检查成功仅表示进程可用，不代表 MySQL、公开行情或 LLM 均已连接。

### 2. 前端（新终端，项目根目录）

```powershell
Set-Location front
npm ci
npm run dev
```

访问 <http://localhost:8002/dashboard>。当前开发脚本指定 8002，`/api/` 请求经 Umi 开发代理转发到后端 8001。若端口占用，先确认占用进程；以启动日志确认的实际监听端口为准，不要误打开后端端口。

`npm run dev` 关闭 Umi 的前端 Mock，但后端仍可使用 `DATA_PROVIDER=mock`，两者不是同一个开关。生产构建不带开发代理，需要部署环境另配 `/api/` 反向代理；本项目的本地启动不等于生产部署。

## 可选配置

以下内容均修改本机 `backend/.env`，不是把凭证写入模板或前端。

### MySQL 持久化

1. 启动 MySQL，在本地开发实例创建库：

```sql
CREATE DATABASE ai_quant_terminal CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

2. 配置 `DATABASE_URL`，替换用户、密码和库名。优先使用仅能访问该开发库的用户，密码包含 URL 特殊字符时需编码。
3. 在 `backend` 目录执行：

```powershell
..\.venv\Scripts\python.exe -m app.db.init_db
..\.venv\Scripts\python.exe -m app.db.seed
```

`init_db` 按当前 ORM 模型创建缺失表，不是完整数据库迁移工具；`seed` 会写入或更新开发样本，不要对生产库或需保留的演示数据随意重复执行。课程材料中的 SQL 图模脚本不替代当前 ORM 初始化入口。

4. 按模块开启 `ENABLE_*_DATABASE_READS`，需要保存任务、策略、回测或模拟订单时再开启对应 `ENABLE_*_DATABASE_WRITES`。全部开关见 `.env.example`；默认关闭。数据库保存的是样本还是真实来源数据，需要检查记录来源，不因入库而改变其性质。

### 无 Key 公开行情

```dotenv
DATA_PROVIDER=real
REAL_PROVIDER_NAME=YahooFinance
REAL_PROVIDER_BASE_URL=https://query1.finance.yahoo.com
REAL_PROVIDER_API_KEY_ENV=
ENABLE_STOCK_DATABASE_READS=false
```

YahooFinance 路径无需行情 Key，但依赖网络可达性和公开接口可用性，不保证实时性或三市场所有字段齐全。建议个股数据库读取保持关闭，防止 seed 快照覆盖 Provider 行情。失败时观察不可用或 Mock 回退提示；授权用途和数据使用条款应自行核实。

### 百炼摘要与新闻搜索

- 百炼：`ENABLE_LLM_RESEARCH=true`，填写 `BAILIAN_API_KEY`、`BAILIAN_BASE_URL`，选择账户可用的 `BAILIAN_MODEL`。Base URL 必须匹配账户地域和模型服务；超时及摘要长度由模板中的参数控制。
- 搜索：`SEARCH_PROVIDER=tavily` 或 `serpapi`，填写 `SEARCH_API_KEY`；默认 `mock` 不调用真实搜索。
- 这些服务可能产生费用，不是最小启动前提。LLM 不替代量化计算，也不会自动提交真实交易。需保存和查询研究任务时，先完成 MySQL 初始化，再开启 AI 研究的数据库读写开关。

## 验证与常见问题

在 `backend` 目录运行 `..\.venv\Scripts\python.exe -m pytest`；在 `front` 目录运行 `npm test`、`npm run tsc` 和 `npm run build`。测试通过不等于外部行情、LLM、搜索或真实历史回测已经验收，需要分别联调。

- 前端 504：检查后端 8001 是否运行，以及 `front/config/proxy.ts` 的目标地址。
- 后端 `/` 或 `/dashboard` 返回 404：后端不托管前端页面，应打开前端地址。
- 修改配置无效：确认改的是运行目录下的 `.env` 并重启后端；已有 `.env` 不会被模板更新自动覆盖。
- 数据库读取失败：先检查 MySQL、连接串、表结构和 seed，再开启对应开关。

## GitHub 提交范围与安全检查

上传源码、测试、依赖清单、`front/package-lock.json`、已脱敏的配置模板及必要文档。保留 `front/LICENSE` 等第三方许可；它不自动决定整个项目的授权，未确认前不要擅自改成 MIT 等开源许可。

根目录 `.gitignore` 排除真实 `.env`、私钥、依赖、缓存、构建产物、本地数据库文件、`outputs/`、私人开发目录以及 `docs/`、`front/docs/`、`Process/` 中的开发和课程材料。初始化和 seed 使用 `backend/app/db/` 的代码，不依赖课程材料中的 SQL 图模脚本。额外的明文 SQL 数据备份也需筛除，不要误把真实数据当作建表脚本。

初始化 Git 后、提交前检查：

```powershell
git check-ignore -v .env backend/.env front/node_modules front/dist outputs
git add .
git status --short
git diff --cached --stat
git diff --cached -- .env.example backend/.env.example
```

确认没有真实凭证再提交。`.gitignore` 不会取消已跟踪文件，也不扫描密钥；密钥若曾上传，必须撤销并重新生成，同时处理历史记录。GitHub 单个普通文件不能超过 100 MiB，大附件应筛除或另行评估 Git LFS。

开发文档和课程材料仍保留在原作者本机，但不是运行依赖。API 请求结构可在后端启动后通过 `/docs` 查看；实际能力需结合代码、配置和页面来源标签判断，不将规划能力视为已经完成。
