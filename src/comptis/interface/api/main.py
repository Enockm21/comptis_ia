from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from comptis.interface.api.admin.comptabilite.router import router as admin_comptabilite_router
from comptis.interface.api.admin.integrations.router import router as admin_integrations_router
from comptis.interface.api.auth.router import router as auth_router
from comptis.interface.api.categorization.router import router as categorization_router
from comptis.interface.api.rapprochement.router import router as rapprochement_router
from comptis.interface.api.tenancy.router import router as tenancy_router

app = FastAPI(title="Comptis API", version="0.1.0")

app.include_router(auth_router)
app.include_router(rapprochement_router)
app.include_router(admin_integrations_router)
app.include_router(admin_comptabilite_router)
app.include_router(tenancy_router)
app.include_router(categorization_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


# Servir le frontend buildé (prod uniquement — ignoré si dist/ n'existe pas)
_dist = Path(__file__).parent.parent.parent.parent.parent / "frontend" / "dist"
if _dist.exists():
    app.mount(
        "/assets",
        StaticFiles(directory=str(_dist / "assets"), check_dir=False),
        name="frontend-assets",
    )

    _dist_resolved = _dist.resolve()

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(request: Request, full_path: str) -> FileResponse:
        """SPA fallback: serve a real static file if it exists on disk (e.g. favicon,
        manifest), otherwise fall back to index.html so client-side routes like
        /login or /reconciliation are handled by the React router instead of 404ing.

        Registered after the API routers, so it only matches requests none of them
        claimed. Note this means a GET on a POST-only API path (e.g. GET
        /reconciliation/run) falls through to this handler and returns index.html
        rather than a 405 — Starlette matches routes on path+method together, so this
        route's full match wins over the real route's path-only partial match. This
        is a known, accepted trade-off of the SPA-fallback pattern, not a bug.

        `full_path` is untrusted and must never be joined onto `_dist` without a
        containment check: percent-encoded dot-segments (e.g. `%2e%2e/%2e%2e/etc/hosts`)
        or a leading slash from a `//`-prefixed path (Path('/a') / '/etc/passwd' ==
        Path('/etc/passwd'), pathlib discards the left side) can otherwise escape the
        served directory entirely.
        """
        candidate = (_dist / full_path).resolve()
        if full_path and candidate.is_file() and candidate.is_relative_to(_dist_resolved):
            return FileResponse(candidate)
        return FileResponse(_dist / "index.html")
