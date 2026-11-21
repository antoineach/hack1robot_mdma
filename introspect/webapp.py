"""Interface web v2 (Gradio) : lancer une « prise » depuis un téléphone.

./run.sh web            -> lien public *.gradio.live protégé par mot de passe
./run.sh web --local    -> http://127.0.0.1:7860 seulement

Sécurité : la question n'est jamais insérée dans une commande shell (elle va dans un
YAML écrit par Python) ; sous-processus en liste d'arguments ; listes vérifiées contre
les catalogues ; Gradio ne sert que runs/ ; file d'attente limitée à 5."""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import yaml

from .common import ROOT

RUNS = ROOT / "runs"
AUTH_FILE = Path.home() / ".config" / "hack1robo" / "web_auth"
PCLOUD = Path.home() / "pCloudDrive" / "Transfert" / "hack1robo"
MAX_Q = 300
MIN_PER_MIN = 7.0  # minutes de calcul par minute de vidéo (mesuré la nuit du 21/11)

ENVS = yaml.safe_load((ROOT / "configs" / "environments.yaml").read_text(encoding="utf-8"))
DRUGS = yaml.safe_load((ROOT / "configs" / "drugs.yaml").read_text(encoding="utf-8"))["drugs"]
ENV_CHOICES = [("aucun", "aucun")] + [(v["label"], k) for k, v in ENVS.items()]
DRUG_CHOICES = [("aucune", "aucune")] + [(v["label"], k) for k, v in DRUGS.items()]
MODES = ["mixte", "voix", "sonorisation"]
STEPS = {"record_run": "1/5 Le modèle disserte (lecture J-lens)", "render": "2/5 Images",
         "voice": "3/5 Voix", "sound": "4/5 Effets et sonorisation", "assemble": "5/5 Montage"}

_job = {"proc": None, "run": None}
_lock = threading.Lock()


# ------------------------------------------------------------------ accès
def get_auth() -> tuple[str, str]:
    if AUTH_FILE.exists():
        user, pw = AUTH_FILE.read_text().strip().split(":", 1)
        return user, pw
    AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
    user, pw = "prise", secrets.token_urlsafe(12)
    AUTH_FILE.write_text(f"{user}:{pw}\n")
    os.chmod(AUTH_FILE, 0o600)
    print(f"[web] mot de passe généré dans {AUTH_FILE}", flush=True)
    return user, pw


# ------------------------------------------------------------------ helpers
def clean_question(q: str) -> str:
    q = (q or "").replace("\r", " ").replace("\n", " ")
    q = "".join(c for c in q if c.isprintable())
    return q.strip()[:MAX_Q]


def past_questions() -> list[str]:
    qs = []
    for p in sorted(RUNS.glob("*/config.yaml"), key=os.path.getmtime, reverse=True):
        try:
            c = yaml.safe_load(p.read_text(encoding="utf-8"))
            inp = c.get("input", {})
            q = inp.get("phrase") or inp["phrases"][inp.get("phrase_index", 0)]
        except Exception:
            continue
        if q and q not in qs:
            qs.append(q)
    for q in yaml.safe_load((ROOT / "configs" / "default.yaml").read_text(encoding="utf-8"))["input"]["phrases"]:
        if q not in qs:
            qs.append(q)
    return qs[:30]


def estimate(duration: float) -> str:
    m = duration / 60 * MIN_PER_MIN
    return f"Calcul estimé : environ {m:.0f} min (≈ {MIN_PER_MIN:.0f} min par minute de vidéo). La durée réelle peut dépasser un peu."


def make_request(q, env, env_style, drug, intensity, duration, n_voices, mode) -> Path:
    q = clean_question(q)
    if not q:
        raise ValueError("La question est vide.")
    if env not in dict((v, l) for l, v in ENV_CHOICES):
        raise ValueError("Environnement inconnu.")
    if drug not in dict((v, l) for l, v in DRUG_CHOICES):
        raise ValueError("Drogue inconnue.")
    if mode not in MODES:
        raise ValueError("Mode son inconnu.")
    intensity = float(min(1.5, max(0.5, intensity)))
    duration = int(min(300, max(30, round(float(duration) / 15) * 15)))
    n_voices = int(min(4, max(1, int(n_voices))))
    rid = f"web-{dt.datetime.now():%Y%m%d-%H%M%S}-{drug}-{env}"
    d = RUNS / rid
    d.mkdir(parents=True, exist_ok=False)
    req = {
        "run_tag": "web",
        "input": {"phrase": q, "environment": env, "environment_style": bool(env_style)},
        "drug": {"name": drug, "intensity": intensity} if drug != "aucune" else {},
        "video": {"target_duration_s": duration},
        "voice": {"n_voices": n_voices},
        "sound": {"mode": mode},
    }
    (d / "request.yaml").write_text(yaml.safe_dump(req, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return d


def summary(d: Path, video: Path | None = None) -> str:
    try:
        c = yaml.safe_load((d / "config.yaml").read_text(encoding="utf-8"))
    except Exception:
        return d.name
    inp = c.get("input", {})
    q = inp.get("phrase") or (inp.get("phrases") or ["?"])[inp.get("phrase_index", 0)]
    env = ENVS.get(inp.get("environment") or "", {}).get("label", "—")
    dg = (c.get("drug") or {}).get("name")
    drug = f"{DRUGS[dg]['label']} ×{c['drug'].get('intensity', 1)}" if dg in DRUGS else \
        (", ".join(f"{x['word']} α={x['alpha']}" for x in c.get("drugs") or []) or "sans drogue")
    v = c.get("video", {}).get("target_duration_s") or "long"
    nv = c.get("voice", {}).get("n_voices", 1)
    mode = c.get("sound", {}).get("mode")
    if video is not None and video.stem.startswith("out_"):
        mode = video.stem[4:].replace("_", " ")  # ex. out_voix_brute -> « voix brute »
    return f"{q[:70]} · {env} · {drug} · {v}{' s' if v != 'long' else ''} · {nv} voix · {mode}"


def videos() -> list[tuple[str, str]]:
    out = []
    for p in sorted(RUNS.glob("*/out*.mp4"), key=os.path.getmtime, reverse=True):
        if p.name == "out.mp4" and any(p.parent.glob("out_*.mp4")):
            continue  # out.mp4 double un out_<mode>.mp4
        label = f"{dt.datetime.fromtimestamp(p.stat().st_mtime):%d/%m %H:%M} · {p.parent.name}/{p.name} · {summary(p.parent, p)}"
        out.append((label, str(p)))
    return out


def publish(video: Path):
    try:
        if PCLOUD.parent.exists():
            PCLOUD.mkdir(exist_ok=True)
            dst = PCLOUD / f"{video.parent.name}_{video.name}"
            if not dst.exists():
                shutil.copyfile(video, dst)
    except OSError as e:
        print("[web] copie pCloud impossible :", e, flush=True)


def current_step(log: Path) -> str:
    step = "En attente du GPU…"
    if log.exists():
        for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.search(r"-m introspect\.(\w+)", line)
            if line.startswith(">>") and m and m.group(1) in STEPS:
                step = STEPS[m.group(1)]
    return step


# ------------------------------------------------------------------ actions
def run_job(q, env, env_style, drug, intensity, duration, n_voices, mode):
    """Générateur : (statut, images, vidéo). Un seul rendu à la fois (file Gradio, concurrence 1)."""
    try:
        d = make_request(q, env, env_style, drug, intensity, duration, n_voices, mode)
    except ValueError as e:
        yield f"⚠️ {e}", [], None
        return
    log = d / "web.log"
    with _lock:
        with open(log, "w", encoding="utf-8") as lf:
            proc = subprocess.Popen([sys.executable, "-m", "introspect.cli", "all", "--config", str(d / "request.yaml")],
                                    cwd=ROOT, stdout=lf, stderr=subprocess.STDOUT)
        _job.update(proc=proc, run=d)
        t0 = time.time()
        while proc.poll() is None:
            frames = sorted(glob.glob(str(d / "frames" / "[0-9][0-9][0-9][0-9].png")))
            yield f"**{d.name}** — {current_step(log)} — {int(time.time() - t0)} s", frames, None
            time.sleep(4)
        _job.update(proc=None, run=None)
    frames = sorted(glob.glob(str(d / "frames" / "[0-9][0-9][0-9][0-9].png")))
    out = d / "out.mp4"
    if proc.returncode == 0 and out.exists():
        publish(out)
        yield f"✅ **{d.name}** terminé en {int(time.time() - t0)} s.", frames, str(out)
    elif proc.returncode is not None and proc.returncode < 0:
        yield f"⏹️ **{d.name}** annulé.", frames, None
    else:
        tail = log.read_text(encoding="utf-8", errors="replace").splitlines()[-3:]
        yield f"❌ **{d.name}** a échoué (code {proc.returncode}). " + " / ".join(tail)[-300:], frames, None


def cancel():
    p = _job.get("proc")
    if p is not None and p.poll() is None:
        p.terminate()
        try:
            p.wait(10)
        except subprocess.TimeoutExpired:
            p.kill()
        # les sous-étapes tournent dans des processus enfants de cli : on les arrête aussi
        subprocess.run(["pkill", "-f", "--", f"--run {_job.get('run')}"], check=False)
        return "⏹️ Annulation demandée."
    return "Aucun rendu en cours."


# ------------------------------------------------------------------ interface
def build():
    import gradio as gr

    with gr.Blocks(title="Prise") as demo:
        gr.Markdown("## Prise\nLe modèle disserte sur ta question ; on voit et on entend ce qui se passe à l'intérieur.")
        with gr.Tab("Lancer"):
            q = gr.Textbox(label="Question", max_lines=3, max_length=MAX_Q, placeholder="Une machine peut-elle rêver ?")
            past = gr.Dropdown(choices=past_questions(), label="Questions déjà utilisées", value=None, filterable=False)
            env = gr.Dropdown(choices=ENV_CHOICES, value="aucun", label="Environnement", filterable=False)
            env_style = gr.Checkbox(label="L'environnement colore aussi les images et le son", value=True)
            drug = gr.Dropdown(choices=DRUG_CHOICES, value="aucune", label="Drogue", filterable=False)
            intensity = gr.Slider(0.5, 1.5, value=1.0, step=0.05, label="Intensité globale")
            duration = gr.Slider(30, 300, value=60, step=15, label="Durée visée (s)")
            n_voices = gr.Slider(1, 4, value=1, step=1, label="Nombre de voix")
            mode = gr.Radio(MODES, value="mixte", label="Son")
            est = gr.Markdown(estimate(60))
            with gr.Row():
                go = gr.Button("Lancer", variant="primary")
                stop = gr.Button("Annuler", variant="stop")
            status = gr.Markdown()
            gallery = gr.Gallery(label="Images au fil du rendu", columns=3, height="auto")
            video = gr.Video(label="Vidéo")
            past.change(lambda x: x or gr.update(), past, q, api_name=False)
            duration.change(estimate, duration, est, api_name=False)
            ev = go.click(run_job, [q, env, env_style, drug, intensity, duration, n_voices, mode],
                          [status, gallery, video], api_name=False, concurrency_limit=1)
            stop.click(cancel, None, status, api_name=False, cancels=[ev])
        with gr.Tab("Galerie"):
            refresh = gr.Button("Rafraîchir")
            pick = gr.Dropdown(choices=videos(), label="Runs (les plus récents en haut)", filterable=False)
            gvideo = gr.Video(label="Vidéo")
            refresh.click(lambda: gr.update(choices=videos()), None, pick, api_name=False)
            pick.change(lambda p: p, pick, gvideo, api_name=False)
    demo.queue(max_size=5, default_concurrency_limit=1, api_open=False)
    return demo


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", action="store_true", help="pas de lien public")
    ap.add_argument("--port", type=int, default=7860)
    a = ap.parse_args(argv)
    demo = build()
    user, pw = get_auth()
    demo.launch(share=not a.local, auth=(user, pw), auth_message="Prise — accès réservé",
                server_name="127.0.0.1", server_port=a.port, allowed_paths=[str(RUNS)],
                footer_links=[], prevent_thread_lock=True, quiet=True)
    url = getattr(demo, "share_url", None)
    print(f"[web] local : http://127.0.0.1:{a.port}  public : {url}", flush=True)
    if url and PCLOUD.parent.exists():
        PCLOUD.mkdir(exist_ok=True)
        (PCLOUD / "lien_web.txt").write_text(f"{url}\n(démarré le {dt.datetime.now():%d/%m/%Y à %H:%M})\n")
    try:
        demo.block_thread()
    finally:
        cancel()


if __name__ == "__main__":
    main()
