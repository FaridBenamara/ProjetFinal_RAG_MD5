from pathlib import Path

from groq import Groq, GroqError

# un petit modele suffit pour traduire une question, et son quota Groq est
# distinct de celui du modele de generation
MODELE = "llama-3.1-8b-instant"
PROMPT_SYSTEME = (Path(__file__).parent.parent / "prompts" / "reformulator_system.txt").read_text(
    encoding="utf-8"
)


class Reformulator:
    # traduit la question de l'utilisateur en vocabulaire du Code du travail,
    # uniquement pour la recherche — la generation repond a la question originale

    def __init__(self, api_key, model=MODELE):
        self.client = Groq(api_key=api_key)
        self.model = model

    def reformuler(self, question):
        # en cas d'echec de l'appel, la question brute fait l'affaire :
        # la reformulation ameliore le pipeline, elle ne doit jamais le casser
        try:
            return self._appeler_llm(question)
        except GroqError:
            return question

    def _appeler_llm(self, question):
        completion = self.client.chat.completions.create(
            messages=[
                {"role": "system", "content": PROMPT_SYSTEME},
                {"role": "user", "content": question},
            ],
            model=self.model,
            temperature=0,
            max_tokens=150,
        )
        return completion.choices[0].message.content.strip()


if __name__ == "__main__":
    import os
    import sys

    from dotenv import load_dotenv

    load_dotenv()
    reformulator = Reformulator(os.environ["GROQ_API_KEY"])

    question = " ".join(sys.argv[1:]) or "JE TRAVAILLE 45H EN CDI JAI LE DROIT OU PAS"
    print(f"question    : {question}")
    print(f"reformulee  : {reformulator.reformuler(question)}")
