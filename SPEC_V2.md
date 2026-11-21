# Spécification v2 — Interface web, environnements et drogues

Nov 21, 2026 · @OB

## Objectif

La v2 permet de lancer une « prise » depuis un téléphone : on choisit une question, un environnement, une drogue, une durée et un nombre de voix, puis on regarde la vidéo produite. Elle s'appuie entièrement sur le code de la v1 (`introspect/`, `run.sh`, `configs/`), qui fonctionne et ne doit pas être réécrit.

Ce qui change :

- **Interface web** Gradio, accessible par un lien public protégé par mot de passe.
- **Environnements** : une liste de situations qui remplacent le prompt système, avec en option leur influence sur le style des images et du son.
- **Drogues** : un catalogue de 11 drogues. Chacune est une suite de phases, avec ses mots-clés tirés au hasard et sa propre intensité. Ce catalogue remplace la drogue à un seul mot de la v1.
- **Voix en parallèle** : de 1 à 4 voix, la voix française plus des voix anglaises.

Ce qui reste tel quel : la chaîne `record → render → voice → sound → assemble`, le gabarit d'image « métaphore visuelle », les effets sémantiques et la sonorisation. L'intensité reste dans la plage calibrée cette nuit : α entre 0,001 (à peine perceptible) et 0,005 (texte qui se défait).

## Interface web (Gradio)

Une application Gradio en une seule colonne, pensée pour un téléphone, lancée par `./run.sh web` (fichier `introspect/webapp.py`). Elle pilote la chaîne existante. Un seul rendu à la fois sur le GPU.

### Accès

- `launch(share=True, auth=(utilisateur, mot_de_passe), show_api=False)`. Le lien public est en `*.gradio.live` et [expire au bout de 72 heures](https://www.gradio.app/3.50.2/guides/sharing-your-app).
- Mot de passe : généré aléatoirement au premier lancement, stocké hors du dépôt dans `~/.config/hack1robo/web_auth`, jamais commité. Claude Code le communique une fois à l'utilisateur par Remote Control.
- À chaque démarrage, écrire le nouveau lien (sans le mot de passe) dans `~/pCloudDrive/Transfert/hack1robo/lien_web.txt`, pour le retrouver depuis le téléphone.
- Service permanent : un service utilisateur systemd (`systemctl --user`) qui redémarre en cas d'erreur, et un timer qui le relance toutes les 48 heures pour renouveler le lien avant son expiration. Pour qu'il survive à une déconnexion ou à un redémarrage, lancer `loginctl enable-linger` sans nom d'utilisateur : pour soi-même, cela ne demande normalement pas de droits administrateur. Ne jamais utiliser `sudo` ni demander le mot de passe de la machine. Si la commande est refusée, s'en passer : le service tourne tant que la session de l'utilisateur reste ouverte. Le noter dans le rapport.
- Le tunnel Gradio a besoin d'un accès réseau sortant : le serveur tourne hors sandbox, via `run.sh`.

### Sécurité

Le lien étant public, l'application ne doit rien exposer d'autre que ses paramètres et ses vidéos.

- La question est du texte libre (300 caractères au plus). Elle est écrite dans un fichier de configuration par Python, et n'est jamais insérée dans une commande shell.
- Sous-processus lancés avec une liste d'arguments, jamais avec `shell=True`.
- Les listes (environnement, drogue, mode son) sont vérifiées par rapport aux catalogues.
- Gradio ne sert que les fichiers de `runs/` (`allowed_paths`).
- File d'attente limitée à 5 demandes.

### Écran

**Formulaire**, de haut en bas :

1. Question : champ libre, avec un menu de questions déjà utilisées.
2. Environnement : liste des noms seuls, plus « aucun ». Case « l'environnement colore aussi les images et le son ».
3. Drogue : liste des 11 drogues, plus « aucune ». Curseur « intensité globale » de 0,5 à 1,5 (1 par défaut), qui multiplie les α des phases.
4. Durée : curseur de 30 s à 5 min, par pas de 15 s. La durée réelle peut dépasser.
5. Nombre de voix : 1 à 4.
6. Mode son : voix, sonorisation ou mixte (mixte par défaut).
7. Bouton « Lancer », avec une estimation du temps de calcul (environ 7 min par minute de vidéo, d'après les mesures de la nuit).

**Suivi** : position dans la file, étape en cours, puis les images qui s'ajoutent au fur et à mesure du rendu (lecture de `runs/<id>/frames/` toutes les quelques secondes). À la fin, le lecteur vidéo. Un bouton « Annuler » arrête le rendu en cours.

**Galerie** : les runs passés, les plus récents en haut, avec leurs paramètres résumés sur une ligne et la vidéo. Les vidéos de la v1 y figurent aussi.

Chaque vidéo terminée est aussi copiée dans `~/pCloudDrive/Transfert/hack1robo/`, comme pendant la nuit.

## Paramètres

Chaque demande venue de l'interface devient un fichier `runs/<id>/request.yaml`. Il ne contient que ce qui change et hérite de `configs/default.yaml`, avec le mécanisme d'héritage qui existe déjà.

| Paramètre | Clé de configuration | Effet |
| --- | --- | --- |
| Question | `input.phrase` | Texte sur lequel le modèle disserte |
| Environnement | `input.environment` | Remplace `input.system` par le prompt de l'environnement |
| Style d'environnement | `input.environment_style` (oui/non) | Ajoute le style de l'environnement aux images et à la sonorisation |
| Drogue | `drug.name` | Charge la drogue depuis le catalogue `configs/drugs.yaml` |
| Intensité globale | `drug.intensity` | Multiplie les α de toutes les phases |
| Durée | `video.target_duration_s` | Durée visée de la vidéo, et donc de la prise entière |
| Nombre de voix | `voice.n_voices` | De 1 à 4 voix en parallèle |
| Mode son | `sound.mode` | voix, sonorisation ou mixte |

**Durée et longueur du texte.** La prise dure toute la vidéo : les phases de la drogue sont donc réparties sur les tokens générés. Le nombre de tokens doit suffire pour la durée demandée :

- `max_new_tokens = pas × nombre de tranches + taille de tranche`, borné entre 200 et 1 500 tokens. Le nombre de tranches est calculé par la logique `target_duration_s` déjà en place.
- Empêcher la fin de génération (token de fin) avant ce nombre de tokens, pour que la prise ne s'arrête pas en cours de route.
- Les phases sont exprimées en fraction de la prise (de 0 à 1) et converties en pas de tokens au moment du `record`.

## Environnements

Un environnement est une situation décrite en une phrase courte, pour laisser place à la surprise. Catalogue : `configs/environments.yaml`. L'interface n'affiche que le nom.

Prompt système = phrase de l'environnement + « Tu dissertes longuement et librement sur le sujet donné. ». Il ne mentionne jamais la drogue, qui n'agit que par le biais des couches intermédiaires.

Quand l'option de style est cochée, le style image s'ajoute à `image.style`, et la texture sonore remplace le suffixe de la couche A de la sonorisation (Stable Audio, prompts en anglais).

| Nom affiché | Phrase du prompt système | Style image | Texture sonore |
| --- | --- | --- | --- |
| Rave | Il est 4 h, tu es au fond d'un entrepôt où joue une rave. | strobe lights, concrete, haze, neon | distant techno through concrete walls, crowd |
| Mariage | Tu es à un mariage, entre le dessert et la première danse. | warm string lights, white tablecloths, golden hour | reception murmur, clinking glasses, distant accordion |
| Enterrement | Tu es à un enterrement, au bord de la tombe. | grey sky, black coats, wet cemetery | wind, muffled crowd, distant bell |
| Open space | C'est lundi, 9 h 03, dans un open space. | fluorescent office light, cubicles, beige | air conditioning hum, keyboards, phone ringing |
| Forêt | Tu es seul dans une forêt, la nuit. | moonlit forest, fog, dark trees | night forest, owls, wind in leaves |
| Urgences | Tu attends depuis des heures aux urgences. | hospital corridor, neon, plastic chairs | hospital hum, beeping monitors, distant announcements |
| Plage | Tu es sur une plage, à l'aube. | pastel dawn, wet sand, mist | gentle waves, seagulls, morning wind |
| Garde à vue | Tu es en garde à vue depuis la veille. | concrete cell, harsh light, bars | metal doors, echoing corridor, fluorescent buzz |
| Église | Tu es assis au fond d'une église vide. | stained glass light, stone, candles | stone reverberation, distant organ drone, footsteps |
| Chambre | Tu es dans ta chambre d'adolescent, porte fermée. | posters, desk lamp, cluttered bedroom at night | muffled music, rain on the window |

Avec « aucun », on garde le prompt système de la v1.

## Drogues

Chaque drogue est une suite de phases calées sur la durée de la vidéo : la prise commence au premier token et finit au dernier. Chaque phase a son niveau d'intensité et sa liste de mots-clés, dans lesquels on tire au hasard pendant la génération. Catalogue : `configs/drugs.yaml`.

### Mécanique

1. **Phase courante** : au pas t sur T tokens, la phase est celle qui couvre t / T.
2. **Intensité** : α(t) = α du niveau de la phase × intensité globale, plafonné à 0,006. Transition lissée entre deux phases sur 5 % de la prise, pour éviter les sauts.
3. **Tirage** : tous les 12 tokens, tirer 3 mots au hasard dans la liste de la phase courante, en évitant ceux du tirage précédent. Direction injectée = somme normalisée des directions J-lens des 3 mots (même formule que la v1).
4. **Couches** : plage calibrée \[0,45 ; 0,70\], comme la nuit dernière.
5. **Hasard reproductible** : tirage initialisé par la graine du run. Les mots tirés à chaque pas sont enregistrés dans `trace.jsonl` avec α et le nom de la phase.

Niveaux d'intensité (à vérifier avec `sweep` sur 2 ou 3 drogues, et à ajuster si le texte s'effondre trop tôt) :

| Niveau | α | Effet attendu |
| --- | --- | --- |
| 0 | 0 | Sobre |
| 1 | 0,0015 | À peine perceptible |
| 2 | 0,0022 | Glissements |
| 3 | 0,0030 | Dérive nette |
| 4 | 0,0040 | Texte qui se défait |

### Mots-clés

Les listes ci-dessous sont des amorces d'une dizaine de mots. Claude Code les étend à 30 à 50 mots par phase, en restant dans le registre de l'expérience vécue : humeur, perceptions, corps, pensées, images.

- Mots anglais : la J-lens lit surtout de l'anglais.
- De préférence des mots qui font un seul token dans le tokenizer de Gemma (« ▁mot »). Les mots en plusieurs tokens sont écartés ou moyennés comme en v1, et listés dans le journal.
- Pas de noms de personnes, pas de marques.

| Drogue | Phase | Part de la prise | Niveau | Mots-clés d'amorce |
| --- | --- | --- | --- | --- |
| Alcool | Désinhibition | 0–25 % | 2 | laugh, warm, bold, chatty, flirt, cheers, loose, friends, glow, toast |
| Alcool | Euphorie | 25–50 % | 3 | dance, sing, shout, love, wild, party, spin, brave, hug, joke |
| Alcool | Ivresse lourde | 50–75 % | 4 | stumble, blur, sway, slur, heavy, nausea, fall, fog, clumsy, dizzy |
| Alcool | Gueule de bois | 75–100 % | 2 | regret, headache, shame, thirst, grey, empty, tired, sorry, silence, sick |
| Cannabis | Montée | 0–15 % | 2 | tingle, smile, soft, slow, warm, curious, float, hazy, calm, giggle |
| Cannabis | Fous rires | 15–45 % | 3 | laugh, funny, absurd, silly, cartoon, hungry, snack, colors, music, wonder |
| Cannabis | Lenteur | 45–80 % | 3 | couch, drift, sticky, time, cosmic, deep, sleepy, honey, melt, slow |
| Cannabis | Paranoïa, somnolence | 80–100 % | 2 | watched, door, suspicious, heartbeat, mistake, whisper, nervous, hide, sleep, dark |
| Cocaïne | Rush | 0–8 % | 4 | sharp, bright, electric, fast, ice, spark, crisp, rush, alert, clean |
| Cocaïne | Toute-puissance | 8–30 % | 4 | king, genius, power, win, money, talk, control, perfect, invincible, gold |
| Cocaïne | Chute | 30–45 % | 3 | crash, cold, empty, grey, sweat, falling, hollow, nervous, dark, shiver |
| Cocaïne | Manque, paranoïa | 45–100 % | 2 | more, again, need, window, footsteps, mirror, watch, alone, hunger, dawn |
| Amphétamines | Montée | 0–15 % | 2 | awake, focus, sharp, quick, ready, buzz, clear, eager, bright, alert |
| Amphétamines | Énergie | 15–55 % | 3 | run, build, list, plan, endless, motor, drive, task, engine, tireless |
| Amphétamines | Logorrhée, obsession | 55–80 % | 4 | talk, again, detail, count, sort, repeat, theory, map, wire, pattern |
| Amphétamines | Épuisement | 80–100 % | 2 | drained, ache, hollow, grey, insomnia, dust, brittle, irritable, empty, numb |
| MDMA | Montée | 0–15 % | 2 | shiver, chills, nausea, wave, rising, tingling, butterflies, pulse, flushed, open |
| MDMA | Amour, fusion | 15–55 % | 4 | love, hug, together, music, everyone, touch, soft, heart, glow, beautiful |
| MDMA | Descente | 55–75 % | 2 | tired, fading, quiet, thirsty, cold, ending, sweat, grey, tender, slow |
| MDMA | Contrecoup | 75–100 % | 3 | sad, empty, lonely, tears, Tuesday, hollow, dull, gloom, fragile, numb |
| LSD | Montée | 0–15 % | 2 | shimmer, breathing, patterns, giggle, strange, vivid, ripple, odd, electric, unfold |
| LSD | Pic | 15–45 % | 4 | fractal, kaleidoscope, cosmos, infinite, melt, geometry, colors, ego, dissolve, prism |
| LSD | Plateau | 45–80 % | 3 | universe, meaning, connection, nature, time, mirror, symbol, wisdom, wonder, eternity |
| LSD | Retour | 80–100 % | 1 | tired, gentle, afterglow, sunrise, quiet, home, grounded, calm, ordinary, soft |
| Champignons | Malaise de montée | 0–15 % | 2 | nausea, yawn, cold, uneasy, stomach, earthy, heavy, shiver, waiting, strange |
| Champignons | Pic | 15–50 % | 4 | forest, moss, roots, breathing, alive, spiral, laughter, giant, green, trees |
| Champignons | Introspection | 50–80 % | 3 | childhood, mother, tears, forgive, truth, soul, memory, past, humble, death |
| Champignons | Redescente | 80–100 % | 1 | rain, soil, gratitude, rest, soft, quiet, sleep, home, clean, gentle |
| DMT | Sobre | 0–10 % | 0 | — |
| DMT | Décollage | 10–20 % | 4 | rocket, tunnel, roar, buzzing, launch, vibration, tearing, speed, explode, light |
| DMT | Percée | 20–60 % | 4 | entities, beings, palace, jester, machine, elves, temple, alien, hyperspace, jewels |
| DMT | Retour | 60–100 % | 1 | falling, body, ordinary, laugh, impossible, gone, echo, dream, stunned, return |
| Kétamine | Montée | 0–15 % | 2 | numb, heavy, distant, slow, rubber, floating, muffled, wobble, foggy, quiet |
| Kétamine | Dissociation | 15–65 % | 4 | void, hole, detached, nowhere, machine, pixels, outside, dimension, nothing, observer |
| Kétamine | Retour | 65–100 % | 2 | confused, wobbly, robot, blank, clumsy, gravity, reboot, words, strange, slow |
| Héroïne | Rush | 0–10 % | 4 | warm, wave, bliss, honey, melt, rush, heavy, glow, sigh, velvet |
| Héroïne | Cocon | 10–55 % | 3 | cocoon, blanket, safe, womb, soft, nothing, peace, cushion, sleepy, cotton |
| Héroïne | Torpeur | 55–80 % | 2 | nod, drift, dream, sink, still, slow, fog, silence, drowsy, dim |
| Héroïne | Manque | 80–100 % | 3 | cold, ache, sweat, crawling, need, restless, shiver, pain, sick, craving |
| Datura | Confusion | 0–20 % | 2 | thirsty, blurry, dry, heat, lost, stranger, confused, flushed, muttering, cigarette |
| Datura | Délire | 20–65 % | 4 | spiders, shadows, voices, ghosts, phantom, conversation, invisible, crawling, smoke, strangers |
| Datura | Cauchemar | 65–90 % | 4 | terror, darkness, trapped, insects, screaming, demons, walls, endless, chase, coffin |
| Datura | Amnésie | 90–100 % | 1 | blank, missing, nothing, gap, erased, waking, forgotten, hospital, morning, silence |

Format d'une entrée du catalogue :

```yaml
alcool:
  label: Alcool
  phases:
    - {name: Désinhibition, start: 0.00, end: 0.25, level: 2, words: [laugh, warm, bold, ...]}
    - {name: Euphorie, start: 0.25, end: 0.50, level: 3, words: [dance, sing, shout, ...]}
```

## Voix en parallèle

Plusieurs voix lisent chacune leur part des mots, en décalé. Plus de mots intérieurs sont donc entendus. Le respect exact de la durée n'a pas d'importance.

| Voix | Voix Kokoro | Langue | Panoramique de base |
| --- | --- | --- | --- |
| 1 | `ff_siwis` | Français | Centre |
| 2 | `af_heart` | Anglais américain, femme | Gauche (−0,5) |
| 3 | `am_michael` | Anglais américain, homme | Droite (+0,5) |
| 4 | `bm_george` | Anglais britannique, homme | Gauche (−0,25) |

**Répartition des mots**

- Avec N voix, chaque tranche fournit jusqu'à N fois plus de mots à dire : les mots nouveaux d'abord, puis les plus forts.
- Les mots anglais vont aux voix anglaises et les mots français à `ff_siwis`, avec la détection de langue déjà codée (`voice.english_voice`). Le reste est réparti à tour de rôle, par ordre de poids.
- Avec une seule voix, `ff_siwis` lit tout, comme en v1.

**Fabrication et placement**

1. Chaque voix est une piste à part. Tous les fragments sont générés indépendamment, si possible en parallèle, avec les effets sémantiques mot par mot de la v1.
2. Placement a posteriori : le fragment de la voix k pour la tranche i démarre au début de la tranche, décalé de k × (durée de tranche / N). Si la voix parle encore, son fragment suivant attend qu'elle ait fini : une voix ne se chevauche jamais elle-même. Les voix peuvent déborder sur les images suivantes.
3. Le panoramique de la voix s'ajoute à celui qui vient de la couche d'origine du mot, réduit de moitié.
4. En mode mixte, la sonorisation baisse sous l'ensemble des voix (`sound.duck_db`).
5. La dernière image reste à l'écran jusqu'à la fin de la dernière voix, plus 1 seconde de résonance.

## Mode de travail, étapes et critères d'acceptation

Les règles de la v1 s'appliquent : décider plutôt qu'attendre, noter chaque décision dans `DECISIONS.md`, commit git à chaque jalon, et tenir `PROGRESS.md` à jour. Si l'utilisateur est présent par Remote Control, on peut lui poser une question, mais sans bloquer en attendant sa réponse. Toute nouvelle autorisation nécessaire (service systemd, règle de permission) est demandée pendant qu'il est là.

### Étapes

1. **Catalogues** : `configs/environments.yaml` et `configs/drugs.yaml`, avec les listes de mots étendues. Le contrôle de tokenisation va dans `runs/setup/drug_tokens.json` : mots gardés, écartés, moyennés.
2. **Moteur de drogue** dans `record` : phases, transitions, tirages, nombre de tokens calculé à partir de la durée, blocage du token de fin. Faire un `sweep` sur l'alcool, le LSD et la cocaïne pour vérifier les niveaux, et ajuster si besoin.
3. **Voix en parallèle** (1 à 4).
4. **Ligne de commande** : `./run.sh all --config runs/<id>/request.yaml` fonctionne avec les nouvelles clés.
5. **Interface** : d'abord en local, puis avec le lien public et le mot de passe, puis en service permanent, avec le lien écrit dans pCloud.
6. **Démonstration** : trois vidéos d'une minute lancées depuis l'interface. MDMA et Rave, Datura et Forêt, Héroïne et Église, avec 1, 2 et 4 voix.

### Critères d'acceptation

- Depuis un téléphone : connexion avec le mot de passe, lancement, images qui s'affichent pendant le rendu, vidéo lisible à la fin.
- Chacune des 11 drogues produit une vidéo de 30 s sans erreur. Dans `trace.jsonl`, les phases se suivent dans le bon ordre, avec leurs mots tirés.
- Avec 4 voix, les quatre voix s'entendent, et la dernière image reste jusqu'à la fin de la dernière.
- L'option de style d'environnement change bien le prompt d'image et la texture sonore.
- Une question contenant des guillemets, un point-virgule ou `; rm -rf ~` est traitée comme du texte ordinaire.
- Après un arrêt forcé du serveur, le service redémarre et le nouveau lien apparaît dans `lien_web.txt`.
- `V2_REPORT.md` contient : comment accéder à l'interface, les durées mesurées, les vidéos de démonstration et ce qui reste à faire. Le mot de passe n'y figure pas : il est donné à l'utilisateur par Remote Control.

## Sources

- [Gradio : partager une application](https://www.gradio.app/3.50.2/guides/sharing-your-app) (lien public, expiration, authentification)
- [Voix Kokoro-82M](https://huggingface.co/onnx-community/Kokoro-82M-v1.0-ONNX-timestamped)
- [Spécification v1](https://claude.ai/artifact/T597WNT4MSnfrzrH6T8zCg)
