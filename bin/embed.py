#!/usr/bin/env python
"""
embed.py — compute MegaDescriptor embeddings for any new sightings.

Reads:  data/sightings.csv
Writes: data/embeddings.parquet  (one row per sighting id, with a 1024-dim L2-normalized vector)

Skips sightings already present in the parquet. Idempotent — safe to re-run.

First invocation downloads ~1GB of model weights from Hugging Face.
"""

import csv
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from PIL import Image
from tqdm import tqdm

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
PHOTOS_DIR = DATA_DIR / "photos"
SIGHTINGS_CSV = DATA_DIR / "sightings.csv"
EMBEDDINGS_PQ = DATA_DIR / "embeddings.parquet"

MODEL_NAME = "hf_hub:BVRA/MegaDescriptor-L-384"
IMAGE_SIZE = 384
NORM_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
NORM_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


def load_model():
    """Lazily import timm so the module can be imported by match.py without paying the cost twice."""
    import timm
    print(f"Loading {MODEL_NAME} (first run downloads ~1GB) ...")
    t0 = time.time()
    model = timm.create_model(MODEL_NAME, pretrained=True, num_classes=0)
    model.eval()
    print(f"  loaded in {time.time() - t0:.1f}s")
    return model


def preprocess_image(path: Path) -> torch.Tensor:
    """Resize to 384x384, ImageNet-normalize, CHW float tensor with leading batch dim."""
    img = Image.open(path).convert("RGB")
    img = img.resize((IMAGE_SIZE, IMAGE_SIZE), Image.BILINEAR)
    arr = np.asarray(img, dtype=np.float32) / 255.0
    arr = (arr - NORM_MEAN) / NORM_STD
    tensor = torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0).float()
    return tensor


def embed_one(model, tensor: torch.Tensor) -> np.ndarray:
    """Forward pass, return L2-normalized feature vector as numpy."""
    with torch.inference_mode():
        feats = model(tensor)
    if isinstance(feats, (list, tuple)):
        feats = feats[0]
    vec = feats.squeeze(0).cpu().numpy().astype(np.float32)
    norm = float(np.linalg.norm(vec))
    if norm > 0:
        vec = vec / norm
    return vec


def load_existing_embeddings() -> pd.DataFrame:
    if not EMBEDDINGS_PQ.exists():
        return pd.DataFrame(columns=["id", "embedding"])
    return pd.read_parquet(EMBEDDINGS_PQ)


def main() -> None:
    if not SIGHTINGS_CSV.exists():
        print("No data/sightings.csv yet. Run bin/ingest.py first.", file=sys.stderr)
        sys.exit(1)

    with SIGHTINGS_CSV.open("r", newline="", encoding="utf-8") as f:
        sightings = list(csv.DictReader(f))

    if not sightings:
        print("No sightings to embed.")
        return

    existing = load_existing_embeddings()
    embedded_ids: set[int] = set(existing["id"].astype(int).tolist()) if len(existing) else set()
    to_embed = [s for s in sightings if int(s["id"]) not in embedded_ids]

    if not to_embed:
        print(f"All {len(sightings)} sighting(s) already embedded.")
        return

    print(f"{len(sightings)} sighting(s) total; {len(to_embed)} new to embed.")
    model = load_model()

    new_rows: list[dict] = []
    for s in tqdm(to_embed, desc="embedding"):
        photo = PHOTOS_DIR / s["photo_path"]
        if not photo.exists():
            print(f"  WARN: missing photo for id={s['id']}: {photo}", file=sys.stderr)
            continue
        try:
            tensor = preprocess_image(photo)
            vec = embed_one(model, tensor)
            new_rows.append({"id": int(s["id"]), "embedding": vec})
        except Exception as e:
            print(f"  ERROR id={s['id']}: {e}", file=sys.stderr)

    if not new_rows:
        print("No embeddings produced.")
        return

    new_df = pd.DataFrame(new_rows)
    merged = pd.concat([existing, new_df], ignore_index=True) if len(existing) else new_df
    merged.to_parquet(EMBEDDINGS_PQ, index=False)
    print(f"Saved {len(merged)} total embedding(s) to {EMBEDDINGS_PQ.relative_to(REPO_ROOT)}.")


if __name__ == "__main__":
    main()
