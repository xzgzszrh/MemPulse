# TIDE 数据、训练与导出

当前提供**结构验收用合成数据**及真实训练代码，完整工程同时交付独立的 revision4 模型包。脚本语料尚需人工复核、轨迹扩写和困难样本迭代，不能把这份语料的结果称为真实用户场景成绩。

## 可重建的数据结构

- `data/topicshift_os_g_v0/`：2,000 话题 / 20,000 查询 / 13,000 identity pairs。
- 上级项目隔离，话题 split 1,600 / 200 / 200；类别比例 30/25/20/15/10。
- 查询时间不早于相关初始轨迹；字段包含 allowed_context、gold_topic_ids、route。
- `runs/tide_prepare/`：训练配置与 batch manifest；仅 train split 进入批次。
- 批内话题不重复，显式负例排除所有本批正例话题，重复 anchor 延后处理而非丢弃。

```bash
python -m training.generate --output data/topicshift_os_g_v0
python -m training.validate data/topicshift_os_g_v0
python -m training.train --data data/topicshift_os_g_v0 --output runs/tide_prepare
```

小样本检查可使用 `--topics 20 --queries 200`，按项目分组会得到 12/4/4；正式规模严格为 1600/200/200。

## 真实训练入口

准备本地 `BAAI/bge-base-zh-v1.5` 模型目录，安装独立训练环境 `pip install -e '.[train]'`。以下命令会实际运行训练；没有本地权重时拒绝执行，不自动下载。

```bash
python -m training.run_torch \
  --data data/topicshift_os_g_v0 --model-dir /path/to/local/bge-base-zh-v1.5 \
  --output runs/tide-experiment-01 --epochs 5 --batch-size 64
```

采用 PyTorch + Transformers 全参数训练；保留 FlagEmbedding 数据和模型接口作为对照。自定义 sampler 用于落实跨行假负例排除，未直接复用 FlagEmbedding 默认 batch loader。查询 128、话题 384 tokens，CLS + L2 归一化，1 正 7 负，温度 0.02，AdamW 2e-5、warmup 10%、weight decay 0.01。每 100 步验证未见项目 Top-1；输出逐步 loss、验证结果和 best 权重。此入口已做静态检查，GPU 实跑、OOM 调整和模型选模尚未验证。`--max-steps` 可用于试跑；减小 batch 会改变负样本数量，不能声称与 64 组等价。

## 导出与服务接入

```bash
python -m training.export_onnx --model-dir runs/tide-experiment-01/best --output artifacts/tide-onnx
MEMPULSE_MODEL_DIR=artifacts/tide-onnx mempulse --db .mempulse/model-demo.sqlite3 ui
```

导出 FP32 / INT8 ONNX、tokenizer 和小样本余弦检查；服务只从本地目录加载。现存旧模型空间的向量不会与新空间混合评分。导出和 ONNX 推理代码尚待实际权重验证，麒麟 SDK 尚未实机接入。

正式发布前还需：真实困难负样本挖掘与复核、NEW/AMBIGUOUS 联合阈值校准、三种子实验、FP32/INT8 差异报告、目标机 CPU/SDK 全链路测试。

参考：[BGE 模型卡](https://huggingface.co/BAAI/bge-base-zh-v1.5)、[FlagEmbedding 微调](https://github.com/FlagOpen/FlagEmbedding/tree/master/examples/finetune/embedder)。
