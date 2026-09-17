# 完整工程构建验证（2026-09-17）

验证使用独立源码导出目录，从新建 Python 虚拟环境与新安装的 JavaScript 依赖开始，没有复制原工程的 node_modules、Python 环境或编译输出。

| 检查 | 结果 |
| --- | --- |
| 完整模型清单 | 30 个文件大小及 SHA-256 通过，总计 1,012,601,638 字节 |
| 后端及真实模型测试 | 70 passed，独立 WebUI 测试单独执行 |
| 独立 WebUI | npm ci 和 Vite 构建通过；对应测试 1 passed |
| 桌面 TypeScript | bun typecheck 通过 |
| Electron 服务、主进程及渲染器 | 编译通过 |
| macOS ARM64 应用 | 打包成功，包含 Python sidecar、ONNX Runtime 和 FP32 模型 |
| 打包后真实 IPC | 25 项检查通过，包含 15 次 TIDE 检索和工作区持久化切换 |
| DMG | 生成成功，发布目录有 SHA256SUMS |

环境：macOS ARM64、Python 3.13.5、Node 24.18.0、Bun 1.4.2、Electron 42.3.3、ONNX Runtime 1.30.0。

原生依赖首次构建遇到 Xcode 编译器与 Command Line Tools SDK 混用；统一使用选中 Xcode 内的 SDK 后解决，构建入口已包含此设置。

验证涵盖构建和打包后服务，未执行完整桌面 GUI 人工验收。DMG 未签名、公证；Linux/麒麟仍需目标机器构建验证。混合 INT8 随原模型包保留，默认使用 FP32。

完整交付目录的 `release/` 存放本次生成的 DMG 与校验文件。它被 Git 忽略，可作为发行附件单独上传。构建方法见 [BUILD](BUILD.md)。
