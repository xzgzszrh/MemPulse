# 给麒麟端 Codex：编译最新 MemPulse Code DEB

用户已指定 x86_64 / AMD64，在目标系统执行原生编译。此文件夹是新的完整源码包，无需旧包或补丁。先读 README_麒麟编译.md、SOURCE_MANIFEST.json 和仓库 AGENTS.md。

1. 执行 `python3 OpenCode/deploy/kylin/verify-bundle.py`。记录系统版本、架构、glibc、CPU/内存、Node/Bun/Python 版本；确认目标使用 Debian 包管理。如果是 openEuler/RPM 系统，先说明与 DEB 目标不匹配，不伪装成功。
2. 使用普通用户运行 `bash build-deb.sh`；Python 版本不合适时用 `MEMPULSE_BUILD_PYTHON=python3.12 bash build-deb.sh`。安装步骤需要网络，本包没有 Linux 依赖离线镜像。不得修改 bun.lock 来绕开安装问题。
3. 此包只交付 Electron：必须保留 `--strict-markers -m 'not standalone_webui'` 的后端测试范围。独立 WebUI 断言保留，但其源码/产物不属于此包。禁止塞空 HTML 或删断言。前端实际构建来自 OpenCode/packages/app 与 packages/desktop。
4. 原生记忆进程必须带 --with-onnx；FP32 运行资产已带齐，相对安装路径发现。训练权重和 INT8 有意排除。models.dev 目录快照已内置，build.sh 不应重新下载。prod 构建不下载 dev CLI，且关闭上游自动更新/发布。
5. 输出在 OpenCode/packages/desktop/dist：mempulse-code-kylin-x64.deb。先查看 build-logs/packaged-memory-smoke.json，再在目标图形桌面验收：首页最多三行、最近入口、项目切换、话题和遗忘弹窗布局、无 DEV 调试入口、演示/个人工作区切换、FP32、重启持久性。
6. 如需修代码，先初始化独立 Git 并保存快照；归档命令、补丁和日志。Bun SIGKILL/137 只证明进程被杀，必须依据同一时间的内核/系统日志判断原因，不能直接认定 OOM/FD 不足。
7. 用户授权必要的客户端启动/重启，但保留未提交表单，所有记忆写操作保持前端确认。不要删除用户库、默认关闭 sandbox/GPU 或发布到 OpenCode 上游。
8. 返回 DEB 路径、SHA-256、安装/启动方法、实际目标平台测试结果及未完成项。不要把 macOS 源码测试和本机性能数字写成麒麟原生编译/SDK 验收通过。

已有 dev 目录的数据不可自动覆盖或删除。prod 使用 ai.opencode.desktop 数据目录；用户需要迁移时，先备份旧 dev 数据并核对模型路径。测试只用隔离目录。

比赛检索报告和已知缺陷：MemPulse/reports/competition-evaluation-20260915.md。该报告中的凭据过滤/工具副本遗忘、时间语义及上下文裁剪问题尚未修复，本包不是“所有比赛指标已达标”的声明。
