"""Render a film using timecoded Markdown cues, optional J-lens weights and drug intensity.

python scripts/rave_silence_fx.py source.mp4 description.md result.mp4
Requires FFmpeg, OpenCV and NumPy.
"""
import argparse
import json
import math
import re
import subprocess
import tempfile
import unicodedata
from collections import deque
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

import cv2 as cv
import numpy as np

@dataclass
class Shot:
    start: float
    end: float
    dose: float
    phase: str
    comedown: float
    crash: float
    effect: str
    confidence: float


# Matching runs on whole words. Phrases take precedence over latent words.
WORDS = {
    "tear": "brutal brutale chaos fracture rupture",
    "breath": "exhale expire expiration éther",
    "prism": "comunicación communication réseau prisme prism",
    "iris": "énorme gigantic géant immense immenseur expansion",
    "fossil": "seashells coquillages fossiles fossils",
    "halation": "breathe respire respiration lueur halo étincelle étincelles",
    "portal": "incroyable vertige vortex abîme tunnel",
    "echo": "clings écho echo rémanence reflet reflets",
}

def normalize(text):
    return "".join(c for c in unicodedata.normalize("NFKD", text.casefold())
                   if not unicodedata.combining(c))

def tokens(text):
    return set(re.findall(r"[^\W_]+", normalize(text)))

VOCABULARY = {effect: tokens(words) for effect, words in WORDS.items()}
TIMECODE = r"(?:\d+:)?\d+:\d{2}(?:[.,]\d+)?"
HEADING = re.compile(rf"^#{{1,6}}[^\n]*?({TIMECODE})\s*(?:→|->|–|—|-)\s*({TIMECODE}).*$", re.M)

def seconds(text):
    total = 0.
    for field in text.replace(",", ".").split(":"):
        total = 60 * total + float(field)
    return total

def choose_effect(phrase, weights):
    spoken = tokens(phrase)
    candidates = []
    for effect, family in VOCABULARY.items():
        overlap = family & spoken
        latent = max((weights.get(w, 0.) for w in family), default=0.)
        if overlap:
            candidates.append((1 + latent, effect, min(1., .8 + latent)))
        elif latent >= .18:
            candidates.append((latent, effect, min(.65, 2 * latent)))
    if candidates:
        _, effect, confidence = max(candidates)
        return effect, confidence
    return "", 0.

def score(path):
    text = path.read_text(encoding="utf-8")
    headers = list(HEADING.finditer(text))
    if not headers:
        raise ValueError("Expected Markdown headings with start and end times, e.g. ### 0:00 → 0:04")
    shots = []
    last_used = {}
    for i, heading in enumerate(headers):
        section = text[heading.end():headers[i+1].start() if i+1 < len(headers) else len(text)]
        start, end = map(seconds, heading.groups())
        if end <= start or (shots and start < shots[-1].end - .001):
            raise ValueError(f"Invalid or overlapping interval at {heading.group()}")
        plain = section.replace("**", "")
        spoken = re.search(r"^[- *]*Paroles\s*:\s*(.+)$", plain, re.M | re.I)
        phrase = spoken[1].split("»")[0] if spoken else " ".join(
            line for line in plain.splitlines() if ":" not in line)
        jlens = re.search(r"^[- *]*Mots lus[^\n:]*:\s*(.+)$", plain, re.M | re.I)
        weights = {normalize(w): float(n.replace(",", ".")) for w,n in
                   re.findall(r"([\w’-]+)\s+(\d+[.,]\d+)", jlens[1] if jlens else "")}
        dose = re.search(r"\b(?:force perçue\s+)?d\s*=\s*(\d+(?:[.,]\d+)?)", plain)
        value = float(dose[1].replace(",", ".")) if dose else .55
        phase = re.search(r"\bphase\s*(?:[:=]\s*)?(?:«([^»]+)»|([^,\n·]+))", plain, re.I)
        phase = normalize((phase[1] or phase[2]).strip()) if phase else ""
        shares = dict(re.findall(r"mdma_(\w+) (\d+)%", plain))
        effect, confidence = choose_effect(phrase, weights)
        if effect in last_used and start - last_used[effect] < 5:
            confidence *= .35
        if effect:
            last_used[effect] = end
        shots.append(Shot(start, end, min(1., value), phase, int(shares.get("comedown", 0))/100,
                          int(shares.get("crash", 0))/100, effect, confidence))
    # If the vocabulary is unfamiliar, give occasional bright accents to the strongest passages.
    if not any(s.effect for s in shots):
        next_accent = 0.
        for shot in shots:
            if shot.start >= next_accent and shot.dose >= .5 and shot.end-shot.start >= 1.5:
                shot.effect, shot.confidence = "halation", .45
                next_accent = shot.end + 12
    return shots

def ink_ramp(colors):
    stops = [0, 42, 77, 109, 145, 190, 255]
    return np.column_stack([np.interp(np.arange(256), stops, [c[i] for c in colors])
                            for i in (2, 1, 0)]).astype(np.uint8).reshape(256, 1, 3)

HOT = ink_ramp([(8,4,23),(47,10,110),(70,39,220),(240,39,117),(255,98,56),(255,202,83),(255,245,202)])
ICE = ink_ramp([(7,11,23),(12,48,74),(16,113,135),(76,176,171),(215,192,152),(247,211,174),(255,248,223)])
LIME = ink_ramp([(11,9,21),(54,18,104),(111,37,176),(229,42,104),(255,136,70),(222,247,97),(252,255,216)])
def palette(frame, ramp):
    return cv.applyColorMap(cv.cvtColor(frame, cv.COLOR_BGR2GRAY), ramp)

def sound_curve(path):
    pcm = subprocess.check_output(["ffmpeg","-v","error","-i",str(path),"-map","0:a:0","-vn","-ac","1","-ar","12000","-f","f32le","-"])
    signal = np.frombuffer(pcm, np.float32)
    # A 100 Hz analysis clock keeps alignment even at fractional video frame rates.
    count = len(signal)//120
    if not count:
        return np.zeros(1)
    blocks = signal[:count*120].reshape(-1,120)
    rms = np.sqrt(np.mean(blocks**2, axis=1))
    return np.clip(rms / max(np.percentile(rms, 94), .001), 0, 1)

def mix(a, b, weight):
    return cv.addWeighted(a, 1-weight, b, weight, 0)

def smooth(p):
    p = float(np.clip(p, 0, 1))
    return p*p*(3-2*p)

# Local attack, crest and release within selected phrases. Unlisted phrases breathe.
ACCENTS = {
    "tear": (.22, .54, .77, .77),
    "breath": (.08, .72, .96, .55),
    "prism": (.04, .71, .99, .80),
    "iris": (.18, .48, .87, .91),
    "fossil": (.18, .62, .94, .43),
    "halation": (.18, .49, .85, .78),
    "portal": (.34, .59, .83, .74),
    "echo": (.09, .40, .78, .72),
}

def accent(word, progress, dose):
    if word not in ACCENTS:
        return 0.0
    attack, crest, release, peak = ACCENTS[word]
    rise = smooth((progress-attack)/(crest-attack))
    fall = smooth((release-progress)/(release-crest))
    return peak * dose**1.35 * rise * fall

# Deep blue-black shadows, with a long shoulder for reflections in the wet street.
NIGHT = ink_ramp([(3,4,9),(7,10,18),(11,17,28),(20,30,42),(41,49,58),(89,94,92),(207,199,173)])

def glitch(frame, delayed, t, level, energy):
    height, width = frame.shape[:2]
    # Keep chromatic displacement between bursts of horizontal tearing.
    offset = max(1, round(width * (.004 + .023 * level)))
    shifted = frame.copy()
    shifted[:, :, 0] = np.roll(frame[:, :, 0], offset, axis=1)
    shifted[:, :, 2] = np.roll(frame[:, :, 2], -offset, axis=1)
    result = mix(frame, shifted, level * .74)

    beats = t * (1.1 + .65 * level)
    pulse = (.5 + .5 * math.sin(2 * math.pi * beats)) ** 3
    height_fraction = .024 + .06 * level
    for band in range(3):
        position = (.14 + .29 * band + .095 * math.sin(1.8 * t + band * 2.1)) % 1
        top = int(height * position)
        bottom = min(height, top + max(1, round(height * height_fraction)))
        direction = -1 if band % 2 else 1
        jump = direction * round(width * level * (.018 + .12 * pulse))
        tear = np.roll(delayed[top:bottom], jump, axis=1)
        result[top:bottom] = mix(result[top:bottom], tear, level * (.23 + .48 * pulse + .12 * energy))
    return result


def phase_finish(frame, delayed, t, onset, peak, state, dose, energy):
    if state == "crash":
        return mix(frame, palette(frame, NIGHT), .32)
    if state == "dusk":
        return mix(frame, delayed, .12 + .09 * dose)
    if t < peak:
        envelope = smooth((t - onset) / (peak - onset))
        if envelope <= 0:
            return frame
        # A brief fracture at entry gives way to a sustained bloom.
        pulse = smooth((t - onset) / .24) * (1 - smooth((t - onset - .42) / 1.6))
        if pulse > .001:
            frame = glitch(frame, delayed, t, .8 * pulse, energy)
    else:
        envelope = .65 + .35 * dose
    height, width = frame.shape[:2]
    highlights = cv.resize(frame, (max(2, width // 8), max(2, height // 8)), interpolation=cv.INTER_AREA)
    highlights = cv.subtract(highlights, (112, 112, 112, 0))
    glow = cv.resize(cv.GaussianBlur(highlights, (0, 0), 2.8), (width, height))
    return cv.addWeighted(frame, 1., glow, (.42 + .28 * energy) * envelope, 0.)


def render(source, description, output, *, strong=False, continuous=False, by_phase=False):
    shots = score(description)
    onset = next((shot.start for shot in shots if shot.dose > 0), shots[-1].end)
    offset = max((shot.end for shot in shots if shot.dose > 0), default=onset)
    peak = next((shot.start for shot in shots if shot.start > onset and shot.dose >= .55), offset)
    if by_phase:
        peak_accents = iter(("breath", "prism", "portal", "iris"))
        next_accent = peak
        for shot in shots:
            if shot.dose >= .7 and shot.start >= next_accent and not shot.effect:
                shot.effect = next(peak_accents, "")
                shot.confidence = .88
                next_accent = shot.end + 2
    if strong:
        # Keep the spoken cues and add visual accents to otherwise untreated high-dose shots.
        fallback = ("prism", "breath", "iris", "prism")
        next_effect = 0
        for shot in shots:
            if not shot.effect and shot.dose >= .45:
                shot.effect = fallback[next_effect % len(fallback)]
                shot.confidence = .85
                next_effect += 1
    streams = json.loads(subprocess.check_output(["ffprobe","-v","error","-show_streams",
                                                   "-of","json",str(source)]))["streams"]
    video = next(s for s in streams if s["codec_type"] == "video" and not s["disposition"]["attached_pic"])
    rate_text = video.get("avg_frame_rate", "0/0")
    rate = Fraction(video["r_frame_rate"] if rate_text in ("0/0", "0/1") else rate_text)
    fps = float(rate)
    if fps <= 0:
        raise ValueError("Cannot determine the frame rate")
    rotation = sum(int(d.get("rotation", 0)) for d in video.get("side_data_list", []))
    width, height = video["width"], video["height"]
    sar = video.get("sample_aspect_ratio", "1:1")
    if sar not in ("N/A", "0:1"):
        width *= float(Fraction(sar.replace(":", "/")))
    if rotation % 180:
        width, height = height, width
    scale = min(1., 1280/max(width,height), 720/min(width,height))
    W, H = (max(2, 2*round(n*scale/2)) for n in (width,height))
    duration = float(video.get("duration", "inf"))
    short_tail = 0 <= duration-shots[-1].end <= 1.
    if shots[0].start >= duration:
        raise ValueError("The first cue starts after the video ends")
    has_audio = any(s["codec_type"] == "audio" for s in streams)
    energy = sound_curve(source) if has_audio else np.zeros(1)
    cv.setNumThreads(2)
    gy,gx = np.mgrid[0:H:complex(0,181),0:W:complex(0,321)].astype(np.float32)
    mids = [(s.start+s.end)/2 for s in shots]
    levels = np.asarray([[s.dose, s.comedown, s.crash] for s in shots]).T
    phases = []
    for shot in shots:
        state = ("crash" if shot.phase in ("contrecoup", "rechute", "crash") else
                 "dusk" if shot.phase in ("descente", "comedown") else "clear")
        if not phases or phases[-1][1] != state:
            phases.append((shot.start, state))
    phase_index = 0
    past = deque(maxlen=max(2,round(.4*fps)))
    decode = ["ffmpeg","-v","error","-threads","2","-i",str(source),"-map","0:V:0","-an",
              "-vf",f"fps={rate},scale={W}:{H}:flags=area,setsar=1","-pix_fmt","bgr24","-threads","2","-f","rawvideo","-"]
    cmd = ["ffmpeg","-v","error","-y","-f","rawvideo","-pixel_format","bgr24","-video_size",f"{W}x{H}",
           "-framerate",str(rate),"-i","-","-i",str(source),"-map","0:v","-map","1:a:0?","-c:a","copy","-c:v",
           "libx264","-threads","4","-preset","veryfast","-crf","20","-maxrate","6400k","-bufsize","9600k","-pix_fmt","yuv420p","-movflags","+faststart",str(output)]
    idx = frame_no = 0
    with subprocess.Popen(decode,stdout=subprocess.PIPE) as decoder, subprocess.Popen(cmd,stdin=subprocess.PIPE) as encoder:
        while True:
            raw = decoder.stdout.read(W*H*3)
            if not raw:
                break
            t = frame_no/fps
            while idx+1 < len(shots) and t >= shots[idx+1].start:
                idx += 1
            shot = shots[idx]
            start, end = shot.start, shot.end
            dose, comedown, crash = (float(np.interp(t, mids, values)) for values in levels)
            u = min(1,(t-start)/(end-start))
            kind = shot.effect
            ax, ay = (.34,.72) if kind == "fossil" else (.5,.47)
            active = start <= t < end
            strength = accent(kind, u, dose) * shot.confidence if active else 0.
            if strong:
                strength = min(1., 1.6 * strength)
            v = float(energy[min(round(100*t),len(energy)-1)])
            src = np.frombuffer(raw,np.uint8).reshape(H,W,3)
            past.append(src)
            frame = src
            if strength > .001 and kind == "halation":
                # Diffraction spreads the brightest highlights into two crossing streaks.
                small = cv.resize(src,(max(8,W//4),max(8,H//4)), interpolation=cv.INTER_AREA)
                light = cv.subtract(small, (85,85,85,0))
                kernel = np.eye(23,dtype=np.float32)/23
                rays = cv.add(cv.filter2D(light,-1,kernel), cv.filter2D(light,-1,kernel[:,::-1]))
                flare = cv.resize(cv.add(rays,cv.GaussianBlur(light,(0,0),4)),(W,H))
                frame = cv.addWeighted(src,1.,flare,strength*1.7,0)
            elif strength > .001 and kind == "portal":
                # A moving annulus magnifies just a ring of the scene, with glass-like hard rims.
                x, y = (gx-W*ax)/H, (gy-H*ay)/H
                distance = np.hypot(x,y)
                ring = np.exp(-((distance-(.10+.45*u))/.059)**2)
                lens = 1 - .82*strength*ring
                frame = cv.remap(src,cv.resize(W*ax+H*x*lens,(W,H)),cv.resize(H*ay+H*y*lens,(W,H)),
                                 cv.INTER_LINEAR,borderMode=cv.BORDER_REFLECT_101)
            elif strength > .001 and kind == "echo":
                # Drag a cool afterimage of the earlier contours across the current frame.
                old = cv.cvtColor(past[0],cv.COLOR_BGR2GRAY)
                edge = cv.subtract(old,cv.GaussianBlur(old,(0,0),max(1.,W/130)))
                shift = round(W*(.012+.045*u))
                ghost = cv.warpAffine(edge,np.float32([[1,0,shift],[0,1,0]]),(W,H))
                light = cv.merge((ghost,ghost//2,ghost//5))
                frame = cv.addWeighted(src,1.,light,3.2*strength,0)
            elif strength > .001:
                x,y = (gx-W*ax)/H,(gy-H*ay)/H
                r = np.hypot(x,y)
                angle = np.arctan2(y,x)
                ramp = (HOT if idx%2 else LIME) if shot.phase not in ("descente","contrecoup","rechute","crash","comedown") else ICE
                if kind in ("prism","iris","breath"):
                    sectors = {"prism":7,"iris":5,"breath":3}[kind]
                    sector = 2*math.pi/sectors
                    phase = .26*t + .19*np.sin(5*r-2*u)
                    folded = np.abs((angle+phase+sector/2)%sector-sector/2)
                    theta = folded-.9+.23*math.sin(.8*t)
                    if kind == "breath":
                        amount = np.clip((r-.14)*2.8,0,.95)
                    else:
                        amount = .95
                    rr = r*(.76+.16*np.sin(13*r-4*u))
                    mx = gx + amount*(W*ax+H*rr*np.cos(theta)-gx)
                    my = gy + amount*(H*ay+H*rr*np.sin(theta)-gy)
                elif kind == "tear":
                    bands = np.floor((gy/H*11)+.25*math.sin(2*t))
                    jump = np.sin(bands*14.3+math.floor(u*4)*.69)
                    shift = (22+88*dose)*(1+.36*v)
                    mx = gx+jump*shift+16*np.sin(gy/38-3*t)
                    my = gy+7*np.sin(gx/95+2*t)
                else:
                    wave = np.sin(38*r-5*t)
                    mx,my = gx+x*wave*(18+24*dose),gy+y*wave*(18+24*dose)
                warp = cv.remap(src,cv.resize(gx + strength*(mx-gx),(W,H)),cv.resize(gy + strength*(my-gy),(W,H)),cv.INTER_LINEAR,borderMode=cv.BORDER_REFLECT_101)
                print_frame = palette(warp,ramp)
                frame = mix(warp,print_frame,.57+.21*dose)
                if kind == "tear":
                    delay = past[0]
                    for band in range(2,11,3):
                        a,b = H*band//11,H*(band+1)//11
                        frame[a:b] = np.roll(palette(delay[a:b], ICE if ramp is not ICE else HOT), int(40+90*v),axis=1)
                if kind in ("prism","iris","fossil"):
                    gray = cv.cvtColor(warp,cv.COLOR_BGR2GRAY)
                    # Contour bands follow photographic luminance, like a movable engraving plate.
                    level = (gray.astype(np.int16)+int(12*t))%31
                    contour = (level < (3 if kind=="fossil" else 2))
                    frame[contour] = (167,245,239) if ramp is not ICE else (50,52,32)
                if kind in ("iris","fossil"):
                    # Broken wavefronts echo the original light source and later the shell whorl.
                    for j in range(8):
                        rad = ((j+u*2.7)%8)*H/11+12
                        origin = (int(ax*W),int(ay*H))
                        cv.ellipse(frame,origin,(int(rad*1.12),int(rad*.82)), -24, j*47+t*18, j*47+t*18+120,
                                   (158,227,244),1+j%2,cv.LINE_AA)
                frame = mix(src, frame, strength)
            # As the comedown crosses into crash, keep only the street's brightest reflections.
            while phase_index+1 < len(phases) and t >= phases[phase_index+1][0]:
                phase_index += 1
            phase_start, state = phases[phase_index]
            previous = phases[phase_index-1][1] if phase_index else "clear"
            targets = {"clear":0., "dusk":.24+.25*comedown+.20*crash, "crash":.985}
            fade = smooth((t-phase_start)/(5 if state=="crash" else 8))
            shadow = ((1-fade)*targets[previous]+fade*targets[state]) if active else 0.
            if shadow > .001:
                frame = mix(frame, palette(frame, NIGHT), shadow)
            if short_tail and state == "crash" and t >= shots[-1].end:
                # Hold the night grade across the encoder tail, then fade to black.
                frame = cv.convertScaleAbs(palette(src,NIGHT), alpha=max(0,1-(t-shots[-1].end)/.60))
            if continuous and onset <= t < offset:
                fade = min(smooth((t-onset)/.65), smooth((offset-t)/.85))
                level = fade * (.28 + .70 * dose)
                if level > .001:
                    frame = glitch(frame, past[0], t, level, v)
            if by_phase and onset <= t < offset:
                frame = phase_finish(frame, past[0], t, onset, peak, state, dose, v)
            encoder.stdin.write(frame.tobytes())
            frame_no += 1
            if frame_no%max(1,round(10*fps))==0:
                print(f"{frame_no/fps:.0f} s",flush=True)
        encoder.stdin.close()
        if encoder.wait() or decoder.wait() or not frame_no:
            raise RuntimeError("Video encoding failed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source","description","output"):
        parser.add_argument(name,type=Path)
    parser.add_argument("--strong", action="store_true",
                        help="Boost accents and add effects to unassigned high-dose cues.")
    style = parser.add_mutually_exclusive_group()
    style.add_argument("--continuous", action="store_true",
                        help="Layer continuous RGB separation and glitch bands across the active dose.")
    style.add_argument("--by-phase", action="store_true",
                       help="Use an entry glitch, peak optics, and a cool trailing comedown.")
    args = parser.parse_args()
    if args.output.resolve() in (args.source.resolve(), args.description.resolve()):
        parser.error("Choose a separate output MP4")
    with tempfile.TemporaryDirectory(dir=args.output.parent) as directory:
        temporary = Path(directory) / "render.mp4"
        render(args.source, args.description, temporary,
               strong=args.strong, continuous=args.continuous, by_phase=args.by_phase)
        temporary.replace(args.output)
