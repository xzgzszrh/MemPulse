import { existsSync } from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"
import base from "./electron-builder.config"

const directory = path.dirname(fileURLToPath(import.meta.url))
const model = path.resolve(directory, "../../../微调模型/revision4-model-bundle")
const service = path.resolve(directory, "../../../MemPulse/ui/src-tauri/binaries/mempulse-service-aarch64-apple-darwin")

if (process.platform !== "darwin" || process.arch !== "arm64")
  throw new Error("Build this DMG on an Apple Silicon Mac with a matching native memory service")
if (!existsSync(service)) throw new Error("Build MemPulse/scripts/build_desktop_sidecar.py --with-onnx first")
if (!existsSync(path.join(model, "encoder/model-fp32.onnx"))) throw new Error("The FP32 model bundle is missing")

export default {
  ...base,
  productName: "MemPulse Code",
  extraMetadata: { ...base.extraMetadata, version: "1.18.30-mempulse.20260915.1" },
  artifactName: "MemPulse-Code-${version}-mac-${arch}.${ext}",
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
  mac: {
    ...base.mac,
    target: [{ target: "dmg", arch: ["arm64"] }],
    identity: null,
    notarize: false,
  },
  dmg: { ...base.dmg, sign: false },
}
