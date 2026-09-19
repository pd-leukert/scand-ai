"""Delete a person from the statements file, in place: the operation, and the command that
runs it from a terminal.

uv run python -m src.app.delete "Kwame Boateng" [--dry-run]

`delete_from_file` is the whole operation — read, redact, write — and is what both this command
and POST /delete call, so there is one path that changes the record and not two (D46).

Lives in the backend, not in extraction, because extraction is a job that has exited by the time
anyone asks for a deletion (D46). Reads and writes STATEMENTS_FILE_PATH, the file extraction
writes. No backup is kept: a copy of the file from before the deletion would be a second place
the person survives (CLAUDE.md rule 4). The receipt names the person, so it goes to the terminal
and is stored nowhere.
"""

import argparse
import json
import sys
import threading
from pathlib import Path

from .config import statements_file_path
from .deletion import delete_person
from .statements import write_statements

# Read, redact and write are one step as far as anyone else is concerned. Two deletions
# arriving at once would otherwise each redact the file they read and the second write would
# put the first person back. FastAPI runs a sync endpoint in a threadpool, so one process-wide
# lock is enough, and a deletion is a rare, deliberate act — nothing waits on this in practice.
_lock = threading.Lock()


def delete_from_file(path: Path, request: str, dry_run: bool = False) -> dict:
    """Redact one person out of the statements file and return the receipt.

    Nothing is written when the request matches nobody (`receipt["deleted"] is None`) or on a
    dry run. The write is whole-or-nothing (statements.write_statements), so the answering
    path, which re-reads the file on every request (D44), never sees half of a deletion.
    """
    with _lock:
        documents = json.loads(path.read_text(encoding="utf-8"))["documents"]
        redacted, receipt = delete_person(documents, request)
        if receipt["deleted"] is not None and not dry_run:
            write_statements(str(path), redacted)
    return receipt


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Delete a person from the statements file.")
    parser.add_argument("name", help='who to delete, e.g. "Kwame Boateng"')
    parser.add_argument(
        "--dry-run", action="store_true", help="print the receipt and change nothing"
    )
    args = parser.parse_args(argv)

    # The receipt holds names outside ASCII, and a Windows console is not UTF-8 by default.
    sys.stdout.reconfigure(encoding="utf-8")
    path = Path(statements_file_path())
    if not path.exists():
        print(f"No statements file at {path}.", file=sys.stderr)
        return 2

    receipt = delete_from_file(path, args.name, dry_run=args.dry_run)
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
    print(f"Rewrote {path}.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
