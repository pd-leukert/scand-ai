"""Entry point: one loop over source files, per file doing
parse (deterministic) -> annotate (LLM) -> merge -> write JSON.

Usage:
    python -m pipeline.run --dry-run
    python -m pipeline.run --files input/transcripts/05_*.txt input/emails/01_*.txt
    python -m pipeline.run --files input/transcripts/05_*.txt --model Qwen/Qwen3.8-27B

With no --files, runs over the full corpus (transcripts + emails; reports/ is not
implemented yet, see parse_file() below).

This is a run-once job: if --out-dir already has extracted documents in it, main() prints
why and returns without touching the model. Pass --force to re-run anyway.

Env vars: EXTRACTION_LLM_BASE_URL, EXTRACTION_LLM_MODEL, EXTRACTION_LLM_API_KEY — the
names docker compose passes (see ../README.md and ../../docs/decisions.md D23).
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

# statement_extraction/pipeline/run.py -> statement_extraction/pipeline -> statement_extraction -> repo root.
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CORPUS_DIR = REPO_ROOT / "input"


def default_corpus_files() -> list[Path]:
    """Every transcript and email in the corpus, sorted for a stable run order.

    Excludes reports/ — parse_file() below has no parser for it yet.
    """
    return sorted((CORPUS_DIR / "transcripts").glob("*.txt")) + sorted(
        (CORPUS_DIR / "emails").glob("*.txt")
    )


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
    ap.add_argument("--model", default=os.environ.get("EXTRACTION_LLM_MODEL", "Qwen/Qwen3.8-27B"))
    ap.add_argument("--base-url", default=os.environ.get("EXTRACTION_LLM_BASE_URL"))
    ap.add_argument("--dry-run", action="store_true", help="skip the LLM call")
    ap.add_argument(
        "--force",
        action="store_true",
        help="re-run even if --out-dir already has extracted documents in it",
    )
    args = ap.parse_args()

    files = args.files or default_corpus_files()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    already_extracted = [
        p for p in args.out_dir.glob("*.json") if p.name != "_topic_vocabulary.json"
    ]
    if already_extracted and not args.force:
        print(
            f"{len(already_extracted)} document(s) already extracted in {args.out_dir} — "
            "this job runs once per corpus, skipping. Pass --force to re-run."
        )
        return

    vocabulary = load_vocabulary(args.out_dir)

    client = None
    if not args.dry_run:
        from openai import OpenAI
        from .llm_annotate import annotate_document

        # Ollama's OpenAI-compatible endpoint ignores the key but the SDK requires one to
        # be set; EXTRACTION_LLM_API_KEY lets a real key override it if that ever changes.
        client = OpenAI(
            base_url=args.base_url,
            api_key=os.environ.get("EXTRACTION_LLM_API_KEY", "ollama"),
        )

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
