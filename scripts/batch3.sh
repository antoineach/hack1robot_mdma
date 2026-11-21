#!/usr/bin/env bash
# Versions 1 min (variantes 1 à 4), puis drogue subtile et moyenne
set -e
cd "$(dirname "$0")/.."
for r in p1-nodrug-60s p1-drug4-60s; do
  ./run.sh render --run runs/$r
  ./run.sh voice --run runs/$r
  ./run.sh sound --run runs/$r --mode mixte
done
./run.sh assemble --run runs/p1-nodrug-60s --mode voix          # variante 1
./run.sh assemble --run runs/p1-drug4-60s --mode voix           # variante 2
./run.sh assemble --run runs/p1-nodrug-60s --mode sonorisation  # variante 3
./run.sh assemble --run runs/p1-drug4-60s --mode mixte          # variante 4
./run.sh publish runs/p1-nodrug-60s/out_voix.mp4 runs/p1-drug4-60s/out_voix.mp4 runs/p1-nodrug-60s/out_sonorisation.mp4 runs/p1-drug4-60s/out_mixte.mp4
# étape 4 de la spec : baisser α jusqu'à un effet subtil
./run.sh record --config configs/variants/drug_subtle.yaml --run-id p1-drug1-60s
./run.sh record --config configs/variants/drug_medium.yaml --run-id p1-drug2-60s
