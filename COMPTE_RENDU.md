# Compte rendu — Assistant Code du travail (RAG)

## Difficultés rencontrées

La première a été bête : nos identifiants PISTE étaient des identifiants de
production, et le client attaquait les URLs sandbox — deux erreurs 400 avant de
comprendre que le problème n'était pas OAuth2 mais l'environnement visé.

Les données Légifrance sont moins propres qu'attendu. Des articles sont rattachés à
deux sections de l'arborescence (doublons silencieux), de rares articles existent en
deux versions simultanément « en vigueur » (défaut de consolidation, il faut garder la
rédaction la plus récente), la numérotation n'est pas homogène (« L1453-1 A », des
numéros de l'ancien code d'avant 2008), et certaines annexes réglementaires font plus
de 100 000 caractères — inutilisables telles quelles dans un contexte LLM.

Le retrieval nous a appris l'humilité en quatre leçons. Un, l'embedding multilingue est
très sensible à la forme : sans accents ou avec des sigles (« SMIC », « CDI »), les
distances s'effondrent — le corpus ne contient jamais ces sigles. Deux, notre premier
seuil de refus (0,45), calibré sur un échantillon trop petit, refusait des questions
parfaitement légitimes ; c'est une session manuelle qui l'a révélé (« comment
fonctionne la rupture conventionnelle ? » refusée), et il a été recalibré à 0,55 sur
une base de mesures élargie. Trois, en passant de 722 à 10 767 chunks, les articles
attendus se sont fait évincer du top-5 par des voisins tangentiels : k a dû passer de
5 à 10, mesures à l'appui. Quatre, découverte une fois l'application déployée : « la
période de préavis pour un CDI » était refusée, parce que l'article du barème du
préavis (L1234-1) ne prononce jamais les mots « contrat à durée indéterminée » —
l'embedding le classait au-delà du rang 100, aucune reformulation n'y suffisait. Le
correctif a été une recherche par mots-clés (BM25 écrit à la main) fusionnée au
vectoriel par meilleur rang, qui repêche ces cas sans dégrader les autres.

Enfin, le petit modèle de reformulation a halluciné de trois façons (un chiffre
inventé, des méta-réponses au lieu de reformuler, le contenu supposé d'un article cité
par numéro) — trois règles ajoutées au prompt, et la détection des numéros d'articles
se fait sur la question originale, jamais sur la reformulée. Les quotas Groq (100 000
tokens/jour, par organisation et non par clé) ont été épuisés deux fois par nos bancs
de test.

## Décisions de conception

Le refus hors-corpus est à deux étages : un seuil de distance dans le code (gratuit,
déterministe) pour le clairement hors-sujet, le prompt pour la zone grise — vérifié
sur dix questions juridiques d'autres codes, toutes refusées. L'avertissement
juridique est concaténé par le code du générateur, jamais délégué au prompt. La
reformulation sert à chercher, jamais à répondre. Les tâches simples (reformulation,
modération) tournent sur un petit modèle au quota distinct du modèle de génération.
Le corpus couvre tout le Code du travail en vigueur (L, R et D) ; le chunking reste
« un article = un chunk », avec fusion des articles courts et découpe des annexes
géantes aux frontières de phrases. Les renvois entre articles sont suivis à un saut
pour ramener au contexte les voisins cités. Chaque calibrage (seuil, k, choix de
modèle) est adossé à un banc de 30 questions rejouable.

Une session réelle a bien illustré l'ensemble : un étudiant algérien en CDD demandant
s'il est soumis à autorisation de travail a reçu une réponse correcte et sourcée sur
le régime général des étudiants étrangers (R5221-1, R5221-26 — des articles
réglementaires, impossibles à trouver avec un corpus limité à la partie L). Mais à la
relance « même si je suis algérien ? », le système a répondu « je ne trouve pas cette
information dans ma base » : le cas algérien relève de l'accord franco-algérien de
1968, un traité bilatéral qui n'est pas dans le Code du travail. Refuser plutôt
qu'inventer, c'est le comportement voulu — et c'est la limite structurelle à
connaître : le droit applicable ne se réduit pas au Code (conventions collectives,
accords internationaux). Sur la même session, le modérateur a produit un faux positif
sur une question en majuscules mal orthographiée, que l'utilisateur a contournée en
reformulant — défaut mineur assumé.

## Avec plus de temps

Un reranking par cross-encoder : notre seul mode d'échec résiduel mesuré (1 question
sur 30) est un article présent au rang 9 mais noyé — un reranker le remonterait. La
décomposition des questions multi-facettes en sous-questions, sur détection plutôt que
systématique. Un historique de conversation pour les questions de suivi. La détection
des réformes déjà votées mais pas encore en vigueur (les données portent des dates de
fin de version futures). Et l'automatisation du banc de 30 questions en évaluation
continue, pour mesurer chaque changement au lieu de le rejouer à la main.
