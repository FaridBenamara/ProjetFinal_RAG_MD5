import os

from dotenv import load_dotenv
from groq import GroqError

from src.generator import Generator
from src.retriever import Retriever


class ChatCLI:
    # boucle question-reponse en terminal, /quit pour sortir

    def __init__(self, retriever, generator):
        self.retriever = retriever
        self.generator = generator

    def lancer(self):
        print(f"Assistant Code du travail — corpus du {self.retriever.date_corpus()}")
        print("Posez votre question (/quit pour quitter)")
        while True:
            try:
                question = input("\n> ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nAu revoir.")
                break
            if question == "/quit":
                print("Au revoir.")
                break
            if question:
                self._repondre_sans_planter(question)

    def _repondre_sans_planter(self, question):
        # une erreur Groq (reseau, quota, cle) ne doit pas tuer la session
        try:
            self._repondre(question)
        except GroqError as erreur:
            print(f"\nErreur lors de l'appel au modèle : {erreur}")
            print("Réessayez, ou vérifiez la clé GROQ_API_KEY et votre connexion.")

    def _repondre(self, question):
        chunks = self.retriever.rechercher(question)
        resultat = self.generator.repondre(question, chunks)
        print(f"\n{resultat['reponse']}")
        if resultat["articles"]:
            print(f"\nSources : {', '.join(resultat['articles'])}")
        print(f"\n{resultat['avertissement']}")


if __name__ == "__main__":
    load_dotenv()
    cli = ChatCLI(Retriever(), Generator(os.environ["GROQ_API_KEY"]))
    cli.lancer()
