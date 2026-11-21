"""Passe 2a : une image par tranche avec Z-Image-Turbo (t2i puis chaîne img2img)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch

from .common import Log, run_config, load_config, deep_merge
from .windows import make_prompt


def load_pipes(cfg):
    from diffusers import ZImageImg2ImgPipeline, ZImagePipeline

    t2i = ZImagePipeline.from_pretrained(cfg["image"]["model"], torch_dtype=torch.bfloat16).to("cuda")
    i2i = ZImageImg2ImgPipeline(**t2i.components)  # composants partagés : un seul chargement
    t2i.set_progress_bar_config(disable=True)
    i2i.set_progress_bar_config(disable=True)
    return t2i, i2i


def interp_prompt(a: dict, b: dict, frac: float, style: str) -> str:
    wa = dict(a["words"]); wb = dict(b["words"])
    mix = {w: (1 - frac) * wa.get(w, 0) + frac * wb.get(w, 0) for w in set(wa) | set(wb)}
    words = [w for w, _ in sorted(mix.items(), key=lambda x: -x[1])[:12]]
    return words


@torch.no_grad()
def render(run_dir: Path, cfg: dict | None = None, only_t2i: bool = False, limit: int | None = None,
           frames_dir: str = "frames"):
    run_dir = Path(run_dir)
    cfg = cfg or run_config(run_dir)
    log = Log(run_dir, "render")
    ic = cfg["image"]
    wins = json.loads((run_dir / "windows.json").read_text(encoding="utf-8"))
    for w in wins:
        w["prompt"] = make_prompt([x for x, _ in w["words"]], cfg)
    if limit:
        wins = wins[:limit]
    frames = run_dir / frames_dir
    frames.mkdir(exist_ok=True)
    t2i, i2i = load_pipes(cfg)
    W, H = ic["size"]
    seed = ic.get("seed", 1)
    reset = ic.get("reset_every", 0) or 0
    n_mid = ic.get("intermediates", 0) or 0
    prev = None
    manifest = []
    for k, w in enumerate(wins):
        gen = torch.Generator("cuda").manual_seed(seed + k)
        if prev is not None and n_mid:
            for m in range(1, n_mid + 1):
                frac = m / (n_mid + 1)
                p = make_prompt(interp_prompt(wins[k - 1], w, frac, ic["style"]), cfg)
                img = i2i(prompt=p, image=prev, strength=min(0.35, ic["strength"]), height=H, width=W,
                          num_inference_steps=ic["steps"], guidance_scale=0.0, generator=gen).images[0]
                name = f"{k:04d}_{m:02d}.png"
                img.save(frames / name)
                manifest.append({"window": k, "file": name, "intermediate": True})
                prev = img
        if prev is None or only_t2i or (reset and k % reset == 0):
            img = t2i(prompt=w["prompt"], height=H, width=W, num_inference_steps=ic["steps"],
                      guidance_scale=0.0, generator=gen).images[0]
        else:
            img = i2i(prompt=w["prompt"], image=prev, strength=ic["strength"], height=H, width=W,
                      num_inference_steps=ic["steps"], guidance_scale=0.0, generator=gen).images[0]
        img.save(frames / f"{k:04d}.png")
        manifest.append({"window": k, "file": f"{k:04d}.png", "intermediate": False})
        prev = img
        if k % 10 == 0:
            log(f"image {k}/{len(wins)} : {w['prompt'][:90]}")
    (run_dir / ("frames.json" if frames_dir == "frames" else frames_dir + ".json")).write_text(json.dumps(manifest, indent=1))
    log(f"{len(wins)} images")
    log.done()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--only-t2i", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--frames-dir", default="frames")
    ap.add_argument("--override", help="YAML fusionné dans la config du run (essais)")
    a = ap.parse_args(argv)
    cfg = run_config(Path(a.run))
    if a.override:
        import yaml
        cfg = deep_merge(cfg, yaml.safe_load(open(a.override)))
    render(Path(a.run), cfg, only_t2i=a.only_t2i, limit=a.limit, frames_dir=a.frames_dir)


if __name__ == "__main__":
    main()
