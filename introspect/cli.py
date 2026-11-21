"""CLI : record | render | voice | sound | assemble | all.

`all` lance chaque passe dans son propre processus pour libérer la VRAM entre
le LLM et le modèle de diffusion (jamais les deux en même temps sur le GPU)."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from .common import ROOT, load_config, new_run_dir


def sub(module: str, *args: str):
    cmd = [sys.executable, "-m", f"introspect.{module}", *args]
    print(">>", " ".join(cmd), flush=True)
    r = subprocess.run(cmd, cwd=ROOT)
    if r.returncode != 0:
        raise SystemExit(f"échec de l'étape {module} (code {r.returncode})")


def gpu_lock():
    """Verrou fichier : une seule chaîne `all` à la fois sur le GPU (CLI et interface web)."""
    import fcntl

    f = open(ROOT / "runs" / ".gpu.lock", "w")
    print(">> attente du GPU…", flush=True)
    fcntl.flock(f, fcntl.LOCK_EX)
    print(">> GPU obtenu", flush=True)
    return f


def run_all(config: str, run_id: str | None, modes: list[str] | None, skip_record: bool = False):
    _lock = gpu_lock()  # libéré à la fin du processus
    cfg = load_config(config)
    cp = Path(config).resolve()
    if run_id is None and cp.parent.parent == (ROOT / "runs").resolve():  # runs/<id>/request.yaml
        run_id = cp.parent.name
    d = new_run_dir(cfg, run_id)
    run = str(d)
    if not skip_record or not (d / "windows.json").exists():
        sub("record_run", "--run", run)
    sub("render", "--run", run)
    sub("voice", "--run", run)
    snd = cfg["sound"]
    need_sound = snd["voice_fx"].get("enabled") or snd["mode"] != "voix" or any(m != "voix" for m in (modes or []))
    if need_sound:
        sound_mode = "mixte" if (modes and len(set(modes)) > 1) else (modes[0] if modes else snd["mode"])
        sub("sound", "--run", run, "--mode", sound_mode)
    for m in modes or [snd["mode"]]:
        sub("assemble", "--run", run, "--mode", m)
    print(d)
    return d


def main(argv=None):
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    a_all = sp.add_parser("all")
    a_all.add_argument("--config", required=True)
    a_all.add_argument("--run-id")
    a_all.add_argument("--modes", nargs="*", choices=["voix", "sonorisation", "mixte"])
    a_all.add_argument("--skip-record", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "all":
        run_all(a.config, a.run_id, a.modes, a.skip_record)


if __name__ == "__main__":
    main()
