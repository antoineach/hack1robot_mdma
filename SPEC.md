# Spécification — Lecture, rendu et « drogue » de l'espace intermédiaire d'un LLM

Nov 20, 2026 · @OB

## Objectif

Produire une vidéo (images + voix) qui montre l'intérieur d'un LLM pendant qu'il disserte sur une phrase donnée, et pouvoir « droguer » ce contenu intérieur. Le projet est artistique : on cherche un rendu évocateur, pas une mesure scientifique.

- **Voir** : chaque tranche glissante de tokens produit une image par diffusion, à partir des mots lus dans les couches intermédiaires.
- **Dire** : une voix de synthèse prononce ces mots intérieurs.
- **Biaiser** : on injecte un ou plusieurs concepts dans le résidu des couches intermédiaires pendant la génération.

Principes :

- Le texte produit par le modèle n'est jamais montré ni lu à voix haute. Seul l'intérieur est rendu.
- Le rendu est différé : on enregistre d'abord, on rend ensuite. Le temps réel n'est pas un objectif.
- Méthode de lecture : la Jacobian lens (J-lens) d'Anthropic, avec des lentilles pré-ajustées publiées par Neuronpedia.
- Un résultat présentable doit sortir vite. On privilégie les briques existantes plutôt que l'entraînement.

## Mode autonome — nuit de 7 h

Personne ne pourra répondre pendant environ 7 heures. Ne pose aucune question et n'attends jamais de réponse : décide, note ta décision et continue.

### Règles de décision

- Un choix est déjà fixé dans cette spécification : applique-le.
- Un choix est ouvert et les options coûtent peu : implémente-les toutes derrière une clé de configuration, et produis une variante de chacune à la fin.
- Un choix est ouvert et coûteux : choisis l'option la plus simple qui donne un résultat visible.
- Chaque décision est notée dans `DECISIONS.md` : heure, choix, raison, alternatives écartées.
- Une brique échoue après 2 ou 3 tentatives raisonnables : passe à son repli (tableau des choix techniques). Sans repli, désactive-la, note-le et continue.

### Ordre de travail

Une vidéo complète, même simple, passe avant tout raffinement. Si le temps manque, on coupe par la fin de cette liste.

1. Vérifier que la phase 0 est complète, et la terminer sinon.
2. Passe 1 complète, sans puis avec drogue.
3. **Première vidéo de bout en bout** : images + voix brute. C'est le jalon à atteindre en priorité absolue.
4. Effets de voix sémantiques.
5. Sonorisation.
6. Variantes de fin de nuit.

### Variantes à produire en fin de nuit

Adapter le nombre au temps restant, dans cet ordre :

1. Phrase 1, sans drogue, voix avec effets.
2. Phrase 1, drogue forte, voix avec effets.
3. Phrase 1, sans drogue, sonorisation seule.
4. Phrase 1, drogue forte, mixte (voix + sonorisation).
5. Phrases 2 et 3, avec la configuration jugée la plus réussie.

### Discipline de travail

- Travailler uniquement dans le dossier du projet. Pas de `sudo`, rien de supprimé hors du projet. Si un outil système manque, chercher une alternative installable avec pip (par exemple `imageio-ffmpeg`) et le noter.
- Commit git à chaque jalon.
- Les traitements longs écrivent un journal dans `runs/<id>/log.txt`.
- Tenir `PROGRESS.md` à jour (fait, en cours, prochaine étape) pour pouvoir reprendre après une compaction du contexte.
- Mesurer la durée de chaque étape sur une première exécution, puis planifier les variantes en fonction.

### Rapport du matin

`MORNING_REPORT.md` à la racine du projet contient :

- ce qui fonctionne et ce qui ne fonctionne pas ;
- le chemin de chaque vidéo produite, avec une ligne de description ;
- les décisions importantes (renvoi à `DECISIONS.md`) ;
- les durées mesurées par étape ;
- les commandes pour relancer chaque variante.

### Phase 0 — préparation supervisée, avant la nuit

L'utilisateur suit cette phase via Remote Control et peut répondre aux demandes d'autorisation. Tout ce qui pourrait bloquer la nuit se règle ici. Durée visée : moins d'une heure.

**Côté utilisateur, depuis un navigateur (téléphone compris)**

- [x] Sur huggingface.co, connecté à son compte, ouvrir `google/gemma-3-12b-it` et accepter la licence. Idem pour `stabilityai/stable-audio-open-1.0`.
- [ ] Transmettre le jeton Hugging Face (lecture seule) à Claude Code dans un message séparé, jamais dans SPEC.md. Le révoquer le lendemain.
- [ ] Envoyer cette spécification en Markdown et demander à Claude Code de l'enregistrer sous `SPEC.md`.

**Côté Claude Code, dans l'ordre**

1. Indiquer sa version et son mode de permission actuel.
2. Vérifier le GPU (`nvidia-smi`, `torch.cuda.is_available()`) et l'espace disque. Poids et environnement pèsent environ 80 Go (estimation) : viser au moins 100 Go libres.
3. Système Bluefin (immuable) : aucun paquet système via dnf ou rpm-ostree. Python et ses dépendances dans un environnement virtuel du projet. Outils système (ffmpeg, espeak-ng) via Homebrew, présent sur Bluefin, ou via pip.
4. Enregistrer le jeton avec `hf auth login --token …`. Ne jamais l'écrire dans un fichier du projet, un journal ou un commit.
5. Télécharger tous les poids : Gemma 3 12B-it, J-lens, Z-Image-Turbo, Stable Audio Open, Kokoro, modèle d'embeddings, lexiques.
6. Valider la lecture J-lens (étape 2), puis faire un essai de chaque brique : une image, un fragment de voix avec effets, un clip Stable Audio.
7. Regrouper toutes les commandes longues dans un script unique `run.sh <étape>`, et l'autoriser dans les permissions du projet, y compris son exécution hors sandbox pour le GPU. La session tourne en validation manuelle : seules les règles d'autorisation évitent les demandes. Les écrire dans \`.claude/settings.local.json\`, avec l'accord de l'utilisateur : modifications de fichiers dans le projet, \`./run.sh\` (y compris hors sandbox), git. Ajouter des règles de refus pour \`sudo\` et pour toute suppression hors du projet. Ne jamais charger un modèle avec \`trust\_remote\_code=True\`.
8. Faire un essai complet de \`./run.sh\` et de quelques modifications de fichiers, vérifier qu'aucune demande d'autorisation n'apparaît, puis signaler que tout est prêt.

**Lancement**, envoyé par l'utilisateur depuis Remote Control une fois la phase 0 terminée :

```text
/goal Les critères d'acceptation de SPEC.md sont remplis et MORNING_REPORT.md est écrit, ou 7 heures se sont écoulées depuis ce message
```

## Choix techniques (A6000, 48 Go)

Le LLM est **Gemma 3 12B-it en bf16** et le modèle de diffusion **Z-Image-Turbo**. Les deux passes sont séparées, donc les deux modèles ne sont jamais en VRAM en même temps.

| Rôle | Choix par défaut | Pourquoi | Repli |
| --- | --- | --- | --- |
| LLM qui disserte | `google/gemma-3-12b-it`, bf16 (environ 24 Go de poids) | Bon en français, J-lens pré-ajustée disponible, SAE Gemma Scope 2 disponibles pour plus tard | `Qwen/Qwen3-14B` (J-lens aussi disponible) |
| Lecture de l'intérieur | J-lens pré-ajustée [neuronpedia/jacobian-lens](https://huggingface.co/neuronpedia/jacobian-lens), fichier `gemma-3-12b-it/jlens/Salesforce-wikitext/gemma-3-12b-it_jacobian_lens.pt` | Pas d'ajustement à faire | Ajuster soi-même avec `jlens.fit` (environ 100 prompts suffisent) |
| Code J-lens | [anthropics/jacobian-lens](https://github.com/anthropics/jacobian-lens) (`pip install -e .`) | Implémentation de référence, Apache 2.0 | Lecture manuelle à partir du fichier `.pt` (voir passe 1) |
| Images | `Tongyi-MAI/Z-Image-Turbo` via diffusers : `ZImagePipeline` et `ZImageImg2ImgPipeline` ([doc](https://huggingface.co/docs/diffusers/api/pipelines/z_image)) | 8 étapes, photoréaliste, img2img natif | SDXL-Turbo en img2img |
| Voix | Kokoro, voix française `ff_siwis` | Local, Apache 2.0 | Piper `fr_FR-siwis-medium` |
| Montage | ffmpeg | Fondu entre images, piste audio | — |

Points d'attention :

- La J-lens Neuronpedia a été ajustée sur WikiText en anglais. Les mots intérieurs sortiront souvent en anglais même si la dissertation est en français. On le garde comme texture.
- Les SAE (Gemma Scope 2) ne font pas partie de la version 1. On les ajoutera ensuite pour des concepts composés de plusieurs mots.

## Architecture

&#91;embedded content: architecture · 2 passes, 1 drogue\]

La passe 1 tient le LLM en VRAM et écrit les fichiers du run. La passe 2 les relit, une fois le LLM déchargé, pour produire images, voix et vidéo.

## Passe 1 — Enregistrer l'intérieur

La passe 1 génère la dissertation, lit les couches intermédiaires à chaque token, applique la drogue et écrit une trace sur disque. Elle ne produit aucune image ni aucun son.

### Entrée et génération

1. Entrées : une phrase et un prompt système qui invite le modèle à disserter. Les deux sont configurables.
2. Utiliser le chat template du tokenizer. Gemma n'a pas de rôle système natif : vérifier comment le template l'intègre.
3. Boucle de génération token par token avec cache KV, échantillonnage configurable (température, top-p), graine fixée, `max_new_tokens` configurable.

### Capture

- Des forward hooks sur les blocs décodeurs capturent le résidu en sortie de bloc, uniquement à la position du token qu'on vient de générer.
- Couches lues : la bande « espace de travail », par défaut de 38 % à 92 % de `num_hidden_layers`, intersectée avec `lens["source_layers"]`. Bornes configurables.

### Lecture J-lens

Formule donnée par Neuronpedia pour leurs fichiers, où `J[l]` est une matrice `d_model × d_model` en fp16 et `unembed` est la norme finale du modèle suivie de sa tête LM :

```
logits_l = unembed(h_l @ J[l].T)
```

- Réutiliser exactement la norme finale et `lm_head` du modèle chargé. Faire le calcul en fp32.
- Garder le top-k par couche (k = 50 par défaut) avec les probabilités softmax.

### Filtrage des mots

Dans l'ordre :

1. Ne garder que les tokens qui sont des mots entiers (préfixe « ▁ » sous SentencePiece).
2. Ne garder que les tokens alphabétiques (lettres Unicode, accents compris), d'au moins 3 caractères.
3. Retirer les mots vides français et anglais (listes configurables).
4. Dédoublonner en minuscules et cumuler les scores.
5. Option `exclure_echos` (activée par défaut) : retirer les mots présents dans les N derniers tokens du texte généré, pour ne garder que le non-dit.

### Tranches glissantes

- Score d'un mot à un pas = somme de ses probabilités sur les couches de la bande. Pondération par couche optionnelle.
- Une tranche regroupe W tokens (24 par défaut) et avance de S tokens (8 par défaut). Score d'un mot dans la tranche = somme sur ses pas, avec une décroissance optionnelle pour les pas les plus anciens.
- Pour chaque tranche, garder les M meilleurs mots (12 par défaut) avec leurs poids normalisés, et noter les mots nouveaux par rapport à la tranche précédente.

### Drogue (steering)

- Une drogue = une liste de mots-concepts, chacun avec une intensité α, une plage de couches et un profil temporel : constant, rampe, pulsation ou sinusoïde.
- Direction d'un mot t à la couche l : `v = J[l].T @ (g ⊙ W_U[t])`, normalisée. `W_U[t]` est la ligne de la tête LM et `g` le gain de la norme finale (pour Gemma, `1 + weight`). C'est la direction qui fait monter le mot dans la lecture J-lens.
- À chaque position générée (et en option sur le prompt), ajouter `α(t) · ‖h‖ · v` au résidu des couches choisies.
- Si un mot fait plusieurs tokens : prévenir et utiliser la moyenne de leurs directions.
- Variantes pour la version 2 : bruit aléatoire dans le J-space (combinaison aléatoire de directions), échange de deux concepts (retirer A, ajouter B).
- L'état de la drogue est enregistré à chaque pas dans la trace.

## Passe 2 — Rendu image, voix et vidéo

La passe 2 lit la trace et produit une image et un fragment de voix par tranche, puis les monte en vidéo. Elle tourne dans un processus séparé, une fois le LLM déchargé.

### Images (Z-Image-Turbo)

1. Prompt d'une tranche = ses mots classés par poids, séparés par des virgules, suivis d'un suffixe de style fixe et configurable (direction artistique). Z-Image n'a pas de syntaxe de pondération : l'ordre porte le poids, avec en option une répétition des 2 ou 3 premiers mots.
2. Première tranche : `ZImagePipeline`, 8 étapes, `guidance_scale=0.0`, graine fixée, résolution configurable (16:9 par défaut).
3. Tranches suivantes : `ZImageImg2ImgPipeline` à partir de l'image précédente, avec une intensité `strength` configurable (0,55 par défaut). Les deux pipelines partagent leurs composants (encodeur de texte, VAE, transformer) pour ne charger les poids qu'une fois.
4. Option `reset_tous_les` : tous les K tranches, repartir d'un text-to-image pur pour éviter que l'image dégénère.
5. Option `intermediaires` : entre deux tranches, générer n images img2img à intensité faible en interpolant les prompts, pour un mouvement plus fluide.

### Voix (Kokoro)

- Pour chaque tranche, prononcer les mots nouveaux (par défaut) ou les 3 premiers mots, séparés par de courts silences.
- Voix par défaut `ff_siwis`. Option : prononcer les mots anglais avec une voix anglaise de Kokoro, via une détection de langue simple.
- Vitesse et durée des silences configurables. Effets (écho, réverbération) en option, appliqués par ffmpeg.

### Montage (ffmpeg)

- Durée d'une tranche à l'écran = la plus grande valeur entre la durée de sa voix et une durée minimale configurable.
- Fondu enchaîné (`xfade`) entre images consécutives, audio concaténé et calé sur les images.
- Sortie MP4 H.264 en 1080p, encodée en `-preset veryfast`.
- Le texte de la dissertation n'apparaît jamais, ni à l'écran ni dans l'audio.

## Son — sonorisation et effets de voix

Le son traduit ce que les mots évoquent, pas seulement ce qu'ils disent. Chaque mot reçoit d'abord une fiche de traits ; ces traits pilotent ensuite la sonorisation et les effets de voix. Trois modes : `voix`, `sonorisation`, `mixte`.

### 1. Fiche de traits par mot

Calculée une fois par mot et mise en cache dans `features.json`.

| Source | Traits | Remarque |
| --- | --- | --- |
| [Lancaster Sensorimotor Norms](https://www.lancaster.ac.uk/psychology/lsnorms/) | Force perçue par modalité : ouïe, vue, toucher, odorat, goût, intéroception | Anglais, environ 40 000 mots. Licence non commerciale à vérifier |
| Lexique NRC VAD | Valence, éveil, dominance | Anglais. Licence à vérifier |
| Normes de concrétude (Brysbaert) | Concret / abstrait | Anglais |
| Projection d'embeddings (repli) | Les mêmes axes, définis par des paires de mots ancres (joyeux/triste, calme/agité, concret/abstrait, lumineux/sombre, chaud/froid, doux/rugueux) | Modèle d'embedding multilingue. Couvre les mots français et les mots absents des lexiques |
| Trace du LLM | Couche d'origine moyenne, score J-lens, nouveauté, entropie de la lecture, intensité de la drogue à ce pas | Vient de `trace.jsonl` |

Si un lexique ne peut pas être téléchargé, le repli par embeddings suffit. Tous les traits sont normalisés entre 0 et 1.

### 2. Sonorisation

Deux couches superposables, chacune activable séparément.

**Couche A — texture générative (évocation concrète).** Stable Audio Open 1.0 génère un clip par tranche à partir des mots de la tranche et d'un suffixe fixe (« ambient texture, drone, field recording »). Le modèle produit jusqu'à 47 s de stéréo en 44,1 kHz et préfère les prompts en anglais, ce qui convient aux mots J-lens. Fondu enchaîné entre clips. Repli : Stable Audio 3 small, si ses poids sont disponibles.

**Couche B — synthèse paramétrique (évocation abstraite).** Un drone synthétisé en Python, une voix de synthèse par mot de la tranche :

| Trait | Paramètre sonore |
| --- | --- |
| Valence | Harmonie : intervalles consonants (quinte, tierce majeure) si positive, dissonants (seconde mineure, triton) si négative |
| Éveil | Vitesse de pulsation, densité de grains, vitesse du vibrato |
| Dominance | Registre grave et volume |
| Concrétude | Bruit filtré si concret, sinus purs si abstrait |
| Ouïe / vue | Part de bruit réaliste / brillance (harmoniques aigus) |
| Toucher | Rugosité (modulation d'amplitude rapide) |
| Odorat / goût | Flou (chorus, désaccord léger) |
| Intéroception | Battement grave et lent, façon pouls |
| Couche d'origine | Hauteur et position stéréo |
| Score J-lens | Amplitude de la voix du mot |
| Nouveauté | Attaque percussive à l'apparition |
| Drogue α(t) | Désaccord progressif, modulation en anneau, saturation |

Entre deux tranches, les voix se transforment progressivement au lieu de couper. Les tables de correspondance sont dans la configuration pour pouvoir être modifiées.

### 3. Effets de voix (coloration sémantique)

Les effets sont appliqués mot par mot avec [pedalboard](https://github.com/spotify/pedalboard) (Spotify, GPL v3). La bibliothèque fournit chorus, distorsion, phaser, compresseur, filtres, convolution, délai, réverbération, pitch shift et bitcrush.

| Trait | Effet | Rendu |
| --- | --- | --- |
| Valence négative | Pitch shift vers le bas (−1 à −4 demi-tons), passe-bas | Voix assombrie |
| Valence positive | Chorus léger, plus de brillance | Voix claire, ouverte |
| Éveil élevé | Compression forte, légère distorsion, délai court | Voix tendue |
| Éveil faible | Débit Kokoro ralenti, longue réverbération | Voix lente, flottante |
| Abstrait | Très grande réverbération, signal très mouillé | Voix lointaine |
| Concret | Signal sec | Voix proche |
| Score J-lens faible | Gain bas, passe-bas, bitcrush ou rééchantillonnage | Murmure, voix fantôme |
| Mot déjà entendu | Délai avec réinjection | Écho, mémoire |
| Couche d'origine | Panoramique et distance | La profondeur devient de l'espace |
| Drogue active | Pitch oscillant, phaser, distorsion proportionnels à α(t) | Voix « droguée » |

Options :

- **Polyphonie** : les mots d'une même tranche se chevauchent, avec plusieurs voix Kokoro, chacune à un volume proportionnel à son poids.
- **Mixte** : la sonorisation reste en fond, et son volume baisse légèrement quand la voix parle.

### Fichiers ajoutés

- `features.json` : fiche de traits par mot.
- `audio/voice_fx_NNNN.wav`, `audio/sono_NNNN.wav` : voix avec effets et sonorisation, par tranche.
- `out_voix.mp4`, `out_sono.mp4`, `out_mixte.mp4` selon les modes rendus.

## Fichiers, configuration et commandes

Chaque exécution écrit tout dans `runs/<run_id>/`, et chaque étape relit les fichiers de l'étape précédente. On peut donc relancer le rendu sans régénérer le texte.

| Fichier | Contenu |
| --- | --- |
| `config.yaml` | Copie de la configuration utilisée |
| `text.txt` | Dissertation générée, pour le débogage seulement, jamais rendue |
| `trace.jsonl` | Une ligne par token généré : pas, id du token, top-k filtré par couche avec scores, état de la drogue |
| `windows.json` | Une entrée par tranche : pas de début et de fin, mots avec poids, mots nouveaux, prompt image |
| `frames/NNNN.png` | Une image par tranche, plus les intermédiaires éventuels |
| `audio/NNNN.wav` | Voix d'une tranche |
| `out.mp4` | Vidéo finale |

Exemple de configuration :

```yaml
model: google/gemma-3-12b-it
lens:
  repo: neuronpedia/jacobian-lens
  file: gemma-3-12b-it/jlens/Salesforce-wikitext/gemma-3-12b-it_jacobian_lens.pt
input:
  phrases:
    - "Le silence est-il une forme de langage ?"
    - "Que reste-t-il d'un souvenir quand on l'oublie ?"
    - "Une machine peut-elle rêver ?"
  system: "Tu dissertes longuement et librement sur le sujet donné."
generation: {max_new_tokens: 600, temperature: 0.8, top_p: 0.95, seed: 1}
readout:
  band: [0.38, 0.92]
  top_k: 50
  min_len: 3
  exclure_echos: {enabled: true, last_n_tokens: 32}
windows: {size: 24, stride: 8, top_m: 12, decay: 0.0}
drugs:
  - {word: ocean, alpha: 4.0, band: [0.45, 0.70], profile: ramp, start: 100, end: 400}
image:
  model: Tongyi-MAI/Z-Image-Turbo
  size: [1344, 768]
  steps: 8
  strength: 0.55
  reset_every: 0
  intermediates: 0
  style: "peinture onirique, lumière diffuse"
voice: {engine: kokoro, voice: ff_siwis, speed: 0.9, mode: new_words, polyphony: false}
sound:
  mode: voix            # voix | sonorisation | mixte
  features: {lexicons: [lancaster, nrc_vad, concreteness], fallback: embeddings}
  voice_fx: {enabled: true, engine: pedalboard}
  sono:
    layer_a: {enabled: true, model: stabilityai/stable-audio-open-1.0, suffix: "ambient texture, drone, field recording"}
    layer_b: {enabled: true, sample_rate: 44100}
  duck_db: -6
video: {fps: 30, min_duration_s: 2.0, crossfade_s: 0.8}
```

Commandes (à exposer en CLI) :

- `record --config c.yaml` : passe 1, écrit `trace.jsonl`, `windows.json`, `text.txt`.
- `render --run runs/<id>` : images.
- `voice --run runs/<id>` : voix.
- `assemble --run runs/<id>` : vidéo.
- `all --config c.yaml` : les quatre à la suite, chaque passe dans son propre processus pour libérer la VRAM.

## Étapes, critères d'acceptation et points à vérifier

On avance par étapes courtes, et chacune doit marcher avant de passer à la suivante. Les premiers résultats visibles arrivent dès l'étape 5.

### Étapes

1. **Environnement** : PyTorch avec CUDA, transformers, diffusers récent (les pipelines Z-Image sont récents), `jacobian-lens`, Kokoro, ffmpeg. Acceptation de la licence Gemma sur Hugging Face.
2. **Validation de la lecture** : sur un prompt fixe, comparer la lecture manuelle (formule Neuronpedia) avec `lens.apply` de `jlens`. Les top-5 doivent coïncider couche par couche. Contrôle complémentaire : à la dernière couche, la lecture doit retrouver les logits du modèle.
3. **`record` sans drogue** : inspecter `windows.json` sur une phrase de test. Les mots doivent être lisibles après filtrage, pas seulement des fragments.
4. **`record` avec drogue** : avec un concept fort (α élevé), le mot doit monter dans les lectures et le texte doit dériver. Ensuite, baisser α jusqu'à un effet subtil.
5. **`render`** : d'abord en text-to-image seul, puis avec la chaîne img2img.
6. **`voice` puis `assemble`**.

Après l'étape 6 : effets de voix, sonorisation, puis variantes, dans l'ordre de la section Mode autonome.

### Critères d'acceptation

- `all` produit `out.mp4` de bout en bout à partir d'une phrase et d'un fichier de configuration.
- Chaque tranche a une image et une voix. Le texte généré n'est ni visible ni audible.
- À graine et configuration identiques, la passe 1 donne la même trace.
- Avec et sans drogue, `windows.json` diffère nettement sur le concept injecté.
- Les deux modèles ne sont jamais chargés en même temps sur le GPU.

### Points à vérifier pendant le développement

- [ ] Convention d'indices de couches du fichier de lentille (`source_layers`) : sortie de bloc ou entrée de bloc, et décalage éventuel par rapport aux hooks.
- [ ] Traitement du prompt système par le chat template de Gemma 3.
- [ ] Composition exacte de `unembed` pour Gemma 3 (norme finale, tête liée aux embeddings, éventuel softcapping).
- [ ] Dépendances de phonétisation de Kokoro pour le français (espeak-ng).
- [ ] Comportement de Z-Image-Turbo avec des prompts faits uniquement de listes de mots.

## Sources

- [Verbalizable Representations Form a Global Workspace in Language Models](https://transformer-circuits.pub/2026/workspace/index.html) (Anthropic, 2026)
- [anthropics/jacobian-lens](https://github.com/anthropics/jacobian-lens)
- [neuronpedia/jacobian-lens](https://huggingface.co/neuronpedia/jacobian-lens) (lentilles pré-ajustées)
- [Documentation diffusers Z-Image](https://huggingface.co/docs/diffusers/api/pipelines/z_image)
- [Kokoro, voix ff\_siwis](https://offlinetts.com/voice/ff-siwis/)

* [Stable Audio Open](https://stability.ai/news/introducing-stable-audio-open) (Stability AI)
* [Lancaster Sensorimotor Norms](https://www.lancaster.ac.uk/psychology/lsnorms/)
* [pedalboard](https://github.com/spotify/pedalboard) (Spotify)
* [Claude Code en mode non interactif](https://code.claude.com/docs/en/headless.md) et [/goal](https://code.claude.com/docs/en/goal.md)
