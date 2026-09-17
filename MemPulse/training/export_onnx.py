"""Export an already-trained local BGE model; no downloads."""

from pathlib import Path


def export(model_dir, output):
    import torch
    import torch.nn.functional as F
    from transformers import AutoModel, AutoTokenizer
    import onnxruntime as ort
    from onnxruntime.quantization import quantize_dynamic, QuantType

    root = Path(output)
    root.mkdir(parents=True, exist_ok=True)
    base = AutoModel.from_pretrained(model_dir, local_files_only=True).eval()
    tok = AutoTokenizer.from_pretrained(model_dir, local_files_only=True)

    class Encoder(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.base = base

        def forward(self, input_ids, attention_mask, token_type_ids):
            x = self.base(
                input_ids=input_ids,
                attention_mask=attention_mask,
                token_type_ids=token_type_ids,
            ).last_hidden_state[:, 0]
            return F.normalize(x, p=2, dim=1)

    model = Encoder().eval()
    inputs = tok(
        ["继续客户交付报告", "核验当前模板"], return_tensors="pt", padding=True
    )
    names = ["input_ids", "attention_mask", "token_type_ids"]
    values = tuple(inputs[k] for k in names)
    torch.onnx.export(
        model,
        values,
        str(root / "model.onnx"),
        input_names=names,
        output_names=["sentence_embedding"],
        dynamic_axes={
            **{k: {0: "batch", 1: "sequence"} for k in names},
            "sentence_embedding": {0: "batch"},
        },
        opset_version=17,
        dynamo=False,
    )
    tok.save_pretrained(root)
    quantize_dynamic(
        str(root / "model.onnx"),
        str(root / "model.int8.onnx"),
        weight_type=QuantType.QInt8,
    )
    import numpy as np, json

    with torch.no_grad():
        reference = model(*values).numpy()
    check = {}
    for name in ("model.onnx", "model.int8.onnx"):
        session = ort.InferenceSession(
            str(root / name), providers=["CPUExecutionProvider"]
        )
        v = session.run(None, {k: inputs[k].numpy() for k in names})[0]
        check[name] = float(
            np.min(
                (v * reference).sum(-1)
                / (np.linalg.norm(v, axis=1) * np.linalg.norm(reference, axis=1))
            )
        )
    (root / "export_check.json").write_text(
        json.dumps({"fixture_min_cosine": check, "sdk_tested": False}, indent=2)
    )
    return check


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--model-dir", required=True)
    p.add_argument("--output", required=True)
    a = p.parse_args()
    print(export(a.model_dir, a.output))
