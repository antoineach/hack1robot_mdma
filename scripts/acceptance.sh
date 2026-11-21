#!/usr/bin/env bash
# Critères d'acceptation : `all` de bout en bout + déterminisme complet de la passe 1
set -e
cd "$(dirname "$0")/.."
rm -rf runs/accept-all
./run.sh all --config configs/default.yaml --run-id accept-all
.venv/bin/python - <<'PY'
import json, os
def load(r): return [json.loads(l) for l in open(f"runs/{r}/trace.jsonl")]
a, b = load("p1-nodrug"), load("accept-all")
same = len(a) == len(b) and all(x["token_id"] == y["token_id"] and x["layers"] == y["layers"] for x, y in zip(a, b))
print("TRACE IDENTIQUE A p1-nodrug :", same, len(a), len(b))
w = json.load(open("runs/accept-all/windows.json"))
frames = sorted(os.listdir("runs/accept-all/frames"))
audio = [f for f in os.listdir("runs/accept-all/audio") if f[:4].isdigit()]
print("tranches", len(w), "images", len([f for f in frames if f.endswith(".png")]), "voix", len(audio))
print("out.mp4 :", os.path.getsize("runs/accept-all/out.mp4"), "octets")
PY
