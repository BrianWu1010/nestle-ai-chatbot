#!/usr/bin/env python3
"""
Batch-slices all *_text.json files into embedding-friendly chunks.

- Preserves URL, title, and category; fills in missing fields.
- Uses sentence-based or simple splitting with overlap.
- Processes files in parallel using ThreadPoolExecutor.

Output is written to slices.jsonl.gz by default.
"""

import concurrent.futures
import gzip
import glob
import json
import logging
import os
import pathlib
import sys
import base64

from dataclasses import dataclass
from typing import List, Dict

from page import Page, SplitPage
from text_splitter import SentenceTextSplitter, SimpleTextSplitter

# ──────────────────────────────── Logging ────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s | %(asctime)s | %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger("splitter")

# ──────────────────────────────── Configuration ───────────────────────────────
HERE = pathlib.Path(__file__).parent
DATA_DIR = HERE / "scraped_data_async"
OUT_PATH = HERE / "slices.jsonl.gz"
USE_GZIP = OUT_PATH.suffix == ".gz"

MAX_TOKENS = 450
MAX_OBJECT_LEN = 1200
MAX_IMAGES = 3
NUM_WORKERS = os.cpu_count() or 4

# ───────────────────────────── Splitter Instances ─────────────────────────────
sentence_splitter = SentenceTextSplitter(max_tokens_per_section=MAX_TOKENS)
simple_splitter = SimpleTextSplitter(max_object_length=MAX_OBJECT_LEN)


def load_pages(fp: pathlib.Path) -> List[Page]:
    """Load a *_text.json file and convert to a list of Page objects."""
    try:
        doc = json.loads(fp.read_text(encoding="utf-8"))
    except Exception as error:
        log.warning(f"Failed to read {fp}: {error}")
        return []

    meta = doc.get("metadata", {})
    meta.setdefault("url", str(fp))
    meta.setdefault("title", str(fp.stem))
    meta.setdefault("category", meta.get("category", "Uncategorized"))

    blocks = doc.get("text", [])
    if isinstance(blocks, str):
        blocks = [blocks]

    pages: List[Page] = []
    offset = 0
    for idx, text in enumerate(blocks):
        pages.append(Page(page_num=idx, offset=offset, text=text, meta=meta))
        offset += len(text)
    return pages


def choose_splitter(char_count: int):
    """Choose splitter based on total character length."""
    return (
        sentence_splitter
        if char_count > MAX_OBJECT_LEN
        else simple_splitter
    )


def make_id(stem: str, index: int) -> str:
    """Generate a URL-safe base64 ID with an index suffix."""
    b64 = base64.urlsafe_b64encode(stem.encode()).decode("ascii").rstrip("=")
    return f"{b64}__{index:03}"


def slice_one(fp: pathlib.Path) -> List[Dict]:
    """Process one file: load, split pages, and build slice dicts."""
    pages = load_pages(fp)
    if not pages:
        return []

    total_chars = sum(len(p.text) for p in pages)
    splitter = choose_splitter(total_chars)

    slices: List[Dict] = []
    for idx, split in enumerate(splitter.split_pages(pages)):
        meta = pages[split.page_num].meta
        images = (meta.get("images") or [])[:MAX_IMAGES]

        slices.append({
            "id": make_id(fp.stem, idx),
            "url": meta["url"],
            "title": meta["title"],
            "category": meta["category"],
            "images": [img.get("url", "") for img in images],
            "image_titles": [img.get("alt", "") for img in images],
            "content": split.text.strip(),
        })
    return slices


def main() -> None:
    """Main entry: discover files, slice, and write output."""
    files = list(DATA_DIR.glob("**/*_text.json"))
    if not files:
        log.error(f"No *_text.json found under {DATA_DIR}")
        return

    log.info(
        f"Found {len(files)} files; slicing with {NUM_WORKERS} workers..."
    )

    all_slices: List[Dict] = []
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=NUM_WORKERS
    ) as executor:
        futures = {executor.submit(slice_one, fp): fp for fp in files}
        for future in concurrent.futures.as_completed(futures):
            fp = futures[future]
            try:
                result = future.result()
                all_slices.extend(result)
                log.debug(f"{fp.name}: {len(result)} slices")
            except Exception as error:
                log.error(f"Error slicing {fp}: {error}")

    log.info(f"Total slices: {len(all_slices)}; writing to {OUT_PATH.name}")
    opener = gzip.open if USE_GZIP else open
    with opener(OUT_PATH, "wt", encoding="utf-8") as outfile:
        for obj in all_slices:
            outfile.write(json.dumps(obj, ensure_ascii=False) + "\n")

    log.info("All done.")


if __name__ == "__main__":
    main()
