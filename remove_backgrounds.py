"""Remove solid-color backgrounds from item images, replacing with transparency."""

from PIL import Image
import os
from collections import deque

ITEMS_DIR = "images/items"
TOLERANCE = 20  # color distance threshold for flood fill


def color_distance(c1, c2):
    return max(abs(c1[0] - c2[0]), abs(c1[1] - c2[1]), abs(c1[2] - c2[2]))


def flood_fill_transparent(img, start_x, start_y, target_color, tolerance):
    pixels = img.load()
    width, height = img.size
    visited = set()
    queue = deque([(start_x, start_y)])

    while queue:
        x, y = queue.popleft()
        if (x, y) in visited:
            continue
        if x < 0 or x >= width or y < 0 or y >= height:
            continue
        pixel = pixels[x, y]
        if color_distance(pixel[:3], target_color[:3]) > tolerance:
            continue
        visited.add((x, y))
        pixels[x, y] = (0, 0, 0, 0)
        queue.extend([(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)])


def remove_background(path):
    img = Image.open(path).convert("RGBA")
    w, h = img.size

    # Sample background color from top-left corner
    bg_color = img.getpixel((0, 0))

    # Flood fill from all 4 corners
    for sx, sy in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]:
        flood_fill_transparent(img, sx, sy, bg_color, TOLERANCE)

    img.save(path)


files = sorted(os.listdir(ITEMS_DIR))
total = len(files)
for i, fname in enumerate(files, 1):
    if not fname.lower().endswith(".png"):
        continue
    path = os.path.join(ITEMS_DIR, fname)
    remove_background(path)
    if i % 50 == 0 or i == total:
        print(f"  {i}/{total} done")

print("Complete.")
