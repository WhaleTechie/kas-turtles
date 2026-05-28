#!/usr/bin/env python
"""
match.py — given a new photo, find the top-k most similar sightings in the catalog.

Usage:
    python bin/match.py <photo-path> [--k 5]

Embeds the query photo with MegaDescriptor, computes cosine similarity against
data/embeddings.parquet, prints top-k with sighting metadata. Does NOT mutate
the catalog — confirmation of matches is your call.
"""

import argparse
import csv
import sys
from pathlib import Path

import numpy as np

# Reuse loader/preprocess from embed.py
sys.path.insert(0, str(Path(__file__).resolve().parent))
from embed import (  # noqa: E402
    SIGHTINGS_CSV, PHOTOS_DIR,
    load_model, preprocess_image, embed_one, load_existing_embeddings,
)


def load_sighting_index() -> dict[int, dict]:
    with SIGHTINGS_CSV.open("r", newline="", encoding="utf-8") as f:
        return {int(r["id"]): r for r in csv.DictReader(f)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("photo", type=Path, help="path to a new photo to match")
    ap.add_argument("--k", type=int, default=5, help="top-k matches to return (default 5)")
    args = ap.parse_args()

    if not args.photo.exists():
        print(f"ERROR: photo not found: {args.photo}", file=sys.stderr)
        sys.exit(1)

    embeddings_df = load_existing_embeddings()
    if not len(embeddings_df):
        print("No embeddings in catalog yet. Run bin/ingest.py and bin/embed.py first.")
        return

    sightings = load_sighting_index()

    model = load_model()
    print(f"Embedding query: {args.photo.name}")
    tensor = preprocess_image(args.photo)
    query_vec = embed_one(model, tensor)

    catalog = np.stack(embeddings_df["embedding"].to_numpy())
    catalog_ids = embeddings_df["id"].astype(int).to_numpy()

    # cosine = dot product since both are L2-normalized
    sims = catalog @ query_vec
    order = np.argsort(-sims)
    top = order[: args.k]

    print(f"\nTop {len(top)} match(es) by cosine similarity:\n")
    print(f"  {'rank':<5} {'sighting':<10} {'score':<8} {'individual':<14} {'date':<12} location / notes")
    print(f"  {'-'*5} {'-'*10} {'-'*8} {'-'*14} {'-'*12} {'-'*40}")
    for rank, idx in enumerate(top, 1):
        sid = int(catalog_ids[idx])
        score = float(sims[idx])
        s = sightings.get(sid, {})
        individual = s.get("individual_id") or "(unconfirmed)"
        date = s.get("date") or "?"
        location = s.get("location") or "?"
        notes = s.get("notes") or ""
        tail = location + (f"  --  {notes[:60]}" if notes else "")
        print(f"  {rank:<5} {sid:<10} {score:<8.4f} {individual:<14} {date:<12} {tail}")

    print()
    print(f"Reference photos in: {PHOTOS_DIR}")
    print("To confirm a match: edit data/sightings.csv and set individual_id on the matched row,")
    print("then re-run bin/embed.py is NOT needed (embeddings don't depend on individual_id).")


if __name__ == "__main__":
    main()
