#!/usr/bin/env bash
# Critère v2 : chacune des 11 drogues produit une vidéo de 30 s sans erreur
cd "$(dirname "$0")/.."
for d in alcool cannabis cocaine amphetamines mdma lsd champignons dmt ketamine heroine datura; do
  r=runs/v2drug-$d
  mkdir -p $r
  printf 'run_tag: v2drug\ndrug: {name: %s, intensity: 1.0}\nvideo: {target_duration_s: 30}\nsound: {mode: voix}\n' $d > $r/request.yaml
  if ./run.sh all --config $r/request.yaml > $r/all.log 2>&1; then echo "OK $d"; else echo "ECHEC $d"; fi
done
