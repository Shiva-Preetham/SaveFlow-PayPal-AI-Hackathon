import asyncio
import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app import models  # noqa: F401  (registers tables on Base)
from app.api.routes import router
from app.config import REPO_ROOT, get_settings
from app.db import Base, SessionLocal, engine
from app.paypal.client import PayPalError
from app.services import catalogue
from app.services.retention import RetentionError, resume_due
from app.services.seed import seed
from app.services.state import InvalidTransition

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("saveflow")
STATUS = {"paypal_catalogue": "not synced yet"}
FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"


def reset_database() -> None:
    """Render's free disk resets anyway, so the demo DB is rebuilt and re-seeded on every start."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed(db)
    if get_settings().sync_catalogue_on_start:
        threading.Thread(target=_sync_catalogue, daemon=True).start()


def _sync_catalogue() -> None:
    with SessionLocal() as db:
        STATUS["paypal_catalogue"] = catalogue.sync_with_paypal(db)
    log.info(STATUS["paypal_catalogue"])


async def _resume_loop() -> None:
    while True:
        await asyncio.sleep(60)
        try:
            with SessionLocal() as db:
                if n := resume_due(db):
                    log.info("Resumed %d paused subscription(s)", n)
        except Exception:  # keep the scheduler alive, but never silently
            log.exception("Scheduled resume failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    reset_database()
    task = asyncio.create_task(_resume_loop())
    yield
    task.cancel()


app = FastAPI(title="SaveFlow", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[get_settings().frontend_origin],
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(router)


@app.exception_handler(PayPalError)
async def paypal_error_handler(request: Request, exc: PayPalError) -> JSONResponse:
    # Show PayPal's debug_id, never a traceback.
    return JSONResponse(status_code=502, content={
        "error": "paypal_error", "name": exc.name, "message": exc.message, "debug_id": exc.debug_id,
        "issues": [d.get("issue") for d in exc.details]})


@app.exception_handler(RetentionError)
@app.exception_handler(InvalidTransition)
async def conflict_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=409, content={"error": "conflict", "message": str(exc)})


@app.exception_handler(Exception)
async def unexpected_handler(request: Request, exc: Exception) -> JSONResponse:
    log.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"error": "internal_error",
                                                  "message": "Something went wrong; it has been logged."})


@app.get("/api/health")
def health() -> dict:
    s = get_settings()
    return {"status": "ok", "paypal_configured": s.paypal_configured, "gemini_configured": s.gemini_configured,
            "paypal_catalogue": STATUS["paypal_catalogue"]}


if FRONTEND_DIST.exists():  # production: one service serves the built React app too
    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(404)
        file = (FRONTEND_DIST / path).resolve()
        if path and file.is_file() and FRONTEND_DIST.resolve() in file.parents:
            return FileResponse(file)
        return FileResponse(FRONTEND_DIST / "index.html")
