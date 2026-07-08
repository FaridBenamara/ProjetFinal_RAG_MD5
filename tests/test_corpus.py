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
    ids = [d["id"] for d in corpus["documents"]]
    nums = [d["num"] for d in corpus["documents"]]
    assert len(ids) == len(set(ids))
    assert len(nums) == len(set(nums))


def test_tous_les_champs_remplis(corpus):
    for d in corpus["documents"]:
        for champ in ("id", "num", "texte", "theme", "chemin_section", "date_version"):
            assert str(d[champ]).strip(), f"{d['num']} : champ {champ} vide"


def test_numeros_au_format_legislatif(corpus):
    for d in corpus["documents"]:
        assert re.fullmatch(r"L\d{4}(-\d+)*", d["num"]), d["num"]


def test_texte_sans_html_ni_espaces_parasites(corpus):
    for d in corpus["documents"]:
        assert not re.search(r"<[^>]+>", d["texte"]), d["num"]
        assert not re.search(r"\s[,.;:)]", d["texte"]), d["num"]


def test_les_huit_themes_du_sujet_sont_couverts(corpus):
    themes = {d["theme"] for d in corpus["documents"]}
    assert len(themes) == 8
