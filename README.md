# Assistant Code du travail (RAG)

Assistant de questions-réponses sur le droit du travail français. Le corpus vient de
l'API Légifrance, la recherche est vectorielle (sentence-transformers + ChromaDB), la
génération passe par Groq. Pas de LangChain ni LlamaIndex : chaque brique est écrite à
la main. Chaque réponse cite les numéros d'articles utilisés, et quand la question sort
du corpus le système le dit au lieu d'inventer.

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
200 caractères qu'on fusionne avec le chunk précédent de la même section. Chaque chunk
commence par son numéro et sa section (`Article L3121-1 (Sous-section 1 : Travail
effectif.) : ...`). Sur nos 819 articles ça donne 722 chunks, dont 81 regroupés,
médiane 590 caractères. Aucun article n'est coupé : on fusionne des articles entiers,
on ne découpe jamais.

### 2. Traçabilité

Le numéro est stocké aux deux endroits. Dans le texte embeddé, pour qu'une question du
type « que dit L3121-1 ? » ait une chance de matcher. Dans les métadonnées ChromaDB,
pour afficher les sources sans re-parser le texte.

Côté génération, le contexte envoyé au modèle est numéroté avec les métadonnées, et le
prompt interdit de citer un numéro qui n'y figure pas. Si la recherche ne trouve rien
d'assez proche, le code répond directement « je ne trouve pas cette information dans ma
base » sans appeler le LLM — c'est un seuil de distance qui décide, pas le modèle.
En pratique le vectoriel seul ne suffit pas pour les questions par numéro : on a mesuré
que L3121-1 ressort au-delà du rang 30 sur « que dit l'article L3121-1 ? ». D'où la
recherche hybride prévue au jalon 6 (détection du numéro par regex + récupération
directe).

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

## Limites constatées

- Le corpus ne contient jamais les sigles. « SMIC » ne matche pas alors que « salaire
  minimum de croissance » sort en rang 1 ; pareil pour « CDD ». Une reformulation de la
  question par LLM est la piste envisagée.
- Les questions par numéro d'article échouent en vectoriel pur (rang > 30), voir Q2.
- Sur nos tests, les questions du domaine restent sous 0,54 de distance (0,17 à 0,28
  quand la formulation est proche du texte, jusqu'à 0,53 quand elle s'en éloigne) et
  les questions hors sujet démarrent à 0,56. Le seuil de refus est à 0,55 : il n'écarte
  que le clairement hors sujet, et dans la zone grise c'est le prompt qui refuse quand
  le contexte ne répond pas. Un premier seuil à 0,45 refusait à tort des questions
  légitimes (« comment fonctionne la rupture conventionnelle ? » est à 0,506) — trouvé
  en session manuelle, recalibré.
- Les questions en langage très familier (« je travaille 45h en CDI j'ai le droit ? »)
  retrouvent mal leurs articles (distances 0,66 et plus, chunks non pertinents) : un
  seuil ne peut rien y faire, c'est la reformulation de la question qui doit les traiter.
- Les articles les plus longs dépassent la fenêtre du modèle d'embedding et sont
  tronqués à l'encodage (environ 10 % des chunks). Pas d'impact constaté sur nos tests
  de validation ; si ça en avait un, la piste serait de découper ces articles par
  alinéa.
