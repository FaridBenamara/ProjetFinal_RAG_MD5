import html
import json
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path

CODE_TRAVAIL_CID = "LEGITEXT000006072050"
CACHE_ARBRE = Path("data/toc_raw.json")

# plages du tableau du sujet, du plus specifique au plus general
# (rupture conventionnelle est un sous-cas de licenciement dans le code)
THEMES = [
    ("Rupture conventionnelle", "L1237-11", "L1237-19"),
    ("Licenciement", "L1231-1", "L1237-20"),
    ("Contrat de travail (CDI, CDD)", "L1221-1", "L1248-11"),
    ("Harcelement et discrimination", "L1152-1", "L1155-2"),
    ("Duree du travail et heures supplementaires", "L3121-1", "L3121-36"),
    ("Conges payes", "L3141-1", "L3141-32"),
    ("Salaire minimum (SMIC)", "L3231-1", "L3232-9"),
    ("Representation du personnel", "L2311-1", "L2316-26"),
]


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
        documents = []
        for article in self._extraire_articles(arbre):
            theme = self._trouver_theme(article)
            if theme:
                documents.append(self._vers_document(article, theme))
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

    def _trouver_theme(self, article):
        if article["etat"] != "VIGUEUR" or not article["num"].startswith("L"):
            return None
        num = _parse_num(article["num"])
        for theme, debut, fin in THEMES:
            if _parse_num(debut) <= num <= _parse_num(fin):
                return theme
        return None

    def _vers_document(self, article, theme):
        return Document(
            id=article["id"],
            num=article["num"],
            texte=_nettoyer_html(article["content"]),
            theme=theme,
            chemin_section=" > ".join(t.strip() for t in article["pathTitle"]),
            date_version=_epoch_vers_date(article["dateDebut"]),
        )

    def _dedupliquer(self, documents):
        # certains articles sont rattaches a deux sections dans l'arbre Legifrance
        vus = {}
        for doc in documents:
            vus.setdefault(doc.id, doc)
        return list(vus.values())

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

    print(f"{len(documents)} articles extraits sur {len(THEMES)} themes")
    print(f"date d'extraction : {builder._date_extraction()}")
    for doc in random.sample(documents, 10):
        print(f"\n[{doc.theme}] {doc.num} - {doc.chemin_section}")
        print(doc.texte[:200])
