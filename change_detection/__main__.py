"""Command line: ``python -m change_detection OLD_FILE NEW_FILE [--json] [--min-severity LEVEL]``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .api import detect_changes
from .models import SEVERITY_LEVELS

_COLORS = {"major": "\033[91m", "moderate": "\033[93m", "minor": "\033[96m", "none": "\033[90m"}
_RESET = "\033[0m"


def _fmt_diff(change) -> str:
    out = []
    for seg in change.inline_diff:
        if seg.op == "delete":
            out.append(f"[-{seg.text}-]")
        elif seg.op == "insert":
            out.append(f"{{+{seg.text}+}}")
        else:
            out.append(seg.text)
    return " ".join(out)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python -m change_detection", description="Compare two policy versions.")
    p.add_argument("old_file")
    p.add_argument("new_file")
    p.add_argument("--json", action="store_true", help="print the full JSON report")
    p.add_argument("--min-severity", default="none", choices=SEVERITY_LEVELS)
    p.add_argument("--no-formatting", action="store_true", help="hide cosmetic-only edits")
    p.add_argument("--document-id", default=None)
    p.add_argument("--no-color", action="store_true")
    args = p.parse_args(argv)

    old = Path(args.old_file).read_text(encoding="utf-8")
    new = Path(args.new_file).read_text(encoding="utf-8")
    report = detect_changes(
        old, new,
        document_id=args.document_id or Path(args.new_file).stem,
        include_formatting=not args.no_formatting,
        min_severity=args.min_severity,
    )

    try:
        sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252
    except (AttributeError, ValueError):  # pragma: no cover
        pass

    if args.json:
        print(report.to_json())
        return 0

    color = sys.stdout.isatty() and not args.no_color
    print(report.headline())
    print()
    for c in report.changes:
        sev = c.severity.upper()
        if color:
            sev = f"{_COLORS[c.severity]}{sev}{_RESET}"
        print(f"[{sev}] {c.change_type} {c.scope} in '{c.section_heading or c.section_id}' ({c.category})")
        if c.change_type in ("modified", "formatting"):
            print(f"    {_fmt_diff(c)}")
        else:
            if c.old_text:
                print(f"    - {c.old_text}")
            if c.new_text:
                print(f"    + {c.new_text}")
        for r in c.reasons:
            print(f"      * {r}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
