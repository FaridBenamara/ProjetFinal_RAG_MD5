import logging
import os

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from groq import GroqError

from src.generator import Generator
from src.moderator import Moderator
from src.reformulator import Reformulator
from src.retriever import Retriever


class WebApp:
    # les memes classes et le meme chemin de code que la CLI

    def __init__(self, retriever, generator, reformulator, moderator):
        self.retriever = retriever
        self.generator = generator
        self.reformulator = reformulator
        self.moderator = moderator
        self.flask = Flask(__name__, template_folder="../templates")
        self.flask.get("/")(self.accueil)
        self.flask.post("/ask")(self.repondre)

    def accueil(self):
        return render_template("index.html", date_corpus=self.retriever.date_corpus())

    def repondre(self):
        corps = request.get_json(silent=True) or {}
        question = corps.get("question", "").strip()
        if not question:
            return jsonify({"erreur": "question manquante"}), 400
        historique = [tuple(echange[:2]) for echange in corps.get("historique", [])[-3:]]
        # une panne Groq (quota, reseau) ne doit pas finir en 500 brut
        try:
            return self._traiter(question, historique)
        except GroqError:
            return jsonify({"erreur": "service momentanément indisponible"}), 503

    def _traiter(self, question, historique):
        verdict = self.moderator.verifier(question)
        if verdict["classification"] != "LEGITIME":
            resultat = {
                "reponse": Moderator.REFUS[verdict["classification"]],
                "articles": [],
                "avertissement": Generator.AVERTISSEMENT,
                "confiance": 0.0,
                "confiance_faible": True,
            }
        else:
            question = self.reformulator.contextualiser(question, historique)
            reformulee = self.reformulator.reformuler(question)
            chunks = self.retriever.rechercher_hybride(
                question, k=10, question_vectorielle=reformulee
            )
            resultat = self.generator.repondre(question, chunks)

        resultat["date_corpus"] = self.retriever.date_corpus()
        return jsonify(resultat)


def creer_app():
    load_dotenv()
    logging.basicConfig(level=logging.WARNING)
    logging.getLogger("src.moderator").setLevel(logging.INFO)
    cle = os.environ["GROQ_API_KEY"]
    web = WebApp(Retriever(), Generator(cle), Reformulator(cle), Moderator(cle))
    return web.flask


app = creer_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
