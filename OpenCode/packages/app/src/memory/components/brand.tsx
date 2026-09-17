import markOnLight from "../assets/mark-on-light.png"
import markOnDark from "../assets/mark-on-dark.png"
import wordmarkOnLight from "../assets/wordmark-on-light.png"
import wordmarkOnDark from "../assets/wordmark-on-dark.png"
import "./brand.css"

/**
 * MemPulse brand pieces. Each renders both colour-scheme variants and lets CSS
 * pick one from the document's `data-color-scheme`, so a theme switch swaps the
 * artwork with no JavaScript in the loop.
 *
 * Source artwork lives in packages/desktop/icons/mempulse-source; the files here
 * are produced by packages/desktop/scripts/generate-mempulse-icons.py.
 */

export function MemPulseMark(props: { size?: number; class?: string; title?: string }) {
  const size = () => props.size ?? 24
  return (
    <span data-component="mempulse-brand" class={props.class} style={{ width: `${size()}px`, height: `${size()}px` }}>
      <img data-scheme="light" src={markOnLight} width={size()} height={size()} alt={props.title ?? "MemPulse"} draggable={false} />
      <img data-scheme="dark" src={markOnDark} width={size()} height={size()} alt={props.title ?? "MemPulse"} draggable={false} />
    </span>
  )
}

/** Wordmark aspect ratio from the source artwork (width / height). */
const WORDMARK_RATIO = 1980 / 500

export function MemPulseWordmark(props: { height?: number; class?: string; fill?: boolean }) {
  const height = () => props.height ?? 28
  const width = () => Math.round(height() * WORDMARK_RATIO)
  // `fill` lets the wordmark take the container's width (used as a watermark);
  // otherwise it is sized by height like an icon.
  const style = () =>
    props.fill ? { width: "100%", "aspect-ratio": `${WORDMARK_RATIO}` } : { width: `${width()}px`, height: `${height()}px` }
  return (
    <span data-component="mempulse-brand" class={props.class} style={style()}>
      <img data-scheme="light" src={wordmarkOnLight} alt="MemPulse" draggable={false} />
      <img data-scheme="dark" src={wordmarkOnDark} alt="MemPulse" draggable={false} />
    </span>
  )
}
