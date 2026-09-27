# BeHave AI Assistant

Assistant conversationnel RAG (Retrieval-Augmented Generation) pour la suite
logicielle BeHave de Siryos, développé dans le cadre d'un stage d'ingénieur,
Département Data Science.

L'assistant répond aux questions des utilisateurs en s'appuyant exclusivement
sur la documentation officielle BeHave (guides PDF/DOCX/TXT indexés). Chaque
réponse affiche le module concerné et les extraits utilisés (document, page ou
section), lus dans les métadonnées de l'index, jamais générés par le LLM.

## Stack technique

| Composant | Technologie |
|---|---|
| Backend | FastAPI, SQLAlchemy, PostgreSQL, Alembic |
| Frontend | React, Vite, Tailwind CSS |
| Base vectorielle | ChromaDB |
| Embeddings | `intfloat/multilingual-e5-base` (FR/EN, recherche cross-lingue) |
| Reranking | Cross-encoder `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` |
| LLM | Groq API (`openai/gpt-oss-20b`) |
| Configuration | pydantic-settings (`config.py`, `.env`) |
| Authentification | JWT (HS256), rôles utilisateur / administrateur |

## Architecture du pipeline

```
Indexation (offline, ou à chaque upload admin)
  PDF / DOCX / TXT ──► segments (page PDF, section DOCX) ──► chunks ~1200 caractères
                       + module / titre déclarés dans data/manifest.yaml
                   ──► embeddings e5 ("titre — section" + texte) ──► ChromaDB

Question
  historique du chat (PostgreSQL, 10 derniers échanges, budget de tokens)
  question ──► recherche vectorielle top-20 ──► reranking cross-encoder
           ──► chunks au-dessus du seuil (top-4)
               ├─ aucun : réponse sans contexte (salutation ou refus), sans source
               └─ sinon : prompt contextualisé ──► Groq ──► réponse
                          module + sources = métadonnées des chunks retenus
```

Choix structurants :

- **Chaîne sans état.** La table `conversations` est la seule source de
  vérité de l'historique ; il est relu en base à chaque question. Aucun état
  en mémoire : le backend supporte le multi-worker et survit aux redémarrages.
- **Module et sources déterministes.** Le LLM ne produit que du texte ; module
  et sources viennent de la métadonnée du chunk le plus pertinent.
- **Métadonnées déclaratives.** Le module de chaque document est déclaré dans
  `data/manifest.yaml`, jamais déduit du nom de fichier.
- **Reranking à deux étages.** Les scores cosinus de l'embedding séparent mal
  questions pertinentes et hors sujet ; un cross-encoder reclasse les 20
  candidats et fournit le score utilisé pour décider du hors-périmètre.

## Structure du projet

```
behave-chatbot/
├── config.py                  # Configuration centralisée (pydantic-settings)
├── alembic.ini                # Migrations du schéma PostgreSQL
├── backend/                   # API FastAPI
│   ├── main.py                # Point d'entrée, routes chat / chats / santé
│   ├── manage.py              # Gestion des comptes en ligne de commande
│   ├── core/                  # Sécurité JWT, dépendances d'authentification, limite de requêtes
│   ├── database/              # Modèles SQLAlchemy, opérations CRUD
│   ├── migrations/            # Révisions Alembic
│   ├── routers/               # Authentification, administration documentaire
│   ├── schemas/               # Schémas Pydantic
│   └── services/              # Service documentaire (upload, indexation)
├── rag/                       # Pipeline RAG
│   ├── chain.py               # Orchestration : retrieval → prompt → Groq
│   ├── retriever.py           # Recherche vectorielle + reranking + seuil
│   ├── reranker.py            # Cross-encoder
│   └── prompt_builder.py      # Prompts (avec / sans contexte)
├── ingestion/                 # Indexation de la documentation
│   ├── run_indexation.py      # Script d'indexation complète
│   ├── pipeline.py            # Fichier → chunks (partagé avec l'upload admin)
│   ├── document_loader.py     # Extraction PDF / DOCX / TXT en segments
│   ├── chunker.py             # Découpage en chunks
│   ├── manifest.py            # Lecture / écriture de data/manifest.yaml
│   └── embedder.py            # Embeddings + ChromaDB
├── evaluation/                # Évaluation du retrieval
│   ├── eval_set.yaml          # Questions annotées (emplacement attendu)
│   ├── run_eval.py            # Métriques, calibration du seuil, latence
│   └── results.md             # Derniers résultats
├── frontend/                  # Application React
└── data/
    ├── manifest.yaml          # Module / titre de chaque document
    ├── documents/             # Documentation BeHave source (non versionné)
    ├── uploaded_docs/         # Documents ajoutés par l'admin (non versionné)
    └── chroma_db/             # Base vectorielle (non versionné)
```

## Prérequis

- Python 3.12
- Node.js 18+
- PostgreSQL (instance locale ou distante)
- Une clé API Groq (https://console.groq.com)

## Installation

Toutes les commandes Python s'exécutent **depuis la racine du projet**.

### 1. Backend

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
Copy-Item .env.example .env
```

Variables obligatoires dans `.env` (voir `.env.example` pour toutes les options) :

| Variable | Description |
|---|---|
| `JWT_SECRET_KEY` | Clé secrète de signature des tokens JWT |
| `DATABASE_URL` | Chaîne de connexion PostgreSQL |
| `GROQ_API_KEY` | Clé API Groq |

### 2. Base de données

```powershell
alembic upgrade head
```

Sur une base créée avant l'introduction d'Alembic (tables déjà présentes),
marquer d'abord le schéma initial comme appliqué, puis migrer :

```powershell
alembic stamp 0001
alembic upgrade head
```

### 3. Premier compte administrateur

Sur une base neuve, aucun compte n'existe et l'inscription publique ne crée
que des comptes `user`. Créer le premier administrateur, après
`alembic upgrade head` :

```powershell
python -m backend.manage create-user --username admin --role admin
```

Le mot de passe (8 caractères minimum) est demandé au clavier, deux fois, sans
être affiché. Les comptes se gèrent ensuite avec le même script :

| Commande | Effet |
|---|---|
| `python -m backend.manage create-user --username X [--role admin\|user]` | Crée un compte (rôle `user` par défaut) |
| `python -m backend.manage reset-password --username X` | Définit un nouveau mot de passe (y compris pour un admin qui a oublié le sien) |
| `python -m backend.manage set-role --username X --role admin\|user` | Promeut ou rétrograde un compte (le dernier admin ne peut pas être rétrogradé) |

Il n'y a pas de réinitialisation en libre-service : un utilisateur qui a
oublié son mot de passe s'adresse à un administrateur, qui utilise
`reset-password`.

Les tentatives de connexion sont limitées par adresse IP (`LOGIN_RATE_LIMIT`,
5 par minute par défaut) ; au-delà, l'API répond 429.

### 4. Indexation de la documentation

Placer les guides PDF/DOCX/TXT dans `data/documents/`, déclarer leur module
dans `data/manifest.yaml` :

```yaml
documents:
  BeHave_Master_Data_User_Guide.docx:
    module: BeHave Master Data
  User_Guide_PBI_BeHave.pdf:
    module: BeHave Analytics (Power BI)
    title: Guide utilisateur — BeHave Analytics (Power BI)   # optionnel
```

puis :

```powershell
python -m ingestion.run_indexation --reset
```

`--reset` est obligatoire après un changement de modèle d'embedding (l'index
enregistre le modèle utilisé ; le backend refuse de démarrer sur un index
incompatible). Les documents uploadés par l'admin (`data/uploaded_docs/`)
sont réindexés eux aussi.

### 5. Démarrage du backend

```powershell
uvicorn backend.main:app --reload
```

API sur `http://127.0.0.1:8000`, documentation Swagger sur `/docs`.
Au premier lancement, les modèles d'embedding et de reranking sont
téléchargés depuis Hugging Face (~1,5 Go).

### 6. Frontend

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```

Application sur `http://127.0.0.1:5173`.

## Évaluation

```powershell
python -m evaluation.run_eval --rerankers mmarco bge --output evaluation/results.md
```

Le script compare le classement cosinus seul et un ou plusieurs rerankers
sur `evaluation/eval_set.yaml` : qualité du classement (hit@k, MRR), séparation
périmètre / hors périmètre (AUC, seuil optimal), latence CPU. Les résultats
détaillés sont dans [evaluation/results.md](evaluation/results.md).

Résultats actuels (55 questions : 39 BeHave, 16 hors périmètre dont 6 de
domaine proche ; seuils de production) :

| Configuration | doc@1 | loc@4 | MRR@4 | AUC | Questions BeHave acceptées | Hors sujet rejetés | Reranking (CPU) |
|---|---|---|---|---|---|---|---|
| Cosinus seul (seuil 0.81) | 0.90 | 0.92 | 0.81 | 0.96 | 95 % | 75 % | — |
| + reranker mMiniLM (seuil 0.75) | **1.00** | **0.97** | **0.95** | **0.99** | 90 % | **100 %** | ~1,2 s |

Le reranker élimine les faux positifs sur les questions de domaine proche
(installation Python, Wi-Fi, SAP MM…), au prix de quelques questions BeHave
rejetées ; ce compromis et le choix de ne pas évaluer `bge-reranker-v2-m3`
sont justifiés dans [evaluation/results.md](evaluation/results.md).

## Fonctionnalités

- **Pipeline RAG** sur la documentation officielle BeHave, avec module et
  sources (document, page ou section) issus des métadonnées de l'index.
- **Conversations multiples** par utilisateur, historique persistant en base,
  auto-renommage à la première question, réinitialisation d'un chat
  (les échanges restent visibles dans l'historique admin).
- **Interface d'administration** : ajout de documents avec module et titre,
  suppression, historique des conversations de tous les utilisateurs.
- **Authentification JWT** avec rôles utilisateur / administrateur, vérifiés
  en base à chaque requête ; limite de tentatives de connexion par IP ;
  comptes administrés par `python -m backend.manage`.
- **Dictée vocale** (Web Speech API) et questions multilingues (FR/EN).

## Auteure

Maram Bouchrit — stage d'ingénieur, ENICarthage / Siryos, Été 2026.
