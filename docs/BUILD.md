# 完整桌面工程构建

完整交付目录包含 `MemPulse/`、`OpenCode/`、`微调模型/revision4-model-bundle/` 和 `scripts/`，四者保持相邻。模型包包含 FP32 ONNX、实验性混合 INT8、tokenizer、配置、原始 safetensors 权重和原始校验清单。默认应用只打包已使用的 FP32 推理文件，INT8 不作为默认配置。

## 检查模型

```bash
python3 scripts/verify_models.py
```

校验所有交付文件的大小和 SHA-256。若通过 Git 获取工程，先安装 Git LFS 并执行 `git lfs pull` 获取真实权重；完整目录交付已包含实体文件。模型校验失败时构建立即停止。

## macOS Apple Silicon

准备 Python 3.10+、Node 24、Bun ^1.3.14 和 Xcode Command Line Tools。首次构建需要联网安装依赖，不需要下载模型，也不要求原有 Git 历史。

```bash
# python3 若为系统旧版本，设置为已安装的 Python 3.10+ 路径。
export MEMPULSE_BUILD_PYTHON=/path/to/python3
bash scripts/build_desktop.sh dir
# 生成可分发的 DMG：
bash scripts/build_desktop.sh dmg
```

流程：验证权重 → 创建虚拟环境及安装依赖 → 后端与模型测试 → 编译包含 ONNX 的 Python sidecar → 安装 Bun 锁定依赖 → 桌面类型检查 → 编译服务及前端 → 打包应用与 FP32 模型 → 对打包后服务执行真实 IPC、模型检索和工作区切换验证。

应用位于 `OpenCode/packages/desktop/dist/mac-arm64/MemPulse Code.app`；DMG 位于同级 `dist/`。本地包未签名和公证。macOS 构建入口优先使用选中 Xcode 内的 SDK，避免系统 Command Line Tools 的另一版本 SDK 与编译器混用。构建结果与解析后的 Python 依赖记录在 `build-logs/`。

## Linux / 麒麟

在目标 Linux x86_64 或 ARM64 机器安装 Python 3.10+、Node 24、Bun ^1.3.14、C 编译工具和对应打包工具后运行：

```bash
bash scripts/build_desktop.sh dir
bash scripts/build_desktop.sh deb
```

也支持 `AppImage` 和 `rpm`，需对应平台工具。底层沿用 [麒麟构建脚本](../OpenCode/deploy/kylin/README.md)，不能用 macOS 上的验证代替目标机验证。当前统一入口未覆盖 Windows 和 Intel Mac。

## 独立 WebUI

Electron 桌面不依赖独立 React/Tauri WebUI；如需该界面，在 `MemPulse/ui/` 下执行 `npm ci && npm run build`，然后按 [MemPulse README](../MemPulse/README.md)启动服务。完整导出保留其源文件和锁文件。

## 构建产物的交付

源码目录保留完整构建输入；`dist/`、虚拟环境及 `node_modules/` 是构建生成目录，不提交到 Git。对使用者可直接提供 DMG、DEB 或打包应用；对开发者提供带权重的完整源码。二者是同一次发布的不同交付物，不以旧缓存替代源码构建。

模型和程序之外，调用云端大模型仍需使用者配置自己的服务与凭据；不随项目分发私人账号数据。
