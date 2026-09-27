## Décisions

**Reranker par défaut : `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`.**
Par rapport au classement cosinus seul, il place le bon document en première
position pour 100 % des questions du périmètre (contre 90 %) et rejette 100 %
des questions hors périmètre, pour ~1,5 s de reranking par question sur CPU
(20 candidats).

**`BAAI/bge-reranker-v2-m3` non évalué.** Modèle de 2,2 Go (568 M de
paramètres, ~4,8× mMiniLM) : sa latence sur CPU n'est pas compatible avec un
usage interactif sur la machine de développement (un premier lancement du
benchmark a été interrompu après plus d'une heure de calcul). Le gain possible
porte sur les rares questions du périmètre rejetées par mMiniLM (voir
« Erreurs au seuil retenu ») ; il reste à mesurer si le jeu d'évaluation
s'enrichit ou si un GPU est disponible. Le modèle est configurable par
`RERANKER_MODEL` et comparable en une commande :
`python -m evaluation.run_eval --rerankers mmarco bge`.

**Seuil `RAG_MIN_RERANK_SCORE = 0.75`.** Placé dans l'écart entre la question
hors périmètre la mieux notée (« Bonjour », 0.676) et la question du périmètre
acceptée la moins bien notée (0.817), plutôt que sur le seuil optimal exact de
ce jeu (surajusté). Abaisser le seuil pour récupérer les questions rejetées
ferait accepter salutations et questions SAP hors documentation, qui
recevraient alors des sources sans rapport.

**Mode sans reranker** (`RERANKER_ENABLED=false`) : seuil cosinus 0.81,
nettement moins discriminant (AUC 0.964 contre 0.987, 0.908 contre 0.987 sur
les questions de domaine proche).
