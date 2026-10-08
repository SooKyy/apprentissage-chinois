from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import Base, engine
from app.routers import assist, auth, media, prefs, review, stats, triage, words
from app.security import require_auth

settings = get_settings()
Base.metadata.create_all(bind=engine)
# create_all ne touche pas aux tables déjà créées : on y ajoute les index déclarés depuis
for table in Base.metadata.sorted_tables:
    for index in table.indexes:
        index.create(bind=engine, checkfirst=True)

app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
for module in (words, review, triage, stats, media, assist, prefs):
    app.include_router(module.router, dependencies=[Depends(require_auth)])


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
