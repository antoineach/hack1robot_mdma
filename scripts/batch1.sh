#!/usr/bin/env bash
# Rendu des deux runs de passe 1, puis voix/son du run drogué
set -e
cd "$(dirname "$0")/.."
./run.sh render --run runs/p1-nodrug
./run.sh render --run runs/p1-drug4
./run.sh voice --run runs/p1-drug4
