# Image Migration Plan: items_interim/ → items/

## Current State (updated 2026-03-25)

| | `images/items/` (production) | `images/items_interim/` (replacement) |
|---|---|---|
| Resolution | 1024 × 1024 px | 64×64 (650 files) or 128×128 (53 files) |
| Color mode | 24-bit RGB | Palette/indexed 'P' (544 files) or RGBA (159 files) |
| Total size | 639 MB | 5.5 MB |
| File count | 703 PNG files | 703 PNG files |
| Filename match | — | ✅ All 703 filenames match |

---

## End User Platform Concerns

### Discord
- Displays images up to ~400px wide. A raw 64×64 image renders tiny.
- Discord's upscaler uses bilinear interpolation → **blurs pixel art**.
- Indexed palette color can produce banding artifacts.
- **Fix:** Pre-upscale to 512×512 with nearest-neighbor before upload.

### WhatsApp
- Recompresses images on send, degrading small images further.
- Images below ~200px may not trigger expanded preview.
- **Fix:** Same 512×512 upscale resolves this.

---

## Technical Implementation

### Step 1 — Normalize and upscale (`process_interim.py`)

Write a Python script using Pillow that:

1. Iterates all 703 PNGs in `images/items_interim/`
2. Converts palette mode `'P'` → `'RGBA'` (preserves transparency)
3. Upscales to **512×512** using `Image.NEAREST` (nearest-neighbor)
4. Saves output to `images/items_processed/` as 24-bit RGBA PNG

```python
from PIL import Image
import os

SRC = "images/items_interim"
DST = "images/items_processed"
TARGET = (512, 512)

os.makedirs(DST, exist_ok=True)

for filename in os.listdir(SRC):
    if not filename.endswith(".png"):
        continue
    img = Image.open(os.path.join(SRC, filename))
    if img.mode == "P":
        img = img.convert("RGBA")
    elif img.mode != "RGBA":
        img = img.convert("RGBA")
    img = img.resize(TARGET, Image.NEAREST)
    img.save(os.path.join(DST, filename), "PNG")
    print(f"  {filename}: {img.size} {img.mode}")

print("Done.")
```

**Why 512×512:**
- 8× upscale from 64×64 keeps each source pixel as a crisp 8×8 block
- 4× upscale from 128×128 images — consistent output
- Large enough for Discord and WhatsApp previews
- Still 4× smaller in linear dimension than the current 1024×1024 source

### Step 2 — QA spot check

Before replacing production:
- Pick ~10 representative images from `items_processed/`
- Post to Discord and WhatsApp manually and verify they render crisply
- Check transparency renders correctly (items with transparent backgrounds)

### Step 3 — Replace production images

Once QA passes:

```bash
# Archive originals (optional but recommended)
mv images/items images/items_original_backup

# Swap in processed images
mv images/items_processed images/items
```

Or overwrite in place if archiving is not needed:
```bash
cp images/items_processed/*.png images/items/
```

### Step 4 — Commit and push

```bash
git add images/items/
git commit -m "Replace item images with upscaled pixel art (512×512, nearest-neighbor)"
git push
```

---

## Open Decisions (needs answer before proceeding)

| Decision | Options | Recommendation |
|---|---|---|
| Target resolution | 256×256 or 512×512 | **512×512** — safe for Discord/WhatsApp, still 4× smaller than originals |
| Archive originals? | Keep backup or delete | Keep as `items_original_backup/` initially, delete after confirmed working |
| items_interim status | Are all 703 final? | Confirm before running script — any regenerated files should land in interim first |

---

## Estimated Output

| Metric | Value |
|---|---|
| Output resolution | 512 × 512 px |
| Estimated avg file size | ~50–150 KB per image |
| Estimated total size | ~35–100 MB (vs 639 MB today) |
| Script runtime | ~1–2 min for 703 files |