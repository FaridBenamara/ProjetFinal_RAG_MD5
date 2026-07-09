# Assistant Code du travail (RAG)

Assistant de questions-réponses sur le droit du travail français. Le corpus couvre
l'intégralité du Code du travail en vigueur — parties législative et réglementaire,
soit 11 592 articles extraits via l'API Légifrance. La recherche est vectorielle
(sentence-transformers + ChromaDB), la génération passe par Groq. Pas de LangChain ni
LlamaIndex : chaque brique est écrite à la main. Chaque réponse cite les numéros
d'articles utilisés, et quand la question sort du corpus le système le dit au lieu
d'inventer.

## Le corpus

Tous les articles à l'état VIGUEUR du Code du travail, sans filtre thématique : les
huit thèmes du sujet sont donc couverts, et le reste aussi (repos dominical, travail
de nuit, assurance chômage... des sujets que nos tests en conditions réelles ont fait
remonter très vite). Les parties R et D apportent les modalités concrètes que la
partie L ne donne pas — c'est R1234-4 qui contient le calcul de l'indemnité de
licenciement, pas un article L.

Deux défauts des données Légifrance sont corrigés à l'extraction : des articles
rattachés à deux sections de l'arborescence (dédoublonnage par identifiant), et de
rares articles avec deux versions simultanément « en vigueur » (on garde la rédaction
la plus récente).

## Installation

```bash
python -m venv .venv
.venv/Scripts/activate          # Windows (source .venv/bin/activate sous Linux/Mac)
pip install -r requirements.txt
cp .env.example .env            # puis renseigner les clés PISTE et GROQ
```

## Lancement

Dans cet ordre (le corpus doit exister avant d'indexer, la base avant d'interroger) :

```bash
python -m src.build_corpus      # 1. extraction Légifrance -> data/corpus.json (une fois)
python -m src.indexer           # 2. indexation -> ./chroma_db/ (une fois)
pytest tests/ -v                # 3. validation du retrieval
python -m src.cli               # 4. boucle question-réponse (/quit pour sortir)
```

Au lancement l'application recharge la base existante, elle ne réindexe jamais. Pour
rafraîchir le corpus, supprimer `data/toc_raw.json` (le cache de l'arbre Légifrance)
et relancer les étapes 1 et 2.

## Questions de réflexion

### 1. Granularité du chunking

Indexer chaque article séparément donne une traçabilité nette : un chunk = un numéro,
pas d'ambiguïté au moment de citer. L'inconvénient, ce sont les articles très courts
(certains font deux lignes) qui donnent des embeddings pauvres, et la perte du contexte
quand un article renvoie à son voisin.

Regrouper par section, c'est l'inverse : plus de contexte, mais plusieurs numéros par
chunk, donc un vrai risque que le LLM attribue une affirmation au mauvais article. Pour
un assistant juridique c'est le pire défaut possible. Et les chunks deviennent longs,
ce qui dilue la recherche.

On est partis sur un entre-deux : un article = un chunk, sauf les articles de moins de
200 caractères qu'on fusionne avec le chunk précédent de la même section, et les
articles de plus de 2 000 caractères qu'on découpe en morceaux — toujours à une
frontière de phrase, jamais au milieu (certaines annexes réglementaires font plus de
100 000 caractères : un chunk pareil est inutile à l'embedding et hors de prix dans le
contexte du LLM). Chaque chunk commence par son numéro et sa section (`Article L3121-1
(Sous-section 1 : Travail effectif.) : ...`), et chaque morceau d'article découpé garde
le numéro complet. Sur les 11 592 articles ça donne 10 767 chunks, dont 1 141
regroupés, médiane 577 caractères, maximum 3 057.

### 2. Traçabilité

Le numéro est stocké aux deux endroits. Dans le texte embeddé, pour qu'une question du
type « que dit L3121-1 ? » ait une chance de matcher. Dans les métadonnées ChromaDB,
pour afficher les sources sans re-parser le texte.

Côté génération, le contexte envoyé au modèle est numéroté avec les métadonnées, et le
prompt interdit de citer un numéro qui n'y figure pas. Si la recherche ne trouve rien
d'assez proche, le code répond directement « je ne trouve pas cette information dans ma
base » sans appeler le LLM — c'est un seuil de distance qui décide, pas le modèle.
En pratique le vectoriel seul ne suffit pas pour les questions par numéro : on a mesuré
que L3121-1 ressort au-delà du rang 30 sur « que dit l'article L3121-1 ? ». C'est la
recherche hybride qui garantit ces questions (voir Améliorations).

### 3. Fraîcheur

Le corpus est une photo du droit en vigueur à une date donnée. L'extraction interroge
Légifrance consolidé à la date du jour et ne garde que les articles à l'état VIGUEUR.
On conserve deux dates : `date_version` pour chaque article (depuis quand sa rédaction
s'applique) et `date_extraction` pour le corpus entier. Cette dernière est affichée
avec chaque réponse, par le code qui assemble la réponse et pas par le prompt, pour que
l'utilisateur sache toujours sur quel état du droit il s'appuie.

Le rafraîchissement reste une opération manuelle (supprimer le cache, relancer
extraction et indexation). Le droit du travail bouge quelques fois par an, une
réindexation automatique au lancement n'aurait aucun sens — et c'est de toute façon
éliminatoire dans le cadre du projet.

### 4. Réponses conditionnelles

Beaucoup de réponses dépendent de la taille de l'entreprise, de la convention
collective, de l'ancienneté. Poser une question de clarification à chaque fois rendrait
l'assistant pénible, donc le choix est : réponse générale + réserves. Le prompt demande
d'énoncer la règle de droit commun, puis de signaler explicitement les cas où les
articles du contexte mentionnent une condition (seuil d'effectif, accord collectif...).
L'utilisateur a la règle générale et sait ce qu'il doit vérifier pour son cas.

### 5. La frontière du conseil juridique

« Combien de jours de congés par an ? » est une question factuelle : le Code y répond,
on cite l'article. « Mon licenciement est-il abusif ? » demande de qualifier une
situation personnelle : là le système donne le cadre légal (les articles qui
s'appliquent) mais refuse de conclure sur le cas particulier et renvoie vers un avocat
ou l'inspection du travail.

Cette distinction est décrite dans le prompt, avec des exemples. Mais la garantie
finale ne repose pas dessus : l'avertissement « Cet assistant ne fournit pas de conseil
juridique... » est concaténé par le code du Generator à chaque réponse. Un prompt peut
être ignoré de temps en temps, une concaténation non.

## Améliorations (jalon 6)

### Reformulation de la question

Un appel LLM court traduit la question de l'utilisateur en vocabulaire du Code avant
la recherche : sigles développés (CDI, CSE, SMIC...), langage familier remplacé par
les termes juridiques, fautes corrigées. La recherche se fait sur la question
reformulée, la génération répond à la question originale — on reformule pour chercher,
jamais pour répondre. Si l'appel échoue, la question brute est utilisée telle quelle :
la reformulation ne peut pas casser le pipeline.

Ce qu'elle change, mesuré sur un banc de 30 questions (10 factuelles, 10 en langage
quotidien, 10 juridiques mais hors Code du travail) :

| question | distance brute | reformulée |
|---|---|---|
| « UN CDI DE 45H EST POSSIBLE? » | 0,640 (refusée) | 0,209 (répond, L3121-27) |
| « montant du SMIC » | 0,577 (refusée) | 0,273 (répond, L3231-2) |
| « c est quoi le delai pour toucher son solde de tout compte » | 0,815 (refusée) | 0,151 |
| « je peux me faire virer sans preavis ? » (l'exemple du sujet) | 0,651 (refusée) | 0,326 |

Sur le banc : 5 questions sur 13 sauvées du refus, gain moyen de 0,25 de distance,
et aucune question hors sujet « sauvée » à tort — le reformulateur traduit, il
n'attire pas vers le corpus. Deux garde-fous ont été ajoutés au prompt après les
premiers essais : interdiction d'inventer un chiffre absent de la question (le modèle
ajoutait « au-delà de quarante heures »...), et obligation de recopier telle quelle
une question hors sujet (il répondait « je ne peux pas répondre », et ce commentaire
mentionnant le Code du travail faisait artificiellement chuter la distance).

La reformulation tourne sur `llama-3.1-8b-instant` : la tâche est simple, le petit
modèle est cinq fois plus rapide, et son quota Groq est distinct de celui du modèle
de génération — les deux budgets ne se cannibalisent pas.

### Recherche hybride

Une question qui cite un numéro d'article (« que dit L3121-1 ? ») échoue en recherche
vectorielle pure : mesuré au rang > 30, le numéro n'est pas un token discriminant pour
l'embedding. La recherche hybride corrige ça : une regex détecte les numéros dans la
question (graphies tolérées : `L3121-1`, `l. 3121-1`, articles R et D), une table
numéro → chunks construite au chargement les remonte d'office en tête (distance 0,
un article cité explicitement est pertinent par définition), et la recherche
vectorielle complète jusqu'à k. Sans numéro dans la question, le comportement est
strictement identique au vectoriel.

Deux choix à défendre :
- les numéros sont détectés sur la question **originale**, pas la reformulée — en
  test, le modèle de reformulation a inventé que L3121-1 parlait du CDI ; le passage
  lexical neutralise ce genre de pollution ;
- les sources affichées sont filtrées aux articles que la réponse cite réellement —
  avant, les chunks de remplissage vectoriel apparaissaient en source alors qu'ils
  n'avaient pas servi.

Bonus constaté : « Compare L1234-1 et L1237-13 » produit une synthèse comparative
correcte des deux articles — le mode comparaison du sujet, obtenu sans code dédié.

### Le nombre de chunks : k=10

Sur le corpus des 8 thèmes (722 chunks), k=5 suffisait : 30/30 au banc de test. Sur le
corpus complet (10 767 chunks), les voisins tangentiels (contrats aidés, formation...)
évincent l'article attendu vers les rangs 6 à 10 : k=5 perdait 4 questions sur 10,
k=8 encore 3, k=10 n'en perd plus qu'une (voir Limites). Les dix questions piège
d'autres codes restent refusées à k=10 — élargir le contexte n'a pas fait répondre à
tort. C'est l'arbitrage du jalon 4 (« trop peu, la réponse est incomplète ; trop, le
contexte se noie ») tranché avec des mesures.

## Limites constatées

- Les questions par numéro d'article échouent en vectoriel pur (rang > 30) : prises
  en charge par la recherche hybride (voir Améliorations).
- Sur le corpus complet, les distances des questions hors sujet se resserrent : le
  corpus contient du contenu fiscalo-adjacent (saisies sur salaire) et pénal (sanctions
  du travail illégal) qui attire des questions d'autres codes sous le seuil de 0,55.
  Le refus repose alors sur le second étage : le prompt, qui refuse quand le contexte
  ne répond pas — vérifié sur dix questions piège (droit pénal, fiscal, consommation,
  famille, route), toutes refusées.
- Sur les sujets encombrés (licenciement : plusieurs centaines d'articles L et R), la
  précision du retrieval dépend de la formulation. « Quel préavis pour un licenciement
  sans faute grave ? » remonte L1234-1 en rang 2 ; « quel préavis pour deux ans
  d'ancienneté ? » le laisse en rang 9. Un reranking par cross-encoder est la piste
  identifiée si ce mode d'échec devenait fréquent (mesuré : 1 question sur 30).
- La fenêtre du modèle d'embedding (~500 caractères utiles) reste plus courte que la
  médiane des chunks : le début du chunk — numéro, section, premier alinéa — porte
  l'essentiel du signal. Le découpage à 2 000 caractères borne l'effet.
