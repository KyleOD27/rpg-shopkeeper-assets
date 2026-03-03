# RPG Shopkeeper Assets

## PixelLab MCP

PixelLab is available as an MCP server for generating pixel art game assets. All creation tools are **non-blocking** — they return a job ID immediately and process in the background (2-5 minutes). Use the corresponding `get_*` tool to check status and retrieve download links.

### Available Tools

| Tool | Purpose |
|------|---------|
| `create_character` / `animate_character` | Directional character sprites (4/8 dir) and animations. Characters persist and can be reused via `character_id`. |
| `create_topdown_tileset` | 16-tile Wang tilesets for seamless terrain transitions. Chain tilesets using `lower_base_tile_id`/`upper_base_tile_id` for consistency. |
| `create_sidescroller_tileset` | 16-tile platformer tilesets with side-view perspective. |
| `create_isometric_tile` | Individual isometric pixel art tiles. Use same `seed` across tiles for visual consistency. |
| `create_map_object` | Pixel art objects with transparent backgrounds for map placement. |
| `create_tiles_pro` | Advanced tile creation with full control over view angle, depth, and style. |

Each create tool has matching `get_*`, `list_*`, and `delete_*` tools.

### Key Parameters

- **view**: `high top-down` (RTS) or `low top-down` (RPG) — pick based on game perspective
- **outline**: `lineless`, `single color outline`
- **shading**: `basic shading`, `medium shading`
- **detail**: `low detail`, `medium detail`, `high detail`
- **proportions** (characters): `default`, `chibi`, `cartoon`, `stylized`, `realistic_male`, `realistic_female`, `heroic`
- **tile_size**: default 16x16 for tilesets, 32px for isometric

### Workflow

1. Call a `create_*` tool — get back a job ID immediately
2. Queue dependent operations right away (no need to wait)
3. Poll with `get_*` to check status (`processing` / `completed` / `failed`)
4. Download links require no auth — UUIDs act as keys
