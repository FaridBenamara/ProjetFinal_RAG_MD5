import logging
import os

from dotenv import load_dotenv
from groq import GroqError

from src.generator import Generator
from src.moderator import Moderator
from src.reformulator import Reformulator
from src.retriever import Retriever


class ChatCLI:
    # boucle question-reponse en terminal, /quit pour sortir

    def __init__(self, retriever, generator, reformulator, moderator):
        self.retriever = retriever
        self.generator = generator
        self.reformulator = reformulator
        self.moderator = moderator

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
        # le moderateur passe en premier : une question rejetee n'entre
        # jamais dans le retrieval ni dans le prompt du generateur
        verdict = self.moderator.verifier(question)
        if verdict["classification"] != "LEGITIME":
            print(f"\n{Moderator.REFUS[verdict['classification']]}")
            print(f"\n{self.generator.AVERTISSEMENT}")
            return
        # la recherche se fait sur la question reformulee en vocabulaire
        # juridique, la reponse porte sur la question originale
        reformulee = self.reformulator.reformuler(question)
        if reformulee != question:
            print(f"(recherche : {reformulee})")
        # k=10 : sur le corpus complet (10 700 chunks), l'article attendu
        # tombe parfois aux rangs 6-10, evince par des voisins tangentiels ;
        # mesure sur banc de test, k=5 en ratait 3 sur 5.
        # les numeros d'articles sont detectes sur la question originale,
        # la reformulation pourrait les alterer
        chunks = self.retriever.rechercher_hybride(
            question, k=10, question_vectorielle=reformulee
        )
        resultat = self.generator.repondre(question, chunks)
        print(f"\n{resultat['reponse']}")
        if resultat["articles"]:
            print(f"\nSources : {', '.join(resultat['articles'])}")
            print(f"Confiance : {resultat['confiance']:.0%}", end="")
            if resultat["confiance_faible"]:
                print(" — indices faibles, réponse à confirmer auprès d'un professionnel", end="")
            print()
        print(f"\n{resultat['avertissement']}")
        print(f"(corpus Légifrance du {self.retriever.date_corpus()})")


if __name__ == "__main__":
    load_dotenv()
    # les verdicts de moderation sont logges, le reste reste silencieux
    logging.basicConfig(level=logging.WARNING, format="[%(levelname)s] %(message)s")
    logging.getLogger("src.moderator").setLevel(logging.INFO)
    cle = os.environ["GROQ_API_KEY"]
    cli = ChatCLI(Retriever(), Generator(cle), Reformulator(cle), Moderator(cle))
    cli.lancer()
