# Postproduction VFX par phase

Pars du MP4 source et du Markdown générés par le même run. Si plusieurs exports sont demandés, traite chaque paire séparément. Garde le mix audio de chaque export.

## Choisir les effets d’après la fiche

Lis les titres horodatés, les phases, la force perçue `d` et les paroles. La première tranche où `d > 0` marque la bascule. Le préréglage repère la zone haute à la première tranche suivante où `d ≥ 0,55`. Pour une vidéo dont la fiche ne contient pas ces repères, vérifie d’abord la courbe et les phases du run.

| Zone | Traitement |
| --- | --- |
| Neutre | Garde l’image source jusqu’à la bascule. |
| Bascule | Fais apparaître brièvement une séparation RVB et des déchirures horizontales. Le préréglage les estompe en environ deux secondes. |
| Montée | Fais croître le halo des hautes lumières avec la progression de la phase. |
| Pic ou plateau | Maintiens le halo et espace les accents optiques. Alterne respiration, prisme, anneau et iris selon les tranches. Les mots de la fiche peuvent déclencher leurs propres accents. |
| Descente | Fais glisser l’image vers des tons plus froids et réintroduis une image précédente en transparence. |
| Contrecoup | Assombris progressivement l’image et préserve les hautes lumières. |

Sur **MDMA v7 journée S2**, les repères sont **0:07,28** pour la bascule, **0:17,31** pour l’entrée en zone haute, **0:58,11** pour la descente et **1:16,15** pour le contrecoup. Reprends les timecodes de chaque fiche pour les autres vidéos.

## Rendre et vérifier

Depuis la racine du dépôt, avec Python, FFmpeg et FFprobe disponibles.

```bash
python -m pip install opencv-python-headless
python scripts/rave_silence_fx.py source.mp4 source.md rendu.mp4 --by-phase
ffmpeg -v error -xerror -i rendu.mp4 -f null -
```

Le script conserve la première piste audio et limite la résolution à 720p pour une source 16:9. Compare les empreintes des deux pistes si la source contient de l’audio.

```bash
for video in source.mp4 rendu.mp4; do
  ffmpeg -v error -i "$video" -map 0:a:0 -c copy -f hash -
done
```

Pour le GIF, prends des extraits de 2 à 3 secondes à la bascule, au pic, à la descente et au contrecoup lorsque ces zones sont présentes. Utilise le même timecode pour les deux vidéos. Place la source à gauche, le rendu à droite, et indique la phase et le timecode sous l’aperçu ou dans l’image. Vérifie que la déchirure est visible à la bascule et que les extraits suivants montrent des traitements distincts. Sur la S2, le GIF utilise les départs à **7,3**, **29,5**, **62** et **77** secondes.

Publie le MP4 et son GIF ensemble dans `previews/` sur `film-transitions`. Si la taille du MP4 dépasse la limite de l’API GitHub, compresse uniquement la vidéo et conserve l’audio avec `-c:a copy`.

[GIF de référence](previews/v7-mdma-journee-s2-fx-par-phase-avant-apres.gif) · [MP4 de référence](previews/v7-mdma-journee-s2-fx-par-phase.mp4)
