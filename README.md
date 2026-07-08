# Assistant Code du travail (RAG)

Assistant juridique en droit du travail francais, construit en RAG "from scratch"
(sans LangChain ni LlamaIndex) sur le corpus Legifrance.

## Installation

```bash
python -m venv .venv
.venv/Scripts/activate  # ou source .venv/bin/activate sous Linux/Mac
pip install -r requirements.txt
cp .env.example .env  # puis remplir les cles
```

## Lancement

```bash
python -m src.build_corpus
python -m src.indexer
python -m src.cli
```

## Questions de reflexion

### 1. Granularite du chunking

A completer.

### 2. Tracabilite

A completer.

### 3. Fraicheur

A completer.

### 4. Reponses conditionnelles

A completer.

### 5. La frontiere du conseil juridique

A completer.
