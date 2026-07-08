from src.chunking import Chunker


def doc(num, texte, section="Section 1", **extra):
    return {
        "id": f"ID-{num}",
        "num": num,
        "texte": texte,
        "theme": extra.get("theme", "Test"),
        "chemin_section": section,
        "date_version": "2026-01-01",
    }


def test_un_article_long_donne_un_chunk():
    documents = [doc("L1111-1", "x" * 300)]
    chunks = Chunker().decouper(documents)
    assert len(chunks) == 1
    assert chunks[0].nums == ["L1111-1"]


def test_article_court_regroupe_avec_son_voisin_de_section():
    documents = [doc("L1111-1", "x" * 300), doc("L1111-2", "court")]
    chunks = Chunker().decouper(documents)
    assert len(chunks) == 1
    assert chunks[0].nums == ["L1111-1", "L1111-2"]


def test_article_court_jamais_regroupe_hors_de_sa_section():
    documents = [
        doc("L1111-1", "x" * 300, section="Section 1"),
        doc("L2222-1", "court", section="Section 2"),
    ]
    chunks = Chunker().decouper(documents)
    assert len(chunks) == 2


def test_aucun_article_perdu_ni_duplique():
    documents = [doc(f"L1111-{i}", "x" * (50 if i % 3 == 0 else 300)) for i in range(1, 30)]
    chunks = Chunker().decouper(documents)
    nums = [n for c in chunks for n in c.nums]
    assert sorted(nums) == sorted(d["num"] for d in documents)
    assert len(nums) == len(set(nums))


def test_le_numero_et_la_section_sont_dans_le_texte_embedde():
    documents = [doc("L1234-5", "contenu de l'article", section="Livre I > Titre II")]
    chunks = Chunker().decouper(documents)
    assert "L1234-5" in chunks[0].texte
    assert "Titre II" in chunks[0].texte
    assert "contenu de l'article" in chunks[0].texte


def test_texte_jamais_coupe():
    texte_long = "phrase " * 500
    chunks = Chunker().decouper([doc("L1111-1", texte_long)])
    assert texte_long.strip() in chunks[0].texte
