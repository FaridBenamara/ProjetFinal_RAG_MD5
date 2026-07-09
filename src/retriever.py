import math
import re
import unicodedata
from collections import Counter

import chromadb
from sentence_transformers import SentenceTransformer

from src.indexer import COLLECTION

# L. 3121-1, l3121-1, R1234-4... — le point et l'espace apres la lettre sont
# des graphies courantes dans les questions
NUMERO_ARTICLE = re.compile(r"\b([LRD])\.?\s?(\d{1,4}(?:-\d+)*)\b", re.IGNORECASE)
# plafond d'articles ajoutes au contexte en suivant les renvois des chunks
MAX_RENVOIS = 4
# « quelle difference entre X et Y ? », « comparer X et Y »... : chaque notion
# est cherchee separement, sinon l'embedding moyen des deux ne colle a aucune
COMPARAISON = re.compile(
    r"(?:diff[ée]rences?\s+entre|comparaison\s+entre|comparez?|comparer)\s+(.+?)\s+(?:et|avec)\s+(.+?)\s*\??$",
    re.IGNORECASE,
)

# recherche par mots-cles (BM25) : elle rattrape les cas ou l'embedding se
# noie dans un cluster dense — mesure : « quelle est la duree du preavis de
# licenciement ? » classait L1234-1 au-dela du rang 100 en vectoriel pur
BM25_K1 = 1.5
BM25_B = 0.75
TAILLE_POOL = 30  # candidats par source avant fusion
MOTS_VIDES = {
    "le", "la", "les", "un", "une", "des", "de", "du", "au", "aux", "et", "ou",
    "est", "sont", "etre", "avoir", "dans", "sur", "par", "pour", "avec", "sans",
    "que", "qui", "quoi", "dont", "quel", "quelle", "quels", "quelles", "comment",
    "combien", "pourquoi", "quand", "ce", "cette", "ces", "son", "sa", "ses",
    "mon", "ma", "mes", "ton", "ta", "tes", "il", "elle", "on", "je", "tu",
    "nous", "vous", "ils", "elles", "ne", "pas", "plus", "tout", "tous", "toute",
    "toutes", "peut", "doit", "cas", "donne", "moi", "donnez",
}


def _tokeniser(texte):
    # minuscules, accents retires, mots de 3 lettres et plus, hors mots vides
    sans_accents = "".join(
        c for c in unicodedata.normalize("NFD", texte.lower()) if unicodedata.category(c) != "Mn"
    )
    return [m for m in re.findall(r"[a-z]{3,}", sans_accents) if m not in MOTS_VIDES]


class Retriever:
    # recharge la base persistee (sans jamais reindexer) et cherche les top-k

    def __init__(self, persist_dir="./chroma_db"):
        client = chromadb.PersistentClient(path=persist_dir)
        self.collection = client.get_collection(COLLECTION)
        # le meme modele que celui de l'indexation, lu dans les metadonnees
        self.model = SentenceTransformer(self.collection.metadata["embedding_model"])
        self._construire_index_locaux()

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
        # trois sources : les articles cites par leur numero (d'office), puis
        # la fusion RRF du vectoriel et des mots-cles BM25 sur la question
        # reformulee ; les renvois des chunks retenus completent
        requete = question_vectorielle or question
        lexicaux = self._par_numeros(question)
        candidats = self._fusion_rangs(
            self._vectoriels(requete, TAILLE_POOL), self._par_mots_cles(requete, TAILLE_POOL), k
        )
        fusion = self._fusionner(lexicaux, candidats, k)
        return fusion + self._suivre_renvois(fusion)

    def _vectoriels(self, question, k):
        notions = COMPARAISON.search(question)
        if not notions:
            return self.rechercher(question, k)
        # comparaison : la moitie du contexte pour chacune des deux notions
        moitie = max(k // 2, 2)
        return self.rechercher(notions.group(1), moitie) + self.rechercher(notions.group(2), moitie)

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

    def _construire_index_locaux(self):
        # une seule passe sur la collection pour deux tables : les numeros
        # d'articles, et l'index inverse des mots (BM25)
        tout = self.collection.get(include=["documents", "metadatas"])
        self._ids = tout["ids"]
        self._ids_par_num = {}
        self._postings = {}
        self._longueurs = []
        for position, (id_, document, metadonnees) in enumerate(
            zip(tout["ids"], tout["documents"], tout["metadatas"])
        ):
            for num in metadonnees["nums"].split(","):
                self._ids_par_num.setdefault(num, []).append(id_)
            jetons = _tokeniser(document)
            self._longueurs.append(len(jetons))
            for jeton, occurrences in Counter(jetons).items():
                self._postings.setdefault(jeton, []).append((position, occurrences))
        self._longueur_moyenne = sum(self._longueurs) / max(len(self._longueurs), 1)

    def _par_mots_cles(self, question, n):
        # score BM25 : seul un document partageant des mots avec la question
        # est note, via l'index inverse
        scores = {}
        nb_docs = len(self._ids)
        for jeton in set(_tokeniser(question)):
            entrees = self._postings.get(jeton, [])
            if not entrees:
                continue
            idf = math.log(1 + (nb_docs - len(entrees) + 0.5) / (len(entrees) + 0.5))
            for position, tf in entrees:
                norme = 1 - BM25_B + BM25_B * self._longueurs[position] / self._longueur_moyenne
                scores[position] = scores.get(position, 0.0) + idf * tf * (BM25_K1 + 1) / (tf + BM25_K1 * norme)
        meilleurs = sorted(scores, key=scores.get, reverse=True)[:n]
        if not meilleurs:
            return []
        ids = [self._ids[position] for position in meilleurs]
        resultats = self.collection.get(ids=ids, include=["documents", "metadatas"])
        par_id = {
            id_: (document, metadonnees)
            for id_, document, metadonnees in zip(
                resultats["ids"], resultats["documents"], resultats["metadatas"]
            )
        }
        return [self._vers_chunk(id_, par_id[id_][0], par_id[id_][1], None) for id_ in ids]

    def _fusion_rangs(self, vectoriels, mots_cles, k):
        # chaque source propose son classement ; un chunk est classe a son
        # MEILLEUR rang des deux (departage par la somme des rangs), ce qui
        # preserve les vainqueurs d'une source tout en sauvant ceux de l'autre
        rangs, par_id = {}, {}
        absent = TAILLE_POOL + 1
        for liste in (vectoriels, mots_cles):
            for rang, chunk in enumerate(liste, 1):
                rangs.setdefault(chunk["id"], []).append(rang)
                par_id.setdefault(chunk["id"], chunk)
        retenus = sorted(
            rangs, key=lambda id_: (min(rangs[id_]), sum(rangs[id_]) + absent * (2 - len(rangs[id_])))
        )[:k]
        # les chunks venus des seuls mots-cles recoivent la pire distance
        # vectorielle, pour ne fausser ni seuil de refus ni confiance
        pire_distance = max((c["distance"] for c in vectoriels), default=0.5)
        fusion = []
        for id_ in retenus:
            chunk = par_id[id_]
            if chunk["distance"] is None:
                chunk = {**chunk, "distance": pire_distance}
            fusion.append(chunk)
        return fusion

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
