"""Generate the MemPulse brand assets from the source artwork in icons/mempulse-source.

Sources (kept as delivered by design):
  mark.png            square pixel-M mark, black + brand blue, transparent background
  wordmark-black.png  horizontal wordmark for light surfaces
  wordmark-white.png  horizontal wordmark for dark surfaces

Outputs:
  icons/mempulse/*, icons/mempulse.iconset/*   application icons (macOS icns, Windows ico, Linux pngs)
  ../app/src/memory/assets/*                    in-app mark and wordmark, one file per colour scheme
"""

from pathlib import Path
from subprocess import run
import argparse

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "icons" / "mempulse-source"
OUTPUT = ROOT / "icons" / "mempulse"
ICONSET = ROOT / "icons" / "mempulse.iconset"
ASSETS = ROOT.parent / "app" / "src" / "memory" / "assets"

BRAND_BLUE = (0x1F, 0x5B, 0xFF)


def trimmed(path: Path, pad: float = 0.04, alpha_threshold: int = 0) -> Image.Image:
    image = Image.open(path).convert("RGBA")
    box = image.getchannel("A").point(lambda value: 255 if value > alpha_threshold else 0).getbbox()
    if not box:
        return image
    margin = int(max(box[2] - box[0], box[3] - box[1]) * pad)
    left, top = max(0, box[0] - margin), max(0, box[1] - margin)
    right, bottom = min(image.width, box[2] + margin), min(image.height, box[3] + margin)
    return image.crop((left, top, right, bottom))


def recolor_dark_to_white(image: Image.Image) -> Image.Image:
    """Keep the blue squares, turn the black strokes white for dark surfaces."""
    out = image.copy()
    pixels = out.load()
    for y in range(out.height):
        for x in range(out.width):
            r, g, b, a = pixels[x, y]
            if a and max(r, g, b) < 96:
                pixels[x, y] = (255, 255, 255, a)
    return out


def square(image: Image.Image, size: int) -> Image.Image:
    """Fit onto a transparent square canvas, centred."""
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ratio = min(size / image.width, size / image.height)
    fitted = image.resize((max(1, round(image.width * ratio)), max(1, round(image.height * ratio))), Image.LANCZOS)
    canvas.alpha_composite(fitted, ((size - fitted.width) // 2, (size - fitted.height) // 2))
    return canvas


def app_icon(mark: Image.Image, size: int) -> Image.Image:
    """White rounded square with the mark — reads on light and dark docks alike."""
    scale = size / 1024
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    # Match the 824/1024 visible body used by the existing macOS app icon.
    inset = round(100 * scale)
    draw.rounded_rectangle((inset, inset, size - inset - 1, size - inset - 1), radius=round(204 * scale), fill=(255, 255, 255, 255))
    target = round(576 * scale)
    fitted = square(mark, target)
    image.alpha_composite(fitted, ((size - target) // 2, (size - target) // 2))
    return image


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app-icons-only", action="store_true", help="Regenerate app/Dock icons without changing in-app artwork")
    args = parser.parse_args()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    ICONSET.mkdir(parents=True, exist_ok=True)
    ASSETS.mkdir(parents=True, exist_ok=True)

    mark = trimmed(SOURCE / "mark.png", pad=0.0)
    wordmark_black = trimmed(SOURCE / "wordmark-black.png")
    wordmark_white = trimmed(SOURCE / "wordmark-white.png")

    if not args.app_icons_only:
        # In-app assets. 2x-and-then-some so they stay crisp on retina at the sizes used.
        square(mark, 256).save(ASSETS / "mark-on-light.png")
        square(recolor_dark_to_white(mark), 256).save(ASSETS / "mark-on-dark.png")
        for name, image in (("wordmark-on-light.png", wordmark_black), ("wordmark-on-dark.png", wordmark_white)):
            height = 160
            image.resize((round(image.width * height / image.height), height), Image.LANCZOS).save(ASSETS / name)

    # Application icons.
    # Ignore nearly transparent source specks when finding the mark's visual centre.
    mark = trimmed(SOURCE / "mark.png", pad=0.01, alpha_threshold=128)
    for size in (16, 32, 128, 256, 512):
        app_icon(mark, size).save(ICONSET / f"icon_{size}x{size}.png")
        app_icon(mark, size * 2).save(ICONSET / f"icon_{size}x{size}@2x.png")
    app_icon(mark, 1024).save(OUTPUT / "icon.png")
    app_icon(mark, 512).save(OUTPUT / "dock.png")
    app_icon(mark, 256).save(OUTPUT / "128x128@2x.png")
    app_icon(mark, 128).save(OUTPUT / "128x128.png")
    app_icon(mark, 64).save(OUTPUT / "64x64.png")
    app_icon(mark, 32).save(OUTPUT / "32x32.png")
    app_icon(mark, 256).save(OUTPUT / "StoreLogo.png")
    app_icon(mark, 1024).save(OUTPUT / "icon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    run(["iconutil", "-c", "icns", str(ICONSET), "-o", str(OUTPUT / "icon.icns")], check=True)
    print("brand assets written to", OUTPUT, "and", ASSETS)


if __name__ == "__main__":
    main()
