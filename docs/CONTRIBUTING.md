# 贡献指南

提交问题时请说明组件、操作系统、复现步骤、预期和实际结果；日志中请移除凭据与个人内容。

Python 服务遵循 `MemPulse/pyproject.toml`；在 `MemPulse/` 下运行 `python -m pytest -q`。独立 WebUI 需要先在 `MemPulse/ui/` 执行 `npm ci && npm run build`。

OpenCode 遵循其 `AGENTS.md` 和包内约定。类型检查在修改的包内执行 `bun run typecheck`；测试也从对应包运行，不从 OpenCode 根目录运行。

提交采用 `feat:`、`fix:`、`docs:` 或 `chore:` 前缀。PR 说明具体问题、行为变化和实际验证结果。文档放入对应 `docs/`；不要提交凭据、数据库、模型权重、评测输出和构建产物。
