<p align="center">
  <img src="docs/assets/readme/hero-zh.png" alt="MemPulse：本地优先的话题记忆，让 Agent 跨会话恢复工作脉络" width="100%">
</p>

<p align="center"><a href="README.md">English</a> · <strong>简体中文</strong></p>
<p align="center"><a href="#以话题为核心的记忆">理解话题</a> · <a href="#软件界面">软件界面</a> · <a href="#项目定位与-opencode">项目定位</a> · <a href="#快速开始">快速开始</a> · <a href="#系统架构">系统架构</a> · <a href="#模型与权重">模型与权重</a> · <a href="#构建与验证">构建与验证</a> · <a href="#文档导航">文档导航</a></p>

# MemPulse

**记忆，沿着话题生长。让 Agent 在下一次会话中，接着完成。**

**MemPulse 是以“话题”为核心组织长期记忆的 Agent 记忆方案。** 每个话题围绕一件持续推进的事，将分散在多次会话中的事件、证据与工作状态连接起来，使 Agent 能够找到这件事、恢复它的上下文，并接着完成。

话题与事件保存在本地 SQLite 中，记忆核心可独立运行，通过 CLI、MCP 和 HTTP 对外提供能力。当前桌面集成基于 OpenCode，未来将通过插件兼容更多 IDE。

> **许可证：**MemPulse 自研代码采用 [Apache-2.0](LICENSE)。第三方代码和模型资产保留各自适用的上游条款，详见[许可与致谢](#许可与致谢)。

## 以话题为核心的记忆

### 什么是话题？

在 MemPulse 中，**话题（Topic）是围绕一个持续事项组织起来、能够跨会话延续的记忆单元**。它有稳定的身份、明确的目标和边界，并随着这件事的推进积累事件、证据、状态与检查点。例如，“完成青禾客户交付报告”是一个话题；围绕它发生的需求确认、模板变更、初稿生成和验收反馈，都可以成为该话题的事件。

话题回答的是：**“我们一直在推进哪件事，现在进行到哪里，接下来还缺什么？”** 它不仅保存“聊过什么”，还组织继续这件事所需要的工作脉络。

| 概念 | 在 MemPulse 中承担什么角色 |
| --- | --- |
| **话题** | 持续事项的身份与边界，组织其目标、事件链、关联信息和恢复状态。 |
| 会话 | 一段交互及其事件来源。同一话题可以跨多个会话；会话切换事项时，需要明确新的话题归属。 |
| 项目 / 工程目录 | 定位事项的背景线索。一个项目可以有多个独立话题。 |
| 标签 / 人物 / 文件等实体 | 帮助找到话题、连接相关证据。共享这些线索，不会让两个不同事项自动变成同一话题。 |

### 一个话题如何持续生长？

以演示数据中的 **“青禾客户交付报告”** 为例：先确认交付范围并导入 V2 模板，随后客户确认改用 V3，再生成初稿并等待复核。这些记录可以来自不同会话，但它们延续的是同一件事。

```mermaid
flowchart LR
    A["会话 A 的事件<br/>确认需求、导入 V2"] --> T["同一话题<br/>青禾客户交付报告"]
    B["会话 B 的事件<br/>确认改用 V3"] --> T
    C["会话 C 的事件<br/>生成初稿、等待复核"] --> T
    T --> R["恢复工作上下文<br/>字段 · 证据 · 检查点 · 缺口"]
    style T fill:#fff0ec,stroke:#c83127,stroke-width:2px,color:#242522
```

*示意：相关事件在明确归属后汇入同一话题。会话是来源，话题是持续维护的记忆单元。*

话题积累以下内容：

- **目标与边界**：要完成什么，以及哪些相近事项属于另一个话题。
- **事件链与来源**：做过什么、何时发生、依据是什么，保留后续复核所需的来源。
- **关联与有效信息**：人物、资源、标签，以及按作用域和版本解析的偏好、知识。
- **可恢复的状态**：已记录的上下文字段、检查点和缺失信息，使新的会话能够接续工作。

如果同一项目又开始“整理公共模板库”，它可以建立另一个话题。即使涉及相同人员和模板文件，也应按各自目标与边界分别维护；必要时建立关联，而不是按相似词自动合并。

### 从“找到话题”到“继续这件事”

当用户在新会话中说“继续青禾的交付报告”，MemPulse 的处理重点是：

1. **定位话题**：利用名称、人物、资源等线索，结合词法、结构化关系及可选的 TIDE 编码器寻找候选话题，再筛选相关事件证据；歧义需要澄清。
2. **恢复上下文**：围绕确定的话题返回已记录字段、来源证据、可用检查点及缺口。在上述例子中，可以恢复输入文件和当前 V3 模板，并追溯模板变更的来源；尚未结构化记录的输出偏好或步骤状态会显示“待补全”。
3. **继续积累**：在桌面集成中，用户确认创建或关联话题后，后续采集事件按当前绑定归集。话题继续生长，不需要为每个新会话重建一份任务记忆。

未关联话题的采集记录先进入待处理区。新建会话、改变会话标题，或向量检索排在第一，都不会自动创建、重命名或重新绑定话题。检索和恢复是读取；记忆修改遵循相应的确认流程。

完整的归属、标签、检索和治理规则见[话题与任务契约](MemPulse/docs/TOPIC-CONTRACT-20260915.md)。

## 项目定位与 OpenCode

**我们提供的是一套以话题为核心、可复用的 Agent 记忆方案。** 我们选择优秀的开源项目 [OpenCode](https://github.com/anomalyco/opencode) 作为当前桌面客户端的构建基础，复用它的会话管理、工具执行、终端和桌面交互能力，将工作重点放在长期话题记忆、证据检索、上下文恢复和记忆治理上。感谢 OpenCode 社区提供的扎实基础。

OpenCode 是当前完整桌面集成的基础，**并不意味着 MemPulse 的记忆方案仅支持 OpenCode**。独立记忆服务已提供 CLI、MCP 和 HTTP 接口，其他宿主可以通过相应接口接入；具体接入仍需结合宿主的协议、权限和上下文交互方式进行适配与验证。

**未来，我们将以插件形式兼容更多 IDE**，让开发者在熟悉的开发环境中使用同一套记忆能力。更多 IDE 的专用插件目前处于规划阶段。

| 层次 | 当前状态 |
| --- | --- |
| 独立记忆核心与 CLI / MCP / HTTP 接口 | 已提供，可独立运行和接入。 |
| 基于 OpenCode 的桌面集成 | 当前可运行的完整实现，承载本文中的界面。 |
| 面向更多 IDE 的插件 | 后续规划，尚未发布专用插件。 |

## 软件界面

以下为真实运行的 MemPulse 桌面前端截图，通过浏览器开发预览连接独立 Python 记忆服务，使用隔离的合成演示数据。截图展示当前基于 OpenCode 的集成界面。

**首页：围绕持续话题浏览记忆网络。**

![MemPulse 运行界面：首页展示话题网络、最近会话与工作台入口，使用合成演示数据。](docs/assets/screenshots/home.jpg)

<details>
<summary>查看话题工作台与上下文恢复界面</summary>

**话题工作台：查看任务目标、标签和共享实体。**

![MemPulse 话题工作台：示例交付任务的目标、标签和关联实体。](docs/assets/screenshots/workbench.jpg)

**上下文恢复：查看输入文件、模板版本、待补信息与事件时间线。**

![MemPulse 上下文恢复界面：恢复字段和保留版本变化的事件时间线，滚动视图。](docs/assets/screenshots/context.jpg)

</details>

截图来源与复现说明见 [screenshots/README](docs/assets/screenshots/README.md)。

## 围绕话题的核心能力

| 能力 | 具体行为 |
| --- | --- |
| 话题建立与延续 | 明确持续事项的目标与边界，以稳定身份积累跨会话事件。 |
| 话题定位与证据检索 | 结合词法、实体关系及可选 ONNX 编码器定位候选话题，再筛选话题内的相关事件证据。 |
| 话题恢复 | 围绕话题返回上下文字段、来源证据、可用检查点和缺口。 |
| 话题与记忆治理 | 支持话题归属纠正、合并与拆分、偏好作用域、知识版本及定向遗忘。 |
| Agent 接入 | 提供 CLI、MCP、HTTP，以及定制桌面客户端中的 `memory_*` 工具。 |
| 完整桌面构建 | 将前端、Python 服务、ONNX Runtime 和 FP32 模型打包为独立应用。 |

![记忆流程：记录事件、按话题组织，再检索证据并恢复上下文。](docs/assets/readme/lifecycle-zh.png)

在桌面集成中，未绑定话题的采集事件先进入待处理区。Agent 发起的记忆修改以提案形式呈现，由用户在界面确认后执行；检索本身不会授予写入权限。CLI 与 API 是供调用方直接使用的独立接口。

## 快速开始

### 运行安装包

请从 [GitHub Releases](https://github.com/xzgzszrh/MemPulse/releases)下载 macOS Apple Silicon DMG 及 `SHA256SUMS`；完整本地交付目录的 `release/` 下也提供这些文件。打开 DMG 即可安装应用。安装包内置 Python 运行时与 FP32 检索模型，运行该打包版本不需要另行安装 Python、Node 或 Bun。

当前 macOS 安装包尚未签名、公证。演示工作区与个人工作区使用独立数据库。Agent 对话如需调用云端大模型，请自行配置提供商和凭据；本地检索模型不承担对话生成。

### 从源码构建完整桌面应用

准备 **Python 3.10+**、**Node 24**、**Bun ^1.3.14** 和平台编译工具。macOS 需安装 Xcode Command Line Tools 或 Xcode。保持 `MemPulse/`、`OpenCode/`、`微调模型/` 和 `scripts/` 四个目录相邻。

在仓库根目录运行：

```bash
# 通过 Git 获取项目时，拉取真实权重，避免只拿到 LFS 指针。
# 完整交付目录已经包含权重时，可跳过这两条命令。
git lfs install
git lfs pull

python3 scripts/verify_models.py
bash scripts/build_desktop.sh dir
```

如果系统 `python3` 低于 3.10，先将 `MEMPULSE_BUILD_PYTHON` 指向符合要求的解释器：

```bash
export MEMPULSE_BUILD_PYTHON=/absolute/path/to/python3
bash scripts/build_desktop.sh dir
```

| 目标 | 命令 | 当前验证状态 |
| --- | --- | --- |
| macOS Apple Silicon 应用 | `bash scripts/build_desktop.sh dir` | 构建成功，打包后服务检查通过。 |
| macOS Apple Silicon DMG | `bash scripts/build_desktop.sh dmg` | 已生成，磁盘镜像校验通过。 |
| Linux / 麒麟 x86_64、ARM64 | `bash scripts/build_desktop.sh deb` | 已提供原生构建流程，待目标机器验证。 |
| Linux AppImage / RPM | 将 `deb` 替换为 `AppImage` 或 `rpm` | 需要对应打包工具，本次尚未验证。 |

统一构建入口暂未覆盖 Windows 和 Intel Mac。首次安装依赖需要联网，产物位于 `OpenCode/packages/desktop/dist/`。详见[完整构建指南](docs/BUILD.md)。

### 单独体验 Python 记忆服务

可以先使用 CLI，无需构建 Electron：

```bash
cd MemPulse
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .

# 显式创建合成演示数据，使用独立的本地数据库。
mempulse --db .mempulse/quickstart.sqlite3 demo
mempulse --db .mempulse/quickstart.sqlite3 search '麒麟适配'
mempulse --db .mempulse/quickstart.sqlite3 health
```

随附模型基于中文 BGE 编码器微调。未配置模型时，服务仍可使用词法和结构化检索。

在 `MemPulse/` 下启用 CLI 的本地模型推理：

```bash
python -m pip install -e '.[onnx]'
export MEMPULSE_MODEL_DIR="$PWD/../微调模型/revision4-model-bundle"
mempulse --db .mempulse/quickstart.sqlite3 health
```

频繁调用时，建议使用[组件说明](MemPulse/README.md)中的常驻服务接口，避免每次短命令都重新加载模型。

## 接入 Agent

MCP stdio 配置如下，将两处绝对路径替换为实际位置：

```json
{
  "mcpServers": {
    "mempulse": {
      "command": "/absolute/path/MemPulse/.venv/bin/mempulse",
      "args": [
        "--db", "/absolute/path/MemPulse/.mempulse/memory.sqlite3",
        "mcp"
      ]
    }
  }
}
```

MCP 工具包括 `resolve_topic`、`ingest_event`、`search_memory`、`restore_context`、`list_topics` 和 `forget_memory`。OpenCode 桌面集成还提供上下文注入和专用的 `memory_*` 工具，详见[桌面集成说明](OpenCode/docs/MEMPULSE.md)（英文）。

## 系统架构

下图展示当前 OpenCode 桌面集成与独立服务接口。更多 IDE 的插件属于后续规划，记忆核心本身独立于桌面宿主。

![系统简图：Electron 界面和 OpenCode 插件通过 MemoryBridge 调用 Python 记忆服务；CLI、MCP 和 HTTP 也可访问服务，底层使用 SQLite 与本地 ONNX 推理。](docs/assets/readme/architecture-zh.png)

- **OpenCode / Electron / SolidJS**：提供桌面会话、终端与记忆界面。
- **MemoryBridge**：通过 IPC、本地回环网关和 JSON-lines 通信，连接渲染器、Agent 插件与 Python 进程。
- **MemPulse / Python**：负责记忆行为。SQLite 保存持久记录，FTS5 与结构化关系支撑检索，TIDE 提供本地向量编码。
- **独立接口**：通过 CLI、MCP、HTTP 使用相同的记忆能力；`MemPulse/ui/` 另保留 React/Tauri 界面。

本地记忆存储不代表 Agent 对话完全离线。所选择的大模型提供商可能接收提示词与检索出来的上下文。

## 模型与权重

完整交付包含 `微调模型/revision4-model-bundle/`：

| 文件 | 用途 |
| --- | --- |
| `encoder/model-fp32.onnx` | 桌面应用默认使用的检索编码器。 |
| `encoder/model-int8-mixed.onnx` | 实验性混合精度版本，不作为默认配置。 |
| `encoder/` 中的 tokenizer 和配置 | 输入编码与推理参数。 |
| `weights/model.safetensors` | 用于继续训练或重新导出的原始权重。 |
| `manifest.json` | 原始文件大小与 SHA-256 校验清单。 |

清单列出的模型文件合计约 **1.01 GB**。提交仓库时，大权重文件由 Git LFS 管理。桌面构建前，`scripts/verify_models.py` 会验证全部 30 个清单文件。

模型基于 `BAAI/bge-base-zh-v1.5`。TIDE 编码器帮助定位候选话题，具体事实仍要回到话题内的事件与来源证据中检索。它不决定话题归属授权或记忆操作权限。混合 INT8 仍属实验配置，应用默认打包 FP32。评测范围和已知限制见[原始模型说明](微调模型/revision4-model-bundle/README.md)与[训练指南](MemPulse/docs/TRAINING.md)。

## 构建与验证

本次验证使用独立导出的源码目录，在 macOS ARM64 上重新安装依赖后构建。记录日期：**2026-09-17**。

| 检查 | 结果 |
| --- | --- |
| 后端与真实模型测试 | 70 项通过。 |
| 独立 WebUI | 生产构建成功，1 项验收测试通过。 |
| 桌面 TypeScript 与生产构建 | 通过。 |
| 打包后的记忆服务 | 25 项检查通过，包含 15 次检索请求和工作区持久化。 |
| macOS DMG | 生成成功，校验通过。 |

上述结果覆盖构建和打包后的服务，不代表完整桌面 GUI 人工验收，也不代表 Linux／麒麟性能验收。详见[构建验证记录](docs/BUILD-VERIFICATION.md)。

在 `MemPulse/` 目录运行后端测试：

```bash
python -m pip install -e '.[test,onnx]'
MEMPULSE_TEST_MODEL='../微调模型/revision4-model-bundle' \
  python -m pytest -q --strict-markers -m 'not standalone_webui'
```

独立 WebUI 的验收测试需先构建前端：

```bash
cd ui
npm ci
npm run build
cd ..
python -m pytest -q --strict-markers -m standalone_webui
```

OpenCode 的测试与类型检查应在对应包目录执行，并遵循该目录的 `AGENTS.md`。

## 工程目录

```text
.
├── MemPulse/                 Python 服务、CLI、MCP、测试与独立 UI
├── OpenCode/                 定制 Electron 桌面与 Agent 集成
├── 微调模型/
│   └── revision4-model-bundle/  推理与训练权重、tokenizer、校验清单
├── scripts/                  导出、模型验证与桌面构建入口
├── docs/                     文档、验证记录与 README 配图
├── README.md                 English
└── README.zh-CN.md           简体中文
```

完整本地交付中的 `release/` 单独存放安装包。构建产物和依赖可在本地生成，由 Git 忽略。比赛报告、私人数据与历史过程文件保存在公开源码目录之外。

## 文档导航

| 文档 | 语言 |
| --- | --- |
| [文档索引](docs/README.md) | 中文 |
| [完整桌面构建](docs/BUILD.md) | 中文 |
| [Python 服务与 CLI](MemPulse/README.md) | 中文 |
| [桌面集成](OpenCode/docs/MEMPULSE.md) | 英文 |
| [话题与任务契约](MemPulse/docs/TOPIC-CONTRACT-20260915.md) | 中文 |
| [训练与模型导出](MemPulse/docs/TRAINING.md) | 中文 |
| [构建验证](docs/BUILD-VERIFICATION.md) | 中文 |
| [发布准备](docs/RELEASING.md) | 中文 |

## 贡献与安全反馈

提交 Issue 或 PR 时，请说明涉及的组件、平台、复现步骤和实际验证结果，遵循[贡献指南](docs/CONTRIBUTING.md)及组件开发约定。不要在公开报告中附带凭据或个人记忆数据库。

安全问题请先阅读[安全反馈说明](docs/SECURITY.md)。敏感报告请使用仓库的私密漏洞报告入口。

## 许可与致谢

工程包含采用不同许可证的组件：

- **OpenCode**：保留 [MIT 许可证](OpenCode/LICENSE)。MemPulse 为独立定制项目，与上游维护者无隶属关系。
- **源自 Episodic 的指纹代码**：保留 [Apache-2.0 许可证](MemPulse/src/mempulse/_vendor/LICENSE)，复用范围见 [UPSTREAM](MemPulse/docs/UPSTREAM.md)。
- **MemPulse 自研代码**：采用 [Apache-2.0](LICENSE)，署名与来源信息见 [NOTICE](NOTICE)。
- **模型与依赖**：遵循各自条款。BGE 基础模型的[官方模型卡](https://huggingface.co/BAAI/bge-base-zh-v1.5)标注 MIT，已附带上游 [MIT 声明](docs/licenses/BGE-MIT.txt)。

来源索引见[第三方说明](docs/THIRD_PARTY.md)。
