"""Render the v5 rave/silence film from its MP4 and describe.py score.

python scripts/rave_silence_fx.py source.mp4 description.md result.mp4
Requires FFmpeg, OpenCV and NumPy.
"""
import argparse
import math
import re
import subprocess
from collections import deque
from pathlib import Path

import cv2 as cv
import numpy as np

W, H = 1280, 720
# Art direction by phrase. Coordinates locate the optical centre within the shot.
CUES = [
    ("pulse", "SHIMMERING", .35, .47), ("tear", "TREMBLING", .44, .52),
    ("tear", "BRUTAL", .47, .52), ("breath", "BREATHE", .50, .43),
    ("breath", "EXHALE", .52, .46), ("choir", "PARLER", .51, .50),
    ("tear", "CHAOS", .50, .45), ("aperture", "SILENCE", .51, .46),
    ("prism", "COMUNICACIÓN", .50, .48), ("prism", "UNGLAUBLICH", .50, .48),
    ("iris", "ÉNORME", .50, .50), ("iris", "GIGANTIC", .47, .48),
    ("echo", "CLINGS", .50, .52), ("boxes", "CRATES", .47, .49),
    ("boxes", "WAREHOUSES", .5, .52), ("fossil", "SEASHELLS", .34, .72),
    ("stone", "BÉTON", .51, .55), ("fossil", "FOSSILS", .39, .69),
    ("tear", "LOUDNESS", .5, .53), ("aperture", "SILENCE", .51, .51),
]

def timing(value):
    minutes, seconds = value.split(":")
    return 60 * int(minutes) + float(seconds)

def score(path):
    shots = []
    for section in re.split(r"^### Image ", path.read_text().strip(), flags=re.M)[1:]:
        start, end = re.search(r"(\d+:\d+\.\d+) → (\d+:\d+\.\d+)", section).groups()
        dose = float(re.search(r"force perçue d = ([\d.]+)", section)[1])
        phrase = re.search(r"\*\*Paroles\*\* : « (.*?) »", section)[1]
        drug = re.search(r"^- \*\*Drogue\*\* : phase « (.*?) »(.*)$", section, re.M)
        shares = dict(re.findall(r"mdma_(\w+) (\d+)%", drug[2]))
        shots.append((timing(start), timing(end), dose, phrase, drug[1],
                      int(shares.get("comedown", 0))/100, int(shares.get("crash", 0))/100))
    if len(shots) != len(CUES) or any(cue[1].casefold() not in shot[3].casefold()
                                       for cue, shot in zip(CUES, shots)):
        raise ValueError("Expected the 20 phrases of v5-mdma-etats-rave-silence")
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

def sound_curve(path, fps):
    pcm = subprocess.check_output(["ffmpeg","-v","error","-i",str(path),"-vn","-ac","1","-ar","12000","-f","f32le","-"])
    signal = np.frombuffer(pcm, np.float32)
    n = round(12000/fps)
    blocks = signal[:len(signal)//n*n].reshape(-1,n)
    rms = np.sqrt(np.mean(blocks**2, axis=1))
    return np.clip(rms / max(np.percentile(rms, 94), .001), 0, 1)

def mix(a, b, weight):
    return cv.addWeighted(a, 1-weight, b, weight, 0)

def smooth(p):
    p = float(np.clip(p, 0, 1))
    return p*p*(3-2*p)

# Local attack, crest and release within selected phrases. Unlisted phrases breathe.
ACCENTS = {
    "BRUTAL": (.22, .56, .73, .78),
    "EXHALE": (.08, .72, .96, .55),
    "CHAOS": (.41, .49, .75, .69),
    "COMUNICACIÓN": (.04, .71, .99, .77),
    "ÉNORME": (.18, .48, .87, .91),
    "GIGANTIC": (.00, .22, .65, .36),
    "SEASHELLS": (.18, .62, .94, .33),
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

def render(source, description, output):
    shots = score(description)
    cap = cv.VideoCapture(str(source))
    fps = cap.get(cv.CAP_PROP_FPS)
    if not cap.isOpened() or fps != 30:
        raise ValueError("Expected the 30 fps v5 source")
    energy = sound_curve(source, fps)
    cv.setNumThreads(2)
    gy,gx = np.mgrid[0:H:complex(0,181),0:W:complex(0,321)].astype(np.float32)
    mids = [(s[0]+s[1])/2 for s in shots]
    levels = np.asarray([[s[2], s[5], s[6]] for s in shots]).T
    crash_start = next(s[0] for s in shots if s[4] == "Contrecoup")
    dusk_start = next(s[0] for s in shots if s[4] == "Descente")
    past = deque(maxlen=12)
    cmd = ["ffmpeg","-v","error","-y","-f","rawvideo","-pixel_format","bgr24","-video_size",f"{W}x{H}",
           "-framerate",str(fps),"-i","-","-i",str(source),"-map","0:v","-map","1:a","-c:a","copy","-c:v",
           "libx264","-threads","4","-preset","veryfast","-crf","20","-maxrate","6400k","-bufsize","9600k","-pix_fmt","yuv420p","-movflags","+faststart",str(output)]
    idx = frame_no = 0
    with subprocess.Popen(cmd,stdin=subprocess.PIPE) as encoder:
        while True:
            ok, raw = cap.read()
            if not ok:
                break
            t = frame_no/fps
            while idx+1 < len(shots) and t >= shots[idx+1][0]:
                idx += 1
            start, end = shots[idx][:2]
            dose, comedown, crash = (float(np.interp(t, mids, values)) for values in levels)
            u = min(1,(t-start)/(end-start))
            kind,word,ax,ay = CUES[idx]
            strength = accent(word, u, dose)
            v = float(energy[min(frame_no,len(energy)-1)])
            src = cv.resize(raw,(W,H),interpolation=cv.INTER_AREA)
            past.append(src)
            frame = src
            if strength > .001:
                x,y = (gx-W*ax)/H,(gy-H*ay)/H
                r = np.hypot(x,y)
                angle = np.arctan2(y,x)
                ramp = (HOT if idx%2 else LIME) if idx < 12 else ICE
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
                elif kind in ("tear","choir","echo"):
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
                if kind in ("tear","choir","echo"):
                    delay = past[0]
                    for band in range(1 if kind=="choir" else 2,11,3):
                        a,b = H*band//11,H*(band+1)//11
                        frame[a:b] = np.roll(palette(delay[a:b], ICE if idx<12 else HOT), int(40+90*v),axis=1)
                if kind in ("prism","iris","fossil"):
                    gray = cv.cvtColor(warp,cv.COLOR_BGR2GRAY)
                    # Contour bands follow photographic luminance, like a movable engraving plate.
                    level = (gray.astype(np.int16)+int(12*t))%31
                    contour = (level < (3 if kind=="fossil" else 2))
                    frame[contour] = (167,245,239) if idx<12 else (50,52,32)
                if kind in ("iris","fossil"):
                    # Broken wavefronts echo the original light source and later the shell whorl.
                    for j in range(8):
                        rad = ((j+u*2.7)%8)*H/11+12
                        origin = (int(ax*W),int(ay*H))
                        cv.ellipse(frame,origin,(int(rad*1.12),int(rad*.82)), -24, j*47+t*18, j*47+t*18+120,
                                   (158,227,244),1+j%2,cv.LINE_AA)
                frame = mix(src, frame, strength)
            # As the comedown crosses into crash, keep only the street's brightest reflections.
            descent = smooth((t-dusk_start)/9)
            relapse = smooth((t-crash_start+2)/6)
            shadow = descent * (.14 + .27*comedown + .30*crash) + .62*relapse
            if shadow > .001:
                night = palette(frame, NIGHT)
                frame = mix(frame, night, min(.985, shadow))
            if t > shots[-1][1]:
                frame = cv.convertScaleAbs(frame,alpha=max(0,1-(t-shots[-1][1])/.60))
            encoder.stdin.write(frame.tobytes())
            frame_no += 1
            if frame_no%300==0:
                print(f"{frame_no/fps:.0f} s",flush=True)
        encoder.stdin.close()
        if encoder.wait():
            raise RuntimeError("Video encoding failed")
    cap.release()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source","description","output"):
        parser.add_argument(name,type=Path)
    render(**vars(parser.parse_args()))
