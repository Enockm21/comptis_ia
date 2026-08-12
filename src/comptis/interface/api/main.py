from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from comptis.interface.api.admin.integrations.router import router as admin_integrations_router
from comptis.interface.api.auth.router import router as auth_router
from comptis.interface.api.rapprochement.router import router as rapprochement_router
from comptis.interface.api.tenancy.router import router as tenancy_router

app = FastAPI(title="Comptis API", version="0.1.0")

app.include_router(auth_router)
app.include_router(rapprochement_router)
app.include_router(admin_integrations_router)
app.include_router(tenancy_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


# Servir le frontend buildé (prod uniquement — ignoré si dist/ n'existe pas)
_dist = Path(__file__).parent.parent.parent.parent.parent / "frontend" / "dist"
if _dist.exists():
    app.mount("/assets", StaticFiles(directory=str(_dist / "assets")), name="frontend-assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(request: Request, full_path: str) -> FileResponse:
        """SPA fallback: serve a real static file if it exists on disk (e.g. favicon,
        manifest), otherwise fall back to index.html so client-side routes like
        /login or /reconciliation are handled by the React router instead of 404ing.

        Registered after the API routers, so it only matches requests none of them
        claimed (e.g. FastAPI already 405s /reconciliation/run for GET before this
        route is ever considered).
        """
        candidate = _dist / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_dist / "index.html")
