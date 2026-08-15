"""
Command line for the seeder.

    python -m scripts.seed                        # fill the checkout's own database
    python -m scripts.seed --reset --yes          # start from an empty one
    python -m scripts.seed --profile smoke        # fixtures only, no filler
    python -m scripts.seed --data-dir .\\scratch   # somewhere other than data\\

Application modules are imported inside `main`, after `--data-dir` has
been put into the environment. Imported at the top of the file they would
resolve the database path first, and the flag would silently do nothing.
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import asdict
from pathlib import Path
from random import Random

_DEFAULT_SEED = 20260811


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.seed",
        description="Fill the database with test data.",
    )
    parser.add_argument(
        "--profile",
        choices=("demo", "smoke", "load"),
        default="demo",
        help="demo: fixtures plus six months of trading. smoke: fixtures only. load: large dataset. (default: demo)",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        help="Where the database lives. Defaults to this checkout's data folder.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete the database first. Everything in it is lost.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Do not ask before deleting the database.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=_DEFAULT_SEED,
        help=f"Randomness seed — the same one gives the same data. (default: {_DEFAULT_SEED})",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)

    if arguments.data_dir is not None:
        os.environ["ERP_DATA_DIR"] = str(arguments.data_dir.expanduser().resolve())

    from app.config.paths import DATABASE_PATH
    from app.config.settings import load_development_env

    load_development_env()
    print(f"Database: {DATABASE_PATH}")

    if arguments.reset and not _delete_database(DATABASE_PATH, confirmed=arguments.yes):
        return 1

    from app.container import AppContainer
    from app.infrastructure.db import init_db
    from app.infrastructure.db.database import engine

    from scripts.seed.dataset import Profile, build
    from scripts.seed.seeder import Seeder

    init_db()

    if _documents_in(engine):
        print(
            "This database already has documents in it. Seeding on top would "
            "collide with their numbers. Run again with --reset to start over.",
            file=sys.stderr,
        )
        return 1

    dataset = build(Profile(arguments.profile), Random(arguments.seed))
    report = Seeder(AppContainer(), dataset).run()

    print(f"Seeded ({arguments.profile}):")
    for name, count in asdict(report).items():
        print(f"  {name.replace('_', ' '):<12} {count:>6}")
    return 0


def _delete_database(path: Path, *, confirmed: bool) -> bool:
    if not path.exists():
        return True

    if not confirmed:
        answer = input(f"Delete {path} and everything in it? [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            print("Left alone.")
            return False

    # SQLite's journal files, if the database was not closed cleanly.
    for companion in (path, path.with_suffix(path.suffix + "-wal"), path.with_suffix(path.suffix + "-shm")):
        companion.unlink(missing_ok=True)
    return True


def _documents_in(engine) -> bool:
    """Whether anything has been traded in this database already."""
    from sqlalchemy import text

    with engine.connect() as connection:
        for table in ("sales", "purchases"):
            if connection.execute(text(f"SELECT 1 FROM {table} LIMIT 1")).first() is not None:
                return True
    return False


if __name__ == "__main__":
    raise SystemExit(main())
