"""Mots vides français et anglais (listes compactes, complétables par la config)."""

FR = set("""
alors au aucun aussi autre autres aux avec avoir bon car ce cela celle celles celui ces cet cette ceux chaque ci comme comment dans
de des donc dont du elle elles en encore entre est et étaient était étant été être eux fait faire fois font hors ici il ils je
juste la le les leur leurs lui là ma mais me même mes moi mon ne ni nos notre nous on ont ou où par parce pas peu peut plus pour
pourquoi quand que quel quelle quelles quels qui sa sans se ses seulement si sien son sont sous soi sur ta tandis te tes toi ton
tous tout toute toutes très tu un une vos votre vous vu ça ainsi après avant bien cas cela chez dès déjà depuis doit donc dont
elle enfin ensuite est-ce etc jamais leur lors mieux moins non nul parfois peut-être plusieurs pourtant puis quelque quoi sera
seront serait soit tant toujours trop vers voici voilà avez avons aurait sommes êtes suis sera sont ceci celui-ci autant
""".split())

EN = set("""
about above after again against all also although always among and any are aren around because been before being below between
both but can cannot could did does doing down during each either else even ever every few for from further had has have having
her here hers herself him himself his how however into its itself just least less like may might more most much must neither
never nor not now off once only other our ours ourselves out over own per perhaps rather same shall she should since some such
than that the their theirs them themselves then there these they this those though through thus too under until upon very was
were what whatever when where whether which while who whom whose why will with within without would yet you your yours yourself
yourselves one two three also get got make made many way well back still use used using within via etc https http www com
""".split())

ALL = FR | EN
