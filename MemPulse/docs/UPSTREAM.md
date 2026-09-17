# 上游来源与复用边界

## Episodic

- 仓库：https://github.com/mhcoen/episodic
- 固定 commit：`cbce38e344a40909e6a0dfa16d694daaf8006d3c`
- 本地参考 checkout（不随源码分发）：`third_party/episodic/`，Apache-2.0。
- **直接代码复用**：`context_recovery/determinism.py` → `src/mempulse/_vendor/episodic_fingerprint.py`，恢复包使用其指纹算法。许可证随模块保存。
- **重新实现**：Event Fabric、存储、TopicCore、图谱、治理与传输层，以适配标准工具事件及本项目协议。

当前不是已完整移植 Episodic 的 fork。上游完整 CLI/模型测试尚未跑通；现有服务复用其话题工作集与隔离思路，并将已移植代码逐项记录在此。上游 Chroma、LLM 聊天循环未进入 MemPulse 主运行链路。

## shadcn/ui

Button/Card/Badge/Input/Tabs/Dialog/Textarea/Separator 经官方 CLI 安装，位于 `ui/src/components/ui`；基于 Radix、Tailwind、React，保留组件本地可编辑的工作方式。

## Hindsight

仅作服务接口、交互和混合检索参考，没有引入 PostgreSQL、复制后端或将其宣称为 MemPulse 的实际运行底座。
