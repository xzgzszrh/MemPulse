"""Consistent SQLite snapshot; refuse to overwrite an existing artifact."""

import argparse
import sqlite3
from pathlib import Path


def backup(source, output):
    source = Path(source)
    output = Path(output)
    if not source.is_file():
        raise FileNotFoundError(source)
    if output.exists():
        raise FileExistsError(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with (
        sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as src,
        sqlite3.connect(output) as dst,
    ):
        src.backup(dst)
    return str(output)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("source", type=lambda x: Path(x).resolve())
    p.add_argument("output", type=lambda x: Path(x).resolve())
    a = p.parse_args()
    print(backup(a.source, a.output))
