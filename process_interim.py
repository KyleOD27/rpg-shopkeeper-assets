from PIL import Image
import os

SRC = "images/items_interim"
DST = "images/items_processed"
TARGET = (512, 512)

os.makedirs(DST, exist_ok=True)

files = [f for f in os.listdir(SRC) if f.endswith(".png")]
for i, filename in enumerate(sorted(files), 1):
    img = Image.open(os.path.join(SRC, filename))
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    img = img.resize(TARGET, Image.NEAREST)
    img.save(os.path.join(DST, filename), "PNG")
    print(f"[{i}/{len(files)}] {filename}")

print(f"\nDone. {len(files)} images written to {DST}/")
