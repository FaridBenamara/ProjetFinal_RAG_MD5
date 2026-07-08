import html
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

CODE_TRAVAIL_CID = "LEGITEXT000006072050"
CACHE_ARBRE = Path("data/toc_raw.json")

# plages du tableau du sujet, ordre du plus specifique au plus general
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
        articles = self._extraire_articles(arbre)
        documents = self._filtrer_et_convertir(articles)
        self._ecrire(documents)
        return documents

    def _charger_arbre(self):
        if CACHE_ARBRE.exists():
            return json.loads(CACHE_ARBRE.read_text(encoding="utf-8"))

        arbre = self.client.appeler("/consult/legiPart", {"textId": CODE_TRAVAIL_CID})
        CACHE_ARBRE.parent.mkdir(parents=True, exist_ok=True)
        CACHE_ARBRE.write_text(json.dumps(arbre, ensure_ascii=False), encoding="utf-8")
        return arbre

    def _extraire_articles(self, noeud, out=None):
        if out is None:
            out = []
        out.extend(noeud.get("articles") or [])
        for section in noeud.get("sections") or []:
            self._extraire_articles(section, out)
        return out

    def _filtrer_et_convertir(self, articles):
        documents = []
        for article in articles:
            theme = self._theme_valide(article)
            if theme:
                documents.append(self._vers_document(article, theme))
        return documents

    def _theme_valide(self, article):
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

    def _ecrire(self, documents):
        Path(self.output_path).parent.mkdir(parents=True, exist_ok=True)
        contenu = json.dumps([asdict(d) for d in documents], ensure_ascii=False, indent=2)
        Path(self.output_path).write_text(contenu, encoding="utf-8")


def _parse_num(num):
    return tuple(int(n) for n in re.findall(r"\d+", num))


def _nettoyer_html(content):
    texte = re.sub(r"<[^>]+>", " ", content)
    texte = html.unescape(texte)
    return re.sub(r"\s+", " ", texte).strip()


def _epoch_vers_date(epoch_ms):
    from datetime import datetime, timezone

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
    for doc in random.sample(documents, 10):
        print(f"\n[{doc.theme}] {doc.num} - {doc.chemin_section}")
        print(doc.texte[:200])
