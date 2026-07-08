import os
import time

import requests
from dotenv import load_dotenv

TOKEN_URL = "https://oauth.piste.gouv.fr/api/oauth/token"
BASE_URL = "https://api.piste.gouv.fr/dila/legifrance/lf-engine-app"
MARGE_EXPIRATION = 60  # secondes, renouvelle le jeton avant qu'il expire vraiment


class LegifranceClient:
    # auth OAuth2 client credentials + appels a l'API PISTE

    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret
        self._token = None
        self._expire_a = 0

    def _renouveler_token(self):
        reponse = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": "openid",
            },
            timeout=10,
        )
        reponse.raise_for_status()
        data = reponse.json()
        self._token = data["access_token"]
        self._expire_a = time.time() + data["expires_in"]

    def appeler(self, endpoint, payload):
        if self._token is None or time.time() > self._expire_a - MARGE_EXPIRATION:
            self._renouveler_token()

        headers = {"Authorization": f"Bearer {self._token}"}
        reponse = requests.post(BASE_URL + endpoint, json=payload, headers=headers, timeout=10)

        if reponse.status_code == 401:
            self._renouveler_token()
            headers["Authorization"] = f"Bearer {self._token}"
            reponse = requests.post(BASE_URL + endpoint, json=payload, headers=headers, timeout=10)

        reponse.raise_for_status()
        return reponse.json()


if __name__ == "__main__":
    load_dotenv()
    client = LegifranceClient(os.environ["PISTE_CLIENT_ID"], os.environ["PISTE_CLIENT_SECRET"])
    resultat = client.appeler("/consult/getArticle", {"id": "LEGIARTI000006900783"})
    print("Appel OK, article", resultat["article"]["num"])
