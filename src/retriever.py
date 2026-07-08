import chromadb
from sentence_transformers import SentenceTransformer

from src.indexer import COLLECTION


class Retriever:
    # recharge la base persistee (sans jamais reindexer) et cherche les top-k

    def __init__(self, persist_dir="./chroma_db"):
        client = chromadb.PersistentClient(path=persist_dir)
        self.collection = client.get_collection(COLLECTION)
        # le meme modele que celui de l'indexation, lu dans les metadonnees
        self.model = SentenceTransformer(self.collection.metadata["embedding_model"])

    def rechercher(self, question, k=5):
        embedding = self.model.encode([question])
        resultats = self.collection.query(query_embeddings=embedding, n_results=k)
        return [
            {
                "texte": document,
                "nums": metadonnees["nums"].split(","),
                "theme": metadonnees["theme"],
                "chemin_section": metadonnees["chemin_section"],
                "distance": distance,
            }
            for document, metadonnees, distance in zip(
                resultats["documents"][0],
                resultats["metadatas"][0],
                resultats["distances"][0],
            )
        ]

    def date_corpus(self):
        return self.collection.metadata["date_extraction"]


if __name__ == "__main__":
    retriever = Retriever()
    print(f"corpus du {retriever.date_corpus()}\n")
    for chunk in retriever.rechercher("Quelle est la durée légale de travail hebdomadaire ?"):
        print(f"[{chunk['distance']:.3f}] {','.join(chunk['nums'])} - {chunk['texte'][:100]}")
