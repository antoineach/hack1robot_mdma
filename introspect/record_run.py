"""Passe 1 sur un dossier de run déjà créé (config.yaml présente) — utilisé par `all`."""
from __future__ import annotations

import argparse
from pathlib import Path

from .common import run_config
from .record import record


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    a = ap.parse_args(argv)
    d = Path(a.run)
    record(run_config(d), d)


if __name__ == "__main__":
    main()
