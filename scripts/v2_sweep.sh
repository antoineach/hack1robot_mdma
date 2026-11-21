#!/usr/bin/env bash
# Étape 2 de la v2 : vérifier les niveaux sur alcool, LSD, cocaïne (intensité 0,5 / 1 / 1,5)
set -e
cd "$(dirname "$0")/.."
for d in alcool lsd cocaine; do
  ./run.sh py sweep --config configs/tests/v2_$d.yaml --alphas 0.5 1.0 1.5 --prefix v2sweep-$d
done
