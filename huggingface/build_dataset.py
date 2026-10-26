#!/usr/bin/env python3
"""Assemble the Hugging Face dataset folder (default: dist/hf-dataset).

Standard library only. Uploading is a separate, manual step.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = {
    "README.md": ROOT / "huggingface" / "dataset-card.md",
    "LICENSE-DATA": ROOT / "LICENSE-DATA",
    "data/dev/questions.jsonl": ROOT / "data" / "dev" / "questions.jsonl",
    "rubric.md": ROOT / "rubric.md",
    "CITATION.cff": ROOT / "CITATION.cff",
    "data/split-manifest.json": ROOT / "data/split-manifest.json",
}


def build(out_dir: Path) -> list[Path]:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    written = []
    for relative, source in FILES.items():
        target = out_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        written.append(target)
    return written


def main() -> int:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "dist" / "hf-dataset"
    for path in build(out_dir):
        print(path.relative_to(out_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
