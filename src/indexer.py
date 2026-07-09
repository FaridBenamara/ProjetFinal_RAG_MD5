import chromadb
from sentence_transformers import SentenceTransformer

MODELE_DEFAUT = "paraphrase-multilingual-MiniLM-L12-v2"
COLLECTION = "code_travail"


class Indexer:
    # encode les chunks et persiste la base ChromaDB ; l'indexation ne se fait
    # qu'en lancant ce module, jamais au demarrage de l'application

    def __init__(self, persist_dir="./chroma_db", model_name=MODELE_DEFAUT):
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)
        self.client = chromadb.PersistentClient(path=persist_dir)

    # chroma refuse les insertions de plus de ~5400 elements
    TAILLE_LOT = 5000

    def indexer(self, chunks, date_extraction):
        collection = self._nouvelle_collection(date_extraction)
        embeddings = self.model.encode([c.texte for c in chunks], show_progress_bar=True)
        for debut in range(0, len(chunks), self.TAILLE_LOT):
            lot = chunks[debut : debut + self.TAILLE_LOT]
            collection.add(
                ids=[c.id for c in lot],
                embeddings=embeddings[debut : debut + self.TAILLE_LOT],
                documents=[c.texte for c in lot],
                metadatas=[self._metadonnees(c) for c in lot],
            )
        return collection

    def _nouvelle_collection(self, date_extraction):
        if any(c.name == COLLECTION for c in self.client.list_collections()):
            self.client.delete_collection(COLLECTION)
        return self.client.create_collection(
            COLLECTION,
            metadata={
                "hnsw:space": "cosine",
                "embedding_model": self.model_name,
                "date_extraction": date_extraction,
            },
        )

    def _metadonnees(self, chunk):
        # chroma n'accepte que des scalaires : la liste de numeros devient une chaine
        return {
            "nums": ",".join(chunk.nums),
            "theme": chunk.theme,
            "chemin_section": chunk.chemin_section,
            "date_version": chunk.date_version,
        }


if __name__ == "__main__":
    import json

    from src.chunking import Chunker

    with open("data/corpus.json", encoding="utf-8") as f:
        corpus = json.load(f)

    chunks = Chunker().decouper(corpus["documents"])
    indexer = Indexer()
    collection = indexer.indexer(chunks, corpus["date_extraction"])

    print(f"\n{collection.count()} chunks indexes dans '{COLLECTION}'")
    print(f"modele : {collection.metadata['embedding_model']}")
    print(f"corpus du : {collection.metadata['date_extraction']}")
