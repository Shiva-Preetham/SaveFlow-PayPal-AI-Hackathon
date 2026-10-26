import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import models  # noqa: F401  (registers tables on Base)
from app.config import get_settings
from app.db import Base, engine
from app.paypal.client import PayPalError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Render's free disk resets, so the schema (and later the demo seed) is rebuilt on every start.
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="SaveFlow", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[get_settings().frontend_origin],
                   allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(PayPalError)
async def paypal_error_handler(request: Request, exc: PayPalError) -> JSONResponse:
    # Show PayPal's debug_id, never a traceback.
    return JSONResponse(status_code=502, content={
        "error": "paypal_error", "name": exc.name, "message": exc.message, "debug_id": exc.debug_id})


@app.get("/api/health")
def health() -> dict:
    s = get_settings()
    return {"status": "ok", "paypal_configured": s.paypal_configured, "gemini_configured": s.gemini_configured}
