import { createSignal, type JSX } from "solid-js"
import { useDialog } from "@opencode-ai/ui/context/dialog"
import { Dialog, DialogBody, DialogFooter, DialogHeader, DialogTitleGroup } from "@opencode-ai/ui/v2/dialog-v2"
import { ButtonV2 } from "@opencode-ai/ui/v2/button-v2"
import { useLanguage } from "@/context/language"
import "./memory-dialog.css"

/**
 * Confirmation for the destructive half of memory governance. Forgetting is
 * recorded as a tombstone rather than a row delete, but it is still not
 * something to trigger from a single click.
 */
export function ConfirmDialog(props: {
  title: JSX.Element
  description: JSX.Element
  confirmLabel: string
  variant?: "danger" | "neutral"
  onConfirm: () => Promise<void> | void
}) {
  const dialog = useDialog()
  const language = useLanguage()
  const [busy, setBusy] = createSignal(false)

  const confirm = async () => {
    setBusy(true)
    try {
      await props.onConfirm()
      dialog.close()
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog size="normal" fit containerClass="memory-dialog-container">
      <DialogHeader>
        <DialogTitleGroup title={props.title} description={props.description} />
      </DialogHeader>
      <DialogBody class="flex flex-col gap-2" />
      <DialogFooter>
        <ButtonV2 variant="ghost" onClick={() => dialog.close()} disabled={busy()}>
          {language.t("memory.action.cancel")}
        </ButtonV2>
        <ButtonV2
          variant={props.variant === "danger" ? "danger" : "contrast"}
          onClick={() => void confirm()}
          disabled={busy()}
        >
          {props.confirmLabel}
        </ButtonV2>
      </DialogFooter>
    </Dialog>
  )
}
