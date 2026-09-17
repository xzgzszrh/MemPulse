# Running application screenshots / 运行界面截图

Captured on 2026-09-17 from the running `OpenCode/packages/app` frontend and `MemPulse/scripts/desktop_dev.py` backend. This is the desktop frontend's browser development preview, not a mockup or a capture of the packaged native window.

截图来自实际运行的桌面前端浏览器开发预览，后端为独立 Python 记忆服务。它们不是设计稿，也不代表已完成对原生安装包的完整 GUI 验收。

- `home.jpg`: topic network and workbench entry / 首页话题网络。
- `workbench.jpg`: topic goals, tags and shared entities / 话题工作台。
- `context.jpg`: restore fields and event timeline, scrolled view / 上下文恢复与时间线。

The preview used a new temporary data directory specified through `MEMPULSE_PREVIEW_DATA_DIR`, with built-in synthetic demo topics. No personal workspace, provider credentials or real conversation history was loaded. Names and organizations shown are demo content. The screenshots are unretouched; their JPEG format is the native capture output.

本次使用独立临时数据目录与程序内置合成演示话题，未加载个人工作区、提供商凭据或真实会话。图中的人物与机构属于演示内容。截图未作内容修饰，保留原始 JPEG 输出。

To reproduce the memory UI, run `scripts/desktop_dev.py` from `MemPulse/` with `PYTHONPATH=src` and a fresh `MEMPULSE_PREVIEW_DATA_DIR`, then start `bun run dev` from `OpenCode/packages/app/`. See the desktop integration guide for the full development environment.
