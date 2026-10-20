# 贡献指南

感谢你关注本项目！欢迎提交 Issue 与 Pull Request。

## 开发环境

```bash
# 后端
cd backend
python -m venv venv && source venv/bin/activate   # Windows: .\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m app.user_admin create-admin admin YourPass123
python -m uvicorn app.main:app --port 8000 --reload

# 前端（另开终端）
cd frontend
npm install
npm run dev
```

打开 http://localhost:5173 登录。

## 提交前检查清单

- [ ] 后端测试通过：`cd backend && python -m pytest`
- [ ] 前端构建通过：`cd frontend && npm run build`
- [ ] 没有引入新的硬编码密钥 / 地址 / 真实数据
- [ ] 新功能附带测试（`backend/tests/`）

## 代码约定

- 后端：FastAPI + SQLAlchemy，路由放 `backend/app/routers/`，每个模块（人员/项目/论文/知识产权/奖励荣誉）一个路由文件。
- 字段驱动：新增字段优先走「字段定义」机制（`custom_fields.py` / `field_defs` 表），而非直接改模型列。
- 前端：Vue 3 `<script setup>` + Element Plus；通用组件放 `frontend/src/components/`，页面放 `views/`。
- 不提交：`backend/runtime/`（数据库与上传文件）、`.env`、`data/`、`node_modules/`、`dist/`（均已在 `.gitignore`）。

## 提交规范

- Commit message 用简洁的祈使句，例：`修复论文导出 422 错误` 或 `新增奖励荣誉模块`。
- PR 请描述动机、改动点、测试方式。

## 报告安全问题

请不要在公开 Issue 中暴露真实密钥或服务器信息。数据安全问题请直接联系维护者。
