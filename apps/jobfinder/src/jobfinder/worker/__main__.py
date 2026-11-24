"""Worker entry point: `python -m jobfinder.worker`. The run loop arrives with #22 and #27."""

import sys

from jobfinder import __version__


def main() -> int:
    print(f"jobfinder worker {__version__}: no runs to execute yet")
    return 0


if __name__ == "__main__":
    sys.exit(main())
