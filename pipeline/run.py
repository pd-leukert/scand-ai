"""Entry point: one loop over source files, per file doing
parse (deterministic) -> annotate (LLM) -> merge -> write JSON.

Usage:
    python -m pipeline.run --dry-run
    python -m pipeline.run --files acme/transcripts/05_*.txt acme/emails/01_*.txt
    python -m pipeline.run --files acme/transcripts/05_*.txt --model Qwen/Qwen3.8-27B

Env vars (standard OpenAI SDK): OPENAI_API_KEY, OPENAI_BASE_URL.
--dry-run skips the LLM call entirely and fills semantic fields with
defaults, so you can check the deterministic parser output on its own
before spending API calls.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from .parse_email import parse_email_thread
from .parse_transcript import parse_transcript

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SAMPLE_FILES = [
    REPO_ROOT / "acme/transcripts/05_2024-07-15_implementation-kickoff.txt",
    REPO_ROOT / "acme/emails/01_shelf-life-field-mapping.txt",
]

DEFAULT_ANNOTATION = {
    "speech_act": "other",
    "topics": [],
    "people_mentioned": [],
    "is_truncated": False,
    "supersedes_segment_id": None,
}


def parse_file(path: Path) -> dict[str, Any]:
    parent = path.parent.name
    if parent == "transcripts":
        return parse_transcript(path)
    if parent == "emails":
        return parse_email_thread(path)
    if parent == "reports":
        raise NotImplementedError(
            f"report-thread parser not implemented yet: {path}"
        )
    raise ValueError(f"cannot infer doc_type for {path} (expected transcripts/emails/reports dir)")


def merge(doc_meta: dict, segments: list[dict], annotations: dict[str, dict]) -> dict:
    merged_segments = []
    for seg in segments:
        ann = annotations.get(seg["segment_id"])
        if ann is None:
            print(f"  ! no annotation returned for {seg['segment_id']}, using defaults")
            ann = DEFAULT_ANNOTATION
        merged_segments.append({**seg, **{k: v for k, v in ann.items() if k != "segment_id"}})
    return {"doc": doc_meta, "segments": merged_segments}


def load_vocabulary(out_dir: Path) -> set[str]:
    vocab_path = out_dir / "_topic_vocabulary.json"
    if vocab_path.exists():
        return set(json.loads(vocab_path.read_text()))
    return set()


def save_vocabulary(out_dir: Path, vocab: set[str]) -> None:
    vocab_path = out_dir / "_topic_vocabulary.json"
    vocab_path.write_text(json.dumps(sorted(vocab), indent=2))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--files", nargs="+", type=Path, default=None)
    ap.add_argument("--out-dir", type=Path, default=REPO_ROOT / "pipeline_output")
    ap.add_argument("--model", default=os.environ.get("QWEN_MODEL", "Qwen/Qwen3.8-27B"))
    ap.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL"))
    ap.add_argument("--dry-run", action="store_true", help="skip the LLM call")
    args = ap.parse_args()

    files = args.files or DEFAULT_SAMPLE_FILES
    args.out_dir.mkdir(parents=True, exist_ok=True)
    vocabulary = load_vocabulary(args.out_dir)

    client = None
    if not args.dry_run:
        from openai import OpenAI
        from .llm_annotate import annotate_document

        client = OpenAI(base_url=args.base_url) if args.base_url else OpenAI()

    for path in files:
        print(f"[{path.name}]")
        parsed = parse_file(path)
        doc_meta, segments = parsed["doc"], parsed["segments"]
        print(f"  parsed {len(segments)} segments")

        if args.dry_run:
            annotations = {s["segment_id"]: DEFAULT_ANNOTATION for s in segments}
        else:
            annotations = annotate_document(client, args.model, doc_meta, segments, vocabulary)
            print(f"  annotated {len(annotations)} segments, vocabulary size {len(vocabulary)}")

        result = merge(doc_meta, segments, annotations)
        out_path = args.out_dir / f"{doc_meta['doc_id']}.json"
        out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
        print(f"  wrote {out_path}")

    save_vocabulary(args.out_dir, vocabulary)


if __name__ == "__main__":
    main()
