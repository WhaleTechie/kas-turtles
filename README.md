# kas-turtles

Sea-turtle photo-identification and citizen-science research in Kaş, Türkiye.

## What this is

A local-first individual-identification pipeline for Mediterranean sea turtles (mostly loggerheads, *Caretta caretta*). You collect photos, the system embeds them with a pretrained animal re-identification model ([MegaDescriptor](https://huggingface.co/BVRA/MegaDescriptor-L-384)), and proposes top-k similar individuals when you submit a new photo.

This is research infrastructure for a personal catalog at Kaş — and a scaffolding for future citizen-science contributions.

## Current status: Phase 1a — CLI baseline

Three command-line scripts:

- `bin/ingest.py <folder>` — interactive: walks a folder of photos, prompts per-photo for date / location / notes, copies to `data/photos/`, appends to `data/sightings.csv`.
- `bin/embed.py` — embeds any new sightings using MegaDescriptor, updates `data/embeddings.parquet`. Idempotent.
- `bin/match.py <photo>` — given a new photo, prints top-k most similar known sightings with similarity scores. Does not mutate the catalog.

## Honest caveats

- **This is visual similarity, framed for individual re-ID.** MegaDescriptor is trained on multi-species animal re-identification including sea turtles, and works much better than CLIP for "is this the same individual" — but it is not infallible. The published baseline on [SeaTurtleID2022](https://arxiv.org/abs/2311.05524) reaches ~86% with a proper crop pipeline ([Adam et al. 2024](https://www.biorxiv.org/content/10.1101/2024.09.13.612839v1.full)). Treat top-k results as candidates for *your* eye to confirm — not autonomous identification.
- **Photos must be head-side shots showing the post-ocular scute (cheek) pattern.** That pattern is what's unique per individual. Above-water aerial / whole-body shots will not work well.
- **Phase 1a expects you to crop manually** to the head region before submission. Phase 1b adds SAM-assisted cropping.
- **Storage is local files only.** No cloud, no database, no auth. `data/photos/` is gitignored; `data/sightings.csv` and `data/embeddings.parquet` are committed (the catalog and metadata are the value; raw photos can be backed up elsewhere).

## Setup (one-time)

From PowerShell in this folder:

```powershell
.\setup.ps1
```

Creates a Python `.venv`, installs dependencies. First model download is ~1GB and runs the first time you invoke `bin/embed.py` or `bin/match.py`.

Then in any new terminal session, activate the venv first:

```powershell
.\.venv\Scripts\Activate.ps1
```

## Use

```powershell
# 1. Ingest a folder of new sighting photos (interactive)
python bin/ingest.py "C:\Users\L450 User\Pictures\Kas-2026-06"

# 2. Embed any sightings not yet in the catalog
python bin/embed.py

# 3. Match a new photo against the catalog
python bin/match.py "C:\Users\L450 User\Pictures\unknown.jpg"
```

## Data layout

```
data/
├── sightings.csv         # one row per sighting (date, location, photo, individual_id, notes)
├── embeddings.parquet    # 1024-dim MegaDescriptor embeddings, keyed to sighting id
├── photos/               # local images, gitignored
└── .gitkeep
```

`sightings.csv` columns:

| column | description |
|---|---|
| `id` | stable sighting id (auto-incremented) |
| `date` | sighting date (YYYY-MM-DD) |
| `location` | free text, e.g. `Kaputaş`, `Limanağzı`, `Büyükçakıl` |
| `photo_path` | filename inside `data/photos/` |
| `observer` | who logged it |
| `notes` | free text |
| `individual_id` | turtle ID once confirmed (e.g. `T-001`); blank until matched / new individual decided |
| `added_at` | ingestion timestamp (ISO) |

## Roadmap

- **Phase 1b** — SAM-assisted head crop (click on the turtle's head, get a cropped patch). Better than asking the user to crop manually.
- **Phase 2** — Local Gradio web UI (drag-drop photo → see top-k matches). Pushable to Hugging Face Space later if you want public access.
- **Phase 3** — Fine-tune on Kaş data + [SeaTurtleID2022](https://arxiv.org/abs/2311.05524) using ArcFace loss; replicate the 86% baseline.
- **Maybe** — adopt the browser-based WebGPU local-first architecture from [Placitelli et al. 2025](https://www.sciencedirect.com/science/article/pii/S1574954125005783) for the eventual public UI.

## Related work

- **[ARCHELON](https://www.archelon.gr/)** — Greek Mediterranean turtle NGO based at Laganas Bay, Zakynthos. Decades of loggerhead photo-ID. Worth knowing about as a comparison catalog and a network.
- **[WildBook / Internet of Turtles](https://www.wildbook.org/)** — the open citizen-science platform that uses HotSpotter keypoint matching for turtles.
- **[MegaDescriptor](https://huggingface.co/BVRA/MegaDescriptor-L-384)** — the embedding model this project uses.

## License

MIT.
