# MemPulse

> 记忆是沿着话题不断生长的脉络

MemPulse 是本地优先的 OS Agent 记忆工程。工具事件、对话与用户配置进入 SQLite；话题保存目标、事件链、标签、版本和恢复缺口。CLI、MCP 和 React + Ant Design + Tauri 桌面工作台调用同一个 Python 服务。

## 快速开始

需要 Python 3.10+、Node.js 20+。本次开发已在 macOS ARM64、Python 3.13、Node 24 验证。

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[web,test,vector]'
cd ui
npm ci
npm run build
cd ..
mempulse --db .mempulse/demo.sqlite3 demo
mempulse --db .mempulse/demo.sqlite3 ui --port 51983
```

打开 [本地工作台](http://127.0.0.1:51983)。`demo` 只写入明确标记的合成样例。真实数据请使用另一数据库。

桌面前端使用 React 19 + TypeScript + Ant Design 6；Tauri 2 负责 native window、sidecar 生命周期与 JSON-lines IPC。浏览器预览可通过 `cd ui && npm run dev` 和 `PYTHONPATH=src .venv/bin/python scripts/desktop_dev.py` 启动。

## 给 Agent 使用

CLI 默认返回 JSON，`yishu` 是兼容别名。全局选项写在子命令前。

```bash
mempulse --db .mempulse/memory.sqlite3 ingest '报告需求已确认' --topic '客户交付'
mempulse --db .mempulse/memory.sqlite3 ingest --file event.json
mempulse search '客户交付'
mempulse resolve '继续那个报告'
mempulse restore --topic-id topic_xxx
mempulse checkpoint topic_xxx
mempulse relations self person_zhang
mempulse forget event_xxx
mempulse forget event_xxx --field metadata.private_phone
mempulse health
```

`--user` 指定本地用户命名空间，默认 `default`。这用于数据隔离，不代替多用户服务器身份认证；HTTP 工作台固定使用本地默认用户，只绑定 loopback。

MCP stdio 配置：

```json
{
  "mcpServers": {
    "mempulse": {
      "command": "/absolute/path/MemPulse/.venv/bin/mempulse",
      "args": ["--db", "/absolute/path/MemPulse/.mempulse/memory.sqlite3", "mcp"]
    }
  }
}
```

工具包括 `resolve_topic`（只读）、`ingest_event`、`search_memory`、`restore_context`、`list_topics`、`forget_memory`。HTTP API 文档位于 `/docs`；合并、拆分、归属纠正和字段遗忘接口也列在那里。

## 当前已经实现

- SQLite WAL、事务、幂等事件写入、派生来源；写入失败整体回滚。
- 中文双字切分 FTS5、结构化标签和有界标签图；NEW/RESUME/ATTACH/AMBIGUOUS 路由。
- 按话题恢复字段、证据、缺口与检查点；话题归属纠正、合并和拆分。
- CPR 显式/临时/fallback 处理；有效时间、替代链与 disputed 知识版本。
- 同一事件上的共同参与集合查询及分页。
- 事件/话题遗忘、metadata 字段定向擦除、派生摘要重建、FTS 清理、检查点失效；备份恢复重放 tombstone。
- 桌面工作台的事件录入、话题浏览、中文搜索、恢复字段、检查点、偏好/知识治理和遗忘回执。
- 可选本地 ONNX 编码器；合成数据生成/验证、对比学习训练代码和 ONNX/INT8 导出代码。

## 当前不应宣称已经完成的部分

- 默认没有加载 BGE；界面和 `health` 显示 `embedding_backend=unloaded`。规则/FTS 结果不是 TIDE 微调成绩。
- 麒麟 SDK 未获得目标机实测；没有伪造 C ABI，也没有把 ONNX Runtime 当作 SDK 适配通过。
- 训练数据是结构验收用合成 v0，尚未经过完整人工复核；真实权重训练、量化精度和三种子评测未运行。
- 已通过 SQL/FTS 与独立 HNSW 召回融合候选；向量按用户/模型版本隔离并从 SQLite 重建。已测试 1 万个 768 维合成向量，真实 BGE 全链路仍须权重验证。
- 缺少强制标签的话题显示“待补全”。`MEMPULSE_STRICT_TAGS=1` 开启正式检索准入；默认保留草稿检索，便于未加载模型时开发和纠正。
- 关系、别名、共享知识、合并/拆分和遗忘通过结构化 CLI/API 表达；宿主 Agent 将自然语言转换为这些调用。后台 worker 自动处理维护任务并重试；SDK 目标平台的离线依赖包仍需按目标环境生成。
- 字段遗忘验证覆盖字面内容与已知派生对象，不承诺语义改写、文件系统快照或第三方备份物理擦除。
- 原版 Episodic 的完整模型链未集成，准确复用范围见 [UPSTREAM](docs/UPSTREAM.md)。

## 验证

```bash
python -m pytest -q
python -m scripts.verify
cd ui && npx tsc --noEmit && npm run build
```

`reports/verification.json` 是本地小样本验收记录，标明硬件、负载、模型状态与实际耗时。它不是比赛的 1 万话题、BGE、麒麟 SDK 性能报告。

## 数据与微调

见 [训练说明](docs/TRAINING.md)。已生成数据目录为 `data/topicshift_os_g_v0`（可重建，不纳入源码版本控制）。

```bash
python -m training.generate --output data/topicshift_os_g_v0
python -m training.validate data/topicshift_os_g_v0
python -m training.train --data data/topicshift_os_g_v0 --output runs/tide_prepare
```

真正训练使用 `python -m training.run_torch --model-dir /local/bge ...`，必须有本地权重和训练环境；准备脚本不会自动运行训练。

## 备份与恢复

```bash
python -m scripts.backup .mempulse/memory.sqlite3 backups/memory.sqlite3
python -m scripts.restore_backup --snapshot backups/memory.sqlite3 --current .mempulse/memory.sqlite3 --output restored/memory.sqlite3
```

恢复写入新文件并重放当前遗忘记录，不直接覆盖正在使用的数据库。`deploy/mempulse.service` 为 Linux 用户服务模板，部署前按实际安装路径修改；未在 macOS 上安装 systemd 服务。

## 工程结构

```text
src/mempulse/     服务、事件、话题、图谱、治理、CLI、MCP、HTTP
ui/              React + Ant Design + Vite + Tauri 2
training/        合成数据、校验、批次准备、训练和导出
scripts/         验收、备份和恢复
tests/           单元与集成测试
docs/            使用说明、训练和上游来源
```

本地后台任务可手动排空：`mempulse worker`。麒麟适配只在设置 `MEMPULSE_KYLIN_SDK` 后探测动态库，缺少目标头文件/ABI 时返回 `needs_header_verification`，不会静默降级。

设计规模的 SQL 候选 smoke test：`python -m scripts.scale_smoke --topics 10000`。它测的是未加载模型的候选/规则链，不是 500ms 官方成绩。

## 常驻服务与发布包

加载真实模型后，Agent 应使用轻量 HTTP CLI，避免每条命令重新加载模型：

```bash
mempulse --db .mempulse/memory.sqlite3 ui
MEMPULSE_API_URL=http://127.0.0.1:51983 mempulse search '继续报告'
mempulse --server http://127.0.0.1:51983 restore --topic-id topic_xxx
```

构建后的 `dist/` 包含 wheel、源码包和 SHA256 清单，wheel 内置已编译的 shadcn WebUI，安装后无需 Node。构建命令为 `python -m scripts.build_release`。

## Agent 运行方式

安装 Skill 后，每个非 trivial turn 先执行一次 `yishu context "当前请求" --json`；工具由宿主真正执行，结果再通过 `yishu run ... --status ... --result-json ...` 写回。需要常驻模型时使用 Unix socket：

```bash
yishu daemon --socket /tmp/mempulse.sock --db .mempulse/memory.sqlite3
MEMPULSE_SOCKET=/tmp/mempulse.sock yishu context "继续昨天的报告" --json
```

Linux 用户服务模板是 `deploy/yishu-memd.service`；HTTP WebUI 仍由 `yishu ui` 提供。

## MemPulse Desktop

桌面版使用 React + TypeScript + Ant Design 6 与 Tauri 2。Tauri 启动一个随应用分发的 Python sidecar，前端通过 JSON-lines IPC 调用同一套 `TopicFacade`；开发浏览器预览使用本地 loopback 端口 51984。

```bash
cd ui
npm ci
npm run dev
# 另一个终端：PYTHONPATH=../src ../.venv/bin/python ../scripts/desktop_dev.py
# 构建桌面服务与 native bundle（当前平台）
npm run desktop:build
```

首次启动默认打开 `演示工作区`，演示数据写入应用数据目录的 `desktop-demo.sqlite3`；切换到 `个人工作区` 后使用独立的 `memory.sqlite3`。桌面 UI 对应后端的事件流、持续话题、偏好 CPR、知识版本、检查点、冲突和精准遗忘接口。Tauri sidecar 目标文件按当前 Rust target triple 命名，并由 bundle 的 `externalBin` 管理。

## TIDE revision4 本地模型

支持交付包根目录或其 `encoder` 目录，默认 FP32。无需 PyTorch 或云端模型下载：

```bash
uv pip install --python .venv/bin/python 'onnxruntime>=1.20,<2' 'tokenizers>=0.21,<0.23'
MEMPULSE_MODEL_DIR='../微调模型/revision4-model-bundle' PYTHONPATH=src .venv/bin/python -m mempulse --help
```

`OnnxEncoder` 按交付清单核验模型、tokenizer 和输入配置。查询添加固定 BGE 指令，完整查询上限 128 tokens、话题上限 384 tokens；超限时原事件照常保留，检索回退到词法/图谱。每个模型精度和配置具有独立版本，启用新模型会重建向量索引。

桌面 JSON-lines API 支持 `configure_model`（参数 `model_dir`、`precision`）及 `enrich_demo`。前者将验证过的配置保存在指定桌面数据目录的 `model.json`；后者只允许在演示工作区写入版本化合成数据，可重复执行。默认不自动归题，明确的会话/话题 ID 绑定继续有效。混合 INT8 必须通过本机与 FP32 的数值检查才可启用，失败时保留原配置。

本轮 M1 Pro/ONNX Runtime 1.30.0 测试中，FP32 可用，混合 INT8 未通过数值对齐。测试设计、全部统计、错误分析、阈值验证及局限见 独立保存的本地接入与多轮测试记录（不随源码发布）。相同的 132 条查询在三种配置下各运行三轮，并验证持续写入、检查点恢复、偏好作用域与 JSON-lines 通信。结果不能代替麒麟 SDK 和目标硬件验收。

```bash
PYTHONPATH=src MEMPULSE_TEST_MODEL='../微调模型/revision4-model-bundle' .venv/bin/python -m pytest -q
PYTHONPATH=src .venv/bin/python scripts/evaluate_tide.py --model '../微调模型/revision4-model-bundle' --output reports/tide-new-run --rounds 3
PYTHONPATH=src .venv/bin/python scripts/analyze_tide_results.py reports/tide-new-run
```

## 开源发布

源码整理、许可证边界与发布检查见 [发布准备](../docs/RELEASING.md)。完整工程包含相邻的 `微调模型/revision4-model-bundle/`；比赛报告与历史过程材料独立保存。
