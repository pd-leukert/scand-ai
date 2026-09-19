"""Delete a person from the statements file, in place, and print the receipt.

uv run python -m src.app.delete "Kwame Boateng" [--dry-run]

Reads and writes STATEMENTS_FILE_PATH, the same file extraction writes. No backup is kept: a
copy of the file from before the deletion would be a second place the person survives (CLAUDE.md
rule 4). The receipt names the person, so it goes to the terminal and is stored nowhere.
"""

import argparse
import json
import os
import sys
from pathlib import Path

from .deletion import delete_person
from .extract import _write_json


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Delete a person from the statements file.")
    parser.add_argument("name", help='who to delete, e.g. "Kwame Boateng"')
    parser.add_argument(
        "--dry-run", action="store_true", help="print the receipt and change nothing"
    )
    args = parser.parse_args(argv)

    # The receipt holds names outside ASCII, and a Windows console is not UTF-8 by default.
    sys.stdout.reconfigure(encoding="utf-8")
    path = Path(os.environ.get("STATEMENTS_FILE_PATH", "statements.json"))
    if not path.exists():
        print(f"No statements file at {path}.", file=sys.stderr)
        return 2

    documents = json.loads(path.read_text(encoding="utf-8"))["documents"]
    redacted, receipt = delete_person(documents, args.name)
    print(json.dumps(receipt, indent=2, ensure_ascii=False))

    if receipt["deleted"] is None:
        print(
            f'Nobody called "{args.name}" is in the statements, so nothing was changed. '
            "They may already be deleted.",
            file=sys.stderr,
        )
        return 1

    # An interrupted extraction run leaves per-document copies next to the file. They are not
    # what this command rewrites, so say so rather than let the receipt look complete.
    leftover = path.parent / "documents"
    if leftover.exists():
        print(
            f"{leftover} exists (an interrupted extraction run) and still holds the name.",
            file=sys.stderr,
        )
    if args.dry_run:
        print(f"Dry run: {path} was not changed.", file=sys.stderr)
        return 0
    _write_json(path, redacted)
    print(f"Rewrote {path}.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
