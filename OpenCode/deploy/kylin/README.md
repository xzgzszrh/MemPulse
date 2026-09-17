# MemPulse Code：麒麟 x86_64 DEB 源码编译包

本包独立包含最新源码，不需要先解压旧包或叠加补丁。面向 x86_64 / AMD64 的银河麒麟桌面环境，产物是 Electron 客户端及本机编译的 Python 记忆服务。本机只制作源码交付；麒麟原生编译和安装验收由目标端执行。

## 快速开始

```bash
tar -xzf mempulse-deb-source-20260915.tar.gz
cd mempulse-deb-source-20260915
python3 OpenCode/deploy/kylin/verify-bundle.py
bash build-deb.sh
```

如果系统 python3 过旧，指定已安装的 Python 3.11/3.12：

```bash
MEMPULSE_BUILD_PYTHON=python3.12 bash build-deb.sh
```

`build-deb.sh` 先校验清单、检查工具链，再安装依赖并编译 DEB。退出码记录在 `build-logs/exit-codes.log`，完整日志分别是 `install-deps.log` 和 `build-deb.log`。任何步骤失败都会停止，不用额外套一个会掩盖退出码的 tee。

输出：`OpenCode/packages/desktop/dist/mempulse-code-kylin-x64.deb`；目录包为 `dist/linux-unpacked/`，可执行文件 `ai.opencode.desktop`。在普通用户的图形桌面运行，不要用 sudo 启动客户端。

## 工具链和系统

- Node 24；Bun 1.4.2 为本机验证版本，满足仓库要求的 ^1.3.14。使用随包 `bun.lock`，安装始终带 `--frozen-lockfile`，不重新生成锁文件。
- Python >=3.10，目标 Linux 建议 3.11/3.12；需要 pip、venv、C/C++ 编译器、make、git、unzip 和 dpkg-deb。
- 预留至少 15 GiB。Node 24 工作流要求 glibc >=2.28；不要原地替换系统 glibc。平台兼容由 preflight 和实际二进制运行确认。
- DEB 需要支持 Debian 包的系统。若目标实际是 openEuler 或其他 RPM 系统，请确认包管理体系，不能把 DEB 当 RPM 安装。通用脚本仍支持 `build.sh rpm`，但 RPM 原生依赖需另配。
- Electron 运行需要 GTK3、NSS、ALSA、GBM、X11/Wayland、中文字体等，具体系统包名以目标发行版为准。首次依赖安装需访问 npm/Python/Electron 下载源，交付包不是离线依赖全集。

安装依赖单独执行：`bash OpenCode/deploy/kylin/install-deps.sh`。构建单独执行：`bash OpenCode/deploy/kylin/build.sh deb`，也可先用 `dir` 目标。

## 已避免的旧交付问题

1. **明确交付 Electron。** 前端源码为 `OpenCode/packages/app`，包含共享 UI 源码、本地 vendor 包和锁文件；不交付 `MemPulse/ui` 的独立 WebUI/Tauri 原型，也不携带本机生成的 static 页面。
2. **测试与交付范围一致。** 构建执行 `pytest -q --strict-markers -m 'not standalone_webui'`。原有独立 WebUI 页面和真实 JS 资源断言仍完整保留在 `MemPulse/tests/test_webui.py`；没有空页面、删断言或依赖本机 static。默认全量 pytest 仍包含独立 WebUI 测试，因此请使用给出的 Electron 构建命令。
3. **本机构建记忆进程。** `build_desktop_sidecar.py --with-onnx` 在目标 Linux 上生成匹配架构的 ELF；包中不带 macOS 可执行文件、node_modules 或 .venv。不依赖 Rust/Tauri 编译工具链。
4. **固定模型目录快照。** `OpenCode/deploy/kylin/assets/models.dev.json` 随包提供，构建通过 MODELS_DEV_API_JSON 读取它，不额外实时请求 models.dev。该快照是可选对话模型目录，和本地 FP32 embedding 权重不同。
5. **生产构建不下载开发版 CLI。** 使用 prod 通道和内置 Node 后端；不请求不存在的定制版本 CLI 下载。不向 OpenCode 上游发布，固定 `--publish never`；独立发行包关闭上游自动更新。
6. **保留失败证据。** Bun 被终止时记录命令、行号及退出码。137/SIGKILL 不等于已经证明 OOM；结合相应时间的内核/系统日志调查，不预设内存、文件描述符或 GPU 是原因。

## 模型、演示与用户数据

本包携带 revision4 的 **FP32 推理子集**：ONNX、tokenizer、tide_config 及原 manifest；不含训练 safetensors 和未通过对齐测试的 INT8。原 manifest 保留原始全模型交付清单，缺少的训练/INT8 文件属于有意排除，见 SOURCE_MANIFEST.json 的 included_assets；全包实际文件以 SHA256SUMS 为准。

安装包会把推理资产放在 `resources/mempulse/models/tide/`。记忆进程从自身路径发现模型，无需开发机绝对路径。默认 768 维 FP32，自动归题关闭，操作仍需前端确认。

新装默认演示含 **53 个任务话题、284 条事件**；在“设置 → 记忆 → 工作区”切换演示/个人。两类数据库分别保存。已有 model.json 优先，不能直接覆盖用户数据。旧 dev 包的数据目录仍保留，本包 prod 目录为 `~/.config/ai.opencode.desktop/`；有旧数据迁移需求时先备份，不能把测试库覆盖进去。

包含最新界面修改：首页三行固定悬浮卡片、“最近”入口、项目菜单行高、话题页与遗忘确认弹窗布局、移除 DEV 入口及调试浮层、模式切换同步刷新图谱。首页 3D 保持既有版本。

## 目标机验收和已知边界

构建末尾自动对打包后的记忆服务执行真实 JSON-lines 冒烟测试，验证 FP32 自动发现、15 次检索及演示/个人切换，不触碰用户库。

```bash
cd MemPulse
PYTHONPATH=src .venv/bin/python scripts/evaluate_competition.py \
  --model ../微调模型/revision4-model-bundle \
  --output ../build-logs/competition-kylin-run1 --rounds 3
```

每次使用新的评测输出目录。比赛测试报告与原始数据在 `MemPulse/reports/competition-evaluation-20260915.md` 和对应 reports 子目录；本轮本机证据 Recall@10 92.59%、P95 99.30ms，不是麒麟成绩或最终大模型回答准确率。时间语义、工具证据裁剪、凭据过滤和工具参数/结果副本遗忘缺陷尚未修复，详见该报告。

麒麟 embedding SDK ABI/推理、目标端资源占用、真实场景、完整回答质量与 DEB 安装仍需实机验证。不要默认加入 --no-sandbox、关闭 GPU、修改系统限制来掩盖问题。

将根目录 `CODEX_HANDOFF.md` 交给目标端 Codex；`SOURCE_MANIFEST.json` 记录源版本，`SHA256SUMS` 记录实际文件。
