"""Verify an authorized release-notes artifact before publication."""

import argparse
import hashlib
import re
from pathlib import Path


def verify(path: Path, digest: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("Invalid release notes digest.")
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError("Release notes artifact does not match authorized digest.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["verify"])
    parser.add_argument("path", type=Path)
    parser.add_argument("digest")
    args = parser.parse_args()
    verify(args.path, args.digest)


if __name__ == "__main__":
    main()
