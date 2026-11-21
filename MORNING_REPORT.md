# Rapport du matin — 21 novembre 2026

Nuit démarrée à 06:02. L'utilisateur a été disponible pour échanger à partir de ~06:10, et la limite de 7 h a été levée. Détail des choix : [DECISIONS.md](DECISIONS.md). Avancement : [PROGRESS.md](PROGRESS.md).

## En bref

- La chaîne complète fonctionne : Gemma 3 12B disserte, la J-lens lit les couches 19 à 44, les mots filtrés sont regroupés en tranches, puis Z-Image produit les images, Kokoro la voix et ffmpeg monte la vidéo.
- La drogue fonctionne, mais l'échelle de α de la spec est environ 1 000 fois trop forte pour Gemma 3. Les valeurs ont été recalibrées (voir la section « Drogue »).
- 15 vidéos sont produites, toutes copiées dans `~/pCloudDrive/Transfert/hack1robo/`.
- Critères d'acceptation : voir la section dédiée plus bas.

## Le prompt qui fait disserter le modèle

Réglage `input.system` : **« Tu dissertes longuement et librement sur le sujet donné. »**

Gemma 3 n'a pas de rôle système natif : son chat template colle ce texte au début du premier message utilisateur. Prompt exact reçu par le modèle :

```text
<bos><start_of_turn>user
Tu dissertes longuement et librement sur le sujet donné.

Le silence est-il une forme de langage ?<end_of_turn>
<start_of_turn>model
```

Génération : 600 tokens, température 0,8, top-p 0,95, graine 1. Code : `introspect/record.py:build_prompt`, `sample`.

## La drogue : comment le biais est fait

**Direction d'un concept** (`introspect/lensmodel.py:Reader.direction`). Pour un mot t et une couche l :

```text
v = J[l]ᵀ · (g ⊙ W_U[t]),  normalisé
```

- `W_U[t]` : ligne de la tête de sortie pour le token « ▁t ».
- `g = 1 + poids de la norme finale` (RMSNorm de Gemma).
- `J[l]` : matrice de la J-lens Neuronpedia à cette couche.

C'est la direction qui fait le plus monter t dans la lecture J-lens. Si le mot fait plusieurs tokens, on prend la moyenne des directions, avec un avertissement dans le journal.

**Injection** (`introspect/record.py:Hooks`). Un hook sur la sortie de chaque bloc de la plage ajoute, à la position du token en cours (et sur tout le prompt si `on_prompt: true`) :

```text
h ← h + α(t) · ‖h‖ · v
```

La lecture J-lens est faite après l'injection : on lit l'intérieur drogué. L'α de chaque pas est enregistré dans `trace.jsonl`, et il pilote aussi les effets « drogués » du son (phaser, distorsion, vibrato sur la voix ; désaccord, modulation en anneau et saturation sur la sonorisation).

**Réglages** (liste `drugs:`, plusieurs drogues possibles en même temps) :

| Clé | Rôle | Valeur utilisée |
| --- | --- | --- |
| `word` | Concept injecté | `ocean` |
| `alpha` | Intensité | 0,002 (subtile), 0,004 (forte) |
| `band` | Plage de couches, en fraction de la profondeur | [0,45 ; 0,70] → couches 22 à 33 sur 48 |
| `profile` | `constant`, `ramp`, `pulse`, `sine` | `ramp` |
| `start`, `end` | Pas de début de la rampe et pas où α est atteint | 100, 400 |
| `period` | Période de `pulse` et `sine` (tokens) | 40 |
| `on_prompt` | Droguer aussi les tokens de la question | `false` |

**Calibration mesurée** (runs `sweep-a*`, `introspect/sweep.py`) :

| α | Texte | Lecture intérieure |
| --- | --- | --- |
| 0,0005 – 0,001 | Normal | Pas d'océan, légers glissements |
| 0,002 | Cohérent, quelques glissements (« soulagement après une tempête ») | « ocean » affleure par intermittence |
| 0,004 | Dérive vers la mer, texte défait en fin (« ocean breeze… deep sea ») | Océan omniprésent à partir du pas 300 |
| 0,05 à 4 (spec) | S'effondre en « ocean ocean ocean… » | Saturé |

Cause : la norme du résidu de Gemma 3 est dominée par quelques dimensions géantes (massive activations), donc `‖h‖` surestime l'échelle utile. De plus, la poussée est ajoutée sur 12 couches et se cumule.

**Pistes pour faire varier l'effet** (non implémentées) :
- normaliser par une norme robuste (sans les dimensions géantes) pour que α ait une échelle lisible ;
- variantes v2 de la spec : bruit aléatoire dans l'espace J, échange de concepts (retirer A, ajouter B) ;
- explorer la plage de couches et l'injection sur toutes les positions.

## Vidéos produites

Toutes sont dans `runs/<run>/` et copiées dans `~/pCloudDrive/Transfert/hack1robo/<run>_<fichier>`.

**Versions longues** (600 tokens, 73 tranches, une tranche tous les 8 tokens) :

| Fichier | Description |
| --- | --- |
| `p1-nodrug/out_voix_brute.mp4` | Phrase 1, sans drogue, voix brute (6 min 13) : premier jalon de bout en bout |
| `p1-nodrug/out_voix.mp4` | Variante 1 : sans drogue, voix avec effets (7 min 46) |
| `p1-drug4/out_voix.mp4` | Variante 2 : drogue α = 4 (échelle de la spec, saturée), voix avec effets ; les images basculent vers la mer et y restent |
| `p1-nodrug/out_sonorisation.mp4` | Variante 3 : sans drogue, sonorisation seule (Stable Audio + synthèse) |
| `p1-drug4/out_mixte.mp4` | Variante 4 : drogue α = 4, voix + sonorisation |

**Versions d'environ 1 min** (`video.target_duration_s: 60`, 20 tranches, durée réelle 68 à 74 s) :

| Fichier | Description |
| --- | --- |
| `p1-nodrug-60s/out_voix.mp4` | Variante 1 courte : sans drogue, voix avec effets |
| `p1-drug4-60s/out_voix.mp4` | Variante 2 courte : drogue α = 4 (saturée) |
| `p1-nodrug-60s/out_sonorisation.mp4` | Variante 3 courte : sonorisation seule |
| `p1-drug4-60s/out_mixte.mp4` | Variante 4 courte : drogue α = 4, mixte |
| `sweep-a0.002/out_voix.mp4` | Drogue subtile recalibrée (0,002), voix avec effets |
| `sweep-a0.002/out_mixte.mp4` | Drogue subtile recalibrée, mixte |
| `sweep-a0.004/out_voix.mp4` | Drogue forte recalibrée (0,004), voix avec effets |
| `sweep-a0.004/out_mixte.mp4` | Drogue forte recalibrée, mixte |
| `p2-subtle-60s/out_mixte.mp4` | Variante 5 : phrase 2 (« Que reste-t-il d'un souvenir… »), drogue subtile, mixte |
| `p3-subtle-60s/out_mixte.mp4` | Variante 5 : phrase 3 (« Une machine peut-elle rêver ? »), drogue subtile, mixte |

## Ce qui fonctionne

- Lecture J-lens validée : top-5 identiques à `lens.apply` sur 37 couches sur 47, au moins 4 sur 5 en commun partout (les écarts viennent du bf16 de jlens contre le fp32 du code) ; à la dernière couche, on retrouve exactement les logits du modèle (`runs/setup/validate_lens.json`).
- Mots lisibles après filtrage : silence, unspoken, grieving, gestures, tacit… En majorité anglais, comme prévu, avec un peu de français et d'autres langues gardés comme texture.
- Images : Z-Image-Turbo, gabarit « métaphore visuelle » (voir les limites), chaîne img2img avec retour au text-to-image toutes les 8 tranches.
- Voix Kokoro `ff_siwis` (espeak-ng du système), effets sémantiques mot par mot (pedalboard).
- Fiches de traits : NRC VAD (anglais et français), Lancaster, Brysbaert, avec repli par embeddings multilingues ; 141 mots sur 230 couverts par les lexiques dans le run principal.
- Sonorisation : couche A Stable Audio Open (un clip par tranche) et couche B synthèse paramétrique (numpy).
- Durée cible (`video.target_duration_s`) et refonte des tranches sans relancer le LLM (`rewindow`).

## Limites et ce qui ne fonctionne pas

- **Prompt d'image** : la liste brute de la spec (« mot1, mot2, …, style ») fait dessiner les mots en lettres par Z-Image, et l'img2img à 0,55 restait bloqué sur la première composition. Remplacé par « A surreal dreamlike oil painting, a visual metaphor of {6 mots}. {style} », avec `strength` 0,7. La variante liste est conservée dans `configs/variants/img_liste.yaml`. Les images restent assez figuratives (personnages, forêts) : on peut aller vers plus d'abstraction en changeant `image.style` et `image.prompt_template`.
- **Durée cible** dépassée d'environ 10 à 20 % (68 à 74 s pour 60 s), à cause des queues d'effets de voix. Pour corriger : `video.slice_target_s: 2.5` ou `voice.max_words: 1`.
- **α de la spec** inutilisable tel quel (voir « Drogue »). Les vidéos `p1-drug4*` montrent l'état saturé.
- **Montage xfade** : le fondu est calculé en Python et envoyé à ffmpeg, plutôt qu'un graphe `xfade` (même rendu, plus robuste).
- **Pas encore fait** : polyphonie des voix (codée, jamais rendue), voix anglaise pour les mots anglais (codée, `voice.english_voice: true`, jamais rendue), images intermédiaires (`image.intermediates`, codé, jamais rendu), SAE Gemma Scope (v2).
- **Licences** : Lancaster et NRC VAD sont réservés à un usage non commercial / de recherche ; à vérifier avant toute diffusion.

## Critères d'acceptation

| Critère | État |
| --- | --- |
| `all` produit `out.mp4` de bout en bout | ✅ `./run.sh all --config configs/default.yaml --run-id accept-all` → `runs/accept-all/out.mp4` (20 tranches, 72 s, record → render → voice → sound → assemble, un processus par passe) |
| Une image et une voix par tranche, texte ni visible ni audible | ✅ (le texte n'est écrit que dans `text.txt`, jamais rendu) |
| Même graine et même config, même trace | ✅ la trace de `accept-all` est identique au bit près (600 tokens, tokens et lectures) à celle de `p1-nodrug`, produite deux heures plus tôt dans un autre processus |
| Avec / sans drogue, `windows.json` diffère nettement | ✅ mots marins dans 0/73 tranches sans drogue, 63/73 avec α = 4 ; 17/20 avec α = 0,002 |
| Jamais deux modèles en même temps sur le GPU | ✅ chaque passe tourne dans son propre processus, les étapes GPU s'enchaînent |

## Durées mesurées par étape (A6000)

| Étape | Version longue (600 tokens, 73 tranches) | Version 1 min (20 tranches) |
| --- | --- | --- |
| `record` (chargement Gemma ~23 s compris) | 64 s | 43 à 62 s |
| Tranches | ~1 s | ~1 s |
| `render` (Z-Image, chargement compris) | 390 s (≈ 5 s par image) | 120 à 175 s |
| `voice` (Kokoro) | 12 à 30 s | 9 s |
| `sound` (traits + effets + Stable Audio + synthèse) | 615 à 630 s | 180 s |
| `assemble` (par mode) | 150 à 240 s | ~40 s |
| **Total d'une variante complète** | **≈ 20 min** | **≈ 7 min** |

## Commandes pour relancer

Toutes les étapes GPU passent par `./run.sh`, qui tourne hors sandbox. Lancer chaque commande seule, sans `cd … &&` devant.

```bash
# chaîne complète à partir d'une config
./run.sh all --config configs/default.yaml --run-id mon-run [--modes voix mixte sonorisation]

# étape par étape
./run.sh record   --config configs/variants/drug_subtle.yaml --run-id p1-subtil
./run.sh render   --run runs/p1-subtil
./run.sh voice    --run runs/p1-subtil
./run.sh sound    --run runs/p1-subtil --mode mixte      # traits + effets de voix (+ sono si mixte/sonorisation)
./run.sh assemble --run runs/p1-subtil --mode voix|sonorisation|mixte [--raw-voice]

# changer de durée ou de rendu sans relancer le LLM
./run.sh py rewindow --from runs/p1-nodrug --run-id p1-90s --target 90 [--config autre.yaml]

# balayer l'intensité de la drogue (un seul chargement de Gemma)
./run.sh py sweep --config configs/variants/drug_subtle.yaml --alphas 0.001 0.002 0.004 --prefix sweep

# copier des vidéos vers pCloud/Transfert/hack1robo
./run.sh publish runs/<run>/out_mixte.mp4 …

# enchaîner plusieurs étapes (voir scripts/batch*.sh)
./run.sh script scripts/batch4.sh
```

**Configs** : `configs/default.yaml` (base, durée cible 60 s) ; `configs/variants/` contient `drug_subtle` (0,002), `drug_medium` (0,003), `drug_strong` (0,004), `phrase2_subtle`, `phrase3_subtle` et `img_liste`. Une config peut ne contenir que ce qui change : elle hérite de `default.yaml`.

## À faire

- **Révoquer le jeton Hugging Face** (huggingface.co/settings/tokens).
- Écouter le mixte et ajuster `sound.duck_db` et l'équilibre des couches A et B.
- Choisir le registre d'images : figuratif (actuel) ou plus abstrait.
