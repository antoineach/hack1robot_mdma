"""Crée un nouveau run à partir de la trace d'un run existant (sans relancer le LLM),
avec une autre configuration de tranches / durée cible / rendu.

./run.sh py rewindow --from runs/p1-nodrug --run-id p1-nodrug-60s [--config c.yaml] [--target 60]"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import yaml

from .common import ROOT, deep_merge, load_config, new_run_dir, run_config
from . import windows


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="src", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--config", help="config dont on reprend tout sauf model/lens/input/generation/readout/drugs")
    ap.add_argument("--target", type=float, help="video.target_duration_s (0 = désactivé)")
    a = ap.parse_args(argv)
    src = Path(a.src)
    cfg = run_config(src)
    if a.config:
        over = load_config(a.config)
        for k in ("model", "lens", "input", "generation", "readout", "drugs"):
            over.pop(k, None)  # la trace a été produite avec ces réglages : on les garde
        cfg = deep_merge(cfg, over)
    if a.target is not None:
        cfg["video"]["target_duration_s"] = a.target or None
    cfg["rewindow_from"] = str(src)
    cfg["_resolved"] = True  # la trace existe déjà : pas de recalcul du nombre de tokens
    d = new_run_dir(cfg, a.run_id)
    for f in ("trace.jsonl", "text.txt"):
        shutil.copyfile(src / f, d / f)
    windows.build(d, cfg)
    print(d)


if __name__ == "__main__":
    main()
