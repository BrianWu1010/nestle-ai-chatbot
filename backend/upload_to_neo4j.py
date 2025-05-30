#!/usr/bin/env python3
"""
Upload slices with embeddings into Neo4j graph database.

Reads from 'slices_with_embed.jsonl(.gz)' and creates:
  (Category)<-[:IN_CATEGORY]-(Page)-[:HAS_SLICE]->(Slice)
    -[:HAS_IMAGE]->(Image)
Each Image node includes 'url' and 'title' properties.
"""

import gzip
import itertools
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase


# ────────────────────────────── Configuration ──────────────────────────────
SLICE_FILE = Path("data/slices_with_embed.jsonl.gz")
BATCH_SIZE_NEO4J = 500

# Load environment variables
load_dotenv()
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
if not all([NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD]):
    raise RuntimeError(
        "Please set NEO4J_URI, NEO4J_USER, and NEO4J_PASSWORD in .env"
    )

# Initialize Neo4j driver
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


# ──────────────────────────── Cypher Query Template ──────────────────────────
CYPHER_QUERY = """
UNWIND $batch AS s
// Category & Page
MERGE (cat:Category {name: s.category})
MERGE (p:Page {url: s.url})
  ON CREATE SET p.title = s.title
MERGE (p)-[:IN_CATEGORY]->(cat)

// Slice
MERGE (sl:Slice {id: s.id})
  ON CREATE SET sl.content = s.content, sl.embedding = s.embedding
MERGE (p)-[:HAS_SLICE]->(sl)

// Images
WITH sl, s
FOREACH (idx IN range(0, size(s.images) - 1) |
  MERGE (img:Image {url: s.images[idx]})
    ON CREATE SET img.title = s.image_titles[idx]
    ON MATCH  SET img.title = coalesce(img.title, s.image_titles[idx])
  MERGE (sl)-[:HAS_IMAGE]->(img)
)
"""


def read_slices(path: Path):
    """Yield JSON objects from a .jsonl or .jsonl.gz file."""
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, mode="rt", encoding="utf-8") as fh:
        for line in fh:
            yield json.loads(line)


def batches(iterable, size: int):
    """Yield successive chunks of given size from iterable."""
    it = iter(iterable)
    while True:
        chunk = list(itertools.islice(it, size))
        if not chunk:
            break
        yield chunk


def upload() -> None:
    """Main function to upload slices into Neo4j in batches."""
    # Ensure uniqueness constraints
    with driver.session() as session:
        session.run(
            """
            CREATE CONSTRAINT IF NOT EXISTS FOR (s:Slice) REQUIRE s.id IS UNIQUE
            """
        )
        session.run(
            """
            CREATE CONSTRAINT IF NOT EXISTS FOR (p:Page) REQUIRE p.url IS UNIQUE
            """
        )
        session.run(
            """
            CREATE CONSTRAINT IF NOT EXISTS FOR (c:Category) REQUIRE c.name IS UNIQUE
            """
        )
        session.run(
            """
            CREATE CONSTRAINT IF NOT EXISTS FOR (i:Image) REQUIRE i.url IS UNIQUE
            """
        )

        total = 0
        for chunk in batches(read_slices(SLICE_FILE), BATCH_SIZE_NEO4J):
            payload = [
                {
                    "id": d["id"],
                    "url": d["url"],
                    "title": d.get("website_title", d["title"]),
                    "category": d.get("category", "Uncategorized"),
                    "content": d["content"],
                    "embedding": d["embedding"],
                    "images": d.get("images", []),
                    "image_titles": d.get("image_titles", []),
                }
                for d in chunk
            ]
            session.run(CYPHER_QUERY, batch=payload)
            total += len(payload)
            print(f"Uploaded {total} slices…")

    driver.close()
    print("All data synced to Neo4j.")


if __name__ == "__main__":
    upload()
