from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from comptis.interface.api.admin.integrations.router import router as admin_integrations_router
from comptis.interface.api.auth.router import router as auth_router
from comptis.interface.api.rapprochement.router import router as rapprochement_router

app = FastAPI(title="Comptis API", version="0.1.0")

app.include_router(auth_router)
app.include_router(rapprochement_router)
app.include_router(admin_integrations_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


# Servir le frontend buildé (prod uniquement — ignoré si dist/ n'existe pas)
_dist = Path(__file__).parent.parent.parent.parent.parent / "frontend" / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="frontend")
