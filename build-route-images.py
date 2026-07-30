#!/usr/bin/env python3
"""
Turn the route-of-administration photos into transparent-background PNGs for the
stage 2 buttons.

Every source photo puts its subject on the same flat lavender backdrop,
RGB(196, 206, 255). This keys that backdrop out, keeping only the region
connected to the image border so similar colours inside the subject (the pale
blue capsule in Oral, for example) stay opaque. Partly transparent edge pixels
get their backdrop contribution unmixed so no lavender fringe survives on the
blue button.

Sources:  ea-work/data-for-daily-tasks/Routes of Administration - Images/
Output:   assets/routes/<route>.webp

WebP rather than PNG: these are photographs with an alpha channel, where PNG is
badly inefficient. The same seven images are 3.1 MB as PNG and 193 KB as WebP.

Run from the project folder: python3 build-route-images.py
"""
import os
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

SRC = Path(os.environ.get(
    "PE_ROUTE_IMAGES",
    Path(__file__).resolve().parents[2] / "data-for-daily-tasks" / "Routes of Administration - Images",
))
OUT = Path(__file__).parent / "assets" / "routes"

BACKDROP = np.array([196, 206, 255], dtype=np.float32)

# Distance from the backdrop colour, in RGB units. At or below SOLID a pixel is
# treated as pure backdrop; at or above CLEAR it is pure subject; between the two
# the alpha ramps, which keeps hair and glass edges soft.
SOLID, CLEAR = 10.0, 46.0

# The header mark, which lives in the same source folder as the route photos.
MARK_FILE = "Excipients Sourcing Navigator.jpg"

# The mark is blue line art on white. Same keying idea as the photos, with white
# as the backdrop instead of lavender, and a tighter ramp because the edges are
# vector-clean rather than photographic.
MARK_SOLID, MARK_CLEAR = 8.0, 60.0
MARK_H = 144          # 3x the 48px the header renders it at

# Source file -> output slug. Output names follow the project's kebab-case rule.
FILES = {
    "Oral.jpg": "oral",
    "Injectable.jpg": "injectable",
    "Inhalation _ Pulmonary.jpg": "inhalation-pulmonary",
    "Nasal.jpg": "nasal",
    "Topical.jpg": "topical",
    "Ocular.jpg": "ocular",
    "Vaginal _ Rectal.jpg": "rectal-vaginal",
}

# The tallest card renders the photo about 210 CSS px high, so 420 is 2x for
# retina without carrying pixels nobody sees.
TARGET_H = 420
QUALITY = 82

# The two supplier logo walls on the landing page. These are screenshots, so the
# source names are whatever the screenshot tool produced; replacing a wall means
# updating this map. Both sit on a flat #F5F5F5 backdrop, which gets keyed out so
# the white logo cards float on the page background instead of on a grey slab
# that cuts off the page's dot pattern.
#
# Neither frame is cropped, on purpose. The five columns sit at the same relative
# positions in both screenshots (gutter centres within 0.6% of each other), so
# rendering both at the same width lines the columns up between the two blocks.
# Cropping each to its own content would break that.
SUPPLIER_FILES = {
    "Screenshot 2026-07-30 at 06.38.48.png": "suppliers-featured",
    "Screenshot 2026-07-30 at 06.40.09.png": "suppliers-all",
}
SUPPLIER_BACKDROP = np.array([245, 245, 245], dtype=np.float32)
SUPPLIER_SOLID, SUPPLIER_CLEAR = 4.0, 14.0   # white cards are 17 away, so they stay
SUPPLIER_MAX_W = 1680                        # 2x the 820px the block renders at

# Rows to shave off the top of a wall. The featured screenshot caught four rows
# of a blue underline belonging to the heading above it, which otherwise renders
# as a stray blue dash under "Our Suppliers". Its cards start at row 42, so
# taking eight rows loses nothing. Trimming rows only, never columns, keeps the
# two walls the same width and their columns aligned.
SUPPLIER_TRIM_TOP = {"suppliers-featured": 8}

# Cards anchor the photo to their right edge, so its left edge floats somewhere
# in the middle of the card and would otherwise show as a hard vertical seam
# against the blue. Ramping alpha to zero across this fraction of the width
# makes the photo dissolve into the card instead.
FADE_W = 0.22


def key_out(path):
    rgb = np.asarray(Image.open(path).convert("RGB"), dtype=np.float32)
    dist = np.linalg.norm(rgb - BACKDROP, axis=2)

    # Soft alpha straight from the colour distance.
    alpha = np.clip((dist - SOLID) / (CLEAR - SOLID), 0.0, 1.0)

    # Only backdrop that reaches the border counts. Anything enclosed by the
    # subject stays fully opaque even if it happens to match the backdrop.
    is_bg = dist < CLEAR
    labels, n = ndimage.label(is_bg)
    border = np.concatenate([labels[0, :], labels[-1, :], labels[:, 0], labels[:, -1]])
    outer = np.isin(labels, np.unique(border[border > 0]))
    alpha = np.where(outer, alpha, 1.0)

    # Unmix the backdrop out of partly transparent pixels: observed = a*C + (1-a)*bg.
    a = alpha[..., None]
    with np.errstate(divide="ignore", invalid="ignore"):
        colour = np.where(a > 0.004, (rgb - (1 - a) * BACKDROP) / np.maximum(a, 1e-6), rgb)
    colour = np.clip(colour, 0, 255)

    out = np.dstack([colour, alpha * 255.0]).astype(np.uint8)
    im = Image.fromarray(out, mode="RGBA")

    # Crop to what is actually visible, then scale to a common height.
    bbox = im.getbbox()
    if bbox:
        im = im.crop(bbox)
    w, h = im.size
    im = im.resize((max(1, round(w * TARGET_H / h)), TARGET_H), Image.LANCZOS)
    return fade_left_edge(im)


def fade_left_edge(im):
    """Ramp alpha to zero across the left edge so it blends into the card."""
    arr = np.asarray(im).astype(np.float32)
    w = arr.shape[1]
    band = max(1, int(round(w * FADE_W)))

    x = np.linspace(0.0, 1.0, band, dtype=np.float32)
    ramp = x * x * (3.0 - 2.0 * x)              # smoothstep, no visible kink
    gradient = np.ones(w, dtype=np.float32)
    gradient[:band] = ramp

    arr[..., 3] *= gradient[None, :]
    return Image.fromarray(arr.astype(np.uint8), mode="RGBA")


def build_navigator_mark():
    """Header mark: blue line art on white, with all the white keyed out.

    Every white pixel goes, not just the ones reaching the image border, so the
    holes inside the molecule's nodes and the gap inside the compass ring become
    transparent too. That leaves pure blue line art that sits correctly on any
    background rather than only on a white header.
    """
    src = SRC / MARK_FILE
    if not src.exists():
        print(f"  skipped navigator mark, no source at {src}")
        return

    rgb = np.asarray(Image.open(src).convert("RGB"), dtype=np.float32)
    dist = np.linalg.norm(rgb - 255.0, axis=2)
    alpha = np.clip((dist - MARK_SOLID) / (MARK_CLEAR - MARK_SOLID), 0.0, 1.0)

    # Unmix white out of the anti-aliased edge pixels so no pale fringe survives.
    a = alpha[..., None]
    with np.errstate(divide="ignore", invalid="ignore"):
        colour = np.where(a > 0.004, (rgb - (1 - a) * 255.0) / np.maximum(a, 1e-6), rgb)
    colour = np.clip(colour, 0, 255)

    im = Image.fromarray(np.dstack([colour, alpha * 255.0]).astype(np.uint8), mode="RGBA")
    bbox = im.getbbox()
    if bbox:
        im = im.crop(bbox)
    w, h = im.size
    im = im.resize((max(1, round(w * MARK_H / h)), MARK_H), Image.LANCZOS)

    dest = Path(__file__).parent / "assets" / "navigator-mark.webp"
    im.save(dest, "WEBP", quality=90, method=6)
    print(f"  {MARK_FILE[:30]:30s} -> assets/navigator-mark.webp  "
          f"{im.size[0]}x{im.size[1]}  {dest.stat().st_size // 1024} KB  "
          f"renders {round(im.size[0] / 3)}x{MARK_H // 3} in the header")


def build_supplier_walls():
    """The landing page logo walls: key the flat grey backdrop to transparent.

    Only backdrop reaching the image border is removed, so a logo containing the
    same grey stays intact. The frames are left uncropped so the two walls'
    columns stay aligned with each other.
    """
    dest_dir = Path(__file__).parent / "assets"
    for src_name, slug in SUPPLIER_FILES.items():
        src = SRC / src_name
        if not src.exists():
            print(f"  skipped {slug}, no source at {src.name}")
            continue

        rgb = np.asarray(Image.open(src).convert("RGB"), dtype=np.float32)
        trim = SUPPLIER_TRIM_TOP.get(slug, 0)
        if trim:
            rgb = rgb[trim:]
        dist = np.linalg.norm(rgb - SUPPLIER_BACKDROP, axis=2)
        alpha = np.clip((dist - SUPPLIER_SOLID) / (SUPPLIER_CLEAR - SUPPLIER_SOLID), 0.0, 1.0)

        is_bg = dist < SUPPLIER_CLEAR
        labels, _ = ndimage.label(is_bg)
        border = np.concatenate([labels[0, :], labels[-1, :], labels[:, 0], labels[:, -1]])
        outer = np.isin(labels, np.unique(border[border > 0]))
        alpha = np.where(outer, alpha, 1.0)

        a = alpha[..., None]
        with np.errstate(divide="ignore", invalid="ignore"):
            colour = np.where(a > 0.004,
                              (rgb - (1 - a) * SUPPLIER_BACKDROP) / np.maximum(a, 1e-6), rgb)
        colour = np.clip(colour, 0, 255)

        im = Image.fromarray(np.dstack([colour, alpha * 255.0]).astype(np.uint8), mode="RGBA")
        w, h = im.size
        if w > SUPPLIER_MAX_W:
            im = im.resize((SUPPLIER_MAX_W, max(1, round(h * SUPPLIER_MAX_W / w))), Image.LANCZOS)

        dest = dest_dir / f"{slug}.webp"
        im.save(dest, "WEBP", quality=88, method=6)
        kept = round(float((np.asarray(im)[..., 3] > 8).mean()) * 100)
        print(f"  {src_name[:30]:30s} -> assets/{slug}.webp  "
              f"{im.size[0]}x{im.size[1]}  {dest.stat().st_size // 1024} KB  "
              f"{kept}% of frame opaque")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"source: {SRC}")
    missing = [f for f in FILES if not (SRC / f).exists()]
    if missing:
        raise SystemExit("missing source images: " + ", ".join(missing))

    total = 0
    for src_name, slug in FILES.items():
        im = key_out(SRC / src_name)
        dest = OUT / f"{slug}.webp"
        im.save(dest, "WEBP", quality=QUALITY, method=6)
        total += dest.stat().st_size
        kept = round(float((np.asarray(im)[..., 3] > 8).mean()) * 100)
        print(f"  {src_name:30s} -> assets/routes/{slug}.webp  "
              f"{im.size[0]}x{im.size[1]}  {dest.stat().st_size // 1024} KB  "
              f"{kept}% of frame opaque")
    print(f"\n  {len(FILES)} route images, {total // 1024} KB total")
    build_navigator_mark()
    build_supplier_walls()


if __name__ == "__main__":
    main()
