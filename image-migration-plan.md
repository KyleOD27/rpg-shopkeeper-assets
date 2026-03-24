# Image Migration Plan: items/ → items_interim/

## Overview

Plan for replacing production item images with the new pixel art versions from `images/items_interim/`.

---

## Current State

| | `images/items/` (current) | `images/items_interim/` (replacement) |
|---|---|---|
| Resolution | 1024 × 1024 px | 64 × 64 px |
| Color depth | 24-bit RGB (full color) | 4-bit indexed (16 colors) |
| Avg file size | ~949 KB | ~68 KB |
| Total size | 639 MB | 48 MB |
| File count | 703 PNG files | 701 PNG files |
| Format | PNG | PNG |

---

## Potential End User Impacts

### Discord
- Discord scales images to fit chat width (~400px). A 64×64 image will render at roughly 64px — very small on desktop.
- Upscaling by Discord may use bilinear interpolation, which **blurs pixel art**. Nearest-neighbor is needed to keep crisp edges.
- 4-bit indexed color (16 colors) will produce visible **banding and dithering** compared to current full-color images.

### WhatsApp
- WhatsApp **recompresses** images on send, which degrades small images further.
- 64×64 images may not trigger a proper preview and could appear as tiny thumbnails rather than expanded images.

---

## Required Changes Before Swapping

### 1. Upscale images (critical)
- Scale from 64×64 to **256×256 or 512×512**
- Must use **nearest-neighbor interpolation** to preserve pixel art crispness
- Bilinear or bicubic will cause blurring

### 2. Convert to 24-bit PNG (recommended)
- Strip the 4-bit indexed palette
- Ensures correct color rendering across Discord, WhatsApp, and other platforms

### 3. Resolve missing files (2 files)
- `images/items/` has 2 files not present in `images/items_interim/`
- These need to either be generated in the new pixel art style or kept from the original set

---

## Proposed Migration Steps

1. Identify the 2 missing files between directories
2. Write/run a bulk upscale script (nearest-neighbor, 64→256px or 512px)
3. Convert all output to 24-bit PNG
4. QA check a sample on Discord and WhatsApp before full swap
5. Replace `images/items/` contents with processed images
6. Commit and push

---

## Open Questions

- Target upscale resolution: 256×256 or 512×512?
- Should originals in `images/items/` be archived or deleted after swap?
- Are the 701 interim images all final, or are more still being generated?
