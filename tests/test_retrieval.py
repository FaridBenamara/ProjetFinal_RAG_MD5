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


@pytest.mark.parametrize(
    "question,article_attendu",
    [
        ("Que dit l'article L3121-1 ?", "L3121-1"),
        ("que dit l. 3121-27 ?", "L3121-27"),
        ("Que contient R1234-4 ?", "R1234-4"),
    ],
)
def test_question_par_numero_remonte_l_article_en_tete(retriever, question, article_attendu):
    # le vectoriel pur classe ces articles au-dela du rang 30 : c'est la
    # recherche hybride qui garantit leur presence en tete
    chunks = retriever.rechercher_hybride(question, k=5)
    assert article_attendu in chunks[0]["nums"], question


def test_question_sans_numero_retombe_sur_le_vectoriel(retriever):
    # sans numero dans la question, les k premiers chunks sont ceux du
    # vectoriel ; seuls des renvois peuvent s'ajouter derriere
    hybride = retriever.rechercher_hybride("Combien de jours de congés payés par mois ?", k=5)
    vectoriel = retriever.rechercher("Combien de jours de congés payés par mois ?", k=5)
    assert [c["id"] for c in hybride[:5]] == [c["id"] for c in vectoriel]


def test_les_renvois_du_chunk_sont_ajoutes_au_contexte(retriever):
    # L1152-2 cite l'article L1121-2 dans son texte : il doit suivre
    chunks = retriever.rechercher_hybride("Que dit l'article L1152-2 ?", k=5)
    nums = [num for chunk in chunks for num in chunk["nums"]]
    assert "L1121-2" in nums


def test_les_renvois_sont_plafonnes(retriever):
    chunks = retriever.rechercher_hybride("Quelle est la durée légale de travail hebdomadaire ?", k=5)
    assert len(chunks) <= 5 + 4


def test_une_comparaison_couvre_les_deux_notions(retriever):
    # l'embedding d'une question comparative entiere ne colle a aucune des
    # deux notions : chacune doit etre cherchee separement
    question = (
        "Quelle est la différence entre la rupture conventionnelle "
        "et le licenciement pour motif économique ?"
    )
    nums = [n for c in retriever.rechercher_hybride(question, k=10) for n in c["nums"]]
    assert any(n.startswith("L1237") or n.startswith("D1237") for n in nums)
    assert any(n.startswith("L1233") or n.startswith("L1235") for n in nums)


def test_une_question_simple_ne_declenche_pas_la_comparaison(retriever):
    from src.retriever import COMPARAISON

    assert COMPARAISON.search("Quels sont mes droits en congés payés et RTT ?") is None
    assert COMPARAISON.search("Quelle différence entre un CDD et un CDI ?")
