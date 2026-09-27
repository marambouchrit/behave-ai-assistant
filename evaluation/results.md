# Évaluation du retrieval BeHave

Généré le 2026-09-27 par `python -m evaluation.run_eval`.

- Jeu : 55 questions (39 dans le périmètre, 16 hors périmètre dont 6 de domaine proche)
- Index : 155 chunks, embeddings `intfloat/multilingual-e5-base`
- Premier étage : top-20 vectoriel (42 ms/question) ; k = 4 chunks transmis au LLM
- Latences mesurées sur CPU

| Configuration | doc@1 | doc@4 | loc@4 | MRR@4 | AUC | AUC (hard) | seuil optimal | seuil | TPR | TNR | bout-en-bout | ms/question | p95 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cosine (sans reranker) | 0.897 | 0.974 | 0.923 | 0.814 | 0.964 | 0.908 | 0.842 | 0.810 | 0.949 | 0.750 | 0.872 | 0.000 | 0.000 |
| cross-encoder/mmarco-mMiniLMv2-L12-H384-v1 | 1.000 | 1.000 | 0.974 | 0.949 | 0.987 | 0.987 | 0.817 | 0.750 | 0.897 | 1.000 | 0.872 | 1274 | 1511 |

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

## Erreurs au seuil retenu

**cosine (sans reranker)** (seuil 0.810)
- faux négatifs (question BeHave rejetée) : pred-format-fichier, pred-metriques
- faux positifs (hors sujet accepté) : hard-excel-tcd, hard-prix, hard-sap-mm, hard-wifi
- localisation manquée dans le top-4 : pbi-user-360, pred-modeles-fr, sap-mandant

**cross-encoder/mmarco-mMiniLMv2-L12-H384-v1** (seuil 0.750)
- faux négatifs (question BeHave rejetée) : md-fournisseur, pred-metriques, pred-statut-failed-fr, sap-mandant
- faux positifs (hors sujet accepté) : aucun
- localisation manquée dans le top-4 : pred-modeles-fr

## Annexe : meilleur score par question

Trié par score du dernier modèle ; ✗ = hors périmètre.

| Question | cosine (sans reranker) | cross-encoder/mmarco-mMiniLMv2-L12-H384-v1 |
|---|---|---|
| acc-definition | 0.867 | 1.000 |
| acc-avantages-fr | 0.881 | 1.000 |
| pred-public | 0.903 | 1.000 |
| md-definition | 0.931 | 1.000 |
| md-template-client | 0.909 | 1.000 |
| md-articles | 0.887 | 1.000 |
| acc-upload-config-fr | 0.878 | 1.000 |
| pbi-roles-non-assignes | 0.861 | 1.000 |
| pbi-actions-correctives | 0.891 | 1.000 |
| md-run-id | 0.895 | 1.000 |
| pbi-terminal-suspect | 0.868 | 1.000 |
| md-hcm-en | 0.842 | 1.000 |
| pbi-clusters | 0.868 | 1.000 |
| pbi-unlocking-en | 0.851 | 0.999 |
| pbi-score-25 | 0.865 | 0.999 |
| pbi-user-360 | 0.838 | 0.999 |
| pred-admin-compte-fr | 0.851 | 0.999 |
| pbi-score-calcul | 0.887 | 0.999 |
| sap-logs-securite | 0.890 | 0.999 |
| sap-meme-date | 0.844 | 0.999 |
| pbi-sod-risque-violation | 0.869 | 0.998 |
| sap-agr-users | 0.856 | 0.997 |
| pbi-login-anomalies | 0.855 | 0.997 |
| pbi-roles-redondants | 0.869 | 0.996 |
| pbi-tcodes-sans-objet | 0.844 | 0.995 |
| md-envoi-agent | 0.871 | 0.995 |
| pbi-licences | 0.880 | 0.995 |
| pred-modeles-fr | 0.853 | 0.992 |
| pbi-comptes-inactifs | 0.860 | 0.992 |
| sap-transaction | 0.884 | 0.991 |
| md-centre-cout | 0.858 | 0.986 |
| pred-upload-echec | 0.856 | 0.965 |
| pred-historique-fr | 0.819 | 0.940 |
| acc-notifications-fr | 0.829 | 0.902 |
| pred-format-fichier | 0.807 | 0.817 |
| out-bonjour ✗ | 0.774 | 0.676 |
| md-fournisseur | 0.868 | 0.581 |
| hard-sap-mm ✗ | 0.844 | 0.471 |
| pred-metriques | 0.809 | 0.388 |
| sap-mandant | 0.846 | 0.215 |
| out-merci ✗ | 0.798 | 0.191 |
| pred-statut-failed-fr | 0.819 | 0.124 |
| hard-python ✗ | 0.794 | 0.043 |
| hard-wifi ✗ | 0.818 | 0.025 |
| hard-prix ✗ | 0.837 | 0.022 |
| hard-excel-tcd ✗ | 0.840 | 0.022 |
| hard-premiere ✗ | 0.791 | 0.011 |
| out-poeme ✗ | 0.793 | 0.008 |
| out-crepes ✗ | 0.796 | 0.004 |
| out-meteo ✗ | 0.806 | 0.002 |
| out-foot ✗ | 0.737 | 0.001 |
| out-calcul ✗ | 0.796 | 0.001 |
| out-relativite ✗ | 0.807 | 0.001 |
| out-capitale ✗ | 0.754 | 0.001 |
| out-film ✗ | 0.774 | 0.001 |

## Lecture

- **doc@k / loc@k / MRR@k** : qualité du classement sur les 39 questions du périmètre.
- **AUC** : séparation entre questions du périmètre et hors périmètre par le meilleur score (1.0 = un seuil peut tout séparer). **AUC (hard)** : idem contre les seules questions de domaine proche.
- **seuil optimal** : seuil maximisant (TPR + TNR) / 2 sur ce jeu. **seuil** : seuil appliqué (configuré avec `--use-configured-thresholds`, sinon l'optimal).
- **TPR / TNR** : questions du périmètre acceptées / hors périmètre rejetées au seuil appliqué.
- **bout-en-bout** : question du périmètre acceptée ET bon emplacement dans le top-k.
- Jeu de petite taille : les écarts de quelques points ne sont pas significatifs.
