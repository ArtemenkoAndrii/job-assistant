#!/usr/bin/env python3
"""Fails while any ADR is still Proposed.

ADR-0001: the status becomes Accepted (or Rejected) in the same PR, before merge. With the
required `ci` check on main (ADR-0003), a PR with a Proposed ADR cannot be merged until the
owner accepts it and the status is updated. Found twice (#59): ADR-0003 and ADR-0007.
"""
import pathlib
import re
import subprocess
import sys

STATUS = re.compile(r"^\|\s*\*\*Status\*\*\s*\|\s*([A-Za-z]+)", re.M)


def main():
    root = pathlib.Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip())
    proposed = []
    for path in sorted((root / "docs" / "adr").glob("[0-9][0-9][0-9][0-9]-*.md")):
        match = STATUS.search(path.read_text(encoding="utf-8"))
        if match and match.group(1) == "Proposed":
            proposed.append(path.relative_to(root))
    for path in proposed:
        print(f"{path}: status is Proposed — accept (or reject) it before merge (ADR-0001)")
    return 1 if proposed else 0


if __name__ == "__main__":
    sys.exit(main())
