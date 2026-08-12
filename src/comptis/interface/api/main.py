from fastapi import FastAPI

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
