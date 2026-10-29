# Meitai AI Business Innovation Agent Demo

当前仓库实现的是一个可运行的咨询式 Demo，用结构化流程帮助企业完成从问卷到课后跟进的完整链路。

## 版本入口

首页统一进入 `/start`，选择“精简版”或“完整版”。精简版 `/lite` 只必填公司工商全称，可选上传公司介绍；先从真实公开网页生成可追溯画像，确认后再生成四段建议与风险提示。公开资料不足时可补资料或携带公司名转入完整版。完整版原有 14 章节报告、导出和跟进流程保持。

精简版充分的公开资料按规范化公司名在 SQLite 缓存 7 天；来源不足或缺少主营资料的旧缓存会重新检索，上传材料按用户隔离。默认 mock 模式仍需真实联网资料，不伪造来源；Bing RSS / DuckDuckGo 无密钥检索及可选 Brave 配置见 [精简版运行与验收说明](docs/business-lite.md)。

工作台结果摘要显示七项分析的生成进度，完成数量与已保存结果一致，刷新后自动恢复。界面统一使用“管理员”和“前置材料”；历史账号及接口角色保持兼容。

启动配置优先级为显式进程环境变量 > `.env` > `mykey.py` > 默认值。测试时请显式指定独立数据库与 `LLM_MODE=mock`，启动前核对实际路径。

## 完整链路

1. 创建企业问卷（支持导入预填）
2. 生成企业画像
3. 商业模式画布 9 格诊断（九要素问题库增强）
4. 突破要素推荐与选择
5. 创新方向延展
6. 差异化竞争力分析
7. 商业终局设计（私域 + 生态 + OPC + 多路径）
8. AI 场景推荐（方向加权）
9. 分层案例匹配（行业→规模→痛点→方向 + 来源标注）
10. 最终报告生成（14 章节 + 质量审计）
11. 报告导出（Markdown / DOCX / 打印版 / PDF）
12. 课后 30 天跟进任务管理
13. 双周案例推送（去重 + 方案再校准）
14. 管理员工作台（分组/批量点评/CSV 导出）

## 技术栈

- **后端**: FastAPI + SQLAlchemy + SQLite + ChromaDB（可选）
- **前端**: Next.js 15 + TypeScript + Tailwind CSS
- **AI**: OpenAI 兼容接口（可选，默认 Mock 模式）
- **报告导出**: Markdown / HTML / DOCX

## 目录结构

```
.
├── backend/
│   ├── app/
│   │   ├── api/routes/       # 路由层
│   │   ├── core/             # 配置（含 mykey.py 密钥加载）
│   │   ├── db/               # 数据库
│   │   ├── exporters/        # 导出
│   │   ├── models/           # 数据模型
│   │   ├── prompts/          # LLM 提示词
│   │   ├── rag/              # RAG 检索
│   │   ├── schemas/          # Pydantic Schema
│   │   └── services/         # 业务服务
│   ├── data/                 # SQLite / Chroma
│   ├── tests/                # 测试
│   └── run.py                # 入口（端口自动回退）
├── frontend/
│   └── src/
│       ├── app/              # 页面
│       ├── components/       # 组件（含单元测试）
│       └── lib/              # API + 类型
├── knowledge/raw/            # 知识库 YAML
│   ├── ai_scenarios.yaml
│   ├── industry_cases.yaml
│   ├── business_canvas.md
│   ├── report_templates.md
│   └── risk_playbook.md
├── scripts/                  # 启动 / 工具脚本
│   ├── back_start.bat
│   ├── front_start.bat
│   ├── find_port.js          # 端口自动发现
│   └── ngrok_url.js          # ngrok 公网 URL 获取
├── docs/                     # 设计文档
├── start.bat                 # 一键启动（后端 + ngrok + 前端）
├── mykey.py.example          # 密钥配置模板
├── .env.example
├── 使用方法.md                # API 参考与快速启动
├── 使用说明.md                # 面向用户的操作指南（UI 流程 + 常见问题）
└── README.md
```

## 快速开始

### 1. 配置环境

```powershell
Copy-Item .env.example .env
```

默认 Mock 模式即可运行，无需 API Key：

```env
LLM_MODE="mock"
```

如需真实 LLM：

```env
LLM_MODE="live"
OPENAI_API_KEY="sk-..."
OPENAI_BASE_URL="https://api.openai.com/v1"
OPENAI_MODEL="gpt-4o-mini"
LLM_REPORT_ENABLED="true"
```

### 2. 安装依赖

后端（需先配置 conda 环境 `rag-env`，Python 3.11）：

```powershell
cd backend
conda activate rag-env
```

项目依赖由 conda 环境管理，无需 pip install。

前端：

```powershell
cd frontend
npm install
```

### 3. 启动

**方式一：一键启动（推荐）**

```powershell
.\start.bat
```

自动依次启动后端 → ngrok 隧道 → 前端，并自动获取公网 URL。

**方式二：分别启动**

后端（端口自动回退）：

```powershell
cd backend
python run.py
```

前端（端口自动回退）：

```powershell
cd frontend
node ../scripts/find_port.js 3001 | xargs npx next dev -p
```

**方式三：手动指定端口**

后端（端口 8000）：

```powershell
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

前端（端口 3001）：

```powershell
cd frontend
npm run dev
```

**方式四：使用启动脚本**
- `scripts/back_start.bat`
- `scripts/front_start.bat`

### 4. 访问

| 页面 | 地址 |
|------|------|
| 首页 | `http://localhost:3001` |
| 新建问卷（学员/管理员双视角） | `http://localhost:3001/assessment` |
| 指定问卷 | `http://localhost:3001/assessment/{assessment_id}` |
| 报告预览 | `http://localhost:3001/report/{assessment_id}` |
| 前置导入 | `http://localhost:3001/intake` |

## API 端点总览

### 核心流程

| 方法 | 端点 | 说明 |
|------|------|------|
| `GET` | `/health` | 健康检查 |
| `POST` | `/api/assessments` | 创建问卷 |
| `GET` | `/api/assessments/{id}` | 完整聚合状态 |
| `POST` | `/api/assessments/{id}/profile` | 生成企业画像 |
| `POST` | `/api/assessments/{id}/canvas` | 画布 9 格诊断 |
| `POST` | `/api/assessments/{id}/breakthrough/recommend` | 突破要素推荐 |
| `POST` | `/api/assessments/{id}/breakthrough/select` | 突破要素选择 |
| `POST` | `/api/assessments/{id}/directions/expand` | 方向延展 |
| `POST` | `/api/assessments/{id}/directions/select` | 方向选择 |
| `GET` | `/api/assessments/{id}/directions` | 查看已选方向 |
| `POST` | `/api/assessments/{id}/competitiveness/generate` | 竞争力分析 |
| `GET` | `/api/assessments/{id}/competitiveness` | 查看竞争力 |
| `POST` | `/api/assessments/{id}/endgame/generate` | 商业终局分析 |
| `GET` | `/api/assessments/{id}/endgame` | 查看商业终局 |
| `POST` | `/api/assessments/{id}/scenarios` | 场景推荐 |
| `POST` | `/api/assessments/{id}/cases` | 案例匹配（分层检索） |
| `POST` | `/api/assessments/{id}/report` | 生成报告（模板/LLM） |
| `GET` | `/api/assessments/{id}/report-context` | 报告上下文 |

### 报告与导出

| 方法 | 端点 | 说明 |
|------|------|------|
| `GET` | `/api/reports/{report_id}` | 获取报告详情 |
| `GET` | `/api/reports/{report_id}/export/markdown` | 导出 Markdown |
| `GET` | `/api/reports/{report_id}/export/docx` | 导出 DOCX |
| `GET` | `/api/reports/{report_id}/export/pdf` | 导出 PDF |
| `GET` | `/api/reports/{report_id}/print` | 打印版 HTML |
| `GET` | `/api/reports/{report_id}/enrich` | 报告增强 |
| `GET` | `/api/reports/{report_id}/quality` | 质量审计报告 |
| `POST` | `/api/reports/{report_id}/share` | 生成分享链接 |
| `GET` | `/api/reports/{report_id}/share/{token}` | 访问分享链接 |

### 课后跟进

| 方法 | 端点 | 说明 |
|------|------|------|
| `GET` | `/api/assessments/{id}/follow-up` | 跟进计划 |
| `PATCH` | `/api/assessments/{id}/follow-up/tasks/{task_id}` | 更新任务 |
| `POST` | `/api/assessments/{id}/follow-up/recalibrate` | 复盘修订 |
| `POST` | `/api/assessments/{id}/push` | 双周案例推送 |
| `GET` | `/api/assessments/{id}/push/history` | 推送历史 |
| `POST` | `/api/assessments/{id}/recalibrate` | 再校准方案 |

### 管理员视角

| 方法 | 端点 | 说明 |
|------|------|------|
| `GET` | `/api/instructor/dashboard` | 学员总览 |
| `POST` | `/api/instructor/batch-comment` | 批量点评 |
| `GET` | `/api/instructor/export?format=csv` | 导出 CSV |

### RAG 检索

RAG 默认关闭，路由前缀为 `/rag`（非 `/api/rag`）。

| 方法 | 端点 | 说明 |
|------|------|------|
| `GET` | `/rag/status` | RAG 状态 |
| `POST` | `/rag/search` | 搜索知识库 |
| `POST` | `/rag/ingest` | 注入知识 |

## 报告结构

模板报告固定 14 章节：

1. 企业基本画像
2. 当前商业模式画布诊断
3. 突破要素
4. 创新方向延展
5. AI 成熟度评估
6. 高优先级 AI 提效场景
7. 推荐场景详细规划
8. 差异化竞争力设计
9. 参考案例与启示
10. 三阶段 AI 创新路线图
11. 90 天行动计划
12. 风险与阻力
13. 管理员点评区
14. 商业终局设计

## 密钥配置（mykey.py）

除了 `.env` 环境变量，项目还支持通过 `mykey.py` 文件配置 LLM 凭证，优先级为：

```
.env 环境变量  >  mykey.py  >  config.py 默认值
   (最高)          (中间)        (最低)
```

复制模板并填入真实凭证：

```powershell
Copy-Item mykey.py.example backend/app/core/mykey.py
```

编辑 `backend/app/core/mykey.py`：

```python
llm_config = {
    "llm_mode": "live",
    "openai_api_key": "sk-你的真实key",
    "openai_base_url": "https://api.openai.com/v1",
    "openai_model": "gpt-4o-mini",
    "llm_report_enabled": True,
    "llm_report_timeout_seconds": 60,
}
```

- `mykey.py` 已在 `.gitignore` 中，不会被提交
- `mykey.py.example` 为模板文件，可安全提交
- 非 OpenAI 兼容接口（DeepSeek / 千问 / 智谱等）：只需改 `openai_base_url` 和 `openai_model`

## 环境变量参考

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `APP_NAME` | `Meitai AI Business Innovation Agent API` | 应用名称 |
| `APP_ENV` | `development` | 运行环境 |
| `FRONTEND_ORIGIN` | `http://localhost:3001` | CORS 允许的前端地址 |
| `DATABASE_URL` | `sqlite:///./backend/data/meitai_demo.db` | SQLite 路径 |
| `LLM_MODE` | `mock` | `mock` / `live` |
| `OPENAI_API_KEY` | *(空)* | OpenAI API 密钥 |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | API 地址 |
| `OPENAI_MODEL` | *(空)* | 模型名（如 `gpt-4o-mini`） |
| `LLM_REPORT_ENABLED` | `false` | LLM 增强报告 |
| `LLM_REPORT_TIMEOUT_SECONDS` | `60` | LLM 报告超时 |
| `RAG_ENABLED` | `false` | ChromaDB 向量检索 |
| `CHROMA_PERSIST_DIR` | `./backend/data/chroma` | ChromaDB 目录 |
| `RAG_TOP_K` | `5` | RAG 检索条数 |
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` | 前端调用后端地址 |
| `INTAKE_MAX_UPLOAD_SIZE_MB` | `10` | 导入文件大小上限 |
| `INTAKE_PDF_OCR_ENABLED` | `true` | PDF OCR 开关 |

## 测试

后端：

```powershell
cd backend
python -m pytest tests/ -v
# 20 passed, 1 skipped
```

前端：

```powershell
cd frontend
npx vitest run
# 7 passed
```

E2E 全链路：

```powershell
cd backend
python -m pytest tests/test_e2e_full_chain.py -v -s
# 26 个步骤验证，涵盖画像→画布→突破→方向→竞争力→商业终局→
#   场景→案例→报告→导出→分享→跟进→推送→管理员工作台→级联清空
```

## 更多文档

- **[使用说明.md](./使用说明.md)** — 面向用户的操作指南（界面概览、14 步操作流程、常见问题）
- **[使用方法.md](./使用方法.md)** — API 参考手册（环境要求、端点列表、环境变量、级联清空机制）
- **[docs/CURRENT_STATUS.md](./docs/CURRENT_STATUS.md)** — 项目进展总览、已完成功能、待完成功能
- **[docs/PROJECT_OVERVIEW.md](./docs/PROJECT_OVERVIEW.md)** — 项目架构概览
- **[docs/B1_PRE_INPUT_IMPORT_DESIGN.md](./docs/B1_PRE_INPUT_IMPORT_DESIGN.md)** — 前置导入功能设计

## 端口说明

| 服务 | 端口 | 说明 |
|------|:---:|------|
| 前端 | **3001** | 默认端口（3000 已保留） |
| 后端 | **8000** | FastAPI 开发服务器 |

## 运行模式

- **Mock 模式**（默认）：`LLM_MODE="mock"`，所有生成走模板 / 规则引擎，无需 API Key
- **Live 模式**：`LLM_MODE="live"`，画像、画布、报告可走真实 LLM
- **报告模式**：报告支持 `mode=template`（始终模板）、`mode=llm`（尝试 LLM，失败回退）
