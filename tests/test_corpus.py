import json
import re
from pathlib import Path

import pytest

CORPUS = Path("data/corpus.json")


@pytest.fixture(scope="module")
def corpus():
    with open(CORPUS, encoding="utf-8") as f:
        return json.load(f)


def test_le_corpus_a_une_date_d_extraction(corpus):
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", corpus["date_extraction"])


def test_aucun_doublon(corpus):
    # le numero seul n'est pas unique dans le code complet : des annexes de
    # parties differentes s'appellent toutes "Annexe I" — l'unicite porte
    # sur l'id et sur le couple (numero, section)
    ids = [d["id"] for d in corpus["documents"]]
    cles = [(d["num"], d["chemin_section"]) for d in corpus["documents"]]
    assert len(ids) == len(set(ids))
    assert len(cles) == len(set(cles))


def test_tous_les_champs_remplis(corpus):
    for d in corpus["documents"]:
        for champ in ("id", "num", "texte", "theme", "chemin_section", "date_version"):
            assert str(d[champ]).strip(), f"{d['num']} : champ {champ} vide"


def test_numeros_au_format_legislatif(corpus):
    # formats legitimes : L/R/D + numeros (L3121-1, R*1233-3-4, "L1453-1 A"),
    # articles courts L1 a L3, et quelques annexes
    for d in corpus["documents"]:
        assert d["num"] == d["num"].strip(), repr(d["num"])
        assert re.fullmatch(r"[LRD]\*?\d+(-\d+)*( [A-Z])?|Annexe.*", d["num"]), repr(d["num"])


def test_texte_sans_html_ni_espaces_parasites(corpus):
    for d in corpus["documents"]:
        assert not re.search(r"<[^>]+>", d["texte"]), d["num"]
        assert not re.search(r"\s[,.;:)]", d["texte"]), d["num"]


# un article representatif par theme du tableau du sujet
ARTICLES_DES_THEMES = [
    "L3121-27",  # duree du travail et heures supplementaires
    "L3141-3",  # conges payes
    "L1221-2",  # contrat de travail (CDI, CDD)
    "L1234-1",  # licenciement
    "L1237-11",  # rupture conventionnelle
    "L3231-2",  # salaire minimum (SMIC)
    "L2311-2",  # representation du personnel
    "L1152-1",  # harcelement et discrimination
]


def test_les_huit_themes_du_sujet_sont_couverts(corpus):
    nums = {d["num"] for d in corpus["documents"]}
    for article in ARTICLES_DES_THEMES:
        assert article in nums, f"{article} absent du corpus"
