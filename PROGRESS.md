# Avancement

## Fait
- Phase 0, passes 1 et 2, son (effets de voix, sonorisation), variantes 1 à 5, durée cible, recalibrage de la drogue.
- Critères d'acceptation vérifiés (`runs/accept-all`), MORNING_REPORT.md écrit.
- 15 vidéos copiées dans `~/pCloudDrive/Transfert/hack1robo/`.

## En cours
- Rien.

## Prochaines étapes possibles
- Normalisation robuste de la drogue (échelle de α lisible), variantes v2 (bruit J-space, échange de concepts).
- Ajuster la durée cible (`slice_target_s` 2,5) et le mixage après écoute.
- Registre d'images plus abstrait si souhaité.

## Règles pratiques
- Toute commande GPU passe par `./run.sh …` seule (pas de `cd … &&`, pas de pipe).
- Pour enchaîner : `./run.sh script scripts/<fichier>.sh`.
- Ne jamais charger Gemma et Z-Image/Stable Audio en même temps.
