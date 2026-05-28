#!/usr/bin/env python
"""
ingest.py — add new sightings to the kas-turtles catalog.

Usage:
    python bin/ingest.py <folder-of-photos>

Walks the folder, prompts per-photo for date / location / observer / notes / individual_id,
copies each photo to data/photos/ with a stable name, and appends a row to
data/sightings.csv.

This script never edits the source folder. The catalog of record is
data/sightings.csv + data/photos/.
"""

import argparse
import csv
import hashlib
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ExifTags

# HEIC support if pillow-heif is installed (iPhone photos default to HEIC)
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
PHOTOS_DIR = DATA_DIR / "photos"
SIGHTINGS_CSV = DATA_DIR / "sightings.csv"

CSV_HEADER = [
    "id", "date", "location", "photo_path", "observer", "notes",
    "individual_id", "added_at",
]
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".tif", ".tiff", ".webp"}


def ensure_csv_exists() -> None:
    if not SIGHTINGS_CSV.exists():
        SIGHTINGS_CSV.parent.mkdir(parents=True, exist_ok=True)
        with SIGHTINGS_CSV.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(CSV_HEADER)


def read_sightings() -> list[dict]:
    if not SIGHTINGS_CSV.exists():
        return []
    with SIGHTINGS_CSV.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def next_id(rows: list[dict]) -> int:
    if not rows:
        return 1
    return max(int(r["id"]) for r in rows if r.get("id", "").isdigit()) + 1


def file_hash(path: Path) -> str:
    """SHA-1 short hash for dedupe."""
    h = hashlib.sha1()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:12]


def existing_hashes_from_photos() -> set[str]:
    """Hash every file already in data/photos/ so we can skip duplicates on re-ingest."""
    seen: set[str] = set()
    if PHOTOS_DIR.exists():
        for p in PHOTOS_DIR.iterdir():
            if p.is_file() and p.suffix.lower() in IMAGE_EXTS:
                try:
                    seen.add(file_hash(p))
                except Exception:
                    pass
    return seen


def exif_date(path: Path) -> str | None:
    """Try EXIF DateTimeOriginal, then DateTime, then file mtime. Returns YYYY-MM-DD or None."""
    try:
        img = Image.open(path)
        exif = img.getexif() or {}
        # Root-level DateTime / DateTimeOriginal
        for tag_id, value in dict(exif).items():
            tag = ExifTags.TAGS.get(tag_id)
            if tag in ("DateTimeOriginal", "DateTime") and isinstance(value, str):
                return value.split(" ")[0].replace(":", "-")
        # EXIF sub-IFD
        try:
            sub = exif.get_ifd(0x8769)  # Exif IFD
            for tag_id, value in dict(sub).items():
                tag = ExifTags.TAGS.get(tag_id)
                if tag == "DateTimeOriginal" and isinstance(value, str):
                    return value.split(" ")[0].replace(":", "-")
        except Exception:
            pass
    except Exception:
        pass
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d")
    except Exception:
        return None


def prompt(label: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    val = input(f"  {label}{suffix}: ").strip()
    return val or (default or "")


def ingest_folder(folder: Path) -> None:
    if not folder.exists() or not folder.is_dir():
        print(f"ERROR: folder not found: {folder}", file=sys.stderr)
        sys.exit(1)

    PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
    ensure_csv_exists()

    rows = read_sightings()
    next_sighting_id = next_id(rows)
    seen_hashes = existing_hashes_from_photos()

    candidates = sorted(
        p for p in folder.rglob("*")
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS
    )

    if not candidates:
        print(f"No image files found under {folder}.")
        return

    print(f"\nFound {len(candidates)} image file(s) under {folder}.")
    print("For each, you'll be prompted for sighting metadata. Press Enter to accept a default.")
    print("Type 's' to skip a photo, 'q' to quit and save progress.\n")

    last = {"location": "", "observer": "", "individual_id": ""}
    new_rows: list[dict] = []

    for i, src in enumerate(candidates, 1):
        h = file_hash(src)
        if h in seen_hashes:
            print(f"[{i}/{len(candidates)}] SKIP (already in catalog by content hash): {src.name}")
            continue

        default_date = exif_date(src)
        print(f"\n[{i}/{len(candidates)}] {src.name}")
        action = input("  proceed? [Y/s/q]: ").strip().lower()
        if action == "q":
            break
        if action == "s":
            continue

        date = prompt("date (YYYY-MM-DD)", default=default_date)
        location = prompt("location", default=last["location"] or None)
        observer = prompt("observer", default=last["observer"] or None)
        notes = prompt("notes (optional)")
        individual_id = prompt("individual_id (blank if unknown)")

        dest_name = f"{next_sighting_id:04d}_{h}{src.suffix.lower()}"
        dest = PHOTOS_DIR / dest_name
        shutil.copy2(src, dest)

        row = {
            "id": next_sighting_id,
            "date": date,
            "location": location,
            "photo_path": dest_name,
            "observer": observer,
            "notes": notes,
            "individual_id": individual_id,
            "added_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        new_rows.append(row)
        last.update(location=location, observer=observer, individual_id=individual_id)
        seen_hashes.add(h)
        next_sighting_id += 1
        print(f"  -> saved id={row['id']} as {dest_name}")

    if new_rows:
        with SIGHTINGS_CSV.open("a", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=CSV_HEADER).writerows(new_rows)
        print(f"\nIngested {len(new_rows)} new sighting(s).")
        print("Next: python bin/embed.py")
    else:
        print("\nNo new sightings added.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("folder", type=Path, help="folder of photos to ingest")
    args = ap.parse_args()
    ingest_folder(args.folder)


if __name__ == "__main__":
    main()
