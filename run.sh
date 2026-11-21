#!/usr/bin/env bash
# Point d'entrée unique pour toutes les étapes longues (exécuté hors sandbox pour le GPU).
# Usage : ./run.sh <étape> [args...]
#   validate [config]          valide la lecture J-lens (étape 2)
#   smoke <image|voice|audio>   essai d'une brique
#   record  --config c.yaml [--run-id id]
#   render  --run runs/<id>
#   voice   --run runs/<id>
#   sound   --run runs/<id>     traits + sonorisation + effets de voix
#   assemble --run runs/<id> [--mode voix|sonorisation|mixte]
#   all     --config c.yaml [--run-id id]
#   py <module> [args]          lance python -m introspect.<module>
#   test                        tests rapides (CPU)
set -euo pipefail
cd "$(dirname "$0")"
export HF_HUB_CACHE="$PWD/weights/hub"
export HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-1}"
export HF_HUB_DISABLE_TELEMETRY=1
export TOKENIZERS_PARALLELISM=false
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
PY="$PWD/.venv/bin/python"
mkdir -p runs/setup

step="${1:-}"; shift || true
case "$step" in
  validate) "$PY" -m introspect.validate "$@" 2>&1 | tee runs/setup/validate.log ;;
  smoke)    "$PY" -m introspect.smoke "$@" 2>&1 | tee "runs/setup/smoke_${1:-all}.log" ;;
  record)   "$PY" -m introspect.record "$@" ;;
  render)   "$PY" -m introspect.render "$@" ;;
  voice)    "$PY" -m introspect.voice "$@" ;;
  sound)    "$PY" -m introspect.sound "$@" ;;
  assemble) "$PY" -m introspect.assemble "$@" ;;
  all)      "$PY" -m introspect.cli all "$@" ;;
  py)       mod="$1"; shift; "$PY" -m "introspect.$mod" "$@" ;;
  test)     "$PY" -m introspect.selftest "$@" ;;
  git)      git "$@" ;;
  web)      exec "$PY" -m introspect.webapp "$@" ;;   # interface Gradio (lien public + mot de passe)
  web-install)  # installe le service utilisateur systemd + timer de renouvellement (sans sudo)
            d="$HOME/.config/systemd/user"; mkdir -p "$d"
            cp -v scripts/systemd/hack1robo-web.service scripts/systemd/hack1robo-web-renew.service scripts/systemd/hack1robo-web-renew.timer "$d/"
            systemctl --user daemon-reload
            systemctl --user enable --now hack1robo-web.service hack1robo-web-renew.timer
            loginctl enable-linger || echo "loginctl enable-linger refusé : le service tourne tant que la session reste ouverte"
            systemctl --user --no-pager status hack1robo-web.service | head -5 ;;
  web-status) systemctl --user --no-pager status hack1robo-web.service hack1robo-web-renew.timer | head -20
            loginctl show-user "$USER" -p Linger
            journalctl --user -u hack1robo-web.service --no-pager -n 50 -o cat | grep -E "^\[web\]|Traceback|Error" | tail -5 ;;
  web-restart) systemctl --user restart hack1robo-web.service ;;
  web-kill) systemctl --user kill --signal=SIGKILL hack1robo-web.service ;;   # test d'arrêt forcé
  script)   bash "$1" ;;   # enchaîne plusieurs étapes (fichier du projet)
  publish)  # copie les vidéos finales vers pCloud (demandé par l'utilisateur, 2026-11-21)
            dest="$HOME/pCloudDrive/Transfert/hack1robo"
            [ -d "$HOME/pCloudDrive/Transfert" ] || { echo "Transfert introuvable dans pCloudDrive" >&2; exit 1; }
            mkdir -p "$dest"
            for f in "$@"; do               # arguments : runs/<id>/out_*.mp4
              case "$f" in runs/*/out_*.mp4) ;; *) echo "ignoré : $f" >&2; continue ;; esac
              run=$(basename "$(dirname "$f")")
              cp -v --no-clobber "$f" "$dest/${run}_$(basename "$f")"
            done
            ls -la "$dest" ;;
  publish-doc)  # copie des documents du projet vers pCloud/Transfert/hack1robo/echange (demandé par l'utilisateur)
            dest="$HOME/pCloudDrive/Transfert/hack1robo/echange"
            [ -d "$HOME/pCloudDrive/Transfert/hack1robo" ] || { echo "Transfert/hack1robo introuvable" >&2; exit 1; }
            mkdir -p "$dest"
            for f in "$@"; do
              case "$f" in *.md) [ -f "$f" ] && cp -v "$f" "$dest/" ;; *) echo "ignoré : $f" >&2 ;; esac
            done
            ls -la "$dest" ;;
  *) sed -n '2,15p' "$0"; exit 1 ;;
esac
