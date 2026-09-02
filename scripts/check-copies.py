#!/usr/bin/env python3
"""Verify that the platform copies of every SKILL.md match the source.

`skills/<name>/SKILL.md` is the single source of truth. The `.cursor/skills/`
and `.agents/skills/` trees hold verbatim copies for hosts that only read
their own directory. This script fails when a copy drifts from its source.

Usage: python3 scripts/check-copies.py [--fix]
"""

import argparse
import filecmp
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "skills"
COPY_DIRS = [ROOT / ".cursor" / "skills", ROOT / ".agents" / "skills"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fix", action="store_true", help="Copy source over drifted copies")
    args = parser.parse_args()

    sources = sorted(SOURCE.glob("*/SKILL.md"))
    if not sources:
        print(f"ERROR: no skills found under {SOURCE}", file=sys.stderr)
        return 1

    errors: list[str] = []
    for copy_dir in COPY_DIRS:
        if not copy_dir.is_dir():
            errors.append(f"{copy_dir}: missing directory")
            continue
        names = {path.parent.name for path in sources}
        expected = {f"{name}/SKILL.md" for name in names}
        actual = {
            str(path.relative_to(copy_dir))
            for path in copy_dir.glob("*/SKILL.md")
        }
        for missing in sorted(expected - actual):
            errors.append(f"{copy_dir / missing}: missing copy")
        for extra in sorted(actual - expected):
            errors.append(f"{copy_dir / extra}: copy has no source skill")

    for source in sources:
        name = source.parent.name
        for copy_dir in COPY_DIRS:
            copy = copy_dir / name / "SKILL.md"
            if copy.is_file() and not filecmp.cmp(source, copy, shallow=False):
                if args.fix:
                    copy.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
                    print(f"fixed {copy}")
                else:
                    errors.append(f"{copy}: drifted from {source}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print("Run with --fix to overwrite drifted copies from skills/.", file=sys.stderr)
        return 1
    print(f"All platform copies in sync with skills/ ({len(sources)} skills x {len(COPY_DIRS)} dirs).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
