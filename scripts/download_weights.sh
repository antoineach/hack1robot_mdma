#!/usr/bin/env bash
# Télécharge tous les poids dans weights/hub (cache HF du projet).
# Le jeton HF est lu depuis ~/.cache/huggingface/token (jamais écrit ici).
set -u
cd "$(dirname "$0")/.."
export HF_HUB_CACHE="$PWD/weights/hub"
HF=.venv/bin/hf
mkdir -p weights/hub runs/setup
LOG=runs/setup/download_log.txt
dl() { echo "=== $(date +%T) $*" | tee -a "$LOG"; "$HF" download "$@" >>"$LOG" 2>&1 && echo "OK $1" | tee -a "$LOG" || echo "FAIL $1" | tee -a "$LOG"; }

dl neuronpedia/jacobian-lens --include "gemma-3-12b-it/jlens/Salesforce-wikitext/*"
dl hexgrad/Kokoro-82M
dl sentence-transformers/paraphrase-multilingual-mpnet-base-v2
dl stabilityai/stable-audio-open-1.0
dl google/gemma-3-12b-it
dl Tongyi-MAI/Z-Image-Turbo
echo "=== $(date +%T) DONE" | tee -a "$LOG"
du -sh weights/hub/* | tee -a "$LOG"
