"""Passe 2d : montage. Images en fondu enchaîné + piste audio calée, MP4 H.264 1080p."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf
from PIL import Image
from scipy.signal import resample_poly

from .common import Log, run_config

SR = 44100
TRANSITIONS = ("dissolve", "zoom", "prism")


def ffmpeg_bin() -> str:
    b = shutil.which("ffmpeg")
    if b:
        return b
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def load_audio(path: Path, sr_out: int = SR) -> np.ndarray:
    """Charge un wav en stéréo float32 [n, 2] à 44,1 kHz."""
    x, sr = sf.read(path, dtype="float32", always_2d=True)
    if x.shape[1] == 1:
        x = np.repeat(x, 2, axis=1)
    x = x[:, :2]
    if sr != sr_out:
        from math import gcd

        g = gcd(sr, sr_out)
        x = resample_poly(x, sr_out // g, sr // g, axis=0).astype(np.float32)
    return x


def fit(img: Image.Image, W: int, H: int) -> np.ndarray:
    s = max(W / img.width, H / img.height)
    im = img.resize((round(img.width * s), round(img.height * s)), Image.LANCZOS)
    l, t = (im.width - W) // 2, (im.height - H) // 2
    return np.asarray(im.crop((l, t, l + W, t + H)).convert("RGB"))


def transition_frame(left: np.ndarray, right: np.ndarray, progress: float, style: str) -> bytes:
    if style == "dissolve":
        frame = left * (1 - progress) + right * progress
        return np.clip(frame, 0, 255).astype(np.uint8).tobytes()

    # Le zoom culmine à la coupe et retombe sans saut sur l'image fixe.
    alpha = progress * progress * (3 - 2 * progress)
    pulse = 4 * alpha * (1 - alpha)
    frame = (left * (1 - alpha) + right * alpha).astype(np.uint8)
    height, width = frame.shape[:2]
    zoom = 1 + 0.16 * pulse
    dx, dy = width * (1 - 1 / zoom) / 2, height * (1 - 1 / zoom) / 2
    image = Image.fromarray(frame).resize(
        (width, height), Image.BICUBIC, box=(dx, dy, width - dx, height - dy)
    )
    if style == "prism":
        shift = round(width * 0.012 * pulse)
        if shift:
            frame = np.asarray(image).copy()
            columns = np.arange(width)
            frame[:, :, 0] = frame[:, np.clip(columns - shift, 0, width - 1), 0]
            frame[:, :, 2] = frame[:, np.clip(columns + shift, 0, width - 1), 2]
            return frame.tobytes()
    return image.tobytes()


def durations(run_dir: Path, cfg: dict, n: int) -> list[float]:
    vmin = cfg["video"]["min_duration_s"]
    vj = run_dir / "voice_fx.json"
    if not (cfg["sound"]["voice_fx"].get("enabled", True) and vj.exists()):
        vj = run_dir / "voice.json"
    vd = {m["window"]: m["duration"] for m in json.loads(vj.read_text())} if vj.exists() else {}
    return slice_durations([vd.get(k, 0.0) for k in range(n)], cfg)


def slice_durations(voice_durs: list[float], cfg: dict) -> list[float]:
    """Durée de chaque tranche : max(voix, minimum) ; si une durée cible est fixée et
    que le total est plus court, on étire uniformément pour l'atteindre."""
    vmin = cfg["video"]["min_duration_s"]
    d = [max(vmin, x) for x in voice_durs]
    T = cfg["video"].get("target_duration_s")
    if T and d and sum(d) < T:
        extra = (T - sum(d)) / len(d)
        d = [x + extra for x in d]
    return d


def place(track: np.ndarray, clip: np.ndarray, start: int, gain: float = 1.0):
    end = min(len(track), start + len(clip))
    if end > start:
        track[start:end] += clip[: end - start] * gain


def voice_track_single(run_dir, cfg, durs, total):
    tr = np.zeros((total, 2), np.float32)
    use_fx = cfg["sound"]["voice_fx"].get("enabled", True)
    t = 0
    for k, d in enumerate(durs):
        p = run_dir / "audio" / f"voice_fx_{k:04d}.wav"
        if not (use_fx and p.exists()):
            p = run_dir / "audio" / f"{k:04d}.wav"
        if p.exists():
            place(tr, load_audio(p), t)
        t += int(d * SR)
    return tr


def multi_voice_layout(run_dir, cfg, durs) -> tuple[list, int]:
    """Voix en parallèle : (liste (fichier, départ en échantillons, pan), fin de la dernière voix)."""
    from .voice import VOICES

    meta = json.loads((run_dir / "voice.json").read_text(encoding="utf-8"))
    n = int(cfg["voice"].get("n_voices", 1))
    use_fx = cfg["sound"]["voice_fx"].get("enabled", True)
    busy = [0] * n  # fin du fragment précédent de chaque voix
    starts = np.cumsum([0] + [int(d * SR) for d in durs])
    items, end = [], 0
    for k, m in enumerate(meta):
        for v, vv in enumerate(m.get("voices", [])):
            if not vv["words"]:
                continue
            p = run_dir / "audio" / f"v{v}" / (f"fx_{k:04d}.wav" if use_fx else f"{k:04d}.wav")
            if use_fx and not p.exists():
                p = run_dir / "audio" / f"v{v}" / f"{k:04d}.wav"
            if not p.exists():
                continue
            t0 = max(int(starts[k] + v * durs[k] / n * SR), busy[v])  # décalage, jamais sur soi-même
            L = sf.info(p).frames * SR // sf.info(p).samplerate
            busy[v] = t0 + L
            end = max(end, t0 + L)
            items.append((p, t0, None if use_fx else VOICES[v][2]))
    return items, end


def voice_track(run_dir, cfg, durs, total):
    if int(cfg["voice"].get("n_voices", 1)) > 1:
        tr = np.zeros((total, 2), np.float32)
        items, _ = multi_voice_layout(run_dir, cfg, durs)
        n = int(cfg["voice"]["n_voices"])
        for p, t0, pan in items:
            x = load_audio(p)
            if pan is not None:  # voix brute : panoramique de base de la voix
                x = x * np.array([np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)], np.float32) * 1.41
            place(tr, x / np.sqrt(n / 2) if n > 2 else x, t0)
        return tr
    return voice_track_single(run_dir, cfg, durs, total)


def sono_track(run_dir, cfg, durs, total):
    tr = np.zeros((total, 2), np.float32)
    c = int(cfg["video"]["crossfade_s"] * SR)
    t = 0
    for k, d in enumerate(durs):
        p = run_dir / "audio" / f"sono_{k:04d}.wav"
        if p.exists():
            x = load_audio(p)
            n = int(d * SR) + c
            x = x[:n]
            env = np.ones(len(x), np.float32)
            r = min(c, len(x) // 2)
            if r > 0:
                env[:r] = np.linspace(0, 1, r)
                env[-r:] = np.linspace(1, 0, r)
            place(tr, x * env[:, None], max(0, t - c // 2))
        t += int(d * SR)
    return tr


def duck(sono: np.ndarray, voice: np.ndarray, db: float) -> np.ndarray:
    env = np.abs(voice).max(axis=1)
    win = int(0.15 * SR)
    env = np.convolve(env, np.ones(win) / win, mode="same")
    active = np.clip(env / (env.max() + 1e-9) * 8, 0, 1)
    gain = 1 - active * (1 - 10 ** (db / 20))
    return sono * gain[:, None]


def build_audio(run_dir: Path, cfg: dict, mode: str, durs: list[float]) -> np.ndarray:
    total = int(sum(durs) * SR) + int(cfg["video"]["crossfade_s"] * SR)
    if int(cfg["voice"].get("n_voices", 1)) > 1 and mode != "sonorisation":
        _, end = multi_voice_layout(run_dir, cfg, durs)
        total = max(total, end + SR)  # dernière image jusqu'à la fin de la dernière voix + 1 s
    if mode == "voix":
        mix = voice_track(run_dir, cfg, durs, total)
    elif mode == "sonorisation":
        mix = sono_track(run_dir, cfg, durs, total)
    else:
        v = voice_track(run_dir, cfg, durs, total)
        s = sono_track(run_dir, cfg, durs, total)
        s = s / (np.abs(s).max() + 1e-9) * 0.5
        mix = v + duck(s, v, cfg["sound"].get("duck_db", -6))
    peak = np.abs(mix).max()
    if peak > 0:
        mix = mix / peak * 0.9
    return mix


def assemble(run_dir: Path, cfg: dict | None = None, mode: str | None = None, raw_voice: bool = False,
             transition: str | None = None) -> Path:
    run_dir = Path(run_dir)
    cfg = cfg or run_config(run_dir)
    mode = mode or cfg["sound"]["mode"]
    vc = cfg["video"]
    style = transition if transition is not None else vc.get("transition", "dissolve")
    if style not in TRANSITIONS:
        raise ValueError(f"Transition inconnue : {style!r} (choix : {', '.join(TRANSITIONS)})")
    suffix = f"_{style}" if transition is not None else ""
    if raw_voice:
        cfg["sound"]["voice_fx"]["enabled"] = False
        suffix = "_brute" + suffix
    log = Log(run_dir, f"assemble_{mode}{suffix}")
    W, H, fps, c = vc.get("width", 1920), vc.get("height", 1080), vc["fps"], vc["crossfade_s"]
    wins = json.loads((run_dir / "windows.json").read_text())
    n = len(wins)
    durs = durations(run_dir, cfg, n)
    audio = build_audio(run_dir, cfg, mode, durs)
    wav_path = run_dir / f"audio_{mode}{suffix}.wav"
    sf.write(wav_path, audio, SR)

    # liste d'images : (fichier, durée), intermédiaires répartis dans la tranche
    fj = run_dir / "frames.json"
    manifest = json.loads(fj.read_text()) if fj.exists() else [{"window": k, "file": f"{k:04d}.png", "intermediate": False} for k in range(n)]
    shots = []
    for k in range(n):
        subs = sorted((m for m in manifest if m["window"] == k and not m["intermediate"] and "sub" in m),
                      key=lambda m: m["sub"])
        if len(subs) > 1:  # plusieurs images par tranche (render --per-slice) : réparties à parts égales
            shots += [(m["file"], durs[k] / len(subs)) for m in subs]
            continue
        files = [m["file"] for m in manifest if m["window"] == k and m["intermediate"]] + [f"{k:04d}.png"]
        # les intermédiaires préparent la tranche k : ils occupent la 1re moitié de sa durée
        if len(files) > 1:
            dm = durs[k] * 0.5 / (len(files) - 1)
            shots += [(f, dm) for f in files[:-1]] + [(files[-1], durs[k] * 0.5)]
        else:
            shots.append((files[0], durs[k]))
    imgs = {}

    def get(f):
        if f not in imgs:
            imgs.clear() if len(imgs) > 4 else None
            imgs[f] = fit(Image.open(run_dir / "frames" / f), W, H).astype(np.float32)
        return imgs[f]

    starts = np.cumsum([0] + [d for _, d in shots])
    total_t = len(audio) / SR
    nframes = int(total_t * fps)
    out = run_dir / f"out_{mode}{suffix}.mp4"
    cmd = [ffmpeg_bin(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps),
           "-i", "-", "-i", str(wav_path), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-shortest", str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    if style == "dissolve":
        half_widths = [c / 2] * (len(shots) - 1)
    else:
        # Au plus une demi-image de part et d'autre, même avec plusieurs images par tranche.
        half_widths = [min(c, left[1], right[1]) / 2 for left, right in zip(shots, shots[1:])]
    static: dict[str, bytes] = {}
    for fi in range(nframes):
        t = fi / fps
        i = min(len(shots) - 1, int(np.searchsorted(starts, t, side="right") - 1))
        if i + 1 < len(shots) and t > starts[i + 1] - half_widths[i]:
            boundary = i + 1
        elif i > 0 and t < starts[i] + half_widths[i - 1]:
            boundary = i
        else:
            f = shots[i][0]
            if f not in static:
                static.clear()
                static[f] = np.clip(get(f), 0, 255).astype(np.uint8).tobytes()
            proc.stdin.write(static[f])
            continue
        half = half_widths[boundary - 1]
        progress = 0.5 + (t - starts[boundary]) / (2 * half)
        proc.stdin.write(transition_frame(get(shots[boundary - 1][0]), get(shots[boundary][0]), progress, style))
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg a échoué")
    if mode == cfg["sound"]["mode"] and not suffix:
        shutil.copyfile(out, run_dir / "out.mp4")
    log(f"{out.name} : {n} tranches, {total_t:.1f} s, {nframes} images vidéo")
    log.done()
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--mode", choices=["voix", "sonorisation", "mixte"])
    ap.add_argument("--raw-voice", action="store_true", help="voix brute, sans effets")
    ap.add_argument("--transition", choices=TRANSITIONS, help="export de comparaison avec une transition visuelle")
    a = ap.parse_args(argv)
    assemble(Path(a.run), mode=a.mode, raw_voice=a.raw_voice, transition=a.transition)


if __name__ == "__main__":
    main()
