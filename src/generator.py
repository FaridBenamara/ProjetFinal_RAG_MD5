from pathlib import Path

from groq import Groq

MODELE = "llama-3.3-70b-versatile"
PROMPT_SYSTEME = (Path(__file__).parent.parent / "prompts" / "generator_system.txt").read_text(
    encoding="utf-8"
)


class Generator:
    AVERTISSEMENT = (
        "Cet assistant ne fournit pas de conseil juridique. Consultez un avocat "
        "ou l'inspection du travail pour votre situation personnelle."
    )
    REFUS = "Je ne trouve pas cette information dans ma base."
    # mesure sur le corpus : questions du domaine 0.17-0.38, hors sujet 0.56-0.88
    SEUIL_DISTANCE = 0.45

    def __init__(self, api_key, model=MODELE):
        self.client = Groq(api_key=api_key)
        self.model = model

    def repondre(self, question, chunks):
        # le refus hors corpus est decide par le code, avant tout appel au LLM
        if self._hors_corpus(chunks):
            return self._refus()
        reponse = self._appeler_llm(question, chunks)
        # le LLM peut aussi refuser (contexte remonte mais hors sujet) :
        # dans ce cas les chunks n'ont pas servi, on n'affiche pas de sources
        if self.REFUS in reponse:
            return self._refus()
        return {
            "reponse": reponse,
            "articles": [num for chunk in chunks for num in chunk["nums"]],
            "avertissement": self.AVERTISSEMENT,
        }

    def _refus(self):
        return {"reponse": self.REFUS, "articles": [], "avertissement": self.AVERTISSEMENT}

    def _hors_corpus(self, chunks):
        return not chunks or min(c["distance"] for c in chunks) > self.SEUIL_DISTANCE

    def _appeler_llm(self, question, chunks):
        completion = self.client.chat.completions.create(
            messages=[
                {"role": "system", "content": PROMPT_SYSTEME.format(contexte=self._contexte(chunks))},
                {"role": "user", "content": question},
            ],
            model=self.model,
            temperature=0.1,
        )
        return completion.choices[0].message.content

    def _contexte(self, chunks):
        return "\n\n".join(f"[{i}] {chunk['texte']}" for i, chunk in enumerate(chunks, 1))


if __name__ == "__main__":
    import os
    import sys

    from dotenv import load_dotenv

    from src.retriever import Retriever

    load_dotenv()
    retriever = Retriever()
    generator = Generator(os.environ["GROQ_API_KEY"])

    question = " ".join(sys.argv[1:]) or "Quelle est la durée légale de travail hebdomadaire ?"
    chunks = retriever.rechercher(question)
    resultat = generator.repondre(question, chunks)
    print(f"Q : {question}\n")
    print(resultat["reponse"])
    print(f"\nSources : {', '.join(resultat['articles'])}")
    print(f"\n{resultat['avertissement']}")
