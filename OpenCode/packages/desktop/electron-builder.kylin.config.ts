import { existsSync } from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"
import base from "./electron-builder.config"

const directory = path.dirname(fileURLToPath(import.meta.url))
const model = path.resolve(directory, "../../../微调模型/revision4-model-bundle")
const service = path.resolve(
  directory,
  `../../../MemPulse/ui/src-tauri/binaries/mempulse-service-${process.arch === "arm64" ? "aarch64" : "x86_64"}-unknown-linux-gnu`,
)
if (process.platform !== "linux" || !["x64", "arm64"].includes(process.arch))
  throw new Error("Build on the target Linux x64/arm64 machine; cross-compiling this sidecar is not supported")
if (!existsSync(service)) throw new Error("Build MemPulse/scripts/build_desktop_sidecar.py --with-onnx first")
if (!existsSync(path.join(model, "encoder/model-fp32.onnx"))) throw new Error("The FP32 model bundle is missing")

export default {
  ...base,
  productName: "MemPulse Code",
  extraMetadata: { ...base.extraMetadata, version: "1.18.30-mempulse.20260915.2" },
  artifactName: "mempulse-code-kylin-${arch}.${ext}",
  publish: null,
  extraResources: [
    ...(Array.isArray(base.extraResources) ? base.extraResources : []).filter(
      (resource) => typeof resource === "string" || resource.from !== "native/",
    ),
    {
      from: model,
      to: "mempulse/models/tide",
      filter: ["manifest.json", "encoder/**", "!encoder/model-int8-mixed.onnx"],
    },
  ],
}
