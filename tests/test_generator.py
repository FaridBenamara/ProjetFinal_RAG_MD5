from src.generator import Generator

# le chemin de refus est du pur code, testable sans cle API
generator = Generator.__new__(Generator)


def test_l_avertissement_est_le_texte_exact_du_sujet():
    assert Generator.AVERTISSEMENT == (
        "Cet assistant ne fournit pas de conseil juridique. Consultez un avocat "
        "ou l'inspection du travail pour votre situation personnelle."
    )


def test_le_refus_porte_toujours_l_avertissement():
    resultat = generator._refus()
    assert resultat["avertissement"] == Generator.AVERTISSEMENT
    assert resultat["articles"] == []


def test_le_refus_est_decide_par_le_code_sur_le_seuil():
    chunks_lointains = [{"distance": 0.9, "nums": ["L1111-1"]}]
    assert generator._hors_corpus(chunks_lointains)
    assert not generator._hors_corpus([{"distance": 0.2, "nums": ["L1111-1"]}])
    assert generator._hors_corpus([])
