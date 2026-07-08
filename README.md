# Assistant Code du travail (RAG)

Assistant juridique en droit du travail français, construit en RAG « from scratch »
(sans LangChain ni LlamaIndex) sur le corpus Légifrance. Il répond en langage naturel
en citant systématiquement les numéros d'articles sur lesquels il s'appuie, et refuse
de répondre quand l'information n'est pas dans sa base.

## Installation

```bash
python -m venv .venv
.venv/Scripts/activate          # Windows (source .venv/bin/activate sous Linux/Mac)
pip install -r requirements.txt
cp .env.example .env            # puis renseigner les clés PISTE et GROQ
```

## Lancement

L'ordre compte : le corpus doit exister avant l'indexation, la base avant l'interrogation.

```bash
python -m src.build_corpus      # 1. extraction Légifrance -> data/corpus.json (une fois)
python -m src.indexer           # 2. indexation -> ./chroma_db/ (une fois)
pytest tests/ -v                # 3. validation du retrieval
python -m src.cli               # 4. boucle question-réponse (à venir)
```

Au lancement, l'application recharge la base persistée sans jamais réindexer.
Pour rafraîchir le corpus : supprimer `data/toc_raw.json` (le cache de l'arbre
Légifrance) puis relancer les étapes 1 et 2.

## Questions de réflexion

### 1. Granularité du chunking

**Un article par chunk** : la traçabilité est parfaite (un chunk correspond à des
numéros précis, cités sans ambiguïté) et la recherche est précise, mais les articles
très courts donnent des chunks pauvres pour l'embedding, et le contexte des articles
voisins qui se citent entre eux est perdu.

**Un chunk par section** : le contexte est riche, mais un chunk mélange plusieurs
numéros — au moment de citer, le risque d'attribuer la mauvaise référence est réel,
et les gros chunks diluent la pertinence de la recherche.

**Notre choix : hybride.** Un article = un chunk par défaut, et les articles de moins
de 200 caractères sont fusionnés avec leur voisin de la même section. Chaque chunk est
préfixé de son numéro et de sa section la plus fine (`Article L3121-1 (Sous-section 1 :
Travail effectif.) : ...`). Sur notre corpus de 819 articles, cela donne 722 chunks dont
81 regroupés, médiane 590 caractères. Aucun article n'est jamais coupé : on ne fait que
fusionner des articles entiers, jamais découper.

### 2. Traçabilité

Le numéro d'article est stocké **aux deux endroits**. Dans le texte embeddé, pour que
« que dit L3121-1 ? » puisse matcher sémantiquement. Dans les métadonnées ChromaDB,
pour afficher et filtrer les sources sans re-parser le texte.

Pour que le LLM cite juste au lieu d'inventer : le contexte fourni au modèle est
numéroté avec les métadonnées de chaque chunk, le prompt interdit de citer un numéro
absent de ce contexte, et si la recherche ne remonte rien de pertinent le système
répond « je ne trouve pas cette information dans ma base » — décision prise par le
code (seuil de distance), pas laissée au modèle. En complément, la recherche hybride
(jalon 6) récupère lexicalement les articles cités par leur numéro dans la question :
nous avons mesuré que le vectoriel seul classe L3121-1 au-delà du rang 30 pour la
question « que dit l'article L3121-1 ? ».

### 3. Fraîcheur

Le corpus est une photo datée du droit en vigueur : l'extraction interroge Légifrance
consolidé à la date du jour, ne garde que les articles à l'état VIGUEUR, et stocke
deux dates — `date_version` par article (depuis quand sa rédaction s'applique) et
`date_extraction` globale (dérivée de la date de téléchargement des données, pas du
rebuild). Cette date est affichée **par le code** à chaque réponse, à côté de
l'avertissement juridique : l'utilisateur sait toujours sur quel état du droit
l'assistant s'appuie.

Le rafraîchissement est volontairement manuel (supprimer le cache, relancer
l'extraction puis l'indexation) : le droit du travail change quelques fois par an,
pas chaque jour, et toute réindexation automatique au lancement est exclue. Un
système qui dit honnêtement sa date vaut mieux qu'un système qui prétend être à jour.

### 4. Réponses conditionnelles

Réponse générale assortie de réserves explicites, plutôt que question de clarification
systématique (trop de friction pour une première réponse). Le prompt demande d'énoncer
la règle de droit commun, puis de nommer les variables qui peuvent la changer quand les
articles du contexte les mentionnent : taille de l'entreprise, convention collective,
accord d'entreprise, ancienneté. L'utilisateur repart avec la règle générale et sait
précisément ce qu'il doit vérifier pour sa situation.

### 5. La frontière du conseil juridique

Une question **factuelle** (« combien de jours de congés par an ? ») appelle une règle
générale : le système répond et cite l'article. Une question d'**interprétation**
(« mon licenciement est-il abusif ? ») demande de qualifier juridiquement une situation
personnelle : le système donne le cadre légal applicable avec ses articles, mais refuse
de trancher le cas particulier et oriente vers un avocat ou l'inspection du travail.

Cette frontière est portée par le prompt (instructions et exemples), et la garantie
finale est dans le code : l'avertissement « Cet assistant ne fournit pas de conseil
juridique... » est ajouté par le Generator à chaque réponse, sans exception possible —
une consigne de prompt peut être ignorée une fois sur dix, pas une concaténation.

## Limites mesurées

- Le corpus ne contient pas les sigles : « SMIC » ne matche pas (« salaire minimum de
  croissance » sort rang 1), « CDD » non plus. Piste : reformulation LLM de la question.
- Les questions par numéro d'article échouent en vectoriel pur (rang > 30) : c'est la
  recherche hybride du jalon 6 qui les prend en charge.
- Les distances mesurées séparent nettement les questions dans le corpus (0,17–0,28)
  des questions hors sujet (0,56–0,88) : le seuil de refus est calibré vers 0,45.
- Environ 10 % des chunks dépassent la fenêtre du modèle d'embedding (les articles
  les plus longs sont tronqués à l'encodage). Sans impact mesuré sur la validation ;
  une découpe par alinéa des très longs articles est la piste si besoin.
