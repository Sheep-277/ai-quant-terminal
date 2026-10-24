# AI Quant Terminal - Codex Development Rules

## 1. Project Goal

本项目为 AI Quant Terminal。

目标是构建一个支持美股、港股、A股的 AI 原生量化研究、
策略验证、实时监控与模拟交易平台。

所有开发必须优先遵守：

1. docs/PRD.md
2. docs/ARCHITECTURE.md
3. docs/API.md
4. 本文件 AGENTS.md

如果文档之间存在冲突，应停止修改并向用户说明。

---

## 2. Learning Mode

当前项目采用学习式开发模式。

除非用户明确解除限制，否则：

1. 单次任务不限制修改文件数量，但必须控制范围、保持编码质量并完成相应验证，不因追求速度扩大业务目标。
2. 单次任务仍必须围绕一个清晰开发目标，避免把多个无关模块混在一起。
3. 不允许为了让当前代码运行而顺手修改无关业务文件。
4. 当前文件依赖尚未实现模块时，只实现本次目标所需的最小依赖。
5. 空 __init__.py 等纯包初始化文件可以作为例外自动创建。
6. 不进行大规模重构。
7. 不批量生成无业务含义的 boilerplate。
8. 每次完成当前目标后停止，不自动继续开发下一阶段。
9. 涉及金融/量化专业名词时，同步在 docs/GLOSSARY.md 用中文补充解释。

---

## 3. Before Editing

修改文件前必须先说明：

- 文件路径
- 文件职责
- 所属架构层
- 为什么现在需要它
- 依赖哪些已有文件
- 未来哪些文件会依赖它
- 本次准备实现的内容

用户明确同意或任务已经明确要求后再修改。

---

## 4. After Editing

修改完成后必须解释：

- 每个 import 的作用
- 每个类的作用
- 每个函数的作用
- 重要字段和类型
- 关键 Python / TypeScript 语法
- 当前设计原因
- 可替代方案（如重要）
- 当前文件在整个调用链中的位置

最后只推荐下一步最合理开发的一个文件，不自动修改。

---

## 5. Scope Control

不得自行：

- 修改 PRD 核心需求
- 增加一级页面
- 删除一级页面
- 改变 FAST PATH / AI PATH 双路径设计
- 改变核心 Agent 架构
- 增加真实资金自动交易
- 增加高频交易
- 增加期权/期货等 V1 未规划的大模块
- 更换核心技术栈

如认为需求需要修改，先提出建议，等待用户批准。

---

## 6. Core Technology Stack

Frontend:
- React
- TypeScript
- Ant Design Pro
- Ant Design
- Ant Design X
- Lightweight Charts
- Apache ECharts

Backend:
- Python 3.12
- FastAPI
- Pydantic v2
- SQLAlchemy 2
- MySQL
- Redis
- Celery
- LangGraph
- pandas
- NumPy

未经用户批准，不替换核心框架。

---

## 7. Backend Layer Responsibilities

### core/
基础配置、市场上下文、通用类型、异常和基础规则。

### schemas/
Pydantic API Request / Response Schema。

### models/
SQLAlchemy 持久化模型。

### providers/
第三方数据源、新闻源和 Broker 的 Adapter。

### services/
业务逻辑和 Provider 编排。

### quant/
确定性量化计算，包括：
- indicators
- factors
- strategy
- backtest
- risk
- signals

### tools/
将已有业务或 Quant 能力封装为 Agent Tool。

### agents/
AI PATH，包括研究规划、Agent 协作和解释。

### realtime/
FAST PATH，包括实时行情、实时特征和 Signal。

### api/routes/
仅负责 HTTP 层，不放核心业务逻辑。

---

## 8. AI / Quant Boundary

核心原则：

Python 负责计算。
LLM 负责理解、规划、解释和非结构化信息分析。

禁止：

- 让 LLM 手算量化指标
- 让 LLM 替代 Quant Engine
- 让 Agent 绕过 Risk Engine
- 让 Agent 直接提交真实订单
- 用自然语言结论替代结构化数值证据

---

## 9. Multi-Market Rules

系统支持：

- US
- HK
- CN

所有市场相关请求和数据必须显式携带 market。

禁止仅根据 symbol 猜测市场。

市场差异通过：

- MarketContext
- MarketRules
- Provider Adapter

统一处理。

---

## 10. Provider Rules

业务层不得直接依赖第三方供应商 SDK。

必须通过抽象 Provider。

例如：

MarketService
→ MarketDataProvider
→ AlpacaProvider

不得：

MarketService
→ Alpaca SDK

Provider 输出必须转换成项目自己的统一 Schema。

---

## 11. Data Integrity

所有市场数据应尽量包含：

- market
- symbol
- timestamp
- timezone
- currency
- source

不得使用过期数据冒充实时数据。

如果 Provider 返回延迟或不可用数据，应显式标记。

---

## 12. Financial Calculation Rules

量化计算必须：

- 可重复
- 可测试
- 有明确输入输出
- 有时间边界
- 避免 Look-ahead Bias
- 避免 Future Data

回测不得使用当时尚未公开的信息。

---

## 13. Security

禁止：

- 在代码中硬编码 API Key
- 将真实密钥提交到 Git
- 在前端暴露 Broker Secret
- 默认启用真实交易

敏感配置通过环境变量加载。

---

## 14. Code Quality

代码应：

- 有完整类型标注
- 命名清晰
- 避免过度抽象
- 避免重复逻辑
- 使用中文 docstring 解释业务含义
- 优先小函数、小模块
- 遵守现有项目代码风格

不要为了“未来可能需要”提前设计大量暂时没有用途的抽象。

---

## 15. Testing

确定性核心逻辑应优先测试：

- Market Context
- Symbol
- Provider normalization
- Technical indicators
- Factors
- Backtest
- Risk Engine

Agent 测试重点验证：

- Tool schema
- Routing
- Workflow
- Structured output

不要把 LLM 文本内容本身作为核心测试标准。
