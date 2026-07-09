import re

import chromadb
from sentence_transformers import SentenceTransformer

from src.indexer import COLLECTION

# L. 3121-1, l3121-1, R1234-4... — le point et l'espace apres la lettre sont
# des graphies courantes dans les questions
NUMERO_ARTICLE = re.compile(r"\b([LRD])\.?\s?(\d{1,4}(?:-\d+)*)\b", re.IGNORECASE)
# plafond d'articles ajoutes au contexte en suivant les renvois des chunks
MAX_RENVOIS = 4


class Retriever:
    # recharge la base persistee (sans jamais reindexer) et cherche les top-k

    def __init__(self, persist_dir="./chroma_db"):
        client = chromadb.PersistentClient(path=persist_dir)
        self.collection = client.get_collection(COLLECTION)
        # le meme modele que celui de l'indexation, lu dans les metadonnees
        self.model = SentenceTransformer(self.collection.metadata["embedding_model"])
        self._ids_par_num = self._indexer_numeros()

    def rechercher(self, question, k=5):
        embedding = self.model.encode([question])
        resultats = self.collection.query(query_embeddings=embedding, n_results=k)
        return [
            self._vers_chunk(id_, document, metadonnees, distance)
            for id_, document, metadonnees, distance in zip(
                resultats["ids"][0],
                resultats["documents"][0],
                resultats["metadatas"][0],
                resultats["distances"][0],
            )
        ]

    def rechercher_hybride(self, question, k=5, question_vectorielle=None):
        # les articles cites par leur numero remontent d'office ; la recherche
        # vectorielle (sur la question reformulee le cas echeant) complete
        lexicaux = self._par_numeros(question)
        vectoriels = self.rechercher(question_vectorielle or question, k)
        fusion = self._fusionner(lexicaux, vectoriels, k)
        return fusion + self._suivre_renvois(fusion)

    def _suivre_renvois(self, chunks):
        # les articles se citent entre eux (« au sens de l'article L. 1121-2 »)
        # mais le voisin cite n'est pas dans le chunk : on l'ajoute au contexte.
        # il herite de la distance du chunk qui le cite, pour ne pas fausser
        # le seuil de refus du generateur
        presents = {num for chunk in chunks for num in chunk["nums"]}
        renvois = []
        for chunk in chunks:
            for lettre, chiffres in NUMERO_ARTICLE.findall(chunk["texte"]):
                num = f"{lettre.upper()}{chiffres}"
                if num in presents or num not in self._ids_par_num:
                    continue
                presents.add(num)
                cible = self._chunk_par_id(self._ids_par_num[num][0], chunk["distance"])
                renvois.append(cible)
                if len(renvois) == MAX_RENVOIS:
                    return renvois
        return renvois

    def _chunk_par_id(self, id_, distance):
        resultat = self.collection.get(ids=[id_], include=["documents", "metadatas"])
        return self._vers_chunk(id_, resultat["documents"][0], resultat["metadatas"][0], distance)

    def date_corpus(self):
        return self.collection.metadata["date_extraction"]

    def _indexer_numeros(self):
        # table numero d'article -> ids des chunks qui le portent
        tout = self.collection.get(include=["metadatas"])
        table = {}
        for id_, metadonnees in zip(tout["ids"], tout["metadatas"]):
            for num in metadonnees["nums"].split(","):
                table.setdefault(num, []).append(id_)
        return table

    def _par_numeros(self, question):
        ids = []
        for lettre, chiffres in NUMERO_ARTICLE.findall(question):
            num = f"{lettre.upper()}{chiffres}"
            ids.extend(self._ids_par_num.get(num, []))
        if not ids:
            return []
        resultats = self.collection.get(ids=ids, include=["documents", "metadatas"])
        # distance 0 : un article cite explicitement est pertinent par definition
        return [
            self._vers_chunk(id_, document, metadonnees, 0.0)
            for id_, document, metadonnees in zip(
                resultats["ids"], resultats["documents"], resultats["metadatas"]
            )
        ]

    def _fusionner(self, lexicaux, vectoriels, k):
        fusion, vus = [], set()
        for chunk in lexicaux + vectoriels:
            if chunk["id"] not in vus:
                vus.add(chunk["id"])
                fusion.append(chunk)
        # les lexicaux sont toujours gardes, le vectoriel complete jusqu'a k
        return fusion[: max(k, len(lexicaux))]

    def _vers_chunk(self, id_, document, metadonnees, distance):
        return {
            "id": id_,
            "texte": document,
            "nums": metadonnees["nums"].split(","),
            "theme": metadonnees["theme"],
            "chemin_section": metadonnees["chemin_section"],
            "distance": distance,
        }


if __name__ == "__main__":
    retriever = Retriever()
    print(f"corpus du {retriever.date_corpus()}\n")
    for question in ["Que dit l'article L3121-1 ?", "Quelle est la durée légale de travail hebdomadaire ?"]:
        print(f"Q : {question}")
        for chunk in retriever.rechercher_hybride(question):
            print(f"  [{chunk['distance']:.3f}] {','.join(chunk['nums'])} - {chunk['texte'][:80]}")
        print()
