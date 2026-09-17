"""Explicit full-parameter BGE contrastive training on a local model directory.

The custom sampler retains topic IDs and excludes false in-batch negatives.
FlagEmbedding-format data remains available; this auditable PyTorch runner owns
batch assembly because the topic exclusions are stricter than ordinary batches.
"""

import json
import random
from pathlib import Path
from .train import build_batches, TRAIN_CONFIG
from .validate import read_jsonl, validate_dataset


def run(
    data_root, model_dir, output, epochs=5, batch_size=64, max_steps=None, seed=20260911
):
    import torch
    import torch.nn.functional as F
    from transformers import AutoModel, AutoTokenizer, get_linear_schedule_with_warmup

    data_root = Path(data_root)
    model_dir = Path(model_dir)
    output = Path(output)
    if not model_dir.is_dir():
        raise ValueError(
            "Provide a local BGE model directory; network downloads are disabled"
        )
    if not 1 <= epochs <= 5:
        raise ValueError("epochs must be 1..5")
    validate_dataset(data_root)
    pairs = read_jsonl(data_root / "identity_pairs.jsonl")
    train_pairs = [p for p in pairs if p["split"] == "train"]
    valid_pairs = [p for p in pairs if p["split"] == "validation"]
    topics = {t["topic_id"]: t for t in read_jsonl(data_root / "topics.jsonl")}
    pair_map = {p["pair_id"]: p for p in train_pairs}
    torch.manual_seed(seed)
    random.seed(seed)
    device = (
        "cuda"
        if torch.cuda.is_available()
        else ("mps" if torch.backends.mps.is_available() else "cpu")
    )
    tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True)
    model = AutoModel.from_pretrained(model_dir, local_files_only=True).to(device)
    model.gradient_checkpointing_enable()
    optimizer = torch.optim.AdamW(model.parameters(), lr=2e-5, weight_decay=0.01)
    plans = [
        build_batches(train_pairs, batch_size=batch_size, seed=seed + i)
        for i in range(epochs)
    ]
    total = min(sum(len(p) for p in plans), max_steps or 10**9)
    scheduler = get_linear_schedule_with_warmup(
        optimizer, max(1, int(0.1 * total)), max(1, total)
    )
    output.mkdir(parents=True, exist_ok=True)
    if (output / "training_log.jsonl").exists():
        raise FileExistsError("Use a new output directory for each run")

    def encode(texts, length):
        tokens = tokenizer(
            texts, padding=True, truncation=True, max_length=length, return_tensors="pt"
        ).to(device)
        return F.normalize(model(**tokens).last_hidden_state[:, 0], p=2, dim=1)

    def evaluate():
        model.eval()
        candidates = [t for t in topics.values() if t["split"] == "validation"]
        with torch.no_grad():
            vectors = torch.cat(
                [
                    encode([t["summary"] for t in candidates[i : i + 16]], 384)
                    for i in range(0, len(candidates), 16)
                ]
            )
            index = {t["topic_id"]: i for i, t in enumerate(candidates)}
            correct = 0
            for i in range(0, len(valid_pairs), 16):
                rows = valid_pairs[i : i + 16]
                pred = (
                    (encode([p["anchor"] for p in rows], 128) @ vectors.T)
                    .argmax(dim=1)
                    .tolist()
                )
                correct += sum(
                    v == index[p["positive_topic_id"]] for v, p in zip(pred, rows)
                )
        model.train()
        return correct / max(1, len(valid_pairs))

    step = 0
    best = -1
    with (output / "training_log.jsonl").open("w") as log:
        for plan in plans:
            for batch in plan:
                if max_steps and step >= max_steps:
                    break
                records = batch["records"]
                if any(len(r["hard_negative_topic_ids"]) != 7 for r in records):
                    raise ValueError("Insufficient negatives; reduce batch size")
                queries = [pair_map[r["pair_id"]]["anchor"] for r in records]
                texts = [
                    topics[tid]["summary"]
                    for r in records
                    for tid in [r["positive_topic_id"], *r["hard_negative_topic_ids"]]
                ]
                model.train()
                optimizer.zero_grad()
                q = encode(queries, 128)
                p = encode(texts, 384)
                logits = (q @ p.T) / 0.02
                loss = F.cross_entropy(
                    logits, torch.arange(len(records), device=device) * 8
                )
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                scheduler.step()
                step += 1
                record = {
                    "step": step,
                    "loss": float(loss.detach()),
                    "device": device,
                    "groups": len(records),
                }
                if step % 100 == 0 or step == total:
                    record["validation_top1"] = evaluate()
                    if record["validation_top1"] > best:
                        best = record["validation_top1"]
                        model.save_pretrained(output / "best")
                        tokenizer.save_pretrained(output / "best")
                log.write(json.dumps(record) + "\n")
                log.flush()
    result = {
        "status": "TRAINED",
        "steps": step,
        "validation_top1": best,
        "device": device,
        "config": TRAIN_CONFIG,
        "model_source": str(model_dir),
        "seed": seed,
        "warning": "Synthetic schema corpus; not an accepted benchmark without human review",
    }
    (output / "run.json").write_text(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--data", required=True)
    p.add_argument("--model-dir", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--epochs", type=int, default=5)
    p.add_argument("--batch-size", type=int, default=64)
    p.add_argument("--max-steps", type=int)
    a = p.parse_args()
    print(
        json.dumps(
            run(a.data, a.model_dir, a.output, a.epochs, a.batch_size, a.max_steps),
            indent=2,
        )
    )
