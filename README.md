# Chinois PWA

Application web perso pour apprendre le chinois : révisions espacées (FSRS), tri du vocabulaire par fréquence, écoute et dictée, dictionnaire, aide LLM.

- `backend/` : FastAPI + SQLAlchemy + SQLite (`chinois.db`), port `127.0.0.1:8290`
- `frontend/` : Vite + React + TypeScript + Tailwind
- `data/raw/` : dictionnaires téléchargés (non versionnés)

## Données

| Source | Usage | Licence |
| :--- | :--- | :--- |
| [CC-CEDICT](https://www.mdbg.net/chinese/dictionary?page=cc-cedict) | mots, lectures, sens anglais | CC BY-SA 4.0 |
| [CFDICT](https://chine.in/mandarin/dictionnaire/CFDICT/) | sens français | CC BY-SA |
| [complete-hsk-vocabulary](https://github.com/drkameleon/complete-hsk-vocabulary) | niveaux HSK 3.0 | MIT |
| `wordfreq` (PyPI) | rang de fréquence | CC BY-SA 4.0 |

Réimporter (sans risque : les mots existants sont mis à jour sur place, les id ne changent pas) :

```bash
cd backend
R=../data/raw
curl -sL -o $R/cedict/cedict.txt.gz https://www.mdbg.net/chinese/export/cedict/cedict_1_0_ts_utf-8_mdbg.txt.gz
curl -sL -o $R/cfdict/cfdict.u8 https://chine.in/assets/cfdict/cfdict.u8
curl -sL -o $R/hsk/complete.json https://raw.githubusercontent.com/drkameleon/complete-hsk-vocabulary/main/complete.json
.venv/bin/python -I scripts/import_dictionaries.py $R/cedict/cedict.txt.gz $R/cfdict/cfdict.u8 $R/hsk/complete.json
```

## Développement

```bash
# backend (dépendances de test et d'import : requirements-dev.txt)
cd backend && .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8290 --reload
cd backend && .venv/bin/python -m pytest -q tests

# frontend (NODE_ENV=production dans le shell empêche l'installation des devDependencies)
cd frontend && npm install --include=dev && npm run dev    # http://127.0.0.1:5173, /api est relayé vers :8290
```

Configuration dans `backend/.env` (modèle : `.env.example`). Le mot de passe de connexion est `ADMIN_PASSWORD`.
