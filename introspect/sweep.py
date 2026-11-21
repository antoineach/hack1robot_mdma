"""Balayage de l'intensité de drogue : charge Gemma une fois, enregistre un run par α.

./run.sh py sweep --config configs/variants/drug_subtle.yaml --alphas 0.05 0.1 0.2 0.4 --prefix sweep"""
from __future__ import annotations

import argparse
import copy
import json

from .common import load_config, new_run_dir
from .lensmodel import load_lens, load_model
from .record import record


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--alphas", type=float, nargs="+", required=True)
    ap.add_argument("--prefix", default="sweep")
    a = ap.parse_args(argv)
    base = load_config(a.config)
    model, tok = load_model(base)
    lens = load_lens(base)
    summary = {}
    for alpha in a.alphas:
        cfg = copy.deepcopy(base)
        for d in cfg.get("drugs") or []:
            d["alpha"] = alpha
        if (cfg.get("drug") or {}).get("name"):  # drogue du catalogue : la valeur est l'intensité globale
            cfg["drug"]["intensity"] = alpha
        rid = f"{a.prefix}-a{alpha:g}"
        d = new_run_dir(cfg, rid)
        record(cfg, d, model=model, tok=tok, lens=lens)
        text = (d / "text.txt").read_text(encoding="utf-8")
        words = [w for x in json.loads((d / "windows.json").read_text()) for w, _ in x["words"]]
        summary[rid] = {"alpha": alpha, "ocean_in_text": text.lower().count("ocean") + text.lower().count("océan"),
                        "text_tail": text[-200:]}
        print(rid, summary[rid], flush=True)
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
