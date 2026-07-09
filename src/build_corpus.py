import html
import json
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path

CODE_TRAVAIL_CID = "LEGITEXT000006072050"
CACHE_ARBRE = Path("data/toc_raw.json")


@dataclass
class Document:
    id: str
    num: str
    texte: str
    theme: str
    chemin_section: str
    date_version: str


class CorpusBuilder:
    # Arbre legiPart -> data/corpus.json

    def __init__(self, client, output_path="data/corpus.json"):
        self.client = client
        self.output_path = output_path

    def construire(self):
        arbre = self._charger_arbre()
        documents = [
            self._vers_document(article)
            for article in self._extraire_articles(arbre)
            if self._est_retenu(article)
        ]
        documents = self._dedupliquer(documents)
        self._ecrire(documents)
        return documents

    def _charger_arbre(self):
        # pour rafraichir le corpus : supprimer le cache puis relancer
        if CACHE_ARBRE.exists():
            return json.loads(CACHE_ARBRE.read_text(encoding="utf-8"))
        payload = {"textId": CODE_TRAVAIL_CID, "date": date.today().isoformat()}
        arbre = self.client.appeler("/consult/legiPart", payload)
        CACHE_ARBRE.write_text(json.dumps(arbre, ensure_ascii=False), encoding="utf-8")
        return arbre

    def _extraire_articles(self, noeud):
        articles = list(noeud.get("articles") or [])
        for section in noeud.get("sections") or []:
            articles.extend(self._extraire_articles(section))
        return articles

    def _est_retenu(self, article):
        # tous les articles en vigueur, parties legislative et reglementaire
        return article["etat"] == "VIGUEUR"

    def _vers_document(self, article):
        return Document(
            id=article["id"],
            num=article["num"].strip(),
            texte=_nettoyer_html(article["content"]),
            theme=self._theme(article),
            chemin_section=" > ".join(t.strip() for t in article["pathTitle"]),
            date_version=_epoch_vers_date(article["dateDebut"]),
        )

    def _theme(self, article):
        # le "Livre" de l'arborescence sert de theme
        titres = [t.strip() for t in article["pathTitle"]]
        for titre in titres:
            if titre.startswith("Livre"):
                return titre
        return titres[1] if len(titres) > 1 else titres[0]

    def _dedupliquer(self, documents):
        # deux defauts des donnees Legifrance : des articles rattaches a deux
        # sections (dedup par id), et de rares articles avec deux versions
        # simultanement en vigueur (on garde la redaction la plus recente)
        par_id = {}
        for doc in documents:
            par_id.setdefault(doc.id, doc)
        par_version = {}
        for doc in par_id.values():
            cle = (doc.num, doc.chemin_section)
            if cle not in par_version or doc.date_version > par_version[cle].date_version:
                par_version[cle] = doc
        return list(par_version.values())

    def _ecrire(self, documents):
        corpus = {
            "date_extraction": self._date_extraction(),
            "documents": [asdict(d) for d in documents],
        }
        contenu = json.dumps(corpus, ensure_ascii=False, indent=2)
        Path(self.output_path).write_text(contenu, encoding="utf-8")

    def _date_extraction(self):
        # date de telechargement de l'arbre, pas du rebuild : le corpus n'est
        # pas plus frais que les donnees dont il vient
        telecharge_le = CACHE_ARBRE.stat().st_mtime
        return datetime.fromtimestamp(telecharge_le, tz=timezone.utc).strftime("%Y-%m-%d")


def _parse_num(num):
    return tuple(int(n) for n in re.findall(r"\d+", num))


def _nettoyer_html(content):
    texte = re.sub(r"<[^>]+>", " ", content)
    texte = html.unescape(texte)
    texte = re.sub(r"\s+", " ", texte).strip()
    # les renvois ("<a>L. 1234-5</a> .") laissent un espace parasite avant la ponctuation
    return re.sub(r"\s+([,.;:)])", r"\1", texte)


def _epoch_vers_date(epoch_ms):
    return datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


if __name__ == "__main__":
    import os
    import random

    from dotenv import load_dotenv

    from src.legifrance_client import LegifranceClient

    load_dotenv()
    client = LegifranceClient(os.environ["PISTE_CLIENT_ID"], os.environ["PISTE_CLIENT_SECRET"])
    builder = CorpusBuilder(client)
    documents = builder.construire()

    themes = {d.theme for d in documents}
    print(f"{len(documents)} articles extraits, {len(themes)} livres")
    print(f"date d'extraction : {builder._date_extraction()}")
    for doc in random.sample(documents, 10):
        print(f"\n[{doc.theme}] {doc.num} - {doc.chemin_section}")
        print(doc.texte[:200])
