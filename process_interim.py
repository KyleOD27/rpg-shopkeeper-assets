from PIL import Image
import os, json

SRC = "images/items_interim"
DST = "images/items_processed"
TARGET = (512, 512)
ITEM_SIZE = int(512 * 0.70)  # 70% of canvas = ~358px

RARITY_COLORS = {
    "mundane":   (60,  60,  85),   # muted navy
    "common":    (85,  85,  85),   # medium grey
    "uncommon":  (40,  85,  40),   # muted green
    "rare":      (40,  40, 120),   # muted blue
    "very_rare": (75,  40, 120),   # muted purple
    "legendary": (130, 80,  16),   # muted amber
    "artifact":  (130, 24,  24),   # muted crimson
}
DEFAULT_RARITY = "mundane"

with open("data/item_rarities.json") as f:
    rarities = json.load(f)

os.makedirs(DST, exist_ok=True)

files = sorted(f for f in os.listdir(SRC) if f.endswith(".png"))
for i, filename in enumerate(files, 1):
    item_name = filename[:-4]
    rarity = rarities.get(item_name, DEFAULT_RARITY)
    bg_color = RARITY_COLORS[rarity]

    img = Image.open(os.path.join(SRC, filename))
    if img.mode != "RGBA":
        img = img.convert("RGBA")

    img = img.resize((ITEM_SIZE, ITEM_SIZE), Image.NEAREST)

    canvas = Image.new("RGBA", TARGET, (*bg_color, 255))
    offset = ((TARGET[0] - ITEM_SIZE) // 2, (TARGET[1] - ITEM_SIZE) // 2)
    canvas.paste(img, offset, img)

    canvas.save(os.path.join(DST, filename), "PNG")
    print(f"[{i}/{len(files)}] {filename} ({rarity})")

print(f"\nDone. {len(files)} images written to {DST}/")
