from groq import Groq

MODELE = "llama-3.3-70b-versatile"

PROMPT_SYSTEME = """Tu es un assistant spécialisé en droit du travail français.
Tu réponds uniquement à partir des articles fournis dans le contexte ci-dessous.

Règles :
- chaque affirmation cite le numéro de l'article dont elle vient (ex. « article L3121-27 ») ;
- tu ne cites jamais un numéro absent du contexte ;
- si le contexte ne permet pas de répondre, tu réponds exactement : « Je ne trouve pas cette information dans ma base. » ;
- si la réponse dépend de la taille de l'entreprise, d'une convention collective ou d'un accord d'entreprise, tu le signales ;
- si la question demande d'apprécier une situation personnelle (« mon licenciement est-il abusif ? »), tu donnes le cadre légal puis tu invites à consulter un avocat ou l'inspection du travail, sans conclure sur le cas particulier ;
- tu n'ajoutes pas d'avertissement général en fin de réponse, il est ajouté automatiquement.

Contexte :
{contexte}"""


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
            return {"reponse": self.REFUS, "articles": [], "avertissement": self.AVERTISSEMENT}
        return {
            "reponse": self._appeler_llm(question, chunks),
            "articles": [num for chunk in chunks for num in chunk["nums"]],
            "avertissement": self.AVERTISSEMENT,
        }

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
