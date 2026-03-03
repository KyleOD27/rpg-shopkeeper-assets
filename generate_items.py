#!/usr/bin/env python3
"""Batch-generate pixel art RPG item icons using PixelLab MCP over HTTP.

Usage:
    python generate_items.py                  # Run full batch
    python generate_items.py --dry-run        # Preview descriptions only
    python generate_items.py --limit 10       # Generate only first 10 items
    python generate_items.py --verify         # Verify all output files
"""

import argparse
import asyncio
import base64
import json
import os
import re
import sys
import time
from pathlib import Path

try:
    import aiohttp
except ImportError:
    print("ERROR: aiohttp is required. Install with: pip install aiohttp")
    sys.exit(1)

# --- Configuration ---
MCP_ENDPOINT = "https://api.pixellab.ai/mcp"
API_TOKEN = os.environ.get(
    "PIXELLAB_API_KEY", "8e30727e-3261-4c22-ace4-d0a9028239dc"
)
ITEMS_DIR = Path(__file__).parent / "images" / "items_interim"
STATE_FILE = Path(__file__).parent / "generate_items_state.json"
PLACEHOLDER_MAX_BYTES = 600
WAVE_SIZE = 3  # Items to submit per wave (PixelLab limits concurrent jobs)
POLL_INTERVAL = 15  # seconds between polls
MAX_RETRIES = 3
POLL_TIMEOUT = 300  # 5 minutes max poll per item
RATE_LIMIT_WAIT = 30  # seconds to wait on rate limit

# Generation parameters
GEN_PARAMS = {
    "width": 64,
    "height": 64,
    "view": "side",
    "outline": "single color outline",
    "shading": "medium shading",
    "detail": "medium detail",
}

# --- Filename to description conversion ---

APOSTROPHE_WORDS = {
    "alchemists": "alchemist's",
    "brewers": "brewer's",
    "burglars": "burglar's",
    "calligraphers": "calligrapher's",
    "carpenters": "carpenter's",
    "cobblers": "cobbler's",
    "cooks": "cook's",
    "disguisers": "disguiser's",
    "dungeonneers": "dungeoneer's",
    "dungeoneers": "dungeoneer's",
    "explorers": "explorer's",
    "glassblowers": "glassblower's",
    "herbalists": "herbalist's",
    "jewelers": "jeweler's",
    "leatherworkers": "leatherworker's",
    "masons": "mason's",
    "painters": "painter's",
    "potters": "potter's",
    "priests": "priest's",
    "scholars": "scholar's",
    "smiths": "smith's",
    "tinkers": "tinker's",
    "weavers": "weaver's",
    "woodcarvers": "woodcarver's",
}

COMPOUND_WORDS = {
    "clothofgold": "cloth-of-gold",
    "silverplated": "silver-plated",
    "twoperson": "two-person",
    "wellmade": "well-made",
    "halfplate": "half plate",
}

# Items that commonly have _1, _2, _3 variants (strip the suffix)
VARIANT_BASES = {
    "battleaxe", "breastplate", "chain_mail", "chain_shirt", "club",
    "crossbow_hand", "crossbow_heavy", "crossbow_light", "dagger",
    "dart", "flail", "glaive", "greataxe", "greatclub", "greatsword",
    "halberd", "half_plate_armor", "handaxe", "hide_armor", "javelin",
    "lance", "leather_armor", "light_hammer", "longbow", "longsword",
    "mace", "maul", "morningstar", "net", "padded_armor", "pike",
    "plate_armor", "quarterstaff", "rapier", "ring_mail", "scale_mail",
    "scimitar", "shield", "shortbow", "shortsword", "sickle",
    "sling", "spear", "splint_armor", "studded_leather_armor",
    "trident", "war_pick", "warhammer", "whip",
    "rod_of_the_pact_keeper", "staff_of_the_magi",
    "staff_of_the_woodlands", "wand_of_the_war_mage",
    "enspelled_staff", "enspelled_weapon",
}


def filename_to_description(filename: str) -> str:
    """Convert a filename stem to a natural-language item description."""
    stem = Path(filename).stem

    # Remove parenthetical suffixes like " (2)"
    stem = re.sub(r"\s*\(\d+\)$", "", stem)

    # Strip variant suffix (_1, _2, _3) if the base is a known item type
    variant_match = re.match(r"^(.+)_(\d)$", stem)
    if variant_match:
        base, num = variant_match.groups()
        if base in VARIANT_BASES:
            stem = base  # Strip the variant number

    # Replace underscores with spaces
    name = stem.replace("_", " ")

    # Handle Npound patterns -> N-pound
    name = re.sub(r"(\d)pound", r"\1-pound", name)

    # Handle compound words
    for compound, replacement in COMPOUND_WORDS.items():
        name = name.replace(compound, replacement)

    # Handle apostrophes for possessive words
    words = name.split()
    words = [APOSTROPHE_WORDS.get(w, w) for w in words]
    name = " ".join(words)

    return f"RPG item icon: {name}"


# --- MCP Client ---


class PixelLabMCP:
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self._request_id = 0

    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        self._request_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_TOKEN}",
        }
        async with self.session.post(
            MCP_ENDPOINT, json=payload, headers=headers
        ) as resp:
            raw = await resp.text()
            # Parse SSE response: "event: message\ndata: {json}\n\n"
            data_line = None
            for line in raw.split("\n"):
                if line.startswith("data: "):
                    data_line = line[6:]
                    break
            if not data_line:
                raise Exception(f"No data in SSE response: {raw[:200]}")
            result = json.loads(data_line)
            if "error" in result:
                raise Exception(f"MCP error: {result['error']}")
            return result.get("result", {})

    async def create_map_object(self, description: str) -> str:
        """Create a map object and return the object_id."""
        result = await self.call_tool(
            "create_map_object", {"description": description, **GEN_PARAMS}
        )
        # Parse object_id from text content
        text = ""
        for content in result.get("content", []):
            if content.get("type") == "text":
                text = content["text"]
                break
        match = re.search(r"`([0-9a-f-]{36})`", text)
        if not match:
            raise Exception(f"Could not parse object_id from: {text[:200]}")
        return match.group(1)

    async def get_map_object(self, object_id: str) -> dict:
        """Poll a map object. Returns {status, image_data, download_url}."""
        result = await self.call_tool(
            "get_map_object", {"object_id": object_id}
        )
        text = ""
        image_data = None
        for content in result.get("content", []):
            if content.get("type") == "text":
                text = content["text"]
            elif content.get("type") == "image":
                image_data = content.get("data")

        if image_data:
            return {"status": "completed", "image_data": image_data}
        elif "still being generated" in text:
            pct_match = re.search(r"(\d+)%", text)
            pct = int(pct_match.group(1)) if pct_match else 0
            return {"status": "processing", "progress": pct}
        elif "Insufficient" in text or result.get("isError"):
            return {"status": "error", "message": text[:200]}
        else:
            return {"status": "unknown", "message": text[:200]}


# --- State management ---


def load_state() -> dict:
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"items": {}, "stats": {"completed": 0, "failed": 0}}


def save_state(state: dict):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


# --- Discovery ---


def discover_pending_files() -> list[str]:
    """Find placeholder PNGs (under threshold size)."""
    pending = []
    for f in sorted(ITEMS_DIR.iterdir()):
        if f.suffix == ".png" and f.stat().st_size < PLACEHOLDER_MAX_BYTES:
            pending.append(f.name)
    return pending


# --- Batch processor (wave-based) ---


async def submit_one(
    mcp: PixelLabMCP, filename: str, description: str, state: dict
) -> str | None:
    """Submit a single create_map_object. Returns object_id or None on failure."""
    item_state = state["items"].setdefault(
        filename, {"status": "pending", "retries": 0}
    )
    try:
        object_id = await mcp.create_map_object(description)
        item_state["object_id"] = object_id
        item_state["status"] = "submitted"
        item_state["description"] = description
        save_state(state)
        return object_id
    except Exception as e:
        err_str = str(e)
        if "Rate limit" in err_str or "concurrent" in err_str.lower():
            return "RATE_LIMITED"
        item_state["retries"] = item_state.get("retries", 0) + 1
        item_state["status"] = "failed"
        item_state["error"] = err_str
        save_state(state)
        return None


async def poll_and_download(
    mcp: PixelLabMCP, filename: str, object_id: str, state: dict
) -> bool:
    """Poll until complete and download. Returns True on success."""
    item_state = state["items"][filename]
    start_time = time.time()
    while time.time() - start_time < POLL_TIMEOUT:
        await asyncio.sleep(POLL_INTERVAL)
        try:
            result = await mcp.get_map_object(object_id)
        except Exception as e:
            print(f"    Poll error for {filename}: {e}")
            continue

        if result["status"] == "completed":
            image_bytes = base64.b64decode(result["image_data"])
            output_path = ITEMS_DIR / filename
            with open(output_path, "wb") as f:
                f.write(image_bytes)
            file_size = output_path.stat().st_size
            item_state["status"] = "completed"
            item_state["file_size"] = file_size
            save_state(state)
            return True
        elif result["status"] == "error":
            item_state["status"] = "failed"
            item_state["error"] = result.get("message", "Unknown error")
            save_state(state)
            return False

    item_state["status"] = "failed"
    item_state["error"] = f"Polling timeout after {POLL_TIMEOUT}s"
    save_state(state)
    return False


async def run_batch(filenames: list[str], dry_run: bool = False):
    """Process items in waves to respect API rate limits."""
    state = load_state()

    # Filter out already completed items
    pending = []
    for fn in filenames:
        item = state["items"].get(fn, {})
        if item.get("status") == "completed":
            output = ITEMS_DIR / fn
            if output.exists() and output.stat().st_size >= PLACEHOLDER_MAX_BYTES:
                continue  # Already done
        pending.append(fn)

    # Build descriptions
    descriptions = {fn: filename_to_description(fn) for fn in pending}

    if dry_run:
        print(f"\n=== DRY RUN: {len(pending)} items to generate ===\n")
        for fn in pending:
            print(f"  {fn:50s} -> {descriptions[fn]}")
        print(f"\n=== {len(filenames) - len(pending)} already completed ===")
        return

    already_done = len(filenames) - len(pending)
    print(f"\n=== Starting batch: {len(pending)} items ({already_done} already done) ===\n")

    completed = 0
    failed = 0

    async with aiohttp.ClientSession() as session:
        mcp = PixelLabMCP(session)

        # Process in waves
        i = 0
        while i < len(pending):
            wave = pending[i : i + WAVE_SIZE]
            wave_num = (i // WAVE_SIZE) + 1
            total_waves = (len(pending) + WAVE_SIZE - 1) // WAVE_SIZE
            print(
                f"  Wave {wave_num}/{total_waves} "
                f"({completed}/{len(pending)} done so far)"
            )

            # Submit wave
            submitted = {}  # {filename: object_id}
            rate_limited_fns = []
            for fn in wave:
                result = await submit_one(mcp, fn, descriptions[fn], state)
                if result == "RATE_LIMITED":
                    print(
                        f"    Rate limited at {fn}, "
                        f"waiting {RATE_LIMIT_WAIT}s..."
                    )
                    rate_limited_fns.append(fn)
                    await asyncio.sleep(RATE_LIMIT_WAIT)
                    # Retry this one
                    result = await submit_one(mcp, fn, descriptions[fn], state)
                    if result and result != "RATE_LIMITED":
                        submitted[fn] = result
                        print(f"    Submitted: {fn}")
                    else:
                        print(f"    FAILED (rate limit): {fn}")
                        failed += 1
                elif result:
                    submitted[fn] = result
                    print(f"    Submitted: {fn}")
                else:
                    print(f"    FAILED to submit: {fn}")
                    failed += 1

            # Poll all submitted items in this wave concurrently
            if submitted:
                poll_tasks = [
                    poll_and_download(mcp, fn, oid, state)
                    for fn, oid in submitted.items()
                ]
                results = await asyncio.gather(*poll_tasks)
                for fn, success in zip(submitted.keys(), results):
                    if success:
                        completed += 1
                        size = state["items"][fn].get("file_size", "?")
                        print(f"    Completed: {fn} ({size}b)")
                    else:
                        failed += 1
                        print(f"    FAILED: {fn}")

            i += WAVE_SIZE

    print(
        f"\n=== Batch complete: "
        f"{completed} succeeded, {failed} failed, "
        f"{already_done} were already done ==="
    )


def verify_outputs(filenames: list[str]):
    """Verify all output files exist and are valid."""
    good = missing = too_small = 0
    failures = []

    for fn in filenames:
        path = ITEMS_DIR / fn
        if not path.exists():
            missing += 1
            failures.append(f"  MISSING: {fn}")
        elif path.stat().st_size < PLACEHOLDER_MAX_BYTES:
            too_small += 1
            failures.append(
                f"  TOO SMALL: {fn} ({path.stat().st_size}b)"
            )
        else:
            good += 1

    print(f"\n=== Verification: {len(filenames)} items ===")
    print(f"  Good:      {good}")
    print(f"  Missing:   {missing}")
    print(f"  Too small: {too_small}")
    if failures:
        print(f"\nFailures:")
        for f in failures[:50]:
            print(f)
        if len(failures) > 50:
            print(f"  ... and {len(failures) - 50} more")


def main():
    parser = argparse.ArgumentParser(
        description="Batch-generate pixel art RPG item icons"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview descriptions only"
    )
    parser.add_argument(
        "--limit", type=int, default=0, help="Limit number of items to process"
    )
    parser.add_argument(
        "--verify", action="store_true", help="Verify all output files"
    )
    args = parser.parse_args()

    filenames = discover_pending_files()
    print(f"Found {len(filenames)} placeholder items in {ITEMS_DIR}")

    if args.verify:
        verify_outputs(filenames)
        return

    if args.limit > 0:
        filenames = filenames[: args.limit]
        print(f"Limited to {args.limit} items")

    if args.dry_run:
        asyncio.run(run_batch(filenames, dry_run=True))
    else:
        asyncio.run(run_batch(filenames))


if __name__ == "__main__":
    main()
