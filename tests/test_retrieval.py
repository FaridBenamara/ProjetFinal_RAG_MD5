import pytest

from src.retriever import Retriever

# 5 questions dont l'article attendu est connu, une par theme.
# Le libelle colle au vocabulaire du code : le corpus ne connait pas les
# sigles (SMIC, CDD) ni les tournures familieres — voir README.
QUESTIONS = [
    ("Quelle est la durée légale de travail hebdomadaire ?", "L3121-27"),
    ("Combien de jours de congés payés par mois de travail ?", "L3141-3"),
    ("Qu'est-ce que le harcèlement moral ?", "L1152-1"),
    ("Que doit contenir la convention de rupture conventionnelle ?", "L1237-13"),
    (
        "À partir de combien de salariés un comité social et économique est-il obligatoire ?",
        "L2311-2",
    ),
]


@pytest.fixture(scope="module")
def retriever():
    return Retriever()


@pytest.mark.parametrize("question,article_attendu", QUESTIONS)
def test_article_attendu_dans_le_top5(retriever, question, article_attendu):
    chunks = retriever.rechercher(question, k=5)
    nums_trouves = [num for chunk in chunks for num in chunk["nums"]]
    assert article_attendu in nums_trouves, (
        f"{article_attendu} absent du top-5 pour « {question} » : {nums_trouves}"
    )
