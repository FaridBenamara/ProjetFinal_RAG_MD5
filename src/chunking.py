import json
from dataclasses import dataclass, field

MIN_CHARS = 200


@dataclass
class Chunk:
    id: str
    texte: str
    nums: list = field(default_factory=list)
    theme: str = ""
    chemin_section: str = ""
    date_version: str = ""


class Chunker:
    # 1 article = 1 chunk ; les articles courts sont regroupes
    # avec leur voisin de la meme section

    def __init__(self, min_chars=MIN_CHARS):
        self.min_chars = min_chars

    def decouper(self, documents):
        chunks = []
        for doc in documents:
            if self._regroupable(doc, chunks):
                self._fusionner(chunks[-1], doc)
            else:
                chunks.append(self._nouveau_chunk(doc))
        return chunks

    def _regroupable(self, doc, chunks):
        if len(doc["texte"]) >= self.min_chars:
            return False
        return bool(chunks) and chunks[-1].chemin_section == doc["chemin_section"]

    def _nouveau_chunk(self, doc):
        return Chunk(
            id=doc["id"],
            texte=self._texte_embedde(doc),
            nums=[doc["num"]],
            theme=doc["theme"],
            chemin_section=doc["chemin_section"],
            date_version=doc["date_version"],
        )

    def _fusionner(self, chunk, doc):
        chunk.texte += "\n" + self._texte_embedde(doc)
        chunk.nums.append(doc["num"])

    def _texte_embedde(self, doc):
        # le numero est dans le texte pour que "que dit L3121-1 ?" matche ;
        # la section la plus fine suffit, le chemin complet noierait le texte
        section_fine = doc["chemin_section"].split(" > ")[-1]
        return f"Article {doc['num']} ({section_fine}) : {doc['texte']}"


if __name__ == "__main__":
    with open("data/corpus.json", encoding="utf-8") as f:
        corpus = json.load(f)

    chunks = Chunker().decouper(corpus["documents"])
    regroupes = [c for c in chunks if len(c.nums) > 1]

    print(f"{len(corpus['documents'])} articles -> {len(chunks)} chunks")
    print(f"{len(regroupes)} chunks regroupent plusieurs articles courts")
    longueurs = sorted(len(c.texte) for c in chunks)
    print(f"longueur : min={longueurs[0]} mediane={longueurs[len(longueurs)//2]} max={longueurs[-1]}")

    print("\n=== exemple de chunk simple ===")
    print(chunks[0].texte[:400])
    if regroupes:
        print("\n=== exemple de chunk regroupe ===")
        print(f"(articles {', '.join(regroupes[0].nums)})")
        print(regroupes[0].texte[:600])
