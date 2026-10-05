# 贡献指南 / Contributing

感谢对本项目的关注！欢迎一切形式的贡献：Bug 报告、文档改进、代码 PR。

## 提交 Issue

- Bug 请使用 [Bug 模板](.github/ISSUE_TEMPLATE/bug_report.yml)，附上复现步骤与关键日志
- 功能建议请先看「项目文档」确认是否已有设计；与商业集成相关的需求暂不受理（非商业许可）

## 开发环境

| 模块 | 要求 | 启动 |
|---|---|---|
| platform-backend | JDK 21, Maven 3.9+ | `mvn spring-boot:run -pl backend-server` |
| ai-service | Python 3.11+, uv | `uv sync && uv run uvicorn app.main:app --reload` |
| admin-web | Node 18+ | `npm ci && npm run dev` |

提交前请保证：

1. 后端：`mvn clean package -DskipTests` 通过
2. AI 服务：`uv run pytest` 全绿
3. 前端：`npm run build` 通过，`npx eslint .` 无 error

## 提交规范

遵循 Conventional Commits：`feat: xxx` / `fix: xxx` / `docs: xxx` / `chore: xxx`

## 铁律

- ⛔ 不允许硬编码密钥、token、密码 —— 一律走环境变量并在 `.env.example` 占位
- ⛔ 不引入 `:latest` 镜像标签
- ✅ 新增配置必须同步 `.env.example` 注释
