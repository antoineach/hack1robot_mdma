#!/usr/bin/env bash
# Son complet + montage des variantes 1 à 4 (phrase 1)
set -e
cd "$(dirname "$0")/.."
./run.sh sound --run runs/p1-nodrug --mode mixte
./run.sh sound --run runs/p1-drug4 --mode mixte
./run.sh assemble --run runs/p1-nodrug --mode voix --raw-voice
./run.sh assemble --run runs/p1-nodrug --mode voix          # variante 1
./run.sh assemble --run runs/p1-drug4 --mode voix           # variante 2
./run.sh assemble --run runs/p1-nodrug --mode sonorisation  # variante 3
./run.sh assemble --run runs/p1-drug4 --mode mixte          # variante 4
./run.sh publish runs/p1-nodrug/out_voix.mp4 runs/p1-drug4/out_voix.mp4 runs/p1-nodrug/out_sonorisation.mp4 runs/p1-drug4/out_mixte.mp4 runs/p1-nodrug/out_voix_brute.mp4
