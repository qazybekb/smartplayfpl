#!/usr/bin/env python3
"""Fetch smartplay_data.csv from Hugging Face.

The dataset is hosted at huggingface.co/datasets/Qazybek/smartplay-fpl-dataset
rather than tracked in git. A 92 MB file in git LFS would exhaust the
repository's monthly LFS bandwidth in roughly ten clones and grow storage by
another copy on every refresh; Hugging Face is built for this and costs
nothing, for us or for you.

    python data/download.py
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO = "Qazybek/smartplay-fpl-dataset"
TARGET = Path(__file__).resolve().parent / "smartplay_data.csv"


def main() -> int:
    if TARGET.exists():
        print(f"Already present: {TARGET} ({TARGET.stat().st_size / 1e6:.0f} MB)")
        return 0
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        print("pip install huggingface_hub", file=sys.stderr)
        return 1

    print(f"Downloading smartplay_data.csv from {REPO} …")
    cached = hf_hub_download(REPO, "smartplay_data.csv", repo_type="dataset")
    shutil.copy(cached, TARGET)
    print(f"Wrote {TARGET} ({TARGET.stat().st_size / 1e6:.0f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
