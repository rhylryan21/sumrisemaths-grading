#!/usr/bin/env python
import os
import sys
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def find_up(name: str, start: Path) -> Path | None:
    p = start.resolve()
    while True:
        cand = p / name
        if cand.exists():
            return cand
        if p.parent == p:
            return None
        p = p.parent


def main():
    here = Path(__file__).resolve()
    # Start from script dir; search upwards for alembic.ini
    ini = find_up("alembic.ini", here.parent)
    if not ini:
        print("Error: could not find alembic.ini by walking up from", here)
        sys.exit(1)

    cfg = Config(str(ini))
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    if len(heads) != 1:
        print(f"Error: expected 1 Alembic head, found {len(heads)}: {heads}")
        sys.exit(1)
    print(f"Alembic head OK: {heads[0]}")


if __name__ == "__main__":
    main()
