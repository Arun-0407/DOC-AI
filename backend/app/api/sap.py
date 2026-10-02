import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.api.deps import get_current_user
from app.config import settings
from app.database import get_db
from app.models.document import Document
from app.models.project import Project
from app.models.upload import Upload
from app.models.user import User
from app.services import sap_doc_api
from app.services.doc_generator import run_generation
from app.services.sap_doc_api import (
    SapDocApiError,
    _call_with_creds,
    _normalize_pattern,
    search_objects_wildcard,
)
from app.services.sap_repo_builder import build_repository_graph, build_source_from_graph
from app.utils.file_utils import detect_abap_type
from app.utils.sap_extractor import SAPObjectExtractor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sap", tags=["SAP"])

extractor = SAPObjectExtractor()

TYPE_ALIASES = {
    "program": "PROG",
    "class": "CLAS",
    "interface": "INTF",
    "function": "FUNC",
    "function_group": "FUGR",
    "smartform": "SSFO",
    "table": "TABL",
    "cds": "DDLS",
    "transaction": "TRAN",
}


class SAPBuildGraphRequest(BaseModel):
    object_name: str
    object_type: Optional[str] = None
    project_id: str


class SAPBuildGraphResponse(BaseModel):
    upload_id: str
    object_name: str
    object_type: str
    programs: int
    includes: int
    classes: int
    methods: int
    function_modules: int
    tables: int
    data_elements: int
    domains: int
    cds_views: int
    smart_forms: int
    transactions: int
    dependencies: int
    total_objects: int
    source_chars: int


class SAPGenerateRequest(BaseModel):
    object_name: str
    object_type: Optional[str] = None
    project_id: str
    upload_id: Optional[str] = None  # pre-built graph upload; skips SAP read when set


class SAPGenerateResponse(BaseModel):
    document_id: str
    upload_id: str
    object_name: str
    object_count: int
    source_chars: int
    message: str


class SAPHealthResponse(BaseModel):
    ok: bool
    message: str
    host: str
    configured: bool


class SAPSearchResult(BaseModel):
    name: str
    object_type: str
    description: str
    package: str


class SAPObjectPreview(BaseModel):
    name: str
    object_type: str
    description: str
    package: str
    created_by: str
    created_date: str
    changed_by: str
    changed_date: str
    includes: list[str]
    dependencies: list[dict]
    has_source: bool
    source_preview: str


class SAPValidateResponse(BaseModel):
    ok: bool
    message: str


def to_http_error(exc: SapDocApiError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=str(exc))


def _sap_creds(
    x_sap_user: Optional[str] = Header(default=None, alias="X-SAP-User"),
    x_sap_password: Optional[str] = Header(default=None, alias="X-SAP-Password"),
    x_sap_url: Optional[str] = Header(default=None, alias="X-SAP-Url"),
    x_sap_client: Optional[str] = Header(default=None, alias="X-SAP-Client"),
) -> dict:
    """
    Resolve SAP credentials for a single request.

    Priority order (header > env):
    - sap_url    : X-SAP-Url header  → SAP_DOC_API_URL env
    - sap_user   : X-SAP-User header → SAP_DOC_API_USER env
    - sap_password: X-SAP-Password header → SAP_DOC_API_PASSWORD env
    - sap_client : X-SAP-Client header → SAP_DOC_API_CLIENT env

    This allows the frontend SAP Connect Manager to supply a custom URL/client
    without requiring a server restart (e.g. when connecting manually to a
    non-default SAP system).
    """
    sap_url = x_sap_url or settings.SAP_DOC_API_URL
    if not sap_url:
        raise HTTPException(
            status_code=503,
            detail="SAP URL is not configured. Provide X-SAP-Url header or set SAP_DOC_API_URL in server config.",
        )

    # Header takes priority; env values are the fallback.
    user = x_sap_user or settings.SAP_DOC_API_USER
    password = x_sap_password or settings.SAP_DOC_API_PASSWORD

    if not user or not password:
        raise HTTPException(
            status_code=401,
            detail=(
                "SAP credentials are required. "
                "Provide X-SAP-User and X-SAP-Password request headers."
            ),
        )
    return {
        "sap_url": sap_url,
        "sap_user": user,
        "sap_password": password,
        "sap_client": x_sap_client or settings.SAP_DOC_API_CLIENT,
    }


async def _sap_call(creds: dict, params: dict, timeout: float) -> dict | list:
    return await _call_with_creds(
        params,
        sap_url=creds["sap_url"],
        sap_user=creds["sap_user"],
        sap_password=creds["sap_password"],
        sap_client=creds["sap_client"],
        verify_ssl=settings.SAP_DOC_API_VERIFY_SSL,
        timeout=timeout,
    )


@router.get("/health", response_model=SAPHealthResponse)
async def sap_health():
    """
    Returns whether the SAP URL in .env is reachable.
    SAP_DOC_API_URL is mandatory. SAP_DOC_API_USER/PASSWORD are optional.
    If no env credentials are configured the URL is still reported as
    configured — runtime credentials are supplied per-request via headers.
    """
    if not settings.SAP_DOC_API_URL:
        return SAPHealthResponse(ok=False, message="SAP_DOC_API_URL not configured", host="", configured=False)

    # Skip live ping when no env credentials — URL is configured, creds come at runtime.
    if not settings.SAP_DOC_API_USER or not settings.SAP_DOC_API_PASSWORD:
        return SAPHealthResponse(
            ok=True,
            message="URL configured — runtime credentials required per request",
            host=settings.SAP_DOC_API_URL,
            configured=True,
        )

    try:
        await sap_doc_api.search_objects("ZZZ")
        return SAPHealthResponse(ok=True, message="Connected", host=settings.SAP_DOC_API_URL, configured=True)
    except SapDocApiError as exc:
        return SAPHealthResponse(ok=False, message=str(exc), host=settings.SAP_DOC_API_URL, configured=True)


@router.post("/validate", response_model=SAPValidateResponse)
async def validate_sap_credentials(
    current_user: User = Depends(get_current_user),
    creds: dict = Depends(_sap_creds),
):
    """
    Test user-supplied SAP credentials by performing a lightweight search.
    Credentials arrive via X-SAP-URL / X-SAP-User / X-SAP-Password headers
    and are never persisted — they exist only for this request.
    """
    try:
        await _sap_call(creds, {"action": "search", "q": "ZZZ"}, timeout=15)
        return SAPValidateResponse(ok=True, message="SAP credentials are valid")
    except SapDocApiError as exc:
        return SAPValidateResponse(ok=False, message=str(exc))


@router.post("/build-graph", response_model=SAPBuildGraphResponse)
async def build_graph(
    request: SAPBuildGraphRequest,
    current_user: User = Depends(get_current_user),
    creds: dict = Depends(_sap_creds),
    db: AsyncSession = Depends(get_db),
):
    """
    Step 1 of the new generation flow.

    Reads the complete SAP repository graph for the given object,
    stores it as an Upload record (parsed_metadata.repository_graph),
    and returns a summary with counts of all retrieved sub-objects.

    Does NOT create a Document or start AI generation.
    The returned upload_id must be passed to POST /sap/generate to skip
    the SAP read phase and go straight to AI documentation.
    """
    name = request.object_name.strip().upper()
    if not name:
        raise HTTPException(status_code=400, detail="object_name is required")

    try:
        project_id = UUID(request.project_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid project_id")

    project = (await db.execute(select(Project).filter(Project.id == project_id))).scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    object_type = request.object_type or "PROG"
    logger.info("Building repository graph for %s (%s)", name, object_type)

    try:
        graph = await build_repository_graph(name, object_type, creds=creds)
    except SapDocApiError as exc:
        raise to_http_error(exc)

    if graph.get("error") and not graph.get("sourceCode"):
        raise HTTPException(status_code=502, detail=f"SAP read failed: {graph['error']}")

    # Flatten graph to concatenated source so the extractor still works
    content = build_source_from_graph(graph)
    filename = f"{name}.abap"
    file_type = detect_abap_type(content, filename)

    # Count methods across all classes
    total_methods = sum(
        len(cls.get("methods", [])) for cls in graph.get("classes", [])
    )

    metadata = extractor.extract(content, file_type, filename)
    metadata.update({
        "source": "sap_api",
        "s4hana_live": True,
        "s4hana_object_name": name,
        "s4hana_object_type": graph.get("objectType", object_type),
        "s4hana_main_program": graph.get("object", name),
        "s4hana_includes": [inc.get("object", "") for inc in graph.get("includes", [])],
        "s4hana_dependencies": [
            {"type": d.get("objectType"), "name": d.get("objectName"), "relation": d.get("relation")}
            for d in graph.get("dependencies", [])
        ],
        "s4hana_fields": graph.get("fields", []),
        "repository_graph": graph,
    })

    upload = Upload(
        project_id=project_id,
        filename=filename,
        file_type=file_type,
        file_size=len(content.encode("utf-8")),
        content=content,
        parsed_metadata=metadata,
        uploaded_by=current_user.id,
    )
    db.add(upload)
    await db.commit()
    await db.refresh(upload)
    logger.info("Repository graph stored as upload %s (%d chars)", upload.id, len(content))

    return SAPBuildGraphResponse(
        upload_id=str(upload.id),
        object_name=name,
        object_type=graph.get("objectType", object_type),
        programs=1,
        includes=len(graph.get("includes", [])),
        classes=len(graph.get("classes", [])),
        methods=total_methods,
        function_modules=len(graph.get("functionModules", [])),
        tables=len(graph.get("tables", [])),
        data_elements=len(graph.get("dataElements", [])),
        domains=len(graph.get("domains", [])),
        cds_views=len(graph.get("cdsViews", [])),
        smart_forms=len(graph.get("smartForms", [])),
        transactions=len(graph.get("transactions", [])),
        dependencies=len(graph.get("dependencies", [])),
        total_objects=(
            1
            + len(graph.get("includes", []))
            + len(graph.get("classes", []))
            + len(graph.get("functionModules", []))
            + len(graph.get("tables", []))
            + len(graph.get("cdsViews", []))
        ),
        source_chars=len(content),
    )


@router.get("/search", response_model=list[SAPSearchResult])
async def search_sap_objects(
    q: str,
    type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    creds: dict = Depends(_sap_creds),
):
    """
    SAP-style wildcard search.

    Supported patterns (SAP SE80 conventions):
        Z*           all objects starting with Z
        ZSD*         prefix match
        *INVOICE*    contains match
        Z*GST*       multi-wildcard
        *PRINT       suffix match

    A bare string without '*' is treated as a prefix (ZSD → ZSD*).
    Minimum 2 characters before the first wildcard.
    Returns up to 100 results, sorted by object name.
    """
    pattern = _normalize_pattern(q)
    base = pattern.replace("*", "").replace("?", "")
    if len(base) < 2:
        raise HTTPException(
            status_code=400,
            detail="Enter at least 2 characters (e.g. Z*, ZSD*, *INVOICE*)",
        )

    type_filter: list[str] | None = None
    if type:
        mapped = TYPE_ALIASES.get(type.lower(), type.upper())
        type_filter = [mapped]

    try:
        hits = await search_objects_wildcard(pattern, type_filter, creds=creds, max_results=100)
    except SapDocApiError as exc:
        raise to_http_error(exc)

    return [
        SAPSearchResult(
            name=hit.get("objectName", ""),
            object_type=hit.get("objectType", ""),
            description=hit.get("description", ""),
            package=hit.get("package", ""),
        )
        for hit in hits
        if hit.get("objectName")
    ]


@router.get("/suggest", response_model=list[SAPSearchResult])
async def suggest_sap_objects(
    q: str,
    current_user: User = Depends(get_current_user),
    creds: dict = Depends(_sap_creds),
):
    """
    Lightweight autocomplete — returns up to 10 results quickly.
    Used for the search input dropdown while the user is typing.
    Only searches programs and SmartForms for speed.
    """
    pattern = _normalize_pattern(q)
    base = pattern.replace("*", "")
    if len(base) < 2:
        return []

    try:
        hits = await search_objects_wildcard(
            pattern,
            types=["PROG", "SSFO", "CLAS", "FUNC"],
            creds=creds,
            max_results=10,
        )
    except SapDocApiError:
        return []

    return [
        SAPSearchResult(
            name=hit.get("objectName", ""),
            object_type=hit.get("objectType", ""),
            description=hit.get("description", ""),
            package=hit.get("package", ""),
        )
        for hit in hits
        if hit.get("objectName")
    ]


@router.get("/objects/{object_name:path}", response_model=SAPObjectPreview)
async def preview_sap_object(
    object_name: str,
    current_user: User = Depends(get_current_user),
    creds: dict = Depends(_sap_creds),
):
    name = object_name.strip().upper()
    try:
        detail = await _sap_call(creds, {"action": "read", "object": name}, timeout=settings.SAP_DOC_API_TIMEOUT)
    except SapDocApiError as exc:
        raise to_http_error(exc)

    if isinstance(detail, dict) and detail.get("objectType") == "UNKNOWN":
        raise HTTPException(status_code=404, detail=f"Object {name} not found in SAP")

    source = detail.get("sourceCode", "")
    preview = source[:600] + ("\n..." if len(source) > 600 else "")

    return SAPObjectPreview(
        name=name,
        object_type=detail.get("objectType", ""),
        description="",
        package="",
        created_by="",
        created_date="",
        changed_by="",
        changed_date="",
        includes=[inc.get("name", "") for inc in detail.get("includes", [])],
        dependencies=[
            {"type": d.get("objectType", ""), "name": d.get("objectName", "")}
            for d in detail.get("dependencies", [])
        ],
        has_source=bool(source),
        source_preview=preview,
    )


@router.post("/generate", response_model=SAPGenerateResponse)
async def generate_from_sap(
    request: SAPGenerateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    creds: dict = Depends(_sap_creds),
    db: AsyncSession = Depends(get_db),
):
    """
    Start AI document generation.

    Two modes:
    A) upload_id provided — repository graph was already built by POST /sap/build-graph.
       Load the existing Upload, skip SAP entirely, go straight to generation.
    B) upload_id absent — legacy mode: build graph from SAP then generate.
    """
    name = request.object_name.strip().upper()
    if not name:
        raise HTTPException(status_code=400, detail="object_name is required")

    try:
        project_id = UUID(request.project_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid project_id")

    project = (await db.execute(select(Project).filter(Project.id == project_id))).scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # ── Mode A: pre-built graph upload ────────────────────────────────
    if request.upload_id:
        try:
            pre_upload_id = UUID(request.upload_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid upload_id")

        upload = (await db.execute(select(Upload).filter(Upload.id == pre_upload_id))).scalars().first()
        if not upload:
            raise HTTPException(status_code=404, detail="Pre-built graph upload not found")

        metadata = upload.parsed_metadata or {}
        graph = metadata.get("repository_graph", {})
        object_count = (
            1
            + len(graph.get("includes", []))
            + len(graph.get("classes", []))
            + len(graph.get("functionModules", []))
            + len(graph.get("cdsViews", []))
            + len(graph.get("tables", []))
        )
        logger.info(
            "Using pre-built graph upload %s for %s (%d objects)",
            upload.id, name, object_count,
        )

    else:
        # ── Mode B: build graph now (legacy / direct flow) ─────────────
        object_type = request.object_type or "PROG"
        logger.info("Building repository graph for %s (%s)", name, object_type)
        try:
            graph = await build_repository_graph(name, object_type, creds=creds)
        except SapDocApiError as exc:
            raise to_http_error(exc)

        if graph.get("error") and not graph.get("sourceCode"):
            raise HTTPException(status_code=502, detail=f"SAP read failed: {graph['error']}")

        content = build_source_from_graph(graph)
        if not content:
            try:
                detail = await _sap_call(creds, {"action": "read", "object": name}, timeout=settings.SAP_DOC_API_TIMEOUT)
            except SapDocApiError as exc:
                raise to_http_error(exc)
            content = sap_doc_api.build_source(detail)
            graph["sourceCode"] = detail.get("sourceCode", "")

        filename = f"{name}.abap"
        file_type = detect_abap_type(content, filename)
        metadata = extractor.extract(content, file_type, filename)
        includes = graph.get("includes", [])
        dependencies = graph.get("dependencies", [])
        object_count = (
            1 + len(includes) + len(graph.get("classes", []))
            + len(graph.get("functionModules", [])) + len(graph.get("cdsViews", []))
            + len(graph.get("tables", []))
        )
        metadata.update({
            "source": "sap_api", "s4hana_live": True,
            "s4hana_object_name": name,
            "s4hana_object_type": graph.get("objectType", object_type),
            "s4hana_main_program": graph.get("object", name),
            "s4hana_generated_fm": "",
            "s4hana_object_count": object_count,
            "s4hana_includes": [inc.get("object", "") for inc in includes],
            "s4hana_dependencies": [
                {"type": d.get("objectType"), "name": d.get("objectName"), "relation": d.get("relation")}
                for d in dependencies
            ],
            "s4hana_fields": graph.get("fields", []),
            "repository_graph": graph,
        })
        upload = Upload(
            project_id=project_id, filename=filename, file_type=file_type,
            file_size=len(content.encode("utf-8")), content=content,
            parsed_metadata=metadata, uploaded_by=current_user.id,
        )
        db.add(upload)
        await db.commit()
        await db.refresh(upload)

    document = Document(
        project_id=project_id,
        upload_id=upload.id,
        title=f"{name} - Technical Documentation",
        status="queued",
        generation_step="Queued",
        generated_by=current_user.id,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    background_tasks.add_task(run_generation, document.id, current_user.id)
    logger.info("Generation queued for %s, document %s", name, document.id)

    return SAPGenerateResponse(
        document_id=str(document.id),
        upload_id=str(upload.id),
        object_name=name,
        object_count=object_count,
        source_chars=len(upload.content or ""),
        message="Generation started from pre-built repository graph." if request.upload_id
                else "Repository graph built and generation started.",
    )


# ─────────────────────────────────────────────────────────────────────────────
# NEW: Enhanced S/4HANA Connection & Object Browser endpoints
# Inspired by ABAPInspector S4Panel — adds Destination & Manual connection modes
# ─────────────────────────────────────────────────────────────────────────────

import base64
import json
import httpx as _httpx


class SAPConnectionEnvResponse(BaseModel):
    """Detect runtime environment for smart connection UI."""
    onBTP: bool
    hasDestService: bool
    configured_url: str
    configured_client: str


class SAPDestinationConnectRequest(BaseModel):
    """Connect via BTP Destination Service."""
    destinationName: str
    client: Optional[str] = None
    sccLocationId: Optional[str] = None
    host: Optional[str] = None


class SAPManualConnectRequest(BaseModel):
    """Connect manually with explicit host + credentials."""
    host: str
    client: str = "100"
    user: str
    password: str
    virtualHost: Optional[str] = None
    sccLocationId: Optional[str] = None


class SAPConnectResponse(BaseModel):
    ok: bool
    message: str
    sessionToken: Optional[str] = None
    displayInfo: Optional[dict] = None


class SAPObjectBrowseRequest(BaseModel):
    """Browse SAP objects by type and wildcard pattern."""
    object_type: str = "PROG"
    search_query: str = "Z*"
    max_results: int = 50


class SAPObjectBrowseResult(BaseModel):
    name: str
    object_type: str
    description: str
    package: str


class SAPReadAllRequest(BaseModel):
    """Read a SAP object + ALL its dependencies."""
    object_name: str
    object_type: str = "PROG"


class SAPDepItem(BaseModel):
    name: str
    type: str
    lines: int
    error: Optional[str] = None
    source: str = ""


class SAPReadAllResponse(BaseModel):
    object_name: str
    object_type: str
    main_lines: int
    main_source: str
    deps: list[SAPDepItem]
    total_lines: int
    combined_source: str


# Maps frontend object-type key -> TADIR type code used by search_objects_wildcard
_BROWSE_TYPE_MAP = {
    "PROG": "PROG",
    "FUGR": "FUGR",
    "SSFO": "SSFO",
    "CLAS": "CLAS",
    "ENHO": "ENHO",
    "FUNC": "FUNC",
    "INTF": "INTF",
    "TABL": "TABL",
    "DDLS": "DDLS",
}


@router.get("/connection-env", response_model=SAPConnectionEnvResponse)
async def sap_connection_env(
    current_user: User = Depends(get_current_user),
):
    """
    Detect runtime environment so the UI can decide which connection mode to show.
    Equivalent to ABAPInspector /api/s4/env.
    """
    on_btp = bool(settings.BTP_CLIENT_ID and settings.BTP_TOKEN_URL)
    has_dest = bool(on_btp and getattr(settings, "SAP_BTP_DESTINATION_NAME", ""))
    return SAPConnectionEnvResponse(
        onBTP=on_btp,
        hasDestService=has_dest,
        configured_url=settings.SAP_DOC_API_URL or "",
        configured_client=settings.SAP_DOC_API_CLIENT or "100",
    )


@router.post("/connect-manual", response_model=SAPConnectResponse)
async def sap_connect_manual(
    request: SAPManualConnectRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Validate manual SAP connection (host + user + password).
    Analogous to ABAPInspector handleConnect with useDestination=false.
    """
    host = request.host.strip().rstrip("/")
    if not host.startswith("http"):
        host = f"https://{host}"
    sap_url = host if "/sap/bc/zdoc" in host else f"{host}/sap/bc/zdoc"

    try:
        async with _httpx.AsyncClient(timeout=20, verify=settings.SAP_DOC_API_VERIFY_SSL) as client:
            resp = await client.get(
                sap_url,
                params={"action": "search", "q": "ZZZ", "sap-client": request.client},
                auth=(request.user, request.password),
            )
    except _httpx.TimeoutException:
        return SAPConnectResponse(ok=False, message="Connection timed out.")
    except _httpx.HTTPError as exc:
        return SAPConnectResponse(ok=False, message=f"Could not reach SAP: {exc}")

    messages = {
        401: "Invalid SAP credentials.",
        403: "User lacks S_DEVELOP display authorization.",
        404: "ICF service /sap/bc/zdoc is not active.",
    }
    if resp.status_code != 200:
        return SAPConnectResponse(
            ok=False,
            message=messages.get(resp.status_code, f"SAP returned HTTP {resp.status_code}."),
        )

    display_info = {
        "host": request.host,
        "virtualHost": request.virtualHost or "",
        "client": request.client,
        "user": request.user,
        "sccLocationId": request.sccLocationId or "",
        "sap_url": sap_url,
    }
    token_payload = json.dumps({"user": request.user, "client": request.client, "sap_url": sap_url})
    session_token = base64.urlsafe_b64encode(token_payload.encode()).decode()

    return SAPConnectResponse(
        ok=True,
        message=f"Connected to {request.host} as {request.user}",
        sessionToken=session_token,
        displayInfo=display_info,
    )


@router.post("/connect-destination", response_model=SAPConnectResponse)
async def sap_connect_destination(
    request: SAPDestinationConnectRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Connect via SAP BTP Destination Service.
    Analogous to ABAPInspector handleConnect with useDestination=true.
    """
    if not settings.BTP_TOKEN_URL or not settings.BTP_CLIENT_ID:
        return SAPConnectResponse(
            ok=False,
            message="BTP is not configured on this server (missing BTP_TOKEN_URL / BTP_CLIENT_ID).",
        )

    dest_name = request.destinationName.strip()
    if not dest_name:
        return SAPConnectResponse(ok=False, message="destinationName is required.")

    # Step 1 — obtain BTP access token
    try:
        async with _httpx.AsyncClient(timeout=15) as token_client:
            token_resp = await token_client.post(
                settings.BTP_TOKEN_URL,
                data={"grant_type": "client_credentials"},
                auth=(settings.BTP_CLIENT_ID, settings.BTP_CLIENT_SECRET),
            )
        if token_resp.status_code != 200:
            return SAPConnectResponse(
                ok=False,
                message=f"Could not obtain BTP token (HTTP {token_resp.status_code}).",
            )
        access_token = token_resp.json().get("access_token", "")
    except _httpx.HTTPError as exc:
        return SAPConnectResponse(ok=False, message=f"BTP token endpoint error: {exc}")

    # Step 2 — resolve destination URL
    dest_service_url = getattr(settings, "SAP_BTP_DESTINATION_SERVICE_URL", "")
    sap_url = ""
    dest_user = ""
    dest_password = ""

    if dest_service_url:
        try:
            async with _httpx.AsyncClient(timeout=15) as dest_client:
                dest_resp = await dest_client.get(
                    f"{dest_service_url}/destinations/{dest_name}",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
            if dest_resp.status_code == 200:
                dest_cfg = dest_resp.json().get("destinationConfiguration", {})
                sap_url = dest_cfg.get("URL", "")
                if sap_url and "/sap/bc/zdoc" not in sap_url:
                    sap_url = sap_url.rstrip("/") + "/sap/bc/zdoc"
                dest_user = dest_cfg.get("User", "")
                dest_password = dest_cfg.get("Password", "")
        except _httpx.HTTPError:
            pass

    if not sap_url and request.host:
        h = request.host.strip().rstrip("/")
        if not h.startswith("http"):
            h = f"https://{h}"
        sap_url = f"{h}/sap/bc/zdoc"

    if not sap_url:
        return SAPConnectResponse(
            ok=False,
            message=f"Could not resolve destination '{dest_name}'. Provide the host manually.",
        )

    # Step 3 — validate connectivity
    client_val = request.client or settings.SAP_DOC_API_CLIENT or "100"
    try:
        async with _httpx.AsyncClient(timeout=20, verify=settings.SAP_DOC_API_VERIFY_SSL) as chk:
            kwargs: dict = {"params": {"action": "search", "q": "ZZZ", "sap-client": client_val}}
            if dest_user and dest_password:
                kwargs["auth"] = (dest_user, dest_password)
            else:
                kwargs["headers"] = {"Authorization": f"Bearer {access_token}"}
            chk_resp = await chk.get(sap_url, **kwargs)
    except _httpx.TimeoutException:
        return SAPConnectResponse(ok=False, message="SAP via destination timed out.")
    except _httpx.HTTPError as exc:
        return SAPConnectResponse(ok=False, message=f"Could not reach SAP via destination: {exc}")

    if chk_resp.status_code not in (200, 204):
        return SAPConnectResponse(
            ok=False,
            message=f"SAP returned HTTP {chk_resp.status_code} via destination '{dest_name}'.",
        )

    display_info = {
        "destinationName": dest_name,
        "sccLocationId": request.sccLocationId or "",
        "client": client_val,
        "sap_url": sap_url,
        "user": dest_user or "(destination auth)",
    }
    token_payload = json.dumps({
        "user": dest_user or "__destination__",
        "client": client_val,
        "sap_url": sap_url,
        "destination": dest_name,
    })
    session_token = base64.urlsafe_b64encode(token_payload.encode()).decode()

    return SAPConnectResponse(
        ok=True,
        message=f"Connected via destination '{dest_name}'",
        sessionToken=session_token,
        displayInfo=display_info,
    )


@router.post("/browse-objects")
async def sap_browse_objects(
    request: SAPObjectBrowseRequest,
    current_user: User = Depends(get_current_user),
    creds: dict = Depends(_sap_creds),
):
    """
    Browse SAP objects by type and wildcard pattern.
    Supports PROG, FUGR, SSFO, CLAS, ENHO (BADIs/Enhancements).
    search_objects_wildcard uses positional args: (pattern, types, creds, max_results).
    Results carry SAP API keys: objectName, objectType, description, package.
    """
    obj_type = request.object_type.upper()
    query_pattern = _normalize_pattern(request.search_query.strip() or "Z*")

    # Resolve to TADIR code; fall back to the raw value (e.g. user typed "PROG" directly)
    tadir_type = _BROWSE_TYPE_MAP.get(obj_type, obj_type)

    try:
        results = await search_objects_wildcard(
            query_pattern,
            types=[tadir_type],           # list of TADIR codes
            creds=creds,
            max_results=min(request.max_results, 200),
        )
    except SapDocApiError as exc:
        raise to_http_error(exc)

    # search_objects_wildcard returns dicts with SAP API keys:
    #   objectName, objectType, description, package
    return [
        SAPObjectBrowseResult(
            name=r.get("objectName", r.get("name", "")),
            object_type=r.get("objectType", r.get("object_type", obj_type)),
            description=r.get("description", ""),
            package=r.get("package", ""),
        )
        for r in results
        if r.get("objectName") or r.get("name")  # skip empty entries
    ]


@router.post("/read-all", response_model=SAPReadAllResponse)
async def sap_read_all(
    request: SAPReadAllRequest,
    current_user: User = Depends(get_current_user),
    creds: dict = Depends(_sap_creds),
):
    """
    Read a SAP object + ALL its dependencies (includes, classes, FMs, smartforms)
    in a single call. Inspired by ABAPInspector handleFetchDeps.
    Returns individual sources + combined source ready for AI documentation.
    """
    name = request.object_name.strip().upper()
    obj_type = request.object_type.upper()
    if not name:
        raise HTTPException(status_code=400, detail="object_name is required")

    try:
        graph = await build_repository_graph(name, obj_type, creds=creds)
    except SapDocApiError as exc:
        raise to_http_error(exc)

    main_source = graph.get("sourceCode", "")
    main_lines = len(main_source.splitlines()) if main_source else 0

    def _items(bucket: list, dep_type: str) -> list[SAPDepItem]:
        out = []
        for obj in bucket:
            src = obj.get("sourceCode", "")
            err = obj.get("error", "")
            out.append(SAPDepItem(
                name=obj.get("object", ""),
                type=dep_type,
                lines=len(src.splitlines()) if src else 0,
                error=err if err else None,
                source=src,
            ))
        return out

    dep_items: list[SAPDepItem] = []
    dep_items += _items(graph.get("includes", []), "INCLUDE")
    dep_items += _items(graph.get("classes", []), "CLASS")
    dep_items += _items(graph.get("functionModules", []), "FUNCTION_MODULE")
    dep_items += _items(graph.get("smartForms", []), "SMARTFORM")
    dep_items += _items(graph.get("cdsViews", []), "CDS_VIEW")

    combined = build_source_from_graph(graph)
    total_lines = len(combined.splitlines()) if combined else 0

    return SAPReadAllResponse(
        object_name=name,
        object_type=obj_type,
        main_lines=main_lines,
        main_source=main_source,
        deps=dep_items,
        total_lines=total_lines,
        combined_source=combined,
    )