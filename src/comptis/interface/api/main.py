from fastapi import FastAPI

from comptis.interface.api.auth.router import router as auth_router

app = FastAPI(title="Comptis API", version="0.1.0")

app.include_router(auth_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
