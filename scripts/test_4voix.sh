#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."
./run.sh voice --run runs/test-4voix
./run.sh sound --run runs/test-4voix --mode voix
./run.sh assemble --run runs/test-4voix --mode voix
