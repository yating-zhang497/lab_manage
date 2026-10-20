# 课题组信息管理系统

> 面向小型科研团队的信息管理平台：人员、项目、论文、知识产权、奖励荣誉五大模块统一管理，跨表关联、字段自定义、批量导入、AI 辅助提取、统一导出。

📐 **系统架构图**：[docs/architecture.html](docs/architecture.html)（可交互的 SVG 架构图，源文件 [docs/architecture.json](docs/architecture.json)）

---

## 目录

- [特性概览](#特性概览)
- [技术栈](#技术栈)
- [快速开始](#快速开始)
- [配置项](#配置项)
- [数据模型](#数据模型)
- [使用指南](#使用指南)
- [生产部署](#生产部署)
- [项目结构](#项目结构)
- [开发与测试](#开发与测试)
- [贡献](#贡献)
- [许可证](#许可证)

---

## 特性概览

- **五大模块、全库联通**：人员 / 项目 / 论文 / 知识产权 / 奖励荣誉，跨模块关联全部走关系表（唯一事实来源），任意维度可顺藤摸瓜查询。
- **字段驱动**：表单、列表列、详情页、导入/导出字段全部由「字段定义」动态生成。所有字段（含内置字段）可改名 / 改类型 / 改选项 / 启停 / 排序，无需改代码。
- **批量导入**：每个模块都有可下载的 Excel 导入模板（按当前字段定义即时生成）；论文额外支持 BibTeX / Better BibTeX 导入。
- **AI 辅助提取**：上传论文 PDF 后，调用 LLM 从致谢原文结构化提取项目编号并自动建立基金标注关系、标记通讯作者。
- **统一导出中心**：跨表筛选（如「某人员参与的所有项目」「某项目资助的所有论文」）后，按字段定义导出 Excel / BibTeX；多值列可按一行一条关联项展开。
- **权限分级**：管理员 / 只读用户；超级管理员账号受保护（不可删除 / 不可降级）。
- **自动归档**：每月 1 日凌晨自动导出各模块数据为存档，支持手动导出与下载。
- **响应式 UI**：桌面 / 移动端自适应，固定顶部工具栏、多列叠加排序、多选筛选标签行。

## 技术栈

| 层 | 技术 |
| --- | --- |
| 后端 | Python 3.10+ · FastAPI · SQLAlchemy · SQLite |
| 前端 | Vue 3 · Element Plus · Vite |
| 调度 | APScheduler（月度自动归档） |
| AI | OpenAI 兼容接口（默认 DeepSeek，可换任何兼容服务商） |

---

## 快速开始

### 环境要求

- **Python 3.10 或更高**（建议 3.11）
- **Node.js 18 或更高**（建议 20）
- Git

### 1. 克隆仓库

```bash
git clone https://github.com/<your-org>/lab_manage.git
cd lab_manage
```

### 2. 启动后端

```bash
cd backend

# 创建并激活虚拟环境
python -m venv venv
# Linux / macOS:
source venv/bin/activate
# Windows PowerShell:
.\venv\Scripts\Activate.ps1

# 安装依赖
pip install -r requirements.txt

# 创建第一个管理员账号（用户名建议用 admin，会成为受保护的超级管理员）
python -m app.user_admin create-admin admin YourPass123

# 启动开发服务器（热重载）
python -m uvicorn app.main:app --port 8000 --reload
```

后端默认监听 `http://127.0.0.1:8000`，健康检查：`http://127.0.0.1:8000/api/health` → `{"status":"ok"}`。

首次启动会在 `backend/runtime/` 自动创建 SQLite 数据库 `im.db` 与 `uploads/` 目录。

### 3. 启动前端

另开一个终端：

```bash
cd frontend
npm install
npm run dev
```

打开 **http://localhost:5173**，用刚才创建的账号登录。首次登录后会要求修改初始密码，改密后才能执行写操作。

> 前端的 Vite 开发服务器已配置代理：`/api/*` → `http://127.0.0.1:8000`，无需额外配置即可联调。

---

## 配置项

通过环境变量配置（建议写入 `backend/.env` 文件，已被 `.gitignore` 忽略，不会进入版本库）：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `IM_LLM_API_KEY` | 无 | LLM API Key（OpenAI 兼容）。未设置时 AI 提取功能返回 400，其余功能不受影响 |
| `IM_LLM_BASE_URL` | `https://api.deepseek.com` | OpenAI 兼容接口地址，可换 OpenAI / 通义 / 智谱等 |
| `IM_LLM_MODEL` | `deepseek-chat` | 模型名 |
| `IM_AUTHOR_MATCH_THRESHOLD` | `80` | AI 提取通讯作者时的模糊匹配阈值 (0-100) |
| `IM_SUPER_ADMIN` | `admin` | 受保护的超级管理员用户名（不可删除/降级） |
| `IM_LOG_LEVEL` | `INFO` | 后端日志级别（DEBUG/INFO/WARN/ERROR） |
| `IM_LOG_FILE` | 无 | 日志文件路径；未设则只输出到 stdout |

`.env` 示例可参考根目录的 [.env.example](.env.example)。

---

## 数据模型

五个实体模块，各自有唯一标识（必填，其余字段全部可留空）：

| 模块 | 唯一标识 | 说明 |
| --- | --- | --- |
| 人员 | 学号/工号 (`uid`) | 支持姓名变体（英文名 / 别名），用于作者/发明人/获奖人自动匹配 |
| 项目 | 项目编号 (`project_no`) | 经费、KPI、起止时间、成员 |
| 论文 | 论文题目（归一化查重） | 作者、基金标注走关系表；支持 PDF 附件与 AI 提取 |
| 知识产权 | 产权名称 | 类型：专利 / 软著 / 其他；发明人、基金标注走关系表 |
| 奖励荣誉 | 奖项名称 | 获奖人走关系表（可关联人员库，支持排名） |

跨模块关联全部通过关系表实现：

- `paper_authors` 论文作者 ↔ 人员
- `paper_funding` 论文基金标注 ↔ 项目
- `ip_inventors` 知识产权发明人 ↔ 人员
- `ip_funding` 知识产权基金 ↔ 项目
- `project_members` 项目成员 ↔ 人员
- `award_recipients` 奖励获奖人 ↔ 人员

作者 / 发明人 / 获奖人按 **姓名或英文名精确匹配** 人员库（大小写不敏感、`姓, 名` / `名 姓` / `姓 名` 三种语序等价）；匹配不上的可在人员档案的「姓名变体」中补充。

---

## 使用指南

### 字段管理

左侧导航 → **字段管理**：每个模块的字段一视同仁，可改名 / 改类型 / 改下拉选项 / 启停 / 排序。停用 = 隐藏并保留数据，可随时重新启用；唯一标识字段（uid / project_no / title / award_name）不可停用。字段变更后，表单、列表、导入模板、导出全部自动同步。

### 批量导入

每个模块列表页工具栏 → **下载导入模板**（按当前字段定义即时生成的 Excel，含下拉选项与日期格式）。填好后用 **导入** 上传：

- 按 **唯一标识 upsert**（有则更新、无则新增），错误行逐条报告。
- 人员：学号/工号必填；姓名变体列支持 `; ；, ，/` 分隔多个。
- 论文：支持 **Excel / CSV / BibTeX**（兼容 Zotero Better BibTeX 导出）。作者列与项目编号列自动匹配人员库与项目库。
- 知识产权：产权名称必填；发明人列自动匹配人员库。
- 奖励荣誉：奖项名称必填；获奖人列自动匹配人员库。

### AI 提取（论文）

1. 在论文列表上传 PDF（仅上传存入文献库，与 AI 提取分开）。
2. 工具栏点 **AI 提取**：勾选时提取选中项，未勾选时提取当前筛选结果全部（上限 50 篇）。
3. LLM 从致谢原文结构化提取项目编号并与项目库匹配，结果 **自动应用**：写入基金标注关系表、标记通讯作者、保存致谢原文。
4. 通讯作者可在论文详情作者表中手动修正。

> PDF 内容按 SHA256 去重；一篇论文最多关联一个 PDF。

### 筛选与导出

左侧导航 → **筛选与导出**：跨表联动筛选（如「某人员参与的论文」「某项目资助的知识产权」）后，按字段定义选择导出列。多值列（如作者列表、项目标注列表）可按「一行一条关联项」展开；一次导出最多一个多值维度。导出格式：Excel（全部模块）/ BibTeX（仅论文）。

各列表页工具栏也有 **导出当前结果**，按当前列表显示的字段精确导出。

---

## 生产部署

后端用 systemd 托管，前端构建为静态文件，用 Nginx / Caddy 等反向代理。

### 1. 构建前端

```bash
cd frontend
npm install
npm run build      # 产物在 frontend/dist
```

### 2. 部署后端

将代码上传到服务器（例如 `/opt/lab_manage`），在 `backend/` 下创建 `.env`（填入 `IM_LLM_API_KEY` 等），安装依赖：

```bash
cd /opt/lab_manage/backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python -m app.user_admin create-admin admin <your-password>
```

### 3. 注册 systemd 服务

参考 `scripts/im.service` 模板，按你的路径修改 `WorkingDirectory` / `EnvironmentFile` / `ExecStart`：

```bash
sudo cp scripts/im.service /etc/systemd/system/lab_manage.service
sudo systemctl daemon-reload
sudo systemctl enable --now lab_manage
sudo systemctl status lab_manage
```

### 4. 反向代理（示例：Nginx）

```nginx
server {
    listen 80;
    server_name your.domain;

    root /opt/lab_manage/frontend/dist;
    location / { try_files $uri $uri/ /index.html; }   # SPA 子页面直连回退

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 5. 一键部署脚本（可选）

仓库提供两个部署辅助脚本（均为模板，需用环境变量配置目标服务器，不含任何 hardcoded 地址）：

- `scripts/update.ps1`（Windows 端）：构建前端 + 上传代码 + 远程执行部署脚本。运行前设置环境变量 `LAB_REMOTE_HOST` / `LAB_REMOTE_USER` / `LAB_REMOTE_PATH` / `LAB_SSH_KEY`。
- `scripts/deploy_server.sh`（服务器端）：安装依赖、备份数据库、重启服务、健康检查。通过 `APP_DIR` / `PYTHON_BIN` / `SERVICE_NAME` 环境变量配置。

---

## 项目结构

```
lab_manage/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 入口 + 路由注册 + 定时任务
│   │   ├── config.py            # 配置（环境变量读取）
│   │   ├── database.py           # SQLAlchemy 引擎 + 轻量迁移
│   │   ├── models.py            # 数据模型
│   │   ├── schemas.py           # Pydantic 模型
│   │   ├── importexport.py      # CSV/Excel/BibTeX 解析与生成
│   │   ├── export_builder.py    # 导出行构造（一对多展开）
│   │   ├── ai_extract.py        # LLM 调用与 PDF 文本提取
│   │   ├── extraction_apply.py  # AI 提取结果应用
│   │   ├── custom_fields.py     # 自定义字段
│   │   ├── user_admin.py        # 用户管理 CLI
│   │   ├── create_admin.py      # 初始管理员引导
│   │   └── routers/             # 各模块 API 路由
│   ├── scripts/                 # 一次性迁移脚本
│   ├── tests/                   # pytest 测试套件
│   ├── conftest.py
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api.js               # axios 封装 + 鉴权
│   │   ├── router.js
│   │   ├── views/                # 页面组件
│   │   ├── components/           # 通用组件
│   │   └── utils/
│   ├── vite.config.js           # 含 /api 代理配置
│   └── package.json
├── docs/
│   ├── architecture.html        # 可交互架构图
│   └── architecture.json        # 架构图源文件
├── scripts/                     # 部署辅助脚本（模板）
└── README.md
```

---

## 开发与测试

### 后端测试

```bash
cd backend
pip install -r requirements.txt      # 含 pytest / httpx
python -m pytest                     # 运行全部测试
python -m pytest tests/test_api.py   # 运行单个测试文件
```

### 前端开发

```bash
cd frontend
npm install
npm run dev      # http://localhost:5173，热重载
npm run build    # 生产构建
```

### 数据库迁移

后端启动时 `database.py` 会自动执行轻量迁移（加列、回填等），无需手动操作。历史数据迁移脚本见 `backend/scripts/`（幂等，可重复执行）。

### 用户管理 CLI

```bash
python -m app.user_admin create-admin <username> [password]   # 创建管理员
python -m app.user_admin reset-password <username> [new]      # 重置密码
python -m app.user_admin list                                  # 列出用户
python -m app.user_admin delete <username>                     # 删除用户
```

---

## 贡献

欢迎提交 Issue 与 Pull Request。请先阅读 [CONTRIBUTING.md](CONTRIBUTING.md) 了解开发约定与提交规范。

提交前请确保：
- 后端测试通过：`python -m pytest`
- 前端构建通过：`npm run build`
- 不要提交真实数据、密钥或服务器配置（`backend/runtime/`、`.env`、`data/` 等已被 `.gitignore` 忽略）

---

## 许可证

[MIT License](LICENSE) © lab_manage contributors
