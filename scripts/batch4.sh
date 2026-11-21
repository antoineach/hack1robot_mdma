#!/usr/bin/env bash
# Drogue recalibrée (subtile 0,002 / forte 0,004) en 1 min + phrases 2 et 3 (variante 5)
set -e
cd "$(dirname "$0")/.."
./run.sh record --config configs/variants/phrase2_subtle.yaml --run-id p2-subtle-60s
./run.sh record --config configs/variants/phrase3_subtle.yaml --run-id p3-subtle-60s
for r in sweep-a0.002 sweep-a0.004 p2-subtle-60s p3-subtle-60s; do
  ./run.sh render --run runs/$r
  ./run.sh voice --run runs/$r
  ./run.sh sound --run runs/$r --mode mixte
done
./run.sh assemble --run runs/sweep-a0.002 --mode voix
./run.sh assemble --run runs/sweep-a0.002 --mode mixte
./run.sh assemble --run runs/sweep-a0.004 --mode voix
./run.sh assemble --run runs/sweep-a0.004 --mode mixte
./run.sh assemble --run runs/p2-subtle-60s --mode mixte
./run.sh assemble --run runs/p3-subtle-60s --mode mixte
./run.sh publish runs/sweep-a0.002/out_voix.mp4 runs/sweep-a0.002/out_mixte.mp4 runs/sweep-a0.004/out_voix.mp4 runs/sweep-a0.004/out_mixte.mp4 runs/p2-subtle-60s/out_mixte.mp4 runs/p3-subtle-60s/out_mixte.mp4
