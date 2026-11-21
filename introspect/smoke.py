"""Essais unitaires des briques : image, voix (+ effets), clip Stable Audio."""
from __future__ import annotations

import sys
import time

import numpy as np
import torch

from .common import ROOT

OUT = ROOT / "runs" / "setup" / "smoke"


def t(msg, t0):
    print(f"{msg} : {time.time() - t0:.1f} s", flush=True)


def image():
    from diffusers import ZImageImg2ImgPipeline, ZImagePipeline

    t0 = time.time()
    pipe = ZImagePipeline.from_pretrained("Tongyi-MAI/Z-Image-Turbo", torch_dtype=torch.bfloat16).to("cuda")
    t("chargement Z-Image", t0)
    prompt = "silence, voice, whisper, language, echo, music, emptiness, peinture onirique, lumière diffuse"
    t0 = time.time()
    img = pipe(prompt=prompt, height=768, width=1344, num_inference_steps=8, guidance_scale=0.0,
               generator=torch.Generator("cuda").manual_seed(1)).images[0]
    t("text-to-image 1344x768, 8 étapes", t0)
    img.save(OUT / "image_t2i.png")
    i2i = ZImageImg2ImgPipeline(**pipe.components)
    t0 = time.time()
    img2 = i2i(prompt="ocean, waves, depth, salt, " + prompt, image=img, strength=0.55, height=768, width=1344,
               num_inference_steps=8, guidance_scale=0.0, generator=torch.Generator("cuda").manual_seed(1)).images[0]
    t("img2img strength 0.55", t0)
    img2.save(OUT / "image_i2i.png")
    print("VRAM max", round(torch.cuda.max_memory_allocated() / 2**30, 1), "Gio")


def voice():
    import soundfile as sf
    from kokoro import KPipeline
    from pedalboard import Chorus, Delay, Pedalboard, PitchShift, Reverb

    t0 = time.time()
    fr = KPipeline(lang_code="f", repo_id="hexgrad/Kokoro-82M")
    t("chargement Kokoro fr", t0)
    t0 = time.time()
    chunks = [a for _, _, a in fr("silence … mémoire … océan", voice="ff_siwis", speed=0.9)]
    wav = np.concatenate([c.numpy() if hasattr(c, "numpy") else c for c in chunks]).astype(np.float32)
    t("synthèse", t0)
    sf.write(OUT / "voice_raw.wav", wav, 24000)
    board = Pedalboard([PitchShift(semitones=-3), Chorus(), Delay(delay_seconds=0.3, feedback=0.4, mix=0.3),
                        Reverb(room_size=0.9, wet_level=0.5)])
    fx = board(wav[None, :], 24000)[0]
    sf.write(OUT / "voice_fx.wav", fx, 24000)
    print("durée", round(len(wav) / 24000, 2), "s")


def audio():
    import soundfile as sf
    from diffusers import StableAudioPipeline

    t0 = time.time()
    pipe = StableAudioPipeline.from_pretrained("stabilityai/stable-audio-open-1.0", torch_dtype=torch.float16).to("cuda")
    t("chargement Stable Audio", t0)
    t0 = time.time()
    a = pipe("silence, echo, whisper, ambient texture, drone, field recording", negative_prompt="low quality",
             num_inference_steps=100, audio_end_in_s=10.0, generator=torch.Generator("cuda").manual_seed(1)).audios
    t("clip 10 s, 100 étapes", t0)
    sf.write(OUT / "sono_clip.wav", a[0].T.float().cpu().numpy(), pipe.vae.sampling_rate)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    which = sys.argv[1:] or ["image", "voice", "audio"]
    for w in which:
        print(f"=== {w}", flush=True)
        globals()[w]()
        torch.cuda.empty_cache()


if __name__ == "__main__":
    main()
