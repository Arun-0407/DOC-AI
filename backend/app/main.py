import asyncio
import logging
import os
import socket
import subprocess
import sys
import time
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api import auth, chat, documents, export, projects, sap, search, uploads
from app.api import settings as settings_api
from app.config import settings
from app.database import Base, engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

bridge_process: subprocess.Popen | None = None


def start_rfc_bridge() -> None:
    global bridge_process

    script = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "sap_rfc_bridge.js"))
    if not os.path.exists(script):
        logger.warning("RFC bridge script not found: %s", script)
        return

    try:
        with socket.create_connection(("127.0.0.1", settings.SAP_BRIDGE_PORT), timeout=1):
            logger.info("RFC bridge already running on port %s", settings.SAP_BRIDGE_PORT)
            return
    except OSError:
        pass

    log_path = os.path.join(os.path.dirname(script), "sap_rfc_bridge.log")
    try:
        # Open is kept open intentionally: the Popen child writes to it for its
        # entire lifetime. Python's GC closes the fd when bridge_process is
        # garbage-collected; we accept that trade-off here.
        log_file = open(log_path, "a", encoding="utf-8")  # noqa: WPS515
        bridge_process = subprocess.Popen(
            ["node", script],
            cwd=os.path.dirname(script),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        logger.info("RFC bridge started, pid %s", bridge_process.pid)
    except OSError as exc:
        logger.warning("Could not start RFC bridge: %s", exc)


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("AI engine: %s", "BTP AI Core" if settings.btp_enabled else "OpenAI")
    logger.info("SAP Doc API: %s", settings.SAP_DOC_API_URL or "not configured")

    if settings.SAP_RFC_ENABLED:
        await asyncio.get_running_loop().run_in_executor(None, start_rfc_bridge)

    yield

    if bridge_process and bridge_process.poll() is None:
        bridge_process.terminate()


app = FastAPI(
    title="DOC AI API",
    version="1.0.0",
    redirect_slashes=False,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Accept",
        "X-SAP-User",
        "X-SAP-Password",
        "X-SAP-Url",
        "X-SAP-Client",
    ],
)

for module in (auth, projects, uploads, documents, export, chat, search, settings_api, sap):
    app.include_router(module.router)


async def check_database() -> dict:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"ok": True, "message": "Connected"}
    except Exception as exc:
        return {"ok": False, "message": str(exc)[:120]}


async def check_ai_engine() -> dict:
    if settings.btp_enabled and settings.BTP_TOKEN_URL:
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                resp = await client.post(
                    settings.BTP_TOKEN_URL,
                    data={"grant_type": "client_credentials"},
                    auth=(settings.BTP_CLIENT_ID, settings.BTP_CLIENT_SECRET),
                )
            ok = resp.status_code == 200
            return {"ok": ok, "configured": True, "engine": "btp",
                    "message": "Token obtained" if ok else f"HTTP {resp.status_code}"}
        except httpx.HTTPError as exc:
            return {"ok": False, "configured": True, "engine": "btp", "message": str(exc)[:120]}

    if settings.OPENAI_API_KEY:
        return {"ok": True, "configured": True, "engine": "openai", "message": settings.OPENAI_MODEL}

    return {"ok": False, "configured": False, "engine": None, "message": "No AI engine configured"}


async def check_sap_doc_api() -> dict:
    # SAP_DOC_API_URL is the only mandatory setting.
    if not settings.SAP_DOC_API_URL:
        return {"ok": False, "configured": False, "message": "SAP_DOC_API_URL not configured"}

    # Health ping requires credentials. If env credentials are absent, we skip
    # the live ping — the URL is configured and runtime creds come from headers.
    user = settings.SAP_DOC_API_USER
    password = settings.SAP_DOC_API_PASSWORD
    if not user or not password:
        return {
            "ok": True,
            "configured": True,
            "message": "URL configured — runtime credentials required per request",
        }

    errors = {
        401: "Invalid SAP user or password",
        403: "Missing S_DEVELOP display authorization",
        404: "ICF service not active",
    }
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=10, verify=settings.SAP_DOC_API_VERIFY_SSL) as client:
            resp = await client.get(
                settings.SAP_DOC_API_URL,
                params={"action": "search", "q": "ZZZ", "sap-client": settings.SAP_DOC_API_CLIENT},
                auth=(user, password),
            )
    except httpx.TimeoutException:
        return {"ok": False, "configured": True, "message": "Timeout"}
    except httpx.HTTPError as exc:
        return {"ok": False, "configured": True, "message": str(exc)[:120]}

    elapsed = int((time.perf_counter() - started) * 1000)
    if resp.status_code == 200:
        return {"ok": True, "configured": True, "message": f"Reachable ({elapsed} ms)"}
    return {"ok": False, "configured": True,
            "message": errors.get(resp.status_code, f"HTTP {resp.status_code}")}


@app.get("/api/health")
async def health():
    database, ai_engine, sap_doc_api = await asyncio.gather(
        check_database(), check_ai_engine(), check_sap_doc_api()
    )
    return {
        "status": "ok" if database["ok"] else "degraded",
        "version": app.version,
        "checks": {
            "database": database,
            "ai_engine": ai_engine,
            "sap_doc_api": sap_doc_api,
        },
        "sap_rfc_enabled": settings.SAP_RFC_ENABLED,
        "sap_adt_enabled": settings.SAP_ADT_ENABLED,
    }